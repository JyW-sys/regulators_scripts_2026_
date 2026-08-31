#---- Begin_Librairie ----
# =============================================================================
# MT MFSA - Malta Financial Services Authority
# DECD-6834 : List 1 "License Holders"
# Source app : https://fsr.mfsa.mt  (iframed by https://www.mfsa.mt/financial-services-register/)
# Backend    : plain JSON endpoints (no browser, no driver needed)
# =============================================================================
import os
import re
import time
import json
import datetime

import requests
import pandas as pd

requests.packages.urllib3.disable_warnings()  # corporate TLS proxy

#---- Begin_fileName ----
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))   # production (.py)
except NameError:
    scriptfolder = os.getcwd()                                   # notebook

os.chdir(scriptfolder)

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = 'MT MFSA SQL Ready {}.xlsx'.format(now.strftime('%Y-%m-%d %H.%M.%S'))

#---- Begin_Variable ----
BASE = 'https://fsr.mfsa.mt'
EP_PARENTS = BASE + '/LicenceTypes/getParentLicenceTypes'
EP_SUBS    = BASE + '/LicenceTypes/getLicenceTypesByParentId'
EP_HOLDERS = BASE + '/Licences/getLicenceHoldersByLicenceTypeId'

HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'),
    'Referer': BASE + '/',
    'X-Requested-With': 'XMLHttpRequest',
}

# The app rate-limits hard (HTTP 429) above roughly 3 req/s. Stay serial + polite.
REQ_DELAY = 0.4
MAX_RETRY = 6

# ---- ticket-level constants (hard-coded on purpose: never derive RegCode by
# ---- splitting a dict key -- that is how sibling notebooks ended up emitting a
# ---- different regulator's code entirely).
REGCTRY   = 'MT'
REGCODE   = 'MFSA'
LISTCODE  = '1'
LISTNAME  = 'License Holders'
LISTLANG  = 'EN'
# MFSA is a single authority covering banking + insurance + investment + pensions
# + trustees. List 1 is ONE combined register spanning banks and insurers, so 3.
LISTLABEL = '3'

# Observed licence statuses -> RegulationType.
# Anything not listed is treated as NOT regulated and logged loudly.
STATUS_REGULATED = 'Licence Authorised'

sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
          'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
          'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
          'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
          'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
          'Phone - Mother company': []}

SCHEMA = list(sqldict.keys())
assert len(SCHEMA) == 43, 'schema must be exactly 43 keys, got {}'.format(len(SCHEMA))

#---- Begin_Function ----
def make_session():
    """A session that has visited the home page (the app sets an 'MFSA' cookie
    and an antiforgery cookie; the JSON endpoints 400 without them)."""
    s = requests.Session()
    s.headers.update(HEADERS)
    s.verify = False
    s.get(BASE + '/', timeout=90)
    return s


def get_json(session, url, params=None):
    """GET with backoff. Returns parsed JSON, or raises after MAX_RETRY."""
    last = None
    for attempt in range(MAX_RETRY):
        try:
            r = session.get(url, params=params, timeout=90)
            if r.status_code == 200:
                # soft-404 guard: the app answers errors as HTML, not JSON
                ctype = r.headers.get('content-type', '')
                if 'json' not in ctype.lower():
                    raise ValueError('non-JSON content-type {!r} from {}'.format(ctype, r.url))
                return r.json()
            last = 'HTTP {}'.format(r.status_code)
        except Exception as exc:                      # noqa: BLE001
            last = repr(exc)
        time.sleep(5 * (attempt + 1))                 # 429 needs real cooldown
    raise RuntimeError('giving up on {} params={} : {}'.format(url, params, last))


def clean(value):
    """Collapse whitespace / NBSP, strip. None -> ''."""
    if value is None:
        return ''
    text = str(value).replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', text).strip()


def regulation_type(status):
    """Positive register -> 'Regulated'. Everything else is a non-positive
    status (surrendered / withdrawn / suspended / in liquidation ...)."""
    return 'Regulated' if clean(status) == STATUS_REGULATED else clean(status)


def add_row(**kw):
    """Single entry point. Appends to EVERY key; raises on an unknown key."""
    unknown = set(kw) - set(SCHEMA)
    if unknown:
        raise KeyError('unknown column(s): {}'.format(sorted(unknown)))
    for key in SCHEMA:
        sqldict[key].append(clean(kw.get(key, '')))


def licence_label(lic):
    """Reproduce the label the site renders in the Authorisation column."""
    name = clean(lic.get('licenceTypeName'))
    if lic.get('checkForParentLicence') and not lic.get('moreThanOneParent'):
        parent = clean(lic.get('parentLicenceHolderName'))
        if parent:
            desc = clean(lic.get('parentTypeDescription'))
            return '{} - {} {}'.format(name, desc, parent).strip()
    return name

#---- Begin_MainLoop ----
session = make_session()

# --- 1. discover the Sector list (never hard-code an enumeration) -------------
parents = get_json(session, EP_PARENTS)
if not parents:
    raise RuntimeError('SKIPPED - getParentLicenceTypes returned no sectors')
print('Sectors discovered: {}'.format(len(parents)))

# --- 2. discover the Authorisation list under each Sector --------------------
jobs = []
for parent in parents:
    subs = get_json(session, EP_SUBS,
                    {'parentLicenceTypeId': parent['parentLicenceTypeId']})
    time.sleep(REQ_DELAY)
    if not subs:
        print('   NOTE: sector {!r} has no authorisations'.format(parent['parentLicenceTypeName']))
    for sub in subs:
        jobs.append((clean(parent['parentLicenceTypeName']),
                     sub['licenceTypeId'],
                     clean(sub['licenceTypeName'])))
print('Authorisation types discovered: {}'.format(len(jobs)))

# --- 3. pull the holders of every Authorisation ------------------------------
per_type = {}
per_sector = {}
status_counts = {}
failed_types = []
declared_holder_entries = 0

for idx, (sector, ltid, ltname) in enumerate(jobs, 1):
    try:
        holders = get_json(session, EP_HOLDERS, {'licenceTypeId': ltid})
    except Exception as exc:                          # noqa: BLE001
        failed_types.append((sector, ltid, ltname, repr(exc)))
        print('   FAILED {} / {} (id={}): {}'.format(sector, ltname, ltid, exc))
        time.sleep(REQ_DELAY)
        continue

    declared_holder_entries += len(holders)
    rows_here = 0

    for holder in holders:
        name = clean(holder.get('licenceHolderName'))
        if not name:
            continue
        company_id = clean(holder.get('companyId'))
        person_id  = clean(holder.get('identification'))

        # One row per licence, exactly as the site renders it. NO de-duplication:
        # a holder legitimately shows N lines when it holds N authorisations.
        for lic in holder.get('licences', []) or []:
            status = clean(lic.get('licenceStatus'))
            status_counts[status] = status_counts.get(status, 0) + 1
            add_row(
                ListLabel=LISTLABEL,
                Name=name,
                InternalID_1=company_id,
                InternalID_1_type='MBR Registration Code' if company_id else '',
                InternalID_2=person_id,
                InternalID_2_type='MFSA Authorised Person ID' if person_id else '',
                InternalID_3=ltid,
                InternalID_3_type='MFSA Licence Type ID',
                CoType=sector,
                License_Type=licence_label(lic),
                Cntry='MT',
                RegulationType=regulation_type(status),
                RegCtry=REGCTRY,
                RegCode=REGCODE,
                ListCode=LISTCODE,
                ListLanguage=LISTLANG,
                ListName=LISTNAME,
                ListProcessDate=processdate,
            )
            rows_here += 1

    per_type[(sector, ltname)] = rows_here
    per_sector[sector] = per_sector.get(sector, 0) + rows_here
    time.sleep(REQ_DELAY)
    if idx % 25 == 0:
        print('   ... {}/{} authorisation types done'.format(idx, len(jobs)))

# --- 4. reconciliation -------------------------------------------------------
print('\n================ RECONCILIATION ================')
for sector in sorted(per_sector):
    print('  {:<70} {:>6}'.format(sector[:70], per_sector[sector]))
print('  {:<70} {:>6}'.format('TOTAL licence rows built', sum(per_sector.values())))
print('  {:<70} {:>6}'.format('Holder entries returned by the API', declared_holder_entries))
print('  {:<70} {:>6}'.format('Authorisation types with 0 rows',
                              sum(1 for v in per_type.values() if v == 0)))

print('\nLicence status breakdown (source-declared):')
for status in sorted(status_counts, key=lambda s: -status_counts[s]):
    flag = '' if status == STATUS_REGULATED else '   <-- NOT "Regulated"'
    print('  {:<55} {:>6}{}'.format(status[:55], status_counts[status], flag))

if failed_types:
    print('\n*** {} AUTHORISATION TYPE(S) COULD NOT BE FETCHED - OUTPUT IS SHORT ***'.format(len(failed_types)))
    for sector, ltid, ltname, err in failed_types:
        print('   {} / {} (id={}) : {}'.format(sector, ltname, ltid, err))
else:
    print('\nAll {} authorisation types fetched successfully.'.format(len(jobs)))

lengths = {k: len(v) for k, v in sqldict.items()}
assert len(set(lengths.values())) == 1, 'ragged sqldict: {}'.format(lengths)
print('Every one of the {} columns holds {} values.'.format(len(SCHEMA), sum(lengths.values()) // len(SCHEMA)))

#---- Begin_writer and save df to excel ----
os.chdir(scriptfolder)

df = pd.DataFrame(sqldict)

df = df[df['Name'] != '']

# --- schema gate: exact 43 keys, exact order ---------------------------------
assert list(df.columns) == SCHEMA, 'column order/name drift before to_excel'
assert len(df.columns) == 43, 'expected 43 columns, got {}'.format(len(df.columns))

# --- Excel would coerce all-digit strings ('C 12345' survives, but bare
# --- numbers and leading zeros do not). Force the identifier-ish columns to text.
TEXT_COLS = ['InternalID_1', 'InternalID_2', 'InternalID_3',
             'Zip', 'Phone', 'Fax', 'LEI Code', 'BIC SWIFT Code',
             'Zip - Mother company', 'Phone - Mother company']
for col in TEXT_COLS:
    df[col] = df[col].astype(str).replace('nan', '')

with pd.ExcelWriter(os.path.join(scriptfolder, filename), engine='xlsxwriter') as writer:
    df.to_excel(writer, sheet_name='SQL Ready', index=False)
    book = writer.book
    sheet = writer.sheets['SQL Ready']
    text_fmt = book.add_format({'num_format': '@'})
    for col in TEXT_COLS:
        pos = SCHEMA.index(col)
        sheet.set_column(pos, pos, 18, text_fmt)

print('Saved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))

# --- read back and assert the identifiers round-tripped as text --------------
check = pd.read_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', dtype=str)
assert len(check) == len(df), 'row count changed on round-trip: {} -> {}'.format(len(df), len(check))
assert list(check.columns) == SCHEMA, 'column drift on round-trip'
sample = check.loc[check['InternalID_1'].astype(str).str.strip() != '', 'InternalID_1']
if len(sample):
    val = str(sample.iloc[0]).strip()
    assert 'e+' not in val.lower() and not val.endswith('.0'), \
        'InternalID_1 was coerced to a number: {!r}'.format(val)
    print('Round-trip OK - InternalID_1 sample reads back as {!r}'.format(val))
else:
    print('Round-trip OK - no InternalID_1 values to sample')
