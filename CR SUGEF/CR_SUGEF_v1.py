#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CR SUGEF -- Superintendencia General de Entidades Financieras (Costa Rica).

Jira: DECD-6822

List 1 "Entidades Supervisadas":
    https://www.sugef.fi.cr/entidades_supervisadas/lista_entidades_supervisadas_por_SUGEF.aspx

The index page publishes ~350 historical PDFs.  Each PDF is linked from several
anchors; one of them carries the publication date as dd/mm/yyyy text.  The file
name is <YEAR>_<SEQUENCE>.pdf -- the sequence is NOT a month (2024_09.pdf is the
05/11/2024 list), so the file name must never be used to rank the editions.
This script parses the index, reads the dd/mm/yyyy anchor text for every PDF and
downloads the edition with the newest date.  Nothing is hard-coded.

Only "item 1" of the PDF is collected: section

    1. ENTIDADES SUPERVISADAS POR LA SUGEF ACTUALIZADA AL <date>

with its subsections 1.1 .. 1.n.  Extraction stops at the next top-level
numbered heading (in the 03/07/2026 edition that is
"2. CONGLOMERADOS Y GRUPOS FINANCIEROS ACTIVOS INSCRITOS EN LA SUGEF"),
detected structurally -- bold font at the section-heading indent -- so no page
number, line count or heading wording is hard-coded.
"""

# ------------------------------------------------ Begin_Librairie ----------------------------------------
import os
import re
import sys
import datetime
import unicodedata
from urllib.parse import urljoin

import requests
import pandas as pd
import pdfplumber
from bs4 import BeautifulSoup

requests.packages.urllib3.disable_warnings()  # corporate TLS proxy -> verify=False


# ------------------------------------------------ Begin_fileName ----------------------------------------
regulatorName = 'CR SUGEF'  # Superintendencia General de Entidades Financieras

print("Running {} Web Scraping Tool v.1.0".format(regulatorName))

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":", ".")[:-7])

# ------ At first we will define the workspace path -----
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))  # production environment (.py)
except NameError:
    scriptfolder = os.getcwd()  # notebook environment
os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder')  # the PDF is downloaded here before parsing
if os.path.exists(tempfolder):
    for rem in os.listdir(tempfolder):
        try:
            os.remove(os.path.join(tempfolder, rem))
        except OSError:
            pass
else:
    os.mkdir(tempfolder)


# ------------------------------------------------ Begin_Variable ----------------------------------------
REGCTRY = 'CR'
REGCODE = 'SUGEF'

# ListNr -> (ListName, index URL, ListLabel)
# ListLabel 1 = bank list.  Section 1 of the PDF is exclusively deposit-taking /
# credit institutions (state banks, special-law banks, private banks, non-bank
# finance companies, savings & credit co-operatives, mutual savings & loan
# associations).  No insurer appears in it -- insurers sit with SUGESE.
LISTS = {
    1: ('Entidades Supervisadas',
        'https://www.sugef.fi.cr/entidades_supervisadas/lista_entidades_supervisadas_por_SUGEF.aspx',
        1),
}

HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
    'Accept-Language': 'es-CR,es;q=0.9,en;q=0.8',
}

# Only PDFs under this path segment are editions of the supervised-entity list.
PDF_PATH_MARKER = 'entidades_fiscalizadas'

# Keep the name exactly as printed, including a trailing "(antes <old name>)"
# former-name clause?  False -> the clause is dropped so `Name` holds only the
# current legal name (better for downstream entity matching).
KEEP_FORMER_NAME = False

# Spanish subsection heading -> English company type.  Falls back to the printed
# Spanish heading when SUGEF adds a category, so a new subsection can never
# break the run (hard-coded enumerations rot).
COTYPE_MAP = {
    'BANCOS COMERCIALES DEL ESTADO': 'State Commercial Bank',
    'BANCOS CREADOS POR LEYES ESPECIALES': 'Bank Created by Special Law',
    'BANCOS PRIVADOS': 'Private Bank',
    'EMPRESAS FINANCIERAS NO BANCARIAS': 'Non-Bank Financial Company',
    'ORGANIZACIONES COOPERATIVAS DE AHORRO Y CREDITO': 'Savings and Credit Cooperative',
    'ASOCIACIONES MUTUALISTAS DE AHORRO Y PRESTAMO': 'Mutual Savings and Loan Association',
    'OTRAS ENTIDADES FINANCIERAS': 'Other Financial Entity',
}

MESES = {
    'ENERO': 1, 'FEBRERO': 2, 'MARZO': 3, 'ABRIL': 4, 'MAYO': 5, 'JUNIO': 6,
    'JULIO': 7, 'AGOSTO': 8, 'SETIEMBRE': 9, 'SEPTIEMBRE': 9, 'OCTUBRE': 10,
    'NOVIEMBRE': 11, 'DICIEMBRE': 12,
}

# --- regexes -------------------------------------------------------------
RE_DDMMYYYY = re.compile(r'\b(\d{2})/(\d{2})/(\d{4})\b')
RE_CEDULA = re.compile(r'\d-\d{3}-\d{6}')          # cedula juridica, e.g. 3-101-012009
RE_TOPHEAD = re.compile(r'^(\d+)\.\s+(.+)$')        # "2. CONGLOMERADOS ..."
RE_SUBHEAD = re.compile(r'^(\d+)\.(\d+)\s+(.+)$')   # "1.3 BANCOS PRIVADOS ..."
RE_NUMSTART = re.compile(r'^(\d+)\.\s*(.*)$')       # "7. Banco Improsa S.A."
RE_TOTAL = re.compile(r'\(\s*Total\s*:\s*(\d+)\s*\)', re.I)
RE_FOOTER = re.compile(r'^(Página\s+\d+\s+de\s+\d+|Uso\s+Interno)$', re.I)
RE_ANTES = re.compile(r'\s*\((?:antes|anteriormente)\b[^()]*(?:\([^()]*\)[^()]*)*\)\s*$', re.I)

MIN_FONT_SIZE = 8.0   # below this are footnote markers such as "NG-1/", "DC-3"
COL_TOLERANCE = 25.0  # pt; a wrapped name must start in the same column

# ------ the sqldict structure is FIXED - DO NOT ADD / REMOVE / RENAME KEYS ------
sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}


# ------------------------------------------------ Begin_Function ----------------------------------------
def clean(txt):
    """Normalise whitespace / unicode; always return a str."""
    if txt is None:
        return ''
    txt = unicodedata.normalize('NFKC', str(txt))
    txt = txt.replace('­', '').replace('​', '')
    return re.sub(r'\s+', ' ', txt).strip()


def deaccent(txt):
    """Upper-case, accent-stripped key used to look up COTYPE_MAP."""
    txt = unicodedata.normalize('NFD', clean(txt).upper())
    return ''.join(c for c in txt if unicodedata.category(c) != 'Mn')


def bourange_same_length_array(sqldict):
    """Pad every column to the longest one so the columns can never drift."""
    maxlen = max(len(v) for v in sqldict.values())
    for key in sqldict:
        if len(sqldict[key]) != maxlen:
            sqldict[key].extend([''] * (maxlen - len(sqldict[key])))
    return sqldict


def add_row(listcode, **kw):
    """Append ONE entity, filling every fixed field, then pad all 42 columns."""
    listname, _url, listlabel = LISTS[listcode]
    sqldict['Name'].append(clean(kw.get('name')))
    sqldict['InternalID_1'].append(clean(kw.get('internalid1')))
    sqldict['InternalID_1_type'].append(clean(kw.get('internalid1_type')) if kw.get('internalid1') else '')
    sqldict['CoType'].append(clean(kw.get('cotype')))
    sqldict['License_Type'].append(clean(kw.get('license_type')))
    sqldict['Cntry'].append('CR')
    sqldict['RegulationType'].append('Regulated')
    sqldict['RegCtry'].append(REGCTRY)
    sqldict['RegCode'].append(REGCODE)
    sqldict['ListCode'].append(str(listcode))
    sqldict['ListName'].append(listname)
    sqldict['ListLabel'].append(listlabel)
    sqldict['ListLanguage'].append('ES')
    sqldict['ListValidityDate'].append(clean(kw.get('validitydate')))
    sqldict['ListProcessDate'].append(processdate)
    bourange_same_length_array(sqldict)
    return sqldict


# ------ index page: enumerate every published edition, newest first ------
def list_editions(index_url):
    """Return [(date, absolute_url), ...] sorted newest first.

    Every edition is linked from several anchors ("Lista de entidades", the
    year, "Pdf" and the dd/mm/yyyy publication date).  We therefore gather the
    date from *any* anchor that points at a given PDF.
    """
    r = requests.get(index_url, headers=HEADERS, verify=False, timeout=120)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')

    dates = {}
    for a in soup.find_all('a', href=True):
        href = a['href']
        if not href.lower().split('?')[0].endswith('.pdf'):
            continue
        if PDF_PATH_MARKER not in href.lower():
            continue
        m = RE_DDMMYYYY.search(clean(a.get_text(' ', strip=True)))
        if not m:
            continue
        try:
            d = datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            continue
        url = urljoin(index_url, href)
        if url not in dates or d > dates[url]:
            dates[url] = d

    return sorted(dates.items(), key=lambda kv: kv[1], reverse=True)


def download_pdf(url, dest):
    r = requests.get(url, headers=HEADERS, verify=False, timeout=180)
    r.raise_for_status()
    ctype = (r.headers.get('Content-Type') or '').lower()
    if not r.content.startswith(b'%PDF'):
        raise RuntimeError('{} did not return a PDF (Content-Type={}, {} bytes)'
                           .format(url, ctype, len(r.content)))
    with open(dest, 'wb') as f:
        f.write(r.content)
    return len(r.content)


# ------ PDF -> layout-aware lines ------
def pdf_lines(path):
    """Flatten the PDF into lines carrying x0 / bold, footnote markers removed."""
    out = []
    with pdfplumber.open(path) as pdf:
        for pageno, page in enumerate(pdf.pages, 1):
            words = [w for w in page.extract_words(extra_attrs=['fontname', 'size'])
                     if w['size'] >= MIN_FONT_SIZE]
            rows = {}
            for w in words:
                rows.setdefault(round(w['top'] / 3.0), []).append(w)
            for key in sorted(rows):
                grp = sorted(rows[key], key=lambda w: w['x0'])
                text = clean(' '.join(w['text'] for w in grp))
                if not text or RE_FOOTER.match(text):
                    continue
                out.append({
                    'text': text,
                    'x0': min(w['x0'] for w in grp),
                    'bold': any('Bold' in w['fontname'] for w in grp),
                    'page': pageno,
                })
    return out


def is_top_heading(line):
    """A bold, top-level numbered heading such as '2. CONGLOMERADOS ...'."""
    return bool(line['bold']
                and RE_TOPHEAD.match(line['text'])
                and not RE_SUBHEAD.match(line['text']))


def slice_item1(lines):
    """Return (section-1 lines, section-1 heading, heading that ended it).

    Start = the bold top-level heading numbered 1.
    End   = the NEXT bold top-level heading at the SAME left indent whose
            number is not 1.  Entity rows are numbered too ('2. Banco ...'),
            but they are neither bold nor at the section indent, so they can
            never be mistaken for the section-2 heading.
    """
    start = indent = None
    for i, ln in enumerate(lines):
        if not is_top_heading(ln):
            continue
        num = int(RE_TOPHEAD.match(ln['text']).group(1))
        if start is None:
            if num == 1:
                start, indent = i, ln['x0']
            continue
        if num != 1 and ln['x0'] <= indent + 5:
            return lines[start + 1:i], lines[start]['text'], ln['text']
    if start is None:
        raise RuntimeError("Could not locate the top-level heading '1. ...' in the PDF")
    return lines[start + 1:], lines[start]['text'], None


def validity_from_heading(heading):
    """'... ACTUALIZADA AL 03 DE JULIO DE 2026' -> '2026-07-03' (or '')."""
    m = re.search(r'(\d{1,2})\s+DE\s+([A-ZÁÉÍÓÚÑ]+)\s+DE\s+(\d{4})',
                  deaccent(heading))
    if not m:
        return ''
    mon = MESES.get(deaccent(m.group(2)))
    if not mon:
        return ''
    try:
        return datetime.date(int(m.group(3)), mon, int(m.group(1))).isoformat()
    except ValueError:
        return ''


def parse_item1(lines):
    """Parse section-1 lines into entities + the per-subsection declared totals.

    A line opens a NEW entity only when it starts with the next expected
    sequence number inside the current subsection; anything else at the same
    column is a wrapped continuation of the previous name.
    """
    entities, declared = [], []
    subsection = ''
    expected = 0
    col_x0 = None

    for ln in lines:
        text = ln['text']

        sub = RE_SUBHEAD.match(text)
        if ln['bold'] and sub:
            subsection = clean(RE_TOTAL.sub('', sub.group(3)))
            tot = RE_TOTAL.search(text)
            declared.append((subsection, int(tot.group(1)) if tot else None))
            expected, col_x0 = 0, None
            continue

        if not subsection:
            continue  # anything before subsection 1.1 (blurbs, notes)

        num = RE_NUMSTART.match(text)
        if num and int(num.group(1)) == expected + 1:
            expected += 1
            col_x0 = ln['x0'] if col_x0 is None else col_x0
            body = num.group(2)
            ced = RE_CEDULA.search(body)
            entities.append({
                'subsection': subsection,
                'seq': expected,
                'name': clean(RE_CEDULA.sub('', body)),
                'cedula': ced.group(0) if ced else '',
                'page': ln['page'],
            })
            continue

        # wrapped continuation: same column, not bold, an entity is open
        if entities and not ln['bold'] and col_x0 is not None \
                and abs(ln['x0'] - col_x0) <= COL_TOLERANCE:
            body = text
            if not entities[-1]['cedula']:
                ced = RE_CEDULA.search(body)
                if ced:
                    entities[-1]['cedula'] = ced.group(0)
            entities[-1]['name'] = clean(entities[-1]['name'] + ' ' + RE_CEDULA.sub('', body))
        else:
            print('   [skip] unmatched line p{}: {!r}'.format(ln['page'], text[:70]))

    return entities, declared


# ------------------------------------------------ Begin_MainLoop ----------------------------------------
listcode = 1
listname, index_url, listlabel = LISTS[listcode]

print('\n[1] Reading index page: {}'.format(index_url))
editions = list_editions(index_url)
if not editions:
    sys.exit('No supervised-entity PDFs found on the index page - the layout changed.')

print('    {} published editions found. Five most recent:'.format(len(editions)))
for url, d in editions[:5]:
    print('      {}  {}'.format(d.isoformat(), url))

pdf_url, pdf_date = editions[0]
print('\n[2] SELECTED most recent edition: {}  ->  {}'.format(pdf_date.isoformat(), pdf_url))

pdf_path = os.path.join(tempfolder, os.path.basename(pdf_url.split('?')[0]))
nbytes = download_pdf(pdf_url, pdf_path)
print('    Downloaded {} bytes -> {}'.format(nbytes, os.path.basename(pdf_path)))

print('\n[3] Parsing item 1 of the PDF')
lines = pdf_lines(pdf_path)
item1, head1, head_next = slice_item1(lines)
print('    Section 1 heading : {}'.format(head1))
print('    Stopped at        : {}'.format(head_next if head_next else '(end of document)'))

validitydate = validity_from_heading(head1) or pdf_date.isoformat()
print('    ListValidityDate  : {}'.format(validitydate))

entities, declared = parse_item1(item1)

print('\n[4] Cross-check parsed vs the "(Total: n)" printed in each subsection')
declared_sum = 0
ok = True
for sub, tot in declared:
    got = sum(1 for e in entities if e['subsection'] == sub)
    declared_sum += tot or 0
    flag = 'OK' if tot == got else '<<< MISMATCH'
    if tot != got:
        ok = False
    print('    {:<52} declared={} parsed={} {}'.format(sub[:52], tot, got, flag))
print('    TOTAL declared={} parsed={} {}'.format(declared_sum, len(entities),
                                                  'OK' if ok and declared_sum == len(entities) else '<<< CHECK'))
if not ok or declared_sum != len(entities):
    print('\n    ' + '!' * 72)
    print('    !! WARNING: the row count does NOT match the totals printed in the PDF.')
    print('    !! SUGEF most likely changed the layout of the list. Editions up to')
    print('    !! 2023_09 used a two-column bullet layout with no cedula, which this')
    print('    !! parser does not support. Inspect the PDF before shipping the output.')
    print('    ' + '!' * 72)

print('\n[5] Building rows')
for e in entities:
    name = e['name']
    if not KEEP_FORMER_NAME:
        name = clean(RE_ANTES.sub('', name)) or e['name']
    add_row(listcode,
            name=name,
            internalid1=e['cedula'],
            internalid1_type='Cedula Juridica',
            cotype=COTYPE_MAP.get(deaccent(e['subsection']), clean(e['subsection']).title()),
            license_type=clean(e['subsection']).title(),
            validitydate=validitydate)


# ------------------------------------------------ Begin_writer and save df to excel ----------------------------------------
os.chdir(scriptfolder)
df = pd.DataFrame(sqldict)

df = df[df['Name'] != '']

df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)

print('\nSaved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))
print(df.groupby('CoType').size().to_string())
