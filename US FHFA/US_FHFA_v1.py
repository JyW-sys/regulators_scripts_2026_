#------------------------------------------------ Import Lib ----------------------------------------
import os
import re
import datetime
from urllib.parse import urljoin

import requests
import pandas as pd
from bs4 import BeautifulSoup

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# %%
#------------------------------------------------ Begin_ fileName ----------------------------------------
regulatorName = 'US FHFA'  ## change to current controller name

print(f"Running {regulatorName} Web Scraping Tool v.1.0")

now = datetime.datetime.now()
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":", ".")[:-7])

# scriptfolder = f"C:\\Users\\wuj1\\OneDrive - Moody's\\Desktop\\Regulator\\{regulatorName}"
scriptfolder = os.path.dirname(os.path.abspath(__file__))  ## production environment
os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder')  # files are downloaded during the process
if os.path.exists(tempfolder):
    for rem in os.listdir(tempfolder):
        os.remove(os.path.join(tempfolder, rem))
else:
    os.mkdir(tempfolder)

# %%
#------------------------------------------------ Begin_Variable ----------------------------------------
sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': [], 'Check': []}

regdict = {
    regulatorName + ' 1': 'https://www.fhfa.gov/data/fhlb-membership',
}

Typology = {
    regulatorName + ' 1': 'Federal Home Loan Bank Membership',
}

processdate = now.strftime('%Y-%m-%d')

# %%
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


def clean(v):
    """Normalize a cell value: NaN/None -> '', else trimmed string."""
    if v is None:
        return ''
    s = str(v).strip()
    if s.lower() in ('nan', 'none', 'nat'):
        return ''
    return s


def pick_latest_xlsx(page_url, session):
    """Return the absolute URL of the most recent FHLB membership .xlsx on the page."""
    r = session.get(page_url, timeout=30, verify=False)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')
    links = [urljoin(page_url, a['href']) for a in soup.find_all('a', href=True)
             if a['href'].lower().endswith(('.xlsx', '.xls'))]

    def score(u):
        m = re.search(r'[qQ]([1-4]).{0,2}(20\d{2})', u)  # ...Q12026 / q1_2026
        if m:
            return int(m.group(2)) * 10 + int(m.group(1))
        m = re.search(r'(\d{2})(\d{2})(20\d{2})', u)  # MMDDYYYY date style
        if m:
            return int(m.group(3)) * 10 + (int(m.group(1)) - 1) // 3 + 1
        return 0

    return max(links, key=score)


#------------------------------------------------ Begin_Main ----------------------------------------
sess = requests.Session()
sess.headers.update({'User-Agent': 'Mozilla/5.0'})

for k, reg in enumerate(regdict):
    print(f"[INFO] : Working {k+1}/{len(regdict)} _({reg})_ ")

    # 1) find + download the most recent membership workbook
    xlsx_url = pick_latest_xlsx(regdict[reg], sess)
    print(f"[INFO] : Latest file -> {xlsx_url}")
    local_path = os.path.join(tempfolder, os.path.basename(xlsx_url))
    resp = sess.get(xlsx_url, timeout=60, verify=False)
    resp.raise_for_status()
    with open(local_path, 'wb') as f:
        f.write(resp.content)

    # 2) read the membership sheet (first sheet holds the data; 2nd is field definitions)
    df = pd.read_excel(local_path, sheet_name='MembershipOpenGovt', dtype=str)
    df = df.fillna('')

    for _, row in df.iterrows():
        name_ = clean(row.get('MEMBER_NAME'))
        if not name_:
            continue

        # FHFA_ID is the regulator's own identifier; the remaining ids are
        # member-type specific (banks: FDIC + Federal Reserve, credit unions:
        # NCUA, insurers: NAIC) so fill InternalID_2/3 with whichever exist.
        secondary = [
            (clean(row.get('CERT')), 'FDIC Certificate Number'),
            (clean(row.get('FED_ID')), 'Federal Reserve ID'),
            (clean(row.get('NCUA_ID')), 'NCUA Charter Number'),
            (clean(row.get('NAIC_ID')), 'NAIC Company Code'),
        ]
        secondary = [(v, t) for v, t in secondary if v]

        sqldict['Name'].append(name_)
        sqldict['InternalID_1'].append(clean(row.get('FHFA_ID')))
        sqldict['InternalID_1_type'].append('FHFA ID')
        sqldict['InternalID_2'].append(secondary[0][0] if len(secondary) > 0 else '')
        sqldict['InternalID_2_type'].append(secondary[0][1] if len(secondary) > 0 else '')
        sqldict['InternalID_3'].append(secondary[1][0] if len(secondary) > 1 else '')
        sqldict['InternalID_3_type'].append(secondary[1][1] if len(secondary) > 1 else '')
        sqldict['CoType'].append(clean(row.get('MEM_TYPE')))
        sqldict['License_Type'].append(clean(row.get('CHAR_TYPE')))
        sqldict['Address_2'].append(clean(row.get('STATE')))
        sqldict['City'].append(clean(row.get('CITY')))
        sqldict['Zip'].append(clean(row.get('ZIP')))
        sqldict['Cntry'].append('United States')
        sqldict['RegulationDate'].append(clean(row.get('MEM_DATE')))
        sqldict['RegulationType'].append('Regulated')
        sqldict['ListProcessDate'].append(processdate)
        sqldict['ListName'].append(Typology[reg])
        sqldict['RegCtry'].append(reg.split()[0])
        sqldict['RegCode'].append(reg.split()[1])
        sqldict['ListCode'].append(reg.split()[2])

    sqldict = bourange_same_length_array(sqldict)

#------------------------------------------------ Begin_writer and save df to excel  ----------------------------------------
os.chdir(scriptfolder)
df = pd.DataFrame(sqldict)
df = df[df['Name'] != '']
df.to_excel(filename, 'SQL Ready', index=False)
print(f"[INFO] : Saved {len(df)} rows -> {filename}")
