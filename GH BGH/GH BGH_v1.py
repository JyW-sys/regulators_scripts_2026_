# GH BGH - Bank of Ghana (Jira DECD-5022)
# Source: https://www.bog.gov.gh  (wpDataTables, client-side; "Show All" reveals every row)
# Header-driven extraction because column layout varies by institution type.

import os
import re
import datetime
from time import sleep

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

regulatorName = 'GH BGH'
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
    'GH BGH 1':  'https://www.bog.gov.gh/supervision-regulation/registered-institutions/banks/',
    'GH BGH 3':  'https://www.bog.gov.gh/supervision-regulation/ofisd/list-of-ofis/community-banks/',
    'GH BGH 4':  'https://www.bog.gov.gh/supervision-regulation/ofisd/list-of-ofis/microfinance-institutions/',
    'GH BGH 6':  'https://www.bog.gov.gh/supervision-regulation/registered-institutions/savings-loans/',
    'GH BGH 7':  'https://www.bog.gov.gh/supervision-regulation/registered-institutions/finance-houses/',
    'GH BGH 8':  'https://www.bog.gov.gh/supervision-regulation/registered-institutions/leasing-companies/',
    'GH BGH 9':  'https://www.bog.gov.gh/supervision-regulation/registered-institutions/other-banks/',
    'GH BGH 10': 'https://www.bog.gov.gh/supervision-regulation/registered-institutions/representative-offices/',
    'GH BGH 11': 'https://www.bog.gov.gh/supervision-regulation/registered-institutions/finance-and-leasing-companies/',
    'GH BGH 12': 'https://www.bog.gov.gh/supervision-regulation/registered-institutions/mortgage-finance/',
    'GH BGH 13': 'https://www.bog.gov.gh/supervision-regulation/registered-institutions/remittance-companies/',
    'GH BGH 14': 'https://www.bog.gov.gh/supervision-regulation/ofisd/list-of-ofis/financial-ngos/',
    'GH BGH 15': 'https://www.bog.gov.gh/supervision-regulation/ofisd/list-of-ofis/forex-exchange-bureaux/',
    'GH BGH 16': 'https://www.bog.gov.gh/supervision-regulation/ofisd/list-of-ofis/micro-credit/',
}

Typology = {
    'GH BGH 1':  'Banks',
    'GH BGH 3':  'Community Banks',
    'GH BGH 4':  'Microfinance Institutions',
    'GH BGH 6':  'Savings and Loans',
    'GH BGH 7':  'Finance Houses',
    'GH BGH 8':  'Leasing Companies',
    'GH BGH 9':  'Other Banks',
    'GH BGH 10': 'Representative Offices in Ghana',
    'GH BGH 11': 'Finance and Leasing Companies',
    'GH BGH 12': 'Mortgage Finance',
    'GH BGH 13': 'Remittance Companies',
    'GH BGH 14': 'Financial NGOs',
    'GH BGH 15': 'Foreign Exchange Bureaux',
    'GH BGH 16': 'Microcredit Institutions',
}

sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}


def classify(header):
    """Map a column header to a sqldict field. Order matters (email before address)."""
    h = header.strip().lower()
    if 'email' in h or 'e-mail' in h:
        return 'Email'
    if 'web' in h:
        return 'Website'
    if 'phone' in h or 'tel' in h:
        return 'Phone'
    if 'name' in h or 'bureau' in h or 'institution' in h or 'company' in h:
        return 'Name'
    if 'address' in h or 'location' in h:
        return 'Address_1'
    if 'region' in h or 'town' in h or 'city' in h:
        return 'City'
    return None  # S/N, blank spacer columns, etc.


options = webdriver.ChromeOptions()
options.add_argument('--start-maximized')
options.add_argument('--ignore-certificate-errors')
driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 30)

for reg in regdict:
    print(f'Working with list {reg} - {Typology[reg]}')
    driver.get(regdict[reg])
    # wait for the wpDataTable to render
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'table[id^="table_"] tbody tr')))
    except Exception:
        print(f'  !! no table found on {regdict[reg]}')
        continue

    # select "All" in the length dropdown to reveal every row (client-side DataTable)
    try:
        sel = driver.find_element(By.CSS_SELECTOR, '.dataTables_length select')
        Select(sel).select_by_value('-1')
    except Exception:
        pass
    sleep(2)

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    table = soup.select_one('table[id^="table_"]')
    if table is None:
        print('  !! table missing in parsed source')
        continue

    headers = [th.get_text(' ', strip=True) for th in table.select('thead th')]
    colmap = {i: classify(h) for i, h in enumerate(headers)}
    if 'Name' not in colmap.values():
        print(f'  !! no Name column detected; headers={headers}')
        continue

    rows_before = len(sqldict['Name'])
    for tr in table.select('tbody tr'):
        tds = tr.find_all('td')
        if not tds:
            continue
        record = {}
        for i, td in enumerate(tds):
            field = colmap.get(i)
            if not field:
                continue
            # prefer link href for Website/Email when present
            val = td.get_text(' ', strip=True)
            if field == 'Website':
                a = td.find('a', href=True)
                if a:
                    val = a['href'].strip()
            record[field] = re.sub(r'\s+', ' ', val).strip()

        name = record.get('Name', '').strip()
        if not name:
            continue

        sqldict['Name'].append(name)
        sqldict['Address_1'].append(record.get('Address_1', ''))
        sqldict['City'].append(record.get('City', ''))
        sqldict['Phone'].append(record.get('Phone', ''))
        sqldict['Website'].append(record.get('Website', ''))
        sqldict['Email'].append(record.get('Email', ''))
        sqldict['Cntry'].append('GH')
        sqldict['RegCtry'].append(reg.split()[0])
        sqldict['RegCode'].append(reg.split()[1])
        sqldict['ListCode'].append(reg.split()[2])
        sqldict['ListName'].append(Typology[reg])
        sqldict['ListProcessDate'].append(processdate)
        sqldict['RegulationType'].append('Regulated')

        # pad every remaining column for this record
        maxlen = len(sqldict['Name'])
        for key in sqldict:
            if len(sqldict[key]) < maxlen:
                sqldict[key].append('')

    print(f'  -> {len(sqldict["Name"]) - rows_before} entities')

driver.quit()

df = pd.DataFrame(sqldict)
df.to_excel(filename, 'SQL Ready', index=False)
print(f'\nDONE. {len(df)} rows -> {filename}')
print(df.groupby(['ListCode', 'ListName']).size())
