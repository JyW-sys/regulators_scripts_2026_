# -*- coding: utf-8 -*-
# ------------------------------------------------------------------
# NG CBNI  -  Central Bank of Nigeria (Financial Institutions directory)
# Jira:   DECD-6334  (epic DECD-3438, Regulators 2026 - Crawlers)
#
# Each of the 12 Jira lists is a page at https://www.cbn.gov.ng/supervision/Inst-XX.html
# whose Kendo grid ("Click the button to download the Excel file...") is populated
# client-side from a JSON API at https://www.cbn.gov.ng/api/<GetXxx>. Rather than
# driving a browser to click the Kendo "Excel" toolbar button, we call the same
# JSON API directly with plain requests (no Cloudflare/WAF challenge observed on
# this domain - plain GET returns 200) to get the id/name roster for each list.
#
# The Jira comment "click on each company in the website ... extract the
# information" refers to the per-entity detail page fi.html?id=<id>, which is
# itself populated from /api/GetFinInstById/<id> - a JSON record with address,
# phone, email, website, institute type, licence category, ownership type and
# licence date. We call that endpoint once per entity (threaded) to enrich rows.
#
# NOTE: a large fraction of ids (varies by list, observed roughly a third to a
# half) return HTTP 500 from GetFinInstById - a server-side bug on CBN's end
# (consistent/reproducible, not rate-limiting - confirmed by retrying the same
# id with delays). For those ids we keep the row (name from the roster API) and
# leave the detail fields blank rather than fake data.
# ------------------------------------------------------------------
import os
import time
import datetime
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

regulatorName = 'NG CBNI'  # Central Bank of Nigeria
print(f"Running {regulatorName} Web Scraping Tool v.1.0")

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":", ".")[:-7])

# ------ define the workspace path -----
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))
except NameError:
    scriptfolder = os.getcwd()
os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder')
os.makedirs(tempfolder, exist_ok=True)

BASE = 'https://www.cbn.gov.ng'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                         'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'}

session = requests.Session()
session.headers.update(HEADERS)
session.verify = False

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


# ------------------------------------------------ Lists (ListCode -> (ListName, [roster APIs], ListLabel)) ----------------------------------------
# ListLabel: 1 = bank, 4 = other (CBN does not regulate insurance in Nigeria - that's
# NAICOM - so no list here is insurance). Judgment calls documented in the README:
#   - Discount Houses / Merchant Banks / Micro-Finance Banks / Non-Interest Banks /
#     Primary Mortgage Institution / Payment Service Banks are all licensed under
#     Nigeria's Banks and Other Financial Institutions Act (BOFIA) as bank categories -> 1
#   - Development Finance Institutions are government development banks -> 1
#   - Finance Companies, Bureau de Change, Holding Companies and Mobile Money
#     Operators are non-bank financial institutions -> 4
LISTS = {
    1:  ('Commercial banks',                   ['GetDMBs'],                          1),
    2:  ('Development Finance Institutions',   ['GetDFIs'],                          1),
    3:  ('Discount Houses',                    ['GetDHs'],                           1),
    4:  ('Finance Companies',                  ['GetFCs'],                           4),
    5:  ('Merchant Banks',                     ['GetMBs'],                           1),
    6:  ('Micro-Finance Banks',                ['GetMFBs'],                          1),
    7:  ('Non-Interest Banks',                 ['GetNIBs'],                          1),
    8:  ('Primary Mortgage Institution',       ['GetPMIs'],                          1),
    9:  ('Bureau de Change',                   ['GetBDCsTier1', 'GetBDCsTier2'],     4),
    10: ('Holding Companies',                  ['GetHCs'],                           4),
    11: ('Mobile Money Operators',             ['GetMMOs'],                          4),
    12: ('Payment Service Banks',              ['GetPSBs'],                          1),
}


def clean(s):
    if s is None:
        return ''
    return ' '.join(str(s).replace('\r', ' ').replace('\n', ' ').split()).strip()


# Nigeria's 36 states + FCT are a fixed, known list. CBN's own 'state' field is
# inconsistently truncated for a chunk of records (observed e.g. 'ANA', 'OGU',
# 'LAG', 'ABI' instead of the full name) - this is a source-data quirk, not a
# parsing issue (confirmed the same truncated values come straight off the API).
# We canonicalize via unambiguous prefix match against this fixed list rather
# than leaving inconsistent abbreviations, since these are known proper nouns,
# not guessed/fabricated data.
NG_STATES = ['Abia', 'Adamawa', 'Akwa Ibom', 'Anambra', 'Bauchi', 'Bayelsa', 'Benue',
             'Borno', 'Cross River', 'Delta', 'Ebonyi', 'Edo', 'Ekiti', 'Enugu',
             'Gombe', 'Imo', 'Jigawa', 'Kaduna', 'Kano', 'Katsina', 'Kebbi', 'Kogi',
             'Kwara', 'Lagos', 'Nasarawa', 'Niger', 'Ogun', 'Ondo', 'Osun', 'Oyo',
             'Plateau', 'Rivers', 'Sokoto', 'Taraba', 'Yobe', 'Zamfara', 'Abuja']


def normalize_state(raw):
    s = clean(raw)
    if not s or len(s) < 3:
        return s.title() if s else ''
    matches = [full for full in NG_STATES if full.lower().startswith(s.lower())]
    if len(matches) == 1:
        return matches[0]
    return s.title()


def get_roster(api):
    """Call a Kendo-grid-backing roster API; return list of {'id':.., 'name':..}."""
    r = session.get(f'{BASE}/api/{api}', timeout=60)
    r.raise_for_status()
    return r.json()


def get_detail(entity_id, retries=1):
    """Call GetFinInstById/<id>. Returns dict (possibly empty) - never raises."""
    for attempt in range(retries + 1):
        try:
            r = session.get(f'{BASE}/api/GetFinInstById/{entity_id}', timeout=30)
            if r.status_code == 200:
                data = r.json()
                if data:
                    return data[0]
                return {}
            # Non-200 (observed: consistent HTTP 500 on ~30-50% of ids - a server-
            # side bug on CBN's end, not rate limiting; reproducible on retry).
        except requests.RequestException:
            pass
        time.sleep(0.5)
    return {}


# ------------------------------------------------ Begin_ scraping ----------------------------------------
for code, (listname, apis, listlabel) in LISTS.items():
    roster = []
    for api in apis:
        try:
            roster += get_roster(api)
        except Exception as e:
            print(f"List {code} - {listname}: FAILED to fetch roster {api}: {e}")

    if not roster:
        print(f"List {code} - {listname}: 0 entities (roster fetch failed) -- SKIPPED")
        continue

    ids = [item['id'] for item in roster]
    detail_by_id = {}
    ok, fail = 0, 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(get_detail, i): i for i in ids}
        for fut in as_completed(futures):
            i = futures[fut]
            d = fut.result()
            detail_by_id[i] = d
            if d:
                ok += 1
            else:
                fail += 1

    for item in roster:
        i = item['id']
        d = detail_by_id.get(i, {})
        name = clean(d.get('name')) or clean(item.get('name'))
        if not name:
            continue

        street = clean(d.get('streetAddress'))
        postal = clean(d.get('postalAddress'))
        area = clean(d.get('area'))
        state = clean(d.get('state'))
        addr2 = postal if (postal and postal != street) else area

        sqldict['Name'].append(name)
        sqldict['InternalID_1'].append(str(i))
        sqldict['InternalID_1_type'].append('CBN ID')
        sqldict['CoType'].append(clean(d.get('institutetype')))
        sqldict['License_Type'].append(clean(d.get('categorization')))
        sqldict['Typology'].append(clean(d.get('ownershiptype')))
        sqldict['Address_1'].append(street)
        sqldict['Address_2'].append(addr2)
        sqldict['City'].append(normalize_state(state))
        sqldict['Phone'].append(clean(d.get('telephoneNo')))
        sqldict['Fax'].append(clean(d.get('faxNo')))
        sqldict['Website'].append(clean(d.get('website')))
        sqldict['Email'].append(clean(d.get('email')).lower())
        sqldict['RegulationDate'].append(clean(d.get('datelicensed')))
        sqldict['Cntry'].append('NG')
        sqldict['RegulationType'].append('Regulated')
        sqldict['ListName'].append(listname)
        sqldict['ListLabel'].append(listlabel)
        sqldict['ListLanguage'].append('EN')
        sqldict['RegCtry'].append('NG')
        sqldict['RegCode'].append('CBNI')
        sqldict['ListCode'].append(code)
        sqldict['ListProcessDate'].append(processdate)

    sqldict = bourange_same_length_array(sqldict)
    print(f"List {code} - {listname}: {len(roster)} entities (detail OK: {ok}, detail missing/HTTP-500: {fail})")

# ------------------------------------------------ save df to excel ----------------------------------------
os.chdir(scriptfolder)
df = pd.DataFrame(sqldict)
df = df[df['Name'] != '']
df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)
print('Saved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))
