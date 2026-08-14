#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GB GFSC -- Guernsey Financial Services Commission, registered / regulated entities.

Jira: https://moodysdatapipeline.atlassian.net/browse/DECD-6745
(the ticket has no description, so the list inventory below was taken from the
live site and from v1.6's own code, as instructed.)

v1.7 changes vs v1.6:
  * SELENIUM REMOVED ENTIRELY.  v1.6 drove Chrome, accepted the cookie
    banner, clicked 11 filter checkboxes by positional xpath
    ('.../div[2]/div/div[1]/label[8]/input'), then clicked through the
    DataTables pager one page at a time.  The grid is in fact a DataTables
    client-side table fed by two plain JSON endpoints, which return the
    WHOLE dataset in one call (measured live 2026-08-13):
        https://www.gfsc.gg/gfsc-company/feed/registeredbusiness  ->  132 rows
        https://www.gfsc.gg/gfsc-company/feed/regulated           -> 3770 rows
    v1.7 reads those directly.  No browser, no cookie banner, no pager, and
    the 11 positional xpaths -- which silently tick the wrong box the moment
    GFSC reorders the panel -- are gone.
  * DEBUG BREAKS REMOVED.  v1.6 still contained
        if page == 2 : break        # -> only ever 3 pages of the grid
        if i == 10   : break        # -> only ever 11 detail pages per list
    so it could never have produced a complete file: at most 33 rows per
    list reached sqldict.
  * LIST 3 REDEFINED (confirmed with the user).  v1.6's third pass ticked the
    11 "(Revoked/Surrendered/Suspended)" filters and wrote every row it saw
    as RegulationType 'Formerly Regulated' with ListCode '2'.  The filter
    panel is ADDITIVE, not exclusive: default view 2545 rows, all 11 boxes
    ticked 3770 rows.  So v1.6's list 3 was "the 2545 currently-regulated
    entities PLUS the 1225 revoked ones", all mislabelled Formerly Regulated
    and all colliding with list 2 on ListCode '2'.
    v1.7 splits the single 3770-row feed on the entity's own filter
    categories: list 2 = 2545 current, list 3 = 1225 revoked / surrendered /
    suspended, ListCode '3'.  132 + 2545 + 1225 = 3902 rows.
  * pandas 2.x.  v1.6 ended with writer.save(), removed in pandas 2.0
    (AttributeError: 'OpenpyxlWriter' object has no attribute 'save').
  * City / Zip fix.  v1.6 took City = Address.split(',')[-2], which is the
    ISLAND ('Guernsey'), never the town.  v1.7 peels the postcode, then the
    island/country token, and takes the town below it -- 'St Peter Port'
    instead of 'Guernsey' (see split_gg_address).
  * ListName added (v1.6 never filled it), ListLanguage 'EN', and the licence
    text from the feed -> License_Type (v1.6 had it commented out).
  * scriptfolder resolved per project convention -- v1.6 hard-coded
    C:\\Users\\wuj1\\OneDrive - moodys.com\\... which is the retired tenant.
  * Non-schema 'Check' column dropped from sqldict.
  * Detail pages (one per entity, for the address) are fetched with a small
    thread pool.  Sequentially this is ~16 minutes for 3902 pages; at 8
    workers it is a couple of minutes.

NOTE -- the 2545 / 1225 split, measured 2026-08-13:
  Three rows carry a broken Filters value where GFSC's own markup leaks into
  the category string, e.g.
      'Schemes (Revoked/Surrendered/Suspended)<span class="column-has-green-funds"></span>'
  DataTables matches the checkbox label against the exact category string, so
  those three do NOT match the revoked filter and stay in the default view.
  REVOKED_CATEGORY below reproduces that (it anchors on a trailing
  parenthesis), which is what makes the counts come out at exactly the 2545 /
  1225 a human sees on the site.  The three rows are printed at the end of the
  run so the behaviour is visible rather than hidden.
"""

# ------------------------------------------------ Begin_Librairie ----------------------------------------

import datetime
import os
import re
from concurrent.futures import ThreadPoolExecutor
from time import sleep

import pandas as pd
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ------------------------------------------------ Begin_fileName ----------------------------------------

regulatorName = 'GB GFSC'

print("Running {} Web Scraping Tool v.1.7".format(regulatorName))

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

BASE = 'https://www.gfsc.gg'

FEED_REGISTERED = BASE + '/gfsc-company/feed/registeredbusiness'
FEED_REGULATED = BASE + '/gfsc-company/feed/regulated'

LN_REGISTERED = 'List of Registered Entities'
LN_REGULATED = 'List of Regulated Entities'
# LN_FORMER = 'List of Regulated Entities (Revoked/Surrendered/Suspended)'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'en-GB,en;q=0.9',
}

WORKERS = 8

# The corporate proxy answers 502 Bad Gateway every so often -- a v1.7 run died
# on exactly that while fetching the regulated feed.  Every request goes through
# get_with_retry() instead of session.get() for this reason.
RETRIES = 5

# Row counts seen on the site on 2026-08-13.  Printed against the live counts
# at the end of the run; they are expected to drift as GFSC updates the
# registers, they are here so a sudden collapse is obvious.
BASELINE = {'1': 132, '2': 2545, '3': 1225}

# A licence category counts as revoked/surrendered/suspended when the token
# ENDS in a parenthesis that mentions one of those words:
#     'Schemes (Revoked/Surrendered/Suspended)'                        -> yes
#     'Lead/Joint Licensee (Surrendered prior to 1st November 2021)'   -> yes
#     'Closed Ended Scheme (Registered)'                               -> no
# The trailing-parenthesis anchor is deliberate; see the module docstring.
REVOKED_CATEGORY = re.compile(r'\([^()]*(?:revoked|surrendered|suspended)[^()]*\)\s*$', re.I)

# Bailiwick / country tokens that sit between the town and the postcode.
# Alderney and Sark are deliberately NOT here: they have no town below the
# island, so they must be allowed to stand as the City themselves.
COUNTRY_TOKENS = {'guernsey', 'united kingdom', 'england', 'scotland', 'wales',
                  'jersey', 'isle of man', 'uk', 'great britain',
                  'channel islands', 'france', 'switzerland', 'ireland',
                  'republic of ireland', 'usa', 'united states',
                  'united states of america', 'south africa', 'luxembourg',
                  'netherlands', 'the netherlands', 'germany', 'spain', 'italy',
                  'portugal', 'belgium', 'sweden', 'norway', 'denmark', 'finland',
                  'canada', 'australia', 'singapore', 'hong kong', 'japan',
                  'cayman islands', 'bermuda', 'british virgin islands', 'bvi',
                  'malta', 'monaco', 'cyprus', 'gibraltar', 'mauritius'}

POSTCODE = re.compile(r'^[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$', re.I)

# Overseas postcodes that POSTCODE does not describe -- '75009' (Paris),
# 'D02 F3F2' (Dublin), 'DE 19808' (Delaware).  Without this they survive the
# peel and get written into City.  At most two short alphanumeric words, and
# at least one digit, so a town name can never match.
FOREIGN_ZIP = re.compile(r'^(?=.*\d)[A-Z0-9]{1,6}(?:[ -][A-Z0-9]{1,6})?$', re.I)

# A trailing chunk that is really a street line rather than a town.  'st' is
# NOT in the word list -- it would swallow 'St Peter Port', which is the town
# on most of the register.
STREET_LINE = re.compile(
    r'^\d+[A-Za-z]?\s'
    r'|\b(?:street|road|avenue|lane|court|esplanade|place|way|house|quay|'
    r'terrace|drive|row|dock|building|floor|level|suite|box|square|crescent|'
    r'parade)\b', re.I)

mangled_categories = []
unreadable = []

# ------------------------------------------------ Begin_Fonction ----------------------------------------


def norm(text):
    """Collapse whitespace, drop non-breaking spaces and stray tabs."""
    return re.sub(r'\s+', ' ', (text or '').replace('\xa0', ' ')).strip()


def strip_html(value):
    """The feed wraps most cells in an <a>; keep the text only."""
    if not value:
        return ''
    return norm(BeautifulSoup(str(value), 'html.parser').get_text(' ', strip=True))


def detail_url(record):
    """The absolute detail-page URL carried in the feed's View cell."""
    match = re.search(r'href="([^"]+)"', record.get('View') or '')
    if match is None:
        match = re.search(r'href="([^"]+)"', record.get('name') or '')
    return BASE + match.group(1) if match else ''


def categories(record):
    """The entity's filter categories, exactly as DataTables sees them."""
    raw = record.get('Filters') or ''
    return [token.strip() for token in raw.split(',') if token.strip()]


def is_revoked(record):
    revoked = any(REVOKED_CATEGORY.search(token) for token in categories(record))
    if not revoked:
        for token in categories(record):
            if re.search(r'revoked|surrendered|suspended', token, re.I):
                mangled_categories.append((strip_html(record.get('name')), token))
    return revoked


def split_gg_address(address):
    """'Royal Bank Place, St Peter Port, Guernsey, GY1 2HJ' -> town + postcode.

    v1.6 used split(',')[-2] for City, which returns the island rather than
    the town on every Guernsey address.  Here the postcode is peeled first,
    then the island / country token if there is one, and what remains at the
    end is the town.  Alderney addresses have no town below the island, so
    the island itself is kept as City.
    """
    address = norm(address)
    if not address:
        return '', ''

    parts = [part.strip() for part in address.split(',') if part.strip()]
    if not parts:
        return '', ''

    # 1. peel the postcode.  POSTCODE covers the GY/JE/UK shapes; FOREIGN_ZIP
    #    catches the overseas ones ('75009', 'D02 F3F2', 'DE 19808') that would
    #    otherwise be left behind and picked up as the town.
    zip_code = ''
    if POSTCODE.match(parts[-1]) or FOREIGN_ZIP.match(parts[-1]):
        zip_code = parts.pop()

    # 2. peel every trailing island / country token, not just one.
    island = ''
    while parts and parts[-1].lower() in COUNTRY_TOKENS:
        island = parts.pop()

    if not parts:
        # nothing below the island -- Alderney and Sark addresses look like
        # this, and the island IS the town there.
        return island, zip_code

    # 3. what is left is the town, unless it is plainly a street line.  A
    #    street in the City column is worse than an empty City column, because
    #    it looks like real data.
    city = parts[-1]
    if STREET_LINE.match(city):
        return '', zip_code

    return city, zip_code


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


def make_session():
    session = requests.Session()
    session.verify = False
    session.headers.update(HEADERS)
    return session


def get_with_retry(session, url, attempts=RETRIES):
    """The corporate proxy intermittently answers 502; retry with backoff.

    Raises on final failure -- a silent '' here would look exactly like an
    entity that publishes no address, which is the one thing that must not
    happen quietly.
    """
    last = None
    for attempt in range(attempts):
        try:
            response = session.get(url, timeout=180)
            if response.status_code == 200:
                return response
            last = 'HTTP {}'.format(response.status_code)
        except Exception as err:
            last = str(err)[:120]
        sleep(1.5 * (attempt + 1))
    raise RuntimeError('{} failed after {} attempts: {}'.format(url, attempts, last))


def fetch_feed(session, url):
    return get_with_retry(session, url).json()['companies']


def fetch_address(args):
    """One detail page -> its published address.

    Returns '' when the entity simply has no address block, and None when the
    page could not be read at all, so the two cases stay distinguishable.
    """
    session, url = args
    if not url:
        return ''
    try:
        response = get_with_retry(session, url)
    except RuntimeError:
        return None
    content = BeautifulSoup(response.text, 'html.parser').find(
        'div', {'id': 'block-gfsc-theme-content'})
    if content is None:
        return ''
    container = content.find('div', {'class': 'details-container'})
    if container is None:
        return ''
    values = container.find_all('div', {'class': 'value'})
    return norm(values[0].get_text(' ', strip=True)) if values else ''


def fetch_all_addresses(session, urls, label):
    """Detail pages in parallel -- 3902 of them at ~0.25 s each is ~16 min serial."""
    print('  fetching {} detail page(s) with {} workers ...'.format(len(urls), WORKERS))
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        addresses = list(pool.map(fetch_address, [(session, url) for url in urls]))
    failed = sum(1 for a in addresses if a is None)
    addresses = ['' if a is None else a for a in addresses]
    filled = sum(1 for a in addresses if a)
    print('  {}: {}/{} entities publish an address'.format(label, filled, len(addresses)))
    if failed:
        print('  !! {} detail page(s) in {} could not be read after {} attempts --'
              ' their Address_1 is blank for that reason, not because the site is'
              ' empty. Re-run before delivering.'.format(failed, label, RETRIES))
        unreadable.append((label, failed))
    return addresses


def emit(records, list_code, list_name, regulation_type, list_label, addresses):
    for record, address in zip(records, addresses):
        city, zip_code = split_gg_address(address)
        append_row({
            'Name': strip_html(record.get('name')),
            'InternalID_1': strip_html(record.get('GFSC_x0020_Ref')),
            'InternalID_1_type': 'GFSC code',
            'License_Type': strip_html(record.get('Licences')),
            'Address_1': address,
            'City': city,
            'Zip': zip_code,
            'Cntry': 'GB',
            'ListLabel': list_label,
            'RegulationType': regulation_type,
            'RegCtry': 'GB',
            'RegCode': 'GFSC',
            'ListCode': list_code,
            'ListName': list_name,
            'ListLanguage': 'EN',
        })


# ------------------------------------------------ Begin_Main ----------------------------------------

session = make_session()

# ---------------------------------------------------------------------------
# List 1 -- registered entities (prescribed businesses, money service providers)
# ---------------------------------------------------------------------------

print('\n[INFO] : Working 1/3 _(GB GFSC 1)_  {}'.format(LN_REGISTERED))
registered = fetch_feed(session, FEED_REGISTERED)
print('  feed rows: {}'.format(len(registered)))
addresses = fetch_all_addresses(session, [detail_url(r) for r in registered], 'list 1')
emit(registered, '1', LN_REGISTERED, 'Registered', '', addresses)
print('  [1] {:<58} {:>5} rows'.format(LN_REGISTERED, len(registered)))

# ---------------------------------------------------------------------------
# Lists 2 and 3 -- one feed, split on the entity's own filter categories
# ---------------------------------------------------------------------------

print('\n[INFO] : Working 2/3 and 3/3 _(GB GFSC 2 / 3)_')
regulated_feed = fetch_feed(session, FEED_REGULATED)
print('  feed rows: {}'.format(len(regulated_feed)))

former, current = [], []
for record in regulated_feed:
    (former if is_revoked(record) else current).append(record)
print('  split: {} currently regulated / {} revoked-surrendered-suspended'.format(
    len(current), len(former)))

addresses = fetch_all_addresses(session, [detail_url(r) for r in current], 'list 2')
emit(current, '2', LN_REGULATED, 'Regulated', '', addresses)
print('  [2] {:<58} {:>5} rows'.format(LN_REGULATED, len(current)))

# addresses = fetch_all_addresses(session, [detail_url(r) for r in former], 'list 3')
# ListLabel 4 -- GFSC's regulated register is banks + insurers + investment +
# fiduciary, i.e. "everything else" under the project's 1/2/3/4 rule.  Lists 1
# and 2 already carry a ListLabel filled in by hand downstream and are left
# alone; list 3 is new in v1.7, so it gets one here.
# emit(former, '3', LN_FORMER, 'Formerly Regulated', '4', addresses)
# print('  [3] {:<58} {:>5} rows'.format(LN_FORMER, len(former)))

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

print('\nAgainst the 2026-08-13 baseline:')
for list_code in sorted(BASELINE):
    live = int((df['ListCode'] == list_code).sum())
    flag = '' if live == BASELINE[list_code] else '   <-- changed'
    print('  list {}  baseline {:>5}  now {:>5}{}'.format(list_code, BASELINE[list_code], live, flag))

if mangled_categories:
    print('\n[NOTE] {} row(s) mention revoked/surrendered/suspended in a filter category'
          ' that GFSC\'s own markup has corrupted, so the site itself leaves them in the'
          ' regulated view. They are reported here as list 2:'.format(len(mangled_categories)))
    for name, token in mangled_categories:
        print('   {:<45} {!r}'.format(name[:45], token[:80]))

if unreadable:
    print('\n[WARN] the proxy refused some detail pages even after {} attempts, so their'
          ' Address_1 / City / Zip are blank for a network reason rather than a site'
          ' one -- re-run before delivering this file:'.format(RETRIES))
    for label, failed in unreadable:
        print('   {:<40} {} page(s)'.format(label, failed))
else:
    print('\nEvery detail page was read successfully.')
