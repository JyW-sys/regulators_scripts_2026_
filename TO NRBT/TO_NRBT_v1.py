# ------------------------------------------------ Import Lib ----------------------------------------
import os
import re
import datetime
import requests
import pandas as pd
from bs4 import BeautifulSoup

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ------------------------------------------------ Begin_ fileName ----------------------------------------
regulatorName = 'TO NRBT'  # National Reserve Bank of Tonga

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


# ------------------------------------------------ Begin_ scraping ----------------------------------------
# ListNr 1 - "Financial Institutions in Tonga" (single list, mixed: banks / FX dealers / moneylenders)
url = 'https://www.reservebank.to/index.php/financial-system/financial-institutions/financial-institutions-in-tonga'
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'}

r = requests.get(url, headers=headers, verify=False, timeout=60)
r.raise_for_status()
soup = BeautifulSoup(r.text, 'html.parser')

# each entity is a .fd-item card; its category is the nearest preceding h3.mod-title
cat_map = {
    'Commercial Banks': 'Commercial Bank',
    'Licensed Foreign Exchange Dealers': 'Foreign Exchange Dealer',
    'Licensed Moneylenders': 'Moneylender',
}

items = soup.select('.fd-item')
print(f"Found {len(items)} entities on the page")

reg = regulatorName + ' 1'  # 'TO NRBT 1'
listname = 'Financial Institutions in Tonga'

for it in items:
    name_el = it.select_one('.fd-item-title')
    name = name_el.get_text(' ', strip=True) if name_el else ''
    if not name:
        continue

    # category from nearest preceding h3.mod-title
    category = ''
    for prev in it.find_all_previous('h3'):
        cls = prev.get('class') or []
        if 'mod-title' in cls:
            category = prev.get_text(' ', strip=True)
            break
    cotype = cat_map.get(category, category)

    # description block: website link + address + phone
    desc = it.select_one('.fd-item-desc')
    website = ''
    address = ''
    phone = ''
    if desc:
        a = desc.find('a', href=True)
        if a and a['href'].startswith('http'):
            website = a['href'].strip()
        for tag in desc.select('button, a, br'):
            tag.extract()
        text = desc.get_text(' ', strip=True)
        # pull "Tel: +(676) ..." out of the address text
        m = re.search(r'Tel[:.]?\s*(.+)$', text, flags=re.IGNORECASE)
        if m:
            phone = m.group(1).strip()
            text = text[:m.start()].strip().rstrip('.').strip()
        address = text

    sqldict['Name'].append(name)
    sqldict['CoType'].append(cotype)
    sqldict['Address_1'].append(address)
    sqldict['Phone'].append(phone)
    sqldict['Website'].append(website)
    sqldict['Cntry'].append('TO')
    sqldict['RegulationType'].append('Regulated')
    sqldict['ListName'].append(listname)
    sqldict['ListLabel'].append(4)  # mixed banks + FX + moneylenders -> "everything else"
    sqldict['ListLanguage'].append('EN')
    sqldict['RegCtry'].append(reg.split()[0])   # TO
    sqldict['RegCode'].append(reg.split()[1])   # NRBT
    sqldict['ListCode'].append(reg.split()[2])  # 1
    sqldict['ListProcessDate'].append(processdate)
    sqldict = bourange_same_length_array(sqldict)

# ------------------------------------------------ save df to excel ----------------------------------------
os.chdir(scriptfolder)
df = pd.DataFrame(sqldict)
df = df[df['Name'] != '']
df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)
print('Saved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))
