# HN CNBS - Comision Nacional de Bancos y Seguros, Honduras (Jira DECD-5025)
# Source: official Excel "Instituciones Supervisadas por la CNBS" (Spanish).
# Download host is publicaciones.cnbs.gob.hn (the www page redirects there).
# Entity list lives in the "REPORTE" sheet, grouped by institution category.

import os
import datetime

import requests
import pandas as pd
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

regulatorName = 'HN CNBS'
print(f'Running {regulatorName} Web Scraping Tool v1.0')

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')

scriptfolder = os.path.dirname(os.path.abspath(__file__))
tempfolder = os.path.join(scriptfolder, 'tempfolder')
if not os.path.exists(tempfolder):
    os.mkdir(tempfolder)
filename = os.path.join(scriptfolder, '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(':', '.')[:-7]))

# ListNr 1 (single list). %2F must stay encoded in the download route.
XLSX_URL = ('https://publicaciones.cnbs.gob.hn/Home/Download/'
            'Instituciones%20Supervisadas%2FListado%20de%20Instituciones%2F2026/'
            '1.%20Instituciones%20Supervisadas%20por%20la%20CNBS%20-%20Marzo%202026.xlsx')
LIST_NAME = 'Instituciones Supervisadas por la CNBS'
LIST_CODE = '1'

sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}

JUNK = {'subtotal', 'institución', 'institucion', 'no.', 'total'}


def s(v):
    v = '' if v is None else str(v).strip()
    return '' if v.lower() == 'nan' else v


def is_num(v):
    v = s(v)
    if not v:
        return False
    try:
        int(float(v))
        return True
    except ValueError:
        return False


def is_junk(c):
    cl = c.lower()
    return (cl in JUNK or cl.startswith('instituciones supervisadas')
            or cl.startswith('al 31') or cl.startswith('comisi'))


# ---- download the Excel ----
r = requests.get(XLSX_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=120, verify=False)
xlsxpath = os.path.join(tempfolder, 'source.xlsx')
with open(xlsxpath, 'wb') as f:
    f.write(r.content)
print(f'Downloaded Excel: HTTP {r.status_code}, {len(r.content)} bytes')

# ---- parse the REPORTE sheet (cols: 1=No, 2=Institucion, 3=Ref, 4=Fecha, 5=Ciudad) ----
df = pd.read_excel(xlsxpath, sheet_name='REPORTE', header=None, dtype=str)

category = ''
for _, row in df.iterrows():
    no, name, ref, city = s(row[1]), s(row[2]), s(row[3]), s(row[5])
    if is_num(no) and name:                       # institution row
        sqldict['Name'].append(name)
        sqldict['Typology'].append(category)
        sqldict['City'].append(city)
        sqldict['Cntry'].append('HN')
        sqldict['RegCtry'].append('HN')
        sqldict['RegCode'].append('CNBS')
        sqldict['ListCode'].append(LIST_CODE)
        sqldict['ListName'].append(LIST_NAME)
        # sqldict['ListLanguage'].append('Spanish')
        sqldict['ListProcessDate'].append(processdate)
        sqldict['RegulationType'].append('Regulated')
        maxlen = len(sqldict['Name'])
        for key in sqldict:
            if len(sqldict[key]) < maxlen:
                sqldict[key].append('')
    elif name and not is_num(no) and not is_junk(name):   # category header row
        category = name

df_out = pd.DataFrame(sqldict)
df_out.to_excel(filename, 'SQL Ready', index=False)
print(f'\nDONE. {len(df_out)} entities -> {filename}')
print(df_out.groupby('Typology', sort=False).size())
for tf in os.listdir(tempfolder):



	try:



		os.remove(tf)



	except:



		print(f'ERROR trying to delete {tf}, please delete manually...')