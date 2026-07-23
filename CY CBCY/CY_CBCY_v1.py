#------------------------------------------------ Begin_Librairie ----------------------------------------
from bs4 import BeautifulSoup
import datetime, os, re
import pandas as pd
import requests
import pdfplumber

#------------------------------------------------ Begin_fileName ----------------------------------------
regulatorName = 'CY CBCY'   # Cyprus - Central Bank of Cyprus
print(f"Running {regulatorName} Web Scraping Tool v.1.0")

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":", ".")[:-7])
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))
except NameError:
    scriptfolder = os.getcwd()
os.chdir(scriptfolder)
tempfolder = os.path.join(scriptfolder, 'tempfolder')
os.makedirs(tempfolder, exist_ok=True)

# ListNr -> (ListName from Jira, source URL)
REG = {
 1: ("Register of Credit Institutions operating in Cyprus",
     "https://www.centralbank.cy/en/licensing-supervision/banks/register-of-credit-institutions-operating-in-cyprus"),
 2: ("Register of Payment Institutions",
     "https://www.centralbank.cy/en/licensing-supervision/payment-institutions/licensing-and-supervision-of-payment-institutions"),
 3: ("Register of Electronic Money Institutions licensed by the CBC",
     "https://www.centralbank.cy/en/licensing-supervision/electronic-money-institutions/licensing-and-supervision-of-electronic-money-institutions"),
 4: ("Register of Electronic Money Institutions licensed in other EU member states which have notified their intention to provide electronic money services in the Republic of Cyprus",
     "https://www.centralbank.cy/en/licensing-supervision/electronic-money-institutions/licensing-and-supervision-of-electronic-money-institutions"),
}

# Direct file links scraped off the landing pages (verified 2026-06-18). The CBC rotates the
# date suffix on each republish, so re-resolve from the landing page rather than hard-coding.
FILES = {
 'natid':  ('National-ident-codes.pdf', "https://www.centralbank.cy/images/media/redirectfile/AUTHORISATIONS/National-ident-code-list-EN-28052026.pdf"),
 'lei':    ('BANKS-LEI-CODES.pdf',       "https://www.centralbank.cy/images/media/redirectfile/AUTHORISATIONS/BANKS-LEI-CODES-EN-28052026.pdf"),
 'pi':     ('PI-register.xlsx',          "https://www.centralbank.cy/images/media/redirectfile/Payment Institutions/PI-register-17062026.xlsx"),
 'emi':    ('EMI-register.xlsx',         "https://www.centralbank.cy/images/media/redirectfile/Electronic Money Institutions/EMI-REGISTER-10062026.xlsx"),
 'emipas': ('EMI-incoming-passport.xlsx',"https://www.centralbank.cy/images/media/redirectfile/Electronic Money Institutions/emi-incom-passp-register-16062026.xlsx"),
}

#------------------------------------------------ Begin_Fonction ----------------------------------------
def bourange_same_length_array(sqldict):
    maxlen = len(sqldict['ListProcessDate'])
    for key in sqldict:
        if len(sqldict[key]) != maxlen:
            sqldict[key] = sqldict[key] + [''] * (maxlen - len(sqldict[key]))
    return sqldict

def norm_name(s):
    # match HTML names against PDF names: drop "(previous name: ...)" notes, the leading
    # "N." numbering, the trailing "*" footnote, fold the Greek capital Alpha to Latin A,
    # lowercase and keep alnum only.
    s = str(s)
    s = re.sub(r'\(previous name.*?\)', '', s, flags=re.I)
    s = re.sub(r'^\s*\d+\.\s*', '', s)
    s = re.sub(r'\(the\)', '', s, flags=re.I)   # "... Ltd (The)"
    s = s.replace('Α', 'A')          # Greek Α -> Latin A (e.g. "Αlpha Bank")
    s = s.replace('*', '')
    s = re.sub(r'\blimited\b', 'ltd', s, flags=re.I)   # unify Ltd / Limited
    return re.sub(r'[^a-z0-9]', '', s.lower())

def parse_ho_address(cell):
    # CBC "Contact details" cells are "H.O. address: <street...>, <ZIP> <City>" (all Cyprus).
    out = {'Address_1': '', 'Zip': '', 'City': '', 'Cntry': ''}
    s = str(cell or '').strip()
    if not s or s.lower() == 'nan':
        return out
    s = re.sub(r'^H\.?O\.?\s*address\s*:\s*', '', s, flags=re.I).strip()
    out['Cntry'] = 'CY'
    m = re.search(r'(?:Cy-)?(\d{4})\s+(.+)$', s)   # 4-digit postal code + trailing city
    if m:
        out['Zip'] = m.group(1)
        out['City'] = m.group(2).strip().rstrip(',')
        out['Address_1'] = s[:m.start()].strip().rstrip(',')
    else:
        out['Address_1'] = s
    return out

def first_date(cell):
    # auth-date cells are either text "Current Lic. Date: 18/06/2018" or a bare datetime
    # value ("2018-06-19 00:00:00"); normalise both to dd/mm/yyyy.
    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
        return ''
    m = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', str(cell))
    if m:
        return m.group(1)
    try:
        return pd.to_datetime(cell).strftime('%d/%m/%Y')
    except Exception:
        return ''

def add_row(sqldict, **kw):
    sqldict['ListProcessDate'].append(processdate)
    sqldict['ListLanguage'].append('EN')
    sqldict['RegulationType'].append('Regulated')
    sqldict['RegCtry'].append('CY')
    sqldict['RegCode'].append('CBCY')
    for k, v in kw.items():
        sqldict[k].append(v)
    bourange_same_length_array(sqldict)

#------------------------------------------------ Begin_Variable ----------------------------------------
sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}

#------------------------------------------------ Begin_Download ----------------------------------------
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.centralbank.cy/",
})

def fpath(key):
    return os.path.join(tempfolder, FILES[key][0])

for key, (fname, url) in FILES.items():
    r = session.get(url, timeout=60)
    r.raise_for_status()
    with open(fpath(key), 'wb') as fh:
        fh.write(r.content)
    print(f"downloaded {fname} ({len(r.content)} bytes)")

#------------------------------------------------ List 1: Credit Institutions (HTML + PDFs) ----------------------------------------
# Build National-ID and LEI lookups from the two enrichment PDFs.
def pdf_code_map(path, want_idx):
    out = {}
    with pdfplumber.open(path) as pdf:
        for pg in pdf.pages:
            for tbl in pg.extract_tables():
                for row in tbl:
                    if not row or len(row) <= want_idx:
                        continue
                    name = (row[0] or '').strip()
                    code = (row[want_idx] or '').strip()
                    if name and code and re.match(r'^\d+\.', name):
                        out[norm_name(name)] = code
    return out

natid_map = pdf_code_map(fpath('natid'), 1)   # name col 0, code col 1
lei_map   = pdf_code_map(fpath('lei'),   1)   # name col 0, LEI col 1
print(f"List1 enrichment: {len(natid_map)} national-id codes, {len(lei_map)} LEI codes")

# Scrape the landing-page hierarchy: section headings (<p>) classify the <li> entities below them.
resp = session.get(REG[1][1], timeout=30)
soup = BeautifulSoup(resp.text, 'html.parser')
anchor = soup.find(string=re.compile("SUBSIDIARIES OF FOREIGN"))
container = anchor
for _ in range(8):
    container = container.parent
    if len(container.find_all('li')) > 5:
        break

CATEGORY_HEADS = re.compile(
    r'(LOCAL AUTHORISED|SUBSIDIARIES OF FOREIGN|BRANCHES OF FOREIGN|REPRESENTATIVE OFFICES)', re.I)
current_cat = ''
l1_rows = []
for el in container.descendants:
    nm = getattr(el, 'name', None)
    if nm == 'p':
        txt = ' '.join(el.get_text(' ', strip=True).split())
        if CATEGORY_HEADS.search(txt):
            current_cat = txt
    elif nm == 'li':
        txt = ' '.join(el.get_text(' ', strip=True).split())
        # entities only: skip nav/breadcrumb noise; real names contain "Bank"/"Corporation" etc.
        if txt and 1 < len(txt) < 120 and current_cat and txt not in [r[0] for r in l1_rows]:
            l1_rows.append((txt, current_cat))

for name, cat in l1_rows:
    key = norm_name(name)
    add_row(sqldict,
            Name=name, ListCode='1', ListName=REG[1][0], ListLabel=REG[1][0],
            CoType=cat, License_Type=cat, Cntry='CY',
            InternalID_1=natid_map.get(key, ''),
            InternalID_1_type='National Identification Code' if natid_map.get(key) else '',
            **{'LEI Code': lei_map.get(key, '')})
print(f"List1: {len(l1_rows)} credit institutions")

#------------------------------------------------ List 2: Payment Institutions (xlsx) ----------------------------------------
# Sheet 'PI licensed in CY'. Header at row 2; data rows interleaved with blank spacer rows.
d2 = pd.read_excel(fpath('pi'), sheet_name='PI licensed in CY', header=None)
n2 = 0
for _, row in d2.iloc[3:].iterrows():
    name = str(row[0]).strip()
    if not name or name.lower() == 'nan':
        continue
    name = re.sub(r'\s+', ' ', name)
    addr = parse_ho_address(row[6])
    add_row(sqldict,
            Name=name, ListCode='2', ListName=REG[2][0], ListLabel=REG[2][0],
            CoType='Payment Institution',
            InternalID_1=re.sub(r'\s+', '', str(row[4])) if str(row[4]).strip().lower() != 'nan' else '',
            InternalID_1_type='Registration Number' if str(row[4]).strip().lower() != 'nan' else '',
            InternalID_2=str(row[2]).strip() if str(row[2]).strip().lower() != 'nan' else '',
            InternalID_2_type='Licence Number' if str(row[2]).strip().lower() != 'nan' else '',
            Address_1=addr['Address_1'], Zip=addr['Zip'], City=addr['City'], Cntry=addr['Cntry'],
            RegulationDate=first_date(row[1]),
            **{'LEI Code': str(row[3]).strip() if str(row[3]).strip().lower() != 'nan' else ''})
    n2 += 1
print(f"List2: {n2} payment institutions")

#------------------------------------------------ List 3: Electronic Money Institutions (xlsx) ----------------------------------------
# Sheet 'EMIs'. Header at row 1; data rows interleaved with blank spacer rows.
d3 = pd.read_excel(fpath('emi'), sheet_name='EMIs', header=None)
n3 = 0
for _, row in d3.iloc[2:].iterrows():
    name = str(row[0]).strip()
    if not name or name.lower() == 'nan':
        continue
    name = re.sub(r'\s+', ' ', name)
    addr = parse_ho_address(row[6])
    add_row(sqldict,
            Name=name, ListCode='3', ListName=REG[3][0], ListLabel=REG[3][0],
            CoType='Electronic Money Institution',
            InternalID_1=re.sub(r'\s+', '', str(row[3])) if str(row[3]).strip().lower() != 'nan' else '',
            InternalID_1_type='Registration Number' if str(row[3]).strip().lower() != 'nan' else '',
            InternalID_2=str(row[1]).strip() if str(row[1]).strip().lower() != 'nan' else '',
            InternalID_2_type='Licence Number' if str(row[1]).strip().lower() != 'nan' else '',
            Address_1=addr['Address_1'], Zip=addr['Zip'], City=addr['City'], Cntry=addr['Cntry'],
            RegulationDate=first_date(row[4]),
            **{'LEI Code': str(row[2]).strip() if str(row[2]).strip().lower() != 'nan' else ''})
    n3 += 1
print(f"List3: {n3} e-money institutions")

#------------------------------------------------ List 4: EMIs passported into Cyprus (xlsx) ----------------------------------------
# Sheet 'EMIs passp to Cyprus'. Header at row 2; col0 = home country, col1 = institution name.
d4 = pd.read_excel(fpath('emipas'), sheet_name='EMIs passp to Cyprus', header=None)
n4 = 0
for _, row in d4.iloc[3:].iterrows():
    name = str(row[1]).strip()
    if not name or name.lower() == 'nan' or 'Name of Institution' in name:
        continue
    name = re.sub(r'\s+', ' ', name)
    home = str(row[0]).strip()
    # some cells use Greek capitals that look identical to Latin (e.g. "ΙΕ" -> "IE")
    home = home.translate(str.maketrans('ΑΒΕΖΗΙΚΜΝΟΡΤΥΧ', 'ABEZHIKMNOPTYX'))
    home = home if (len(home) == 2 and home.isalpha()) else ''
    rdate = ''
    
    if not pd.isna(row[2]):
        try:
            rdate = pd.to_datetime(row[2]).strftime('%d/%m/%Y')
        except Exception:
            rdate = ''
    add_row(sqldict,
            Name=name, ListCode='4', ListName=REG[4][0], ListLabel=REG[4][0],
            CoType='Electronic Money Institution (passporting into Cyprus)',
            Cntry=home, RegulationDate=rdate)
    n4 += 1
print(f"List4: {n4} passporting EMIs")

#------------------------------------------------ Begin_writer and save df to excel ----------------------------------------
df = pd.DataFrame(sqldict)
out = os.path.join(scriptfolder, filename)
df.to_excel(out, sheet_name='SQL Ready', index=False)
print(f"\nSaved {len(df)} rows -> {out}")
print(df.groupby('ListCode').size().to_string())
