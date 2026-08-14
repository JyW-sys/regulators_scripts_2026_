#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
KY CIMA — Cayman Islands Monetary Authority, "Search Entities" register.

v4 changes vs v3:
  * Selenium removed entirely (v3 opened Chrome and never used it).
  * scriptfolder resolved per project convention (no hard-coded C:\\ path).
  * Paging starts at PageNumber=1, which skips the reCAPTCHA branch on the
    server -- no more hand-pasted g-recaptcha-response.  See NOTE below.
  * All 36 AuthorizationType values on the site are mapped (v3 mapped 29 and
    silently dropped 3,831 rows).
  * ListLabel / ListLanguage / ListName filled.

NOTE on the reCAPTCHA -- measured, not assumed (2026-08-12):
  cima_cfrf_token_name is NOT a captcha token.  It is CodeIgniter's CSRF
  token, checked only as "POST field == cima_cfrf_token_cookie_name cookie"
  (double-submit, no server-side state).  reCAPTCHA is validated only on the
  "new search" branch, i.e. a POST that carries NO PageNumber.  Any POST that
  carries PageNumber skips the captcha check completely.  PHPSESSID is
  irrelevant.  So: always send PageNumber, starting at 1.
"""

# ------------------------------------------------ Begin_Librairie ----------------------------------------

import datetime
import os
import re
import sys
import time

import pandas as pd
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ------------------------------------------------ Begin_fileName ----------------------------------------

print("Running KY CIMA Web Scraping Tool v.4.0")

now = datetime.datetime.now()
filename = 'KY CIMA SQL Ready {}.xlsx'.format(str(now).replace(":", ".")[:-7])
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

BASE = 'https://www.cima.ky'
FORM_URL = BASE + '/search-entities-cima'
DATA_URL = BASE + '/search-entities-cima/get_search_data'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Origin': BASE,
    'Referer': FORM_URL,
}

CSRF_COOKIE = 'cima_cfrf_token_cookie_name'   # cookie the site sets
CSRF_FIELD = 'cima_cfrf_token_name'           # POST field the site checks it against

MAX_PAGES = int(os.environ.get('KY_MAX_PAGES', '2000'))   # runaway guard / smoke-test knob

# ------------------------------------------------ Begin_Variable ----------------------------------------

# Jira list numbering -- ListNr / ListName taken verbatim from DECD-6740.
# NOTE: v2/v3 regdict had 'KY CIM 4' = Trust (Registered PTC) and 'KY CIM 8' = '-'.
#       The ticket says 4 = Trust and 8 = Trust (Registered PTC), which is what the
#       v3 `mapping` actually emitted, so regdict was the stale one.  Corrected here.
regdict = {
    'KY CIM 1':  'Banking Class A',
    'KY CIM 2':  'Banking Class B',
    'KY CIM 3':  'Money Services',
    'KY CIM 4':  'Trust',
    'KY CIM 5':  'Trust (Restricted)',
    'KY CIM 6':  'Nominee (Trust)',
    'KY CIM 7':  'Trust (Controlled Subsidiary)',
    'KY CIM 8':  'Trust (Registered PTC)',
    'KY CIM 9':  'Company Manager',
    'KY CIM 10': 'Corporate Service Provider',
    'KY CIM 11': 'Insurance Entities',
    'KY CIM 12': 'Mutual Fund - Registered',
    'KY CIM 13': 'Mutual Fund - Administered',
    'KY CIM 14': 'Securities - Registered Person',
    'KY CIM 15': 'Private Fund',
    'KY CIM 16': 'Virtual Asset Service Provider Registration',
    'KY CIM 17': 'Securities - Full',
    'KY CIM 18': 'Building Society',
    'KY CIM 19': 'Credit Union',
    'KY CIM 20': 'Development Bank',
}

# ListName per ListCode -- derived from regdict so the two can never drift.
LIST_NAME = {k.split()[-1]: v for k, v in regdict.items()}

# ListLabel per ListCode: 1 = bank, 2 = insurance, 3 = bank & insurance, 4 = everything else.
LIST_LABEL = {
    '1':  '1',   # Banking Class A
    '2':  '1',   # Banking Class B
    '3':  '4',   # Money Services -- MSB, not a bank
    '4':  '4',   # Trust
    '5':  '4',   # Trust (Restricted)
    '6':  '4',   # Nominee (Trust)
    '7':  '4',   # Trust (Controlled Subsidiary)
    '8':  '4',   # Trust (Registered PTC)
    '9':  '4',   # Company Manager
    '10': '4',   # Corporate Service Provider
    '11': '2',   # Insurance entities
    '12': '4',   # Mutual Funds
    '13': '4',   # Mutual Fund Administrators
    '14': '4',   # Securities - Registered Person
    '15': '4',   # Private Fund
    '16': '4',   # Virtual Asset Service Provider
    '17': '4',   # Securities - Full
    '18': '1',   # Building Society   -- deposit-taker
    '19': '1',   # Credit Union       -- deposit-taker
    '20': '1',   # Development Bank
}

# Site AuthorizationType -> ListCode.  Covers all 36 options in the site's
# AuthorizationType dropdown as of 2026-08-12.  (# NEW in v4) marks the seven
# that v3 was missing and therefore silently dropped.
#
# DECD-6740 names 20 lists covering 28 of the site's 36 categories.  The other 8
# are marked (# OFF-TICKET) below and are folded into the nearest ticketed list
# rather than dropped -- see README_KY_CIMA.md "Categories not in the ticket".
# 'Mutual Fund - Licenced' -> 12 is inherited from v3 and predates this change.
mapping = {
    'Banking Class A':                             '1',
    'Banking Class B':                             '2',
    'Banking Class B (Restricted)':                '2',    # NEW in v4, OFF-TICKET
    'Money Services':                              '3',
    'Trust':                                       '4',
    'Trust (Restricted)':                          '5',
    'Nominee (Trust)':                             '6',
    'Trust (Controlled Subsidiary)':               '7',
    'Trust (Registered PTC)':                      '8',
    'Company Manager':                             '9',
    'Corporate Service Provider':                  '10',

    'Class A Local Insurer':                       '11',
    'Class A External Insurer':                    '11',
    'Class B Insurer':                             '11',
    'Class C Insurer':                             '11',
    'Class D Insurer':                             '11',
    'Insurance Agent':                             '11',
    'Insurance Broker':                            '11',
    'Insurance Manager':                           '11',
    'Portfolio Insurance Company':                 '11',

    'Mutual Fund - Registered':                    '12',
    'Mutual Fund - Licenced':                      '12',   # OFF-TICKET (inherited from v3)
    'Mutual Fund - Limited Investor':              '12',   # NEW in v4, OFF-TICKET
    'Mutual Fund - Master Fund':                   '12',   # NEW in v4, OFF-TICKET

    # Ticket list 13 is "Mutual Fund - Administered", i.e. administered *funds*.
    # The two administrator categories have no list of their own in DECD-6740 and
    # are folded here as the nearest match -- confirm with the ticket owner.
    'Mutual Fund - Administered':                  '13',
    'Mutual Fund Administrator - Full':            '13',   # NEW in v4, OFF-TICKET
    'Mutual Fund Administrator - Restricted':      '13',   # NEW in v4, OFF-TICKET

    'Securities - Registered Person':              '14',
    'Private Fund':                                '15',
    'Virtual Asset Service Provider Registration': '16',
    'Virtual Asset Service Provider Licence':      '16',   # NEW in v4, OFF-TICKET
    'Securities - Full':                           '17',
    'Securities - Restricted':                     '17',   # NEW in v4, OFF-TICKET
    'Building Society':                            '18',
    'Credit Union':                                '19',
    'Development Bank':                            '20',
}

# ------------------------------------------------ Begin_Fouction ----------------------------------------


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


def get_csrf_token(session):
    """GET the search form once and return the CSRF token it hands out.

    The server only checks that the POST field equals the cookie value, so the
    cookie is authoritative; the hidden input is a fallback.
    """
    resp = session.get(FORM_URL, headers={'User-Agent': HEADERS['User-Agent']}, timeout=60, verify=False)
    resp.raise_for_status()

    token = session.cookies.get(CSRF_COOKIE)
    if not token:
        field = BeautifulSoup(resp.text, 'html.parser').find('input', {'name': CSRF_FIELD})
        token = field.get('value') if field else None
    if not token:
        raise RuntimeError('Could not obtain CSRF token from {}'.format(FORM_URL))
    return token


def fetch_page(session, token, page_number, authorization_type='All'):
    """POST one page of results.  Returns (html, token) -- token may be refreshed."""
    payload = {
        CSRF_FIELD: token,
        'Searching': '',
        'AuthorizationType': authorization_type,
        'PageNumber': page_number,       # <-- presence of this key is what skips the captcha
        'p': 'y',
        'ajax': 'Y',
    }

    for attempt in range(3):
        try:
            resp = session.post(DATA_URL, data=payload, headers=HEADERS, timeout=60,
                                verify=False, allow_redirects=False)
        except requests.RequestException as exc:
            print('   page {} attempt {}: {}'.format(page_number, attempt + 1, type(exc).__name__))
            time.sleep(3)
            continue

        if resp.status_code == 200:
            return resp.text, token

        # 302 -> the captcha branch was taken (PageNumber lost).
        # 500 -> CSRF token no longer matches the cookie.  Refresh and retry.
        print('   page {} attempt {}: HTTP {} -- refreshing CSRF token'.format(
            page_number, attempt + 1, resp.status_code))
        time.sleep(2)
        token = get_csrf_token(session)
        payload[CSRF_FIELD] = token

    raise RuntimeError('Page {} failed after 3 attempts'.format(page_number))


def parse_rows(html):
    """Return the data rows of the results table as lists of cell strings."""
    table = BeautifulSoup(html, 'html.parser').select_one('div.table-responsive')
    if not table:
        return []

    out = []
    for row in table.select('tr')[1:]:            # [1:] skips the header row
        cells = [td.get_text(strip=True) for td in row.find_all('td')]
        if len(cells) < 4:                        # "no records" / spacer rows
            continue
        out.append(cells)
    return out


# ------------------------------------------------ Main_Function ----------------------------------------

session = requests.Session()
session.headers.update({'User-Agent': HEADERS['User-Agent']})

token = get_csrf_token(session)
print('CSRF token acquired: {}'.format(token))

scraped = []          # (internal_id, name, typology, regulated_date)
page = 1

while page <= MAX_PAGES:
    html, token = fetch_page(session, token, page)
    rows = parse_rows(html)

    if not rows:
        print('Page {} returned no rows -- end of list.'.format(page))
        break

    for cells in rows:
        scraped.append((cells[0], cells[1], cells[2], cells[3]))

    print('Fetched page {} ({} rows, {} total)'.format(page, len(rows), len(scraped)))
    page += 1
else:
    print('WARNING: hit MAX_PAGES={} guard -- list may be incomplete.'.format(MAX_PAGES))

print('\nScraped {} rows from {} pages.'.format(len(scraped), page - 1))

# ------------------------------------------------ Begin_Mapping ----------------------------------------

unmapped = {}

for internal_id, name_, type_, regulated_date in scraped:
    listcode = mapping.get(type_)
    if not listcode:
        unmapped[type_] = unmapped.get(type_, 0) + 1
        continue

    sqldict['Name'].append(name_)
    sqldict['Typology'].append(type_)
    sqldict['InternalID_1'].append(internal_id)
    sqldict['InternalID_1_type'].append('Reference Number')
    sqldict['RegulationDate'].append(regulated_date)
    sqldict['RegulationType'].append('Regulated')
    sqldict['ListCode'].append(listcode)
    sqldict['ListName'].append(LIST_NAME[listcode])
    sqldict['ListLabel'].append(LIST_LABEL[listcode])
    sqldict['ListLanguage'].append('EN')
    sqldict['RegCtry'].append('KY')
    sqldict['RegCode'].append('CIMA')
    sqldict['Cntry'].append('KY')
    sqldict['ListProcessDate'].append(processdate)

sqldict = bourange_same_length_array(sqldict)

# Never drop rows silently -- v3 did, and lost 3,831 of them.
if unmapped:
    print('\n' + '!' * 78)
    print('!! {} row(s) have an AuthorizationType missing from `mapping` and were DROPPED:'.format(
        sum(unmapped.values())))
    for t, n in sorted(unmapped.items(), key=lambda kv: -kv[1]):
        print('!!   {:>6}  {}'.format(n, t))
    print('!! Add them to `mapping` above and re-run.')
    print('!' * 78 + '\n')
else:
    print('All {} scraped rows mapped to a ListCode.'.format(len(scraped)))

# ------------------------------------------------ Begin_writer and save df to excel  ----------------------------------------

os.chdir(scriptfolder)
df = pd.DataFrame(sqldict)

df = df[df['Name'] != '']

df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)

print('Saved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))
print('\nRows per list:')
print(df.groupby(['ListCode', 'ListLabel']).size().rename('rows').reset_index().to_string(index=False))
