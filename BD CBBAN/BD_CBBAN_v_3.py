#---- Begin_Librairie ----
# BD CBBAN - Bangladesh Bank (central bank of Bangladesh)
# DECD-6975
#
# NOTES ON THE SOURCE (verified live 2026-09-03):
#
#   1. A REAL BROWSER IS MANDATORY. www.bb.org.bd sits behind an F5 / TrustedShield
#      "TSPD" JavaScript bot challenge. Plain `requests` gets HTTP **200** with a
#      ~43 KB body that contains only an obfuscated JS challenge (window["bobcmn"],
#      TSPD_101 cookies) and ZERO <table> elements. A status-code check would call
#      that a success, which is exactly why the acceptance test below is a real
#      parse, not a 200-check. DrissionPage/Chromium solves the challenge and the
#      table appears.
#
#   2. `--headless=new` passed via set_argument() breaks the DevTools websocket
#      handshake on this box (WebSocketBadStatusException: Handshake status 404).
#      ChromiumOptions.headless(True) is the form that works - measured, not guessed.
#      Chrome is isolated with auto_port() and NEVER with set_user_data_path()
#      (auto_port already allocates a throwaway profile; setting both kills startup).
#
#   3. THE TABLE HAS NO <thead>. The header row ('Organisation' | 'Web Link') is the
#      first <tr> inside <tbody>. v1/v2 both did soup.find('table').find('tbody') on
#      a page that had no table at all (they used the retired /links/index.php URL)
#      and died with AttributeError: 'NoneType' object has no attribute 'find'.
#
#   4. THE SOURCE ONLY PUBLISHES TWO COLUMNS - organisation name and a web link.
#      There is no address, phone, licence number or registration date anywhere on
#      these pages. Most of the 43-key schema is therefore legitimately empty; that
#      is a property of the source, not a scrape failure.
#
#   5. Columns are resolved BY HEADER LABEL, never by position, so a column swap
#      upstream cannot silently put URLs into Name.

import os
import re
import time
import datetime

import pandas as pd
from bs4 import BeautifulSoup
from DrissionPage import ChromiumPage, ChromiumOptions

#---- Begin_fileName ----

regulatorName = 'BD CBBAN'

print('Running {} Web Scraping Tool v.3.0'.format(regulatorName), flush=True)

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')

filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(':', '.')[:-7])

try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))   ## production environment (.py)
except NameError:
    scriptfolder = os.getcwd()                                  ## notebook environment

os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder')  # failing HTML is dumped here
if not os.path.exists(tempfolder):
    os.mkdir(tempfolder)

#---- Begin_Variable ----

BASE = 'https://www.bb.org.bd'

# ListNr / ListName / URL exactly as per DECD-6975.
#
# The ticket Comments say "click on the corresponding list name" from the links
# index. Confirmed live: the index page (/en/index.php/links/index) links each of
# those names straight to the /links/links/<id> URL already given in the ticket,
# so the ticket URL IS the destination page - no click-through is needed.
#   links/9 -> "Banks"                       links/2 -> "Finance Companies"
#   links/3 -> "Micro Finance Institutions"  links/4 -> "Others"
#
# ListLabel: 1 = bank, 2 = insurance, 3 = both, 4 = everything else.
#   1 Banks                      -> 1  (scheduled banks)
#   2 Financial Institutions     -> 4  (Bangladesh's "Finance Companies" are
#                                       non-bank financial institutions under the
#                                       Finance Company Act; not banks, not insurers.
#                                       Same treatment as NG CBNI / PK SBP Finance
#                                       Companies.)
#   3 Micro Finance Institutions -> 4  (NGO-MFIs such as ASA / BRAC - not licensed
#                                       as banks)
#   4 Others                     -> 4
REGDICT = {
    '1': {'ListName': 'Banks',
          'URL': BASE + '/en/index.php/links/links/9',
          'ListLabel': 1,
          'Comments': 'Click on the corresponding list name "Banks" and collect all the entities from the table'},
    '2': {'ListName': 'Financial Institutions',
          'URL': BASE + '/en/index.php/links/links/2',
          'ListLabel': 4,
          'Comments': 'Click on the corresponding list name "Finance Companies" and collect all the entities from the table'},
    '3': {'ListName': 'Micro Finance Institutions',
          'URL': BASE + '/en/index.php/links/links/3',
          'ListLabel': 4,
          'Comments': 'Click on the corresponding list name "Micro Finance Institutions" and collect all the entities from the table'},
    '4': {'ListName': 'Others',
          'URL': BASE + '/en/index.php/links/links/4',
          'ListLabel': 4,
          'Comments': 'Click on the corresponding list name "Others" and collect all the entities from the table'},
}

SCHEMA_KEYS = ['bvdid', 'priority', 'ListLabel', 'Typology', 'EntryType', 'Name', 'InternalID_1', 'InternalID_1_type', 'InternalID_2',
               'InternalID_2_type', 'InternalID_3', 'InternalID_3_type', 'CoType', 'License_Type', 'Address_1', 'Address_2', 'City',
               'Zip', 'Cntry', 'Phone', 'Fax', 'Website', 'Email', 'RegulationType', 'RegulationTypeCode', 'RegulationDate', 'CancellationDate',
               'RegCtry', 'RegCode', 'ListCode', 'ListLanguage', 'ListValidityDate', 'ListName', 'ListProcessDate', 'LEI Code', 'BIC SWIFT Code', 'Name - Mother Company',
               'Address_1 - Mother company', 'Address_2 -  Mother company', 'City - Mother company', 'Zip - Mother company', 'Cntry - Mother company',
               'Phone - Mother company']

sqldict={'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
          'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
          'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
          'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
          'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
          'Phone - Mother company': []}

assert len(SCHEMA_KEYS) == 43, 'schema must hold exactly 43 keys'
assert list(sqldict.keys()) == SCHEMA_KEYS, 'sqldict drifted from the frozen schema'

# Columns Excel would otherwise turn into 4.2e+10 or strip leading zeros from.
TEXT_COLUMNS = ['InternalID_1', 'InternalID_2', 'InternalID_3', 'Phone', 'Fax', 'Zip',
                'Zip - Mother company', 'Phone - Mother company']

# Header labels, normalised. Position is never trusted.
NAME_LABELS = ('organisation', 'organization', 'name', 'institution')
LINK_LABELS = ('web link', 'weblink', 'website', 'web site', 'url', 'link')

PAGE_WAIT = 25      # seconds allowed for the TSPD challenge to clear per attempt
ATTEMPTS = 4        # navigations before a list is declared unreachable

#---- Begin_Fonction ----


def norm(text):
    """Lower-cased, whitespace-collapsed, nbsp-free label text."""
    return re.sub(r'\s+', ' ', (text or '').replace('\xa0', ' ')).strip().lower()


def ascii_safe(text):
    """ASCII-only rendering for the console.

    The Windows control server runs a cp1252 console; printing scraped text
    straight from the site raises UnicodeEncodeError in encodings\\cp1252.py.
    Nothing read off the website reaches print() without passing through here.
    """
    return (text or '').encode('ascii', 'replace').decode('ascii')


def split_annotation(name):
    """Split a trailing SQUARE-bracket status annotation off an organisation name.

    Bangladesh Bank annotates a not-yet-operating entity inside the name cell:
        'Nagad Digital Bank PLC. [Yet not granted permission for Commercial Operation]'
    Left in place, that editorial note becomes part of the loaded entity name.

    Only a TRAILING [...] is split, and only square brackets. Round parentheses
    are left alone on purpose - on these four pages every '(...)' is part of the
    real name (abbreviations such as '(BIFC)', '(PKSF)', or the former name in
    'BASIC Bank PLC. (Bangladesh Small Industries and Commerce Bank PLC.)').
    Audited live 2026-09-03: 1 square-bracket annotation, 10 legitimate '(...)'.

    Returns (clean_name, annotation).
    """
    match = re.search(r'\s*\[([^\]]*)\]\s*$', name)
    if not match:
        return name, ''
    clean = name[:match.start()].strip()
    # Never let the rule empty out a name.
    if not clean:
        return name, ''
    return clean, match.group(1).strip()


def parse_rows(html):
    """THE single acceptance test. Returns [(name, website, note), ...] or None.

    None means 'this is not the page we asked for' - a TSPD challenge, a proxy
    interstitial, or a layout change. The fetch wait-loop and the post-fetch
    assertion both call THIS function, so nothing that would fail the assert can
    be handed back by the loop as a success.
    """
    if not html:
        return None
    soup = BeautifulSoup(html, 'html.parser')

    for table in soup.find_all('table'):
        rows = table.find_all('tr')
        if len(rows) < 2:
            continue

        # Header row: first <tr>, whether or not it lives in a <thead>.
        header = [norm(c.get_text(' ', strip=True)) for c in rows[0].find_all(['th', 'td'])]
        namecol = linkcol = None
        for i, label in enumerate(header):
            if namecol is None and label in NAME_LABELS:
                namecol = i
            if linkcol is None and label in LINK_LABELS:
                linkcol = i
        if namecol is None:
            continue  # not the entity table

        out = []
        for tr in rows[1:]:
            tds = tr.find_all('td')
            if len(tds) <= namecol:
                continue
            name = re.sub(r'\s+', ' ', tds[namecol].get_text(' ', strip=True).replace('\xa0', ' ')).strip()
            if not name:
                continue

            website = ''
            if linkcol is not None and len(tds) > linkcol:
                cell = tds[linkcol]
                anchor = cell.find('a', href=True)
                if anchor:
                    href = anchor['href'].strip()
                    # Ignore the site's own javascript:/# placeholders.
                    if href.lower().startswith(('http://', 'https://')):
                        website = href
                if not website:
                    text = cell.get_text(' ', strip=True)
                    if text.lower().startswith(('http://', 'https://', 'www.')):
                        website = text

            name, note = split_annotation(name)
            out.append((name, website, note))

        if out:
            return out

    return None


def add_row(**kw):
    """Append one complete record - every one of the 43 keys, every time.

    No padding pass, so a ragged-array ValueError at DataFrame time is impossible.
    """
    for key in SCHEMA_KEYS:
        sqldict[key].append(kw.get(key, ''))


def start_browser():
    co = ChromiumOptions().auto_port()   # isolated port + throwaway profile
    co.headless(True)                    # NOT set_argument('--headless=new') - see note 2
    co.set_argument('--disable-extensions')
    co.set_argument('--no-sandbox')
    return ChromiumPage(co)


def fetch_rows(page, url, listcode):
    """Navigate until parse_rows() succeeds. Dumps the last bad HTML on failure."""
    lasthtml = ''
    for attempt in range(1, ATTEMPTS + 1):
        try:
            page.get(url)
        except Exception as exc:
            print('[WARN]   navigation error on attempt {}: {}'
                  .format(attempt, ascii_safe(type(exc).__name__)), flush=True)
            time.sleep(3)
            continue

        # Poll while the TSPD challenge script runs and rewrites the document.
        waited = 0
        while waited < PAGE_WAIT:
            time.sleep(2)
            waited += 2
            try:
                lasthtml = page.html
            except Exception:
                continue
            rows = parse_rows(lasthtml)
            if rows:
                return rows
        print('[WARN]   attempt {}/{} produced no parsable table ({} bytes) - re-navigating'
              .format(attempt, ATTEMPTS, len(lasthtml)), flush=True)

    dump = os.path.join(tempfolder, 'FAILED list{} {}.html'
                        .format(listcode, now.strftime('%Y%m%d-%H%M%S')))
    with open(dump, 'w', encoding='utf-8') as fh:
        fh.write(lasthtml or '')
    print('[FAIL]   unusable HTML written to {}'.format(dump), flush=True)
    return None


#---- Begin_Main ----

page = start_browser()
reconciliation = {}
failed_lists = []

try:
    for listcode in sorted(REGDICT):
        meta = REGDICT[listcode]
        print('\n[INFO] List {} - {}'.format(listcode, meta['ListName']), flush=True)

        rows = fetch_rows(page, meta['URL'], listcode)
        if rows is None:
            print('[FAIL]   list {} SKIPPED - no table could be read'.format(listcode), flush=True)
            failed_lists.append(listcode)
            reconciliation[listcode] = (0, 0)
            continue

        print('[INFO]   {} data rows on the source page'.format(len(rows)), flush=True)

        # One output row per source row, in source order. No de-duplication:
        # if the site shows a name twice, the load must show it twice.
        kept = 0
        annotated = 0
        for name, website, note in rows:
            if note:
                annotated += 1
            add_row(
                ListLabel=meta['ListLabel'],
                Typology=meta['ListName'],
                Name=name,
                # A status note the site prints inside the name cell. Kept out of
                # Name, kept in the file - see split_annotation().
                License_Type=note,
                Website=website,
                Cntry='BD',
                RegulationType='Regulated',
                RegCtry='BD',
                RegCode='CBBAN',
                ListCode=listcode,
                ListLanguage='EN',
                ListName=meta['ListName'],
                ListProcessDate=processdate,
            )
            kept += 1

        withsite = sum(1 for _, w, _n in rows if w)
        print('[INFO]   kept {} rows ({} carry a web link, {} carry a status annotation)'
              .format(kept, withsite, annotated), flush=True)
        if annotated:
            print('[WARN]   {} name(s) in this list carried a bracketed status note; it was '
                  'moved to License_Type and RegulationType still says Regulated - '
                  'CONFIRM this is the wanted treatment'.format(annotated), flush=True)
        reconciliation[listcode] = (len(rows), kept)
finally:
    try:
        page.quit()
    except Exception:
        pass

#---- Begin_reconciliation ----

print('\n[INFO] ---- reconciliation (rows on site / rows kept) ----', flush=True)
tot_s = tot_k = 0
mismatch = False
for listcode in sorted(reconciliation):
    seen, kept = reconciliation[listcode]
    print('   list {}  {:>18s}  {:4d} / {:4d}'
          .format(listcode, REGDICT[listcode]['ListName'][:18], seen, kept), flush=True)
    tot_s += seen
    tot_k += kept
    if seen != kept:
        mismatch = True
print('   {:>26s}  {:4d} / {:4d}'.format('TOTAL', tot_s, tot_k), flush=True)

if mismatch:
    raise SystemExit('[FATAL] rows kept do not match rows seen on the site')
if failed_lists:
    raise SystemExit('[FATAL] list(s) {} could not be scraped - refusing to write a '
                     'partial workbook that would de-list every entity in them'
                     .format(', '.join(failed_lists)))
if tot_k == 0:
    raise SystemExit('[FATAL] nothing was scraped')

#---- Begin_writer and save df to excel ----

os.chdir(scriptfolder)

df = pd.DataFrame(sqldict)

assert list(df.columns) == SCHEMA_KEYS, 'output columns drifted from the 43-key schema'

df = df[df['Name'] != '']

# A file can reconcile N/N rows while Name holds junk lifted from the wrong
# column. Assert on Name CONTENT, separately from the row count.
bad = df[df['Name'].str.strip().isin(['', 'Yes', 'No', 'Organisation', 'Web Link', 'Name'])]
assert bad.empty, 'Name column holds header/placeholder text on {} rows'.format(len(bad))
assert not df['Name'].str.lower().str.startswith(('http://', 'https://', 'www.')).any(), \
    'a URL leaked into Name - the column mapping is wrong'
assert df['Name'].str.len().between(2, 200).all(), 'implausible Name length'

for col in TEXT_COLUMNS:
    df[col] = df[col].astype(str).replace('nan', '')

outpath = os.path.join(scriptfolder, filename)

with pd.ExcelWriter(outpath, engine='openpyxl') as writer:
    df.to_excel(writer, sheet_name='SQL Ready', index=False)
    sheet = writer.sheets['SQL Ready']
    for col in TEXT_COLUMNS:
        letter = sheet.cell(row=1, column=list(df.columns).index(col) + 1).column_letter
        for cell in sheet[letter][1:]:
            cell.number_format = '@'

print('\nSaved {} rows to {}'.format(len(df), outpath), flush=True)

#---- Begin_readback assertion ----

check = pd.read_excel(outpath, sheet_name='SQL Ready', dtype=str)

assert list(check.columns) == SCHEMA_KEYS, 'saved sheet columns drifted from the schema'
assert len(check) == len(df), 'row count changed on the round trip through Excel'

for col in TEXT_COLUMNS:
    vals = check[col].dropna()
    assert vals[vals.str.contains(r'e\+', case=False, na=False)].empty, \
        '{} was coerced to scientific notation by Excel'.format(col)

# Encoding red flags - mojibake from a mis-decoded response.
blob = ' '.join(check['Name'].fillna('').tolist() + check['Website'].fillna('').tolist())
for flag in ('Ã©', 'â', 'Â '):
    assert flag not in blob, 'mojibake detected in the saved workbook'
assert not re.search(r'\?{3,}', blob), 'runs of ??? in the saved workbook'

print('[INFO] read-back OK - {} rows, {} columns, ID/Phone columns still text'
      .format(len(check), len(check.columns)), flush=True)

for listcode in sorted(REGDICT):
    n = int((check['ListCode'] == listcode).sum())
    print('[INFO]   ListCode {} -> {} rows'.format(listcode, n), flush=True)

for col in ('Name', 'Website', 'City', 'Address_1', 'Phone', 'InternalID_1'):
    filled = int(check[col].fillna('').astype(str).str.strip().ne('').sum())
    print('[INFO]   {:14s} non-empty {:4d}/{:4d} ({:.1f}%)'
          .format(col, filled, len(check), 100.0 * filled / max(len(check), 1)), flush=True)
