# -*- coding: utf-8 -*-
# ------------------------------------------------------------------
# ZM BZA  -  Bank of Zambia
# Source page: https://www.boz.zm/financial-stability/registered-financial-institutions
# Jira:   DECD-6327  (epic DECD-3438, Regulators 2026 - Crawlers)
#
# The page is an Angular SPA (<app-root>); plain requests only returns the empty
# shell. Capturing the browser network log shows the app pages through exactly
# one public JSON endpoint (pages 0..9, 25 records/page, [] when exhausted):
#
#   GET https://www.boz.zm/api/v1/views/registered_financial_institutions?page=N
#
# That endpoint is not behind a WAF - plain `requests` with a desktop UA and
# verify=False returns clean JSON, so no browser automation is needed here.
#
# ---- v2 CHANGES vs v1 (why the v1 output was wrong) --------------------------
# 1) DUPLICATE NODES (the real bug).  The raw feed returns 216 records but the
#    site renders 213 ("Showing 1-10 of 213 institutions") and its four named
#    filter cards read 15 / 100 / 9 / 89.  The Angular front-end collapses
#    records that share the same title within the same content type; there are
#    exactly three such pairs, all genuine content duplicates (same category,
#    same licence):
#       payment_system_institutions : BEELINE FINTECH LIMITED (nodes 113831/113832)
#                                     JustTap Payments Limited (nodes 3611/3138)
#       non_bank_financial_institution: Access Financial Services Limited
#                                     (nodes 3381/3656, both Liquidated)
#    v1 emitted all 91 payment-system records -> 2 rows MORE than the website
#    shows.  v2 de-duplicates on (type, normalised title) keeping the richer of
#    the two records (node 3611 "JustTap" has an empty address, node 3138 has
#    the real one), which reproduces the site counts exactly: 15/91/9/89.
#    NOTE: these are not "rows that appear separately on the site" - the site
#    itself prints a single row for each, verified on the rendered grid.
# 2) RegulationDate for List 4 was empty.  The Drupal JSON:API node feed
#    (/jsonapi/node/payment_system_institutions) exposes
#    field_month_year_of_designation as a clean ISO date for all 91 payment
#    system institutions -> joined in by node id.  (The on-page grid column
#    "Licensed Since" renders "-" because that view simply omits the field.)
# 3) City for List 4 was always blank.  The payment-systems content type has no
#    city field, but its free-text field_address ends in the town in caps; the
#    town is now recovered against a Zambian town list (41 of the 43 non-empty
#    addresses resolve).
# 4) List 2 gained ASA MICROFINANCE ZAMBIA LIMITED (added by BOZ after the
#    2026-07-27 run) - 90 -> 91.
#
# Content type -> Jira list mapping (unchanged from v1, verified correct):
#   type == 'banks_and_deposit_non_banks'    -> field_commercial_bank_non_bank
#         "Commercial Banks"         -> ListNr 1
#         "Deposit Taking Non-Banks" -> ListNr 3
#   type == 'non_bank_financial_institution' -> field_institution_category
#         everything EXCEPT "Liquidated Institutions" -> ListNr 2
#         (Jira comment: "please remove liquidated institutions")
#   type == 'payment_system_institutions'    -> ListNr 4
# ------------------------------------------------------------------
import os
import re
import html
import json
import datetime
import requests
import pandas as pd

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ------------------------------------------------ Begin_ fileName ----------------------------------------
regulatorName = 'ZM BZA'  # Bank of Zambia
print(f"Running {regulatorName} Web Scraping Tool v.2.0")

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":", ".")[:-7])

# ------ define the workspace path -----
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))  # production environment (.py)
except NameError:
    scriptfolder = os.getcwd()  # notebook environment
os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder')
os.makedirs(tempfolder, exist_ok=True)

API_URL = "https://www.boz.zm/api/v1/views/registered_financial_institutions"
JSONAPI_PS = "https://www.boz.zm/jsonapi/node/payment_system_institutions"
PAGE_URL = "https://www.boz.zm/financial-stability/registered-financial-institutions"

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


# ------------------------------------------------ Lists (ListNr -> ListName / ListLabel) --------------------------------
# ListLabel: 1 = bank, 2 = insurance, 3 = bank & insurance, 4 = everything else (per CLAUDE.md).
# List 1 (Commercial Banks) and List 3 (Deposit Taking Non-Banks) are deposit-taking, prudentially
# supervised entities that BOZ itself groups under one "banks_and_deposit_non_banks" content type
# -> ListLabel 1.  List 2 (microfinance, bureaux de change, leasing/finance, credit reference
# bureaus, development finance) and List 4 (payment system institutions) are neither bank nor
# insurance lists -> ListLabel 4.
LIST_META = {
    1: {"ListName": "Registered Commercial Banks", "ListLabel": 1},
    2: {"ListName": "Registered Non-Bank Financial Institutions", "ListLabel": 4},
    3: {"ListName": "Deposit Taking Non-Banks", "ListLabel": 1},
    4: {"ListName": "Payment System Institutions", "ListLabel": 4},
}

# ------------------------------------------------ Fetch helpers ----------------------------------------
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
    'Accept': 'application/json',
    'Referer': PAGE_URL,
}

TAG_RE = re.compile(r'<[^>]+>')
WS_RE = re.compile(r'\s+')
COMMA_RE = re.compile(r'\s+,')
NODE_RE = re.compile(r'/node/(\d+)')


def clean_html(raw):
    """Strip HTML tags/entities from a Drupal-views text field, collapse whitespace."""
    if not raw:
        return ''
    text = TAG_RE.sub(' ', str(raw))
    text = html.unescape(text)
    text = WS_RE.sub(' ', text).strip()
    text = COMMA_RE.sub(',', text)
    return text.strip(' ,."')


def clean_ws(raw):
    if not raw:
        return ''
    text = html.unescape(str(raw))
    return WS_RE.sub(' ', text).strip(' ,."')


PLACEHOLDER_RE = re.compile(r'^[.\-–—\s]*$')  # e.g. a lone "." with no real content


def drop_placeholder(text):
    """Blank out junk placeholder values (BOZ's payment-systems feed uses a lone
    '.' for some 'field_address' entries when no real address is on file)."""
    return '' if PLACEHOLDER_RE.match(text) else text


# Zambian towns/cities, used to recover City from the payment-systems free-text address,
# which is the only address field that content type carries.
ZM_TOWNS = ['KAPIRI MPOSHI', 'CHILILABOMBWE', 'KASUMBALESA', 'LIVINGSTONE', 'KALULUSHI',
            'MPULUNGU', 'MAZABUKA', 'CHINGOLA', 'MUFULIRA', 'LUANSHYA', 'SIAVONGA', 'CHIRUNDU',
            'NAKONDE', 'PETAUKE', 'SESHEKE', 'SERENJE', 'ZAMBEZI', 'CHIBOMBO', 'LUNDAZI',
            'CHIPATA', 'SOLWEZI', 'MUMBWA', 'KASAMA', 'KATETE', 'SAMFYA', 'MKUSHI', 'NYIMBA',
            'LUSAKA', 'KITWE', 'KABWE', 'MANSA', 'MONGU', 'CHOMA', 'KAFUE', 'MPIKA', 'MONZE',
            'KAOMA', 'NDOLA']


def city_from_address(address):
    """Return the town mentioned last in a free-text address ('' if none found)."""
    if not address:
        return ''
    upper = address.upper()
    hits = [(upper.rfind(town), town) for town in ZM_TOWNS if town in upper]
    if not hits:
        return ''
    return max(hits)[1].title()


def node_id(record):
    match = NODE_RE.search(str(record.get('title', '')))
    return match.group(1) if match else ''


def fetch_all_records():
    """Page through the public JSON API until an empty page is returned."""
    records = []
    page = 0
    while True:
        r = requests.get(API_URL, headers=HEADERS, params={'page': page}, verify=False, timeout=60)
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        records.extend(data)
        page += 1
        if page > 100:  # safety valve against an infinite loop
            break
    return records


def fetch_designation_dates():
    """node id -> field_month_year_of_designation (ISO date) for payment system institutions."""
    dates = {}
    url = JSONAPI_PS + '?page[limit]=50'
    while url:
        r = requests.get(url, headers=HEADERS, verify=False, timeout=60)
        r.raise_for_status()
        payload = r.json()
        for item in payload.get('data', []):
            attrs = item.get('attributes', {})
            nid = str(attrs.get('drupal_internal__nid', ''))
            value = attrs.get('field_month_year_of_designation') or ''
            if nid and value:
                dates[nid] = str(value)[:10]
        url = payload.get('links', {}).get('next', {}).get('href')
    return dates


def richness(record):
    """How many populated fields a record carries - used to keep the better of two duplicates."""
    return sum(1 for k, v in record.items() if k not in ('type', 'title') and clean_html(v))


def dedupe_like_website(records):
    """The BOZ front-end collapses same-title records inside a content type; mirror that so the
    row counts equal what the site prints (216 raw -> 213, matching 'of 213 institutions')."""
    best = {}
    order = []
    for item in records:
        key = (item.get('type', ''), clean_html(item.get('title', '')).upper())
        if key not in best:
            best[key] = item
            order.append(key)
        elif richness(item) > richness(best[key]):
            best[key] = item
    return [best[k] for k in order]


# ------------------------------------------------ Fetch + save raw ----------------------------------------
raw_records = fetch_all_records()
ps_dates = fetch_designation_dates()
print(f"Fetched {len(raw_records)} raw records from API across pages")
print(f"Fetched {len(ps_dates)} designation dates for payment system institutions")

with open(os.path.join(tempfolder, 'registered_financial_institutions_raw.json'), 'w', encoding='utf-8') as f:
    json.dump(raw_records, f, ensure_ascii=False, indent=1)

records = dedupe_like_website(raw_records)
print(f"After collapsing same-title duplicates (as the website does): {len(records)} records")

# ------------------------------------------------ Begin_ scraping ----------------------------------------
list_counts = {1: 0, 2: 0, 3: 0, 4: 0}
skipped_liquidated = 0
skipped_unknown = 0

for item in records:
    name = clean_html(item.get('title', ''))
    if not name:
        continue

    item_type = item.get('type', '')
    regdate = ''

    if item_type == 'banks_and_deposit_non_banks':
        subcat = clean_html(item.get('field_commercial_bank_non_bank', ''))
        if subcat == 'Commercial Banks':
            listcode = 1
        elif subcat == 'Deposit Taking Non-Banks':
            listcode = 3
        else:
            skipped_unknown += 1
            continue
        license_type = subcat
        address = clean_html(item.get('field_postal_address', ''))
        city = clean_ws(item.get('field_city', ''))
        phone = clean_ws(item.get('field_telephone', ''))
        email = ''

    elif item_type == 'non_bank_financial_institution':
        subcat = clean_html(item.get('field_institution_category', ''))
        if subcat == 'Liquidated Institutions':
            skipped_liquidated += 1
            continue  # Jira comment: "please remove liquidated institutions"
        listcode = 2
        license_type = subcat
        address = clean_html(item.get('field_institution_address', ''))
        city = clean_ws(item.get('field_institution_city', ''))
        phone = clean_ws(item.get('field_institution_telephone', ''))
        email = clean_ws(item.get('field_email', ''))

    elif item_type == 'payment_system_institutions':
        listcode = 4
        ptype = clean_html(item.get('field_payment_system_type', ''))
        licenses = clean_html(item.get('field_payment_system_license_s', ''))
        license_type = f"{ptype} ({licenses})" if (ptype and licenses) else (ptype or licenses)
        address = drop_placeholder(clean_ws(item.get('field_address', '')))
        city = city_from_address(address)  # no separate city field on this content type
        phone = ''  # not provided for this content type
        email = ''
        regdate = ps_dates.get(node_id(item), '')  # month/year of designation

    else:
        skipped_unknown += 1
        continue

    meta = LIST_META[listcode]
    sqldict['Name'].append(name)
    sqldict['License_Type'].append(license_type)
    sqldict['Address_1'].append(address)
    sqldict['City'].append(city)
    sqldict['Phone'].append(phone)
    sqldict['Email'].append(email)
    sqldict['Cntry'].append('ZM')
    sqldict['RegulationType'].append('Regulated')
    sqldict['RegulationDate'].append(regdate)
    sqldict['ListName'].append(meta['ListName'])
    sqldict['ListLabel'].append(meta['ListLabel'])
    sqldict['ListLanguage'].append('EN')
    sqldict['RegCtry'].append('ZM')
    sqldict['RegCode'].append('BZA')
    sqldict['ListCode'].append(listcode)
    sqldict['ListProcessDate'].append(processdate)
    sqldict = bourange_same_length_array(sqldict)
    list_counts[listcode] += 1

print("\n==== Per-list row counts (expected from the website: 15 / 91 / 9 / 89) ====")
for code, meta in LIST_META.items():
    print(f"List {code} - {meta['ListName']}: {list_counts[code]}")
print(f"Skipped (Liquidated Institutions, per Jira): {skipped_liquidated}")
print(f"Skipped (unrecognized type/subcategory): {skipped_unknown}")

# ------------------------------------------------ save df to excel ----------------------------------------
os.chdir(scriptfolder)
df = pd.DataFrame(sqldict)

df = df[df['Name'] != '']

df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)

print('Saved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))
