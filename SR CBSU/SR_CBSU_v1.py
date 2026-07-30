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

# ------ OCR wiring: bundled Windows binaries at the repo root (control server) ------
# Put the bundled Tesseract-OCR on PATH and point TESSDATA_PREFIX at its language
# files so image_to_string(lang='eng') can find eng.traineddata. Resolve the bundled
# poppler bin (pdftoppm) so pages can be rendered to images with pdf2image.
projectroot = os.path.dirname(scriptfolder)
_tessdir = os.path.join(projectroot, 'Tesseract-OCR')
if os.path.isdir(_tessdir):
    os.environ['PATH'] = _tessdir + os.pathsep + os.environ.get('PATH', '')
    _tessdata = os.path.join(_tessdir, 'tessdata')
    if not os.path.isdir(_tessdata):
        _tessdata = os.path.join(projectroot, 'tessdata')
    if os.path.isdir(_tessdata):
        os.environ['TESSDATA_PREFIX'] = _tessdata
_poppler = os.path.join(projectroot, 'poppler-25.12.0', 'Library', 'bin')
POPPLER_BIN = _poppler if os.path.isdir(_poppler) else None

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

# Which lists to scrape. Start with [1] to validate the OCR path on the control
# server, then set to [1, 2, 3, 4] to scrape everything.
LISTS_TO_RUN = [1, 2, 3, 4]

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"(?:Tel|Telefoon)[:.\s]*([0-9()+\-/ ]{5,})", re.I)
# A name line starts with an item number. OCR often loses the dot ("2 STICHTING")
# so the separator is optional; the preamble gate (below) keeps intro lines such as
# "4 van de Wet ..." from matching.
NUM_RE = re.compile(r"^\s*(\d{1,3})[.)]?\s+(.+\S)\s*$")
# A bare item-number box with no name merged onto it (the case _rapid_page_lines'
# ytol=22 same-line merge misses). Only trusted as an anchor left of ANCHOR_X_MAX --
# lone page-number stamps in the far-right margin match this shape too.
ANCHOR_NUM_ONLY_RE = re.compile(r"^\s*(\d{1,3})[.)]?\s*$")
ANCHOR_X_MAX = 700
# A company-name line ends with a legal-form suffix (N.V. / G.A.). Used to recover
# an entity whose leading item number was dropped by OCR (e.g. list 1 entry 4,
# 'SURINAAMSE TRUSTMAATSCHAPPIJ N.V.', where RapidOCR never detected the '4.').
NAME_TAIL_RE = re.compile(r"(N\.?\s*V\.?|G\.?\s*A\.?)[\"'»)\s]*$", re.I)
# The BEKENDMAKING closing boilerplate begins here; nothing after it is an entity.
STOP_RE = re.compile(r"Hierin niet genoemde|Houdstermaatschappij", re.I)
# Repeated page-footer / letterhead / signature lines to drop wherever they appear.
NOISE_RE = re.compile(
    r"Telefoon.*Telefax"
    r"|wettelijk gestelde|niet onder het toezicht|staan derhalve|voldoen nog niet"
    r"|ondertoezichtstelling|^Suriname\.?$"
    r"|^Paramaribo,?\s*\d.*20\d\d"
    r"|CENTRALE\s*BANK\s*VAN\s*SURINAME"
    r"|Deputy Governor|Compliance\s*and\s*Internationa|Bancaire Zaken"
    r"|Economische Aangelegenheden|Monetaire Zaken"
    r"|^[FW]\.?\s*(Hausil|Orie)|Soekhnandan"
    r"|^SLRR$|^\d{1,2}$",
    re.I)


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
    """Resolve a tesseract binary (project Tesseract-OCR folder or PATH) and
    confirm it actually runs. The bundled tesseract.exe exists on disk on every
    machine, but on a non-Windows dev box (e.g. the Mac) the Windows binary can't
    execute -- a file-exists check would wrongly pick it and make OCR fail instead
    of falling back to RapidOCR. So we probe the version before accepting it."""
    import pytesseract
    candidates = [
        os.path.join(projectroot, 'Tesseract-OCR', 'tesseract.exe'),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        shutil.which('tesseract') or '',
    ]
    for c in candidates:
        if c and os.path.exists(c):
            pytesseract.pytesseract.tesseract_cmd = c
            try:
                pytesseract.get_tesseract_version()
                return True
            except Exception:
                continue
    return False


def _render_pdf_pages(path):
    """Render each page to an image with the bundled poppler (pdf2image); this is
    robust where pypdf's embedded-image extraction silently returns nothing for
    DCTDecode/JPEG scans on older pypdf builds (the cause of the empty output on
    the control server). Falls back to pypdf's page.images if poppler is absent."""
    images = []
    try:
        from pdf2image import convert_from_path
        images = convert_from_path(path, dpi=300, poppler_path=POPPLER_BIN)
    except Exception as e:
        print(f"   [pdf2image render failed, falling back to pypdf images] {e}")
    if not images:
        import io
        from PIL import Image
        from pypdf import PdfReader
        reader = PdfReader(path)
        for page in reader.pages:
            for img in page.images:
                images.append(Image.open(io.BytesIO(img.data)))
    return images


def ocr_boxes_tesseract(path):
    """OCR via pytesseract. Preferred engine on the Windows production box.
    Returns positioned rows (page, y, x, text) -- grouped by Tesseract's own
    block/paragraph/line numbers -- instead of a joined string, so
    parse_entities_geometric can segment entities by row position rather than
    requiring the item number and name to land on the same merged line."""
    import pytesseract
    from pytesseract import Output
    images = _render_pdf_pages(path)
    boxes = []
    for pi, im in enumerate(images):
        data = pytesseract.image_to_data(im, lang='eng', output_type=Output.DICT)
        rows = {}
        for i in range(len(data['text'])):
            word = data['text'][i].strip()
            if not word:
                continue
            key = (data['block_num'][i], data['par_num'][i], data['line_num'][i])
            rows.setdefault(key, []).append(
                (data['left'][i], data['top'][i] + data['height'][i] / 2.0, word))
        for words in rows.values():
            words.sort(key=lambda w: w[0])
            y = sum(w[1] for w in words) / len(words)
            x = words[0][0]
            boxes.append((pi, y, x, ' '.join(w[2] for w in words)))
    return boxes


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


def _rapid_page_rows(res, ytol=22):
    """Group RapidOCR's per-box output into row-boxes: sort boxes top-to-bottom,
    group boxes whose vertical centres are within `ytol` px into one row (so
    wrapped word-boxes on the same visual line still combine), order left-to-right
    within the row. Unlike the old line-joining version, the row's own position
    (y, x) is kept -- callers need it to segment entities by geometry rather than
    requiring the item number and name to land on the same merged row."""
    items = []
    for box, txt, _score in (res or []):
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        items.append((sum(ys) / 4.0, min(xs), txt))
    items.sort(key=lambda t: (t[0], t[1]))

    def flatten(cur):
        cur.sort(key=lambda t: t[0])  # left to right
        y = sum(t[1] for t in cur) / len(cur)
        return (y, cur[0][0], ' '.join(t[2] for t in cur))

    rows, cur, cy = [], [], None
    for y, x, txt in items:
        if cy is None or abs(y - cy) <= ytol:
            cur.append((x, y, txt))
            cy = y if cy is None else (cy + y) / 2.0
        else:
            rows.append(flatten(cur))
            cur, cy = [(x, y, txt)], y
    if cur:
        rows.append(flatten(cur))
    return rows  # list of (y, x, text)


def ocr_boxes_rapidocr(path):
    """OCR via RapidOCR (PP-OCR / onnxruntime), a pure-Python engine that ships
    its own models and needs no system binary. Page images are pulled with pypdf.
    Returns positioned rows (page, y, x, text) instead of a joined string, so
    parse_entities_geometric can segment entities by row position rather than
    requiring the item number and name to land on the same merged line.
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
    boxes = []
    for pi, page in enumerate(reader.pages):
        for img in page.images:
            im = Image.open(io.BytesIO(img.data)).convert('RGB')
            res, _ = _RAPID_OCR(np.array(im))
            for y, x, txt in _rapid_page_rows(res):
                boxes.append((pi, y, x, txt))
    return boxes


def ocr_boxes(path):
    """Dispatch to the best available OCR engine, returning positioned rows
    (page, y, x, text): tesseract (preferred), else RapidOCR. Raises RuntimeError
    if neither is available."""
    if tesseract_available():
        return ocr_boxes_tesseract(path)
    if rapidocr_available():
        return ocr_boxes_rapidocr(path)
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
    # The BEKENDMAKING preamble ("... maakt bekend, dat ... staan ingeschreven:")
    # ends with a colon; the numbered list begins on the next line. Gating on it
    # also drops the intro's "4 van de Wet ..." that would otherwise match NUM_RE.
    started = False
    for ln in lines:
        stripped = ln.strip()
        if not started:
            if stripped.endswith(':'):
                started = True
            continue
        if STOP_RE.search(stripped):        # closing boilerplate / holding company
            break
        if not stripped or NOISE_RE.search(stripped):
            continue
        m = NUM_RE.match(ln)
        if m:
            if current:
                entities.append(current)
            current = {'name': m.group(2).strip(), 'addr_lines': []}
            continue
        if current is None:
            continue
        # a section sub-header (ends with ':', e.g. "... NIET MEER OPERATIONEEL ZIJN:")
        if stripped.endswith(':'):
            entities.append(current)
            current = None
            continue
        # Recover an entity whose leading item number OCR dropped: an ALL-CAPS line
        # ending in a company suffix (N.V./G.A.) that follows a COMPLETE entity (one
        # that already has an address). The 'has an address' gate is what tells a new
        # entity apart from a multi-line name continuation (where the current entity
        # has no address yet); real section headers never end in N.V./G.A.
        if current['addr_lines'] and stripped.isupper() and NAME_TAIL_RE.search(stripped):
            entities.append(current)
            current = {'name': stripped, 'addr_lines': []}
            continue
        # stop collecting once we hit an ALL-CAPS section header line
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
        # City = token after the last comma, but ignore a trailing status note in
        # parentheses ("(Ingetrokken ...)", "(respondeert niet, ...)") which would
        # otherwise be read as the city. The note stays in Address_1.
        city = ''
        city_src = re.sub(r'\s*\([^)]*\)\s*$', '', addr).rstrip(',').strip()
        if ',' in city_src:
            city = city_src.rsplit(',', 1)[1].strip()
        out.append({'name': e['name'], 'address': addr, 'city': city,
                    'phone': phone, 'email': email})
    return out


def _is_section_header(stripped):
    """ALL-CAPS short line (roman-numeral run titles included, e.g. 'I. PRIMAIRE
    BANKEN') or a line ending in ':' (a run's own sub-heading, e.g. '... NIET MEER
    OPERATIONEEL ZIJN:') -- either closes whatever entity is open and resets the
    anchor state for the next 1..N run."""
    return (stripped.endswith(':')
            or (stripped.isupper() and len(stripped.split()) <= 6 and ',' not in stripped))


def parse_entities_geometric(boxes):
    """Segment numbered entities from positioned OCR rows (page, y, x, text) by
    the position of item-number anchors, instead of requiring the number and name
    to be merged onto one reconstructed text line (parse_entities's approach,
    still used for the text-layer path). A single PDF holds several independent
    1..N runs, one per section heading; each header resets the anchor state the
    same way parse_entities does.

    Fixes entity loss seen with the line-based parser: when OCR places the number
    far from the name, or drops the number/name merge, the previous parser folded
    the real entity's text into the prior entity (or silently dropped a bare digit
    as noise). Here every row keeps its own (page, y, x), so:
      - a bare number row (no name attached) still opens a new entity -- its name
        is recovered from the next content row(s) instead of being discarded;
      - a content run with no active entity (the run's first item never got a
        number at all) still opens an entity instead of being lost;
      - within an entity, once an address line has appeared, a later ALL-CAPS row
        ending in a legal suffix (N.V./G.A.) still splits off as a new entity --
        recovers an entity whose own number was never OCR'd at all.
    Genuinely name-blank slots (the OCR never produced a name at all) still come
    out with name='' and are filtered out downstream like today."""
    import unicodedata
    rows = sorted(
        ((pi, y, x, unicodedata.normalize('NFKC', txt)) for pi, y, x, txt in boxes),
        key=lambda r: (r[0], r[1], r[2]))

    def _scan_ahead_is_header(start_idx):
        """From start_idx onward, skip rows that are themselves ALL-CAPS with no
        comma (name-continuation-shaped or nested-header-shaped -- either way,
        not yet decisive) to find the first row that settles it: a number
        anchor confirms the row being judged really is a header (a numbered
        entity follows, however many more header-shaped lines come first --
        e.g. a colon-ending header immediately followed by a second short
        all-caps sub-header); an address-shaped row (has a comma, or isn't
        all-caps) confirms it's actually unnumbered entity content that only
        happens to look like a header (e.g. a run's first entity whose own
        number was never OCR'd, or an entity whose header-shaped closing row
        is really the *next* entity's name)."""
        for _pi2, _y2, x2, txt2 in rows[start_idx:]:
            s2 = txt2.strip()
            if not s2:
                continue
            if STOP_RE.search(s2):
                break
            if (ANCHOR_NUM_ONLY_RE.match(s2) and x2 < ANCHOR_X_MAX) or NUM_RE.match(s2):
                return True
            if ',' in s2 or not s2.isupper():
                return False
        return True

    entities = []
    current = None        # {'name': str, 'addr_lines': [str]}
    started = False        # preamble gate, same semantics as parse_entities()

    def close_current():
        nonlocal current
        if current:
            entities.append(current)
        current = None

    for i, (_pi, _y, x, txt) in enumerate(rows):
        stripped = txt.strip()
        if not stripped:
            continue
        if not started:
            if stripped.endswith(':'):
                started = True
            continue
        if STOP_RE.search(stripped):        # closing boilerplate / holding company
            break

        m_bare = ANCHOR_NUM_ONLY_RE.match(stripped)
        if m_bare and x < ANCHOR_X_MAX:
            close_current()
            current = {'name': '', 'addr_lines': []}
            continue

        m_num = NUM_RE.match(stripped)
        if m_num:
            close_current()
            current = {'name': m_num.group(2).strip(), 'addr_lines': []}
            continue

        if NOISE_RE.search(stripped):
            continue

        # Still-open, possibly multi-row name (e.g. "...G.A.(SPAAR EN KREDIET
        # KOOPERATIE" then "A.D.B.)", or "SURIFAST MONEY EXCHANGE N.V." then
        # "(VOORHEEN JOHN-RUS EXCHANGE N.V.)") must win over the section-header
        # check below: a short ALL-CAPS continuation fragment looks exactly like
        # a header (<=6 words, no comma) but is really the rest of the name. No
        # address line has been seen yet for this entity -- that's what tells a
        # continuation apart from a genuine header, regardless of whether the
        # name started from a bare anchor or one merged with the item number.
        if current is not None and not current['addr_lines'] and stripped.isupper():
            current['name'] = (current['name'] + ' ' + stripped).strip()
            continue

        # An ALL-CAPS line ending in a legal suffix (N.V./G.A.), arriving once an
        # address has already started, is an entity whose own number was never
        # OCR'd at all (e.g. "SURINAAMSETRUSTMAATSCHAPPIJN.V." -- one glued word,
        # so it also happens to look like a short section header). Must be
        # checked before _is_section_header: real section headers in this data
        # never end in N.V./G.A., so this can't misfire on a genuine header.
        if current is not None and current['addr_lines'] and stripped.isupper() \
                and NAME_TAIL_RE.search(stripped):
            close_current()
            current = {'name': stripped, 'addr_lines': []}
            continue

        if _is_section_header(stripped):
            # Always ambiguous, whether or not an entity is currently open: this
            # row could be a genuine (possibly second, back-to-back) section
            # header -- e.g. a colon-ending header immediately followed by a
            # short all-caps sub-header, "PENSIOEN- EN VOORZIENINGSFONDSEN ...
            # ZIJN:" then "PENSIOENFONDSEN" -- or it could actually be an
            # entity's own name whose number box was never OCR'd, which just
            # happens to be short/glued ALL-CAPS and so is equally
            # header-shaped. That mis-shaped name can surface two ways: as a
            # run's first entity (current is None, e.g. "PENSIOENFONDSEN"
            # header directly followed by "STICHTINGPENSIOENFONDS...
            # WATERLEIDING"), or as the very row that appears to close a
            # *different*, already-open entity while really starting the next
            # one (current is not None, e.g. entry 2's address is still
            # accumulating when "STICHTING PENSIOENFONDS VOOR DE..." arrives --
            # that row must close entry 2 *and* seed a new entity from itself,
            # not be discarded). Tell genuine headers apart from either case by
            # what comes right after: a genuine header's own first entity is
            # introduced by a number anchor (however many more header-shaped
            # lines intervene); a mis-shaped name is instead followed directly
            # by address content (a comma, or non-upper text) with no number
            # ever appearing first.
            if _scan_ahead_is_header(i + 1):
                close_current()
                continue
            close_current()
            current = {'name': stripped, 'addr_lines': []}
            continue

        if current is None:
            current = {'name': '', 'addr_lines': []}
            if stripped.isupper():
                current['name'] = stripped
                continue
            current['addr_lines'].append(stripped)
            continue

        current['addr_lines'].append(stripped)
    close_current()

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
        city_src = re.sub(r'\s*\([^)]*\)\s*$', '', addr).rstrip(',').strip()
        if ',' in city_src:
            city = city_src.rsplit(',', 1)[1].strip()
        out.append({'name': e['name'], 'address': addr, 'city': city,
                    'phone': phone, 'email': email})
    return out


# ------------------------------------------------ Begin_ scraping ----------------------------------------
links = discover_pdf_links()
print("Discovered PDF links:")
for nr in sorted(links):
    print(f"  List {nr} ({LISTS[nr][0]}): {links[nr]}")

blocked = []
for nr in LISTS_TO_RUN:
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
        # None of the 4 CBSU PDFs have a text layer today, so this path is
        # dormant; left as-is (line-based parse_entities), no need for the
        # geometric parser here since there's no box position to segment by.
        text = extract_text(pdf_path)
        entities = parse_entities(text)
    else:
        # Scanned-image PDF (no text layer). OCR with tesseract (preferred) or RapidOCR,
        # then segment entities by OCR box geometry (position), not same-line text
        # merging -- see parse_entities_geometric for why.
        if tesseract_available() or rapidocr_available():
            engine = 'tesseract' if tesseract_available() else 'rapidocr'
            print(f"[INFO] List {nr} ({listname}): no text layer -> running OCR ({engine})")
            try:
                boxes = ocr_boxes(pdf_path)
                entities = parse_entities_geometric(boxes)
            except Exception as e:
                print(f"[WARN] List {nr} ({listname}): OCR failed ({e})")
                entities = []
        else:
            print(f"[BLOCKED] List {nr} ({listname}): scanned-image PDF, no text layer, "
                  f"no OCR engine (tesseract / rapidocr) -> needs OCR on Windows box. Not fabricating.")
            blocked.append((nr, listname, 'scanned image, needs OCR (no engine available)'))
            continue

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
