#---- Begin_Librairie ----
# BA KOMVP - Komisija za vrijednosne papire Federacije Bosne i Hercegovine
# (Securities Commission of the Federation of Bosnia and Herzegovina)
# DECD-6830
#
# NOTES ON THE SOURCE (verified live 2026-08-28):
#
#   1. TLS. www.komvp.gov.ba speaks TLS 1.3 ONLY - 1.0/1.1/1.2 all fail. Mac system
#      python (LibreSSL 2.8.3) can never reach it. Guarded at startup below so a TLS
#      failure aborts loudly instead of silently producing an empty workbook.
#
#   2. PAGINATION IS CLIENT-SIDE. The three list pages ship EVERY row inside <tbody>
#      (855 / 16 / 29). DataTables slices them in the browser afterwards. v1 drove a
#      Selenium "next" button over that widget and lost rows (15/16 fmc, 21/29 funds).
#      Plain requests sees the complete table in one GET - no browser needed.
#
#   3. DETAIL PAGES ARE OFTEN EMPTY. Roughly a third of issuer detail pages carry only
#      an ('Address', ',') row - no 'Company Name'. v1 appended a record only when it
#      saw 'Company Name', so those entities vanished (~300 of 855). This version drives
#      rows from the LIST page, where ID and Name are always present, and treats the
#      detail page purely as enrichment.
#
#   4. EMAILS ARE CLOUDFLARE-OBFUSCATED (data-cfemail). Decoded below, scoped to the
#      value cell - the page footer holds the regulator's own info@komvp.gov.ba and a
#      page-wide lookup would stamp it onto every record.

import os
import ssl
import time
import datetime

import requests
import pandas as pd
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter

requests.packages.urllib3.disable_warnings()

# Connect/read timeout. Deliberately short: a single stalled socket must not be able
# to swallow a 900-page run. Observed latency to this host is ~0.2 s per page, so 20 s
# is ~100x headroom and still fails fast.
TIMEOUT = (10, 20)

#---- Begin_TLS guard ----

if ssl.OPENSSL_VERSION_INFO < (1, 1, 1):
    raise SystemExit(
        '[FATAL] This interpreter links {}, which has no TLS 1.3.\n'
        '        www.komvp.gov.ba accepts TLS 1.3 only, so it can never be reached\n'
        '        from here. Re-run under a python built against OpenSSL >= 1.1.1.'
        .format(ssl.OPENSSL_VERSION))

#---- Begin_fileName ----

regulatorName = 'BA KOMVP'

print('Running {} Web Scraping Tool v.2.0'.format(regulatorName))

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')

filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(':', '.')[:-7])

try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))  ## production environment (.py)
except NameError:
    scriptfolder = os.getcwd()  ## notebook environment

os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder')
if not os.path.exists(tempfolder):
    os.mkdir(tempfolder)

#---- Begin_Variable ----

BASE = 'https://www.komvp.gov.ba'

# List Code / List Name / URL slug, exactly as per DECD-6830.
REGDICT = {
    '1': {'name': 'List of Issuers',                    'slug': 'issuers', 'expected': 855},
    '2': {'name': 'List of Fund Management Companies',  'slug': 'fmc',     'expected': 16},
    '3': {'name': 'List of Investment Funds',           'slug': 'funds',   'expected': 29},
}

# Issuers, fund managers and investment funds are securities-market entities:
# neither banks (1) nor insurers (2), so "everything else".
LIST_LABEL = 4

HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

SCHEMA_KEYS = ['bvdid', 'priority', 'ListLabel', 'Typology', 'EntryType', 'Name', 'InternalID_1', 'InternalID_1_type', 'InternalID_2',
               'InternalID_2_type', 'InternalID_3', 'InternalID_3_type', 'CoType', 'License_Type', 'Address_1', 'Address_2', 'City',
               'Zip', 'Cntry', 'Phone', 'Fax', 'Website', 'Email', 'RegulationType', 'RegulationTypeCode', 'RegulationDate', 'CancellationDate',
               'RegCtry', 'RegCode', 'ListCode', 'ListLanguage', 'ListValidityDate', 'ListName', 'ListProcessDate', 'LEI Code', 'BIC SWIFT Code', 'Name - Mother Company',
               'Address_1 - Mother company', 'Address_2 -  Mother company', 'City - Mother company', 'Zip - Mother company', 'Cntry - Mother company',
               'Phone - Mother company']

sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}

# Columns that must stay TEXT in Excel: leading zeros and long digit strings
# otherwise become 4.2e+12 / lose their zeros.
TEXT_COLUMNS = ['InternalID_1', 'InternalID_2', 'InternalID_3', 'Phone', 'Fax', 'Zip']

#---- Begin_Fonction ----


def cfdecode(hexstring):
    """Decode a Cloudflare data-cfemail blob. First byte is the XOR key."""
    key = int(hexstring[:2], 16)
    return ''.join(chr(int(hexstring[i:i + 2], 16) ^ key)
                   for i in range(2, len(hexstring), 2))


def cell_email(td):
    """Email out of a value cell, de-obfuscating Cloudflare's protection if present."""
    node = td.find(attrs={'data-cfemail': True})
    if node:
        try:
            return cfdecode(node['data-cfemail'])
        except (ValueError, KeyError):
            return ''
    text = td.get_text(' ', strip=True)
    return '' if 'email' in text.lower() and 'protected' in text.lower() else text


def city_from_address(address):
    """Addresses read 'Danijela Ozme 1, Sarajevo' - the town is the last segment."""
    parts = [p.strip() for p in address.split(',') if p.strip()]
    return parts[-1] if len(parts) > 1 else ''


def detail_fields(soup):
    """Label -> plain-string value for a detail page, keyed on the EXACT first-cell text.

    Exact matching matters: v1 used `'License Issuance' in tr.text`, which also
    matched 'Date License Issuance', and `'Address' in ...` collided with the
    mother-company block.

    Values are strings, never Tags: the parse tree is dropped as soon as this returns,
    which is what lets the caller hold all 855 issuers' fields at once.
    """
    fields = {}
    tbody = soup.find('tbody')
    if not tbody:
        return fields
    for tr in tbody.find_all('tr'):
        tds = tr.find_all('td')
        if len(tds) < 2:
            continue
        label = tds[0].get_text(' ', strip=True)
        if label in fields:
            continue
        # The email is resolved here, while its own <td> is in hand. Scoping the
        # data-cfemail lookup to this cell is what keeps the footer's own
        # info@komvp.gov.ba off the rows that carry no entity email.
        fields[label] = (cell_email(tds[-1]) if label == 'E-mail'
                         else tds[-1].get_text(' ', strip=True))
    return fields


def make_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    s.verify = False
    # Small pool, no urllib3-level retry: retries are handled in get() so that a
    # stalled keep-alive connection is answered by discarding the whole pool.
    adapter = HTTPAdapter(pool_connections=4, pool_maxsize=4, max_retries=0)
    s.mount('https://', adapter)
    s.mount('http://', adapter)
    return s


session = make_session()


def get(url, attempts=3):
    """GET with retries. Returns None only after every attempt failed.

    On any transport failure the session is rebuilt. This run goes through a local
    corporate proxy (127.0.0.1:3636) and a keep-alive connection there can go
    half-open: the socket stays ESTABLISHED, the read never returns, and every
    subsequent request reusing that pooled connection inherits the stall. Throwing
    the connection pool away is what actually clears it - retrying on the same
    Session does not.
    """
    global session
    for i in range(attempts):
        try:
            r = session.get(url, timeout=TIMEOUT)
            if r.status_code == 200:
                r.encoding = 'utf-8'
                return r.text
            if r.status_code == 404:
                return None
        except requests.RequestException:
            session.close()
            session = make_session()
        time.sleep(1 + i)
    return None


def add_row(**kw):
    """Append one complete record - every key written on every row, no padding pass."""
    for key in SCHEMA_KEYS:
        sqldict[key].append(kw.get(key, ''))


#---- Begin_Main ----

reconciliation = {}

for listcode in sorted(REGDICT):
    meta = REGDICT[listcode]
    listurl = '{}/en/market-participants/{}'.format(BASE, meta['slug'])
    print('\n[INFO] List {} - {}'.format(listcode, meta['name']), flush=True)

    html = get(listurl)
    if html is None:
        raise SystemExit('[FATAL] could not load list page {}'.format(listurl))

    soup = BeautifulSoup(html, 'html.parser')
    tbody = soup.find('tbody')
    if tbody is None:
        raise SystemExit('[FATAL] no <tbody> on {} - the page layout changed'.format(listurl))

    # The list page is the source of truth for how many entities exist and what
    # they are called. Every row here becomes exactly one output row.
    entries = []
    for tr in tbody.find_all('tr'):
        tds = tr.find_all('td')
        if len(tds) < 2:
            continue
        anchor = tds[-1].find('a')
        entries.append({
            'id': tds[0].get_text(' ', strip=True),
            'name': tds[1].get_text(' ', strip=True),
            'href': anchor['href'] if anchor and anchor.has_attr('href') else None,
        })

    print('[INFO]   {} rows on the list page (expected {})'.format(len(entries), meta['expected']), flush=True)
    if len(entries) != meta['expected']:
        print('[WARN]   row count moved since 2026-08-28 - confirm against the site '
              'before shipping this run')

    # ---- phase 1: fetch every detail page, then sweep the stragglers once more ----
    # A failed fetch is almost always the half-open proxy socket described in the header,
    # not a missing page: the first pass of the 2026-08-28 run lost 12 of 855 issuers'
    # details this way and every one of them came back on a retry. Sweeping at the end
    # (rather than retrying in place) also keeps one bad stretch of network from being
    # charged against the rows that happen to sit in it.
    detail = {}
    pending = [e for e in entries if e['href']]
    total = len(pending)
    t0 = time.time()
    for sweep in (1, 2):
        if sweep == 2:
            if not pending:
                break
            print('[INFO]   re-trying {} detail page(s) that failed'
                  .format(len(pending)), flush=True)
        stillpending = []
        for n, entry in enumerate(pending, 1):
            dhtml = get(BASE + entry['href'])
            if dhtml:
                detail[entry['href']] = detail_fields(BeautifulSoup(dhtml, 'html.parser'))
            else:
                stillpending.append(entry)
            if sweep == 1 and (n % 50 == 0 or n == total):
                print('[INFO]   {}/{} detail pages read ({:.0f}s elapsed)'
                      .format(n, total, time.time() - t0), flush=True)
            time.sleep(0.15)
        pending = stillpending
    failed = len(pending)

    # ---- phase 2: one row per list row, in list order, detail data overlaid ----
    kept = 0
    no_detail = 0
    for entry in entries:
        fields = detail.get(entry['href'], {}) if entry['href'] else {}
        if not fields.get('Company Name'):
            no_detail += 1

        def val(label):
            return fields.get(label, '')

        # Detail name wins when present, otherwise the list name stands.
        name = val('Company Name') or entry['name']

        address = val('Address')
        # Empty detail pages render Address as a bare ',' - not an address.
        if address.strip(' ,') == '':
            address = ''

        email = val('E-mail')

        cid = val('Company Identification Number')
        court = val('Court Registry File Number')

        add_row(
            ListLabel=LIST_LABEL,
            Name=name,
            InternalID_1=entry['id'],
            InternalID_1_type='ID' if entry['id'] else '',
            InternalID_2=cid,
            InternalID_2_type='Company Identification Number' if cid else '',
            InternalID_3=court,
            InternalID_3_type='Court Registry File Number' if court else '',
            CoType=val('Company type') or val('Fund Type'),
            License_Type=val('Investment method'),
            Address_1=address,
            City=city_from_address(address),
            Cntry='BA',
            Phone=val('Phone'),
            Fax=val('Fax'),
            Website=val('Web page'),
            Email=email,
            RegulationType='Regulated',
            RegulationTypeCode=val('License Issuance'),
            RegulationDate=val('Date License Issuance'),
            CancellationDate=val('License withdrawal date'),
            RegCtry='BA',
            RegCode='KOMVP',
            ListCode=listcode,
            ListLanguage='EN',
            ListName=meta['name'],
            ListProcessDate=processdate,
            **{'Name - Mother Company': val('Društvo koje upravlja Fondom')}
        )
        kept += 1

    print('[INFO]   kept {} rows ({} had no detail data - name taken from the list page, '
          '{} detail fetches failed)'.format(kept, no_detail, failed), flush=True)
    if failed:
        print('[WARN]   {} detail page(s) could not be fetched even on the retry sweep - '
              'those rows carry the list-page name only'.format(failed), flush=True)
    reconciliation[meta['slug']] = (meta['expected'], len(entries), kept)

#---- Begin_reconciliation ----

print('\n[INFO] ---- reconciliation (expected / on site / kept) ----')
mismatch = False
tot_e = tot_s = tot_k = 0
for slug, (exp, seen, kept) in reconciliation.items():
    print('   {:10s} {:5d} / {:5d} / {:5d}'.format(slug, exp, seen, kept))
    tot_e += exp
    tot_s += seen
    tot_k += kept
    if seen != kept:
        mismatch = True
print('   {:10s} {:5d} / {:5d} / {:5d}'.format('TOTAL', tot_e, tot_s, tot_k))

if mismatch:
    raise SystemExit('[FATAL] rows kept do not match rows seen on the site')

#---- Begin_writer and save df to excel ----

os.chdir(scriptfolder)

df = pd.DataFrame(sqldict)

assert list(df.columns) == SCHEMA_KEYS, 'output columns drifted from the 42-key schema'

df = df[df['Name'] != '']

# Guard against the failure mode where the row count reconciles but Name holds
# junk lifted from the wrong column.
bad_names = df[df['Name'].str.strip().isin(['', 'Yes', 'No', 'Details', 'Details add'])]
assert bad_names.empty, 'Name column holds placeholder text on {} rows'.format(len(bad_names))
assert not df['Name'].str.contains(r'\[email', regex=True).any(), 'obfuscated email leaked into Name'

outpath = os.path.join(scriptfolder, filename)

for col in TEXT_COLUMNS:
    df[col] = df[col].astype(str).replace('nan', '')

with pd.ExcelWriter(outpath, engine='openpyxl') as writer:
    df.to_excel(writer, sheet_name='SQL Ready', index=False)
    sheet = writer.sheets['SQL Ready']
    for col in TEXT_COLUMNS:
        letter = sheet.cell(row=1, column=list(df.columns).index(col) + 1).column_letter
        for cell in sheet[letter][1:]:
            cell.number_format = '@'

print('\nSaved {} rows to {}'.format(len(df), outpath))

#---- Begin_readback assertion ----

check = pd.read_excel(outpath, sheet_name='SQL Ready', dtype=str)
assert len(check) == len(df), 'row count changed on the round trip through Excel'
for col in TEXT_COLUMNS:
    coerced = check[col].dropna()
    coerced = coerced[coerced.str.contains(r'e\+', case=False, na=False)]
    assert coerced.empty, '{} was coerced to scientific notation by Excel'.format(col)
print('[INFO] read-back OK - {} rows, ID/Phone columns still text'.format(len(check)))
