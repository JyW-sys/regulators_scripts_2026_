"""YE CBYE web-scraping tool — script version.

Uses the official googletrans 4.0.2 async API pattern:

    async with Translator() as translator:
        result = await translator.translate(text, src='ar', dest='en')

Run from the workspace root:
    python "YE CBYE\\YE_CBYE_v1.py"
"""

# ------------------------------------------------ Begin_Librairie ----------------------------------------
import pandas as pd
import datetime
import re
import os
import asyncio
import requests
import pdfplumber
from googletrans import Translator
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ------------------------------------------------ Begin_fileName ----------------------------------------
regulatorName = 'YE CBYE'
print(f"Running {regulatorName} Web Scraping Tool v.1.0")

now = datetime.datetime.now()
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(':', '.')[:-7])

scriptfolder = f"C:\\Users\\wuj1\\OneDrive - Moody's\\Desktop\\Regulator\\{regulatorName}"
# scriptfolder=os.path.dirname(os.path.abspath(__file__))
os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder')
if os.path.exists(tempfolder):
    for rem in os.listdir(tempfolder):
        os.remove(os.path.join(tempfolder, rem))
else:
    os.mkdir(tempfolder)

processdate = now.strftime('%Y-%m-%d')


# ------------------------------------------------ Begin_Function ----------------------------------------
def bourange_same_length_array(sqldict):
    maxlen = len(sqldict['ListProcessDate'])
    for key in sqldict:
        if len(sqldict[key]) != maxlen:
            sqldict[key] = sqldict[key] + [''] * (maxlen - len(sqldict[key]))
    return sqldict


_MISSING_TOKENS = {'', '-', '—', 'N/A', 'NA', 'None', 'null', '无', '無'}
_translation_cache = {}  # populated by translate_all() once, reused everywhere


def is_missing(value) -> bool:
    if value is None:
        return True
    s = str(value).strip()
    return s == '' or s in _MISSING_TOKENS


async def translate_all(strings, src='ar', dest='en', max_retries=3, base_delay=2.0):
    """Official googletrans 4.0.2 async pattern: open ONE translator session,
    translate every unique string inside it, store results in _translation_cache.
    """
    items = sorted(s for s in strings if not is_missing(s))
    async with Translator() as translator:
        for i, text in enumerate(items, 1):
            key = (str(text), src, dest)
            if key in _translation_cache:
                continue
            cleaned = str(text).replace('\n', ' ').strip()
            for attempt in range(1, max_retries + 1):
                try:
                    result = await translator.translate(cleaned, src=src, dest=dest)
                    _translation_cache[key] = result.text
                    break
                except Exception as e:
                    print(f"[translate] '{cleaned[:40]}' attempt {attempt}/{max_retries}: {e}")
                    if attempt == max_retries:
                        _translation_cache[key] = cleaned
                    else:
                        await asyncio.sleep(base_delay * attempt)
            if i % 25 == 0:
                print(f'  translated {i}/{len(items)}')


def translate_text(text, src='ar', dest='en'):
    """Synchronous lookup into the cache populated by translate_all()."""
    if is_missing(text):
        return ''
    return _translation_cache.get((str(text), src, dest), str(text))


def download_pdf(url: str, dest_folder: str) -> str:
    fname = url.rstrip('/').split('/')[-1]
    if not fname.lower().endswith('.pdf'):
        fname = fname + '.pdf'
    local = os.path.join(dest_folder, fname)
    headers = {'User-Agent': 'Mozilla/5.0'}
    r = requests.get(url, headers=headers, verify=False, timeout=60)
    r.raise_for_status()
    with open(local, 'wb') as f:
        f.write(r.content)
    print(f"[download] {url} -> {local} ({len(r.content)} bytes)")
    return local


def clear_tempfolder(folder: str):
    folder_abs = os.path.abspath(folder)
    if not folder_abs or folder_abs in ('/', '\\') or not folder_abs.lower().endswith('tempfolder'):
        raise RuntimeError(f'Refusing to clear suspicious path: {folder_abs}')
    for rem in os.listdir(folder_abs):
        os.remove(os.path.join(folder_abs, rem))


_URL_RE = re.compile(r'(?:https?://|www\.)[\w.\-/]+', re.IGNORECASE)


def split_address_website(text: str):
    if not text:
        return '', ''
    s = str(text).replace('\n', ' ').strip()
    m = _URL_RE.search(s)
    if not m:
        return s, ''
    website = m.group(0)
    address = (s[:m.start()] + s[m.end():]).strip(' ,;-')
    return address, website


# ------------------------------------------------ Begin_Variable ----------------------------------------
Typology = {
    'YE CBYE 1': 'Licensed banks in the Republic of Yemen',
    'YE CBYE 2': 'Licensed exchange companies in the Republic of Yemen',
}

PdfLinks = {
    'YE CBYE 1': ['https://english.cby-ye.com/files/69dfc71a51c14.pdf'],
    'YE CBYE 2': [
        'https://english.cby-ye.com/files/615d6aedbf960.pdf',
        'https://english.cby-ye.com/files/615d6b5e11ba1.pdf',
    ],
}

sqldict = {k: [] for k in [
    'bvdid', 'priority', 'ListLabel', 'Typology', 'EntryType', 'Name',
    'InternalID_1', 'InternalID_1_type', 'InternalID_2', 'InternalID_2_type',
    'InternalID_3', 'InternalID_3_type', 'CoType', 'License_Type',
    'Address_1', 'Address_2', 'City', 'Zip', 'Cntry', 'Phone', 'Fax',
    'Website', 'Email', 'RegulationType', 'RegulationTypeCode',
    'RegulationDate', 'CancellationDate', 'RegCtry', 'RegCode', 'ListCode',
    'ListLanguage', 'ListValidityDate', 'ListName', 'ListProcessDate',
    'LEI Code', 'BIC SWIFT Code', 'Name - Mother Company',
    'Address_1 - Mother company', 'Address_2 -  Mother company',
    'City - Mother company', 'Zip - Mother company', 'Cntry - Mother company',
    'Phone - Mother company', 'Check']}


# =========================================================================================
# List 1 — Licensed banks in the Republic of Yemen (English PDF)
# =========================================================================================
reg = 'YE CBYE 1'
print(f'\nWorking with list {reg}')
clear_tempfolder(tempfolder)
pdf_path = download_pdf(PdfLinks[reg][0], tempfolder)

rows = []
with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        tbl = page.extract_table()
        if tbl:
            rows.extend(tbl)
        else:
            for line in (page.extract_text() or '').splitlines():
                if line.strip():
                    rows.append([line.strip()])

print(f'Raw rows extracted: {len(rows)}')

header_idx = None
for i, r in enumerate(rows):
    joined = ' '.join(str(c or '') for c in r).lower()
    if 'bank' in joined and ('address' in joined or 'website' in joined or 'name' in joined):
        header_idx = i
        break

if header_idx is not None:
    header = [str(c or '').strip() for c in rows[header_idx]]
    body = [r for r in rows[header_idx + 1:] if r and any(str(c or '').strip() for c in r)]
    width = len(header)
    body = [list(r) + [''] * (width - len(r)) if len(r) < width else list(r)[:width] for r in body]
    df1 = pd.DataFrame(body, columns=header)
else:
    df1 = pd.DataFrame({'Name': [str(r[0]).strip() for r in rows if r and str(r[0]).strip()]})


def pick_col(df, *needles):
    for c in df.columns:
        if any(n in str(c).lower() for n in needles):
            return c
    return None


name_col = pick_col(df1, "bank's name", 'name')
addr_col = pick_col(df1, "bank's adress", 'adress')
site_col = pick_col(df1, 'ينوتركللاا عقولما', 'url', 'web')
# print('cols:', name_col, addr_col, site_col)

for _, row in df1.iterrows():
    name = str(row[name_col]).replace('\n', ' ').strip() if name_col else ''
    if is_missing(name):
        continue
    address = str(row[addr_col]).replace('\n', ' ').strip() if addr_col else ''
    website = str(row[site_col]).replace('\n', ' ').strip() if site_col else ''
    if not website:
        address, website = split_address_website(address)

    sqldict['Name'].append(name)
    sqldict['Address_1'].append(address)
    sqldict['Website'].append(website if len(website) > 2 else '')
    sqldict['Cntry'].append('YE')
    sqldict['ListProcessDate'].append(processdate)
    sqldict['RegulationType'].append('Regulated')
    sqldict['RegCtry'].append(reg.split()[0])
    sqldict['RegCode'].append(reg.split()[1])
    sqldict['ListCode'].append(reg.split()[2])
    sqldict['ListName'].append(Typology[reg])


sqldict = bourange_same_length_array(sqldict)
clear_tempfolder(tempfolder)
print(f"Rows after list 1: {len(sqldict['ListProcessDate'])}")


# =========================================================================================
# List 2 — Licensed exchange companies (Arabic PDFs, translate to English)
# =========================================================================================
reg = 'YE CBYE 2'
print(f'\nWorking with list {reg}')

# Visual-order Arabic header tokens (pdfplumber returns RTL text reversed).
FIELD_VISUAL_TOKENS = {
    # Use only LONG header phrases. Bare 'ةكشلا' / 'ةأشنملا' would also match
    # real entity names (e.g. الشركة الوطنية للتحويلات النقدية), causing data
    # rows to be silently dropped as if they were repeated headers.
    'name':         ['ةكشلا مسا', 'ةأشنملا مسا'],
    'address':      ['ناونعلا'],
    'city':         ['ةظفاحملا', 'سيئرلا زكرملا', 'ةنيدملا'],
    'owner':        ['كلاملا مسا', 'يذيفنتلا ريدملا مسا', 'ريدملا مسا'],
    # 'legal_entity': ['نوناقلا نايكلا'],
    'renewal':      ['ديدجتلا', 'ديدج / ديدجت', 'ديدجت / ديدج'],
    'number':       ['مقرلا'],
}


def _to_logical(s):
    if not s:
        return ''
    s = str(s).replace('\n', '').replace('\r', '')[::-1]
    return re.sub(r'\s+', ' ', s).strip()


def _match_field(cell_visual):
    cv = re.sub(r'\s+', ' ', str(cell_visual or '').replace('\n', ' ')).strip()
    for field, toks in FIELD_VISUAL_TOKENS.items():
        if any(tok in cv for tok in toks):
            return field
    return None


def _build_col_map(header_row):
    col_map = {}
    for i, cell in enumerate(header_row):
        f = _match_field(cell)
        if f and f not in col_map:
            col_map[f] = i
    return col_map


def _is_header_row(row, col_map):
    if 'name' not in col_map or col_map['name'] >= len(row):
        return False
    cv = re.sub(r'\s+', ' ', str(row[col_map['name']] or '').replace('\n', ' ')).strip()
    return any(tok in cv for tok in FIELD_VISUAL_TOKENS['name'])


def extract_arabic_pdf(path):
    out = []
    with pdfplumber.open(path) as pdf:
        col_map = None
        header_keys = ('name', 'address')
        for page in pdf.pages:
            tbl = page.extract_table()
            if not tbl:
                continue
            start = 0
            if col_map is None:
                for i, row in enumerate(tbl):
                    cmap = _build_col_map(row)
                    if all(k in cmap for k in header_keys):
                        col_map = cmap
                        start = i + 1
                        print(f'  [{os.path.basename(path)}] header @ page-row {i}: {col_map}')
                        break
                if col_map is None:
                    continue
            for row in tbl[start:]:
                if not row or _is_header_row(row, col_map):
                    continue
                rec = {f: _to_logical(row[i]) if i < len(row) else '' for f, i in col_map.items()}
                if rec.get('name'):
                    out.append(rec)
    return out


all_records = []
clear_tempfolder(tempfolder)
for url in PdfLinks[reg]:
    p = download_pdf(url, tempfolder)
    recs = extract_arabic_pdf(p)
    print(f'  {os.path.basename(p)}: {len(recs)} rows')
    all_records.extend(recs)

print(f'Total exchange entities collected: {len(all_records)}')

# ---- Collect every unique Arabic string we will need to translate ----
unique_ar = set()
for rec in all_records:
    for k in ('name', 'address', 'city', 'legal_entity'):
        v = rec.get(k, '')
        if v and not is_missing(v):
            unique_ar.add(v)

print(f'Unique Arabic strings to translate: {len(unique_ar)}')

# ---- Run the official async googletrans pattern: ONE session, all strings ----
asyncio.run(translate_all(unique_ar, src='ar', dest='en'))
print('Translation pass complete.')

# ---- Populate sqldict from cache ----
for rec in all_records:
    name_ar = rec.get('name', '')
    addr_ar = rec.get('address', '')
    city_ar = rec.get('city', '')
    # legal_ar = rec.get('legal_entity', '')

    sqldict['Name'].append(name_ar)
    sqldict['Name - Mother Company'].append(translate_text(name_ar))
    sqldict['Address_1'].append(addr_ar)
    sqldict['Address_1 - Mother company'].append(translate_text(addr_ar))
    sqldict['City'].append(translate_text(city_ar))
    sqldict['City - Mother company'].append(city_ar)
    # sqldict['License_Type'].append(translate_text(legal_ar))
    # sqldict['Check'].append(rec.get('renewal', ''))
    sqldict['Cntry'].append('YE')
    sqldict['ListProcessDate'].append(processdate)
    sqldict['RegulationType'].append('Regulated')
    sqldict['RegCtry'].append(reg.split()[0])
    sqldict['RegCode'].append(reg.split()[1])
    sqldict['ListCode'].append(reg.split()[2])
    sqldict['ListName'].append(Typology[reg])
    # sqldict['ListLanguage'].append('Arabic')

sqldict = bourange_same_length_array(sqldict)
clear_tempfolder(tempfolder)
# print(f"Rows after list 2: {len(sqldict['ListProcessDate'])}")


# ------------------------------------------------ Begin_writer ----------------------------------------
os.chdir(scriptfolder)
df = pd.DataFrame(sqldict).drop_duplicates()
df.to_excel(filename, sheet_name='SQL Ready', index=False)
print(f'\nSaved -> {filename} (rows: {len(df)})')
