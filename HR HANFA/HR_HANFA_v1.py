#---- Begin_Librairie ----
# -*- coding: utf-8 -*-
"""
HR HANFA - Hrvatska agencija za nadzor financijskih usluga (Croatia)
Croatian Financial Services Supervisory Agency
Jira: DECD-6823

6 lists from the ticket, each of which is a *section* of https://www.hanfa.hr/registers/
containing several sub-registers.  31 sub-registers are in scope.

Two different delivery mechanisms are used by the same DataTables widget:

  a) small registers  -> the complete <tbody> is server-rendered into the page,
     DataTables only paginates it client side.  Plain requests + BeautifulSoup.
  b) large registers  -> `serverSide: true` with a POST to /Api/Registers/GetData
     keyed by a per-register GUID.  The page then renders only the first 10 rows.
     The GUID and the true row count (`deferLoading: N`) are read off the page at
     run time, never hard-coded, and the API is paged until recordsTotal is hit.

Detecting (b) matters: the 5 server-side registers would otherwise silently yield
10 rows instead of 11,527.

Out of scope per the ticket: "Notifications from EU Member States" registers, and
the "... in liquidation" registers (investment funds / leasing / factoring).
"""
import os
import re
import json
import time
import datetime
import unicodedata

import requests
import pandas as pd
from bs4 import BeautifulSoup

requests.packages.urllib3.disable_warnings()


#---- Begin_fileName ----
# ------ At first we will define the workspace path -----
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))  ## production environment (.py)
except NameError:
    scriptfolder = os.getcwd()  ## notebook environment

os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder')
if not os.path.exists(tempfolder):
    os.makedirs(tempfolder)

regulatorName = 'HR HANFA'  ## change to current controller name
now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(':', '.')[:-7])


#---- Begin_Variable ----
BASE = 'https://www.hanfa.hr'
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
HEADERS = {'User-Agent': UA,
           'Accept-Language': 'en-GB,en;q=0.9,hr;q=0.8'}
API = BASE + '/Api/Registers/GetData'
PAGE_SIZE = 2000

RegCtry = 'HR'
RegCode = 'HANFA'
ListLanguage = 'EN'          # the /registers/ tree is the English edition of the site

sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}

# ---- the 6 lists of the ticket -------------------------------------------------
ListName = {
    regulatorName + ' 1': 'List of Investment firms',
    regulatorName + ' 2': 'List of Investment funds',
    regulatorName + ' 3': 'List of Pension System',
    regulatorName + ' 4': 'List of Insurance Market',
    regulatorName + ' 5': 'List of Leasing Companies',
    regulatorName + ' 6': 'List of Factoring Companies',
}

# 1 = bank, 2 = insurance, 3 = bank & insurance, 4 = everything else.
# HANFA supervises non-banking financial services; the banking supervisor is HNB.
# Only list 4 is an insurance register -> 2.  Everything else -> 4.
ListLabel = {
    regulatorName + ' 1': '4',
    regulatorName + ' 2': '4',
    regulatorName + ' 3': '4',
    regulatorName + ' 4': '2',
    regulatorName + ' 5': '4',
    regulatorName + ' 6': '4',
}

urls = {
    regulatorName + ' 1': BASE + '/registers/investment-firms/',
    regulatorName + ' 2': BASE + '/registers/investment-funds/',
    regulatorName + ' 3': BASE + '/registers/pension-system/',
    regulatorName + ' 4': BASE + '/registers/insurance-market/',
    regulatorName + ' 5': BASE + '/registers/leasing/',
    regulatorName + ' 6': BASE + '/registers/factoring/',
}

# Sub-registers that the ticket explicitly excludes.  Matched as a normalised
# substring against the anchor's *visible label* on the section page, never
# against the href, so a URL slug change does not break the exclusion.
EXCLUDE_LABEL = [
    'notifications',        # "Notifications from EU Member States" / "Notifications - ..."
    'in liquidation',       # funds / leasing / factoring in liquidation
]

# ---- header -> sqldict mapping (normalised, lower-cased, accent-stripped) ------
H_NAME = ('name', 'fund', 'tied agent')
H_SURNAME = ('surname',)

# label -> canonical key, for the "General data" / "Contact" detail cells.
# Croatian labels appear on the English pages of some registers (tied agents).
LABEL_MAP = {
    'address': 'address', 'sjediste': 'address',
    'phone': 'phone', 'telefon': 'phone',
    'website': 'website', 'internetska stranica': 'website',
    'e-mail': 'email', 'email': 'email',
    'lei': 'lei',
    'bic': 'bic',
    'oib': 'oib',
    'personal identification number': 'oib',
    'registration number': 'regno',
    'craft registration number': 'regno',
    'rbs': 'regno',
    'management company': 'mother',
    'activity': 'licence',
    'classes': 'licence',
    'manner of provision of services': 'licence',
}

EU_CNTRY = {
    'austria': 'AT', 'belgium': 'BE', 'bulgaria': 'BG', 'croatia': 'HR', 'cyprus': 'CY',
    'czech republic': 'CZ', 'czechia': 'CZ', 'denmark': 'DK', 'estonia': 'EE',
    'finland': 'FI', 'france': 'FR', 'germany': 'DE', 'greece': 'GR', 'hungary': 'HU',
    'ireland': 'IE', 'italy': 'IT', 'latvia': 'LV', 'liechtenstein': 'LI',
    'lithuania': 'LT', 'luxembourg': 'LU', 'malta': 'MT', 'netherlands': 'NL',
    'norway': 'NO', 'poland': 'PL', 'portugal': 'PT', 'romania': 'RO',
    'slovakia': 'SK', 'slovenia': 'SI', 'spain': 'ES', 'sweden': 'SE',
    'iceland': 'IS',
}

counts = {}          # reg key -> rows written
declared = {}        # (reg, sub-register title) -> count published by the site
scraped_sub = {}     # (reg, sub-register title) -> count scraped


#---- Begin_Function ----
def norm(text):
    """lower-case, accent-stripped, whitespace-collapsed - for label matching.

    Croatian uses c/c/z/s/d; never compare register labels with == .
    """
    if text is None:
        return ''
    text = unicodedata.normalize('NFKD', str(text))
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace('đ', 'd').replace('Đ', 'D')
    return re.sub(r'\s+', ' ', text).strip().lower()


def clean(value):
    if value is None:
        return ''
    text = unicodedata.normalize('NFKC', str(value)).replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    if text.lower() in ('nan', 'none', 'n/a', 'na', '-', '--', '/'):
        return ''
    return text


def add_row(reg, **kw):
    """Append one record, filling EVERY key of sqldict so columns cannot drift."""
    row = {k: '' for k in sqldict}
    row['RegCtry'] = RegCtry
    row['RegCode'] = RegCode
    row['ListCode'] = reg.split(' ')[-1]
    row['ListName'] = ListName[reg]
    row['ListLabel'] = ListLabel[reg]
    row['ListLanguage'] = ListLanguage
    row['ListProcessDate'] = processdate
    row['RegulationType'] = 'Regulated'
    row['Cntry'] = RegCtry
    for key, value in kw.items():
        if key not in row:
            raise KeyError('Unknown sqldict column: %s' % key)
        row[key] = clean(value)
    for key in sqldict:
        sqldict[key].append(row[key])


def get(url, tries=3):
    last = None
    for attempt in range(tries):
        try:
            r = requests.get(url, headers=HEADERS, verify=False, timeout=120)
            r.raise_for_status()
            r.encoding = r.encoding or 'utf-8'
            return r.text
        except Exception as exc:          # noqa: BLE001
            last = exc
            time.sleep(2 + 2 * attempt)
    print('    !! GET failed after {} tries: {} ({})'.format(tries, url, last))
    return ''


def parse_date(value):
    """dd/mm/yyyy or dd.mm.yyyy -> yyyy-mm-dd, else ''.

    HANFA is inconsistent: the HTML pages render '04/12/2015' while the
    /Api/Registers/GetData JSON returns the same date as '04. 12. 2015'
    (Croatian style, spaces after the dots) - the separator regex must tolerate
    the whitespace or every server-side register silently loses its dates.
    """
    text = clean(value)
    if not text:
        return ''
    m = re.search(r'(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{4})', text)
    if m:
        d, mo, y = m.groups()
        try:
            return datetime.date(int(y), int(mo), int(d)).strftime('%Y-%m-%d')
        except ValueError:
            return ''
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', text)
    return m.group(0) if m else ''


def split_address(value):
    """'Slavonska avenija 6, Zagreb' -> ('Slavonska avenija 6', 'Zagreb', '').

    HANFA writes 'street no, city'; a few carry a 5-digit postcode in the city part.
    """
    text = clean(value)
    if not text:
        return '', '', ''
    if ',' in text:
        street, city = text.rsplit(',', 1)
    else:
        street, city = text, ''
    street, city = clean(street), clean(city)
    zipc = ''
    m = re.match(r'^(\d{4,5})\s+(.*)$', city)
    if m:
        zipc, city = m.group(1), m.group(2)
    return street, city, zipc


def detail_pairs(cell):
    """Parse a '<span>Label:</span> value<br/>' detail cell into {canonical: value}.

    Unlabelled fragments are collected under '_text'.
    """
    out = {}
    free = []
    for chunk in re.split(r'<br\s*/?>', str(cell)):
        frag = BeautifulSoup(chunk, 'html.parser')
        span = frag.find('span')
        label = clean(span.get_text()) if span else ''
        if span is not None and label.endswith(':'):
            span.extract()
            key = LABEL_MAP.get(norm(label.rstrip(':')), norm(label.rstrip(':')))
            val = clean(frag.get_text(' '))
            if val:
                out[key] = (out[key] + ' | ' + val) if key in out else val
        else:
            txt = clean(frag.get_text(' '))
            if txt:
                free.append(txt)
    if free:
        out['_text'] = ' | '.join(free)
    return out


def cell_text(cell):
    return clean(cell.get_text(' '))


def discover_subregisters(section_url):
    """Return [(label, absolute_url)] for the in-scope sub-registers of a section.

    Links are resolved from the section page every run and filtered on the
    anchor's VISIBLE LABEL (normalised), so re-slugged URLs keep working.
    """
    html = get(section_url)
    if not html:
        return []
    soup = BeautifulSoup(html, 'html.parser')
    root = section_url.replace(BASE, '').rstrip('/')
    seen, out = set(), []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if not href.startswith(root + '/') or href.rstrip('/') == root:
            continue
        label = clean(a.get_text(' '))
        if not label:
            continue
        n = norm(label)
        if any(bad in n for bad in EXCLUDE_LABEL):
            continue
        url = href if href.startswith('http') else BASE + href
        if url in seen:
            continue
        seen.add(url)
        out.append((label, url))
    return out


def fetch_rows(page_html, page_url):
    """Return (headers, [row_cells]) where row_cells is a list of BeautifulSoup <td>-likes.

    Handles both the server-rendered <tbody> and the serverSide DataTables API.
    """
    soup = BeautifulSoup(page_html, 'html.parser')
    table = soup.find('table', id='registar') or soup.find('table', class_='registarTable')
    if table is None:
        print("    SKIPPED - no register table on {}".format(page_url))
        return [], [], None
    headers = [clean(th.get_text(' ')) for th in table.find_all('th')]

    key = re.search(r"d\.Key\s*=\s*'([0-9a-fA-F-]{36})'", page_html)
    lang = re.search(r"d\.Lang\s*=\s*'([A-Za-z]{2})'", page_html)
    server_side = bool(re.search(r'serverSide:\s*true', page_html)) and key is not None

    if not server_side:
        body = table.find('tbody')
        rows = body.find_all('tr', recursive=False) if body else []
        cells = [tr.find_all('td', recursive=False) for tr in rows]
        return headers, cells, None

    # ---- serverSide: page /Api/Registers/GetData -------------------------------
    ncol = max(len(headers), 1)
    total, start, cells = None, 0, []
    while True:
        data = {'draw': '1', 'start': str(start), 'length': str(PAGE_SIZE),
                'search[value]': '', 'search[regex]': 'false',
                'Key': key.group(1), 'Lang': (lang.group(1) if lang else 'EN')}
        for i in range(ncol):
            data['columns[%d][data]' % i] = str(i)
            data['columns[%d][name]' % i] = ''
            data['columns[%d][searchable]' % i] = 'true'
            data['columns[%d][orderable]' % i] = 'true'
            data['columns[%d][search][value]' % i] = ''
            data['columns[%d][search][regex]' % i] = 'false'
        data['order[0][column]'] = '0'
        data['order[0][dir]'] = 'asc'
        try:
            resp = requests.post(API, headers=dict(HEADERS, **{
                'X-Requested-With': 'XMLHttpRequest', 'Referer': page_url}),
                data=data, verify=False, timeout=180)
            payload = resp.json()
        except Exception as exc:          # noqa: BLE001
            print('    !! API page start={} failed: {}'.format(start, exc))
            break
        if total is None:
            total = int(payload.get('recordsTotal') or 0)
        batch = payload.get('data') or []
        if not batch:
            break
        for raw in batch:
            cells.append([BeautifulSoup(str(c), 'html.parser') for c in raw])
        start += len(batch)
        print('      api {}/{}'.format(start, total))
        if total and start >= total:
            break
    return headers, cells, total


def row_map(headers, cells):
    """{normalised header: cell} - repeated headers get a _2, _3 suffix."""
    out = {}
    for i, cell in enumerate(cells):
        h = norm(headers[i]) if i < len(headers) else 'col%d' % i
        if not h:
            h = 'detail%d' % i
        base, n = h, 2
        while h in out:
            h = '%s_%d' % (base, n)
            n += 1
        out[h] = cell
    return out


def pick(rm, *names):
    for n in names:
        if n in rm:
            return cell_text(rm[n])
    return ''


def harvest(reg, sub_label, page_url):
    """Scrape one sub-register page into sqldict.  Returns (scraped, declared)."""
    html = get(page_url)
    if not html:
        print('    SKIPPED - page unreachable: {}'.format(page_url))
        return 0, None
    headers, all_cells, total = fetch_rows(html, page_url)
    if not headers:
        return 0, None
    hn = [norm(h) for h in headers]
    has_surname = any(h in H_SURNAME for h in hn)
    written = 0

    for cells in all_cells:
        rm = row_map(headers, cells)

        # ---- merge every labelled detail cell into one dict --------------------
        det = {}
        for h, cell in rm.items():
            if cell.find('span') is not None:
                for k, v in detail_pairs(cell).items():
                    if k == '_text':
                        continue
                    det.setdefault(k, v)

        # ---- Name --------------------------------------------------------------
        name = pick(rm, 'name', 'fund', 'tied agent')
        if has_surname:
            first = pick(rm, 'name')
            last = pick(rm, 'surname')
            name = clean('{} {}'.format(first, last))
        if not name:
            continue

        # ---- identifiers -------------------------------------------------------
        oib = pick(rm, 'oib') or det.get('oib', '')
        regno = pick(rm, 'registration number') or det.get('regno', '')
        isin = pick(rm, 'isin')
        lei = pick(rm, 'lei') or det.get('lei', '')

        ids = []
        if oib:
            ids.append((oib, 'OIB'))
        if regno:
            ids.append((regno, 'Registration Number'))
        if isin:
            ids.append((isin, 'ISIN'))
        # the hidden 4th column carries HANFA's own register id (e.g. R195)
        for h, cell in rm.items():
            if h.startswith('detail') or h.startswith('col'):
                t = cell_text(cell)
                if re.fullmatch(r'[A-Z]\d{2,6}', t):
                    ids.append((t, 'HANFA Register ID'))
                    break
        ids = ids[:3]

        # ---- address -----------------------------------------------------------
        street, city, zipc = split_address(det.get('address', '') or pick(rm, 'address'))

        # ---- licence / activities ---------------------------------------------
        lic_parts = []
        for h in hn:
            if h and (h.startswith('approved activities') or h == 'classes'
                      or h == 'activity' or h.startswith('line of business')
                      or h.startswith('type of insurance') or h.startswith('tied agents activities')
                      or h.startswith('category of intermediary')):
                v = pick(rm, h)
                # some of these cells repeat their own label inside the cell
                # ("<span>Activity:</span> Operativni, ...") - drop the prefix so
                # it does not duplicate the value harvested from the detail pairs
                v = re.sub(r'^[^:]{2,40}:\s*', '', v)
                if v:
                    lic_parts.append(v)
        if det.get('licence'):
            lic_parts.append(det['licence'])
        seen_lic, licence_parts = set(), []
        for p in lic_parts:
            p = p.strip(' ,;|')
            k = norm(p)
            if p and k not in seen_lic:
                seen_lic.add(k)
                licence_parts.append(p)
        licence = ' | '.join(licence_parts)

        # ---- misc --------------------------------------------------------------
        mother = pick(rm, 'management company', 'investment firm') or det.get('mother', '')
        cotype = pick(rm, 'category', 'intermediary status')
        regdate = parse_date(pick(rm, 'date of registration', 'date of authorisation'))
        cntry = RegCtry
        member_state = pick(rm, 'eu member state')
        if member_state and norm(member_state) in EU_CNTRY:
            cntry = EU_CNTRY[norm(member_state)]

        kw = dict(
            Name=name,
            Typology=sub_label,
            CoType=cotype,
            License_Type=licence,
            Address_1=street,
            City=city,
            Zip=zipc,
            Cntry=cntry,
            Phone=det.get('phone', ''),
            Website=det.get('website', ''),
            Email=det.get('email', ''),
            RegulationDate=regdate,
        )
        kw['LEI Code'] = lei
        kw['BIC SWIFT Code'] = det.get('bic', '')
        kw['Name - Mother Company'] = mother
        for n, (val, typ) in enumerate(ids, start=1):
            kw['InternalID_%d' % n] = val
            kw['InternalID_%d_type' % n] = typ
        add_row(reg, **kw)
        written += 1

    return written, total


#---- Begin_MainLoop ----
print('=' * 78)
print('HR HANFA  -  DECD-6823   run {}'.format(now.strftime('%Y-%m-%d %H:%M:%S')))
print('=' * 78)

for reg in sorted(urls, key=lambda k: int(k.split(' ')[-1])):
    before = len(sqldict['Name'])
    print('\n### {}  {}'.format(reg, ListName[reg]))
    print('    section: {}'.format(urls[reg]))

    subs = discover_subregisters(urls[reg])
    if not subs:
        print("    SKIPPED - no sub-register anchors found under {}".format(urls[reg]))
        counts[reg] = 0
        continue

    # Lists 5 and 6 point at a single sub-register in the ticket; the exclusion of
    # the "... in liquidation" twin already narrows the section to that one page.
    for label, url in subs:
        print('  - {}'.format(label))
        got, total = harvest(reg, label, url)
        scraped_sub[(reg, label)] = got
        declared[(reg, label)] = total
        if total is not None and got != total:
            print('    !! MISMATCH scraped {} vs site total {}'.format(got, total))
        else:
            print('    rows: {}{}'.format(got, '' if total is None else ' (site total {})'.format(total)))

    counts[reg] = len(sqldict['Name']) - before
    print('    -> list total: {}'.format(counts[reg]))


#---- Begin_writer and save df to excel ----
os.chdir(scriptfolder)
df = pd.DataFrame(sqldict)

df = df[df['Name'] != '']

df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)

print('\n================ SUMMARY ================')
for reg in sorted(counts, key=lambda k: int(k.split(' ')[-1])):
    print('  {:<12} {:<32} {:>6}'.format(reg, ListName[reg], counts[reg]))
print('  {:<45} {:>6}'.format('TOTAL rows written', len(df)))

print('\n---------------- per sub-register (scraped vs site-declared) ----------------')
for reg, label in scraped_sub:
    tot = declared[(reg, label)]
    flag = '' if tot is None or tot == scraped_sub[(reg, label)] else '   <-- MISMATCH'
    print('  {:<12} {:<74} {:>6} / {}{}'.format(
        reg, label[:74], scraped_sub[(reg, label)], 'n-a' if tot is None else tot, flag))

print('\nSaved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))
