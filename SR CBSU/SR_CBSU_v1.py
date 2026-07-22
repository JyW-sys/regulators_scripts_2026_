# ------------------------------------------------ Import Lib ----------------------------------------
import os
import re
import shutil
import datetime
import requests
import pandas as pd
from urllib.parse import urljoin
from bs4 import BeautifulSoup

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ------------------------------------------------ Begin_ fileName ----------------------------------------
regulatorName = 'SR CBSU'  # Central Bank of Suriname (Centrale Bank van Suriname)

print(f"Running {regulatorName} Web Scraping Tool v.1.0")

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":", ".")[:-7])

# ------ define the workspace path -----
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))  # production environment (.py)
except NameError:
    scriptfolder = os.getcwd()  # notebook environment
os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder')  # PDFs are downloaded here
os.makedirs(tempfolder, exist_ok=True)

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'}
LANDING = 'https://www.cbvs.sr/en/financial-system/payments-systems/suriname-financial-institutions/financial-institutions'

# ------------------------------------------------ sqldict (DO NOT CHANGE STRUCTURE) ----------------------------------------
sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}


def bourange_same_length_array(sqldict):
    maxlen = max(len(v) for v in sqldict.values())
    for key in sqldict:
        if len(sqldict[key]) != maxlen:
            sqldict[key].extend([''] * (maxlen - len(sqldict[key])))
    return sqldict


# ------------------------------------------------ List metadata ----------------------------------------
# ListNr -> (ListName, ListLabel). ListLabel: 1=bank, 2=insurance, 3=both, 4=everything else.
LISTS = {
    1: ('Other Depository Corporations', 1),
    2: ('Insurance Companies', 2),
    3: ('Pension- and Provident funds', 4),
    4: ('Money Exchange and Money Transfer Houses', 4),
}

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"(?:Tel|Telefoon)[:.\s]*([0-9()+\-/ ]{5,})", re.I)
# A name line starts with an item number: "1.  REPUBLIC BANK (SURINAME) N.V."
NUM_RE = re.compile(r"^\s*(\d{1,3})[.)]\s+(.+\S)\s*$")


def discover_pdf_links():
    """Fetch the landing page and return {ListNr: pdf_url} by matching the
    'Click here for the <ListName>' paragraphs in the article body."""
    r = requests.get(LANDING, headers=HEADERS, verify=False, timeout=60)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')
    main = (soup.find('div', itemprop='articleBody')
            or soup.find('article')
            or soup.find('div', class_=lambda c: c and 'item-page' in c)
            or soup)
    found = {}
    for p in main.find_all('p'):
        txt = p.get_text(' ', strip=True)
        low = txt.lower()
        if 'click here for the' not in low:
            continue
        a = p.find('a', href=True)
        if not a:
            continue
        href = urljoin(LANDING, a['href'])
        for nr, (name, _label) in LISTS.items():
            if name.lower() in low:
                found[nr] = href
                break
    return found


def download_pdf(url, dest):
    r = requests.get(url, headers=HEADERS, verify=False, timeout=120)
    r.raise_for_status()
    with open(dest, 'wb') as f:
        f.write(r.content)
    return dest


def pdf_has_text_layer(path):
    """True if the PDF carries any real text (not a pure scanned image)."""
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            if page.chars:
                return True
    return False


def extract_text(path):
    """pdfplumber first; camelot(stream) then tabula as fallback. Returns text."""
    import pdfplumber
    chunks = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ''
            if t.strip():
                chunks.append(t)
    if chunks:
        return '\n'.join(chunks)

    # ---- fallback 1: camelot (flavor='stream') ----
    try:
        import camelot
        tables = camelot.read_pdf(path, pages='all', flavor='stream')
        rows = []
        for t in tables:
            for _, row in t.df.iterrows():
                rows.append(' '.join(str(c) for c in row if str(c).strip()))
        if any(r.strip() for r in rows):
            return '\n'.join(rows)
    except Exception as e:
        print(f"   [camelot fallback skipped] {e}")

    # ---- fallback 2: tabula ----
    try:
        import tabula
        dfs = tabula.read_pdf(path, pages='all', stream=True, silent=True)
        rows = []
        for d in dfs:
            for _, row in d.iterrows():
                rows.append(' '.join(str(c) for c in row if str(c) and str(c) != 'nan'))
        if any(r.strip() for r in rows):
            return '\n'.join(rows)
    except Exception as e:
        print(f"   [tabula fallback skipped] {e}")

    return ''


def tesseract_available():
    """Resolve a tesseract binary (project Tesseract-OCR folder or PATH)."""
    import pytesseract
    candidates = [
        os.path.join(os.path.dirname(scriptfolder), 'Tesseract-OCR', 'tesseract.exe'),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        shutil.which('tesseract') or '',
    ]
    for c in candidates:
        if c and os.path.exists(c):
            pytesseract.pytesseract.tesseract_cmd = c
            return True
    if shutil.which('tesseract'):
        return True
    return False


def ocr_text_tesseract(path):
    """OCR via pytesseract. Extracts the embedded page image with pypdf (no
    poppler needed). Preferred engine on the Windows production box."""
    import pytesseract
    from PIL import Image
    import io
    from pypdf import PdfReader
    reader = PdfReader(path)
    chunks = []
    for page in reader.pages:
        for img in page.images:
            im = Image.open(io.BytesIO(img.data))
            chunks.append(pytesseract.image_to_string(im, lang='eng'))
    return '\n'.join(chunks)


def rapidocr_available():
    """True if the pure-Python RapidOCR (onnxruntime) engine is importable.
    Needs no system binary, so it works where tesseract cannot be installed
    (e.g. the corporate Mac)."""
    try:
        import rapidocr_onnxruntime  # noqa: F401
        return True
    except Exception:
        return False


_RAPID_OCR = None


def _rapid_page_lines(res, ytol=22):
    """Rebuild text lines from RapidOCR's per-box output: sort boxes top-to-bottom,
    group boxes whose vertical centres are within `ytol` px into one line, order
    left-to-right within the line. This re-joins the item number ('1.') with the
    name box on the same row, giving the '1.  NAME' layout parse_entities expects."""
    items = []
    for box, txt, _score in (res or []):
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        items.append((sum(ys) / 4.0, min(xs), txt))
    items.sort(key=lambda t: (t[0], t[1]))
    lines, cur, cy = [], [], None
    for y, x, txt in items:
        if cy is None or abs(y - cy) <= ytol:
            cur.append((x, txt))
            cy = y if cy is None else (cy + y) / 2.0
        else:
            cur.sort()
            lines.append(' '.join(t for _, t in cur))
            cur, cy = [(x, txt)], y
    if cur:
        cur.sort()
        lines.append(' '.join(t for _, t in cur))
    return lines


def ocr_text_rapidocr(path):
    """OCR via RapidOCR (PP-OCR / onnxruntime), a pure-Python engine that ships
    its own models and needs no system binary. Page images are pulled with pypdf.
    NOTE: PP-OCR occasionally drops spaces inside tightly-kerned all-caps names
    (e.g. 'SURINAAMSEPOSTSPAARBANK'); such names are flagged for QA, not fixed."""
    import io
    import numpy as np
    from PIL import Image
    from pypdf import PdfReader
    from rapidocr_onnxruntime import RapidOCR
    global _RAPID_OCR
    if _RAPID_OCR is None:
        _RAPID_OCR = RapidOCR()
    reader = PdfReader(path)
    lines = []
    for page in reader.pages:
        for img in page.images:
            im = Image.open(io.BytesIO(img.data)).convert('RGB')
            res, _ = _RAPID_OCR(np.array(im))
            lines.extend(_rapid_page_lines(res))
    return '\n'.join(lines)


def ocr_text(path):
    """Dispatch to the best available OCR engine: tesseract (preferred), else
    RapidOCR. Raises RuntimeError if neither is available."""
    if tesseract_available():
        return ocr_text_tesseract(path)
    if rapidocr_available():
        return ocr_text_rapidocr(path)
    raise RuntimeError('no OCR engine available (need tesseract or rapidocr-onnxruntime)')


def parse_entities(text):
    """Parse the CBvS 'BEKENDMAKING' numbered layout:
        '1.  ENTITY NAME N.V.'
        '    Street 1, Paramaribo'
    Returns list of dicts. The address line(s) following a numbered name line
    (until the next numbered line / blank gap) are captured; City = token after
    the last comma; Phone/Email pulled by regex if present."""
    # OCR sometimes emits fullwidth punctuation (e.g. '，' U+FF0C instead of ',').
    # NFKC folds those back to ASCII so comma-based City/address splitting works.
    import unicodedata
    text = unicodedata.normalize('NFKC', text)
    lines = [ln.rstrip() for ln in text.splitlines()]
    entities = []
    current = None
    for ln in lines:
        m = NUM_RE.match(ln)
        if m:
            if current:
                entities.append(current)
            current = {'name': m.group(2).strip(), 'addr_lines': []}
        elif current is not None and ln.strip():
            # stop collecting once we hit an ALL-CAPS section header line
            stripped = ln.strip()
            if stripped.isupper() and len(stripped.split()) <= 6 and ',' not in stripped:
                entities.append(current)
                current = None
                continue
            current['addr_lines'].append(stripped)
    if current:
        entities.append(current)

    out = []
    for e in entities:
        addr = ' '.join(e['addr_lines']).strip()
        phone = ''
        pm = PHONE_RE.search(addr)
        if pm:
            phone = pm.group(1).strip()
            addr = addr[:pm.start()].strip().rstrip(',').strip()
        email = ''
        em = EMAIL_RE.search(addr)
        if em:
            email = em.group(0)
            addr = EMAIL_RE.sub('', addr).strip().rstrip(',').strip()
        city = ''
        if ',' in addr:
            city = addr.rsplit(',', 1)[1].strip()
        out.append({'name': e['name'], 'address': addr, 'city': city,
                    'phone': phone, 'email': email})
    return out


# ------------------------------------------------ Begin_ scraping ----------------------------------------
links = discover_pdf_links()
print("Discovered PDF links:")
for nr in sorted(links):
    print(f"  List {nr} ({LISTS[nr][0]}): {links[nr]}")

blocked = []
for nr in sorted(LISTS):
    listname, listlabel = LISTS[nr]
    url = links.get(nr)
    if not url:
        print(f"[WARN] List {nr} ({listname}): link not found on landing page -> skipped")
        blocked.append((nr, listname, 'link not found'))
        continue

    pdf_path = os.path.join(tempfolder, f"list{nr}.pdf")
    try:
        download_pdf(url, pdf_path)
    except Exception as e:
        print(f"[WARN] List {nr} ({listname}): download failed ({e}) -> skipped")
        blocked.append((nr, listname, f'download failed: {e}'))
        continue

    if pdf_has_text_layer(pdf_path):
        # Text-based PDF: pdfplumber first, camelot(stream)/tabula as fallback.
        text = extract_text(pdf_path)
    else:
        # Scanned-image PDF (no text layer). OCR with tesseract (preferred) or RapidOCR.
        if tesseract_available() or rapidocr_available():
            engine = 'tesseract' if tesseract_available() else 'rapidocr'
            print(f"[INFO] List {nr} ({listname}): no text layer -> running OCR ({engine})")
            try:
                text = ocr_text(pdf_path)
            except Exception as e:
                print(f"[WARN] List {nr} ({listname}): OCR failed ({e})")
                text = ''
        else:
            print(f"[BLOCKED] List {nr} ({listname}): scanned-image PDF, no text layer, "
                  f"no OCR engine (tesseract / rapidocr) -> needs OCR on Windows box. Not fabricating.")
            blocked.append((nr, listname, 'scanned image, needs OCR (no engine available)'))
            continue

    entities = parse_entities(text)
    entities = [e for e in entities if e['name']]
    if not entities:
        print(f"[BLOCKED] List {nr} ({listname}): no entities parsed from extracted text -> needs review.")
        blocked.append((nr, listname, 'no entities parsed'))
        continue

    for e in entities:
        sqldict['Name'].append(e['name'])
        sqldict['Address_1'].append(e['address'])
        sqldict['City'].append(e['city'])
        sqldict['Phone'].append(e['phone'])
        sqldict['Email'].append(e['email'])
        sqldict['Cntry'].append('SR')
        sqldict['RegulationType'].append('Regulated')
        sqldict['ListName'].append(listname)
        sqldict['ListLabel'].append(listlabel)
        sqldict['ListLanguage'].append('EN')
        sqldict['RegCtry'].append('SR')
        sqldict['RegCode'].append('CBSU')
        sqldict['ListCode'].append(nr)
        sqldict['ListProcessDate'].append(processdate)
        sqldict = bourange_same_length_array(sqldict)

    print(f"[OK] List {nr} ({listname}): {len(entities)} entities")

# ------------------------------------------------ save df to excel ----------------------------------------
os.chdir(scriptfolder)
df = pd.DataFrame(sqldict)
df = df[df['Name'] != '']
df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)
print('Saved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))

if blocked:
    print("\nBLOCKED / empty lists:")
    for nr, name, why in blocked:
        print(f"  List {nr} ({name}): {why}")
