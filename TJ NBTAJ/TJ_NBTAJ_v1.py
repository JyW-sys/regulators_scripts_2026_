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
regulatorName = 'TJ NBTAJ'  # National Bank of Tajikistan

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


def norm(s):
    """Collapse whitespace (incl. non-breaking spaces)."""
    return re.sub(r'\s+', ' ', s.replace('\xa0', ' ')).strip()


def clean(v):
    """Normalize a value cell; treat placeholder '-' as empty."""
    v = norm(v)
    return '' if v in ('-', '') else v


# ------------------------------------------------ Scraping config ----------------------------------------
# ListNr | ListName | URL | ListLabel
# 1=bank list, 2=insurance, 3=bank&insurance, 4=everything else
LISTS = [
    (1, 'Banks',
     'https://www.nbt.tj/en/banking_system/banks.php', 1),
    (2, 'Micro Credit Deposit Organizations',
     'https://www.nbt.tj/en/banking_system/tashkilot_amonatii_karzii_khurd.php', 4),
    (3, 'Micro-Loan Organizations',
     'https://www.nbt.tj/en/banking_system/tashkilot_karzii_khurd.php', 4),
    (4, 'Micro Loan Funds',
     'https://www.nbt.tj/en/banking_system/fondhoi_karzii_khurd.php', 4),
    (5, 'List of representative offices of foreign banks',
     'https://www.nbt.tj/en/banking_system/namoyandagi-bonkho/rui_nam_bonk_horigi.php', 1),
    (6, 'List of professional participants of the insurance market',
     'https://www.nbt.tj/en/sugurta/insurance_companies.php', 2),
]

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'}

# Map (normalized, lowercased, ':'-stripped) label -> sqldict field.
# Officer rows (chairman/director/chief accountant/...) are intentionally ignored.
FIELD_LABELS = {
    'address': 'Address_1',
    'telephone': 'Phone',
    'phone': 'Phone',
    'fax': 'Fax',
    'website': 'Website',
    'email': 'Email',
    'e-mail': 'Email',
}


def parse_entities(soup):
    """Each entity is a rowspan block: a leading numbered cell + a name cell
    (both with rowspan), followed by 'label | value' rows. The name/number
    cells are <td> on most lists and <th> on the insurance list; detection is
    by the presence of a rowspan on the first cell of a row."""
    table = soup.find('table')
    entities = []
    cur = None
    for tr in table.find_all('tr'):
        cells = tr.find_all(['td', 'th'])
        if not cells:
            continue
        if cells[0].get('rowspan'):          # start of a new entity
            if cur is not None:
                entities.append(cur)
            cur = {'Name': norm(cells[1].get_text(' ', strip=True))}
            lab_cells = cells[2:]
        else:                                # continuation row
            lab_cells = cells
        if cur is None:
            continue
        if len(lab_cells) >= 2:
            label = norm(lab_cells[0].get_text(' ', strip=True)).rstrip(':').lower()
            field = FIELD_LABELS.get(label)
            if field:
                valcell = lab_cells[1]
                val = clean(valcell.get_text(' ', strip=True))
                if not val:                  # fall back to link href (website/email)
                    a = valcell.find('a', href=True)
                    if a:
                        val = a['href'].replace('mailto:', '').strip()
                cur.setdefault(field, val)
    if cur is not None:
        entities.append(cur)
    return entities


# ------------------------------------------------ Begin_ scraping ----------------------------------------
for listnr, listname, url, listlabel in LISTS:
    reg = '{} {}'.format(regulatorName, listnr)  # e.g. 'TJ NBTAJ 1'
    r = requests.get(url, headers=headers, verify=False, timeout=60)
    r.raise_for_status()
    r.encoding = 'utf-8'
    soup = BeautifulSoup(r.text, 'html.parser')

    entities = parse_entities(soup)
    print(f"List {listnr} ({listname}): found {len(entities)} entities")

    for e in entities:
        name = e.get('Name', '')
        if not name:
            continue
        sqldict['Name'].append(name)
        sqldict['Address_1'].append(e.get('Address_1', ''))
        sqldict['Phone'].append(e.get('Phone', ''))
        sqldict['Fax'].append(e.get('Fax', ''))
        sqldict['Website'].append(e.get('Website', ''))
        sqldict['Email'].append(e.get('Email', ''))
        sqldict['Cntry'].append('TJ')
        sqldict['RegulationType'].append('Regulated')
        sqldict['ListName'].append(listname)
        sqldict['ListLabel'].append(listlabel)
        sqldict['ListLanguage'].append('EN')
        sqldict['RegCtry'].append(reg.split()[0])   # TJ
        sqldict['RegCode'].append(reg.split()[1])   # NBTAJ
        sqldict['ListCode'].append(reg.split()[2])  # <listnr>
        sqldict['ListProcessDate'].append(processdate)
        sqldict = bourange_same_length_array(sqldict)

# ------------------------------------------------ save df to excel ----------------------------------------
os.chdir(scriptfolder)
df = pd.DataFrame(sqldict)
df = df[df['Name'] != '']
df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)
print('Saved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))
