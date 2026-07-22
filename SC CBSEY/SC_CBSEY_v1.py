# ------------------------------------------------ Import Lib ----------------------------------------
import os
import re
import datetime
import requests
import pandas as pd

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ------------------------------------------------ Begin_ fileName ----------------------------------------
regulatorName = 'SC CBSEY'  # Central Bank of Seychelles

print(f"Running {regulatorName} Web Scraping Tool v.1.0")

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":", ".")[:-7])

try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))  # production (.py)
except NameError:
    scriptfolder = os.getcwd()  # notebook
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
# The site is an AngularJS app; data comes from a JSON endpoint (no browser needed).
API = 'https://www.cbs.sc/Controller/getFinancialInstitution.jsp?type={}'
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'}

# ListNr, ListName, [API types], ListLabel
LISTS = [
    (1, 'Commercial Banks',              ['bank institution'],        1),
    (2, 'Non-bank Credit Institutions',  ['NBCI'],                    4),
    (3, 'Bureaux de Change',             ['bdc class A', 'bdc class B'], 4),
    (4, 'Financial Leasing',             ['DTI', 'NDTI'],             4),
    (5, 'Payment Service Providers',     ['PSP'],                     4),
    (6, 'Credit Unions',                 ['NBDTI'],                   4),
]


def fetch(atype):
    r = requests.get(API.format(requests.utils.quote(atype)), headers=headers, verify=False, timeout=60)
    r.raise_for_status()
    data = r.json()
    key = list(data.keys())[0]
    rows = data[key]
    return rows if isinstance(rows, list) else []


for listnr, listname, types, label in LISTS:
    reg = '{} {}'.format(regulatorName, listnr)  # e.g. 'SC CBSEY 1'
    count = 0
    for atype in types:
        for rec in fetch(atype):
            name = (rec.get('institutionName') or '').strip()
            name = re.sub(r'^\s*\d+\.\s*', '', name).strip()  # drop leading "1. " numbering
            if not name:
                continue
            pobox = (rec.get('poBox') or '').strip()
            state = (rec.get('state') or '').strip()
            addr2 = ', '.join([p for p in [pobox, state] if p])

            sqldict['Name'].append(name)
            sqldict['Address_1'].append((rec.get('streetName') or '').strip())
            sqldict['Address_2'].append(addr2)
            sqldict['City'].append((rec.get('city') or '').strip())
            sqldict['Phone'].append((rec.get('telephone') or '').strip())
            sqldict['Email'].append((rec.get('email') or '').strip())
            sqldict['Website'].append((rec.get('website') or '').strip())
            sqldict['Cntry'].append('SC')
            sqldict['RegulationType'].append('Regulated')
            sqldict['ListName'].append(listname)
            sqldict['ListLabel'].append(label)
            sqldict['ListLanguage'].append('EN')
            sqldict['RegCtry'].append(reg.split()[0])   # SC
            sqldict['RegCode'].append(reg.split()[1])    # CBSEY
            sqldict['ListCode'].append(reg.split()[2])   # list number
            sqldict['ListProcessDate'].append(processdate)
            sqldict = bourange_same_length_array(sqldict)
            count += 1
    print(f"  List {listnr} '{listname}': {count} entities")

# ------------------------------------------------ save df to excel ----------------------------------------
os.chdir(scriptfolder)
df = pd.DataFrame(sqldict)
df = df[df['Name'] != '']
df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)
print('Saved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))
