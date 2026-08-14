#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
HK IAHK -- Insurance Authority (Hong Kong), public registers.

Jira: https://moodysdatapipeline.atlassian.net/browse/DECD-6746

v1.3 changes vs v1.2:
  * LIST 1 REWRITTEN.  v1.2 did
        driver.find_element(By.LINK_TEXT, 'Download Full List').click()
    on the Register of Authorized Insurers page.  That link no longer exists
    (confirmed live 2026-08-13: the page has 22 alphabetical tables of insurer
    names and no download anchor at all), so v1.2 died with
    NoSuchElementException before it wrote a single row.
    The register is now served by a JSON API that the page itself calls:
        https://www.ia.org.hk/iareg/insurerlist.php?lang=en          -> 162 insurers
        https://www.ia.org.hk/iareg/insurerdetail.php?lang=en&ubi_no=<id>
    v1.3 reads those directly.  The detail endpoint carries every field the
    retired workbook had (address / tel / fax / website / email / place of
    incorporation) plus the UBI number, so no data is lost by the change.
  * CLOUDFLARE.  www.ia.org.hk sits behind Cloudflare; plain requests gets
    403 "Just a moment..." on both the HTML pages and the .php endpoints
    (measured).  v1.3 opens one DrissionPage browser purely to obtain the
    cf_clearance cookie, copies that cookie plus the browser's exact
    User-Agent into a requests.Session, then closes the browser.  All 162
    detail calls and both workbooks then go over plain requests
    (~0.7 s each, measured), which is far faster and steadier than driving
    Chrome 162 times.  The browser must NOT be headless -- headless Chrome
    is challenged by Cloudflare and never clears.
  * pandas 2.x.  v1.2 ended with writer.save(), removed in pandas 2.0
    (AttributeError: 'OpenpyxlWriter' object has no attribute 'save').
    v1.3 uses df.to_excel(path, sheet_name='SQL Ready') and writes into the
    regulator folder, not tempfolder.
  * scriptfolder resolved per project convention -- v1.2 hard-coded
    C:\\Users\\wuj1\\OneDrive - moodys.com\\... which is the retired tenant.
  * Non-schema 'Check' column dropped from sqldict.
  * Per-row padding.  v1.2 called bourange_same_length_array() once per LIST;
    v1.3 pads after every row, so a missing email/fax cannot shift a column.
  * ISO_HK extended.  The API returns place of incorporation in UPPER CASE
    and uses names v1.2's map did not have ("GERMANY" not "Federal Republic
    of Germany", "THE PEOPLE'S REPUBLIC OF CHINA", "UNITED STATES OF
    AMERICA", "SWEDEN").  Lookup is now case-insensitive and any unmapped
    country is printed as a loud warning instead of silently becoming None.
  * New data captured that v1.2 dropped: UBI number -> InternalID_1,
    insurer type -> CoType, business nature / line of business ->
    License_Type, year of first authorization -> RegulationDate, licence
    number -> InternalID_1 for lists 2 and 3 (v1.2 had this) and licence
    status -> RegulationType.  v1.2 stamped every intermediary 'Regulated';
    the workbooks in fact carry 'Active - Suspended' rows, which v1.3
    reports as 'Suspended'.
  * ListLanguage = 'EN' on every row (the registers are published in EN/TC/SC;
    every field taken here is the English one).

NOTE -- counts measured live 2026-08-13:
    list 1  Register of Authorized Insurers                 162
    list 2  List of Licensed Insurance Agencies            1467
    list 3  List of Licensed Insurance Broker Companies     811
  v1.2's last good run had 158 / 1569 / 800.  The agency count really did
  fall; it is not a scraping loss -- the workbook itself has 1467 rows.
"""

# ------------------------------------------------ Begin_Librairie ----------------------------------------

import datetime
import io
import json
import os
import re

import pandas as pd
import requests
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from DrissionPage import ChromiumPage, ChromiumOptions

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ------------------------------------------------ Begin_fileName ----------------------------------------

regulatorName = 'HK IAHK'

print("Running {} Web Scraping Tool v.1.3".format(regulatorName))

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

BASE = 'https://www.ia.org.hk'

# List 1 -- the register page is loaded only to (a) clear Cloudflare and
# (b) count the on-page anchors as a cross-check on the API row count.
INSURERS_PAGE = BASE + '/en/supervision/reg_insurers_lloyd/register_of_authorized_insurers.html'
INSURERS_LIST_API = BASE + '/iareg/insurerlist.php?lang=en'
INSURERS_DETAIL_API = BASE + '/iareg/insurerdetail.php?lang=en&ubi_no={}'

# Lists 2 and 3 -- two workbooks linked off the intermediaries page.  The
# file names carry a month ("LALIA_31July2026.xlsx") so they must be
# discovered from the anchor text, never hard-coded.
INTERMEDIARIES_PAGE = BASE + '/en/supervision/reg_ins_intermediaries/registers_of_insurance_intermediaries.html'
AGENCIES_LINK = 'Download Full List \u2013 Licensed Insurance Agencies'
BROKERS_LINK = 'Download Full List \u2013 Licensed Insurance Broker Companies'

LN_INSURERS = 'Register of Authorized Insurers'
LN_AGENCIES = 'List of Licensed Insurance Agencies'
LN_BROKERS = 'List of Licensed Insurance Broker Companies'

# Place of incorporation -> ISO code.  Keys are matched case-insensitively;
# 'United Kingdom' -> 'UK' is kept exactly as v1.2 had it (see README).
ISO_HK = {
    'HONG KONG': 'HK', 'BERMUDA': 'BM', 'GERMANY': 'DE',
    'FEDERAL REPUBLIC OF GERMANY': 'DE', 'UNITED STATES OF AMERICA': 'US',
    'SINGAPORE': 'SG', 'CHINA': 'CN', "THE PEOPLE'S REPUBLIC OF CHINA": 'CN',
    'ITALY': 'IT', 'NORWAY': 'NO', 'SPAIN': 'ES', 'LUXEMBOURG': 'LU',
    'UNITED KINGDOM': 'UK', 'CANADA': 'CA', 'FRANCE': 'FR', 'BELGIUM': 'BE',
    'ISLE OF MAN': 'IM', 'INDIA': 'IN', 'SOUTH AFRICA': 'ZA',
    'REPUBLIC OF IRELAND': 'IE', 'IRELAND': 'IE', 'PHILIPPINES': 'PH',
    'JAPAN': 'JP', 'GUERNSEY': 'GG', 'JERSEY': 'JE', 'SWITZERLAND': 'CH',
    'SWEDEN': 'SE', 'DENMARK': 'DK', 'FINLAND': 'FI', 'NETHERLANDS': 'NL',
    'AUSTRIA': 'AT', 'PORTUGAL': 'PT', 'GREECE': 'GR', 'AUSTRALIA': 'AU',
    'NEW ZEALAND': 'NZ', 'MALAYSIA': 'MY', 'THAILAND': 'TH', 'TAIWAN': 'TW',
    'MACAU': 'MO', 'ISRAEL': 'IL', 'BARBADOS': 'BB', 'CAYMAN ISLANDS': 'KY',
    'BRITISH VIRGIN ISLANDS': 'VG', 'REPUBLIC OF KOREA': 'KR',
}

unmapped_countries = set()
liquidation_notes = []

# ------------------------------------------------ Begin_Fonction ----------------------------------------


def norm(text):
    """Collapse whitespace, drop non-breaking spaces."""
    return re.sub(r'\s+', ' ', (text or '').replace('\xa0', ' ')).strip()


def clean(value):
    """Normalise a JSON / worksheet value into a plain string cell."""
    if value is None:
        return ''
    if isinstance(value, float) and pd.isna(value):
        return ''
    value = norm(str(value))
    if value in ('None', 'nan', 'NaN', 'null', '---', 'N/A'):
        return ''
    return value


def english_part(value):
    """The IA workbooks hold 'English / 繁體 / 简体' in one cell -- keep the English."""
    value = clean(value)
    if not value:
        return ''
    return norm(value.split('/')[0])


def regulation_type(status):
    """Licence Status -> RegulationType.

    The intermediary workbooks use exactly two values per list (measured):
    'Active' and 'Active - Suspended' / 'Active - Suspended (No RO)'.  A
    suspended licensee is still on the register but may not carry on
    regulated activity, so it must not be reported as plain 'Regulated'.
    """
    status = clean(status)
    if not status:
        return 'Regulated'
    if status.lower() == 'active':
        return 'Regulated'
    if 'suspend' in status.lower():
        return 'Suspended'
    return status


def iso_country(place):
    """Place of incorporation -> ISO code, case-insensitive, warn if unknown."""
    place = clean(place)
    if not place:
        return ''
    code = ISO_HK.get(place.upper())
    if code is None:
        unmapped_countries.add(place)
        return ''
    return code


def bourange_same_length_array(sqldict):
    maxlen = len(sqldict['ListProcessDate'])
    for key in sqldict:
        if len(sqldict[key]) != maxlen:
            sqldict[key] = sqldict[key] + [''] * (maxlen - len(sqldict[key]))
    return sqldict


def append_row(row):
    """Append one record and immediately pad every other column."""
    sqldict['ListProcessDate'].append(processdate)
    for key, value in row.items():
        sqldict[key].append(value)
    bourange_same_length_array(sqldict)


def open_session():
    """Clear Cloudflare with a real browser, then hand the cookie to requests.

    headless(False) is deliberate: headless Chrome never clears the
    ia.org.hk challenge.  The browser is closed as soon as the cookie and
    the intermediaries page HTML have been captured.
    """
    options = ChromiumOptions().auto_port()
    options.headless(False)
    page = ChromiumPage(options)
    try:
        page.get(INSURERS_PAGE)
        page.wait.doc_loaded()
        page.wait(5)
        insurers_html = page.html

        page.get(INTERMEDIARIES_PAGE)
        page.wait.doc_loaded()
        page.wait(5)
        intermediaries_html = page.html

        user_agent = page.run_js('return navigator.userAgent;')
        cookies = page.cookies(all_domains=True)
    finally:
        page.quit()

    session = requests.Session()
    session.verify = False
    session.headers.update({
        'User-Agent': user_agent,
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': INSURERS_PAGE,
    })
    for cookie in cookies:
        try:
            session.cookies.set(cookie['name'], cookie['value'],
                                domain=cookie.get('domain', '.ia.org.hk'))
        except Exception:
            pass

    if 'cf_clearance' not in [c['name'] for c in cookies]:
        print('  !! no cf_clearance cookie was issued -- the API calls will most likely 403')

    return session, insurers_html, intermediaries_html


def get_json(session, url):
    response = session.get(url, timeout=120)
    response.raise_for_status()
    text = response.text.lstrip()
    if not text.startswith('{'):
        raise RuntimeError('{} did not return JSON (Cloudflare challenge?)'.format(url))
    return json.loads(text)


# ------------------------------------------------ Begin_Main ----------------------------------------

print('\n[INFO] : clearing Cloudflare with a visible browser ...')
session, insurers_html, intermediaries_html = open_session()

# ---------------------------------------------------------------------------
# List 1 -- Register of Authorized Insurers
# ---------------------------------------------------------------------------

print('\n[INFO] : Working 1/3 _(HK IAHK 1)_  {}'.format(LN_INSURERS))

# Cross-check: the register page renders one anchor per insurer across its
# 22 alphabetical tables.  If the API and the page disagree, say so loudly --
# the delivered row count has to match what a human counts on the site.
page_names = [norm(a.get_text()) for a in
              BeautifulSoup(insurers_html, 'html.parser').select('table a[href]')]
page_names = [n for n in page_names if n]

payload = get_json(session, INSURERS_LIST_API)
insurers = [entity for letter in payload['data'].values() for entity in letter]
print('  page anchors {} / API rows {}'.format(len(page_names), len(insurers)))
if len(page_names) != len(insurers):
    print('  !! MISMATCH between the register page and the API -- check the site before delivering')

for position, entity in enumerate(insurers, 1):
    ubi = clean(entity.get('ubi_no'))
    detail = get_json(session, INSURERS_DETAIL_API.format(ubi)).get('data') or {}

    business_nature = '; '.join(clean(x) for x in (detail.get('en_business_nature')
                                                   or entity.get('en_business_nature') or []) if clean(x))
    insurer_type = clean(detail.get('en_insurer_type')) or clean(entity.get('en_insurer_type'))
    auth_year = clean(detail.get('auth_year')) or clean(entity.get('auth_year'))

    # 2-3 insurers carry a provisional-liquidation / winding-up date but are
    # still on the register.  They are reported at the end of the run rather
    # than written into CancellationDate, which would read as "licence
    # cancelled" -- see the README, this one is open for confirmation.
    liquid = clean(entity.get('liquid_date'))
    windup = clean(entity.get('windup_date'))
    if liquid or windup:
        liquidation_notes.append((clean(entity.get('en_name')), liquid, windup))

    append_row({
        'Name': clean(detail.get('en_name')) or clean(entity.get('en_name')),
        'InternalID_1': ubi,
        'InternalID_1_type': 'Unique Business Identifier' if ubi else '',
        'CoType': insurer_type,
        'License_Type': business_nature,
        'Address_1': clean(detail.get('en_address')),
        'Cntry': iso_country(detail.get('en_poi') or entity.get('en_poi')),
        'Phone': clean(detail.get('tel')),
        'Fax': clean(detail.get('fax')),
        'Website': clean(detail.get('website')),
        'Email': clean(detail.get('email')),
        'RegulationType': 'Regulated',
        'RegulationDate': auth_year,
        'RegCtry': 'HK',
        'RegCode': 'IAHK',
        'ListCode': '1',
        'ListName': LN_INSURERS,
        'ListLanguage': 'EN',
    })

    if position % 25 == 0 or position == len(insurers):
        print('    {}/{} insurer detail pages read'.format(position, len(insurers)))

print('  [1] {:<50} {:>5} rows'.format(LN_INSURERS, len(insurers)))

# ---------------------------------------------------------------------------
# Lists 2 and 3 -- licensed insurance agencies / broker companies
# ---------------------------------------------------------------------------

soup = BeautifulSoup(intermediaries_html, 'html.parser')
workbook_urls = {}
for anchor in soup.select('a[href]'):
    label = norm(anchor.get_text())
    for wanted in (AGENCIES_LINK, BROKERS_LINK):
        # compare on the ASCII-folded label so an en-dash / hyphen swap on the
        # site cannot break the match
        if label.replace('\u2013', '-') == wanted.replace('\u2013', '-'):
            workbook_urls[wanted] = urljoin(INTERMEDIARIES_PAGE, anchor['href'])

for list_code, link_text, list_name in ((2, AGENCIES_LINK, LN_AGENCIES),
                                        (3, BROKERS_LINK, LN_BROKERS)):
    print('\n[INFO] : Working {}/3 _(HK IAHK {})_  {}'.format(list_code, list_code, list_name))

    url = workbook_urls.get(link_text)
    if url is None:
        raise RuntimeError('the "{}" link is gone from {}'.format(link_text, INTERMEDIARIES_PAGE))
    print('  workbook: {}'.format(url))

    response = session.get(url, timeout=300)
    response.raise_for_status()
    tempdf = pd.read_excel(io.BytesIO(response.content))

    columns = {c: norm(c) for c in tempdf.columns}

    def column(prefix):
        """Columns are trilingual headers -- match on the English prefix."""
        for original, text in columns.items():
            if text.lower().startswith(prefix.lower()):
                return original
        raise KeyError('no column starting with {!r} in {}'.format(prefix, list(columns.values())))

    col_licence = column('Licence No.')
    col_name = column('English Name')
    col_business = column('Line(s) of Business')
    col_status = column('Licence Status')

    statuses = {}
    for _, record in tempdf.iterrows():
        name = clean(record[col_name])
        if not name:
            continue
        status = english_part(record[col_status])
        statuses[status] = statuses.get(status, 0) + 1

        append_row({
            'Name': name,
            'InternalID_1': clean(record[col_licence]),
            'InternalID_1_type': 'Licence No.',
            'License_Type': english_part(record[col_business]),
            'RegulationType': regulation_type(status),
            'RegCtry': 'HK',
            'RegCode': 'IAHK',
            'ListCode': str(list_code),
            'ListName': list_name,
            'ListLanguage': 'EN',
        })

    print('  workbook rows {} -- licence statuses seen: {}'.format(
        len(tempdf), {k: statuses[k] for k in sorted(statuses)}))
    print('  [{}] {:<50} {:>5} rows'.format(list_code, list_name, len(tempdf)))

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

if liquidation_notes:
    print('\n[NOTE] {} insurer(s) on the register carry a provisional liquidation /'
          ' winding up date. They are written as Regulated with an empty'
          ' CancellationDate -- confirm how you want them treated:'.format(len(liquidation_notes)))
    for name, liquid, windup in liquidation_notes:
        print('   {:<55} liquidation={!r} winding-up={!r}'.format(name[:55], liquid, windup))

if unmapped_countries:
    print('\n!! {} place(s) of incorporation are not in ISO_HK and were left blank:'.format(len(unmapped_countries)))
    for place in sorted(unmapped_countries):
        print('   {!r}'.format(place))
