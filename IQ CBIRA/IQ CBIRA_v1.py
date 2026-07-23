# IQ CBIRA - Central Bank of Iraq (Jira DECD-5026)
# Source: https://cbi.iq  (bilingual; English requires a session language cookie set via the
# /language/change/english/ toggle). Every list is a server-rendered HTML <table>.
# List 1 (Banks) spans 6 sub-pages; lists 2 & 4 have several tables per page; list 3 is headerless.

import os
import re
import datetime

import requests
import pandas as pd
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

regulatorName = 'IQ CBIRA'
print(f'Running {regulatorName} Web Scraping Tool v1.0')

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')

scriptfolder = os.path.dirname(os.path.abspath(__file__))
tempfolder = os.path.join(scriptfolder, 'tempfolder')
if not os.path.exists(tempfolder):
    os.mkdir(tempfolder)
filename = os.path.join(tempfolder, '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(':', '.')[:-7]))

# (ListCode, ListName, sub-Typology, page_id)
PAGES = [
    (1, 'Banks', 'Government banks', 23),
    (1, 'Banks', 'Local commercial banks', 24),
    (1, 'Banks', 'Local Islamic banks', 113),
    (1, 'Banks', 'Branches of local commercial banks abroad', 126),
    (1, 'Banks', 'Branches of foreign commercial and Islamic banks', 114),
    (1, 'Banks', 'Foreign representative offices operating in Iraq', 118),
    (2, 'Non-banking Financial Institutions', '', 25),
    (3, 'International economic and financial institutions', '', 22),
    (4, 'Authorized institutions providing electronic collection and payment services', '', 94),
]

sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}

PHONE_RE = re.compile(r'(?:00964|\+964|0)\d{6,}|\b\d{10,}\b')
DATE_RE = re.compile(r'\d{1,2}/\d{1,2}/\d{2,4}')


def clean(v):
    if v is None:
        return ''
    v = re.sub(r'\s+', ' ', str(v)).strip()
    return '' if v.lower() == 'nan' else v


def is_int(v):
    v = clean(v).rstrip('.')
    return v.isdigit()


def classify(h):
    h = clean(h).lower()
    if any(k in h for k in ('responsible', 'director', 'manager', 'deputy')):
        return None
    if 'license type' in h:
        return 'License_Type'
    if 'e-mail' in h or 'email' in h or 'website' in h:
        return 'EmailWeb'
    if 'phone' in h or 'telephone' in h or h.endswith('mob') or 'mobile' in h:
        if 'address' not in h:
            return 'Phone'
    if 'address' in h:
        return 'Address'
    if 'certification' in h or 'number, date' in h or 'license number' in h or ('license' in h and 'date' in h) or 'number and date' in h:
        return 'Cert'
    if any(k in h for k in ('equity', 'invested', 'capital')):
        return None
    if 'bank name' in h or 'institution name' in h or 'company name' in h or h == 'name':
        return 'Name'
    return None


def split_email_web(cell):
    email = web = ''
    for tok in re.split(r'[\s|]+', clean(cell)):
        if '@' in tok and not email:
            email = tok
        elif ('www' in tok.lower() or re.match(r'^[\w.-]+\.(com|iq|org|net)', tok.lower())) and not web:
            web = tok
    return email, web


def split_addr_phone(cell):
    txt = clean(cell)
    phones = PHONE_RE.findall(txt)
    for p in phones:
        txt = txt.replace(p, ' ')
    return re.sub(r'\s+', ' ', txt).strip(' /,'), ' '.join(phones)


def add_entity(listcode, listname, typology, name, **kw):
    sqldict['Name'].append(name)
    sqldict['ListCode'].append(str(listcode))
    sqldict['ListName'].append(listname)
    sqldict['Typology'].append(typology)
    sqldict['Address_1'].append(kw.get('addr', ''))
    sqldict['Phone'].append(kw.get('phone', ''))
    sqldict['Email'].append(kw.get('email', ''))
    sqldict['Website'].append(kw.get('web', ''))
    sqldict['License_Type'].append(kw.get('lic', ''))
    sqldict['RegulationDate'].append(kw.get('regdate', ''))
    sqldict['Cntry'].append('' if str(listcode) == '3' else 'IQ')
    sqldict['RegCtry'].append('IQ')
    sqldict['RegCode'].append('CBIRA')
    sqldict['ListLanguage'].append('English')
    sqldict['ListProcessDate'].append(processdate)
    sqldict['RegulationType'].append('Regulated')
    maxlen = len(sqldict['Name'])
    for key in sqldict:
        if len(sqldict[key]) < maxlen:
            sqldict[key].append('')


# ---- session with English language cookie ----
s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0'})
s.verify = False
s.get('https://cbi.iq/language/change/english/https:----cbi.iq--page--93', timeout=60)

for listcode, listname, sub_typ, pid in PAGES:
    r = s.get(f'https://cbi.iq/page/{pid}', timeout=60)
    soup = BeautifulSoup(r.text, 'html.parser')
    before = len(sqldict['Name'])

    for table in soup.select('table'):
        rows = table.select('tr')
        cells_per = [[clean(c.get_text(' ', strip=True)) for c in tr.select('td,th')] for tr in rows]

        # table title = a leading single-cell row (used as Typology for lists 2 & 4)
        table_title = ''
        for cr in cells_per:
            non_empty = [c for c in cr if c]
            if len(non_empty) == 1:
                table_title = non_empty[0]
                break
            if len(non_empty) > 1:
                break

        # locate header row (first cell is the "No." label)
        hdr_idx = next((i for i, cr in enumerate(cells_per)
                        if cr and clean(cr[0]).lower() in ('no', 'no.', '.no', '#')), None)

        if hdr_idx is None:
            # headerless name list (List 3): every non-empty first cell is an entity;
            # the website lives in the row's <a href> (e.g. AMF -> http://www.amf.org.ae/)
            for tr in rows:
                tds = tr.select('td,th')
                name = clean(tds[0].get_text(' ', strip=True)) if tds else ''
                if not name or is_int(name):
                    continue
                a = tr.find('a', href=re.compile(r'^https?://'))
                web = a['href'].strip() if a else ''
                add_entity(listcode, listname, sub_typ, name, web=web)
            continue

        colmap = {i: classify(h) for i, h in enumerate(cells_per[hdr_idx])}
        typ = sub_typ or table_title
        for cr in cells_per[hdr_idx + 1:]:
            if not cr or not is_int(cr[0]):     # entity rows start with the No.; skip continuations
                continue
            rec = {}
            for i, val in enumerate(cr):
                f = colmap.get(i)
                if not f or not val:
                    continue
                if f == 'Name':
                    rec['name'] = val
                elif f == 'Address':
                    rec['addr'], ph = split_addr_phone(val)
                    if ph:
                        rec['phone'] = ph
                elif f == 'Phone':
                    rec['phone'] = val
                elif f == 'EmailWeb':
                    em, web = split_email_web(val)
                    if em:
                        rec['email'] = em
                    if web:
                        rec['web'] = web
                elif f == 'License_Type':
                    rec['lic'] = val
                elif f == 'Cert':
                    m = DATE_RE.search(val)
                    if m:
                        rec['regdate'] = m.group(0)
            name = rec.pop('name', '')
            if name:
                add_entity(listcode, listname, typ, name, **rec)

    print(f'List {listcode} page {pid} ({sub_typ or listname}): {len(sqldict["Name"]) - before} entities')

df = pd.DataFrame(sqldict)
df.to_excel(filename, 'SQL Ready', index=False)
print(f'\nDONE. {len(df)} entities -> {filename}')
print(df.groupby(['ListCode', 'Typology'], sort=False).size())
