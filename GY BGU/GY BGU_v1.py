# GY BGU - Bank of Guyana (Jira DECD-5024)
# Source: 5 text-based PDFs on https://www.bankofguyana.org.gy  (no OCR needed).
# pdfplumber.extract_tables(); per-list config because each PDF has a different schema.

import os
import re
import datetime
import requests
import pandas as pd
import pdfplumber
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

regulatorName = 'GY BGU'
print(f'Running {regulatorName} Web Scraping Tool v1.0')

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')

scriptfolder = os.path.dirname(os.path.abspath(__file__))
tempfolder = os.path.join(scriptfolder, 'tempfolder')
if not os.path.exists(tempfolder):
    os.mkdir(tempfolder)
filename = os.path.join(tempfolder, '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(':', '.')[:-7]))

regdict = {
    'GY BGU 1': 'https://www.bankofguyana.org.gy/bog/images/supervision/List%20of%20commercial%20banks_Update_2.pdf',
    'GY BGU 2': 'https://www.bankofguyana.org.gy/bog/images/bank_supervision/licensed_financial_institutions/nonbanks.pdf',
    'GY BGU 3': 'https://www.bankofguyana.org.gy/bog/images/insurance_supervision/List_of_Registered_Insurance_Companies%20v2.pdf',
    'GY BGU 4': 'https://www.bankofguyana.org.gy/bog/images/insurance_supervision/List_of_Insurance_Brokers_2025_upd.pdf',
    'GY BGU 5': 'https://www.bankofguyana.org.gy/bog/images/insurance_supervision/List_of_Registered_Pension_Plans.pdf',
}

Typology = {
    'GY BGU 1': 'Commercial Banks',
    'GY BGU 2': 'Non-Bank Financial Institutions',
    'GY BGU 3': 'Registered Insurance Companies in Guyana',
    'GY BGU 4': 'Registered Insurance Brokers in Guyana',
    'GY BGU 5': 'Pension Plan Managers',
}

# per-list extraction config: which column header holds the Name / Address / Date
CONF = {
    'GY BGU 1': {'name_kw': 'commercial bank', 'addr_kw': 'address', 'name_lineonly': False},
    'GY BGU 2': {'name_kw': 'institution',    'addr_kw': 'address', 'name_lineonly': True},
    'GY BGU 3': {'name_kw': 'company',        'addr_kw': 'address', 'name_lineonly': False},
    'GY BGU 4': {'name_kw': 'brokers',        'addr_kw': 'address', 'name_lineonly': False, 'date_kw': 'initial date'},
    'GY BGU 5': {'name_kw': 'managers',       'addr_kw': None,      'name_lineonly': False, 'dedupe': True},
}

sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}

HEADERS = {'User-Agent': 'Mozilla/5.0'}
EXCLUDE = {"planstrustees", "planstrustee"}   # generic placeholder, not an entity (letters-only match)


def clean(s):
    if not s:
        return ''
    s = s.replace('\r', ' ')
    # normalize valid-but-non-ASCII smart punctuation to plain ASCII
    s = s.replace('‘', "'").replace('’', "'")     # curly single quotes
    s = s.replace('“', '"').replace('”', '"')     # curly double quotes
    s = s.replace('–', '-').replace('—', '-')     # en/em dash
    s = s.replace('�', "'")                            # undecodable glyph fallback
    s = re.sub(r'[ \t]+', ' ', s)
    return s.strip()


def name_value(cell, lineonly):
    if not cell:
        return ''
    lines = [clean(l) for l in cell.split('\n') if clean(l)]
    if not lines:
        return ''
    val = lines[0] if lineonly else ' '.join(lines)
    val = re.sub(r'^\d+[\.\)]\s*', '', val).strip()       # drop leading "1. " numbering
    return val


def first_addr_line(cell):
    if not cell:
        return ''
    for l in cell.split('\n'):
        l = clean(l)
        if not l:
            continue
        if l.lower().strip(':') in ('head office', 'branches', 'branch'):
            continue
        return l
    return ''


def col_index(header_cells, kw):
    if kw is None:
        return None
    for i, c in enumerate(header_cells):
        if c and kw in clean(c).lower():
            return i
    return None


def download(url, dest):
    r = requests.get(url, headers=HEADERS, timeout=60, verify=False)
    open(dest, 'wb').write(r.content)


def add_entity(reg, name, addr='', regdate=''):
    sqldict['Name'].append(name)
    sqldict['Address_1'].append(addr)
    sqldict['RegulationDate'].append(regdate)
    sqldict['Cntry'].append('GY')
    sqldict['RegCtry'].append(reg.split()[0])
    sqldict['RegCode'].append(reg.split()[1])
    sqldict['ListCode'].append(reg.split()[2])
    sqldict['ListName'].append(Typology[reg])
    # sqldict['ListLanguage'].append('English')
    sqldict['ListProcessDate'].append(processdate)
    sqldict['RegulationType'].append('Regulated')
    maxlen = len(sqldict['Name'])
    for key in sqldict:
        if len(sqldict[key]) < maxlen:
            sqldict[key].append('')


for reg in regdict:
    conf = CONF[reg]
    pdfpath = os.path.join(tempfolder, reg.replace(' ', '_') + '.pdf')
    download(regdict[reg], pdfpath)
    print(f'Working with list {reg} - {Typology[reg]}')

    rows_before = len(sqldict['Name'])
    captured = set()           # lowercased names already added for this list
    name_i = addr_i = date_i = None

    with pdfplumber.open(pdfpath) as pdf:
        for page in pdf.pages:
            for table in (page.extract_tables() or []):
                for row in table:
                    if not row or all(c is None or not str(c).strip() for c in row):
                        continue
                    joined = clean(' '.join(c for c in row if c)).lower()
                    # (re)detect header row whenever we hit one
                    if conf['name_kw'] in joined and ('address' in joined or 'managers' in joined or 'no.' in joined):
                        name_i = col_index(row, conf['name_kw'])
                        addr_i = col_index(row, conf.get('addr_kw'))
                        date_i = col_index(row, conf.get('date_kw'))
                        continue
                    if name_i is None or name_i >= len(row):
                        continue

                    name = name_value(row[name_i], conf['name_lineonly'])
                    if not name or re.sub(r'[^a-z]', '', name.lower()) in EXCLUDE:
                        continue
                    # skip section headers / stray all-caps banners in the name column
                    if name.upper() == name and len(name.split()) <= 4 and 'PLANS' in name.upper():
                        continue
                    if conf.get('dedupe') and name.lower() in captured:
                        continue

                    addr = first_addr_line(row[addr_i]) if (addr_i is not None and addr_i < len(row)) else ''
                    regdate = clean(row[date_i]) if (date_i is not None and date_i < len(row) and row[date_i]) else ''
                    add_entity(reg, name, addr, regdate)
                    captured.add(name.lower())

    # List 1: extract_tables drops name rows that lack an inline address (e.g. "3 Scotiabank
    # Guyana Incorporated"). Recover any numbered entity present in the text but missed above.
    if reg == 'GY BGU 1':
        with pdfplumber.open(pdfpath) as pdf:
            txt = '\n'.join((p.extract_text() or '') for p in pdf.pages)
        for m in re.finditer(r'(?m)^\s*([1-6])\s+([A-Z][^\n]*)', txt):
            cand = re.split(r'\s+(?=Lot\b|Lots\b|Public\b|Area\b|\d)', clean(m.group(2)), maxsplit=1)[0].strip()
            low = cand.lower()
            if cand and not any(low == c or low in c or c in low for c in captured):
                add_entity(reg, cand)
                captured.add(low)

    print(f'  -> {len(sqldict["Name"]) - rows_before} entities')

df = pd.DataFrame(sqldict)
df.to_excel(filename, 'SQL Ready', index=False)
print(f'\nDONE. {len(df)} rows -> {filename}')
print(df.groupby(['ListCode', 'ListName']).size())
for tf in os.listdir(tempfolder):
	try:
		os.remove(tf)
	except:
		print(f'ERROR trying to delete {tf}, please delete manually...')