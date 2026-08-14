#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AU APRA -- Australian Prudential Regulation Authority, public registers.

Jira: https://moodysdatapipeline.atlassian.net/browse/DECD-6743

v3 changes vs v2:
  * TYPOLOGY FIX.  v2's parse_tables() did
        typology = p.get_text() if p else (h2.get_text() if h2 else "")
    i.e. it preferred <p> over <h2>.  On every accordion page the section
    heading is the <h2> and the first <p> is the FIRST COMPANY NAME inside
    the table, so v2 stamped e.g. "Alex Bank Pty Ltd" as the section name of
    all 67 Australian-owned ADIs.  The order is now h2/h3 first, <p> only as
    a fallback -- which is still needed, because the NOHC page genuinely has
    no heading tag and carries its three section titles in <p> (measured).
  * LIST 11 FIX.  v2's AU_APRA_11 branch read `soup`, a leftover from the
    AU_APRA_7 iteration -- it never fetched the Retirement Savings Accounts
    page at all, so it scraped the life-insurance table instead.
  * LIST 12 FIX.  v2 appended field-by-field inside the row loop and padded
    only once, after all 28 cards.  9 of the 28 private health insurers have
    no Email row, so every Email after the first gap was written against the
    wrong insurer.  v3 collects a whole card into a dict, then appends once.
  * ListNr 8 dropped -- it is a duplicate of ListNr 5 in the ticket (same
    register of non-operating holding companies).  Confirmed with the user.
  * SELENIUM REMOVED.  The superannuation workbook that v2 downloaded by
    driving Chrome is a plain link on the page; it is now fetched with
    requests.  No browser, no download folder race, no wait_for_file().
  * Names are read from the cell's first <p>, with the embedded PDF
    "download tile" stripped first.  v2 did name.split(':')[0], which left
    the name duplicated ("Alex Bank Pty Ltd Alex Bank Pty Ltd").
  * New data captured that v2 dropped: revocation / deregistration dates ->
    CancellationDate, RSA approval date -> RegulationDate, RFC category and
    ABN, private-health membership type and restriction, RSE fund status.
  * Unknown section headings now raise a loud warning instead of being
    silently mis-filed, so a site re-heading cannot corrupt the output.
  * scriptfolder resolved per project convention (no hard-coded C:\\ path).
  * Non-schema 'Check' column dropped from sqldict.

NOTE -- page structure, measured live 2026-08-13:
  Two different accordion markups are in use.  The older pages wrap each
  section in div.js-accordion; the registered-financial-corporations page
  uses div.anx-accordion__item with an <h3>.  Both are handled.
"""

# ------------------------------------------------ Begin_Librairie ----------------------------------------

import datetime
import io
import os
import re

import pandas as pd
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ------------------------------------------------ Begin_fileName ----------------------------------------

regulatorName = 'AU APRA'

print("Running {} Web Scraping Tool v.3.0".format(regulatorName))

now = datetime.datetime.now()
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":", ".")[:-7])
processdate = now.strftime('%Y-%m-%d')

try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))   # production environment (.py)
except NameError:
    scriptfolder = os.getcwd()                                  # notebook environment

os.chdir(scriptfolder)
tempfolder = os.path.join(scriptfolder, 'tempfolder')

if os.path.exists(tempfolder):
    for rem_file in os.listdir(tempfolder):
        os.remove(os.path.join(tempfolder, rem_file))
else:
    os.mkdir(tempfolder)

# ------------------------------------------------ Begin_Varible ----------------------------------------

sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}

BASE = 'https://www.apra.gov.au'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

# The accordion pages.  Every table on these pages is dispatched by its
# section heading through SECTIONS below.
PAGE_URLS = [
    BASE + '/register-authorised-deposit-taking-institutions',          # list 1
    BASE + '/register-general-insurance',                               # lists 2, 3, 4
    BASE + '/register-non-operating-holding-companies',                 # list 5
    BASE + '/list-of-registered-life-insurers-and-friendly-societies',  # lists 6, 7
    BASE + '/list-institutions-offering-retirement-savings-accounts',   # list 11
    BASE + '/list-of-registered-financial-corporations',                # list 13
]

SUPER_URL = BASE + '/list-of-superannuation-institutions'               # lists 9, 10
PHI_URL = BASE + '/list-of-registered-private-health-insurers'          # list 12

# ListName strings are the ticket's (DECD-6743) list names, kept verbatim.
LN_ADI = 'List of Authorised Deposit-taking Institutions'
LN_GI = 'List of Register of general insurance'
LN_RUNOFF = 'Insurers Only Authorised to Conduct Run-Off Business'
LN_REVOKED = 'Insurers that have had Insurance Authorisations Revoked (since 1st January 2002)'
LN_DEREG = 'Insurers deregistered under the Corporations Act 2001'
LN_NOHC = 'Register of non-operating holding companies (NOHCs)'
LN_LIFE = 'List of Registers of life insurance companies'
LN_FRIENDLY = 'List of Friendly Societies'
LN_RSE = 'List of RSEs'
LN_RSEL = 'List of RSE Licensees'
LN_RSA = 'List of Institutions offering Retirement Savings Accounts'
LN_PHI = 'List of Register of private health insurers'
LN_RFC = 'List of Registered financial corporations'

# section heading (exactly as rendered) -> (ListCode, ListName, RegulationType)
SECTIONS = {
    # ---- list 1, register of authorised deposit-taking institutions
    'Australian-owned authorised deposit-taking institutions': ('1', LN_ADI, 'Regulated'),
    'Foreign subsidiary banks': ('1', LN_ADI, 'Regulated'),
    'Branches of foreign banks': ('1', LN_ADI, 'Regulated'),
    'Providers of purchased payment facilities': ('1', LN_ADI, 'Regulated'),
    # ---- lists 2, 3, 4, register of general insurance
    'Authorised to conduct new or renewal insurance business': ('2', LN_GI, 'Regulated'),
    'Insurers only authorised to conduct run-off business': ('3', LN_RUNOFF, 'Regulated'),
    'Revoked insurance authorisations (since 1 January 2002)': ('4', LN_REVOKED, 'Revoked'),
    'Insurers deregistered under the Corporations Act 2001': ('4', LN_DEREG, 'Deregistered'),
    # ---- list 5, non-operating holding companies (titles live in <p>, no heading tag)
    'Non-operating holding companies licensed under Subsection 11AA(2) of the Banking Act 1959': ('5', LN_NOHC, 'Regulated'),
    'Non-operating holding companies licensed under Section 18 of the Insurance Act 1973': ('5', LN_NOHC, 'Regulated'),
    'Non-operating holding companies licensed under Section 28A of the Life Insurance Act': ('5', LN_NOHC, 'Regulated'),
    # ---- lists 6, 7
    'Life insurance companies': ('6', LN_LIFE, 'Regulated'),
    'Friendly societies': ('7', LN_FRIENDLY, 'Regulated'),
    # ---- list 11
    'List of institutions offering Retirement Savings Accounts': ('11', LN_RSA, 'Regulated'),
    # ---- list 13, registered financial corporations
    'Category D (Money market corporations)': ('13', LN_RFC, 'Regulated'),
    'Category Other (formerly categories E, F and G)': ('13', LN_RFC, 'Regulated'),
    'Category I (Intra group financiers)': ('13', LN_RFC, 'Regulated'),
    'Exempted corporations': ('13', LN_RFC, 'Regulated'),
}

MONTHS = {'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
          'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12}

AU_STATES = ('ACT', 'NSW', 'NT', 'QLD', 'SA', 'TAS', 'VIC', 'WA')

# Tokens that end the suburb when walking an address backwards.
STREET_WORDS = {'street', 'st', 'road', 'rd', 'avenue', 'ave', 'av', 'drive', 'dr',
                'lane', 'ln', 'court', 'ct', 'crescent', 'cres', 'place', 'pl',
                'parade', 'pde', 'terrace', 'tce', 'highway', 'hwy', 'boulevard',
                'blvd', 'square', 'sq', 'circuit', 'cct', 'esplanade', 'esp',
                'way', 'walk', 'close', 'grove', 'level', 'suite', 'unit', 'floor',
                'box', 'bag', 'po', 'gpo', 'building', 'tower', 'centre', 'center',
                'house', 'the'}

# Tokens skipped, rather than stopping the walk, when they trail the suburb.
IGNORE_WORDS = {'australia'}

unknown_sections = []

# ------------------------------------------------ Begin_Fonction ----------------------------------------


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


def norm(text):
    """Collapse whitespace and drop the zero-width spaces APRA sprinkles in."""
    text = (text or '').replace('\u200b', '').replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', text).strip()


def append_row(row):
    """Append one record and immediately pad every other column.

    Padding per row is what stops a missing field (e.g. the 9 private health
    insurers with no Email) from shifting later values into the wrong row.
    """
    sqldict['ListProcessDate'].append(processdate)
    for key, value in row.items():
        sqldict[key].append(value)
    bourange_same_length_array(sqldict)


def get_soup(url):
    response = requests.get(url, headers=HEADERS, timeout=90, verify=False)
    response.raise_for_status()
    return BeautifulSoup(response.text, 'html.parser')


def cell_text(td):
    """Clean text of a table cell.

    A name cell is often
        <td><p>Alex Bank Pty Ltd</p><div class="media ...">...PDF tile...</div></td>
    The tile repeats the name and adds "PDF 47.40 KB - 20 December 2022", so it
    is removed first and the first <p> preferred.  Trailing footnote markers
    ("IMB Ltd 1") are stripped.
    """
    td = BeautifulSoup(str(td), 'html.parser')
    for junk in td.select('div.media, div.download-tile, .download-tile__meta'):
        junk.decompose()
    paragraph = td.find('p')
    text = norm(paragraph.get_text(' ', strip=True)) if paragraph else norm(td.get_text(' ', strip=True))
    text = re.sub(r'\s+\d$', '', text)          # footnote marker: "IMB Ltd 1"
    return re.sub(r'[*†‡#]+$', '', text).strip()   # footnote marker: "Westpac Banking Corporation*"


def section_title(table):
    """Heading of the accordion section a table sits in.

    h2/h3 first, <p> only as a fallback -- this is the v2 bug that mislabelled
    every Typology.  The NOHC page has no heading tag at all, which is why the
    <p> fallback has to stay.
    """
    accordion = (table.find_parent('div', class_='js-accordion')
                 or table.find_parent('div', class_='anx-accordion__item'))
    if accordion is not None:
        heading = accordion.find(['h2', 'h3', 'h4'])
        if heading is not None:
            return norm(heading.get_text(' ', strip=True))
        paragraph = accordion.find('p')
        if paragraph is not None:
            return norm(paragraph.get_text(' ', strip=True))
    heading = table.find_previous(['h2', 'h3', 'h4'])
    return norm(heading.get_text(' ', strip=True)) if heading is not None else ''


def parse_date(value):
    """'7 April 2003' / '25/06/1997' / '2015-11-15' -> 'YYYY-MM-DD'.

    A bare year ('2023' in the run-off table) is not a date and is returned
    unchanged so the caller can decide what to do with it.
    """
    value = norm(value)
    if not value:
        return ''

    match = re.match(r'^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$', value)
    if match and match.group(2).lower() in MONTHS:
        return '{}-{:02d}-{:02d}'.format(match.group(3), MONTHS[match.group(2).lower()], int(match.group(1)))

    match = re.match(r'^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$', value)
    if match:
        return '{}-{:02d}-{:02d}'.format(match.group(3), int(match.group(2)), int(match.group(1)))

    match = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', value)
    if match:
        return value

    return value


def split_au_address(address):
    """Pull the suburb and postcode out of an Australian address.

    The two layouts in APRA's data are
        '148 Fox Valley Rd (Locked Bag 2014) Wahroonga, NSW 2076'   (web cards)
        'GPO BOX 2307 MELBOURNE Australia 3001'                     (RSE workbook)
    so the postcode and any state abbreviation are peeled off the end, then the
    suburb is read as the trailing run of capitalised words -- stopping at a
    token that holds a digit or is a street/box word ('Street', 'GPO', 'Level').
    'Australia' is skipped rather than treated as the suburb.
    """
    address = norm(address)
    if not address:
        return '', ''

    head, zipcode = address, ''

    match = re.search(r'\b(\d{4})\s*$', head)
    if match:
        zipcode = match.group(1)
        head = head[:match.start()]

    head = re.sub(r'[\s,]*\b({})\b[\s,]*$'.format('|'.join(AU_STATES)), '', head, flags=re.I)
    head = head.rstrip(' ,-')

    city_tokens = []
    for token in reversed(head.split()):
        bare = token.strip('.,()[]').lower()
        if not bare:
            continue
        if bare in IGNORE_WORDS:
            if city_tokens:
                break
            continue
        if any(character.isdigit() for character in token) or bare in STREET_WORDS:
            break
        if not token[0].isupper():
            break
        city_tokens.insert(0, token.strip('.,()[]'))
        if len(city_tokens) >= 3:
            break

    return ' '.join(city_tokens), zipcode


# ------------------------------------------------ Begin_Main ----------------------------------------

# ---------- accordion pages: lists 1, 2, 3, 4, 5, 6, 7, 11, 13 ----------

for url in PAGE_URLS:

    print('\n[INFO] fetching {}'.format(url))
    soup = get_soup(url)

    for table in soup.select('table'):

        title = section_title(table)
        config = SECTIONS.get(title)

        if config is None:
            unknown_sections.append((url, title))
            print('  !! UNKNOWN SECTION HEADING -- rows skipped: {!r}'.format(title))
            continue

        list_code, list_name, regulation_type = config

        headers = [norm(th.get_text(' ', strip=True)).lower() for th in table.select('tr th')]

        rows_written = 0

        for tr in table.select('tr')[1:]:

            tds = tr.select('td')
            if not tds:
                continue

            values = [cell_text(td) for td in tds]

            name = values[0]
            if not name:
                continue

            row = {
                'Name': name,
                'Typology': title,
                'Cntry': 'AU',
                'RegCtry': 'AU',
                'RegCode': 'APRA',
                'RegulationType': regulation_type,
                'ListCode': list_code,
                'ListName': list_name,
                'ListLanguage': 'EN',
            }

            # second column, if any -- its meaning is given by the header text
            if len(values) > 1 and len(headers) > 1 and values[1]:
                header = headers[1]
                value = values[1]
                if 'revocation' in header or 'deregistration' in header:
                    row['CancellationDate'] = parse_date(value)
                elif 'approved' in header:
                    row['RegulationDate'] = parse_date(value)
                elif 'run-off' in header:
                    row['License_Type'] = 'Run-off commenced {}'.format(value)
                elif 'abn' in header:
                    row['InternalID_1'] = value
                    row['InternalID_1_type'] = 'ABN'

            append_row(row)
            rows_written += 1

        print('  [{:>2}] {:<62} {:>4} rows'.format(list_code, title[:62], rows_written))

# ---------- list 12: private health insurers (accordion cards) ----------

print('\n[INFO] fetching {}'.format(PHI_URL))
soup = get_soup(PHI_URL)

cards = soup.select('div.js-accordion.accordion')
print('  {} private health insurer cards'.format(len(cards)))

phi_rows = 0

for card in cards:

    # One card == one insurer.  Collect the whole card first, then append
    # once, so a missing Email row cannot shift the column.
    fields = {}

    for tr in card.select('div.accordion__content table tr'):

        th = tr.find('th')
        td = tr.find('td')
        if th is None or td is None:
            continue

        key = norm(th.get_text(' ', strip=True)).lower()
        value = norm(td.get_text(' ', strip=True))

        if 'registered name' in key or key == 'name':
            fields['name'] = value
        elif 'membership type' in key:
            fields['membership'] = value
        elif 'restriction' in key:
            fields['restriction'] = value
        elif 'address' in key:
            fields['address'] = value
        elif 'telephone' in key:
            fields['phone'] = value
        elif 'email' in key:
            fields['email'] = value
        elif 'web site' in key or 'website' in key:
            link = td.find('a', href=True)
            fields['website'] = link['href'].strip() if link else value

    if not fields.get('name'):
        continue

    city, zipcode = split_au_address(fields.get('address', ''))

    append_row({
        'Name': fields['name'],
        'Typology': fields.get('membership', ''),
        'License_Type': fields.get('restriction', ''),
        'Address_1': fields.get('address', ''),
        'City': city,
        'Zip': zipcode,
        'Phone': fields.get('phone', ''),
        'Email': fields.get('email', ''),
        'Website': fields.get('website', ''),
        'Cntry': 'AU',
        'RegCtry': 'AU',
        'RegCode': 'APRA',
        'RegulationType': 'Regulated',
        'ListCode': '12',
        'ListName': LN_PHI,
        'ListLanguage': 'EN',
    })
    phi_rows += 1

print('  [12] {:<62} {:>4} rows'.format(LN_PHI[:62], phi_rows))

# ---------- lists 9 and 10: superannuation workbook ----------

print('\n[INFO] fetching {}'.format(SUPER_URL))
soup = get_soup(SUPER_URL)

workbook_url = ''
for link in soup.select('a[href]'):
    href = link['href']
    if href.lower().endswith('.xlsx') and 'rse' in href.lower():
        workbook_url = href if href.startswith('http') else BASE + href
        break

if not workbook_url:
    raise RuntimeError('No RSE workbook (.xlsx) link found on {} -- lists 9 and 10 '
                       'cannot be built.'.format(SUPER_URL))

print('  workbook: {}'.format(workbook_url))

response = requests.get(workbook_url, headers=HEADERS, timeout=180, verify=False)
response.raise_for_status()

workbook_path = os.path.join(tempfolder, 'apra_superannuation.xlsx')
with open(workbook_path, 'wb') as handle:
    handle.write(response.content)

workbook = pd.ExcelFile(io.BytesIO(response.content), engine='openpyxl')

# --- list 9: List of RSE
rse = workbook.parse('List of RSE').fillna('')
for _, record in rse.iterrows():
    name = norm(str(record['Fund Name']))
    if not name:
        continue
    address = norm(str(record['Postal Address']))
    city, zipcode = split_au_address(address)
    append_row({
        'Name': name,
        'Typology': norm(str(record.get('Fund Type', ''))),
        'RegulationType': 'Regulated' if 'wound up' not in norm(str(record.get('Fund Status', ''))).lower() else 'Wound Up',
        'CoType': norm(str(record.get('Fund Status', ''))),
        'InternalID_1': norm(str(record['Fund ABN'])),
        'InternalID_1_type': 'Fund ABN',
        'InternalID_2': norm(str(record['Registration Number'])),
        'InternalID_2_type': 'Registration Number',
        'Address_1': address,
        'City': city,
        'Zip': zipcode,
        'Phone': norm(str(record.get('Contact Telephone Number', ''))),
        'Fax': norm(str(record.get('Contact Facsimile Number', ''))),
        'Name - Mother Company': norm(str(record.get('Trustee Name', ''))),
        'Cntry': 'AU',
        'RegCtry': 'AU',
        'RegCode': 'APRA',
        'ListCode': '9',
        'ListName': LN_RSE,
        'ListLanguage': 'EN',
    })
print('  [ 9] {:<62} {:>4} rows'.format(LN_RSE[:62], len(rse)))

# --- list 10: List of Licensee
licensee = workbook.parse('List of Licensee').fillna('')
for _, record in licensee.iterrows():
    name = norm(str(record['Trustee Name']))
    if not name:
        continue
    address = norm(str(record['Postal Address']))
    city, zipcode = split_au_address(address)
    append_row({
        'Name': name,
        'License_Type': norm(str(record.get('Class of Licence', ''))),
        'InternalID_1': norm(str(record['Trustee ABN'])),
        'InternalID_1_type': 'Trustee ABN',
        'InternalID_2': norm(str(record['Licence Number'])),
        'InternalID_2_type': 'Licence Number',
        'Address_1': address,
        'City': city,
        'Zip': zipcode,
        'Cntry': 'AU',
        'RegCtry': 'AU',
        'RegCode': 'APRA',
        'RegulationType': 'Regulated',
        'ListCode': '10',
        'ListName': LN_RSEL,
        'ListLanguage': 'EN',
    })
print('  [10] {:<62} {:>4} rows'.format(LN_RSEL[:62], len(licensee)))

# ------------------------------------------------ Begin_writer and save df to excel  ----------------------------------------

os.chdir(scriptfolder)

df = pd.DataFrame(sqldict)

df = df[df['Name'] != '']

df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)

print('\nSaved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))

print('\nRows per list:')
summary = df.groupby(['ListCode', 'ListName', 'RegulationType']).size().rename('rows').reset_index()
summary['ListCode'] = summary['ListCode'].astype(int)
print(summary.sort_values('ListCode').to_string(index=False))

print('\nTypology values:')
print(df['Typology'].value_counts().to_string())

if unknown_sections:
    print('\n!! {} table(s) were skipped because their heading is not in SECTIONS:'.format(len(unknown_sections)))
    for url, title in unknown_sections:
        print('   {!r}  ({})'.format(title, url))
