# GM CBG - Central Bank of The Gambia (Jira DECD-5023)
# Source: https://www.cbg.gm  -- static Bootstrap HTML tables, server-rendered, no JS/pagination.
# Plain requests + BeautifulSoup. Header-driven; multi-line cells parsed per field.

import os
import re
import datetime

import requests
import pandas as pd
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

regulatorName = 'GM CBG'
print(f'Running {regulatorName} Web Scraping Tool v1.0')

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')

scriptfolder = os.path.dirname(os.path.abspath(__file__))
tempfolder = os.path.join(scriptfolder, 'tempfolder')
if not os.path.exists(tempfolder):
    os.mkdir(tempfolder)
filename = os.path.join(tempfolder, '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(':', '.')[:-7]))

# regdict key = "<RegCtry> <RegCode> <ListCode>"  (ListCode = Jira ListNr)
regdict = {
    'GM CBG 1': 'https://www.cbg.gm/list-of-licensed-banks',
    'GM CBG 2': 'https://www.cbg.gm/insurers',
    'GM CBG 3': 'https://www.cbg.gm/list-of-approved-bureaus',
    'GM CBG 4': 'https://www.cbg.gm/list-of-licensed-microfinance-institutions',  # first table = Finance Company only (exclude VISACA)
    'GM CBG 5': 'https://www.cbg.gm/mobile-money',
}

Typology = {
    'GM CBG 1': 'Commercial Banks',
    'GM CBG 2': 'Insurance Companies',
    'GM CBG 3': 'Forex Bureaux',
    'GM CBG 4': 'Finance Companies',
    'GM CBG 5': 'Mobile Money Operators',
}

sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}

HEADERS = {'User-Agent': 'Mozilla/5.0'}


def classify(header):
    h = header.strip().lower()
    if 'website' in h or h == 'web':
        return 'Website'
    if 'contact' in h or 'phone' in h or 'tel' in h:
        return 'Contact'
    if 'address' in h:
        return 'Address_1'
    if 'managing director' in h or h == 'manager' or h == 'director':
        return None  # person column, no target field
    if any(k in h for k in ('bank', 'company', 'bureau', 'insurance', 'finance', 'institution', 'visaca', 'name')):
        return 'Name'
    return None


def first_line(cell):
    """Entity name = first text line; drops the Manager:/Status: lines below it."""
    lines = [ln.strip() for ln in cell.get_text('\n', strip=True).split('\n') if ln.strip()]
    return lines[0] if lines else ''


def parse_address(cell):
    lines = [ln.strip() for ln in cell.get_text('\n', strip=True).split('\n') if ln.strip()]
    if len(lines) >= 2:
        return ', '.join(lines[:-1]), lines[-1]   # Address_1, City
    return (lines[0] if lines else ''), ''


def parse_contact(cell):
    website = email = ''
    for a in cell.select('a[href]'):
        href = a['href'].strip()
        if href.lower().startswith('mailto:'):
            email = href[7:]
        elif href.lower().startswith('http'):
            website = href
    txt = cell.get_text(' ', strip=True)
    if website:
        txt = txt.replace(website, '')
    for a in cell.select('a'):
        txt = txt.replace(a.get_text(strip=True), '')
    phone = re.sub(r'(?i)\btel\b\s*:?', '', txt)
    phone = re.sub(r'\s{2,}', ' ', phone).strip(' :/').strip()
    return phone, website, email


for reg in regdict:
    print(f'Working with list {reg} - {Typology[reg]}')
    r = requests.get(regdict[reg], headers=HEADERS, timeout=40, verify=False)
    soup = BeautifulSoup(r.text, 'html.parser')
    table = soup.select_one('table')          # first table only (List 4: Finance Company, not VISACA)
    if table is None:
        print('  !! no table found')
        continue

    headers = [th.get_text(' ', strip=True) for th in table.select('thead th, thead td')]
    colmap = {i: classify(h) for i, h in enumerate(headers)}
    if 'Name' not in colmap.values():
        print(f'  !! no Name column; headers={headers}')
        continue

    rows_before = len(sqldict['Name'])
    for tr in table.select('tbody tr'):
        tds = tr.find_all('td')
        if not tds:
            continue
        rec = {}
        for i, td in enumerate(tds):
            field = colmap.get(i)
            if not field:
                continue
            if field == 'Name':
                rec['Name'] = first_line(td)
            elif field == 'Address_1':
                rec['Address_1'], rec['City'] = parse_address(td)
            elif field == 'Contact':
                ph, web, em = parse_contact(td)
                rec['Phone'] = ph
                if web:
                    rec.setdefault('Website', web)
                if em:
                    rec['Email'] = em
            elif field == 'Website':
                a = td.find('a', href=True)
                rec['Website'] = a['href'].strip() if a else td.get_text(' ', strip=True)

        name = rec.get('Name', '').strip()
        if not name:
            continue

        sqldict['Name'].append(name)
        sqldict['Address_1'].append(rec.get('Address_1', ''))
        sqldict['City'].append(rec.get('City', ''))
        sqldict['Phone'].append(rec.get('Phone', ''))
        sqldict['Website'].append(rec.get('Website', ''))
        sqldict['Email'].append(rec.get('Email', ''))
        sqldict['Cntry'].append('GM')
        sqldict['RegCtry'].append(reg.split()[0])
        sqldict['RegCode'].append(reg.split()[1])
        sqldict['ListCode'].append(reg.split()[2])
        sqldict['ListName'].append(Typology[reg])
        sqldict['ListLanguage'].append('English')
        sqldict['ListProcessDate'].append(processdate)
        sqldict['RegulationType'].append('Regulated')

        maxlen = len(sqldict['Name'])
        for key in sqldict:
            if len(sqldict[key]) < maxlen:
                sqldict[key].append('')

    print(f'  -> {len(sqldict["Name"]) - rows_before} entities')

df = pd.DataFrame(sqldict)
df.to_excel(filename, 'SQL Ready', index=False)
print(f'\nDONE. {len(df)} rows -> {filename}')
print(df.groupby(['ListCode', 'ListName']).size())
