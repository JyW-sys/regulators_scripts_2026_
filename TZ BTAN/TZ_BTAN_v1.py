# ------------------------------------------------ Import Lib ----------------------------------------
import os
import re
import io
import datetime
import requests
import pandas as pd
import pdfplumber
from bs4 import BeautifulSoup

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ------------------------------------------------ Begin_ fileName ----------------------------------------
regulatorName = 'TZ BTAN'  # Bank of Tanzania

print(f"Running {regulatorName} Web Scraping Tool v.1.0")

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":", ".")[:-7])

try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))
except NameError:
    scriptfolder = os.getcwd()
os.chdir(scriptfolder)

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'}


def get(url, timeout=90, tries=4):
    """GET with retries — bot.go.tz is a slow/flaky government host."""
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, headers=headers, verify=False, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as e:  # noqa: BLE001 - retry any transient network error
            last = e
            print(f"    retry {i + 1}/{tries} for {url[:60]}... ({type(e).__name__})")
    raise last

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


def clean(s):
    return re.sub(r'\s+', ' ', (s or '').replace('\n', ' ')).strip()


def add_row(reg, listname, label, **fields):
    """Append one entity, filling the required list-level fields, then pad."""
    sqldict['Name'].append(clean(fields.get('name')))
    sqldict['CoType'].append(clean(fields.get('cotype')))
    sqldict['Typology'].append(clean(fields.get('typology')))
    sqldict['Address_1'].append(clean(fields.get('addr1')))
    sqldict['Address_2'].append(clean(fields.get('addr2')))
    sqldict['City'].append(clean(fields.get('city')))
    sqldict['Phone'].append(clean(fields.get('phone')))
    sqldict['Fax'].append(clean(fields.get('fax')))
    sqldict['Email'].append(clean(fields.get('email')))
    sqldict['Website'].append(clean(fields.get('website')))
    if fields.get('internalid'):
        sqldict['InternalID_1'].append(clean(fields.get('internalid')))
        sqldict['InternalID_1_type'].append(fields.get('internalid_type', 'Licence Number'))
    sqldict['Cntry'].append('TZ')
    sqldict['RegulationType'].append('Regulated')
    sqldict['ListName'].append(listname)
    sqldict['ListLabel'].append(label)
    sqldict['ListLanguage'].append('EN')
    sqldict['RegCtry'].append(reg.split()[0])
    sqldict['RegCode'].append(reg.split()[1])
    sqldict['ListCode'].append(reg.split()[2])
    sqldict['ListProcessDate'].append(processdate)
    bourange_same_length_array(sqldict)


# =================================================================================================
# LIST 1 - LIST OF LICENSED INSTITUTIONS (HTML tab panes; SKIP the Bureau de Change filter)
# =================================================================================================
reg1 = regulatorName + ' 1'
list1name = 'List of Licensed Institutions'
html = get('https://www.bot.go.tz/BankSupervision/Institutions', timeout=90).text
soup = BeautifulSoup(html, 'html.parser')

# map pane id -> readable category (CoType); skip Bureau de Change per ticket
SKIP = {'nav-BureauDeChange'}
count1 = 0
for pane in soup.select('div.tab-pane'):
    pid = pane.get('id')
    if not pid or pid in SKIP:
        continue
    tbl = pane.find('table')
    if not tbl:
        continue
    cotype = pid.replace('nav-', '').replace('_', ' ').title()
    rows = tbl.find_all('tr')
    for r in rows[1:]:
        cells = r.find_all(['td', 'th'])
        if len(cells) < 2:
            continue
        name = clean(cells[1].get_text(' ', strip=True))
        if not name or name.lower() == 'name of institution':
            continue
        contact_block = clean(cells[3].get_text(' ', strip=True)) if len(cells) > 3 else ''
        phys = clean(cells[4].get_text(' ', strip=True)) if len(cells) > 4 else ''
        # parse Tel / Fax / email out of the contact block
        phone = fax = email = ''
        m = re.search(r'Tel[:\s]*(.*?)(?:Fax[:\s]|email[:\s]|$)', contact_block, re.I)
        if m: phone = m.group(1).strip(' |')
        m = re.search(r'Fax[:\s]*(.*?)(?:email[:\s]|$)', contact_block, re.I)
        if m: fax = m.group(1).strip(' |')
        m = re.search(r'email[:\s]*([^\s|]+@[^\s|]+)', contact_block, re.I)
        if m: email = m.group(1).strip(' |')
        website = ''
        m = re.search(r'(https?://\S+|www\.\S+)', contact_block, re.I)
        if m: website = m.group(1).strip(' |')
        add_row(reg1, list1name, 1, name=name, cotype=cotype, addr1=phys,
                phone=phone, fax=fax, email=email, website=website)
        count1 += 1
print(f"  List 1 '{list1name}': {count1} entities")


# =================================================================================================
# LIST 2 - REGISTER OF TIER 2 MICROFINANCE SERVICE PROVIDERS (PDF, text-extractable)
# =================================================================================================
reg2 = regulatorName + ' 2'
list2name = 'List of Licensed Tier 2 Microfinance Service Providers'
url2 = 'https://www.bot.go.tz/Other/Orodha ya Watoa Huduma Ndogo za Fedha wa Daraja la Pili.pdf'
pdf2 = get(url2, timeout=180).content
count2 = 0
annex2 = 0
with pdfplumber.open(io.BytesIO(pdf2)) as pdf:
    for page in pdf.pages:
        for tbl in page.extract_tables():
            for row in tbl:
                if not row or len(row) < 8:
                    continue
                name = clean(row[1])
                if not name or name.upper() == 'NAME':
                    continue
                # The PDF appends a status-change annex (col6=LOCAL/FOREIGN, col7=STATUS
                # such as REVOKED/UPGRADED). Those are no longer active Tier-2 licensees,
                # so they are excluded from this positive list (counted + flagged below).
                if clean(row[6]).upper() in ('LOCAL', 'FOREIGN'):
                    annex2 += 1
                    continue
                add_row(reg2, list2name, 4,
                        name=name, addr1=row[2], addr2=row[3], city=row[4],
                        phone=row[6], email=row[7],
                        internalid=row[8] if len(row) > 8 else '',
                        internalid_type='Licence Number')
                count2 += 1
print(f"  List 2 '{list2name}': {count2} entities  (excluded {annex2} REVOKED/UPGRADED annex rows)")


# =================================================================================================
# LIST 3 - LIST OF APPROVED DIGITAL LENDING PLATFORMS (PDF, text-extractable)
# =================================================================================================
reg3 = regulatorName + ' 3'
list3name = 'List of Approved Digital Lending Platforms'
url3 = 'https://www.bot.go.tz/Other/REGISTER OF LIST OF APPROVED DIGITAL LENDING PLATFORMS.pdf'
pdf3 = get(url3, timeout=180).content
count3 = 0
with pdfplumber.open(io.BytesIO(pdf3)) as pdf:
    for page in pdf.pages:
        for tbl in page.extract_tables():
            for row in tbl:
                if not row or len(row) < 7:
                    continue
                sn = clean(row[0])
                name = clean(row[1])
                if not re.match(r'^\d+\.?$', sn) or not name:
                    continue
                add_row(reg3, list3name, 4,
                        name=name,                 # licensed MSP (the regulated entity)
                        typology=row[2],           # digital lending platform name
                        cotype='Digital Lending Platform',
                        addr1=row[4], phone=row[5], email=row[6])
                count3 += 1
print(f"  List 3 '{list3name}': {count3} entities")

# ------------------------------------------------ save df to excel ----------------------------------------
os.chdir(scriptfolder)
df = pd.DataFrame(sqldict)
df = df[df['Name'] != '']
df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)
print('Saved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))
