# KV BQK - Central Bank of The Republic of Kosovo (DECD-6109)
# Generated from KV_BQK_v2.ipynb - keep the two in sync.

#------------------------------------------------ Import Lib ----------------------------------------
import re
import os
import difflib
import datetime
import requests
import pandas as pd
import pdfplumber
from bs4 import BeautifulSoup
from time import sleep
from urllib.parse import urljoin

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

#------------------------------------------------ Begin_fileName ----------------------------------------

regulatorName = 'KV BQK' ## change to current controller name

print(f"Running {regulatorName} Web Scraping Tool v.1.0")

now = datetime.datetime.now()

filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":", ".")[:-7])

try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__)) ## production environment (.py)
except NameError:
    scriptfolder = os.getcwd() ## notebook environment

os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder') # PDF is downloaded here, deleted after parsing

if os.path.exists(tempfolder):
    for rem in os.listdir(tempfolder):
        os.remove(os.path.join(tempfolder, rem))
else:
    os.mkdir(tempfolder)


# %%
#------------------------------------------------ Begin_Dict ----------------------------------------

sqldict={'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
          'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
          'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
          'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
          'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
          'Phone - Mother company': []}

# All six lists live in one PDF ("Lists of licensed/registered financial institutions") linked on this page
regdict = {
    'KV BQK 1': 'https://bqk-kos.org/mbikeqyrja-financiare/institucionet-financiare-te-licencuara-2/?lang=en',
    'KV BQK 3': 'https://bqk-kos.org/mbikeqyrja-financiare/institucionet-financiare-te-licencuara-2/?lang=en',
    'KV BQK 4': 'https://bqk-kos.org/mbikeqyrja-financiare/institucionet-financiare-te-licencuara-2/?lang=en',
    'KV BQK 5': 'https://bqk-kos.org/mbikeqyrja-financiare/institucionet-financiare-te-licencuara-2/?lang=en',
    'KV BQK 8': 'https://bqk-kos.org/mbikeqyrja-financiare/institucionet-financiare-te-licencuara-2/?lang=en',
    'KV BQK 9': 'https://bqk-kos.org/mbikeqyrja-financiare/institucionet-financiare-te-licencuara-2/?lang=en',
}

Typology = {
    'KV BQK 1': 'Commercial Banks',
    'KV BQK 3': 'Licensed Insurance Companies',
    'KV BQK 4': 'Micro Finance Institutions',
    'KV BQK 5': 'Non Banks Financial Institutions',
    'KV BQK 8': 'Licensed Insurance Intermediaries',
    'KV BQK 9': 'Pension Funds',
}

# ListLabel = 1 for bank lists, 2 for insurance, 3 for bank & insurance, 4 for everything else
ListLabelDict = {
    'KV BQK 1': '1',
    'KV BQK 3': '2',
    'KV BQK 4': '4',
    'KV BQK 5': '4',
    'KV BQK 8': '2',
    'KV BQK 9': '4',
}

# PDF section heading -> regdict key (None = excluded per Jira DECD-6109)
SECTION_MAP = {
    'Banks licensed': 'KV BQK 1',
    'MFIs registered': 'KV BQK 4',
    'NBFIs registered': 'KV BQK 5',
    'NBFIs registered with the activity: Currency Exchange': None,   # Do not collect (ticket)
    'Crypto-asset service operator (CASO) Licensed': None,           # not requested in ticket
    'Insurers licensed': 'KV BQK 3',
    'Insurance brokers licensed': 'KV BQK 8',
    'Individual Brokers in insurance': None,                         # Do not collect (ticket)
    'PENSION FUNDS': 'KV BQK 9',
}

SUBHEADINGS_SKIP = {
    'List of licensed/registered Financial Institutions',
    'Brokerage and claims handling companies in insurance',
}

processdate = now.strftime('%Y-%m-%d')

#------------------------------------------------ Begin_Fouction ----------------------------------------

def bourange_same_length_array(sqldict):
    maxlen = len(sqldict['ListProcessDate'])
    for key, val in sqldict.items():
        if len(sqldict[key]) != maxlen:
            empty = []
            total_empty = maxlen - len(sqldict[key])
            for i in range(total_empty):
                empty.append('')
            sqldict[key] = sqldict[key] + empty
    return sqldict


# %%
#------------------------------------------------ Begin_Download ----------------------------------------
# Find the "Lists of licensed/registered financial institutions" PDF link (filename is date-stamped) and download it.
# bqk-kos.org sits behind Cloudflare: plain requests works from some networks but gets 403 from the production
# machine, so on any requests failure we fall back to DrissionPage (real Chrome) - same approach as DO SSDO / CW CBCSCW.

page_url = regdict['KV BQK 1']
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

dp = None
try:
    resp = requests.get(page_url, headers=headers, timeout=60, verify=False)
    resp.raise_for_status()
    page_html = resp.text
    fetch_mode = 'requests'
except Exception as e:
    print('[WARN] requests failed ({}); falling back to DrissionPage (Cloudflare)'.format(e))
    from DrissionPage import ChromiumPage, ChromiumOptions
    opt = ChromiumOptions().headless(False)  # Cloudflare challenge does not clear in headless mode
    opt.set_download_path(tempfolder)
    opt.set_pref('plugins.always_open_pdf_externally', True)
    dp = ChromiumPage(opt)
    dp.get(page_url)
    waited = 0
    while waited < 120:
        sleep(3)
        waited += 3
        if 'Just a moment' not in dp.title:
            break
    if 'Just a moment' in dp.title:
        raise RuntimeError('Cloudflare challenge not bypassed; rerun to retry.')
    page_html = dp.html
    fetch_mode = 'drission'

print('[INFO] page fetched via', fetch_mode)

soup = BeautifulSoup(page_html, 'lxml')

pdf_url = ''
pdf_href_raw = ''
for a in soup.find_all('a', href=True):
    href = a['href']
    text = a.get_text(' ', strip=True).lower()
    # in the browser-rendered DOM the site JS appends ?lang=en to the href, so strip query/fragment first
    href_path = href.lower().split('?')[0].split('#')[0]
    if href_path.endswith('.pdf') and ('lists of licensed' in text or re.search(r'lista-e-institucioneve-financiare', href, re.I)):
        pdf_href_raw = href
        pdf_url = urljoin(page_url, href)
        break

if not pdf_url:
    raise RuntimeError('PDF link "Lists of licensed/registered financial institutions" not found on the page - check the site layout')

print('[INFO] PDF link:', pdf_url)

# list validity date from the date-stamped filename, e.g. ...09.07.2026-ENG.pdf
m = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', pdf_url)
validitydate = '{}-{}-{}'.format(m.group(3), m.group(2), m.group(1)) if m else ''
print('[INFO] ListValidityDate:', validitydate)

pdf_path = os.path.join(tempfolder, 'kv_bqk_list.pdf')
if fetch_mode == 'requests':
    r = requests.get(pdf_url, headers=headers, timeout=120, verify=False)
    r.raise_for_status()
    with open(pdf_path, 'wb') as f:
        f.write(r.content)
    print('[INFO] downloaded {} bytes -> {}'.format(len(r.content), pdf_path))
else:
    # browser-native download: Cloudflare blocks requests' TLS fingerprint, so download inside Chrome
    link_ele = dp.ele('xpath://a[@href="{}"]'.format(pdf_href_raw), timeout=10)
    if not link_ele:
        link_ele = dp.ele('xpath://a[contains(@href, ".pdf")]', timeout=10)
    mission = link_ele.click.to_download(tempfolder, 'kv_bqk_list.pdf')
    mission.wait()
    if mission.final_path:
        pdf_path = str(mission.final_path)
    print('[INFO] downloaded via browser ->', pdf_path)
    dp.quit()


# %%
#------------------------------------------------ Begin_Parse_Function ----------------------------------------

ENTITY_RE = re.compile(r'^(\d{1,3})\.(?!\d)\s*(\S.*)$')
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
URL_RE = re.compile(r'(?:https?://\S+|www\.\S+)', re.I)
LABEL_RE = re.compile(
    r'^(tel[\s:./]|tel$|telefoni|phone|mob[\s:.]|call centre|fax|web[\s:]|web$|website|'
    r'e-?mail|email|^mail:|contact:|client services|central office|general:|complaints|toll free)', re.I)
PHONEISH_RE = re.compile(r'^[+(\s]*\d[\d\s()/,.;+&-]*$')
PHONE_LABEL_RE = re.compile(r'^(tel|telefoni|phone|mob|call centre|client services|central office)', re.I)
ZIP_CITY_RE = re.compile(r'\b(\d{5,6})\b[,\s]*([^,\d]+?)(?:,|$)')
CITY_ZIP_RE = re.compile(r'([A-Za-z\u00eb\u00cb\u00e7\u00c7\u00fc.\- ]{3,}?)\s+(\d{5,6})\b')
ACTIVITY_RE = re.compile(r'^(Activity|Veprimtaria):\s*(.*)$', re.I)
SCOPE_RE = re.compile(r'^(Insurance Broker for the product|Intermediary in)', re.I)
QUOTED_NAME_RE = re.compile(r'^[\u201c"\u00ab][^\u201d"\u00bb]+[\u201d"\u00bb]$')
LIQUIDATOR_RE = re.compile(r'(likuidator|liquidator)', re.I)


def get_lines(pdf_path):
    lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            for ln in text.split('\n'):
                ln = re.sub(r'\s+', ' ', ln).strip()
                if ln:
                    lines.append(ln)
    return lines


def split_sections(lines):
    sections = []
    current_key, current_lines = 'PREAMBLE', []
    for ln in lines:
        if ln in SECTION_MAP:
            sections.append((current_key, current_lines))
            current_key, current_lines = SECTION_MAP[ln], []
        elif ln in SUBHEADINGS_SKIP:
            continue
        else:
            current_lines.append(ln)
    sections.append((current_key, current_lines))
    return sections


def split_entities(section_lines):
    # entity blocks start at "N. Name"; an unnumbered leading block (e.g. ICM Co & Services) is kept too
    blocks, current, preamble = [], None, []
    for ln in section_lines:
        m = ENTITY_RE.match(ln)
        if m:
            if current:
                blocks.append(current)
            elif preamble:
                blocks.append(('', preamble))
                preamble = []
            current = (m.group(1), [m.group(2)])
        elif current:
            current[1].append(ln)
        else:
            preamble.append(ln)
    if current:
        blocks.append(current)
    elif preamble:
        blocks.append(('', preamble))
    return blocks


def is_addressish(ln):
    if re.match(r'^(str|rr|rruga|st)[.\s\u201c"]', ln, re.I):
        return True
    if re.search(r'\b\d{5}\b', ln):
        return True
    if re.search(r'(square|neighbourhood|boulevard|bulevardi|no\.|n\.n|nn\.)', ln, re.I):
        return True
    return False


def norm_for_match(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def clean_url(u):
    return u.strip().rstrip('/,;.')


def parse_block(number, lines):
    block_text = ' '.join(lines)
    ent = {'number': number, 'name': '', 'activity': '', 'address': [],
           'phone': '', 'fax': '', 'web': '', 'email': '', 'zip': '', 'city': ''}

    # ---- name ----
    if number == '':
        # unnumbered block: name wraps over leading lines until address/labels start
        name_lines, rest, in_name = [], [], True
        for ln in lines:
            if in_name and not (is_addressish(ln) or LABEL_RE.match(ln)):
                name_lines.append(ln)
            else:
                in_name = False
                rest.append(ln)
    else:
        name_lines, rest = [lines[0]], lines[1:]
        # quoted-only continuation line belongs to the name (e.g. N.T.SH. "Eurokoha-Reisen")
        while rest and QUOTED_NAME_RE.match(rest[0]):
            name_lines.append(rest.pop(0))
    ent['name'] = ' '.join(name_lines).strip()

    # ---- field extraction ----
    activity_parts, last_was_activity = [], False
    for ln in rest:
        m = ACTIVITY_RE.match(ln)
        if m:
            activity_parts.append(m.group(2).strip().rstrip(';'))
            last_was_activity = True
            continue
        if SCOPE_RE.match(ln) or ln.startswith('- '):
            activity_parts.append(ln.lstrip('- ').rstrip(':;'))
            last_was_activity = True
            continue
        # wrapped activity continuation (lowercase start, not an address line)
        if last_was_activity and re.match(r'^[a-z\u00e7]', ln) and not is_addressish(ln) and not LABEL_RE.match(ln):
            activity_parts[-1] = activity_parts[-1].rstrip(',') + ', ' + ln.rstrip(';,')
            continue
        last_was_activity = False
        if LIQUIDATOR_RE.search(ln):
            continue
        if LABEL_RE.match(ln) or PHONEISH_RE.match(ln):
            for seg in ln.split('|'):
                seg = seg.strip()
                if not seg:
                    continue
                if not ent['fax'] and re.match(r'^fax', seg, re.I):
                    ent['fax'] = re.sub(r'^fax[.:\s&]*', '', seg, flags=re.I).strip().rstrip(';,')
                elif not ent['phone'] and PHONE_LABEL_RE.match(seg):
                    val = re.sub(r'^[a-z\u00e7\u00eb&./ ]*[:.]\s*', '', seg, flags=re.I).strip().rstrip(';,')
                    ent['phone'] = val
            continue
        # pure email / pure URL lines are contacts, not address
        if EMAIL_RE.search(ln) and len(EMAIL_RE.sub('', ln).strip(' ,;|')) == 0:
            continue
        if URL_RE.match(ln) and len(URL_RE.sub('', ln).strip(' ,;|-')) <= 2:
            continue
        # line that just repeats the entity name (PDF duplication)
        if difflib.SequenceMatcher(None, norm_for_match(ln), norm_for_match(ent['name'])).ratio() > 0.75:
            continue
        ent['address'].append(ln)

    ent['activity'] = '; '.join(p for p in activity_parts if p)

    emails = EMAIL_RE.findall(block_text)
    ent['email'] = emails[0] if emails else ''
    no_mail = EMAIL_RE.sub('', block_text)
    m = re.search(r'Web(?:site)?\s*:?\s*(\S+)', no_mail, re.I)
    if m and ('.' in m.group(1)):
        ent['web'] = clean_url(m.group(1))
    else:
        m = URL_RE.search(no_mail)
        ent['web'] = clean_url(m.group(0)) if m else ''

    def _clean_city(c):
        c = re.sub(r'\b(kosovo|kosova|kosov\u00eb|republic of|republika e)\b.*$', '', c, flags=re.I)
        return c.strip(' ,.-\u201c\u201d"')

    addr_text = ' '.join(ent['address'])
    city = ''
    mz = ZIP_CITY_RE.search(addr_text)
    if mz:
        ent['zip'], city = mz.group(1), _clean_city(mz.group(2))
    if not city:
        mz = CITY_ZIP_RE.search(addr_text)
        if mz:
            city = _clean_city(mz.group(1))
            ent['zip'] = ent['zip'] or mz.group(2)
    if not city:
        mz = re.search(r'([^,\d]{3,}?),\s*(?:Republic of\s+|Republika e\s+)?Kosov', addr_text, re.I)
        if mz:
            tail = mz.group(1).split(',')[-1].strip()
            city = _clean_city(tail.split()[-1]) if tail else ''
    ent['city'] = city
    return ent


# %%
#------------------------------------------------ Begin_Main ----------------------------------------

lines = get_lines(pdf_path)
sections = split_sections(lines)

for key, sec_lines in sections:
    if key == 'PREAMBLE' or key is None:
        continue
    blocks = split_entities(sec_lines)
    rows_before = len(sqldict['Name'])
    for num, blines in blocks:
        ent = parse_block(num, blines)
        if not ent['name']:
            continue
        sqldict['Name'].append(ent['name'])
        sqldict['ListLabel'].append(ListLabelDict[key])
        sqldict['License_Type'].append(ent['activity'])
        sqldict['Address_1'].append(ent['address'][0] if ent['address'] else '')
        sqldict['Address_2'].append(' '.join(ent['address'][1:]))
        sqldict['City'].append(ent['city'])
        sqldict['Zip'].append(ent['zip'])
        sqldict['Cntry'].append('KV')
        sqldict['Phone'].append(ent['phone'])
        sqldict['Fax'].append(ent['fax'])
        sqldict['Website'].append(ent['web'])
        sqldict['Email'].append(ent['email'])
        sqldict['RegulationType'].append('Regulated')
        sqldict['RegCtry'].append(key.split()[0])
        sqldict['RegCode'].append(key.split()[1])
        sqldict['ListCode'].append(key.split()[2])
        sqldict['ListLanguage'].append('EN')
        sqldict['ListValidityDate'].append(validitydate)
        sqldict['ListName'].append(Typology[key])
        sqldict['ListProcessDate'].append(processdate)
        sqldict = bourange_same_length_array(sqldict)
    print('[INFO] {} ({}): {} rows'.format(key, Typology[key], len(sqldict['Name']) - rows_before))

print('[INFO] total rows:', len(sqldict['Name']))


# %%
#------------------------------------------------ Begin_Save ----------------------------------------

os.chdir(scriptfolder)
df = pd.DataFrame(sqldict)

df = df[df['Name'] != '']

df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)

print('Saved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))

# clean tempfolder (downloaded PDF)
for rem in os.listdir(tempfolder):
    os.remove(os.path.join(tempfolder, rem))
print('[INFO] tempfolder cleaned')
