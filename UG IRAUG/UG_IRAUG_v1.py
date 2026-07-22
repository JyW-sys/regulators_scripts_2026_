# ------------------------------------------------ Import Lib ----------------------------------------
import os
import re
import datetime
import requests
import pandas as pd
import pdfplumber

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ------------------------------------------------ Begin_ fileName ----------------------------------------
regulatorName = 'UG IRAUG'  # Insurance Regulatory Authority of Uganda

print(f"Running {regulatorName} Web Scraping Tool v.1.0")

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":", ".")[:-7])

# ------ define the workspace path -----
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))  # production environment (.py)
except NameError:
    scriptfolder = os.getcwd()  # notebook environment
os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder')  # PDFs are downloaded here before parsing
if os.path.exists(tempfolder):
    for rem in os.listdir(tempfolder):
        os.remove(os.path.join(tempfolder, rem))
else:
    os.mkdir(tempfolder)

# ------------------------------------------------ sqldict (DO NOT CHANGE STRUCTURE) ----------------------------------------
sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}


def bourange_same_length_array(sqldict):
    maxlen = max(len(v) for v in sqldict.values())
    for key in sqldict:
        if len(sqldict[key]) != maxlen:
            sqldict[key].extend([''] * (maxlen - len(sqldict[key])))
    return sqldict


# ------------------------------------------------ Lists (ListCode -> (ListName, PDF URL, mode)) ----------------------------------------
# mode: 'uganda'  -> numbered two-column "business card" layout, name may wrap over a line
#       'foreign' -> numbered single-column list, single-line names
#       'dap'      -> un-numbered two-column layout (name line followed by an address line)
LISTS = {
    1: ('Licensed Insurance Companies',              'https://ira.go.ug/wp-content/uploads/2026/01/Licensed-Insurance-Companies.pdf', 'uganda'),
    2: ('Authorised Takaful Insurance Companies',    'https://ira.go.ug/wp-content/uploads/2026/01/Approved-Takful-Companies.pdf', 'uganda'),
    3: ('Authorised Insurance Brokers',              'https://ira.go.ug/wp-content/uploads/2026/06/AUTHORISED-INSURANCE-BROKERS-2.pdf', 'uganda'),
    4: ('Authorised Re-Insurance Companies',         'https://ira.go.ug/wp-content/uploads/2026/01/Approved-Re-Insurance-Companies.pdf', 'uganda'),
    5: ('Authorised Health Membership Organizations', 'https://ira.go.ug/wp-content/uploads/2026/01/Approved-HMOs.pdf', 'uganda'),
    6: ('Authorised Bancassurance Companies',        'https://ira.go.ug/wp-content/uploads/2026/01/Bancassurance.pdf', 'uganda'),
    7: ('DAP-Authorized Companies',                  'https://ira.go.ug/wp-content/uploads/2025/01/DAP-AUTHORISED.pdf', 'dap'),
    8: ('List of accredited foreign companies',      'https://ira.go.ug/wp-content/uploads/2026/07/LIST-OF-ACCREDITED-COMPANIES-2026-As-at-23RD-JUNE-2026-1.pdf', 'foreign'),
}

# ------------------------------------------------ Parsing helpers ----------------------------------------
MARK = re.compile(r'^\s*(\d+)\s*[.)]\s*')                       # entry marker "1." / "1)"
EMAIL_RE = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
# a line that starts the address / contact block (used to stop name capture)
ANCHOR = re.compile(r'^(P\.?\s*O\b|PO\b|P\s+O\b|Plot|Block|Ground|Room|Suite|Level|Wing|Floor|Next to|Opposite|Website|Web\b|website|Email|Emai|E-mail|Tel|Fax|Cell|Mob|\d)', re.I)
CONTACT = re.compile(r'^(Website|Web\b|website|Email|Emai|E-mail|Tel|Fax|Cell|Mob)', re.I)
# name is complete once it ends with one of these company-form suffixes
SUFFIX_END = re.compile(r'\b(Limited|Ltd|Plc|MDI)\b\.?[.,)\s]*$', re.I)
# in single-line 'foreign' mode, only a pure company-suffix line is appended to a name
SUFFIX_ONLY = re.compile(r'^(Limited|Ltd\.?|SMC Ltd|Company Ltd|Company Limited|Company|Plc|PLC|SE|LLP|LLC|\(U\)\s*Ltd|of Uganda)[.,]?$', re.I)


def clean(s):
    return re.sub(r'\s+', ' ', s).strip().strip('.,;').strip()


def col_texts(page, force2=False):
    """Return a list of columns; each column is a list of text lines in reading order.
    Two-column pages are split at the gutter just left of the right column's markers."""
    W = page.width
    words = page.extract_words()
    marks = [w['x0'] for w in words if MARK.match(w['text'])]
    rights = [x for x in marks if x > W * 0.45]
    if not (rights or force2):
        return [(page.extract_text() or "").split("\n")]
    split = (min(rights) - 10) if rights else W * 0.5
    left = (page.crop((0, 0, split, page.height)).extract_text() or "").split("\n")
    right = (page.crop((split, 0, W, page.height)).extract_text() or "").split("\n")
    return [[l for l in left if l.strip()], [l for l in right if l.strip()]]


def contacts(block):
    """Extract address / city / phone / email / website from an entity's detail lines."""
    txt = ' '.join(block)
    emails = EMAIL_RE.findall(txt)
    email = emails[0].strip(' ,;.') if emails else ''
    m = re.search(r'Web(?:site)?\s*[:.]?\s*((?:https?://)?[\w.-]+\.[a-z]{2,}[\w./-]*)', txt, re.I)
    website = m.group(1).strip(' ,;.') if m else ''
    phone = ''
    for l in block:
        mm = re.match(r'Tel\s*[:.]?\s*(.+)', l.strip(), re.I)
        if mm:
            phone = clean(mm.group(1))
            break
    addr_lines = [l for l in block if not CONTACT.match(l.strip()) and '@' not in l]
    address = clean(', '.join(addr_lines))
    city = 'Kampala' if re.search(r'\bKampala\b', address, re.I) else ''
    return address, city, phone, email, website


def parse_numbered(lines, mode):
    """Parse a single column of a numbered list into (name, address, city, phone, email, website)."""
    idxs = [i for i, l in enumerate(lines) if MARK.match(l)]
    out = []
    for j, i in enumerate(idxs):
        end = idxs[j + 1] if j + 1 < len(idxs) else len(lines)
        block = lines[i:end]
        first = MARK.sub('', block[0]).strip()
        rest = block[1:]
        if not first and rest:                      # marker sat alone on its line
            first = rest[0].strip()
            rest = rest[1:]
        name = first
        used = 0
        if mode == 'uganda':
            # append wrapped name lines until the name ends with a company suffix or an address begins
            while not SUFFIX_END.search(name) and used < len(rest):
                cc = rest[used].strip()
                if ANCHOR.match(cc) or '@' in cc:
                    break
                name += ' ' + cc
                used += 1
        else:  # foreign: single-line names, only append a pure company-suffix continuation
            while used < len(rest) and SUFFIX_ONLY.match(rest[used].strip()):
                name += ' ' + rest[used].strip()
                used += 1
        body = rest[used:]
        out.append((clean(name),) + contacts(body))
    return out


def parse_dap(cols):
    """Un-numbered layout: a name is a line that is immediately followed by an address line."""
    out = []
    for lines in cols:
        def is_name(k):
            l = lines[k].strip()
            nxt = lines[k + 1].strip() if k + 1 < len(lines) else ''
            return (bool(ANCHOR.match(nxt)) and not ANCHOR.match(l) and '@' not in l
                    and len(l.split()) >= 3 and not l.isupper() and 'DAP' not in l)
        nidx = [k for k in range(len(lines)) if is_name(k)]
        for j, i in enumerate(nidx):
            end = nidx[j + 1] if j + 1 < len(nidx) else len(lines)
            out.append((clean(lines[i]),) + contacts(lines[i + 1:end]))
    return out


# ------------------------------------------------ Download PDFs ----------------------------------------
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'}
pdf_paths = {}
for code, (listname, url, mode) in LISTS.items():
    path = os.path.join(tempfolder, f'list{code}.pdf')
    r = requests.get(url, headers=headers, verify=False, timeout=120)
    r.raise_for_status()
    with open(path, 'wb') as f:
        f.write(r.content)
    pdf_paths[code] = path
    print(f"Downloaded list {code}: {len(r.content)} bytes -> {os.path.basename(path)}")

# ------------------------------------------------ Begin_ scraping ----------------------------------------
for code, (listname, url, mode) in LISTS.items():
    rows = []
    with pdfplumber.open(pdf_paths[code]) as pdf:
        for page in pdf.pages:
            cols = col_texts(page, force2=(mode == 'dap'))
            if mode == 'dap':
                rows += parse_dap(cols)
            else:
                for col in cols:
                    rows += parse_numbered(col, mode)

    rows = [row for row in rows if row[0]]  # drop empty names
    for name, address, city, phone, email, website in rows:
        sqldict['Name'].append(name)
        sqldict['Address_1'].append(address)
        sqldict['City'].append(city)
        sqldict['Phone'].append(phone)
        sqldict['Email'].append(email)
        sqldict['Website'].append(website)
        sqldict['Cntry'].append('UG')
        sqldict['RegulationType'].append('Regulated')
        sqldict['ListName'].append(listname)
        sqldict['ListLabel'].append(2)          # insurance sector
        sqldict['ListLanguage'].append('EN')
        sqldict['RegCtry'].append('UG')
        sqldict['RegCode'].append('IRAUG')
        sqldict['ListCode'].append(code)
        sqldict['ListProcessDate'].append(processdate)
    sqldict = bourange_same_length_array(sqldict)
    print(f"List {code} - {listname}: {len(rows)} entities")

# ------------------------------------------------ save df to excel ----------------------------------------
os.chdir(scriptfolder)
df = pd.DataFrame(sqldict)
df = df[df['Name'] != '']
df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)
print('Saved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))
