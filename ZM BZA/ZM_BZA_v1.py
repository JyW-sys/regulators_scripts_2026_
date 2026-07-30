# -*- coding: utf-8 -*-
# ------------------------------------------------------------------
# ZM BZA  -  Bank of Zambia
# Source page: https://www.boz.zm/financial-stability/registered-financial-institutions
# Jira:   DECD-6327  (epic DECD-3438, Regulators 2026 - Crawlers)
#
# The page itself is an Angular single-page app (<app-root>) - plain requests
# only returns the empty shell HTML. Rendering it once with DrissionPage
# (real Chrome) to pass through the JS bootstrap showed the page listens for
# XHR calls to a public JSON endpoint that backs the on-page table & the four
# "named filter" summary cards (Registered Commercial Banks / Registered
# non-bank institutions / Deposit taking Non-banks / Payment Systems):
#
#   GET https://www.boz.zm/api/v1/views/registered_financial_institutions?page=N
#
# This endpoint is NOT behind Cloudflare/WAF - plain `requests` with a
# desktop User-Agent and verify=False returns clean JSON directly (confirmed
# with curl), so no browser automation is needed in the production script.
# It is paginated (25 records/page) and returns [] once exhausted.
#
# Each JSON record carries a 'type' field that cleanly partitions the data
# into the three underlying Drupal content types, which in turn map to the
# four Jira lists:
#   - type == 'banks_and_deposit_non_banks'   -> field_commercial_bank_non_bank
#         "Commercial Banks"        -> ListNr 1 (Registered Commercial Banks)
#         "Deposit Taking Non-Banks"-> ListNr 3 (Deposit Taking Non-Banks)
#   - type == 'non_bank_financial_institution' -> field_institution_category
#         everything EXCEPT "Liquidated Institutions" -> ListNr 2
#         (Jira comment: "please remove liquidated institutions")
#   - type == 'payment_system_institutions'    -> ListNr 4 (Payment System
#         Institutions); field_payment_system_type is the category
#         (Designated Payment System Participants/Businesses/Systems)
#
# Field availability differs cleanly by type (confirmed empirically):
#   banks_and_deposit_non_banks : field_city, field_postal_address,
#                                  field_telephone, field_short_name
#   non_bank_financial_institution: field_institution_address,
#                                  field_institution_city, field_email,
#                                  field_institution_telephone
#   payment_system_institutions  : field_address only (plain text, no
#                                  separate city/phone/email fields on this
#                                  content type)
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
print(f"Running {regulatorName} Web Scraping Tool v.1.0")

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
# List 1 (Commercial Banks) and List 3 (Deposit Taking Non-Banks) are both prudentially-supervised
# deposit-taking entities under BOZ's own "banks_and_deposit_non_banks" grouping -> ListLabel 1 (bank),
# matching the project convention elsewhere (e.g. KE CBK treats "Microfinance Banks" as ListLabel 1).
# List 2 (Non-Bank Financial Institutions: microfinance, bureaux de change, leasing/finance,
# credit reference bureaus, development finance) and List 4 (Payment System Institutions) are neither
# clean bank nor insurance lists -> ListLabel 4 (other), a judgment call documented in the README.
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


def clean_html(raw):
    """Strip HTML tags/entities from a Drupal-views text field, collapse whitespace."""
    if not raw:
        return ''
    text = TAG_RE.sub(' ', str(raw))
    text = html.unescape(text)
    text = WS_RE.sub(' ', text).strip()
    text = COMMA_RE.sub(',', text)
    return text.strip(' ,.')


def clean_ws(raw):
    if not raw:
        return ''
    text = html.unescape(str(raw))
    return WS_RE.sub(' ', text).strip()


PLACEHOLDER_RE = re.compile(r'^[.\-–—\s]*$')  # e.g. a lone "." with no real content


def drop_placeholder(text):
    """Blank out junk placeholder values (BOZ's payment-systems feed uses a lone
    '.' for ~half its 'field_address' entries when no real address is on file)."""
    return '' if PLACEHOLDER_RE.match(text) else text


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


# ------------------------------------------------ Fetch + save raw ----------------------------------------
records = fetch_all_records()
print(f"Fetched {len(records)} raw records from API across pages")

with open(os.path.join(tempfolder, 'registered_financial_institutions_raw.json'), 'w', encoding='utf-8') as f:
    json.dump(records, f, ensure_ascii=False, indent=1)

# ------------------------------------------------ Begin_ scraping ----------------------------------------
list_counts = {1: 0, 2: 0, 3: 0, 4: 0}
skipped_liquidated = 0
skipped_unknown = 0

for item in records:
    name = clean_html(item.get('title', ''))
    if not name:
        continue

    item_type = item.get('type', '')

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
        city = ''   # not provided as a separate field for this content type
        phone = ''  # not provided as a separate field for this content type
        email = ''

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
    sqldict['ListName'].append(meta['ListName'])
    sqldict['ListLabel'].append(meta['ListLabel'])
    sqldict['ListLanguage'].append('EN')
    sqldict['RegCtry'].append('ZM')
    sqldict['RegCode'].append('BZA')
    sqldict['ListCode'].append(listcode)
    sqldict['ListProcessDate'].append(processdate)
    sqldict = bourange_same_length_array(sqldict)
    list_counts[listcode] += 1

print("\n==== Per-list row counts ====")
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
