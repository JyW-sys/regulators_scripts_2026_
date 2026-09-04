# -*- coding: utf-8 -*-
"""
BI BRB - Banque de la Republique du Burundi
Jira: DECD-6976

Three lists, three completely different page technologies:

  1  Banking Supervision   https://www.brb.bi/node/119   free-text <p> blocks, entity name in bold
  2  Microfinance Superv.  https://www.brb.bi/node/120   12 scanned PNG images (no text layer) -> OCR
  3  Payment Systems       https://www.brb.bi/node/2928  HTML table, first table only

List 2 used to be HTML text (see BI_BRB_v2.ipynb) but the BRB replaced the whole
node body with page images, so the only way to read it is OCR. We use img2table
for the ruled-table geometry (OpenCV line detection, resolution independent) and
a per-machine OCR engine for the glyphs - that combination keeps the French
accents, which a plain full-page OCR pass does not.

OCR ENGINE: Tesseract when the binary is on PATH (the Windows control server -
the repo bundles Tesseract-OCR/), RapidOCR only as a fallback for machines with
no tesseract (the Mac: no brew, no admin). See resolve_ocr(). Both imports live
inside their branch on purpose - v3 first shipped with an unconditional
`from img2table.ocr import RapidOCR` and died on the control server with
`ImportError: cannot import name 'RapidOCR' from 'img2table.ocr'` because that
box runs Python 3.8 with an img2table predating the RapidOCR backend.

NOTE ON PRINTING: the production console is cp1252. Nothing scraped from the
site is ever printed - only counts and ASCII status lines.

@author: JyW
Created 2026-09-03
"""

import datetime
import os
import re
import shutil
import subprocess
import unicodedata

import pandas as pd
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------- workspace --
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))   # production (.py)
except NameError:
    scriptfolder = os.getcwd()                                  # notebook

os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder')
if not os.path.exists(tempfolder):
    os.mkdir(tempfolder)

# ----------------------------------------------------------------- constants --
REGULATOR = 'BI BRB'
REGCTRY = 'BI'
REGCODE = 'BRB'
LISTLANGUAGE = 'FR'
CNTRY = 'BI'

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = '{} SQL Ready {}.xlsx'.format(REGULATOR, str(now).replace(':', '.')[:-7])

# ListLabel: 1 = bank, 2 = insurance, 3 = bank & insurance, 4 = everything else.
#   list 1 - commercial banks + the central bank + financial establishments -> 1
#   list 2 - microfinance institutions. Not literally a "bank" list; follows the
#            KH NBC / TJ NBTAJ precedent of classifying microfinance as 4.
#            FLAGGED for review: cat.1 and cat.3 MFIs do take deposits.
#   list 3 - payment institutions / e-money issuers / aggregators -> 4
REGLIST = {
    '1': {'ListName': 'List of "Banking Supervision"',
          'URL': 'https://www.brb.bi/node/119',
          'ListLabel': 1},
    '2': {'ListName': 'List of "Microfinance Supervision"',
          'URL': 'https://www.brb.bi/node/120',
          'ListLabel': 4},
    '3': {'ListName': 'List of "Payment Systems"',
          'URL': 'https://www.brb.bi/node/2928',
          'ListLabel': 4},
}

HEADERS = {'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/124.0.0.0 Safari/537.36'),
           'Accept-Language': 'fr,en;q=0.8'}

# The frozen schema. Do not add, remove or rename a key.
SQLDICT_KEYS = ['bvdid', 'priority', 'ListLabel', 'Typology', 'EntryType', 'Name', 'InternalID_1',
                'InternalID_1_type', 'InternalID_2', 'InternalID_2_type', 'InternalID_3',
                'InternalID_3_type', 'CoType', 'License_Type', 'Address_1', 'Address_2', 'City',
                'Zip', 'Cntry', 'Phone', 'Fax', 'Website', 'Email', 'RegulationType',
                'RegulationTypeCode', 'RegulationDate', 'CancellationDate', 'RegCtry', 'RegCode',
                'ListCode', 'ListLanguage', 'ListValidityDate', 'ListName', 'ListProcessDate',
                'LEI Code', 'BIC SWIFT Code', 'Name - Mother Company', 'Address_1 - Mother company',
                'Address_2 -  Mother company', 'City - Mother company', 'Zip - Mother company',
                'Cntry - Mother company', 'Phone - Mother company']

sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}

assert list(sqldict.keys()) == SQLDICT_KEYS, 'frozen sqldict schema drifted'


def add_row(**kw):
    """Append one record, filling every frozen key so the frame can never go ragged."""
    unknown = set(kw) - set(SQLDICT_KEYS)
    if unknown:
        raise KeyError('not part of the frozen schema: {}'.format(sorted(unknown)))
    for key in SQLDICT_KEYS:
        sqldict[key].append(kw.get(key, ''))


# ------------------------------------------------------------------ helpers --
NBSP = ' '


def clean(text):
    """Collapse NBSP / repeated whitespace. Keeps accents untouched."""
    if text is None:
        return ''
    # img2table leaves empty cells as float('nan'); str() would turn that into
    # the literal 'nan' and manufacture a phantom row.
    if isinstance(text, float) and text != text:
        return ''
    text = str(text).replace(NBSP, ' ').replace(' ', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def deaccent(text):
    """Accent-stripped lowercase copy - for MATCHING ONLY, never for output."""
    text = unicodedata.normalize('NFKD', clean(text).lower())
    return ''.join(c for c in text if not unicodedata.combining(c))


FR_MONTHS = {'janvier': 1, 'fevrier': 2, 'mars': 3, 'avril': 4, 'mai': 5, 'juin': 6,
             'juillet': 7, 'aout': 8, 'septembre': 9, 'octobre': 10, 'novembre': 11,
             'decembre': 12}


def french_date_to_iso(text):
    """'au 24 aout 2026' / 'au 09 Fevrier 2026' -> '2026-08-24'. '' when not found."""
    m = re.search(r'(\d{1,2})\s+([a-z]+)\s+(\d{4})', deaccent(text))
    if not m:
        return ''
    month = FR_MONTHS.get(m.group(2))
    if not month:
        return ''
    try:
        return datetime.date(int(m.group(3)), month, int(m.group(1))).isoformat()
    except ValueError:
        return ''


PHONE_RE = re.compile(r'(?:\(?\+?\d{1,4}\)?[\s.\-]*)?\d{2,4}(?:[\s.\-]\d{2,4}){1,4}')


def first_phone(text):
    """First plausible phone number in a free-text blob."""
    text = clean(text)
    m = PHONE_RE.search(text)
    if not m:
        return ''
    return re.sub(r'\s+', ' ', m.group(0)).strip(' .-')


# Burundi provinces / main towns, used only to sanity-check the city guess.
BI_PLACES = ['Bubanza', 'Bujumbura', 'Bururi', 'Cankuzo', 'Cibitoke', 'Gitega', 'Karuzi',
             'Kayanza', 'Kirundo', 'Makamba', 'Muramvya', 'Muyinga', 'Mwaro', 'Ngozi',
             'Rumonge', 'Rutana', 'Ruyigi', 'Bukirasazi', 'Kabezi', 'Kibondo', 'Nyanza-Lac',
             'Kiremba', 'Gihosha', 'Kinama', 'Ngagara', 'Rohero', 'Musaga', 'Kamenge']


def city_from_address(address):
    """
    Burundi addresses read 'Bujumbura Mairie, Avenue ...' or 'Province Cibitoke, ...'
    or 'Commune Rumonge, ...'. Take the first segment and strip the administrative
    words; fall back to any known place name appearing anywhere in the address.
    """
    address = clean(address)
    if not address:
        return ''
    head = re.split(r'[,;]', address)[0]
    head = re.sub(r'(?i)\b(province|commune|mairie|zone|quartier|de|du)\b', ' ', head)
    head = clean(head)
    for place in BI_PLACES:
        if deaccent(place) in deaccent(head):
            return place
    for place in BI_PLACES:
        if re.search(r'\b' + re.escape(deaccent(place)) + r'\b', deaccent(address)):
            return place
    return head if 0 < len(head) <= 40 else ''


def fetch(url, session):
    resp = session.get(url, headers=HEADERS, verify=False, timeout=90)
    resp.raise_for_status()
    resp.encoding = 'utf-8'          # the site is UTF-8; pin it so accents survive
    return resp


# ============================================================================
# LIST 1 - Banking Supervision (node/119)
# ============================================================================
# Page layout, one <p> per line:
#     <li>  SECTEUR BANCAIRE                 <- sector heading
#     <p>   A. BANQUE CENTRALE               <- category heading
#     <p>   BANQUE DE LA REPUBLIQUE DU ...   <- entity name
#     <p>   Code Swift : ... / NIF : ... / Tel ... / Courriel: ...
#     <p>   B. LES BANQUES COMMERCIALES      <- category heading
#     <p>   1. LA BANCOBU                    <- entity heading (short name)
#     <p>   BANQUE COMMERCIALE DU BURUNDI    <- entity name (official)
#     <p>   SOCIETE MIXTE                    <- legal form
#     ...
# The <strong> tagging is inconsistent (some entries bold the short name, some the
# official name, some both), so entity boundaries are taken from the numbered
# heading pattern instead of from the markup.

CATEGORY_HEADINGS = [
    (r'^a\s*\.\s*banque centrale', 'Banque Centrale'),
    (r'^b\s*\.\s*les banques commerciales', 'Banque Commerciale'),
    (r'^etablissements? financiers?', 'Etablissement Financier'),
    (r'^secteur bancaire', None),          # sector heading, carries no category
]

LEGAL_FORMS = ['societe mixte', 'societe anonyme', 'societe annonyme', 'societe publique',
               'societe cooperative']

ENTITY_HEADING_RE = re.compile(r'^\s*\d{1,2}\s*\.\s+\S')


def flush_entity(entity, listcode, meta, validity):
    if not entity or not entity.get('Name'):
        return 0
    add_row(
        ListLabel=meta['ListLabel'],
        Name=entity['Name'],
        InternalID_1=entity.get('NIF', ''),
        InternalID_1_type='NIF' if entity.get('NIF') else '',
        CoType=entity.get('CoType', ''),
        License_Type=entity.get('License_Type', ''),
        Address_1=entity.get('Address_1', ''),
        City=city_from_address(entity.get('Address_1', '')),
        Cntry=CNTRY,
        Phone=entity.get('Phone', ''),
        Fax=entity.get('Fax', ''),
        Website=entity.get('Website', ''),
        Email=entity.get('Email', ''),
        RegulationType='Regulated',
        RegulationDate=entity.get('RegulationDate', ''),
        RegCtry=REGCTRY,
        RegCode=REGCODE,
        ListCode=listcode,
        ListLanguage=LISTLANGUAGE,
        ListValidityDate=validity,
        ListName=meta['ListName'],
        ListProcessDate=processdate,
        **{'BIC SWIFT Code': entity.get('BIC SWIFT Code', '')}
    )
    return 1


def parse_list1(soup, listcode, meta):
    section = soup.find('section', id='block-solo-content')
    if section is None:
        raise RuntimeError('list 1: content section not found - page layout changed')

    lines = []
    for node in section.find_all(['p', 'li']):
        text = clean(node.get_text(' ', strip=True))
        if text:
            lines.append(text)
    if not lines:
        raise RuntimeError('list 1: content section holds no text - page layout changed')

    category = ''
    entity = None
    expect_name = False
    kept = 0

    for text in lines:
        low = deaccent(text)

        # --- category / sector headings -------------------------------------
        heading_hit = False
        for pattern, label in CATEGORY_HEADINGS:
            if re.match(pattern, low):
                kept += flush_entity(entity, listcode, meta, '')
                entity = None
                heading_hit = True
                if label:
                    category = label
                    # 'A. BANQUE CENTRALE' is followed directly by the entity name,
                    # with no numbered heading in between.
                    expect_name = (label == 'Banque Centrale')
                    if expect_name:
                        entity = {'License_Type': category}
                break
        if heading_hit:
            continue

        # --- new numbered entity --------------------------------------------
        if ENTITY_HEADING_RE.match(text):
            kept += flush_entity(entity, listcode, meta, '')
            entity = {'License_Type': category}
            expect_name = True
            continue

        if entity is None:
            continue

        # --- the line straight after a heading is the official name ----------
        if expect_name:
            if ':' not in text and low not in LEGAL_FORMS:
                entity['Name'] = text
                expect_name = False
                continue
            expect_name = False   # fall through and treat it as a detail line

        # --- legal form ------------------------------------------------------
        if low in LEGAL_FORMS:
            entity['CoType'] = text
            continue

        value = text.split(':', 1)[1].strip() if ':' in text else text

        if 'capital social' in low:
            continue                                   # share capital: no schema slot
        elif low.startswith('nif'):
            entity['NIF'] = value
        elif 'swift' in low:
            entity['BIC SWIFT Code'] = value
        elif low.startswith('date de creation') or low.startswith("date d'obtention") \
                or low.startswith("date d'agrement"):
            entity.setdefault('RegulationDate', value)
        elif low.startswith('tel') or low.startswith('telephone'):
            entity.setdefault('Phone', first_phone(value))
            fax = re.search(r'(?i)fax\s*:?\s*([^,;]*)', text)
            if fax and not entity.get('Fax'):
                entity['Fax'] = first_phone(fax.group(1))
        elif low.startswith('fax'):
            entity.setdefault('Fax', first_phone(value))
        elif 'courriel' in low or 'courrie' in low or '@' in text:
            m = re.search(r'[\w.\-+]+@[\w.\-]+', text)
            if m:
                entity.setdefault('Email', m.group(0))
        elif 'site web' in low or low.startswith('web'):
            entity.setdefault('Website', value)
        elif re.search(r'\bb\.?\s?p\b', low) or 'avenue' in low or 'boulevard' in low:
            entity['Address_1'] = (entity.get('Address_1', '') + ', ' + text).strip(', ')

    kept += flush_entity(entity, listcode, meta, '')
    return kept


# ============================================================================
# LIST 2 - Microfinance Supervision (node/120) - scanned images, OCR
# ============================================================================
# The node body is 12 PNG page images. Wanted: the first three categories only
# (the ticket excludes 'Institutions de microfinance de quatrieme categorie').
# Category 2 is declared empty on the page itself.

ORDINALS = {'premiere': 1, 'deuxieme': 2, 'troisieme': 3, 'quatrieme': 4, 'cinquieme': 5}

# Stored as a value, so it carries its accents - deaccent() is for matching only.
CAT_LABEL = {1: 'Institution de microfinance de première catégorie',
             2: 'Institution de microfinance de deuxième catégorie',
             3: 'Institution de microfinance de troisième catégorie'}

WANTED_CATEGORIES = (1, 2, 3)

HEADER_LABELS = {'nom de l institution': 'Name',
                 'nom de linstitution': 'Name',
                 'forme juridique': 'CoType',
                 'adresse du siege': 'Address',
                 'date d agrement': 'RegulationDate',
                 'date dagrement': 'RegulationDate'}

# Matched as substrings so a header cell that OCR merged - 'Forme juridique
# Adresse du siege' happens on the first page - still resolves to two columns.
LABEL_PATTERNS = [('Name', 'nom de l institution'),
                  ('Name', 'nom de linstitution'),
                  ('CoType', 'forme juridique'),
                  ('Address', 'adresse du siege'),
                  ('RegulationDate', 'date d agrement'),
                  ('RegulationDate', 'date dagrement')]


def _norm_label(text):
    return re.sub(r'[^a-z ]', ' ', re.sub(r'\s+', ' ', deaccent(text))).strip()


def download_list2_images(soup, session):
    """Image srcs in DOCUMENT order (the filenames are not in reading order)."""
    section = soup.find('section', id='block-solo-content')
    if section is None:
        raise RuntimeError('list 2: content section not found')
    srcs = [img.get('src') for img in section.find_all('img') if img.get('src')]
    if not srcs:
        raise RuntimeError('list 2: no page images found - the node body changed again')

    paths = []
    for src in srcs:
        url = src if src.startswith('http') else 'https://www.brb.bi' + src
        local = os.path.join(tempfolder, os.path.basename(url.split('?')[0]))
        if not os.path.exists(local):
            resp = session.get(url, headers=HEADERS, verify=False, timeout=180)
            resp.raise_for_status()
            with open(local, 'wb') as handle:
                handle.write(resp.content)
        paths.append(local)
    return paths


def split_pages(path):
    """
    Each PNG holds two to four landscape pages stacked vertically (image_4 is
    6440px tall). RapidOCR's detector rescales whatever it is handed, so a tall
    stack is read at a fraction of the resolution of a single page and the
    recognition falls apart - that is what turned 'Societe Cooperative' into
    noise on the tall pages. Cut the stack at the blank bands between pages
    (no table ever crosses one) and OCR each page on its own.

    Returns a list of file paths, in reading order.
    """
    import cv2
    import numpy as np
    from PIL import Image as PILImage

    gray = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if gray is None:
        return [path]
    height, width = gray.shape[:2]

    blank = (gray < 200).sum(axis=1) <= width * 0.002
    cuts, start = [], None
    for y, is_blank in enumerate(blank):
        if is_blank and start is None:
            start = y
        elif not is_blank and start is not None:
            # Only the band between two printed pages is this tall; the gaps
            # inside a page are smaller and must not become cut points.
            if y - start >= 100 and start > 0:
                cuts.append((start + y) // 2)
            start = None

    interior = [c for c in cuts if 200 < c < height - 200]
    if not interior:
        return [path]

    # Keep every boundary that leaves a full-size page behind it, and never drop
    # a band: a short leftover is merged into its neighbour instead.
    bounds = [0]
    for cut in interior:
        if cut - bounds[-1] >= 400:
            bounds.append(cut)
    bounds.append(height)
    while len(bounds) > 2 and bounds[-1] - bounds[-2] < 400:
        del bounds[-2]
    if len(bounds) <= 2:
        return [path]

    parts = []
    with PILImage.open(path) as image:
        for index in range(len(bounds) - 1):
            top, bottom = bounds[index], bounds[index + 1]
            if not (~blank[top:bottom]).any():      # nothing but background
                continue
            out = os.path.join(tempfolder, '_pg{}_{}'.format(index, os.path.basename(path)))
            image.crop((0, top, width, bottom)).save(out)
            parts.append(out)
    return parts or [path]


def topmost_hline(path):
    """
    y of the first long horizontal ruling line (the top border of the first
    table on the page). Used to crop the letterhead away without guessing a
    pixel offset. Returns 0 when no line is found.
    """
    import cv2
    import numpy as np

    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0
    height, width = img.shape[:2]
    binary = (img < 200).astype('uint8')
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(width // 2, 50), 1))
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    # A real ruling line covers most of the page width; the odd speck does not.
    row_counts = horizontal.sum(axis=1)
    rows = np.where(row_counts > width * 0.5)[0]
    rows = rows[(rows > 20) & (rows < height - 20)]
    return int(rows[0]) if len(rows) else 0


HEADING_RE = re.compile(r'^\d{1,2}\s*[.)]\s*institutions de microfinance de')

# Page-segmentation mode for the heading pass. 3 = full automatic layout analysis,
# which is what these pages need: a heading line sitting above a ruled table. If a
# category heading ever goes missing on the Tesseract path, this is the knob - try
# 4 (single column of variable-size text) before touching HEADING_RE.
TESSERACT_PSM = 3


def find_tesseract_dir():
    """The bundled Tesseract-OCR folder, searched upward from this script.

    Resolved at runtime rather than hard-coded: the production box runs as a
    different Windows user and from a different root than any dev machine
    (observed 2026-09-03: C:\\Users\\LaraZenl\\Desktop\\regulators_project\\
    regulators_scripts\\BI-BRB\\), so an absolute path baked in from a dev
    checkout silently misses and the run falls through to the wrong engine.

    Set TESSERACT_DIR to override without editing this file.
    """
    override = os.environ.get('TESSERACT_DIR')
    if override and os.path.isdir(override):
        return override

    folder = scriptfolder
    for _ in range(5):
        candidate = os.path.join(folder, 'Tesseract-OCR')
        if os.path.isdir(candidate):
            return candidate
        parent = os.path.dirname(folder)
        if parent == folder:
            break
        folder = parent
    return None


def tesseract_langs():
    """Language packs the tesseract binary actually has installed."""
    try:
        out = subprocess.run(['tesseract', '--list-langs'],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        text = out.stdout.decode('utf-8', 'replace')
        return set(line.strip() for line in text.splitlines()[1:] if line.strip())
    except Exception:
        return set()


def resolve_ocr():
    """Choose the OCR engines for this machine.

    Returns (table_ocr, text_reader, description). `table_ocr` goes to
    img2table's extract_tables(ocr=...); `text_reader(path)` returns a list of
    {top, bottom, left, text} boxes for the heading scan.

    TESSERACT IS THE PREFERRED AND AUTHORITATIVE ENGINE - it is what the Windows
    control server has and what the rest of this repo uses (LC FSRALC, GN BCRG,
    RW NBRW). RapidOCR exists only to unblock machines with no tesseract binary
    (the Mac: no brew, no admin).

    The RapidOCR imports MUST stay inside their branch. The control server runs
    Python 3.8 with an img2table old enough that `img2table.ocr` has no RapidOCR
    attribute at all, so importing it unconditionally raises ImportError before
    any of this code gets a chance to pick Tesseract:
        ImportError: cannot import name 'RapidOCR' from 'img2table.ocr'
    That is exactly how this script failed in production on 2026-09-03.
    """
    tess_dir = find_tesseract_dir()
    if tess_dir:
        os.environ['PATH'] = tess_dir + os.pathsep + os.environ.get('PATH', '')

    if shutil.which('tesseract'):
        from img2table.ocr import TesseractOCR
        langs = tesseract_langs()
        # The source is French. Prefer 'fra' so accented glyphs are recognised
        # rather than approximated; fall back to 'eng' with a warning, because
        # the accents feed a QA gate downstream.
        if 'fra' in langs:
            lang = 'fra'
        else:
            lang = 'eng'
            print("[WARN] tesseract has no 'fra' language pack (found: {}); falling back to "
                  "'eng'. French accents will degrade - install fra.traineddata on this box."
                  .format(','.join(sorted(langs)) or 'none reported'), flush=True)
        table_ocr = TesseractOCR(n_threads=1, lang=lang)

        def text_reader(path, _lang=lang):
            return tesseract_boxes(path, _lang)

        return table_ocr, text_reader, 'TesseractOCR(lang={})'.format(lang)

    # ---- no tesseract binary on this machine: pure-Python fallback ----------
    try:
        from img2table.ocr import RapidOCR as TableOCR
        from rapidocr import RapidOCR as TextOCR
    except ImportError as exc:
        raise RuntimeError(
            'No usable OCR engine. tesseract is not on PATH (looked for a bundled '
            'Tesseract-OCR folder from {} upward) and the RapidOCR fallback is '
            'unavailable: {}. On the Windows control server the fix is tesseract, '
            'not RapidOCR - this img2table is too old to have it.'
            .format(scriptfolder, exc))

    table_ocr = TableOCR()
    engine = TextOCR()

    def text_reader(path):
        return boxes_from_rapidocr(engine(path))

    print('[WARN] running on the RapidOCR fallback, not Tesseract. Treat this output as a '
          'dev run - the Tesseract result from the control server is authoritative.',
          flush=True)
    return table_ocr, text_reader, 'RapidOCR (fallback)'


def tesseract_boxes(path, lang):
    """Word boxes from the tesseract binary via TSV, as {top,bottom,left,text}.

    Shells out rather than importing pytesseract: the binary is bundled with the
    repo and present on the control server, the Python wrapper is not.

    Raises rather than returning [] when the call fails. An empty box list would
    mean 'no headings on this page', which is a legal state - so a crashed OCR
    call would silently push every row into category 0 and drop the whole list
    while still exiting 0.
    """
    out = subprocess.run(['tesseract', path, 'stdout', '-l', lang,
                          '--psm', str(TESSERACT_PSM), 'tsv'],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1800)
    if out.returncode != 0:
        raise RuntimeError('tesseract failed on {} (exit {}): {}'.format(
            os.path.basename(path), out.returncode,
            out.stderr.decode('utf-8', 'replace').strip()[:400]))

    text = out.stdout.decode('utf-8', 'replace')
    boxes = []
    for line in text.splitlines()[1:]:
        field = line.split('\t')
        if len(field) < 12:
            continue
        try:
            conf = float(field[10])
            left, top, width, height = (int(field[6]), int(field[7]),
                                        int(field[8]), int(field[9]))
        except ValueError:
            continue
        word = '\t'.join(field[11:]).strip()
        if conf < 0 or not word:
            continue
        boxes.append({'top': top, 'bottom': top + height, 'left': left, 'text': word})
    return boxes


def boxes_from_rapidocr(result):
    """Word boxes from a rapidocr result object, in the same shape as above."""
    if getattr(result, 'boxes', None) is None:
        return []
    boxes = []
    for box, txt in zip(result.boxes, result.txts):
        ys = [point[1] for point in box]
        xs = [point[0] for point in box]
        boxes.append({'top': min(ys), 'bottom': max(ys), 'left': min(xs), 'text': txt})
    return boxes


def _ocr_lines(boxes):
    """OCR boxes regrouped into text lines: [(y_top, joined text)], top to bottom.

    Engine-neutral: takes the {top,bottom,left,text} boxes produced by either
    reader. Tesseract emits one box per WORD where RapidOCR emits one per text
    run, which is precisely why the heading match is done on regrouped lines
    rather than on individual boxes.
    """
    boxes = sorted(boxes, key=lambda item: (item['top'], item['left']))

    lines = []
    for box in boxes:
        placed = False
        for line in lines:
            # same text line when the vertical centres sit inside each other's band
            centre = (box['top'] + box['bottom']) / 2
            if line['top'] <= centre <= line['bottom']:
                line['parts'].append((box['left'], box['text']))
                line['top'] = min(line['top'], box['top'])
                line['bottom'] = max(line['bottom'], box['bottom'])
                placed = True
                break
        if not placed:
            lines.append({'top': box['top'], 'bottom': box['bottom'],
                          'parts': [(box['left'], box['text'])]})

    out = []
    for line in sorted(lines, key=lambda item: item['top']):
        text = ' '.join(text for _, text in sorted(line['parts']))
        out.append((float(line['top']), text))
    return out


def page_headings(path, text_reader):
    """
    [(y, category_number)] for every 'N. Institutions de microfinance de X categorie'.

    The heading wraps over two printed lines and OCR splits it into several
    boxes, so match against reconstructed lines and let the pattern run into the
    following line. Requiring the leading 'N.' keeps the prose sentence
    'aucune institution de microfinance de deuxieme categorie ...' out.

    `text_reader` is whichever reader resolve_ocr() picked; both return the same
    box shape, so nothing below this point knows which engine ran.
    """
    lines = _ocr_lines(text_reader(path))
    found = []
    for index, (top, text) in enumerate(lines):
        blob = deaccent(text)
        if not HEADING_RE.match(blob):
            continue
        if index + 1 < len(lines):
            blob = blob + ' ' + deaccent(lines[index + 1][1])
        for word, number in ORDINALS.items():
            if word + ' categorie' in blob:
                found.append((top, number))
                break
    found.sort()
    return found


def page_tables(path, table_ocr):
    """
    Tables on one page, as (y_top, DataFrame), in reading order.

    Two passes. img2table silently drops the first table of a page when a
    letterhead sits above it, so a second pass runs on the page cropped at the
    first ruling line; tables from that pass are kept only when they cover a
    band the full-page pass did not reach.
    """
    from PIL import Image as PILImage
    from img2table.document import Image as I2TImage

    def extract(image_path, offset):
        doc = I2TImage(image_path, detect_rotation=False)
        tables = doc.extract_tables(ocr=table_ocr, implicit_rows=False,
                                    borderless_tables=False, min_confidence=50)
        return [(int(t.bbox.y1) + offset, int(t.bbox.y2) + offset, t.df) for t in tables]

    found = extract(path, 0)

    # Leave room above the first ruling line or img2table cannot see it as a border.
    cut = max(topmost_hline(path) - 80, 0)
    if cut > 0:
        with PILImage.open(path) as image:
            width, height = image.size
            cropped = os.path.join(tempfolder, '_crop_' + os.path.basename(path))
            image.crop((0, cut, width, height)).save(cropped)
        for y1, y2, frame in extract(cropped, cut):
            overlaps = any(not (y2 <= fy1 or y1 >= fy2) for fy1, fy2, _ in found)
            if not overlaps:
                found.append((y1, y2, frame))

    found.sort(key=lambda item: item[0])
    return [(y1, frame) for y1, _, frame in found]


def map_columns(frame):
    """
    label -> column index, read off a header row. Returns (mapping, header_row_index)
    or (None, None) when this table is a continuation with no header.
    """
    for row_index in range(min(2, frame.shape[0])):
        mapping = {}
        for col_index in range(frame.shape[1]):
            label = _norm_label(frame.iloc[row_index, col_index])
            if not label or label == 'nan':
                continue
            hits = []
            for field, pattern in LABEL_PATTERNS:
                position = label.find(pattern)
                if position >= 0 and field not in [hit[1] for hit in hits]:
                    hits.append((position, field))
            hits.sort()
            # A merged cell holds several labels; they belong to consecutive columns.
            for offset, (_, field) in enumerate(hits):
                mapping.setdefault(field, min(col_index + offset, frame.shape[1] - 1))
        if 'Name' in mapping and 'Address' in mapping:
            return mapping, row_index
    return None, None


# The 'Forme juridique' column of list 2 uses a closed vocabulary.
L2_LEGAL_FORMS = ('Société Anonyme', 'Société Coopérative')


def repair_legal_form(co_type, address_blob):
    """Put back a legal form whose second line the OCR gave to the address.

    'Société Coopérative' wraps inside its cell on some rows; img2table then
    assigns the trailing word to the neighbouring address column, leaving
    CoType as a bare 'Société'. Only a CoType that is a strict prefix of a
    known form is repaired, and only if that exact word is in the address.
    """
    base = clean(co_type)
    address = str(address_blob or '')
    if not base:
        return co_type, address_blob
    for form in L2_LEGAL_FORMS:
        if deaccent(base) == deaccent(form):
            return co_type, address_blob          # already complete
    for form in L2_LEGAL_FORMS:
        if not deaccent(form).startswith(deaccent(base) + ' '):
            continue
        tail = form[len(base):].strip()
        for word in re.findall(r'\S+', address):
            if deaccent(word).strip(',;.').lower() != deaccent(tail).lower():
                continue
            address = re.sub(r'\s*' + re.escape(word) + r'\s*', ' ', address, count=1)
            address = re.sub(r'[ \t]+', ' ', address).strip(' ,;')
            return form, address
    return co_type, address_blob


def split_address(blob):
    """'Bujumbura Mairie,\\nAvenue X,\\nTel: 1 2,\\nB.P. 99 BUJUMBURA' -> parts."""
    parts = [clean(part) for part in re.split(r'[\n]+', str(blob or '')) if clean(part)]
    street, box, phone = [], '', ''
    for part in parts:
        low = deaccent(part)
        if re.match(r'^t[eé]l', low) or low.startswith('tel'):
            if not phone:
                phone = first_phone(part)
            rest = re.sub(r'(?i)t[eé]l\.?\s*:?.*$', '', part).strip(' ,;')
            if rest:
                street.append(rest)
        elif re.match(r'^b\.?\s?p\b', low):
            box = part
        else:
            if not phone:
                inline = re.search(r'(?i)t[eé]l\.?\s*:?\s*(.+)$', part)
                if inline:
                    phone = first_phone(inline.group(1))
                    part = re.sub(r'(?i),?\s*t[eé]l\.?\s*:?.*$', '', part).strip(' ,;')
            if part:
                street.append(part)
    return clean(', '.join(street)), box, phone


def parse_list2(soup, listcode, meta, session):
    # Engine chosen per machine - see resolve_ocr(). Never import RapidOCR at module
    # scope: the control server's img2table does not have the name.
    table_ocr, text_ocr, engine_name = resolve_ocr()
    print('[INFO] list 2: OCR engine = {}'.format(engine_name), flush=True)

    validity = french_date_to_iso(soup.get_text(' ', strip=True))
    images = download_list2_images(soup, session)
    paths = []
    for image_path in images:
        paths.extend(split_pages(image_path))
    print('[INFO] list 2: {} images -> {} pages to OCR'.format(len(images), len(paths)), flush=True)

    category = 0
    mapping = None
    kept = 0
    seen_rows = {}          # category -> count, for the completeness report

    for index, path in enumerate(paths, 1):
        headings = page_headings(path, text_ocr)
        tables = page_tables(path, table_ocr)

        events = [(y, 'heading', number) for y, number in headings]
        events += [(y, 'table', frame) for y, frame in tables]
        events.sort(key=lambda item: item[0])

        for _, kind, payload in events:
            if kind == 'heading':
                category = payload
                mapping = None          # each category restarts its own table
                continue
            if category not in WANTED_CATEGORIES:
                continue

            frame = payload
            new_mapping, header_row = map_columns(frame)
            if new_mapping:
                mapping = new_mapping
                start = header_row + 1
            else:
                start = 0
            if not mapping:
                continue
            if max(mapping.values()) >= frame.shape[1]:
                # Continuation table with a different column count - the carried
                # mapping cannot be trusted, so do not guess at the contents.
                print('[WARN] list 2: skipped a {}-column block that does not match '
                      'the carried header'.format(frame.shape[1]), flush=True)
                continue

            for row_index in range(start, frame.shape[0]):
                name = clean(frame.iloc[row_index, mapping['Name']])
                if not name or _norm_label(name) in HEADER_LABELS:
                    continue

                address_blob = frame.iloc[row_index, mapping['Address']] \
                    if 'Address' in mapping else ''
                co_type = clean(frame.iloc[row_index, mapping['CoType']]) \
                    if 'CoType' in mapping else ''
                co_type, address_blob = repair_legal_form(co_type, address_blob)
                street, box, phone = split_address(address_blob)
                reg_date = clean(frame.iloc[row_index, mapping['RegulationDate']]) \
                    if 'RegulationDate' in mapping else ''

                add_row(
                    ListLabel=meta['ListLabel'],
                    Name=name,
                    CoType=co_type,
                    License_Type=CAT_LABEL.get(category, ''),
                    Address_1=street,
                    Address_2=box,
                    City=city_from_address(street),
                    Cntry=CNTRY,
                    Phone=phone,
                    RegulationType='Regulated',
                    RegulationDate=reg_date,
                    RegCtry=REGCTRY,
                    RegCode=REGCODE,
                    ListCode=listcode,
                    ListLanguage=LISTLANGUAGE,
                    ListValidityDate=validity,
                    ListName=meta['ListName'],
                    ListProcessDate=processdate,
                )
                kept += 1
                seen_rows[category] = seen_rows.get(category, 0) + 1

        print('[INFO] list 2: page {}/{} done, running total {}'.format(index, len(paths), kept),
              flush=True)
        if category > max(WANTED_CATEGORIES):
            print('[INFO] list 2: reached category {} - stopping as instructed'.format(category),
                  flush=True)
            break

    for cat in sorted(seen_rows):
        print('[INFO] list 2: category {} -> {} entities'.format(cat, seen_rows[cat]), flush=True)
    return kept


# ============================================================================
# LIST 3 - Payment Systems (node/2928) - first table only
# ============================================================================
# Two tables on the page: 'actifs' then 'Non-actifs'. The ticket wants the first.
# Inside it, rows whose second cell reads 'Dirigeants' are category headers
# (A. transfer of funds, B. e-money issuers, C. payment platform providers).

def parse_list3(soup, listcode, meta):
    section = soup.find('section', id='block-solo-content')
    if section is None:
        raise RuntimeError('list 3: content section not found')
    tables = section.find_all('table')
    if not tables:
        raise RuntimeError('list 3: no table on the page')

    heading = section.get_text(' ', strip=True)
    validity = french_date_to_iso(heading[:200])

    table = tables[0]           # 'Liste des Etablissements de paiement actifs'
    category = ''
    kept = 0

    for row in table.find_all('tr'):
        cells = [clean(cell.get_text(' ', strip=True)) for cell in row.find_all(['td', 'th'])]
        if not cells or not cells[0]:
            continue

        # category header row: second column repeats the word 'Dirigeants'
        if len(cells) > 1 and deaccent(cells[1]).startswith('dirigeant'):
            category = re.sub(r'^[A-Za-z]\s*\.\s*', '', cells[0]).strip()
            continue

        name = re.sub(r'^\s*\d+\s*\.\s*', '', cells[0]).strip()
        if not name:
            continue
        phone = first_phone(cells[3]) if len(cells) > 3 else ''

        add_row(
            ListLabel=meta['ListLabel'],
            Name=name,
            License_Type=category,
            Cntry=CNTRY,
            Phone=phone,
            RegulationType='Regulated',
            RegCtry=REGCTRY,
            RegCode=REGCODE,
            ListCode=listcode,
            ListLanguage=LISTLANGUAGE,
            ListValidityDate=validity,
            ListName=meta['ListName'],
            ListProcessDate=processdate,
        )
        kept += 1
    return kept


# ============================================================================
# MAIN
# ============================================================================
def main():
    print('Running {} Web Scraping Tool v3'.format(REGULATOR), flush=True)
    session = requests.Session()

    parsers = {'1': parse_list1, '2': parse_list2, '3': parse_list3}
    counts = {}

    for listcode in sorted(REGLIST):
        meta = REGLIST[listcode]
        print('[INFO] list {}: fetching'.format(listcode), flush=True)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(fetch(meta['URL'], session).text, 'html.parser')

        if listcode == '2':
            kept = parse_list2(soup, listcode, meta, session)
        else:
            kept = parsers[listcode](soup, listcode, meta)

        counts[listcode] = kept
        print('[INFO] list {}: {} rows'.format(listcode, kept), flush=True)
        if kept == 0:
            print('[WARN] list {} produced no rows'.format(listcode), flush=True)

    # ---------------------------------------------------------------- save --
    os.chdir(scriptfolder)
    df = pd.DataFrame(sqldict)
    df = df[df['Name'] != '']

    # Excel turns long digit strings into floats and eats leading zeros.
    for column in ['InternalID_1', 'InternalID_2', 'InternalID_3', 'Zip', 'Phone', 'Fax',
                   'BIC SWIFT Code', 'ListCode']:
        df[column] = df[column].astype(str).replace('nan', '')

    df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)
    print('Saved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)), flush=True)

    for listcode in sorted(counts):
        print('  list {}: {} rows'.format(listcode, counts[listcode]), flush=True)
    return os.path.join(scriptfolder, filename)


if __name__ == '__main__':
    main()
