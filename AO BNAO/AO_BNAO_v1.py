# -*- coding: utf-8 -*-
# ------------------------------------------------------------------
# AO BNAO  -  Banco Nacional de Angola (National Bank of Angola)
# Source page: https://www.bna.ao/#/pt/supervisao/politica-macroprudencial/inst-financeiras-autorizadas
# Jira:   DECD-6964  (story DECD-3438, Regulators 2026 - Internal Crawlers)
#
# Jira defines a SINGLE list:
#   ListNr 1 | "Instituicoes financieras autorizadas"
#            | Comments: "Click in the most recent list and collect all the
#              entities from the pdf"
# so every entity in the PDF is emitted under ListCode '1'. The PDF's nine
# internal sections are NOT separate Jira lists - they are carried on each row
# as License_Type (section heading, verbatim Portuguese) + CoType (English
# descriptor).
#
# ---- How the source is reached -----------------------------------------
# bna.ao is an Angular SPA with hash routing, so the HTML at the Jira URL
# contains no content. The page is fed by a SharePoint-backed JSON API behind a
# Java proxy. The list component (lazy chunk 587.*.js) issues:
#
#   POST https://www.bna.ao/service/rest/generic/sharepoint/v2/search
#   {"url": "Supervisao",
#    "parameters": {"$top": 1000,
#                   "$orderby": "DataDePublicacao desc",
#                   "$filter": "Categoria eq '<category>' and Visualizar eq 1"}}
#
#   download: https://www.bna.ao/service/rest/file/getPDF/v2?url=<tail after "cms/">
#
# TRAP - do NOT use GET /service/rest/generic/sharepoint/supervisao. It answers
# 200 with ~63 records but is STALE: it holds only document ID 178 (the English
# "List of Authorised Financial Institutions - January 2023") and does NOT hold
# ID 272, the current Portuguese December 2025 edition. Using it silently yields
# a three-year-old list.
#
# Each record carries an OData__dlc_DocIdUrl.Url pointing at an INTERNAL host
# (http://172.20.42.86/sites/cms/...) that is not reachable from outside. The
# public getPDF/v2 endpoint takes the path tail after "cms/" and streams the
# file, so the internal URL is used only as a key, never fetched.
#
# "The most recent list" is resolved dynamically: every record in the category is
# collected and the one with the latest DataDePublicacao wins. No Idioma filter
# is applied, so a future English-only re-publication is still picked up. As of
# this writing the category holds two documents:
#   ID 272  2025-12-09  Portugues  "Lista das Instituicoes Financeiras Autorizadas - Dezembro 2025"
#   ID 178  2023-02-22  Ingles     "List of Authorised Financial Institutions - January 2023"
# -> ID 272 is used. ListLanguage is taken from the winning record's Idioma.
#
# Entity names are kept VERBATIM in Portuguese. They are never machine
# translated (see MZ BMO v1 -> v2: translating names corrupted them).
#
# ---- PDF layout ---------------------------------------------------------
# 4 pages, real ruled tables, selectable text (no OCR needed).
# Nine sections, each a numbered table restarting at 1:
#   NOME | SIGLA              | N.o DE REGISTO   (banks only)
#   NOME | PAIS DE ORIGEM                        (foreign bank rep. offices, 3 cols)
#   NOME | PROVINCIA / SEDE   | N.o DE REGISTO   (all other sections)
#
# Three parsing hazards, all handled:
#  1. Page-break orphan OUTSIDE the table. A section continuing onto a new page
#     has its first row rendered above the detected table bbox (the top border is
#     not re-drawn), so find_tables() drops it. Those rows are recovered from the
#     gap band above each table by bucketing their words against that table's own
#     column x-edges. Lines whose only non-empty cell is the leading number are
#     rejected (page numbers / footnote markers).
#  2. Page-break orphan INSIDE the table with UNDRAWN cell borders. On page 2 the
#     continuation row keeps its number cell but the name/seat/registration cells
#     have no top border, so extract() returns ['16', None, None, None]. Any row
#     whose leading cell is a number and whose remaining cells are all empty is
#     re-bucketed from the words in that row's own y-band. Exactly 1 row in the
#     current edition (CASAS DE CAMBIO #16 RUCAMBIO / LUANDA / 678).
#  3. Phantom columns. Some tables are detected 6 or 8 columns wide because of
#     stray vertical rules. Columns that are empty in EVERY data row of that
#     table are collapsed away, normalising each section to 3 or 4 real columns.
#
# Also handled: "SOCIEDADES NAO FINANCEIRAS PRESTADORES DE SERVICOS DE
# MICROCREDITO" is a SUPER-heading grouping the two microcredit sections that
# follow it - it has no table of its own and must not open a section.
#
# Sections 2 and 3 legitimately OVERLAP: an exchange office additionally
# authorised for cash remittances is listed in BOTH, with the SAME registration
# number. These are NOT duplicates to be removed - the source shows both rows, so
# both are emitted (project rule: row count must match the source).
#
# Self-validation: every section numbers its own rows 1..N, so after parsing the
# script asserts each section's sequence is exactly range(1, N+1) and that no row
# has an empty Name. A dropped, doubled or hollow row fails the run loudly.
#
# ---- Status markers -----------------------------------------------------
# Footnote legends read verbatim from the PDF:
#   p1  "* Banco em liquidacao, apos dissolucao voluntaria."
#   p1  "** Banco em processo de inicio de actividade"
#   p3  "* Sociedade de Microcredito Avanca na Vida - Com actividade suspensa"
#   p3  "* (SM) - Servicos moveis"
# The first three are STATUS and drive RegulationType. "(SM)" is a licence-scope
# note on payment institutions, NOT a status - it is moved into License_Type and
# leaves RegulationType as 'Regulated'.
# An unmapped marker aborts the run rather than being silently ignored.
#
# ---- Fields the source does NOT publish ---------------------------------
# This list is name + abbreviation/seat + registration number only. There is NO
# address, phone, fax, e-mail, website or authorisation date anywhere in the
# document, so those columns are left empty rather than invented.
# ------------------------------------------------------------------
import os
import re
import ssl
import time
import datetime
import warnings

import requests
import pandas as pd
import pdfplumber

warnings.filterwarnings('ignore')
# Mac / corporate TLS proxy: certificate chain is re-signed, so verification off.
ssl._create_default_https_context = ssl._create_unverified_context

# ------ workspace path ------------------------------------------------
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))   # production (.py)
except NameError:
    scriptfolder = os.getcwd()                                  # notebook
os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder')
os.makedirs(tempfolder, exist_ok=True)

# Project convention for the output workbook (see CLAUDE.md and every sibling
# regulator): "<CC> <AGENCY> SQL Ready <YYYY-MM-DD HH.MM.SS>.xlsx" - spaces, not
# underscores, and timestamped. The _vN suffix belongs on the SCRIPT, never on
# the workbook.
regulatorName = 'AO BNAO'
now = datetime.datetime.now()
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":", ".")[:-7])

print('Running {} Web Scraping Tool v.1'.format(regulatorName))

# ------ the 43-key project schema (order is fixed, do not change) ------
SQL_KEYS = ['bvdid', 'priority', 'ListLabel', 'Typology', 'EntryType', 'Name',
            'InternalID_1', 'InternalID_1_type', 'InternalID_2', 'InternalID_2_type',
            'InternalID_3', 'InternalID_3_type', 'CoType', 'License_Type',
            'Address_1', 'Address_2', 'City', 'Zip', 'Cntry', 'Phone', 'Fax',
            'Website', 'Email', 'RegulationType', 'RegulationTypeCode',
            'RegulationDate', 'CancellationDate', 'RegCtry', 'RegCode', 'ListCode',
            'ListLanguage', 'ListValidityDate', 'ListName', 'ListProcessDate',
            'LEI Code', 'BIC SWIFT Code', 'Name - Mother Company',
            'Address_1 - Mother company', 'Address_2 -  Mother company',
            'City - Mother company', 'Zip - Mother company',
            'Cntry - Mother company', 'Phone - Mother company']

# columns Excel would otherwise coerce from digit-strings to floats
TEXT_COLS = ['InternalID_1', 'InternalID_2', 'InternalID_3', 'Zip', 'Phone', 'Fax',
             'Zip - Mother company', 'Phone - Mother company']


def blank_row():
    return {k: '' for k in SQL_KEYS}


# ------ regdict (parsed from the Jira description) --------------------
# ListName follows the SOURCE PAGE, not the Jira description.  Jira writes
# "Instituicoes financieras autorizadas" -- "financieras" is the Spanish spelling; BNA is
# Portuguese-language and calls the section "Instituições Financeiras Autorizadas" (verified
# 2026-09-02 against the live API's own Categoria field, "Política Macroprudencial -
# Instituições Financeiras Autorizadas", and the page slug inst-financeiras-autorizadas).
# The accented form is safe on the cp1252 control server because ListName is never printed --
# it only ever travels into the workbook, which is UTF-8.
regdict = {
    1: {"ListName": u"Instituições Financeiras Autorizadas",
        "URL": "https://www.bna.ao/#/pt/supervisao/politica-macroprudencial/inst-financeiras-autorizadas",
        "Comments": "Click in the most recent list and collect all the entities from the pdf"},
}

REG_CTRY = 'AO'
REG_CODE = 'BNAO'
LIST_CODE = '1'
# ListLabel: 1 = bank, 2 = insurance, 3 = bank & insurance, 4 = everything else.
# This single list is BNA's register of authorised credit / financial
# institutions and is headed by the 23 licensed banks; Angolan insurers are
# supervised by ARSEG, not BNA, so nothing here is an insurance entry -> 1.
LIST_LABEL = 1

# ------ API ------------------------------------------------------------
BASE = 'https://www.bna.ao/service/rest'
SEARCH_URL = BASE + '/generic/sharepoint/v2/search'
GETPDF_URL = BASE + '/file/getPDF/v2?url='
CATEGORY = ('Política Macroprudencial - '
            'Instituições Financeiras Autorizadas')

HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/124.0 Safari/537.36'),
    'Accept': 'application/json, text/plain, */*',
    'Content-Type': 'application/json',
    'Origin': 'https://www.bna.ao',
    'Referer': 'https://www.bna.ao/',
}


def http_json(url, payload, tries=5):
    """POST with retry - the proxy intermittently answers 502."""
    last = None
    for attempt in range(tries):
        try:
            r = requests.post(url, json=payload, headers=HEADERS,
                              verify=False, timeout=90)
            if r.status_code == 200:
                return r.json()
            last = 'HTTP {}'.format(r.status_code)
        except Exception as exc:                      # noqa: BLE001
            last = type(exc).__name__
        print('  retry {} ({})'.format(attempt + 1, last))
        time.sleep(4)
    raise RuntimeError('search endpoint failed: {}'.format(last))


def newest_document():
    """Return the most recently published document record in the IFA category."""
    payload = {
        'url': 'Supervisão',
        'parameters': {
            '$top': 1000,
            '$orderby': 'DataDePublicacao desc',
            '$filter': "Categoria eq '{}' and Visualizar eq 1".format(CATEGORY),
        },
    }
    data = http_json(SEARCH_URL, payload)
    recs = data if isinstance(data, list) else (data.get('value') or data.get('results') or [])
    recs = [r for r in recs if (r.get('OData__dlc_DocIdUrl') or {}).get('Url')]
    if not recs:
        raise RuntimeError('no documents returned for the IFA category')
    recs.sort(key=lambda r: r.get('DataDePublicacao') or '', reverse=True)
    print('documents in category: {} - using ID {}'.format(len(recs), recs[0].get('ID')))
    return recs[0]


def download_pdf(rec, dest):
    url = (rec['OData__dlc_DocIdUrl']['Url'] or '')
    if 'cms/' not in url:
        raise RuntimeError('unexpected DocIdUrl shape')
    tail = url.split('cms/', 1)[1]          # kept unencoded - that is what the app sends
    full = GETPDF_URL + tail
    last = None
    for attempt in range(5):
        try:
            r = requests.get(full, headers={'User-Agent': HEADERS['User-Agent']},
                             verify=False, timeout=180)
            if r.status_code == 200 and r.content[:5] == b'%PDF-':
                with open(dest, 'wb') as fh:
                    fh.write(r.content)
                print('downloaded {} bytes'.format(len(r.content)))
                return dest
            last = 'HTTP {} / magic {!r}'.format(r.status_code, r.content[:5])
        except Exception as exc:                      # noqa: BLE001
            last = type(exc).__name__
        print('  retry {} ({})'.format(attempt + 1, last))
        time.sleep(4)
    raise RuntimeError('PDF download failed: {}'.format(last))


# ------ PDF section vocabulary ----------------------------------------
# Order matters only for substring disambiguation; headings_in() sorts by
# position in the page text.
SECTIONS = [
    'SOCIEDADES NÃO FINANCEIRAS PRESTADORES DE SERVIÇOS DE MICROCRÉDITO',
    'CASAS DE CÂMBIO AUTORIZADAS A EXERCER ACTIVIDADE DE REMESSA DE VALORES',
    'ESCRITÓRIOS DE REPRESENTAÇÃO DE BANCOS ESTRANGEIROS',
    'SOCIEDADES PRESTADORAS DE SERVIÇOS DE PAGAMENTOS',
    'INSTITUIÇÕES FINANCEIRAS BANCÁRIAS',
    'SOCIEDADES DE MICROCRÉDITO',
    'OPERADORES DE MICROCRÉDITO',
    'COOPERATIVAS DE CRÉDITO',
    'CASAS DE CÂMBIO',
    'FUNDOS',
]
# grouping header, has no table of its own
SUPER = {'SOCIEDADES NÃO FINANCEIRAS PRESTADORES DE SERVIÇOS DE MICROCRÉDITO'}

BANKS = 'INSTITUIÇÕES FINANCEIRAS BANCÁRIAS'
REP_OFFICES = 'ESCRITÓRIOS DE REPRESENTAÇÃO DE BANCOS ESTRANGEIROS'
PAYMENTS = 'SOCIEDADES PRESTADORAS DE SERVIÇOS DE PAGAMENTOS'
MICROCREDIT_CO = 'SOCIEDADES DE MICROCRÉDITO'

COTYPE = {
    BANKS: 'Bank',
    'CASAS DE CÂMBIO': 'Foreign Exchange Bureau',
    'CASAS DE CÂMBIO AUTORIZADAS A EXERCER ACTIVIDADE DE REMESSA DE VALORES':
        'Foreign Exchange Bureau - Money Remittance',
    MICROCREDIT_CO: 'Microcredit Company',
    'OPERADORES DE MICROCRÉDITO': 'Microcredit Operator',
    PAYMENTS: 'Payment Service Provider',
    'FUNDOS': 'Fund',
    'COOPERATIVAS DE CRÉDITO': 'Credit Cooperative',
    REP_OFFICES: 'Representative Office of a Foreign Bank',
}

# (section, marker) -> RegulationType, from the verbatim PDF footnote legends
MARKER_STATUS = {
    (BANKS, '**'): 'Not Operational',      # "Banco em processo de inicio de actividade"
    (BANKS, '*'): 'Inactive License',      # "Banco em liquidacao, apos dissolucao voluntaria"
    (MICROCREDIT_CO, '*'): 'Inactive License',   # "Com actividade suspensa"
}

# 'PAIS DE ORIGEM' values -> ISO country code (rep. offices only)
COUNTRY_ISO = {
    'ALEMANHA': 'DE',
    'ÁFRICA DO SUL': 'ZA',
}


def norm(t):
    return re.sub(r'\s+', ' ', (t or '')).upper().strip()


def tidy(s):
    return re.sub(r'\s+', ' ', (s or '').replace('\n', ' ')).strip()


def headings_in(text):
    """Real section headings present in a text block, in order of appearance."""
    flat = norm(text)
    found = []
    for s in SECTIONS:
        i = flat.find(s)
        if i >= 0:
            found.append((i, s))
    found.sort()
    out = []
    for i, s in found:
        # drop a heading that is only a substring of a longer heading also present
        if any((s != o and s in o) for _, o in found):
            continue
        out.append((i, s))
    return [s for _, s in out if s not in SUPER]


def bucket(words, edges):
    """Assign words to columns by their horizontal centre."""
    cells = [''] * (len(edges) - 1)
    for w in sorted(words, key=lambda w: w['x0']):
        cx = (w['x0'] + w['x1']) / 2.0
        for k in range(len(edges) - 1):
            if edges[k] - 2 <= cx < edges[k + 1] + 2:
                cells[k] = (cells[k] + ' ' + w['text']).strip()
                break
    return cells


def collapse(rows):
    """Drop columns that are empty in EVERY data row of this table."""
    if not rows:
        return rows
    n = max(len(r) for r in rows)
    rows = [r + [''] * (n - len(r)) for r in rows]
    keep = [k for k in range(n) if any(r[k].strip() for r in rows)]
    return [[r[k] for k in keep] for r in rows]


def col_edges(t):
    """Vertical grid lines of a detected table, as x coordinates.

    Table.columns exists only in recent pdfplumber; the control server's build
    has Table.rows but NOT Table.columns, so `t.columns` raises
    AttributeError there.  A pdfplumber column is nothing but the table's
    cells grouped by their left edge (Table._get_rows_or_cols groups
    self.cells on x0), so the same edge list is derived from t.cells directly
    and is byte-identical on every version.
    """
    xs = sorted(set(c[0] for c in t.cells))          # one left edge per column
    last = max(c[2] for c in t.cells if c[0] == xs[-1])   # right edge of the last one
    return xs + [last]


def parse_pdf(path):
    """-> ({section: [ [seq, name, col3, col4?], ... ]}, [section order])"""
    per, order, current = {}, [], None
    repaired = 0
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            tables = sorted(page.find_tables(), key=lambda t: t.bbox[1])
            prev_bottom = 0.0
            for t in tables:
                edges = col_edges(t)

                # --- band above this table: headings + orphan rows -----
                gap = page.crop((0, prev_bottom, page.width, t.bbox[1]))
                heads = headings_in(gap.extract_text() or '')
                lines = {}
                for w in gap.extract_words():
                    lines.setdefault(round(w['top'] / 3.0), []).append(w)
                strays = []
                for key in sorted(lines):
                    cells = bucket(lines[key], edges)
                    lead = cells[0].strip()
                    if lead.isdigit() and len(lead) <= 3 and any(c.strip() for c in cells[1:]):
                        strays.append([tidy(c) for c in cells])
                # orphans belong to the section open BEFORE any heading in this gap
                if strays and current:
                    per.setdefault(current, []).extend(strays)
                for h in heads:
                    current = h
                    if h not in order:
                        order.append(h)
                    per.setdefault(h, [])

                # --- the ruled table itself ---------------------------
                meta_rows = t.rows
                data = []
                for ri, raw in enumerate(t.extract()):
                    cells = [tidy(c) for c in raw]
                    if not (cells and cells[0].isdigit()):
                        continue
                    if not any(c for c in cells[1:]):
                        # hollow row: borders not drawn - re-bucket its y-band
                        rb = meta_rows[ri].bbox
                        band = page.crop((t.bbox[0], rb[1], t.bbox[2], rb[3]))
                        cells = [tidy(c) for c in bucket(band.extract_words(), edges)]
                        repaired += 1
                    data.append(cells)
                data = collapse(data)
                if current and data:
                    per.setdefault(current, []).extend(data)
                prev_bottom = t.bbox[3]
    print('hollow rows repaired: {}'.format(repaired))
    return per, order


def check_sections(per, order):
    """Every section must number its rows 1..N and never carry an empty name."""
    total = 0
    for s in order:
        rows = per[s]
        nums = [int(r[0]) for r in rows]
        assert nums == list(range(1, len(nums) + 1)), \
            'section {!r}: row numbers not contiguous -> {}'.format(s[:40], nums)
        assert all(len(r) >= 2 and r[1].strip() for r in rows), \
            'section {!r}: a row has an empty name'.format(s[:40])
        total += len(rows)
        print('  {:>4} rows  {}'.format(len(rows), s[:60]))
    return total


MARKER_RE = re.compile(r'\*+\s*$')
SM_RE = re.compile(r'\s*\(SM\)\s*')


def split_markers(name):
    """-> (clean name, marker string or '', had_SM)"""
    had_sm = bool(SM_RE.search(name))
    n = SM_RE.sub(' ', name).strip()
    m = MARKER_RE.search(n)
    marker = m.group(0).strip() if m else ''
    n = MARKER_RE.sub('', n).strip()
    n = n.rstrip(',').strip()
    return n, marker, had_sm


def build_rows(per, order, doc):
    processdate = now.strftime('%Y-%m-%d')     # same clock as the output filename
    validity = (doc.get('DataDePublicacao') or '')[:10]
    lang = 'PT' if (doc.get('Idioma') or '').startswith('Portugu') else 'EN'
    list_name = regdict[1]['ListName']

    rows, unmapped = [], []
    for section in order:
        for cells in per[section]:
            raw_name = cells[1]
            name, marker, had_sm = split_markers(raw_name)

            regtype = 'Regulated'
            if marker:
                key = (section, marker)
                if key in MARKER_STATUS:
                    regtype = MARKER_STATUS[key]
                else:
                    unmapped.append((section[:40], marker, name[:40]))

            r = blank_row()
            r.update({
                'ListLabel': LIST_LABEL,
                'Name': name,                       # verbatim Portuguese
                'CoType': COTYPE.get(section, ''),
                'License_Type': section,            # verbatim Portuguese heading
                'Cntry': REG_CTRY,
                'RegulationType': regtype,
                'RegCtry': REG_CTRY,
                'RegCode': REG_CODE,
                'ListCode': LIST_CODE,
                'ListLanguage': lang,
                'ListValidityDate': validity,
                'ListName': list_name,
                'ListProcessDate': processdate,
            })

            if section == REP_OFFICES:
                # NOME | PAIS DE ORIGEM - no seat, no registration number
                origin = cells[2] if len(cells) > 2 else ''
                r['Cntry - Mother company'] = COUNTRY_ISO.get(norm(origin), origin)
            elif section == BANKS:
                # NOME | SIGLA | N.o DE REGISTO
                if len(cells) > 2 and cells[2]:
                    r['InternalID_2'] = cells[2]
                    r['InternalID_2_type'] = 'Sigla'
                if len(cells) > 3 and cells[3]:
                    r['InternalID_1'] = cells[3]
                    r['InternalID_1_type'] = 'N.o de Registo'
            else:
                # NOME | PROVINCIA / SEDE | N.o DE REGISTO
                if len(cells) > 2:
                    r['City'] = cells[2]
                if len(cells) > 3 and cells[3]:
                    r['InternalID_1'] = cells[3]
                    r['InternalID_1_type'] = 'N.o de Registo'

            if had_sm:
                # licence-scope note, not a status
                r['License_Type'] = section + ' - Serviços Móveis'

            rows.append(r)

    assert not unmapped, 'unmapped status marker(s) - read the new PDF legend: {}'.format(unmapped)
    return rows


# ================= run =================================================
doc = newest_document()
pdf_path = os.path.join(tempfolder, 'AO_BNAO_ifa.pdf')
download_pdf(doc, pdf_path)

per, order = parse_pdf(pdf_path)
print('sections found: {}'.format(len(order)))
total_parsed = check_sections(per, order)
print('parsed rows: {}'.format(total_parsed))

rows = build_rows(per, order, doc)
assert len(rows) == total_parsed

df = pd.DataFrame(rows)
df = df.reindex(columns=SQL_KEYS, fill_value='')
df = df[df['Name'] != '']

for col in TEXT_COLS:
    df[col] = df[col].apply(lambda v: '' if v == '' or pd.isna(v) else str(v))

assert list(df.columns) == SQL_KEYS
assert len(df.columns) == 43

outfile = os.path.join(scriptfolder, filename)
df.to_excel(outfile, sheet_name='SQL Ready', index=False)

# ------ read the workbook back and prove nothing was coerced -----------
chk = pd.read_excel(outfile, sheet_name='SQL Ready', dtype=str).fillna('')
assert len(chk) == len(df), 'row count changed on write/read'
assert list(chk.columns) == SQL_KEYS, 'column set changed on write/read'
for col in TEXT_COLS:
    bad = [v for v in chk[col] if v and ('.' in v or 'e+' in v.lower())]
    assert not bad, '{} was coerced to float: {}'.format(col, bad[:3])
assert (chk['InternalID_1'].astype(str).str.strip() != '').sum() == \
       (df['InternalID_1'].astype(str).str.strip() != '').sum()

print('Saved {} rows to {}'.format(len(df), outfile))
print('per ListCode: {}'.format(df.groupby('ListCode').size().to_dict()))
print('per RegulationType: {}'.format(df.groupby('RegulationType').size().to_dict()))

# ------ clean the temp download ---------------------------------------
# Project convention: empty tempfolder's CONTENTS, keep the directory itself
# (every sibling regulator ships a tempfolder/). Guarded against a bad path.
assert os.path.isabs(tempfolder) and os.path.basename(tempfolder) == 'tempfolder' \
    and os.path.dirname(tempfolder) == scriptfolder, 'refusing to clear {!r}'.format(tempfolder)
for rem in os.listdir(tempfolder):
    target = os.path.join(tempfolder, rem)
    if os.path.isfile(target):
        os.remove(target)
print('tempfolder emptied, directory kept: {}'.format(os.path.isdir(tempfolder)))
