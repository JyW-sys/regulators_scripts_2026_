#---- Begin_Librairie ----
import datetime
import os
import re
import struct
import unicodedata
import warnings

import pandas as pd
import pdfplumber
import requests
from bs4 import BeautifulSoup
from docx import Document
from urllib.parse import urljoin, unquote

warnings.filterwarnings('ignore')
requests.packages.urllib3.disable_warnings()

#---- Begin_fileName ----
regulatorName = 'MD CNPF'
print('Running {} Web Scraping Tool v.3'.format(regulatorName))

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(':', '.')[:-7])

try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))   # production environment (.py)
except NameError:
    scriptfolder = os.getcwd()                                  # notebook environment

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

#---- Begin_Variable ----
HUB = 'https://www.cnpf.md/ro/registrele-actelor-permisive-6412.html'

topology = {
    regulatorName + ' 1': 'Companies licensed or authorized on the capital market',
    regulatorName + ' 2': 'Authorized companies in the stock market',
    regulatorName + ' 3': 'Register of crowdfunding service providers',
    regulatorName + ' 4': 'Entities holding information on securities holders',
    regulatorName + ' 5': 'Issuers of securities that have concluded register keeping contracts with registrars',
    regulatorName + ' 6': 'Issuers of securities whose shares are kept by the Central Single Depository',
    regulatorName + ' 7': 'Investment funds that have reorganized into joint-stock companies',
    regulatorName + ' 8': 'Trust companies',
}

# ListLabel: 1 = bank, 2 = insurance, 3 = bank & insurance, 4 = everything else.
# CNPF's capital-market / crowdfunding / trust registers are none of the first three -> 4.
listlabel = {'1': 4, '2': 4, '3': 4, '4': 4, '5': 4, '6': 4, '7': 4, '8': 4}

# Registers are resolved every run by the ACCORDION LABEL and the ANCHOR LABEL,
# never by file name: CNPF re-uploads under "(1)(1)(1)" / date suffixes constantly.
# Keys are accent-stripped, lower-cased substrings (see norm()).
ACCORDIONS = {
    '1': 'persoane licentiate sau autorizate pe piata de capital',
    '2': 'persoane autorizate in domeniul evaluarii actiunilor',
    '3': 'registrul furnizorilor de servicii de finantare participativa',
    '4': 'entitati care detin informatia privind detinatorii de valori mobiliare',
    '5': 'emitenti de valori mobiliare care au incheiate contracte',
    '6': 'emitentii de valori mobiliare a caror evidenta a actiunilor este tinuta',
    '7': 'fonduri de investitii in proces de lichidare',
    '8': 'companii fiduciare',
}
# Where an accordion holds several files, pick the one the ticket asks for.
ANCHORS = {
    '4': 'lista persoanelor autorizate',
    '7': 'care s-au reorganizat',
}

sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}

HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
session = requests.Session()
session.headers.update(HEADERS)
session.verify = False          # corporate TLS proxy: a cert error here is the proxy, not CNPF

counts = {}                     # list_code -> rows written, printed in the reconciliation block

#---- Begin_Function ----
def norm(txt):
    """Accent-stripped, whitespace-collapsed, lower-cased text.

    Romanian on cnpf.md mixes the correct comma-below s/t (U+0219/U+021B) with the
    Turkish cedilla s/t (U+015F/U+0163). They render identically but are different
    codepoints, so anchor text can NEVER be compared with '=='. NFKD decomposes both
    into 's'/'t' + a combining mark, which we then drop.
    """
    if txt is None:
        return ''
    txt = unicodedata.normalize('NFKD', str(txt))
    txt = ''.join(c for c in txt if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', txt).strip().lower()


def clean(val):
    """Normalise a cell: drop NaN, collapse newlines / repeated spaces."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ''
    txt = str(val).strip()
    if txt.lower() in ('nan', 'none', '-'):
        return ''
    return re.sub(r'[ \t]+', ' ', txt.replace('\n', ' ').replace('\r', ' ')).strip()


def add_row(list_code, **kw):
    """Append ONE record. Every one of the 43 columns is written on every row, so the
    columns can never drift out of alignment. An unknown key is a hard error."""
    unknown = [k for k in kw if k not in sqldict]
    if unknown:
        raise KeyError('add_row: unknown column(s) {}'.format(unknown))
    base = {
        'ListLabel': listlabel[list_code],
        'Cntry': 'MD',
        'RegCtry': 'MD',
        'RegCode': 'CNPF',
        'ListCode': list_code,
        'ListLanguage': 'RO',                       # every source file is Romanian
        'ListName': topology[regulatorName + ' ' + list_code],
        'ListProcessDate': processdate,
        'RegulationType': 'Regulated',
        'ListValidityDate': VALIDITY.get(list_code, ''),
    }
    base.update({k: v for k, v in kw.items() if v not in (None, 'nan')})
    if not clean(base.get('Name', '')):
        return False
    for col in sqldict:
        sqldict[col].append(base.get(col, ''))
    counts[list_code] = counts.get(list_code, 0) + 1
    return True


VALIDITY = {}   # list_code -> date stamped inside the source file itself


def to_iso(raw):
    """'11.05.2015' / '11/05/2015' -> '2015-05-11'. Anything else -> ''."""
    m = re.search(r'(\d{1,2})[./-](\d{1,2})[./-](\d{4})', clean(raw))
    if not m:
        m2 = re.search(r'(\d{4})-(\d{2})-(\d{2})', clean(raw))
        return m2.group(0) if m2 else ''
    d, mo, y = m.groups()
    try:
        return datetime.date(int(y), int(mo), int(d)).strftime('%Y-%m-%d')
    except ValueError:
        return ''


def pick_idno(txt, loose=False):
    """Moldovan IDNO is normally 13 digits, but CNPF's registers carry plenty of
    12-digit ones ('100602004674') and the odd shorter typo. `loose=True` is for a
    dedicated IDNO column, where any long digit run is the IDNO; the default is for
    free-text blobs, where a short run would be a phone number."""
    t = clean(txt)
    m = re.search(r'IDNO[:\s]*(\d{6,})', t, re.I)
    if m:
        return m.group(1)
    m = re.search(r'\b(\d{13})\b', t)
    if m:
        return m.group(1)
    if loose:
        # SA "COMPANIA BUGEAC" really is filed under the 5-digit legacy code 64096,
        # so a dedicated IDNO column must not impose a length floor.
        m = re.search(r'\b(\d{4,13})\b', t)
        if m:
            return m.group(1)
    return ''


def pick_email(txt):
    m = re.search(r'[\w.\-+]+@[\w.\-]+\.\w{2,}', clean(txt))
    return m.group(0) if m else ''


def pick_web(txt):
    m = re.search(r'(https?://[^\s,;]+|www\.[^\s,;]+)', clean(txt))
    return m.group(0).rstrip('.,;') if m else ''


def pick_phone(txt, want_fax=False):
    """Pull a telephone (or the fax) out of a mixed contact blob."""
    t = clean(txt)
    t = re.sub(r'[\w.\-+]+@[\w.\-]+\.\w{2,}', ' ', t)       # e-mails first
    t = re.sub(r'https?://\S+|www\.\S+', ' ', t)
    # CNPF types phone numbers with EN DASHes and spaces ('0 - 235 - 2-33-06'),
    # so the separator class must include - and the en/em dash, or the match
    # truncates after the first group.
    SEP = r'[\d()\-‐-―\s]'
    if want_fax:
        m = re.search(r'[Ff]ax[:\s]*(\d' + SEP + r'{4,})', t)
        return re.sub(r'\s+', ' ', m.group(1)).strip(' -–;:') if m else ''
    t = re.sub(r'[Ff]ax[:\s]*\d' + SEP + r'{4,}', ' ', t)
    m = re.search(r'(\+?\d' + SEP + r'{5,}\d)', t)
    return re.sub(r'\s+', ' ', m.group(1)).strip(' -–;:') if m else ''


def pick_zip(txt):
    m = re.search(r'MD\s?-?\s?(\d{4})', clean(txt))
    return 'MD-' + m.group(1) if m else ''


def pick_city(txt):
    """CNPF addresses are 'mun. Chişinău, str. X 1' / 'or. Orhei, ...' / 'r-l Rîşcani ...'."""
    t = clean(txt)
    # The dot is REQUIRED on the one-letter abbreviations: a bare 's' would otherwise
    # match inside 'strada' and yield the city 'trada'.
    m = re.search(r'\b(?:mun\.|or\.|s\.|com\.|r-l|raionul|mun|or)\s*'
                  r'([A-Za-zĂÂÎŞŢȘȚăâîşţșț][A-Za-zĂÂÎŞŢȘȚăâîşţșț\-]{2,})', t, re.I)
    if m and m.group(1).lower() not in ('str', 'strada', 'bd', 'sos'):
        return m.group(1).strip(' .,')
    return ''


def split_addr(txt, limit=250):
    """Address text minus the IDNO / phone / e-mail decorations, split over two fields."""
    t = clean(txt)
    t = re.sub(r'IDNO[:\s]*\d+', ' ', t, flags=re.I)
    t = re.sub(r'[\w.\-+]+@[\w.\-]+\.\w{2,}', ' ', t)
    t = re.sub(r'(?:Tel|Telefon|Fax|tel/fax)[.:\s/]*[\d()+\-\s]{5,}', ' ', t)
    t = re.sub(r'(?:Adresa\s+juridic\w*|Sediul\s+si\s+adresa[^:]*|Adresa)\s*:', ' ', t, flags=re.I)
    t = re.sub(r'\s*[;,]\s*$', '', re.sub(r'\s+', ' ', t)).strip(' ,;-')
    return t[:limit], t[limit:limit * 2]


def is_header_row(cells):
    """A header row carries column captions. A DATA row may legitimately contain the
    word 'denumirea' inside a cell (MD CNPF list 7 does), so any row holding a long
    digit run - an IDNO - is never a header, whatever words it contains."""
    joined = norm(' '.join(clean(c) for c in cells))
    if re.search(r'\b\d{8,13}\b', joined):
        return False
    return bool(re.search(r'denumire|nr\.? d/o|denumirea societatii|codul fiscal', joined))


# ---------- link resolution: by label, never by file name ----------
def resolve_files(soup, base):
    """{list_code: (accordion_title, anchor_label, url)} discovered from the hub page."""
    found = {}
    buttons = soup.select('button.accordion')
    print('[HUB] {} accordions on the page'.format(len(buttons)))
    for btn in buttons:
        title = clean(btn.get_text(' ', strip=True))
        sib = btn.find_next_sibling()
        if sib is None:
            continue
        links = []
        for a in sib.select('a[href]'):
            href = (a.get('href') or '').strip()
            if not re.search(r'\.(pdf|docx?|xlsx?)(\?|$)', href.split('#')[0], re.I):
                continue
            links.append((clean(a.get_text(' ', strip=True)), urljoin(base, href)))
        if not links:
            continue
        for code, key in ACCORDIONS.items():
            if key in norm(title):
                want = ANCHORS.get(code)
                pick = None
                if want:
                    for label, u in links:
                        if want in norm(label):
                            pick = (label, u)
                            break
                    if pick is None:
                        print("SKIPPED - list {}: no anchor whose label contains '{}' "
                              'under accordion "{}"'.format(code, want, title))
                        continue
                else:
                    pick = links[0]
                found[code] = (title, pick[0], pick[1])
    for code in ACCORDIONS:
        if code not in found:
            print("SKIPPED - list {}: no accordion whose label contains '{}'".format(code, ACCORDIONS[code]))
    return found


def download(url, tag):
    fn = re.sub(r'[^\w.\- ()]', '_', unquote(url.split('/')[-1].split('?')[0]))
    fp = os.path.join(tempfolder, '{}_{}'.format(tag, fn))
    r = session.get(url, timeout=300)
    r.raise_for_status()
    body = r.content
    # Soft-404 guard: some sites answer an HTML error page with HTTP 200.
    head = body[:8]
    ext = os.path.splitext(fn)[1].lower()
    ok = ((ext == '.pdf' and head[:4] == b'%PDF')
          or (ext in ('.docx', '.xlsx') and head[:2] == b'PK')
          or (ext in ('.doc', '.xls') and head == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'))
    if not ok:
        raise IOError('SKIPPED - {}: {} is not a real {} (magic={!r}, {} bytes) - soft 404?'
                      .format(tag, fn, ext, head, len(body)))
    with open(fp, 'wb') as fh:
        fh.write(body)
    print('[DL] {}: {} ({:,} bytes)'.format(tag, fn, len(body)))
    return fp


# ---------- legacy .doc reader: pure Python, NO MS Word / pywin32 ----------
# Lifted from MD NBMO/MD_NBMO_v2.py - the production control server has no Office.
def _cfb_streams(data):
    """Minimal Compound-File-Binary (OLE2) reader -> {stream name: bytes}."""
    if data[:8] != b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
        raise ValueError('not an OLE2 compound file')
    ssz = 1 << struct.unpack_from('<H', data, 30)[0]
    msz = 1 << struct.unpack_from('<H', data, 32)[0]
    n_fat = struct.unpack_from('<I', data, 44)[0]
    dir_start = struct.unpack_from('<I', data, 48)[0]
    mini_start = struct.unpack_from('<I', data, 60)[0]
    difat_start, n_difat = struct.unpack_from('<II', data, 68)

    def sector(i):
        off = 512 + i * ssz
        return data[off:off + ssz]

    fat_sectors = list(struct.unpack_from('<109I', data, 76))[:n_fat]
    nxt = difat_start
    while len(fat_sectors) < n_fat and nxt not in (0xFFFFFFFE, 0xFFFFFFFF):
        blk = sector(nxt)
        fat_sectors += list(struct.unpack_from('<%dI' % (ssz // 4 - 1), blk, 0))
        nxt = struct.unpack_from('<I', blk, ssz - 4)[0]
    fat = []
    for s in fat_sectors[:n_fat]:
        fat += list(struct.unpack_from('<%dI' % (ssz // 4), sector(s), 0))

    def chain(start, table):
        out, cur, guard = [], start, 0
        while cur < 0xFFFFFFFC and guard < 1 << 20:
            out.append(cur)
            cur = table[cur] if cur < len(table) else 0xFFFFFFFE
            guard += 1
        return out

    dir_bytes = b''.join(sector(s) for s in chain(dir_start, fat))
    entries = []
    for off in range(0, len(dir_bytes), 128):
        e = dir_bytes[off:off + 128]
        if len(e) < 128 or e[66] == 0:
            continue
        nlen = struct.unpack_from('<H', e, 64)[0]
        name = e[:max(nlen - 2, 0)].decode('utf-16-le', 'replace')
        start, size = struct.unpack_from('<I', e, 116)[0], struct.unpack_from('<I', e, 120)[0]
        entries.append((name, e[66], start, size))

    root = next((x for x in entries if x[1] == 5), None)
    mini_fat = []
    for s in chain(mini_start, fat):
        mini_fat += list(struct.unpack_from('<%dI' % (ssz // 4), sector(s), 0))
    mini_data = b''.join(sector(s) for s in chain(root[2], fat)) if root else b''

    streams = {}
    for name, typ, start, size in entries:
        if typ != 2:
            continue
        if size < 4096 and name != 'Root Entry':
            raw = b''.join(mini_data[i * msz:(i + 1) * msz] for i in chain(start, mini_fat))
        else:
            raw = b''.join(sector(s) for s in chain(start, fat))
        streams[name] = raw[:size]
    return streams


def doc_text(path):
    """Text stream of a Word 97-2003 .doc, with \\x07 cell markers preserved."""
    with open(path, 'rb') as fh:
        data = fh.read()
    st = _cfb_streams(data)
    wd = st['WordDocument']
    tbl_name = '1Table' if (struct.unpack_from('<H', wd, 0x0A)[0] & 0x0200) else '0Table'
    if tbl_name not in st:
        tbl_name = '0Table' if tbl_name == '1Table' else '1Table'
    tbl = st[tbl_name]

    fcClx, lcbClx = struct.unpack_from('<II', wd, 0x01A2)
    clx = tbl[fcClx:fcClx + lcbClx]
    i = 0
    while i < len(clx) and clx[i] == 0x01:
        i += 3 + struct.unpack_from('<h', clx, i + 1)[0]
    if i >= len(clx) or clx[i] != 0x02:
        raise ValueError('piece table (PlcPcd) not found')
    lcb = struct.unpack_from('<I', clx, i + 1)[0]
    plc = clx[i + 5:i + 5 + lcb]
    n = (len(plc) - 4) // 12
    cps = list(struct.unpack_from('<%dI' % (n + 1), plc, 0))

    out = []
    for k in range(n):
        fc = struct.unpack_from('<I', plc, 4 * (n + 1) + 8 * k + 2)[0]
        compressed = bool(fc & 0x40000000)
        fc = (fc & 0x3FFFFFFF) // 2 if compressed else fc
        ln = cps[k + 1] - cps[k]
        raw = wd[fc:fc + (ln if compressed else ln * 2)]
        out.append(raw.decode('cp1251', 'replace') if compressed else raw.decode('utf-16-le', 'replace'))
    return ''.join(out)


def doc_table(path):
    """First table of a .doc / .docx as a DataFrame (no MS Word required)."""
    if path.lower().endswith('.docx'):
        doc = Document(path)
        if not doc.tables:
            return None
        rows = [[c.text for c in r.cells] for r in doc.tables[0].rows]
        return pd.DataFrame(rows)

    text = doc_text(path)
    rows, cur, cell = [], [], []
    for ch in text:
        if ch == '\x07':
            if cur and not cell:
                rows.append(cur)
                cur = []
            else:
                cur.append(''.join(cell).replace('\r', ' ').strip())
                cell = []
        elif ch in '\x0b\x0c':
            continue
        else:
            cell.append(ch)
    if cur:
        rows.append(cur)
    if not rows:
        return None
    width = max(len(r) for r in rows)
    return pd.DataFrame([r + [''] * (width - len(r)) for r in rows])


def pdf_tables(path):
    """[(page_index, page_text, table_rows), ...] for a text-layer PDF."""
    out = []
    with pdfplumber.open(path) as pdf:
        for pi, page in enumerate(pdf.pages):
            txt = page.extract_text() or ''
            for tb in page.extract_tables():
                out.append((pi, txt, tb))
    return out


#---- Begin_MainLoop ----
print('\n[HUB] GET {}'.format(HUB))
resp = session.get(HUB, timeout=120)
resp.raise_for_status()
hub = BeautifulSoup(resp.content.decode('utf-8', 'replace'), 'html.parser')
files = resolve_files(hub, resp.url)
print('[HUB] resolved {}/8 registers\n'.format(len(files)))

paths = {}
for code in sorted(files):
    title, label, url = files[code]
    print('  list {} <- "{}"'.format(code, label[:70]))
    try:
        paths[code] = download(url, 'L' + code)
    except Exception as exc:
        print('SKIPPED - list {}: {}'.format(code, exc))
print('')

declared = {}   # list_code -> count the source itself declares (for reconciliation)

# ---------------- List 1: licensed / authorised on the capital market (PDF) ----------------
if '1' in paths:
    print('Working with {} 1 ...'.format(regulatorName))
    tabs = pdf_tables(paths['1'])
    if tabs:
        VALIDITY['1'] = to_iso(re.search(r'situa\w*\s*(?:la\s*)?([\d.]{8,10})', tabs[0][1] or '').group(1)
                               if re.search(r'situa\w*\s*(?:la\s*)?([\d.]{8,10})', tabs[0][1] or '') else '')
    section = ''
    sec1 = {}               # section banner -> highest Nr. seen under it
    pending = None          # entity being assembled across continuation rows

    def flush1(ent):
        if not ent:
            return
        blob = ent['contact']
        a1, a2 = split_addr(blob)
        add_row('1',
                Name=clean(ent['name']),
                CoType=section_of(ent),
                InternalID_1=pick_idno(blob), InternalID_1_type='IDNO',
                InternalID_2=ent['lic_no'], InternalID_2_type='License number',
                License_Type=' | '.join(dict.fromkeys([x for x in ent['lic'] if x]))[:500],
                Address_1=a1, Address_2=a2, City=pick_city(blob), Zip=pick_zip(blob),
                Phone=pick_phone(blob), Fax=pick_phone(blob, True),
                Email=pick_email(blob), Website=pick_web(blob),
                RegulationDate=ent['regdate'],
                RegulationType='Withdrawn' if ent.get('withdrawn') else 'Regulated')

    def section_of(ent):
        return ent.get('section', '')

    seckey, lastnr, withdrawn = '', 0, False
    for pi, ptxt, tb in tabs:
        # Pages 6-7 of this PDF are a second register - entities whose licence was
        # WITHDRAWN but which have not been struck off. pdfplumber never emits that
        # banner as a table row, so it must be read off the page text.
        if 'retrase' in norm(ptxt):
            withdrawn = True
        for row in tb:
            cells = [clean(c) for c in row] + [''] * 6
            if is_header_row(cells) and not re.match(r'^\d+$', cells[0]):
                continue
            filled = [c for c in cells[:6] if c]
            # section banner: only the first cell carries text
            if cells[0] and not cells[1] and len(filled) == 1 and not re.match(r'^\d+$', cells[0]):
                section, seckey, lastnr = cells[0], cells[0], 0
                continue
            if re.match(r'^\d+\.?$', cells[0]) and cells[1]:
                nr = int(cells[0].strip('.'))
                # Numbering restarts under every banner. If it restarts WITHOUT one
                # (the withdrawn block), open a synthetic section so the declared
                # total stays a sum and never collapses to a single maximum.
                if nr <= lastnr:
                    seckey = '{} <restart @p{}>'.format(section, pi)
                lastnr = nr
                sec1[seckey] = max(sec1.get(seckey, 0), nr)
                flush1(pending)
                pending = {'name': cells[1], 'contact': cells[3], 'lic': [cells[4]],
                           'lic_no': '', 'regdate': '', 'section': section,
                           'withdrawn': withdrawn}
                m = re.search(r'(\d{6,})', cells[5])
                pending['lic_no'] = m.group(1) if m else ''
                pending['regdate'] = to_iso(cells[5])
                continue
            if pending is not None and not cells[0] and not cells[1] and (cells[4] or cells[3]):
                # continuation: an extra licence / authorisation for the same entity
                if cells[4]:
                    pending['lic'].append(cells[4])
                if cells[3]:
                    pending['contact'] += ' ' + cells[3]
    flush1(pending)
    declared['1'] = sum(sec1.values())
    print('  list 1: {} entities  (sections: {})'.format(counts.get('1', 0), sec1))

# ---------------- List 2: authorised in share valuation (DOCX, 2 tables) ----------------
if '2' in paths:
    print('Working with {} 2 ...'.format(regulatorName))
    doc = Document(paths['2'])
    heads = [clean(p.text) for p in doc.paragraphs if clean(p.text)]
    for ti, t in enumerate(doc.tables):
        # the 2nd table in this file is the WITHDRAWN-qualification list
        withdrawn = any('retras' in norm(h) for h in heads) and ti > 0
        for r in t.rows:
            cells = [clean(c.text) for c in r.cells] + [''] * 9
            if not re.match(r'^\d+\.?$', cells[0]) or not cells[1]:
                continue
            blob = cells[3]
            a1, a2 = split_addr(blob)
            if withdrawn:
                add_row('2', Name=cells[1], InternalID_1=pick_idno(cells[2]), InternalID_1_type='IDNO',
                        Address_1=a1, Address_2=a2, City=pick_city(blob), Zip=pick_zip(blob),
                        RegulationType='Withdrawn',
                        RegulationDate=to_iso(cells[4]), CancellationDate=to_iso(cells[5]),
                        License_Type='Persoana autorizata in domeniul evaluarii actiunilor')
            else:
                add_row('2', Name=cells[1], InternalID_1=pick_idno(cells[2]), InternalID_1_type='IDNO',
                        InternalID_2=(re.search(r'nr\.?\s*(\d{4,})', cells[7], re.I).group(1)
                                      if re.search(r'nr\.?\s*(\d{4,})', cells[7], re.I) else ''),
                        InternalID_2_type='Certificate number',
                        Address_1=a1, Address_2=a2, City=pick_city(blob), Zip=pick_zip(blob),
                        Phone=pick_phone(cells[5]), Fax=pick_phone(cells[5], True), Email=pick_email(cells[5]),
                        License_Type='Persoana autorizata in domeniul evaluarii actiunilor',
                        RegulationDate=to_iso(cells[8]))
    print('  list 2: {} entities'.format(counts.get('2', 0)))

# ---------------- List 3: crowdfunding service providers (XLSX) ----------------
if '3' in paths:
    print('Working with {} 3 ...'.format(regulatorName))
    raw = pd.read_excel(paths['3'], sheet_name=0, header=None, dtype=str)
    hdr = None
    for i in range(min(12, len(raw))):
        if 'denumire' in norm(' '.join(clean(x) for x in raw.iloc[i])):
            hdr = i
            break
    for i in range(min(12, len(raw))):
        joined = ' '.join(clean(x) for x in raw.iloc[i])
        m = re.search(r'[Aa]ctualizat\s+la\s*:?\s*([\d.]{8,10})', joined)
        if m:
            VALIDITY['3'] = to_iso(m.group(1))
    if hdr is not None:
        for i in range(hdr + 1, len(raw)):
            cells = [clean(x) for x in raw.iloc[i]] + [''] * 13
            if not cells[2]:
                continue
            name = re.sub(r'^Denumirea\s+complet\w*\s*:?\s*', '', cells[2], flags=re.I)
            name = re.split(r'Denumirea\s+(?:prescurtat|comercial)', name, flags=re.I)[0].strip(' .,;')
            blob = cells[6]
            a1, a2 = split_addr(blob)
            # This sheet's DATA rows are shifted against their own header from the
            # e-mail column onward (a merged cell), so e-mail and web address are
            # located by pattern across the whole row, never by a fixed index.
            rowtext = ' '.join(cells)
            add_row('3', Name=name, CoType=cells[3],
                    InternalID_1=pick_idno(cells[4]), InternalID_1_type='IDNO',
                    InternalID_2=(re.search(r'nr\.?\s*([\d/]+)', cells[5], re.I).group(1)
                                  if re.search(r'nr\.?\s*([\d/]+)', cells[5], re.I) else ''),
                    InternalID_2_type='CNPF decision number',
                    Address_1=a1, Address_2=a2, City=pick_city(blob), Zip=pick_zip(blob),
                    Phone=pick_phone(cells[7]), Email=pick_email(rowtext), Website=pick_web(rowtext),
                    License_Type='Furnizor de servicii de finantare participativa',
                    RegulationDate=to_iso(cells[5]) or to_iso(cells[1]))
    print('  list 3: {} entities'.format(counts.get('3', 0)))

# ---------------- List 4: entities holding securities-holder information (PDF) ----------------
if '4' in paths:
    print('Working with {} 4 ...'.format(regulatorName))
    tabs = pdf_tables(paths['4'])
    if tabs:
        m = re.search(r'situa\w*\s*(?:la\s*)?([\d.]{8,10})', tabs[0][1] or '')
        VALIDITY['4'] = to_iso(m.group(1)) if m else ''
    for pi, ptxt, tb in tabs:
        withdrawn = 'retrase' in norm(ptxt)
        # the section banner is the last ALL-CAPS heading line above the table
        cat = ''
        for line in (ptxt or '').split('\n'):
            ln = clean(line)
            if ln and ln == ln.upper() and len(ln) > 8 and 'RETRASE' not in ln and 'LISTA' not in ln:
                cat = ln
                break
        tmax = 0
        for row in tb:
            cells = [clean(c) for c in row] + [''] * 8
            if is_header_row(cells) and not re.match(r'^\d+$', cells[0]):
                continue
            if not re.match(r'^\d+\.?$', cells[0]) or not cells[1]:
                continue
            # every sub-table in this PDF restarts its own Nr. d/o numbering
            tmax = max(tmax, int(cells[0].strip('.')))
            blob = ' '.join(x for x in cells[3:8] if x)
            a1, a2 = split_addr(cells[3])
            add_row('4', Name=cells[1], CoType=cat,
                    InternalID_1=pick_idno(blob), InternalID_1_type='IDNO',
                    Address_1=a1, Address_2=a2, City=pick_city(cells[3]), Zip=pick_zip(cells[3]),
                    Phone=pick_phone(blob), Fax=pick_phone(blob, True), Email=pick_email(blob),
                    RegulationType='Withdrawn' if withdrawn else 'Regulated')
        declared['4'] = declared.get('4', 0) + tmax
    print('  list 4: {} entities'.format(counts.get('4', 0)))

# ---------------- List 5: issuers with register-keeping contracts (XLSX) ----------------
if '5' in paths:
    print('Working with {} 5 ...'.format(regulatorName))
    xl = pd.ExcelFile(paths['5'])
    # Discover the ACTIVE-contracts sheet by label; never index by position.
    active = [s for s in xl.sheet_names if 'activ' in norm(s)]
    other = [s for s in xl.sheet_names if s not in active]
    if not active:
        print("SKIPPED - list 5: no sheet whose name contains 'activ' (sheets={})".format(xl.sheet_names))
    for s in other:
        d = pd.read_excel(paths['5'], sheet_name=s, header=None, dtype=str)
        print('  [info] list 5: sheet "{}" holds {} further rows (terminated/cancelled '
              'contracts) - NOT scraped, see README'.format(s, max(len(d) - 1, 0)))
    for s in active:
        raw = pd.read_excel(paths['5'], sheet_name=s, header=None, dtype=str)
        declared['5'] = 0
        for i in range(len(raw)):
            cells = [clean(x) for x in raw.iloc[i]] + [''] * 6
            if is_header_row(cells) or not cells[1]:
                continue
            if not pick_idno(cells[3]) and not re.match(r'^\d+$', cells[0]):
                continue
            if re.match(r'^\d+$', cells[0]):
                declared['5'] = max(declared['5'], int(cells[0]))
            add_row('5', Name=cells[1], CoType='SA',
                    InternalID_1=pick_idno(cells[3], True), InternalID_1_type='IDNO',
                    InternalID_2=cells[2], InternalID_2_type='ISIN',
                    Address_1=split_addr(cells[4])[0], Address_2=split_addr(cells[4])[1],
                    City=pick_city(cells[4]), Zip=pick_zip(cells[4]),
                    License_Type='Contract de tinere a registrului cu ' + cells[5] if cells[5] else '')
    print('  list 5: {} entities'.format(counts.get('5', 0)))

# ---------------- List 6: issuers kept by the Central Single Depository (XLSX) ----------------
if '6' in paths:
    print('Working with {} 6 ...'.format(regulatorName))
    raw = pd.read_excel(paths['6'], sheet_name=0, header=None, dtype=str)
    section = ''
    # This workbook RESTARTS its Nr. numbering inside every section banner
    # (BANCI / SOCIETATI DE ASIGURARI / ALTI EMITENTI), so the source-declared total
    # is the SUM of the per-section maxima, never the last number on the sheet.
    secmax = {}
    for i in range(len(raw)):
        cells = [clean(x) for x in raw.iloc[i]] + [''] * 4
        if is_header_row(cells):
            continue
        if cells[1] and not cells[2] and not cells[3] and not cells[0]:
            section = cells[1]                       # e.g. BANCI / ASIGURARI
            continue
        if not cells[1] or not pick_idno(cells[2], True):
            continue
        if re.match(r'^\d+\.?$', cells[0]):
            secmax[section] = max(secmax.get(section, 0), int(cells[0].strip('.')))
        add_row('6', Name=cells[1], CoType=section or 'SA',
                InternalID_1=pick_idno(cells[2], True), InternalID_1_type='IDNO',
                Address_1=split_addr(cells[3])[0], Address_2=split_addr(cells[3])[1],
                City=pick_city(cells[3]), Zip=pick_zip(cells[3]),
                Phone=pick_phone(cells[3]),
                License_Type='Evidenta actiunilor tinuta de Depozitarul Central Unic')
    declared['6'] = sum(secmax.values())
    print('  list 6: {} entities  (sections: {})'.format(counts.get('6', 0), secmax))

# ---------------- List 7: investment funds reorganised into joint-stock companies (.doc) ----
if '7' in paths:
    print('Working with {} 7 ...'.format(regulatorName))
    df7 = doc_table(paths['7'])
    if df7 is None:
        print('SKIPPED - list 7: no table found in the .doc')
    else:
        for i in range(len(df7)):
            cells = [clean(x) for x in df7.iloc[i]] + [''] * 6
            if is_header_row(cells) or not cells[2]:
                continue
            newname = re.split(r'IDNO', cells[2], flags=re.I)[0].strip(' .,;')
            add_row('7', Name=newname or cells[1], CoType='SA',
                    InternalID_1=pick_idno(cells[2]), InternalID_1_type='IDNO',
                    Address_1=split_addr(cells[4])[0], Address_2=split_addr(cells[4])[1],
                    City=pick_city(cells[4]), Zip=pick_zip(cells[4]),
                    Phone=pick_phone(cells[4]), Fax=pick_phone(cells[4], True),
                    License_Type='Fond de investitii reorganizat in societate pe actiuni; '
                                 'denumirea veche: ' + cells[1] if cells[1] else '')
    print('  list 7: {} entities'.format(counts.get('7', 0)))

# ---------------- List 8: trust companies (.doc) ----------------
if '8' in paths:
    print('Working with {} 8 ...'.format(regulatorName))
    df8 = doc_table(paths['8'])
    if df8 is None:
        print('SKIPPED - list 8: no table found in the .doc')
    else:
        for i in range(len(df8)):
            cells = [clean(x) for x in df8.iloc[i]] + [''] * 6
            if is_header_row(cells) or not cells[1]:
                continue
            name = re.split(r'\s+[-–]\s+(?=in proces|î[nn] proces)', cells[1])[0].strip(' .,;')
            name = re.sub(r'\s*[-–]\s*(?:în|in)\s+proces.*$', '', cells[1]).strip(' .,;') or name
            liquidating = 'proces de lichidare' in norm(cells[1])
            add_row('8', Name=name, CoType='Companie fiduciara',
                    Address_1=split_addr(cells[3])[0], Address_2=split_addr(cells[3])[1],
                    City=pick_city(cells[3]), Zip=pick_zip(cells[3]),
                    Phone=pick_phone(cells[4]), Fax=pick_phone(cells[4], True),
                    License_Type='Administrator fiduciar',
                    RegulationType='In liquidation' if liquidating else 'Regulated')
    print('  list 8: {} entities'.format(counts.get('8', 0)))

#---- Begin_writer and save df to excel ----
print('\n================ RECONCILIATION ================')
for code in sorted(topology, key=lambda k: int(k.split(' ')[-1])):
    c = code.split(' ')[-1]
    got = counts.get(c, 0)
    dec = declared.get(c)
    flag = ''
    if dec:
        flag = '   <-- MISMATCH vs source-declared {}'.format(dec) if dec != got else '   (matches source-declared {})'.format(dec)
    print('  list {}  ListLabel={}  rows={:5d}{}   validity={}'.format(
        c, listlabel[c], got, flag, VALIDITY.get(c, '-')))
print('  TOTAL rows: {}'.format(sum(counts.values())))
print('===============================================\n')

lens = {k: len(v) for k, v in sqldict.items()}
assert len(set(lens.values())) == 1, 'column length drift: {}'.format(lens)
assert len(sqldict) == 43, 'schema must have exactly 43 keys, has {}'.format(len(sqldict))
print('Schema OK: 43 columns, all {} rows deep.'.format(list(lens.values())[0]))

os.chdir(scriptfolder)
df = pd.DataFrame(sqldict)
df = df[df['Name'] != '']
df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)
print('Saved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))
