#---- Begin_Librairie ----
# BO ASFI - Autoridad de Supervision del Sistema Financiero (Bolivia)
# DECD-6977
#
# List 1: "Entidades Supervisadas Con Licencia De Funcionamiento"
#   https://www.asfi.gob.bo/la/entidades-intermediacion-financiera-licencia-funcionamiento
#   Ticket comment: "take the data provided from the first pdf 'Listado general de las
#   entidades de intermediacion financiera con licencia de funcionamiento 04_2026.pdf'".
#
# NOTES ON THE SOURCE (verified live 2026-09-03):
#
#   1. NAME IS THE LISTADO NAME COLUMN, VERBATIM. The PDF is laid out as six blocks, each
#      with the entity category in the top-left header cell ("Bancos Multiples",
#      "Cooperativas de Ahorro y Credito Abiertas y Societarias", ...). The name column then
#      carries only the REMAINDER of the legal name: row 1 of Bancos Multiples reads
#      "Nacional de Bolivia S.A.", not "Banco Nacional de Bolivia S.A."; the cooperativas
#      read 'Abierta "Jesus Nazareno" R.L.'.
#
#      DECISION (ticket owner, 2026-09-03): take the name column as published and do NOT
#      prepend the block header. Rationale given: the category is already carried in CoType,
#      and repeating it in Name makes the 41 cooperativas share a ~39-char prefix, which
#      inflates pairwise similarity in downstream entity matching.
#
#      So Name here is deliberately NOT the full legal name. The only cleanup applied is
#      stripping a trailing footnote marker ("(1)"). If a future consumer needs the official
#      full name, it is in the Siglas PDF that this script already downloads - see below.
#
#      The same page publishes "Siglas de Entidades de Intermediacion Financiera", which
#      lists the identical 67 entities with their full official name and a 3-character ASFI
#      sigla. This version still joins the two, but ONLY to populate InternalID_1 with the
#      sigla. The Listado drives the ROW SET (as the ticket requires), supplies Name, and
#      supplies Oficina Central/City.
#
#   2. THE TWO PDFs ARE NOT IN THE SAME ORDER, so they cannot be zipped positionally.
#      "Madre y Maestra" is entry 8 in the Siglas cooperativas block but entry 24 in the
#      Listado. Joining by position would have silently mislabelled ~30 cooperativas.
#      The join is therefore by normalised name, scoped to the matching category block.
#
#   3. ONE NAME DISAGREES BETWEEN THE TWO PDFs: the Listado says "DIACONIA FRIF - IFD",
#      the Siglas say "DIACONIA FRID - IFD" (F/D transposition - one of them is a typo).
#      Rather than lower a fuzzy threshold until it matches - which would also let genuine
#      mismatches through - the join pairs RESIDUALS: after exact containment matching, if
#      a category has exactly one unmatched row and exactly one unclaimed sigla, they are
#      by construction each other's partner. Measured 2026-09-03: 66/67 by containment,
#      1/67 by residual, 0 unmatched.
#      Since Name now comes from the Listado, the OUTPUT CARRIES THE LISTADO SPELLING
#      ("DIACONIA FRIF - IFD"); the sigla IDI still comes from the Siglas side.
#
#   4. SIX CITIES ARE GENUINELY BLANK IN THE SOURCE (cooperativas 13, 28, 32, 33, 34, 40).
#      Verified against the raw PDF text layer, not just the table cells - the "Oficina
#      Central" column really is empty for those rows. They are left blank, not guessed.
#
#   5. PARSING THE SIGLAS PDF HAS TWO TRAPS, both of which produced a plausible-looking
#      67/67 total while individual blocks were wrong:
#        - the sigla "VL1" contains a digit, so a [A-Z]{3} code pattern silently drops it;
#        - the header "ENTIDADES FINANCIERAS DEL ESTADO O CON PARTICIPACION MAYORITARIA /
#          DEL ESTADO" wraps, and the continuation line "DEL ESTADO" parses as a perfectly
#          well-formed entry with code "DEL" and name "ESTADO".
#      Both are handled below (alphanumeric code, and an entry name must contain a
#      lowercase letter - ALL-CAPS lines are headers, never entities).
#
#   6. No browser is needed: plain requests returns 200 for both the page and the PDFs.
#      verify=False is required behind the corporate TLS-inspecting proxy.
#
#   7. The sibling PDFs on the same page - "en Liquidacion", "en Proceso de Intervencion",
#      "en Proceso de Quiebra" - are deliberately NOT scraped. The ticket scopes this list
#      to the first PDF, and those entities do not hold a Licencia de Funcionamiento.
#      Every row this script emits therefore gets RegulationType 'Regulated'.

import os
import re
import io
import sys
import difflib
import datetime
import unicodedata

import requests
import pandas as pd
import pdfplumber

requests.packages.urllib3.disable_warnings()

TIMEOUT = (10, 60)

#---- Begin_fileName ----

regulatorName = 'BO ASFI'
REGCTRY = 'BO'
REGCODE = 'ASFI'

print('Running {} Web Scraping Tool v.3.0'.format(regulatorName))

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(':', '.')[:-7])

try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))   # production (.py)
except NameError:
    scriptfolder = os.getcwd()                                   # notebook

os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder')
if os.path.exists(tempfolder):
    for rem in os.listdir(tempfolder):
        try:
            os.remove(os.path.join(tempfolder, rem))
        except OSError:
            pass
else:
    os.mkdir(tempfolder)

#---- Begin_regdict ----
# Straight from the DECD-6977 description table.

regdict = {
    1: dict(
        ListName='Entidades Supervisadas Con Licencia De Funcionamiento',
        # ListLabel 1: every entity here is a bank / financial-intermediation entity
        # (bancos multiples, bancos PYME, EFV, cooperativas de ahorro y credito, IFD).
        # No insurance entity appears on this list - ASFI supervises insurance under a
        # separate register that this ticket does not cover.
        ListLabel=1,
        URL='https://www.asfi.gob.bo/la/entidades-intermediacion-financiera-licencia-funcionamiento',
        Comments='Take the data from the first pdf, "Listado general de las entidades '
                 'de intermediacion financiera con licencia de funcionamiento".',
    ),
}

# Per-category row counts measured on the 04_2026 edition (2026-09-03). The PDF is
# reissued monthly, so drift is reported as a warning, never a failure.
EXPECTED_2026_04 = {
    'BANCOS MULTIPLES': 11,
    'BANCOS PYME': 2,
    'ENTIDADES FINANCIERAS DEL ESTADO': 2,
    'ENTIDADES FINANCIERAS DE VIVIENDA': 3,
    'COOPERATIVAS DE AHORRO Y CREDITO': 41,
    'INSTITUCIONES FINANCIERAS DE DESARROLLO': 8,
}
EXPECTED_TOTAL = sum(EXPECTED_2026_04.values())   # 67

#---- Begin_sqldict ----

sqldict={'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
          'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
          'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
          'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
          'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
          'Phone - Mother company': []}

SQL_KEYS = list(sqldict.keys())
assert len(SQL_KEYS) == 43, 'schema must be exactly 43 keys, got {}'.format(len(SQL_KEYS))

# Identifiers are text, not quantities. Excel turns a numeric-looking id into 4.0e+10 and
# eats leading zeros, so these are pinned to str and re-checked after the round-trip.
TEXT_COLS = ['InternalID_1', 'InternalID_2', 'InternalID_3', 'Zip', 'Phone', 'Fax',
             'ListCode', 'ListLabel']

warnings_seen = []


#---- Begin_Function ----
def warn(msg):
    warnings_seen.append(msg)
    print('   ** {}'.format(msg))


def ascii_slug(s, limit=70):
    """cp1252 console safety. The Windows control server raises UnicodeEncodeError on any
    non-cp1252 byte, and this source is Spanish (acentos + enye + curly quotes), so
    nothing scraped is ever printed raw."""
    return re.sub(r'[^\x20-\x7e]', '?', str(s or ''))[:limit]


def add_row(**kw):
    """Single writer for sqldict. Appends to EVERY one of the 43 keys on every record and
    raises on an unknown key, so ragged columns / schema drift are impossible."""
    unknown = set(kw) - set(SQL_KEYS)
    if unknown:
        raise KeyError('add_row got unknown column(s): {}'.format(sorted(unknown)))
    for k in SQL_KEYS:
        v = kw.get(k, '')
        sqldict[k].append('' if v is None else str(v))
    lens = set(len(v) for v in sqldict.values())
    if len(lens) != 1:
        raise AssertionError('sqldict columns fell out of sync: {}'.format(lens))


def clean(t):
    """Collapse the newlines pdfplumber leaves inside a wrapped cell and normalise the
    typographic quotes the PDF uses around cooperativa names."""
    if t is None:
        return ''
    t = str(t).replace('\n', ' ')
    for a, b in (('“', '"'), ('”', '"'), ('‘', "'"), ('’', "'"),
                 ('–', '-'), ('—', '-'), (' ', ' ')):
        t = t.replace(a, b)
    return re.sub(r'\s+', ' ', t).strip()


def norm(t):
    """Accent-folded, punctuation-free key used for every comparison. The two PDFs differ
    in hyphenation ('CIDRE - IFD' vs 'CIDRE IFD'), capitalisation and quote characters, so
    nothing may be compared on its raw form."""
    t = unicodedata.normalize('NFKD', clean(t).lower())
    t = ''.join(c for c in t if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]', '', t)


# Canonical category keys, matched as a normalised PREFIX so that the header wording may
# drift ("...Societaria" / "...Societarias" / "...(continuacion)") without breaking. The
# two "Entidades Financieras de/del ..." prefixes are fully spelled out because one would
# otherwise be a prefix of the other.
#
# The third element is the label written to CoType. It is spelled out rather than derived
# from the key with .title(), which produces "Bancos Pyme" and "Cooperativas De Ahorro Y
# Credito" - wrong casing and stripped accents in a Spanish-language field.
CATEGORIES = [
    ('bancosmultiples',                      'BANCOS MULTIPLES',
     'Bancos Múltiples'),
    ('bancospyme',                           'BANCOS PYME',
     'Bancos PYME'),
    ('entidadesfinancierasdelestado',        'ENTIDADES FINANCIERAS DEL ESTADO',
     'Entidades Financieras del Estado o con Participación Mayoritaria del Estado'),
    ('entidadesfinancierasdevivienda',       'ENTIDADES FINANCIERAS DE VIVIENDA',
     'Entidades Financieras de Vivienda'),
    ('cooperativasdeahorroycredito',         'COOPERATIVAS DE AHORRO Y CREDITO',
     'Cooperativas de Ahorro y Crédito Abiertas y Societarias'),
    ('institucionesfinancierasdedesarrollo', 'INSTITUCIONES FINANCIERAS DE DESARROLLO',
     'Instituciones Financieras de Desarrollo'),
]

CATEGORY_LABEL = dict((key, label) for _, key, label in CATEGORIES)


def category_of(text):
    n = norm(text)
    for prefix, key, _label in CATEGORIES:
        if n.startswith(prefix):
            return key
    return None


MONTHS = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
          'julio': 7, 'agosto': 8, 'septiembre': 9, 'setiembre': 9, 'octubre': 10,
          'noviembre': 11, 'diciembre': 12}


def spanish_date(text):
    """'30 de abril de 2026' -> '2026-04-30'. Returns '' when no date is present."""
    t = unicodedata.normalize('NFKD', clean(text).lower())
    t = ''.join(c for c in t if not unicodedata.combining(c))
    m = re.search(r'(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})', t)
    if not m or m.group(2) not in MONTHS:
        return ''
    try:
        return datetime.date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1))).isoformat()
    except ValueError:
        return ''


def fetch(url, what):
    r = requests.get(url, timeout=TIMEOUT, verify=False, headers={
        'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/126.0 Safari/537.36'),
        'Accept-Language': 'es-ES,es;q=0.9',
    })
    r.raise_for_status()
    print('   fetched {:<8} {:>9,} bytes  {}'.format(what, len(r.content), r.status_code))
    return r


def resolve_pdf(html, base_url, must_contain):
    """Resolve a PDF href off the index page at RUNTIME by its link text.

    The filenames carry the edition ('...04_2026.pdf') and the directory carries the
    publication month ('/2026-05/'), so both change every month. Hard-coding either would
    quietly serve a stale edition forever, so nothing here is hard-coded but the wording.
    """
    from urllib.parse import urljoin
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    want = norm(must_contain)
    for a in soup.find_all('a', href=True):
        if '.pdf' not in a['href'].lower():
            continue
        if want in norm(a.get_text(' ', strip=True)):
            return urljoin(base_url, a['href'])
    raise RuntimeError('no PDF link whose text contains {!r} on {}'.format(must_contain, base_url))


def parse_listado(pdf_path):
    """Row set + Oficina Central, straight from the ticket's PDF.

    Each category block is a table whose [0][0] cell holds the category name; data rows are
    the ones whose first cell is the running number. The small stray 'Oficina/Central'
    tables pdfplumber also finds (the rotated column caption) are skipped.
    """
    rows = []
    validity = ''
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            if not validity:
                m = re.search(r'actualizada\s+al\s+(.{0,40})', clean(page.extract_text() or ''), re.I)
                if m:
                    validity = spanish_date(m.group(1))
            for table in pdf_page_tables(page):
                header = clean(table[0][0]) if table and table[0] else ''
                cat = category_of(header)
                if cat is None:
                    continue
                for r in table:
                    num = clean(r[0])
                    if not num.isdigit():
                        continue
                    rows.append(dict(cat=cat, num=int(num),
                                     raw_name=clean(r[1]) if len(r) > 1 else '',
                                     city=clean(r[2]) if len(r) > 2 else ''))
    return rows, validity


def pdf_page_tables(page):
    for t in page.extract_tables():
        if t and len(t) >= 3:
            yield t


def parse_siglas(pdf_path):
    """Official full names + ASFI siglas, grouped by the same category keys.

    An entry line is 'XXX Some Name'. Two guards, both earned (see header note 5):
      - the code is [A-Z][A-Z0-9]{2}, because the EFV sigla 'VL1' ends in a digit;
      - the name must contain a lowercase letter, because a wrapped ALL-CAPS header
        continuation ('DEL ESTADO') is otherwise a valid-looking entry.
    """
    groups = {}
    notes = {}
    cur = None
    note_id = None
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for line in (page.extract_text() or '').split('\n'):
                line = clean(line)
                if not line:
                    continue

                m = re.match(r'^\((\d+)\)\s*(.*)$', line)          # footnote starts
                if m:
                    note_id = m.group(1)
                    notes[note_id] = m.group(2)
                    continue
                if note_id is not None and not re.match(r'^[A-Z][A-Z0-9]{2}\s', line):
                    notes[note_id] += ' ' + line                    # footnote continuation
                    continue

                cat = category_of(line)
                if cat is not None:
                    cur, note_id = cat, None
                    groups.setdefault(cat, [])
                    continue

                m = re.match(r'^([A-Z][A-Z0-9]{2})\s+(\S.*)$', line)
                if m and cur and re.search(r'[a-z]', m.group(2)):
                    name = m.group(2)
                    ref = re.search(r'\((\d+)\)\s*$', name)
                    groups[cur].append(dict(code=m.group(1),
                                            name=re.sub(r'\s*\(\d+\)\s*$', '', name).strip(),
                                            ref=ref.group(1) if ref else ''))
                    note_id = None
    return groups, notes


def join_names(rows, groups):
    """Attach the official name + sigla to every Listado row, within its own category.

    Pass 1 - containment on the normalised form: the Listado stub is a substring of the
             official name ('nacionaldeboliviasa' in 'banconacionaldeboliviasa').
    Pass 2 - residual: a category left with exactly one unmatched row and exactly one
             unclaimed sigla has, by construction, found its pair. This is what absorbs the
             FRIF/FRID typo without a fuzzy threshold that could mis-assign a real entity.
    Anything still unmatched keeps the Listado stub and is reported - never silently
    guessed, and never quietly dropped.
    """
    claimed = {}
    for row in rows:
        stub = re.sub(r'\s*\(\d+\)\s*$', '', row['raw_name']).strip()
        row['stub'] = stub
        row['match'] = None
        row['how'] = ''
        key = norm(stub)
        pool = [e for e in groups.get(row['cat'], [])
                if e['code'] not in claimed.get(row['cat'], set())]
        hits = [e for e in pool if key and key in norm(e['name'])]
        if len(hits) == 1:
            row['match'], row['how'] = hits[0], 'contains'
            claimed.setdefault(row['cat'], set()).add(hits[0]['code'])

    for cat in set(r['cat'] for r in rows):
        left_rows = [r for r in rows if r['cat'] == cat and r['match'] is None]
        left_sig = [e for e in groups.get(cat, []) if e['code'] not in claimed.get(cat, set())]
        if len(left_rows) == 1 and len(left_sig) == 1:
            ratio = difflib.SequenceMatcher(None, norm(left_rows[0]['stub']),
                                            norm(left_sig[0]['name'])).ratio()
            left_rows[0]['match'], left_rows[0]['how'] = left_sig[0], 'residual'
            claimed.setdefault(cat, set()).add(left_sig[0]['code'])
            warn('{}: paired the last row by residual, not by name - '
                 '"{}" <-> "{}" (similarity {:.2f}). Check the two PDFs still agree.'
                 .format(cat, ascii_slug(left_rows[0]['stub'], 40),
                         ascii_slug(left_sig[0]['name'], 55), ratio))
    return rows


#---- Begin_Scraping ----

listnr = 1
spec = regdict[listnr]
print('\nWorking with {} {}'.format(regulatorName, listnr))

page = fetch(spec['URL'], 'page')
page.encoding = page.apparent_encoding or 'utf-8'

listado_url = resolve_pdf(page.text, spec['URL'],
                          'Listado general de las entidades de intermediacion financiera')
siglas_url = resolve_pdf(page.text, spec['URL'],
                         'Siglas de Entidades de Intermediacion Financiera')

listado_path = os.path.join(tempfolder, 'listado.pdf')
siglas_path = os.path.join(tempfolder, 'siglas.pdf')
open(listado_path, 'wb').write(fetch(listado_url, 'listado').content)
open(siglas_path, 'wb').write(fetch(siglas_url, 'siglas').content)

rows, validity = parse_listado(listado_path)
groups, notes = parse_siglas(siglas_path)

# ---- ONE strict acceptance test -------------------------------------------------------
# A byte count or an HTTP 200 proves only that something arrived. What must be true is that
# the PDF parsed into the shape this script depends on: named category blocks whose running
# numbers are complete 1..n. Contiguous numbering is the property that actually catches a
# dropped row or a lost page break, which is the failure mode that matters here.
def acceptance(rows):
    if len(rows) < 40:
        return 'only {} rows parsed out of the Listado PDF'.format(len(rows))
    seen = {}
    for r in rows:
        seen.setdefault(r['cat'], []).append(r['num'])
    for cat, nums in seen.items():
        if sorted(nums) != list(range(1, len(nums) + 1)):
            return 'category {} numbering is not contiguous 1..{}: got {}'.format(
                cat, len(nums), sorted(nums))
    return ''


problem = acceptance(rows)
if problem:
    dump = os.path.join(tempfolder, 'FAILED_listado.pdf')
    if os.path.exists(listado_path):
        os.rename(listado_path, dump)
    raise SystemExit('[FATAL] Listado PDF did not parse into the expected shape: {}\n'
                     '        The PDF has been kept at {} for diagnosis.'.format(problem, dump))

print('\nParsed {} rows from the Listado PDF, list valid at {}'.format(len(rows), validity or '?'))
for _prefix, cat, _label in CATEGORIES:
    got = len([r for r in rows if r['cat'] == cat])
    exp = EXPECTED_2026_04.get(cat)
    flag = '' if got == exp else '   <-- was {} on 2026-09-03'.format(exp)
    print('   {:<40} {:>3}{}'.format(cat, got, flag))
    if got != exp:
        warn('category {} moved from {} to {} rows'.format(cat, exp, got))

sig_total = sum(len(v) for v in groups.values())
print('Parsed {} official names from the Siglas PDF'.format(sig_total))
if sig_total != len(rows):
    warn('Siglas holds {} entities but the Listado holds {} - the join will leave '
         'residuals'.format(sig_total, len(rows)))

rows = join_names(rows, groups)

unmatched = [r for r in rows if r['match'] is None]
if unmatched:
    warn('{} row(s) have no Siglas match, so InternalID_1 is blank for them: {}'
         .format(len(unmatched), [ascii_slug(r['stub'], 30) for r in unmatched]))

print('Sigla join: {} by containment, {} by residual, {} unmatched'.format(
    len([r for r in rows if r['how'] == 'contains']),
    len([r for r in rows if r['how'] == 'residual']),
    len(unmatched)))

#---- Begin_sqldict_fill ----

for r in rows:
    entry = r['match']
    # Name is the Listado name column verbatim, per the ticket owner's instruction
    # (2026-09-03): do not prepend the category from the block header. The Siglas join
    # is kept, but only to supply InternalID_1 - it no longer touches Name.
    name = r['stub']

    # RegulationDate only where a footnote actually states a licence date. Footnotes on
    # this PDF are a mixed bag - some describe a 2014 legal reclassification or a merger -
    # so the phrase is required, not just the presence of a marker.
    regdate = ''
    if entry and entry['ref']:
        note = notes.get(entry['ref'], '')
        n = unicodedata.normalize('NFKD', note.lower())
        n = ''.join(c for c in n if not unicodedata.combining(c))
        if 'cuenta con licencia de funcionamiento' in n:
            regdate = spanish_date(re.sub(r'^a partir del\s*', '', n.split('cuenta con')[0]))

    add_row(
        Name=name,
        InternalID_1=entry['code'] if entry else '',
        InternalID_1_type='ASFI sigla' if entry else '',
        CoType=CATEGORY_LABEL.get(r['cat'], r['cat']),
        License_Type='Licencia de Funcionamiento',
        City=r['city'],
        Cntry=REGCTRY,
        RegulationType='Regulated',
        RegulationDate=regdate,
        RegCtry=REGCTRY,
        RegCode=REGCODE,
        ListCode=str(listnr),
        ListLabel=spec['ListLabel'],
        Typology=spec['ListName'],
        ListLanguage='ES',
        ListValidityDate=validity,
        ListName=spec['ListName'],
        ListProcessDate=processdate,
    )

#---- Begin_writer and save df to excel ----

os.chdir(scriptfolder)
df = pd.DataFrame(sqldict)
df = df[df['Name'] != '']

assert list(df.columns) == SQL_KEYS, 'schema drift: columns do not match the fixed 43-key sqldict'
print('\nSchema check OK: {} columns, in template order'.format(len(df.columns)))

# Template fields have a fixed shape: the three tokens of the folder name '<CC> <AGENCY>
# <listnr>'. ListCode is the bare ticket number, NOT 'BO ASFI 1'. A row-count QA cannot
# catch this, so it is asserted.
assert set(df['RegCtry']) == {REGCTRY}, 'RegCtry must be {!r}, got {}'.format(REGCTRY, set(df['RegCtry']))
assert set(df['RegCode']) == {REGCODE}, 'RegCode must be {!r}, got {}'.format(REGCODE, set(df['RegCode']))
assert set(df['ListCode']) == {'1'}, 'ListCode must be the bare ListNr, got {}'.format(set(df['ListCode']))
assert set(df['ListLabel']) <= {'1', '2', '3', '4'}, 'ListLabel out of range: {}'.format(set(df['ListLabel']))
assert (df['ListProcessDate'] == processdate).all(), 'ListProcessDate not stamped on every row'
assert (df['RegulationType'] == 'Regulated').all(), 'RegulationType missing on some rows'
print('Template fields OK: RegCtry={} RegCode={} ListCode={} ListLabel={}'.format(
    REGCTRY, REGCODE, ','.join(sorted(set(df['ListCode']))), ','.join(sorted(set(df['ListLabel'])))))

# A row count alone does not prove the Name column holds names - a sibling regulator once
# shipped 997 reconciled rows with 'Yes'/'No' in Name. Assert the CONTENT separately.
_bad = df[df['Name'].str.strip().isin(['', 'Yes', 'No', 'Si', 'N/A', '-', 'Name',
                                       'Nombre', 'Denominacion', 'Entidad', 'ESTADO'])]
assert _bad.empty, 'Name column holds non-name values in {} rows'.format(len(_bad))
_short = df[df['Name'].str.len() < 5]
assert _short.empty, 'implausibly short Name in {} rows: {}'.format(
    len(_short), [ascii_slug(v, 20) for v in _short['Name']])
print('Name content check OK: {} distinct names over {} rows, shortest {} chars'.format(
    df['Name'].nunique(), len(df), int(df['Name'].str.len().min())))

# Spanish source: a decode fault anywhere in request -> parse -> Excel shows up as mojibake.
# Checked on the frame rather than trusted, because the fix is a decode fix, not a replace.
MOJIBAKE = ['Ã©', 'â€™', 'Â ', 'Ã±', 'ï¿½']
for col in ('Name', 'City'):
    for bad in MOJIBAKE:
        hit = df[df[col].str.contains(re.escape(bad), regex=True, na=False)]
        assert hit.empty, 'mojibake {!r} in {} on {} rows'.format(bad, col, len(hit))
    hit = df[df[col].str.contains(r'\?{3,}', regex=True, na=False)]
    assert hit.empty, 'run of question marks in {} on {} rows'.format(col, len(hit))
_accented = int(df['Name'].str.contains(r'[áéíóúñÁÉÍÓÚÑ]', regex=True).sum())
print('Encoding check OK: no mojibake in Name/City; {} names still carry Spanish accents'
      .format(_accented))

for _c in TEXT_COLS:
    df[_c] = df[_c].apply(lambda v: '' if v is None or (isinstance(v, float) and pd.isna(v))
                          else str(v).strip())

outpath = os.path.join(scriptfolder, filename)
df.to_excel(outpath, sheet_name='SQL Ready', index=False)

# Read the workbook back and prove Excel did not mangle anything on the way out.
_chk = pd.read_excel(outpath, sheet_name='SQL Ready', dtype=str, keep_default_na=False)
assert len(_chk) == len(df), 'round-trip row count changed: {} -> {}'.format(len(df), len(_chk))
assert list(_chk.columns) == SQL_KEYS, 'round-trip lost or reordered columns'
for _c in TEXT_COLS:
    _b = _chk[_c].astype(str).str.contains(r'[eE]\+\d|\.0$', regex=True, na=False)
    assert not _b.any(), 'Excel coerced {} to float in {} rows'.format(_c, int(_b.sum()))
assert list(_chk['InternalID_1']) == list(df['InternalID_1']), 'InternalID_1 changed across the round-trip'
assert list(_chk['Name']) == list(df['Name']), 'Name changed across the round-trip'
print('Round-trip check OK: {} rows re-read, {} columns, IDs and names text-safe'
      .format(len(_chk), len(_chk.columns)))

#---- Begin_run_summary ----

print('\n{:<12} {:<52} {:>5}'.format('ListCode', 'ListName', 'rows'))
print('{:<12} {:<52} {:>5}'.format('1', ascii_slug(spec['ListName'], 52), len(df)))
print('{:<65} {:>5}'.format('TOTAL', len(df)))
print('site rows on the 04_2026 Listado PDF: {} -> {}'.format(
    EXPECTED_TOTAL, 'MATCH' if len(df) == EXPECTED_TOTAL else 'DRIFT (see warnings)'))

print('\nField completeness (non-empty / {} rows):'.format(len(df)))
for _c in ('Name', 'InternalID_1', 'City', 'CoType', 'RegulationDate',
           'Address_1', 'Phone', 'Website'):
    _n = int((df[_c].astype(str).str.strip() != '').sum())
    print('   {:<16} {:>3}  {:>5.1f}%'.format(_c, _n, 100.0 * _n / len(df)))

if warnings_seen:
    print('\n{} warning(s) raised during the run:'.format(len(warnings_seen)))
    for w in warnings_seen:
        print('  - {}'.format(w))
else:
    print('\nNo warnings raised.')

print('\nSaved {} rows to {}'.format(len(df), outpath))
