# -*- coding: utf-8 -*-
"""
AI ECCBAI - Eastern Caribbean Central Bank (ECCB)
Jira: DECD-6832

List 1 - "Licensed Finance Companies"
  Index : https://www.eccb-centralbank.org/register-of-licensed-financial-institutions
  Source: PDF "Register of Financial Institutions Licensed Under the Banking Act"
          (link resolved every run from the anchor's visible label - NEVER hard-coded)

v2 (multi-regulator) - the ECCB is one supranational central bank shared by EIGHT member
territories, each of which carries its own regulator code in our reference data:

    AI -> ECCBAI    AG -> ECCBAG    DM -> ECCBDM    GD -> ECCBGD
    KN -> ECCBKN    LC -> ECCBLC    MS -> ECCBMS    VC -> ECCBVC

The register is parsed ONCE and then emitted once per member regulator, exactly as
CF CEMACCF does for the six CEMAC/COBAC members. `Cntry` still carries the territory the
institution is licensed in, so every regulator copy holds the full eight-territory list.
v1 emitted a single copy tagged AI/ECCBAI.
"""

#---- Begin_Librairie ----
import os
import re
import io
import datetime
import warnings

import requests
import pandas as pd
import pdfplumber
from bs4 import BeautifulSoup

requests.packages.urllib3.disable_warnings()
warnings.filterwarnings('ignore')

# ------ At first we will define the workspace path -----
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))  # production environment (.py)
except NameError:
    scriptfolder = os.getcwd()  # notebook environment

os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder')
os.makedirs(tempfolder, exist_ok=True)

#---- Begin_fileName ----
regulatorName = 'AI ECCBAI'

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')

# One stamp for the whole run, so all eight member workbooks carry the SAME timestamp and
# are obviously one delivery: "AI ECCBAI SQL Ready 2026-08-25 14.38.11.xlsx",
#                             "KN ECCBKN SQL Ready 2026-08-25 14.38.11.xlsx", ...
stamp = str(now).replace(':', '.')[:-7]
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, stamp)

print('Regulator : {}'.format(regulatorName))
print('Output dir: {}'.format(scriptfolder))

#---- Begin_Variable ----
REGCTRY = 'AI'
REGCODE = 'ECCBAI'
LISTLANGUAGE = 'EN'

INDEX_URL = 'https://www.eccb-centralbank.org/register-of-licensed-financial-institutions'

# The anchor is matched on its VISIBLE LABEL, not its href. The regulator re-uploads the
# register under a new timestamped filename each revision (the URL in the Jira ticket,
# dated 2024-07-30, is already stale), so any hard-coded href would rot.
ANCHOR_KEYWORD = 'register of financial institutions licensed under the banking act'

HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

# ListLabel: 1 = bank, 2 = insurance, 3 = bank & insurance, 4 = everything else.
# This register is issued under the Banking Act 2015 and contains banks, non-bank credit
# institutions and bank holding companies -> banking sector -> ListLabel 1.
LISTS = {
    1: {'ListName': 'Licensed Finance Companies',
        'ListLabel': 1,
        'url': INDEX_URL},
}

# Section headers in the PDF are discovered from the document itself (see
# `is_country_header`). This table only NORMALISES a discovered heading to an ISO code -
# it is not an enumeration of what to scrape. An unrecognised heading raises loudly.
COUNTRY_TOKEN_TO_ISO = [
    ('ANGUILLA', 'AI'),
    ('ANTIGUA', 'AG'),
    ('DOMINICA', 'DM'),
    ('GRENADA', 'GD'),
    ('MONTSERRAT', 'MS'),
    ('NEVIS', 'KN'),
    ('KITTS', 'KN'),
    ('LUCIA', 'LC'),
    ('VINCENT', 'VC'),
]

# ---- the eight ECCB member regulators -----------------------------------------------
# One central bank, eight member territories, eight regulator codes. The base parse tags
# rows with REGCTRY/REGCODE (AI/ECCBAI); these are the other seven, applied at write time.
OTHER_REGULATORS = {
    'AG': 'ECCBAG',   # Antigua and Barbuda
    'DM': 'ECCBDM',   # Commonwealth of Dominica
    'GD': 'ECCBGD',   # Grenada
    'KN': 'ECCBKN',   # Saint Christopher (St Kitts) and Nevis
    'LC': 'ECCBLC',   # Saint Lucia
    'MS': 'ECCBMS',   # Montserrat
    'VC': 'ECCBVC',   # Saint Vincent and the Grenadines
}

# Guard: the regulator list and the country sections found in the PDF must describe the
# same eight territories. If the ECCB ever admits/drops a member, this fires instead of
# silently shipping a lopsided file.
assert set(OTHER_REGULATORS) | {REGCTRY} == set(iso for _tok, iso in COUNTRY_TOKEN_TO_ISO), (
    'ECCB member regulators and the PDF country map disagree: {} vs {}'.format(
        sorted(set(OTHER_REGULATORS) | {REGCTRY}),
        sorted(set(iso for _tok, iso in COUNTRY_TOKEN_TO_ISO))))
for _ctry, _code in list(OTHER_REGULATORS.items()) + [(REGCTRY, REGCODE)]:
    assert _code == 'ECCB' + _ctry, 'RegCode {} does not follow ECCB<CC> for {}'.format(_code, _ctry)

# All eight, base regulator included - drives both the replication and the per-member files.
ALL_REGULATORS = dict(OTHER_REGULATORS)
ALL_REGULATORS[REGCTRY] = REGCODE

# Each member regulator receives the FULL register, not only its own territory's rows -
# the same decision taken in CF CEMACCF_v2 (the country-filtered variant is present there
# but commented out). Flip to True to deliver only each regulator's own territory.
OWN_COUNTRY_ONLY = False

# ---- output shape -------------------------------------------------------------------
# WRITE_PER_REGULATOR : one workbook per ECCB member, named "<CC> ECCB<CC> SQL Ready
#                       <stamp>.xlsx", all eight sharing the run's single timestamp.
#                       This is the delivery format.
# WRITE_COMBINED      : additionally write every member into ONE workbook, named
#                       "AI ECCBAI ALL SQL Ready <stamp>.xlsx". Off by default - it holds
#                       exactly the same data as the eight files concatenated, and the
#                       "ALL" infix keeps it from colliding with the Anguilla workbook.
WRITE_PER_REGULATOR = True
WRITE_COMBINED = False

TABLE_SETTINGS = {'vertical_strategy': 'lines', 'horizontal_strategy': 'lines'}

# Columns that Excel would otherwise coerce from text to a number / float.
TEXT_COLUMNS = ['InternalID_1', 'InternalID_2', 'InternalID_3', 'Zip', 'Phone', 'Fax',
                'Zip - Mother company', 'Phone - Mother company', 'bvdid']

sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}

assert len(sqldict) == 43, 'sqldict must have exactly 43 keys, got {}'.format(len(sqldict))


#---- Begin_Function ----
def add_row(**kwargs):
    """Append exactly one value to EVERY key of sqldict. Unknown keys raise."""
    unknown = set(kwargs) - set(sqldict)
    if unknown:
        raise KeyError('add_row got unknown column(s): {}'.format(sorted(unknown)))
    for key in sqldict:
        sqldict[key].append(kwargs.get(key, ''))


def norm(text):
    """Collapse whitespace."""
    return re.sub(r'\s+', ' ', (text or '')).strip()


def clean_cell(text):
    """Normalise a pdfplumber cell: keep line breaks, drop soft hyphens/footnote noise."""
    if not text:
        return ''
    text = text.replace('’', "'").replace('‘', "'")
    text = text.replace('“', '"').replace('”', '"')
    text = text.replace('\xad', '')
    # pdfplumber splits words across wrapped lines like "Limit\ned" -> repair "- \n"
    lines = [norm(l) for l in text.split('\n')]
    return '\n'.join([l for l in lines if l])


def flatten(text):
    """Cell -> single line, repairing words the PDF wrapped mid-token (e.g. 'Co- operative')."""
    one = norm((text or '').replace('\n', ' '))
    one = re.sub(r'(\w)- (\w)', r'\1\2', one)
    return one


def fetch(url, binary=False):
    """GET with the corporate TLS proxy tolerated (verify=False)."""
    resp = requests.get(url, headers=HEADERS, verify=False, timeout=120)
    resp.raise_for_status()
    if binary:
        return resp.content
    resp.encoding = resp.apparent_encoding or 'utf-8'
    return resp.text


def resolve_pdf_link(index_html, keyword):
    """Find the register PDF by the anchor's VISIBLE LABEL. Returns (url, label)."""
    soup = BeautifulSoup(index_html, 'html.parser')
    hits = []
    for a in soup.find_all('a', href=True):
        label = norm(a.get_text(' ', strip=True))
        if keyword in label.lower():
            href = a['href']
            if href.startswith('/'):
                href = 'https://www.eccb-centralbank.org' + href
            hits.append((href, label))
    if not hits:
        raise RuntimeError(
            "SKIPPED - no anchor whose label contains '{}' on {}".format(keyword, INDEX_URL))
    # Prefer the longest label (the dated current revision) if several match.
    hits.sort(key=lambda t: len(t[1]), reverse=True)
    return hits[0]


def validity_from_url(url, label):
    """ListValidityDate: prefer the dd.m.yy stamp in the label, else the upload date in the href."""
    m = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{2})\b', label)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), 2000 + int(m.group(3))
        try:
            return datetime.date(year, month, day).strftime('%Y-%m-%d')
        except ValueError:
            pass
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', url)
    if m:
        return '{}-{}-{}'.format(m.group(1), m.group(2), m.group(3))
    return ''


def country_to_iso(heading):
    """Normalise a discovered section heading to an ISO-2 code. Raises on the unknown."""
    up = norm(heading).upper()
    for token, iso in COUNTRY_TOKEN_TO_ISO:
        if token in up:
            return iso
    raise RuntimeError('Unrecognised country section heading in PDF: {!r}. '
                       'The register layout changed - review before trusting output.'.format(heading))


# The column header is repeated on every page but is NOT byte-identical across pages
# (pages 1-5 print "BRANCH LOCATION2", pages 6-11 print "BRANCH LOCATIONS2"), and it is
# stacked over four physical rows. Recognise it by these per-cell patterns rather than by
# comparing against a signature lifted from page 1.
HEADER_CELL_PATTERNS = [
    r'^NO$', r'NAME OF LICENSED', r'^FINANCIAL$', r'^INSTITUTION OR$', r'^HOLDING COMPANY$',
    r'HEAD OFFICE', r"COMPANY'S ADDRESS", r'MAILING ADDRESS', r'PRINCIPAL OFFICE',
    r'CURRENCY UNION', r'BRANCH LOCATION', r'CLASS OR', r'CATEGORY OF', r'LICENCE HELD',
    r'RESTRICTIONS', r'LISTED ON', r'^LICENCE$',
]


def is_header_row(row):
    """A repeated column-header row: EVERY non-empty cell is header vocabulary."""
    cells = [norm((c or '').replace('\n', ' ')).upper() for c in row if norm(c)]
    if not cells:
        return False
    return all(any(re.search(p, c) for p in HEADER_CELL_PATTERNS) for c in cells)


def is_country_header(row):
    """Structural signature of a section heading: exactly one non-empty cell, all caps, no digits."""
    cells = [norm((c or '').replace('\n', ' ')) for c in row if norm(c)]
    if len(cells) != 1:
        return False
    text = cells[0]
    if len(text) < 4 or any(ch.isdigit() for ch in text):
        return False
    if is_header_row(row):
        return False
    return text == text.upper()


def map_columns(page_rows):
    """Map logical fields -> column indices using THIS page's header (9 vs 10 cols varies)."""
    ncols = max(len(r) for r in page_rows)
    joined = [''] * ncols
    for row in page_rows:
        if not is_header_row(row):
            continue
        for i, cell in enumerate(row):
            if i < ncols and norm(cell):
                joined[i] = (joined[i] + ' ' + norm(cell.replace('\n', ' ')).upper()).strip()

    def find(*keys):
        for i, head in enumerate(joined):
            for k in keys:
                if k in head:
                    return i
        return None

    def find_exact(key):
        for i, head in enumerate(joined):
            if head == key:
                return i
        return None

    cols = {
        'no': find_exact('NO'),
        'head_office': find('HEAD OFFICE'),
        'mailing': find('MAILING ADDRESS'),
        'branch': find('BRANCH LOCATION'),
        'klass': find('CLASS OR', 'CATEGORY OF'),
        'restrict': find('RESTRICTIONS'),
    }
    if cols['no'] is None or cols['head_office'] is None:
        return None
    # The licensee name lives in the merged block between NO and HEAD OFFICE.
    cols['name_span'] = list(range(cols['no'] + 1, cols['head_office']))
    return cols


def split_parent(head_office_cell):
    """HEAD OFFICE/PARENT cell -> (parent name, parent address).

    When the licensee is a subsidiary the cell's first line is the PARENT COMPANY NAME
    followed by its address. 'Not applicable' means the licensee has no foreign parent.
    """
    cell = clean_cell(head_office_cell)
    if not cell:
        return '', ''
    lines = [l for l in cell.split('\n') if l]
    if not lines:
        return '', ''
    if norm(lines[0]).lower().startswith('not applicable'):
        return '', ''
    return lines[0], ' '.join(lines[1:])


def split_city(address_cell, country_heading=''):
    """Mailing address -> (single-line address, city).

    House heuristic: the ECCB register writes the address as
      [PO Box] / [street] / [town] / [territory]
    so the town is the line above the territory. The territory itself may wrap over
    several lines ("Saint Vincent and the" / "Grenadines"), so trailing lines are dropped
    while they are still part of a territory name. Documented as a heuristic in the README.
    """
    cell = clean_cell(address_cell)
    lines = [l for l in cell.split('\n') if l]
    if not lines:
        return '', ''
    address_1 = ' '.join(lines)

    territory_words = set()
    for token, _iso in COUNTRY_TOKEN_TO_ISO:
        territory_words.add(token)
    territory_words.update(['SAINT', 'ST', 'AND', 'THE', 'COMMONWEALTH', 'OF', 'BARBUDA',
                            'GRENADINES', 'CHRISTOPHER', 'KITTS', 'NEVIS', 'BARBADOS',
                            'TRINIDAD', 'TOBAGO'])
    if country_heading:
        territory_words.update(re.sub(r'[^A-Z ]', ' ', country_heading.upper()).split())

    body = list(lines)
    while len(body) >= 2:
        tail_words = re.sub(r'[^A-Za-z ]', ' ', body[-1]).upper().split()
        if tail_words and all(w in territory_words for w in tail_words):
            body.pop()
        else:
            break

    city = body[-1] if body else ''
    city = city.strip(' ,;.')
    if re.match(r'^p\.?\s*o\.?\s*box', city, re.I) or len(city) < 2:
        city = ''
    return address_1, city


#---- Begin_MainLoop ----
listcode = 1
meta = LISTS[listcode]

print('\n[List {}] {}'.format(listcode, meta['ListName']))
print('Index: {}'.format(meta['url']))

index_html = fetch(meta['url'])
pdf_url, pdf_label = resolve_pdf_link(index_html, ANCHOR_KEYWORD)
print('Resolved anchor label : {}'.format(pdf_label))
print('Resolved PDF url      : {}'.format(pdf_url))

validity = validity_from_url(pdf_url, pdf_label)
print('ListValidityDate      : {}'.format(validity or '(not found)'))

pdf_bytes = fetch(pdf_url, binary=True)
print('PDF bytes             : {}'.format(len(pdf_bytes)))
if not pdf_bytes.startswith(b'%PDF'):
    raise RuntimeError('SKIPPED - {} did not return a PDF (soft 404?). First bytes: {!r}'
                       .format(pdf_url, pdf_bytes[:40]))

pdf_path = os.path.join(tempfolder, 'AI_ECCBAI_register.pdf')
with open(pdf_path, 'wb') as fh:
    fh.write(pdf_bytes)

# ---- parse -------------------------------------------------------------------------
entities = []          # each = dict of accumulated cell text
current_country = ''
declared_no = {}       # country -> highest NO printed by the register itself

with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
    npages = len(pdf.pages)
    print('PDF pages             : {}'.format(npages))

    for pageno, page in enumerate(pdf.pages, start=1):
        table = page.extract_table(TABLE_SETTINGS)
        if not table:
            print('  page {:>2}: no ruled table, skipped'.format(pageno))
            continue

        cols = map_columns(table)
        if cols is None:
            raise RuntimeError('page {}: column header not recognised - the register layout '
                               'changed, review before trusting output.'.format(pageno))

        for row in table:
            row = [clean_cell(c) for c in row]
            if not any(row):
                continue
            if is_header_row(row):
                continue
            if is_country_header(row):
                current_country = norm(' '.join([c for c in row if c]))
                continue

            def cell(key):
                idx = cols.get(key)
                if idx is None or idx >= len(row):
                    return ''
                return row[idx]

            name = norm(' '.join([row[i] for i in cols['name_span']
                                  if i < len(row) and row[i]]).replace('\n', ' '))
            name = re.sub(r'(\w)- (\w)', r'\1\2', name)

            no_val = norm(cell('no'))
            if no_val.isdigit() and current_country:
                declared_no[current_country] = max(declared_no.get(current_country, 0), int(no_val))

            if name:
                # A new licensee starts here.
                entities.append({
                    'country': current_country,
                    'no': no_val,
                    'name': name,
                    'head_office': cell('head_office'),
                    'mailing': cell('mailing'),
                    'branch': cell('branch'),
                    'klass': cell('klass'),
                    'restrict': cell('restrict'),
                    'page': pageno,
                })
            elif entities:
                # Continuation of the previous licensee (the register splits tall rows
                # across page breaks and across wrapped sub-cells).
                prev = entities[-1]
                for key in ('head_office', 'mailing', 'branch', 'klass', 'restrict'):
                    extra = cell(key)
                    if extra:
                        prev[key] = (prev[key] + '\n' + extra).strip()
                if no_val and not prev['no']:
                    prev['no'] = no_val

print('\nParsed {} licensee blocks'.format(len(entities)))

# ---- reconcile against the register's own per-country numbering ---------------------
from collections import Counter, OrderedDict

scraped_by_country = OrderedDict()
for ent in entities:
    scraped_by_country[ent['country']] = scraped_by_country.get(ent['country'], 0) + 1

print('\nRow-count reconciliation (scraped vs the NO column printed in the PDF):')
mismatch = 0
for country, count in scraped_by_country.items():
    dec = declared_no.get(country, 0)
    flag = 'OK' if count == dec else '*** MISMATCH ***'
    if count != dec:
        mismatch += 1
    print('  {:<45} scraped={:<3} declared_max_NO={:<3} {}'.format(country, count, dec, flag))
if mismatch:
    print('WARNING: {} country section(s) do not reconcile - inspect before delivery.'.format(mismatch))
else:
    print('All country sections reconcile with the register\'s own numbering.')

# ---- emit ---------------------------------------------------------------------------
for ent in entities:
    iso = country_to_iso(ent['country'])
    address_1, city = split_city(ent['mailing'], ent['country'])
    parent_name, parent_addr = split_parent(ent['head_office'])
    branches = flatten(ent['branch'])
    if branches.lower() in ('none', 'not applicable', ''):
        branches = ''
    licence = flatten(ent['klass'])
    restrictions = flatten(ent['restrict'])

    add_row(
        ListLabel=meta['ListLabel'],
        Name=flatten(ent['name']),
        License_Type=licence,
        CoType=restrictions if restrictions.lower() not in ('none', '') else '',
        Address_1=address_1,
        Address_2=branches,
        City=city,
        Cntry=iso,
        RegulationType='Regulated',
        RegCtry=REGCTRY,
        RegCode=REGCODE,
        ListCode=listcode,
        ListLanguage=LISTLANGUAGE,
        ListValidityDate=validity,
        ListName=meta['ListName'],
        ListProcessDate=processdate,
        **{'Name - Mother Company': parent_name,
           'Address_1 - Mother company': parent_addr}
    )

#---- Begin_writer and save df to excel ----
os.chdir(scriptfolder)

df = pd.DataFrame(sqldict)

df = df[df['Name'] != '']

# ---- replicate the register across the eight ECCB member regulators -----------------
# The parse above produced the register once, tagged RegCtry/RegCode = AI/ECCBAI. The
# ECCB licenses jointly for all eight territories, so the same register is delivered
# under each member's regulator code. `Cntry` is left untouched.
#
# NOT deduped: several institutions are licensed in more than one territory and the
# source lists them once per territory. Row count is QA'd against the register's own
# per-country numbering, so dropping them would break the reconciliation.
base_rows = len(df)
frames = [df if not OWN_COUNTRY_ONLY else df[df['Cntry'] == REGCTRY]]
for regctry, regcode in OTHER_REGULATORS.items():
    other = df[df['Cntry'] == regctry].copy() if OWN_COUNTRY_ONLY else df.copy()
    other['RegCtry'] = regctry
    other['RegCode'] = regcode
    frames.append(other)
df = pd.concat(frames, ignore_index=True)

n_regulators = 1 + len(OTHER_REGULATORS)
print('\nReplicated {} register rows across {} ECCB member regulators -> {} rows{}'.format(
    base_rows, n_regulators, len(df), ' (own-country rows only)' if OWN_COUNTRY_ONLY else ''))
if not OWN_COUNTRY_ONLY:
    assert len(df) == base_rows * n_regulators, \
        'replication produced {} rows, expected {}'.format(len(df), base_rows * n_regulators)
assert df['RegCode'].nunique() == n_regulators, \
    'expected {} distinct RegCodes, got {}'.format(n_regulators, sorted(df['RegCode'].unique()))

print('\nRows per RegCtry / RegCode:')
print(df.groupby(['RegCtry', 'RegCode']).size().to_string())

print('\nRows per Cntry (territory the institution is licensed in), {} copy:'.format(REGCODE))
print(df[df['RegCode'] == REGCODE].groupby(['ListCode', 'Cntry']).size().to_string())

print('\nRows per ListCode / ListName:')
print(df.groupby(['ListCode', 'ListName']).size().to_string())


def force_text(frame):
    """Excel silently coerces all-digit strings to floats ("40003764029" -> 4.000376e+10)
    and eats leading zeros. Pin the identifier-ish columns to text before writing."""
    frame = frame.copy()
    for col in TEXT_COLUMNS:
        frame[col] = frame[col].apply(lambda v: '' if v == '' or pd.isna(v) else str(v))
    return frame


def write_and_verify(frame, out_name):
    """Write one SQL-Ready workbook, then READ IT BACK and assert it survived the trip."""
    path = os.path.join(scriptfolder, out_name)
    frame = force_text(frame)
    frame.to_excel(path, sheet_name='SQL Ready', index=False)

    check = pd.read_excel(path, sheet_name='SQL Ready', dtype=str)
    assert len(check) == len(frame), \
        '{}: round-trip row count changed {} -> {}'.format(out_name, len(frame), len(check))
    assert list(check.columns) == list(sqldict), \
        '{}: column set changed on write'.format(out_name)
    for col in TEXT_COLUMNS:
        bad = check[col].dropna()
        bad = bad[bad.str.contains(r'^\d+\.\d+e\+', case=False, na=False)]
        assert bad.empty, '{}: Excel coerced {} to scientific notation: {}'.format(
            out_name, col, bad.tolist()[:5])
    # Validate Name CONTENT, not just that rows reconcile - a full column of the wrong
    # values would still round-trip perfectly.
    names = check.loc[check['Name'].notna(), 'Name']
    assert not names.empty, '{}: every Name is empty'.format(out_name)
    assert isinstance(names.iloc[0], str), '{}: Name did not round-trip as string'.format(out_name)
    print('  {:<46} {:>4} rows, {} cols  OK   e.g. {!r}'.format(
        out_name, len(check), len(check.columns), names.iloc[0][:38]))
    return path


#---- Begin_output files ----
written = []

if WRITE_PER_REGULATOR:
    # One workbook per ECCB member. Same run timestamp on all eight so they read as a
    # single delivery. Each file holds that regulator's rows only; `Cntry` inside still
    # spans all eight territories (see OWN_COUNTRY_ONLY).
    print('\nPer-regulator workbooks:')
    for regctry, regcode in sorted(ALL_REGULATORS.items()):
        part = df[df['RegCode'] == regcode]
        assert not part.empty, 'no rows for {} - replication did not run'.format(regcode)
        assert set(part['RegCtry']) == {regctry}, 'RegCtry leaked into the {} file'.format(regcode)
        written.append(write_and_verify(part, '{} {} SQL Ready {}.xlsx'.format(
            regctry, regcode, stamp)))

if WRITE_COMBINED:
    print('\nCombined workbook:')
    written.append(write_and_verify(df, '{} ALL SQL Ready {}.xlsx'.format(regulatorName, stamp)))

assert written, 'nothing written - set WRITE_PER_REGULATOR and/or WRITE_COMBINED'

# The eight files must together account for every row exactly once.
if WRITE_PER_REGULATOR:
    total = sum(len(pd.read_excel(p, sheet_name='SQL Ready', dtype=str))
                for p in written if not os.path.basename(p).startswith(regulatorName + ' ALL'))
    assert total == len(df), \
        'per-regulator files hold {} rows, in-memory frame has {}'.format(total, len(df))

print('\nWrote {} workbook(s) to {}'.format(len(written), scriptfolder))
