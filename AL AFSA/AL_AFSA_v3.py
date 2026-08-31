#---- Begin_Librairie ----
# AL AFSA - Autoriteti i Mbikeqyrjes Financiare (Albanian Financial Supervisory Authority)
# Jira: DECD-6833
# Source: https://amf.gov.al  (static ASP pages, Bootstrap accordion "panel-group")
# No browser needed: every panel body is present in the initial HTML response.

import os
import re
import ssl
import datetime
import unicodedata

import requests
import pandas as pd
from bs4 import BeautifulSoup

requests.packages.urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context


#---- Begin_fileName ----
regulatorName = 'AL AFSA'

print("Running {} Web Scraping Tool v.3".format(regulatorName))

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":", ".")[:-7])

try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))  # production environment (.py)
except NameError:
    scriptfolder = os.getcwd()  # notebook environment

os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder')
if not os.path.exists(tempfolder):
    os.mkdir(tempfolder)


#---- Begin_Variable ----
regdict = {
    regulatorName + ' 1': 'https://amf.gov.al/ts_shoqeri_sigurimi.asp',
    regulatorName + ' 2': 'https://amf.gov.al/ts_shoqeri_risigurimi.asp',
    regulatorName + ' 3': 'https://amf.gov.al/tt_shoqeri_komisionere.asp',
    regulatorName + ' 4': 'https://amf.gov.al/tt_rregjistrar.asp',
    regulatorName + ' 5': 'https://amf.gov.al/tt_treg.asp',
    regulatorName + ' 6': 'https://amf.gov.al/tsik_fond.asp',
    regulatorName + ' 7': 'https://amf.gov.al/tsik_depositare.asp',
}

ListNameDict = {
    regulatorName + ' 1': 'List of "Insurance Companies"',
    regulatorName + ' 2': 'List of "Reinsurance Companies"',
    regulatorName + ' 3': 'List of "Brokerage Companies"',
    regulatorName + ' 4': 'List of "Registrars"',
    regulatorName + ' 5': 'List of "Regulated Markets"',
    regulatorName + ' 6': 'List of "Investment Funds"',
    regulatorName + ' 7': 'List of "Depository for Collective Investment Undertakings"',
}

# ListLabel: 1 = bank, 2 = insurance, 3 = bank & insurance, 4 = everything else.
# AFSA supervises insurance, private pensions and securities. Banks are the Bank of
# Albania's remit, so no list here is a bank list even when banks appear as members.
ListLabelDict = {
    regulatorName + ' 1': 2,   # insurance undertakings
    regulatorName + ' 2': 2,   # reinsurance undertakings
    regulatorName + ' 3': 4,   # investment-service firms (securities), some are banks
    regulatorName + ' 4': 4,   # securities registrar / central depository
    regulatorName + ' 5': 4,   # regulated market (stock exchange)
    regulatorName + ' 6': 4,   # collective investment undertakings
    regulatorName + ' 7': 4,   # depositaries for CIUs
}

# These 43 keys are fixed by the project spec. Do not add, remove or rename any of them.
sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}

SQL_KEYS = list(sqldict.keys())
assert len(SQL_KEYS) == 43, 'schema must have exactly 43 keys, got {}'.format(len(SQL_KEYS))

HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
    'Accept-Language': 'sq-AL,sq;q=0.9,en;q=0.8',
}

# Albanian administrative centres, used only to lift a City out of the free-text address.
AL_CITIES = ['Tiranë', 'Durrës', 'Vlorë', 'Shkodër', 'Elbasan', 'Korçë', 'Fier', 'Berat',
             'Lushnjë', 'Pogradec', 'Kavajë', 'Gjirokastër', 'Sarandë', 'Lezhë', 'Kukës',
             'Peshkopi', 'Krujë', 'Burrel', 'Laç', 'Patos', 'Kuçovë', 'Librazhd']

TEXT_COLS = ['InternalID_1', 'InternalID_2', 'InternalID_3', 'Zip', 'Phone', 'Fax',
             'Zip - Mother company', 'Phone - Mother company']


#---- Begin_Function ----
def norm(s):
    """Accent-stripped, whitespace-collapsed, lower-cased text for tolerant matching.

    AFSA's own editors spell the same label both 'Selise' and 'Selise' with/without the
    diacritic, so labels must never be compared with ==.
    """
    if s is None:
        return ''
    s = unicodedata.normalize('NFKD', str(s))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = s.replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', s).strip().lower()


def clean(s):
    """Collapse whitespace but keep Albanian diacritics intact for stored values."""
    if s is None:
        return ''
    s = unicodedata.normalize('NFKC', str(s)).replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', s).strip()


def decode_cfemail(enc):
    """Cloudflare obfuscates every mailto on this site as data-cfemail hex."""
    try:
        r = int(enc[:2], 16)
        return ''.join(chr(int(enc[i:i + 2], 16) ^ r) for i in range(2, len(enc), 2))
    except Exception:
        return ''


def get_soup(url):
    """Fetch with the corporate TLS proxy tolerated, and assert we got a real AFSA page."""
    resp = requests.get(url, headers=HEADERS, verify=False, timeout=60)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or 'utf-8'
    html = resp.text
    soup = BeautifulSoup(html, 'html.parser')
    # Liveness check that does not rely on response length: a soft-404 or a proxy error
    # page will not carry the accordion.
    if not soup.select('div.panel.panel-default'):
        raise RuntimeError('SKIPPED - no accordion panels found at {} (len={})'.format(url, len(html)))
    return soup


def field_lookup(fields, *keywords):
    """Substring match on accent-stripped labels; returns the first hit."""
    for kw in keywords:
        k = norm(kw)
        for label, value in fields.items():
            if k in norm(label):
                return value
    return ''


def parse_license(text):
    """Pull a licence/decision number and its date out of AFSA's free-text licence line.

    Examples seen live:
      'Nr. 5, datë 31.01.2022 (pa afat). Kjo Licencë zëvendëson Licencën ...'
      'Vendim Nr. 03, dt. 08.06.2000'
      'nr. 1 datë 13.12.2011 (pa afat)'
    """
    lic_no, lic_date = '', ''
    if not text:
        return lic_no, lic_date
    t = clean(text)
    m = re.search(r'(?:nr\.?|nr)\s*[:\s]*([0-9]+(?:/[0-9]+)?)', t, re.I)
    if m:
        lic_no = m.group(1).lstrip('0') or m.group(1)
    d = re.search(r'(\d{1,2})[./](\d{1,2})[./](\d{4})', t)
    if d:
        day, mon, yr = int(d.group(1)), int(d.group(2)), int(d.group(3))
        try:
            lic_date = datetime.date(yr, mon, day).strftime('%Y-%m-%d')
        except ValueError:
            lic_date = ''
    return lic_no, lic_date


def pick_city(address):
    a = norm(address)
    for c in AL_CITIES:
        if norm(c) in a:
            return c
    return ''


def split_phone(text):
    """Site merges telephone and fax into one 'Tel./Faks' cell with no separator marking
    which is which, so everything goes to Phone and Fax is left empty on purpose."""
    return clean(text), ''


def add_row(**kw):
    """Single writer for the fixed schema: appends to EVERY key, rejects unknown keys."""
    unknown = set(kw) - set(SQL_KEYS)
    if unknown:
        raise KeyError('unknown sqldict key(s): {}'.format(sorted(unknown)))
    for key in SQL_KEYS:
        sqldict[key].append(kw.get(key, ''))


def parse_panel(panel):
    """Return (name, {label: value}, body_text) for one accordion panel."""
    head = panel.find(['h4', 'h3'])
    name = clean(head.get_text(' ', strip=True)) if head else ''

    # De-obfuscate Cloudflare-protected e-mail addresses in place before reading text.
    for node in panel.select('[data-cfemail]'):
        node.replace_with(decode_cfemail(node.get('data-cfemail', '')))

    fields = {}
    for li in panel.find_all('li'):
        row = li.select_one('div.row')
        if not row:
            continue
        c3 = row.select_one('div.col-md-3')
        c9 = row.select_one('div.col-md-9')
        if c3 is None or c9 is None:
            continue
        label = clean(c3.get_text(' ', strip=True)).rstrip(':').strip()
        if label:
            fields[label] = clean(c9.get_text(' ', strip=True))

    body = panel.select_one('.panel-body')
    body_text = clean(body.get_text(' ', strip=True)) if body else ''
    return name, fields, body_text


def parse_fund_body(body_text):
    """List 6 panels carry no label/value rows, only a sentence of the shape
    'NEN ADMINISTRIMIN E <manager>. DEPOZITAR I FONDIT: <depositary>'."""
    manager, depositary = '', ''
    n = norm(body_text)
    m = re.search(r'nen administrimin e\s+(.*?)(?:\s*depozitar i fondit|$)', n)
    if m:
        # Map the normalised span back onto the original text to keep diacritics.
        start = m.start(1)
        manager = clean(body_text[start:start + len(m.group(1))]).strip(' .-–')
    d = re.search(r'depozitar i fondit\s*:?\s*(.*)$', n)
    if d:
        start = d.start(1)
        depositary = clean(body_text[start:start + len(d.group(1))]).strip(' .-–')
    return manager, depositary


#---- Begin_MainLoop ----
counts = {}

for reg, url in regdict.items():
    listcode = reg.split(' ')[-1]
    regcode = reg.split(' ')[1]
    listname = ListNameDict[reg]
    listlabel = ListLabelDict[reg]

    print('[INFO] {} -> {}'.format(reg, url))
    soup = get_soup(url)
    panels = soup.select('div.panel.panel-default')
    print('       panels rendered by source: {}'.format(len(panels)))

    n_before = len(sqldict['Name'])

    for panel in panels:
        name, fields, body_text = parse_panel(panel)
        if not name:
            continue

        address = field_lookup(fields, 'Adresa e Selise')
        website = field_lookup(fields, 'Faqja e Internetit')
        email = field_lookup(fields, 'Posta Elektronike')
        cotype = field_lookup(fields, 'Lloji i Pronesise')
        activity = field_lookup(fields, 'Fusha e Aktivitetit')
        lic_raw = field_lookup(fields, 'Licenca', 'Dt. e fillimit te Aktivitetit')
        phone, fax = split_phone(field_lookup(fields, 'Tel./Faks'))
        lic_no, lic_date = parse_license(lic_raw)

        mother = ''
        if listcode == '6':
            # Investment funds are not companies: the panel names the management company.
            mother, depositary = parse_fund_body(body_text)
            if not activity:
                activity = body_text

        if email.lower().startswith('mailto:'):
            email = email[7:]

        add_row(
            ListLabel=listlabel,
            Typology=listname,
            Name=name,
            InternalID_1=lic_no,
            InternalID_1_type='License Number' if lic_no else '',
            CoType=cotype,
            License_Type=activity,
            Address_1=address,
            City=pick_city(address),
            Cntry='AL',
            Phone=phone,
            Fax=fax,
            Website=website,
            Email=email,
            RegulationType='Regulated',
            RegulationDate=lic_date,
            RegCtry='AL',
            RegCode=regcode,
            ListCode=listcode,
            ListLanguage='SQ',
            ListName=listname,
            ListProcessDate=processdate,
            **{'Name - Mother Company': mother}
        )

    counts[reg] = len(sqldict['Name']) - n_before
    # Reconcile what we stored against what the page actually rendered.
    if counts[reg] != len(panels):
        print('       [WARN] scraped {} rows but source rendered {} panels'.format(counts[reg], len(panels)))
    else:
        print('       scraped {} rows (matches source)'.format(counts[reg]))

print('\n[RECONCILIATION] scraped vs source-rendered panels')
for reg in regdict:
    print('   {} ({}): {} rows'.format(reg, ListNameDict[reg], counts[reg]))
print('   TOTAL: {}'.format(sum(counts.values())))


#---- Begin_writer and save df to excel ----
os.chdir(scriptfolder)

df = pd.DataFrame(sqldict)

df = df[df['Name'] != '']

# Excel silently turns all-digit strings into floats and eats leading zeros.
for col in TEXT_COLS:
    df[col] = df[col].apply(lambda v: '' if v == '' or pd.isna(v) else str(v))

assert list(df.columns) == SQL_KEYS, 'column order/'"'"'set drifted from the fixed schema'
assert len(df.columns) == 43, 'expected 43 columns, got {}'.format(len(df.columns))

df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)

print('Saved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))

# Read the workbook back and prove a known all-digit ID survived as text.
_check = pd.read_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', dtype=str)
print('Round-trip: {} rows, {} columns'.format(len(_check), len(_check.columns)))
_ids = [v for v in _check['InternalID_1'].fillna('').tolist() if v]
if _ids:
    print('Round-trip InternalID_1 sample: {!r} (type {})'.format(_ids[0], type(_ids[0]).__name__))
    assert not _ids[0].replace('.', '').endswith('0') or '.' not in _ids[0], 'ID was coerced to a float'
assert list(_check.columns) == SQL_KEYS, 'saved workbook column set drifted'
print('Schema OK: 43 columns, order verified.')
