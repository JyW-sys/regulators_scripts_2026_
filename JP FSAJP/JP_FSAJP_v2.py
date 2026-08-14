"""
JP FSAJP -- Financial Services Agency of Japan
List of licensed / registered financial institutions (12 lists)

Jira: DECD-6758
Index page (single source for every list):
    https://www.fsa.go.jp/en/regulated/licensed/index.html


v2 changes vs v1 (JP_FSAJP_v1.ipynb)
------------------------------------
1. The 12 workbook URLs are no longer hard-coded.  v1 pinned filenames such as
   ".../city.xls"; the FSA has since migrated four of them from .xls to .xlsx, so
   city.xls / s_banks.xls / ins_life.xls / ins_holding.xls all return HTTP 404.
   v2 reads the index page and resolves each list to its live Excel link by
   matching the <li> text, so a future .xls -> .xlsx (or a renamed file) is picked
   up automatically.  A match below MIN_MATCH aborts loudly instead of scraping
   the wrong file.

2. Selenium is gone.  v1 downloaded through a headless Chrome profile and then
   read whatever happened to be sitting in tempfolder.  When the .xls 404'd it
   retried with "+ 'x'" but did NOT wait for that second download, so os.listdir
   returned Chrome's in-progress temp file and the run died on list 1 with
      FileNotFoundError: ... tempfolder/.com.google.Chrome.Uxk3B5
   All 12 workbooks are plain static files that answer a normal GET, so v2 uses
   requests and keeps the bytes in memory -- no download race, no browser.

3. Header detection is label-driven instead of positional.  v1 looked for "the
   first row with no NaN" and then sliced fixed column ranges (data.columns[2:-5]
   for list 8, [1:] for others).  Those slices break whenever the FSA adds or
   reorders a column.  v2 finds the header row by recognising the column labels
   themselves and maps each field by label, so column order no longer matters.

4. Repeated header blocks and section labels are dropped.  s_banks.xlsx carries
   two header blocks ("Federation of Credit Associations" and "Credit
   Associations"); v1's JCN-length filter hid this by accident.

5. Fixed: list 9 wrote the telephone column into 'Name - Mother Company'
   (both read data.columns[3] after the slice).  The affiliation column is now
   mapped by label.

6. Filled in the columns v1 left empty: Typology, ListLanguage, ListLabel, and
   License_Type (list 8 marks five business categories with a circle glyph;
   v1 sliced them away).  Zip is now taken with a postal-code regex -- v1's
   "last space-separated token if the address starts with a digit" missed every
   address beginning with a building name and every one with trailing spaces.

7. Housekeeping: scriptfolder is derived from __file__ instead of the hard-coded
   C:\\Users\\wuj1\\... path; the non-schema 'Check' column is gone; the output
   goes to the regulator folder; ExcelWriter.save() (removed in pandas 2.x) is
   no longer called.

Written for Python 3.8 on the Windows production box: no f-strings, no walrus,
and the source is pure ASCII.
"""

# ------------------------------------------------ Begin_Librairie ---------------------------------------

import os
import re
import io
import sys
import datetime

import requests
import urllib3
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))   # production environment (.py)
except NameError:
    scriptfolder = os.getcwd()                                  # notebook environment

os.chdir(scriptfolder)

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = 'JP FSAJP SQL Ready ' + now.strftime('%Y-%m-%d %H.%M.%S') + '.xlsx'

INDEX_URL = 'https://www.fsa.go.jp/en/regulated/licensed/index.html'

HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'),
    'Accept-Language': 'en-US,en;q=0.9',
}

# A resolved link scoring below this against its ticket name is treated as "the
# index page changed shape", not as a match.  Measured 2026-08-13: the worst
# genuine match scores 0.50 (Credit Associations -> s_banks.xlsx).
MIN_MATCH = 0.35

# The circle glyph the FSA uses to tick a business category in fibo.xlsx.
MARK = u'\u25cb'


# ------------------------------------------------ Begin_Fouction ----------------------------------------

def bourange_same_length_array(sqldict):

    maxlen = len(sqldict['ListProcessDate'])

    for key, val in sqldict.items():

        if len(sqldict[key]) != maxlen:

            empty = []

            total_empty = maxlen - len(sqldict[key])

            for i in range(total_empty):

                empty.append('')

            sqldict[key] = sqldict[key] + empty

    return sqldict


def raw(value):
    """Collapse whitespace; treat NaN/None as empty.  Keeps '-' as-is."""
    text = re.sub(r'\s+', ' ', str(value)).strip()
    if text.lower() in ('nan', 'none', 'nat'):
        return ''
    return text


# The sheets fill a "no value" cell with a dash, and not always the same one:
# ASCII '-', U+2015 HORIZONTAL BAR and U+FF0D FULLWIDTH HYPHEN-MINUS all appear
# in the JCN column of fibo.xlsx / fiisp.xlsx.
DASH_ONLY_RE = re.compile(r'^[-\u2010-\u2015\u2212\uff0d\s]+$')


def clean(value):
    """raw() plus the FSA's dash placeholders folded to empty."""
    text = raw(value)
    if not text or DASH_ONLY_RE.match(text):
        return ''
    return text


def jcn(value):
    """Japan Corporate Number: 13 digits.  pandas reads it as a float."""
    text = clean(value)
    if not text:
        return ''
    match = re.match(r'^(\d+)\.0+$', text)
    if match:
        text = match.group(1)
    return text


ZIP_RE = re.compile(r'(\d{3}\s*-\s*\d{4})\s*$')


def split_address(address):
    """Japanese addresses on these sheets end with the postal code, e.g.
    '1-5-5, Ohtemachi, Chiyoda-ku, Tokyo 100-8176'.  Return (address, zip, city)."""
    address = clean(address)
    if not address:
        return '', '', ''

    zipcode = ''
    match = ZIP_RE.search(address)
    if match:
        zipcode = re.sub(r'\s+', '', match.group(1))
        address = address[:match.start()].strip().rstrip(',').strip()

    city = ''
    if address:
        tail = address.split(',')[-1].strip()
        # Only keep it when it looks like a place name, not a street number.
        if tail and not re.search(r'\d', tail) and len(tail) <= 40:
            city = tail

    return address, zipcode, city


# ---- column recognition ------------------------------------------------------
#
# Each entry is (field, regex tested against the lower-cased header cell).
# Order matters: the first match wins for a given cell.

COLUMN_PATTERNS = [
    ('NameJP',  r'name\s*\(\s*japanese\s*\)'),
    ('Name',    r'^(the\s+)?name\s*\(\s*english\s*\)$'
                r'|^(the\s+)?name\s+of\s+(a|an)\s+(financial\s+institution|institution|trust\s+company)$'
                r'|^name\s+of\s+company$'
                r'|^(the\s+)?name$'),
    ('JCN',     r'^jcn$'),
    ('Address', r'^address$'),
    ('Phone',   r'^telephone$|^phone\s*(\(\s*main\s*\))?$'),
    ('Zip',     r'^postal\s*code$'),
    ('Cntry',   r'^country\s*/\s*area$|^nationality$'),
    ('Pref',    r'^prefecture$'),
    ('CoType',  r'^business\s+category$'),
    ('RegNo',   r'^registration\s+numbers?$'),
    ('Mother',  r'^affiliation\s+financial'),
    ('Juris',   r'^jurisdiction$'),
    ('Auth',    r'^supervisory\s+authority$'),
]

# Header cells that are not a mapped field but still mark a licence category
# in fibo.xlsx -- these become License_Type when the cell below carries MARK.
LICENCE_RE = re.compile(r'business$|business\b', re.I)


def classify(cell):
    text = raw(cell).lower()
    if not text:
        return None
    for field, pattern in COLUMN_PATTERNS:
        if re.search(pattern, text):
            return field
    return None


def find_header(frame):
    """Return (row_index, {field: column_index}) for the first row that names a
    Name column plus at least one of JCN / Address / Telephone."""
    limit = min(15, len(frame))
    for row in range(limit):
        hits = {}
        for col in range(frame.shape[1]):
            field = classify(frame.iat[row, col])
            if field and field not in hits:
                hits[field] = col
        if 'Name' in hits and (set(hits) & set(['JCN', 'Address', 'Phone'])):
            return row, hits
    return None, {}


def licence_columns(frame, header_row, mapped):
    """Columns whose header names a business category (fibo.xlsx only)."""
    taken = set(mapped.values())
    found = []
    for col in range(frame.shape[1]):
        if col in taken:
            continue
        label = raw(frame.iat[header_row, col])
        if label and LICENCE_RE.search(label):
            found.append((col, re.sub(r'\s+', ' ', label)))
    return found


TOTAL_CELL_RE = re.compile(r'^total\s+\d+\s+\w+$', re.I)

DECLARED_RE = re.compile(
    r'total\s+(\d+)\s+(?:banks?|companies)'
    r'|(\d+)\s+companies'
    r'|companies\s*[::]\s*(\d+)'
    r'|offices\s*[::]?\s*(\d+)', re.I)


def declared_total(frame, header_row):
    """The count the sheet states about itself, e.g. 'Total 35 banks'.
    Used as a free QA baseline; returns None when the sheet declares nothing."""
    total = None
    for row in range(min(header_row + 1, len(frame))):
        for col in range(frame.shape[1]):
            match = DECLARED_RE.search(raw(frame.iat[row, col]))
            if match:
                for group in match.groups():
                    if group is not None:
                        value = int(group)
                        total = value if total is None else total + value
    return total


def parse_sheet(frame):
    """Return (list_of_row_dicts, declared_total, header_row, mapped)."""
    header_row, mapped = find_header(frame)
    if header_row is None:
        return [], None, None, {}

    name_col = mapped['Name']
    licences = licence_columns(frame, header_row, mapped)

    # Country/Area, Nationality and Business category are merged cells: the FSA
    # writes the value once against the first entity of the group and leaves the
    # rest blank.  Carry each one down.  The Business category column also holds
    # running annotations ("Total 4 banks") that are not a category -- those must
    # neither be kept nor allowed to end the group.
    for field in ('Cntry', 'CoType'):
        if field not in mapped:
            continue
        col = mapped[field]
        carried = ''
        for row in range(header_row + 1, len(frame)):
            value = clean(frame.iat[row, col])
            if TOTAL_CELL_RE.match(value):
                frame.iat[row, col] = carried
            elif value:
                carried = value
            else:
                frame.iat[row, col] = carried

    rows = []
    for row in range(header_row + 1, len(frame)):
        name = clean(frame.iat[row, name_col])
        if not name:
            continue
        if classify(name):
            continue                     # a repeated header block
        others = [c for c in range(frame.shape[1]) if c != name_col]
        if not any(raw(frame.iat[row, c]) for c in others):
            continue                     # a section label or a footnote

        record = {}
        for field, col in mapped.items():
            record[field] = clean(frame.iat[row, col])
        record['Name'] = name
        if 'JCN' in record:
            record['JCN'] = jcn(frame.iat[row, mapped['JCN']])

        held = []
        for col, label in licences:
            if MARK in raw(frame.iat[row, col]):
                held.append(label)
        record['Licences'] = '/'.join(held)

        rows.append(record)

    return rows, declared_total(frame, header_row), header_row, mapped


# ---- the 12 lists ------------------------------------------------------------
#
# ListNr / ListName exactly as DECD-6758 states them, plus the ListLabel rule
# from CLAUDE.md (1 = bank, 2 = insurance, 3 = bank & insurance, 4 = everything
# else).  'match' is the text matched against the index page's <li> entries.

LISTS = [
    ('1',  'City Banks and Trust Banks',                           '1', 'City Banks and Trust Banks'),
    ('2',  'Regional Banks',                                       '1', 'Regional Banks'),
    ('3',  'Bank Holding Companies',                               '1', 'Bank Holding Companies'),
    ('4',  'Credit Associations',                                  '1', 'Credit Associations'),
    ('5',  'Keito Financial Institutions',                         '1', 'Keito Financial Institutions'),
    ('6',  'Financial Institutions engaged in Trust Business',     '1', 'Financial Institutions engaged in Trust Business'),
    ('8',  'Financial Instruments Business Operators',             '4', 'Financial Instruments Business Operators'),
    ('9',  'Financial Instruments Intermediary Service Providers', '4', 'Financial Instruments Intermediary Service Providers'),
    ('11', 'Life Insurance Companies',                             '2', 'Life Insurance Companies'),
    ('12', 'Non-Life Insurance Companies',                         '2', 'Non-Life Insurance Companies'),
    ('13', 'Insurance Holding Companies',                          '2', 'Insurance Holding Companies'),
    ('14', 'Trust Companies',                                      '4', 'Trust Companies'),
]

STOPWORDS = set(['and', 'of', 'the', 'in', 'a', 'for', 'which', 'engage', 'engaged'])


def tokens(text):
    words = re.findall(r'[a-z]+', text.lower())
    return set(w for w in words if w not in STOPWORDS)


def resolve_links(session):
    """Map every ticket list name to its live Excel URL on the index page."""
    response = session.get(INDEX_URL, headers=HEADERS, verify=False, timeout=60)
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    soup = BeautifulSoup(response.text, 'html.parser')

    candidates = []
    for item in soup.find_all('li'):
        link = None
        for anchor in item.find_all('a', href=True):
            if re.search(r'\.xlsx?$', anchor['href'], re.I):
                link = anchor
        if link is None:
            continue
        label = re.sub(r'\s+', ' ', item.get_text(' ', strip=True))
        label = re.sub(r'\(\s*PDF[^)]*\)|\(\s*Excel[^)]*\)|PDF|Excel', ' ', label)
        candidates.append((label.strip(), requests.compat.urljoin(INDEX_URL, link['href'])))

    print('[INFO] -- index page offers {} Excel link(s) --'.format(len(candidates)))

    resolved = {}
    for listnr, listname, listlabel, match_text in LISTS:
        wanted = tokens(match_text)
        best_url, best_score, best_label = None, 0.0, ''
        for label, url in candidates:
            have = tokens(label)
            if not have:
                continue
            score = len(wanted & have) / float(len(wanted | have))
            if score > best_score:
                best_url, best_score, best_label = url, score, label
        if best_url is None or best_score < MIN_MATCH:
            raise RuntimeError(
                'could not find an Excel link for list {} ({!r}) on {} -- best was '
                '{!r} at {:.2f}.  The index page has changed; check it by hand.'.format(
                    listnr, listname, INDEX_URL, best_label, best_score))
        resolved[listnr] = best_url
        print('  [{}] {:<52.52} -> {:<24} (match {:.2f})'.format(
            listnr, listname, best_url.rsplit('/', 1)[-1], best_score))
    return resolved


# ------------------------------------------------ Begin_Dictionnaire ------------------------------------

sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}


# ------------------------------------------------ Begin_Main --------------------------------------------

session = requests.Session()

print('[INFO] -- resolving the 12 workbook links from the index page --')
links = resolve_links(session)
print('')

counts = []
mismatches = []

for listnr, listname, listlabel, match_text in LISTS:

    print('[Start New Reg] -- Working with list JP FSAJP {} -- {}'.format(listnr, listname))

    url = links[listnr]
    response = session.get(url, headers=HEADERS, verify=False, timeout=180)
    response.raise_for_status()
    print('  {} ({} bytes)'.format(url, len(response.content)))

    book = pd.ExcelFile(io.BytesIO(response.content))
    print('  sheets: {}'.format(len(book.sheet_names)))

    written = 0

    for sheet in book.sheet_names:

        frame = pd.read_excel(book, sheet_name=sheet, header=None)
        rows, declared, header_row, mapped = parse_sheet(frame)

        if header_row is None:
            print('  [!] sheet {!r}: no header row recognised -- skipped. Columns seen: {}'.format(
                sheet, [raw(frame.iat[0, c]) for c in range(min(6, frame.shape[1]))]))
            continue

        fields = ', '.join(sorted(mapped.keys()))
        print('  sheet {!r}: header r{}, {} row(s) [{}]'.format(
            sheet, header_row, len(rows), fields))

        if declared is not None and declared != len(rows):
            mismatches.append((listnr, sheet, declared, len(rows)))
            print('  [!] the sheet declares {} entrie(s) but {} were parsed'.format(
                declared, len(rows)))
        elif declared is not None:
            print('       matches the {} the sheet declares'.format(declared))

        for record in rows:

            address, zipcode, city = split_address(record.get('Address', ''))

            sqldict['ListProcessDate'].append(processdate)

            sqldict['Name'].append(record.get('Name', ''))
            sqldict['ListLabel'].append(listlabel)
            sqldict['Typology'].append(listname)
            sqldict['ListName'].append(listname)
            sqldict['ListCode'].append(listnr)
            sqldict['ListLanguage'].append('EN')
            sqldict['RegCtry'].append('JP')
            sqldict['RegCode'].append('FSAJP')
            sqldict['RegulationType'].append('Regulated')

            if record.get('JCN', ''):
                sqldict['InternalID_1'].append(record['JCN'])
                sqldict['InternalID_1_type'].append('JCN')

            if record.get('RegNo', ''):
                sqldict['InternalID_2'].append(record['RegNo'])
                sqldict['InternalID_2_type'].append('Registration Number')

            if record.get('CoType', ''):
                sqldict['CoType'].append(record['CoType'])

            if record.get('Licences', ''):
                sqldict['License_Type'].append(record['Licences'])

            if address:
                sqldict['Address_1'].append(address)

            # A sheet-supplied Postal Code beats one carved out of the address.
            if record.get('Zip', ''):
                sqldict['Zip'].append(record['Zip'])
            elif zipcode:
                sqldict['Zip'].append(zipcode)

            # Likewise Prefecture beats the city guessed from the address tail.
            if record.get('Pref', ''):
                sqldict['City'].append(record['Pref'])
            elif city:
                sqldict['City'].append(city)

            if record.get('Cntry', ''):
                sqldict['Cntry'].append(record['Cntry'])

            if record.get('Phone', ''):
                sqldict['Phone'].append(record['Phone'])

            if record.get('Mother', ''):
                sqldict['Name - Mother Company'].append(record['Mother'])

            bourange_same_length_array(sqldict)

            written += 1

    counts.append((listnr, listname, written))
    print('  [{}] {} -- {} row(s)'.format(listnr, listname, written))
    print('')


# ------------------------------------------------ Begin_Save --------------------------------------------

os.chdir(scriptfolder)

df = pd.DataFrame(sqldict)

df = df[df['Name'] != '']

df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)

print('Saved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))
print('')

print('Rows per list:')
summary = df.groupby(['ListCode', 'ListName', 'ListLabel'], sort=False).size().reset_index(name='rows')
print(summary.to_string(index=False))
print('')

if mismatches:
    print('[NOTE] {} sheet(s) disagreed with the total they state about themselves -- '
          'check these before delivering:'.format(len(mismatches)))
    for listnr, sheet, declared, parsed in mismatches:
        print('   list {:<3} sheet {!r}: declared {}, parsed {}'.format(
            listnr, sheet, declared, parsed))
else:
    print('[OK] every sheet that declares a total agrees with the number of rows parsed.')
