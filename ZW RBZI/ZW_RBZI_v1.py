# ------------------------------------------------ Import Lib ----------------------------------------
import os
import re
import time
import datetime
import json
from collections import Counter

import requests
import pandas as pd
import pdfplumber
from DrissionPage import ChromiumPage, ChromiumOptions

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ------------------------------------------------ Begin_ fileName ----------------------------------------
regulatorName = 'ZW RBZI'  # Reserve Bank of Zimbabwe

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

tempfolder = os.path.join(scriptfolder, 'tempfolder')  # source files are downloaded here before parsing
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


# ------------------------------------------------ Lists (from Jira DECD-6328) ----------------------------------------
# ListNr | ListName                                              | source page
#   1    | List of Operating Banking Institutions                | .../banking-institutions
#   2    | List of Registered Microfinance Institutions          | .../micro-finance-institutions
#   3    | List of Licensed Money Transfer agents and Bureaux    | .../authorised-dealers-with-limited-authority
#        | de Change ("Licenced Institutions for the Year 2026") |
regdict = {
    1: {"ListName": "List of Operating Banking Institutions",
        "PageURL": "https://www.rbz.co.zw/index.php/regulation-supervision/regulation-supervision/banking-institutions",
        "FileURL": "https://www.rbz.co.zw/documents/bank_sup/Operating_Banking_Institutes/Consolidated_Website_Information_-_January_2026.pdf",
        "Comments": "Click on download and extract all entities from the PDF"},
    2: {"ListName": "List of Registered Microfinance Institutions",
        "PageURL": "https://www.rbz.co.zw/index.php/regulation-supervision/regulation-supervision/micro-finance-institutions",
        "FileURL": "https://www.rbz.co.zw/documents/bank_sup/Registered_Microfinance_/LIST_OF_REGISTERED_MICROFINANCE_INSTIUTIIONS_AS_AT_31_MARCH_2026.pdf",
        "Comments": "Click on download and extract all entities from the PDF"},
    3: {"ListName": "List of Licensed Money Transfer agents and Bureaux de Change",
        "PageURL": "https://www.rbz.co.zw/index.php/regulation-supervision/capital-flows-management/authorised-dealers-with-limited-authority",
        "FileURL": "https://www.rbz.co.zw/documents/Regulations_Acts/2026/ADLA/LICENCED_INSTITUTIONS_FOR_YEAR_2026_1.xlsx",
        "Comments": "NEW LIST! Click on 'Licenced Institutions for the Year 2026' to open the Excel file and extract all entities."},
}

# ------------------------------------------------ Download source files ----------------------------------------
# The site sits behind a Radware ("perfdrive") bot-management challenge - plain `requests` gets served a
# captcha page instead of the file. We open the referring page with DrissionPage (real Chrome) once to
# clear the challenge and collect its session cookies, then hand those cookies to a `requests.Session`
# to pull the 3 files directly (same pattern as the Cloudflare-gated PG BPNG / PW PFIC sites, adapted
# because here the files themselves - not the listing page - need the passed challenge).
opt = ChromiumOptions().auto_port()
dp = ChromiumPage(opt)
try:
    dp.get(regdict[1]["PageURL"])
    time.sleep(4)
    cookies = dp.cookies().as_dict()
    ua = dp.user_agent
finally:
    dp.quit()

session = requests.Session()
for k, v in cookies.items():
    session.cookies.set(k, v)
headers = {"User-Agent": ua, "Referer": "https://www.rbz.co.zw/"}

src_paths = {}
for code, meta in regdict.items():
    ext = os.path.splitext(meta["FileURL"])[1]
    path = os.path.join(tempfolder, f'list{code}{ext}')
    r = session.get(meta["FileURL"], headers=headers, timeout=120, verify=False)
    r.raise_for_status()
    with open(path, 'wb') as f:
        f.write(r.content)
    src_paths[code] = path
    print(f"Downloaded list {code}: {len(r.content)} bytes -> {os.path.basename(path)}")

# ------------------------------------------------ Parsing helpers - shared ----------------------------------------
def clean(s):
    return re.sub(r'\s+', ' ', s or '').strip(' ,;.:-').strip()


ZW_CITIES = ['Harare', 'Bulawayo', 'Mutare', 'Gweru', 'Kwekwe', 'Masvingo', 'Chinhoyi',
             'Marondera', 'Bindura', 'Victoria Falls', 'Chitungwiza', 'Kadoma', 'Chegutu']


def guess_city(text):
    for c in ZW_CITIES:
        if re.search(r'\b' + re.escape(c) + r'\b', text, re.I):
            return c
    return ''


# ------------------------------------------------ List 1: Operating Banking Institutions (PDF) ----------------------------------------
# Layout: a "business-card" profile PDF - one institution per section, each section headed by a
# 14.0pt institution-name heading, followed by ~11pt label:value lines (Name / Head Office / Contact
# Details / Website and Social Media / Type of Bank / Date of Establishment / History / Ownership).
# Label and value columns are NOT vertically synchronised per rendered line (e.g. the "Contact
# Details" label can visually coincide with the tail of the previous field's wrapped value), so fields
# are extracted from content-anchored index ranges + regex, not fixed line-by-line pairing (same
# approach as PW_PFIC / PG_BPNG: identify by regex/content, not position).
def cluster_lines(words, tol=4):
    words = sorted(words, key=lambda w: w['top'])
    lines, cur, last_top = [], [], None
    for w in words:
        if last_top is not None and w['top'] - last_top > tol:
            lines.append(cur)
            cur = []
        cur.append(w)
        last_top = w['top']
    if cur:
        lines.append(cur)
    out = []
    for line in lines:
        line_sorted = sorted(line, key=lambda w: w['x0'])
        out.append({'top': min(w['top'] for w in line), 'words': line_sorted,
                     'text': ' '.join(w['text'] for w in line_sorted),
                     'size': round(max(w.get('size', 0) for w in line), 1)})
    return out


def label_of(l):
    return ' '.join(w['text'] for w in l['words'] if w['x0'] < 200).strip()


def value_of(l):
    return ' '.join(w['text'] for w in l['words'] if w['x0'] >= 200).strip()


EMAIL_RE = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
TERM = r'(?=(Fax\s*:|Email\s*:|E-?mail\s*:|T\s*el(?:ephone)?\s*:|Skype|Website|Contact Details|\(Physical|\(Postal|Toll\s*free|Cell\s*:|WhatsApp|VoIP|SIP|$))'
TEL_RE = re.compile(r'T\s*el(?:ephone)?\s*:\s*(.*?)' + TERM, re.I)
FAX_RE = re.compile(r'Fax\s*:\s*(.*?)' + TERM, re.I)
POBOX_RE = re.compile(r'P\.?\s*O\.?\s*[Bb]ox\s*\d+[^.]*?(?=(Tel|Fax|Email|E-?mail|Telephone|$))', re.I)
BOILERPLATE = [
    re.compile(r'\(Physical[^)]*\)?', re.I),
    re.compile(r'\(Postal[^)]*\)?', re.I),
    re.compile(r'Telephones,\s*Fax,\s*E-?Mail,?\s*Skype\)?', re.I),
    re.compile(r'\(Facebook[^)]*\)?', re.I),
    re.compile(r'Postal Address', re.I),
    re.compile(r'Skype\s*:\s*\S*', re.I),
    re.compile(r'\bN/A\b', re.I),
]


def parse_list1(pdf_path):
    all_lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            all_lines.extend(cluster_lines(page.extract_words(extra_attrs=['size'])))

    # institution boundaries via 14.0pt heading lines; the very first is the document title, not a bank
    heading_idxs = [i for i, l in enumerate(all_lines) if l['size'] == 14.0][1:]
    boundaries = heading_idxs + [len(all_lines)]

    results = []
    for bi in range(len(heading_idxs)):
        block = all_lines[heading_idxs[bi]:boundaries[bi + 1]]
        heading_text = block[0]['text']

        def find(labels):
            for i, l in enumerate(block):
                if label_of(l).lower().rstrip(')') in labels:
                    return i
            return None

        idx_name = find({'name'})
        idx_head = find({'head office'})
        idx_web = find({'website and social media', 'website & social media'})
        idx_type = find({'type of bank'})
        idx_date = find({'date of establishment'})
        idx_hist = find({'history'})
        idx_own = find({'ownership'})

        name = value_of(block[idx_name]) if idx_name is not None else heading_text

        office_end = idx_web if idx_web is not None else (idx_type if idx_type is not None else idx_hist)
        office_blob = ' '.join(l['text'] for l in block[idx_head:office_end]) if idx_head is not None and office_end else ''

        email_m = EMAIL_RE.search(office_blob)
        tel_m = TEL_RE.search(office_blob)
        fax_m = FAX_RE.search(office_blob)
        pobox_m = POBOX_RE.search(office_blob)

        addr_remainder = office_blob
        for m in (email_m, tel_m, fax_m, pobox_m):
            if m:
                addr_remainder = addr_remainder.replace(m.group(0), ' ')
        addr_remainder = re.sub(r'\bHead Office\b', ' ', addr_remainder, flags=re.I)
        addr_remainder = re.sub(r'\bContact Details\b', ' ', addr_remainder, flags=re.I)
        for pat in BOILERPLATE:
            addr_remainder = pat.sub(' ', addr_remainder)

        website = ''
        if idx_web is not None:
            web_end = idx_type if idx_type is not None else idx_hist
            web_blob = ' '.join(l['text'] for l in block[idx_web:web_end])
            for pat in BOILERPLATE:
                web_blob = pat.sub(' ', web_blob)
            web_blob = re.sub(r'Website (and|&) Social Media', ' ', web_blob, flags=re.I)
            m = re.search(r'(https?://\S+|www\.\S+)', web_blob, re.I)
            website = m.group(1).strip(' ,;.') if m else ''

        results.append({
            'Name': clean(name),
            'Address_1': clean(addr_remainder),
            'Address_2': clean(pobox_m.group(0)) if pobox_m else '',
            'Phone': clean(tel_m.group(1)) if tel_m else '',
            'Fax': clean(fax_m.group(1)) if fax_m else '',
            'Email': email_m.group(0) if email_m else '',
            'Website': website,
            'License_Type': value_of(block[idx_type]) if idx_type is not None else '',
            'RegulationDate': value_of(block[idx_date]) if idx_date is not None else '',
            'Name - Mother Company': value_of(block[idx_own]) if idx_own is not None else '',
        })
    return results


# ------------------------------------------------ List 2: Registered Microfinance Institutions (PDF) ----------------------------------------
# Layout: a numbered two-column table (No. | Name | Head Office Address) spanning two sections -
# "CREDIT-ONLY MICROFINANCE INSTITUTIONS" (1-332) then "DEPOSIT TAKING MICROFINANCE INSTITUTIONS" (1-7) -
# where pdfplumber's extract_tables() silently drops rows straddling a page break. Rows are instead
# reconstructed from raw words: numbered "No." tokens in the left margin are anchors, every other word
# on the page is assigned to its nearest anchor by vertical distance (handles addresses wrapping both
# above and below their row), then split into name/address columns by an x0 threshold. Section
# transitions are tracked by the exact vertical position of the section-heading text (not just "does
# this page contain the heading"), since a heading can appear mid-page after several rows of the
# previous section. Header/heading text bleeding into the first/last row of a page or section is
# explicitly excluded.
NUM_RE = re.compile(r'^\d{1,3}$')
HEADER_WORDS = {'NO.', 'NO:', 'NO', 'NAME', 'HEAD', 'OFFICE', 'ADDRESS'}


def join_words_to_lines(ws):
    lines = {}
    for w in ws:
        t = round(w['top'])
        key = next((k for k in lines if abs(k - t) <= 4), None)
        if key is None:
            key = t
            lines[key] = []
        lines[key].append(w)
    return ' '.join(' '.join(w['text'] for w in sorted(lines[k], key=lambda w: w['x0'])) for k in sorted(lines))


def parse_list2(pdf_path):
    entries = []
    section = "CREDIT-ONLY MICROFINANCE INSTITUTIONS"
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            transitions, heading_tops = [], []
            for w in words:
                if w['text'].upper() == 'CREDIT-ONLY':
                    transitions.append((w['top'], "CREDIT-ONLY MICROFINANCE INSTITUTIONS"))
                    heading_tops.append(w['top'])
                if w['text'].upper() == 'DEPOSIT':
                    transitions.append((w['top'], "DEPOSIT TAKING MICROFINANCE INSTITUTIONS"))
                    heading_tops.append(w['top'])
            transitions.sort()

            def is_heading_row(top):
                return any(abs(top - ht) <= 2 for ht in heading_tops)

            anchors = [w for w in words if NUM_RE.match(w['text']) and w['x0'] < 60 and w['top'] < 760]
            if not anchors:
                for _, s in transitions:
                    section = s
                continue
            anchor_tops = [a['top'] for a in anchors]

            groups = {i: [] for i in range(len(anchors))}
            for w in words:
                if w in anchors or w['top'] >= 760 or is_heading_row(w['top']):
                    continue
                i = min(range(len(anchor_tops)), key=lambda k: abs(w['top'] - anchor_tops[k]))
                if w['top'] < anchor_tops[i] - 20:   # word sits >20pt above its nearest anchor -> stray header text
                    continue
                groups[i].append(w)

            ti = 0
            for i, a in enumerate(anchors):
                while ti < len(transitions) and transitions[ti][0] <= a['top']:
                    section = transitions[ti][1]
                    ti += 1
                gwords = [w for w in groups[i] if not (w['text'].upper().rstrip('.:') in HEADER_WORDS and w['top'] < a['top'])]
                name_words = sorted([w for w in gwords if w['x0'] < 310], key=lambda w: (round(w['top']), w['x0']))
                addr_words = sorted([w for w in gwords if w['x0'] >= 310], key=lambda w: (round(w['top']), w['x0']))
                entries.append((section, a['text'], join_words_to_lines(name_words), join_words_to_lines(addr_words)))
            while ti < len(transitions):
                section = transitions[ti][1]
                ti += 1
    return entries


# ------------------------------------------------ List 3: ADLA Licensed Institutions (XLSX) ----------------------------------------
# Layout: a single sheet, no header row object - row 7 is the doc title, row 8 the column headers
# (No. / Name of Institution / Licence Number), then 3 un-numbered tier-heading rows each followed by
# numbered entries (Tier 1: 1-24, Tier 2: 25-48, Tier 3: 49-72). Tier = License_Type.
def parse_list3(xlsx_path):
    raw = pd.read_excel(xlsx_path, sheet_name=0, header=None)
    results = []
    tier = ''
    for _, row in raw.iloc[9:].iterrows():
        no, name, licence = row[1], row[2], row[3]
        if pd.isna(no) and isinstance(name, str) and name.strip():
            tier = re.sub(r'^TIER\s*\d+\s*-\s*', '', name.strip(), flags=re.I)
            continue
        if pd.isna(name) or not str(name).strip():
            continue
        results.append({
            'Name': clean(str(name)),
            'License_Type': tier,
            'InternalID_1': clean(str(licence)) if not pd.isna(licence) else '',
        })
    return results


# ------------------------------------------------ Begin_ scraping ----------------------------------------
list1_rows = parse_list1(src_paths[1])
for r in list1_rows:
    sqldict['Name'].append(r['Name'])
    sqldict['Address_1'].append(r['Address_1'])
    sqldict['Address_2'].append(r['Address_2'])
    sqldict['City'].append(guess_city(r['Address_1']))
    sqldict['Phone'].append(r['Phone'])
    sqldict['Fax'].append(r['Fax'])
    sqldict['Email'].append(r['Email'])
    sqldict['Website'].append(r['Website'])
    sqldict['License_Type'].append(r['License_Type'])
    sqldict['RegulationDate'].append(r['RegulationDate'])
    sqldict['Name - Mother Company'].append(r['Name - Mother Company'])
    sqldict['Cntry'].append('ZW')
    sqldict['RegulationType'].append('Regulated')
    sqldict['ListName'].append(regdict[1]['ListName'])
    sqldict['ListLabel'].append(1)          # bank list
    sqldict['ListLanguage'].append('EN')
    sqldict['RegCtry'].append('ZW')
    sqldict['RegCode'].append('RBZI')
    sqldict['ListCode'].append(1)
    sqldict['ListProcessDate'].append(processdate)
sqldict = bourange_same_length_array(sqldict)
print(f"List 1 - {regdict[1]['ListName']}: {len(list1_rows)} entities")

list2_entries = parse_list2(src_paths[2])
for section, number, name, address in list2_entries:
    if not name.strip():
        continue
    sqldict['Name'].append(clean(name))
    sqldict['Address_1'].append(clean(address))
    sqldict['City'].append(guess_city(address))
    sqldict['License_Type'].append(section.title())
    sqldict['InternalID_1'].append(number)
    sqldict['Cntry'].append('ZW')
    sqldict['RegulationType'].append('Regulated')
    sqldict['ListName'].append(regdict[2]['ListName'])
    sqldict['ListLabel'].append(1)          # microfinance/deposit-taking institutions supervised by Bank Supervision division
    sqldict['ListLanguage'].append('EN')
    sqldict['RegCtry'].append('ZW')
    sqldict['RegCode'].append('RBZI')
    sqldict['ListCode'].append(2)
    sqldict['ListProcessDate'].append(processdate)
sqldict = bourange_same_length_array(sqldict)
print(f"List 2 - {regdict[2]['ListName']}: {len([e for e in list2_entries if e[2].strip()])} entities")

list3_rows = parse_list3(src_paths[3])
for r in list3_rows:
    sqldict['Name'].append(r['Name'])
    sqldict['License_Type'].append(r['License_Type'])
    sqldict['InternalID_1'].append(r['InternalID_1'])
    sqldict['Cntry'].append('ZW')
    sqldict['RegulationType'].append('Regulated')
    sqldict['ListName'].append(regdict[3]['ListName'])
    sqldict['ListLabel'].append(4)          # money transfer agents / bureaux de change - not bank/insurance
    sqldict['ListLanguage'].append('EN')
    sqldict['RegCtry'].append('ZW')
    sqldict['RegCode'].append('RBZI')
    sqldict['ListCode'].append(3)
    sqldict['ListProcessDate'].append(processdate)
sqldict = bourange_same_length_array(sqldict)
print(f"List 3 - {regdict[3]['ListName']}: {len(list3_rows)} entities")

# ------------------------------------------------ save df to excel ----------------------------------------
os.chdir(scriptfolder)
df = pd.DataFrame(sqldict)
df = df[df['Name'] != '']
df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)
print('Saved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))
