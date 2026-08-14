# ------------------------------------------------ Import Lib ----------------------------------------
import os
import re
import sys
import json
import datetime
import unicodedata
from urllib.parse import urljoin

import numpy as np
import pandas as pd
import requests
import urllib3
from bs4 import BeautifulSoup
from PIL import Image

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ------------------------------------------------ Begin_ fileName ----------------------------------------
now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = 'SR CBSU SQL Ready {}.xlsx'.format(now.strftime('%Y-%m-%d %H.%M.%S'))

# ------ At first we will define the workspace path -----
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))  ## production environment (.py)
except NameError:
    scriptfolder = os.getcwd()  ## notebook environment

os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder')
os.makedirs(tempfolder, exist_ok=True)

projectroot = os.path.dirname(scriptfolder)

# ------------------------------------------------ sqldict (DO NOT CHANGE STRUCTURE) ----------------------------------------
sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}


def bourange_same_length_array(sqldict):
    """Pad every column to the length of the longest one."""
    maxlen = max(len(v) for v in sqldict.values())
    for k, v in sqldict.items():
        while len(v) < maxlen:
            v.append('')
    return sqldict


# ------------------------------------------------ List metadata ----------------------------------------
# ListLabel: 1=bank, 2=insurance, 3=both, 4=everything else.
# 'slug' matches the PDF filename on the landing page -- the anchor text is only
# the word "here", so the filename is the only reliable discriminator.
LANDING = ('https://www.cbvs.sr/en/financial-system/payments-systems/'
           'suriname-financial-institutions/financial-institutions')

REGDICT = {
    1: {'ListName': 'Other Depository Corporations',
        'ListLabel': 1,
        'slug': 'kredietinstellingen',
        'file': 'list1.pdf'},
    2: {'ListName': 'Insurance Companies',
        'ListLabel': 2,
        'slug': 'verzekeringsmaatschappijen',
        'file': 'list2.pdf'},
    3: {'ListName': 'Pension- and Provident funds',
        'ListLabel': 4,
        'slug': 'pensioen',
        'file': 'list3.pdf'},
    4: {'ListName': 'Money Exchange and Money Transfer Houses',
        'ListLabel': 4,
        'slug': 'gtks',
        'file': 'list4.pdf'},
}

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                         '(KHTML, like Gecko) Chrome/124.0 Safari/537.36'}

# The ten districts of Suriname -- an address line is recognised by ending in one
# of these, which is what separates it from a wrapped company-name line.
DISTRICTS = ['Paramaribo', 'Wanica', 'Nickerie', 'Coronie', 'Saramacca',
             'Commewijne', 'Marowijne', 'Para', 'Brokopondo', 'Sipaliwini']

DUTCH_MONTHS = {'januari': 1, 'februari': 2, 'maart': 3, 'april': 4, 'mei': 5, 'juni': 6,
                'juli': 7, 'augustus': 8, 'september': 9, 'oktober': 10, 'november': 11, 'december': 12}


# ------------------------------------------------ Step 1: discover + download ----------------------------------------
def discover_pdf_links():
    """Map ListNr -> absolute PDF url by matching the filename slug."""
    r = requests.get(LANDING, headers=HEADERS, verify=False, timeout=90)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')

    found = {}
    for a in soup.find_all('a', href=True):
        href = a['href']
        if '.pdf' not in href.lower():
            continue
        low = href.lower()
        for nr, meta in REGDICT.items():
            if nr in found:
                continue
            # all four target files live under the DTK_2020 publication folder
            if 'dtk_2020' in low and meta['slug'] in low:
                found[nr] = urljoin(LANDING, href)
    return found


def download_pdf(url, dest):
    r = requests.get(url, headers=HEADERS, verify=False, timeout=180)
    r.raise_for_status()
    with open(dest, 'wb') as fh:
        fh.write(r.content)
    return dest


# ------------------------------------------------ Step 2: render pages ----------------------------------------
def render_pages(pdf_path, outdir):
    """Return a list of PNG paths, one per page.

    These four PDFs are pure scans (no text layer at all), so every page carries a
    single full-page image. We pull that image directly with pypdf, which avoids
    needing poppler -- not available on the Mac dev box. If a page has no embedded
    image (or pypdf is too old to expose .images) we fall back to poppler/pdf2image.
    """
    import pypdf
    os.makedirs(outdir, exist_ok=True)
    reader = pypdf.PdfReader(pdf_path)
    pages = []
    base = os.path.splitext(os.path.basename(pdf_path))[0]

    for i, page in enumerate(reader.pages):
        out = os.path.join(outdir, '{}_p{}.png'.format(base, i))
        wrote = False
        try:
            imgs = list(page.images)
            if imgs:
                with open(out, 'wb') as fh:
                    fh.write(imgs[0].data)
                wrote = True
        except Exception:
            wrote = False
        if wrote:
            pages.append(out)

    if len(pages) == len(reader.pages):
        return pages

    # ---- fallback: poppler (control server has it bundled at the repo root) ----
    from pdf2image import convert_from_path
    poppler = os.path.join(projectroot, 'poppler-25.12.0', 'Library', 'bin')
    kwargs = {'dpi': 300}
    if os.path.isdir(poppler):
        kwargs['poppler_path'] = poppler
    pages = []
    for i, im in enumerate(convert_from_path(pdf_path, **kwargs)):
        out = os.path.join(outdir, '{}_p{}.png'.format(base, i))
        im.save(out)
        pages.append(out)
    return pages


# ------------------------------------------------ Step 3: OCR ----------------------------------------
# These are typewriter documents in a MONOSPACE font with wide letter spacing.
# Feeding them straight to an OCR recogniser loses the word spaces -- the v1 output
# was full of names like 'SURINAAMSEPOSTSPAARBANK'. Two changes fix that:
#   1. Segment lines and words from the pixel projection instead of trusting the
#      detector's boxes (the detector silently skipped whole name lines).
#   2. Recognise each word crop on its own, then place it on a character grid
#      derived from the font pitch, so spacing is reconstructed geometrically.
_ENGINE = None


def get_engine():
    global _ENGINE
    if _ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR
        _ENGINE = RapidOCR()
    return _ENGINE


def estimate_pitch(png, engine):
    """Character advance width in pixels, from one detector pass."""
    res, _ = engine(png)
    widths = []
    if res:
        for box in res:
            pts = np.array(box[0])
            txt = box[1]
            if len(txt) >= 6:
                widths.append((pts[:, 0].max() - pts[:, 0].min()) / len(txt))
    return float(np.median(widths)) if widths else 30.0


def _runs(mask, min_gap):
    """Start/end indices of True-runs separated by >= min_gap False pixels."""
    out, start, gap = [], None, 0
    for i, v in enumerate(mask):
        if v:
            if start is None:
                start = i
            gap = 0
        else:
            gap += 1
            if start is not None and gap >= min_gap:
                out.append((start, i - gap))
                start = None
    if start is not None:
        out.append((start, len(mask)))
    return out


def ocr_page(png):
    """Return [(indent_in_chars, text), ...] for one page image."""
    engine = get_engine()
    grey = np.array(Image.open(png).convert('L'))
    rgb = np.array(Image.open(png).convert('RGB'))
    ink = grey < 160
    height, width = ink.shape

    pitch = estimate_pitch(png, engine)

    # ---- horizontal bands = text lines ----
    bands = _runs(ink.sum(axis=1) > max(3, width * 0.002), max(1, int(pitch * 0.35)))
    merged = []
    for b in bands:
        if merged and b[0] - merged[-1][1] < pitch * 0.30:
            merged[-1] = (merged[-1][0], b[1])   # re-attach accents / quote marks
        else:
            merged.append(list(b))
    lines = []

    for y0, y1 in merged:
        if y1 - y0 < pitch * 0.35:
            continue
        segs = _runs(ink[y0:y1, :].any(axis=0), max(1, int(pitch * 0.70)))
        parts = []
        for x0, x1 in segs:
            pad = 6
            crop = rgb[max(y0 - pad, 0):y1 + pad, max(x0 - pad, 0):x1 + pad]
            if crop.size == 0:
                continue
            out, _ = engine(crop, use_det=False, use_cls=False, use_rec=True)
            word = out[0][0].strip() if out else ''
            if word:
                parts.append((x0, word))
        if not parts:
            continue

        text = ''
        for x, word in parts:
            col = int(round(x / pitch))
            if col > len(text):
                text += ' ' * (col - len(text))
            elif text and not text.endswith(' '):
                text += ' '          # never fuse two separate words together
            text += word

        text = unicodedata.normalize('NFKC', text)
        text = text.replace('。', '.').replace('，', ',').replace('’', "'")
        text = re.sub(r' {2,}', ' ', text)
        text = re.sub(r'\s+([.,])', r'\1', text).strip()
        if text:
            lines.append((int(round(parts[0][0] / pitch)), text))
    return lines


# ------------------------------------------------ Step 4: parse ----------------------------------------
# NB: the title line is letter-spaced ("B E K E N D M A K I N G") and OCR sometimes
# mangles one glyph, so it is matched anchored and loosely. It must NOT be a loose
# 'BEKEND' search -- that also matches the word 'bekend,' in the preamble sentence,
# which is the line carrying the ListValidityDate.
NOISE = re.compile(
    r'(CENTRALE\s*BANK\s*VAN\s*SURINAME|CENTRALE\s*ANK|CENTRALEBAN|'
    r'Waterkant\s*20\s*Telefoon|Telefax|P\.O\.B\.\s*1801)', re.I)
TITLE = re.compile(r'^\W*B\s*E\s*K\s*E\s*N\s*D\s*M\s*A\s*K\s*\S?\s*N\s*G\W*$')

ENTRY = re.compile(r'^(\d{1,2})\s*[.)]?\s+(.*)$')
SECTION = re.compile(r'^(?:[IVX]{1,4}\s*[.)]?\s+)?([A-Z][A-ZÀ-Ý\s\-&"\'()/.]{5,})$')
REVOKED = re.compile(r'\(?\s*Ingetrokken\s*d\.?d\.?\s*(.+?)\s*\)?$', re.I)


DISTRICT_RE = re.compile(r'\b(' + '|'.join(DISTRICTS) + r')\b', re.I)


def is_address(line):
    """True for a street/locality line, False for a wrapped company-name line.

    Addresses here are either an explicit 'p/a' (c/o) line, a line naming one of
    the ten districts, or a mixed-case line carrying a house number. Wrapped name
    lines are ALL CAPS ('BEDRIJVEN N.V.') or start with a legal form ('G.A., ...',
    'C-47 G.A. (C-47 Coop)'), so they fail all three tests.
    """
    if re.match(r'^p/a\b', line, re.I):
        return True
    if DISTRICT_RE.search(line):
        return True
    if re.match(r'^[A-Z][a-z]', line) and re.search(r'\d', line):
        return True
    return False


def parse_dutch_date(txt):
    m = re.search(r'(\d{1,2})\s+([a-z]+)\s+(\d{4})', txt, re.I)
    if not m:
        return ''
    month = DUTCH_MONTHS.get(m.group(2).lower())
    if not month:
        return ''
    try:
        return datetime.date(int(m.group(3)), month, int(m.group(1))).strftime('%Y-%m-%d')
    except ValueError:
        return ''


def split_address(line):
    """'Henck Arronstraat 26-30, Paramaribo' -> ('Henck Arronstraat 26-30', 'Paramaribo')"""
    line = re.sub(r'^p/a\s*', '', line, flags=re.I).strip()
    if ',' in line:
        head, tail = line.rsplit(',', 1)
        return head.strip(), re.sub(r'^district\s+', '', tail.strip(), flags=re.I)
    return line, ''


PREAMBLE = re.compile(
    r'^(De\s+CENTRALE|de\s+Wet|Wet\s|bekend,|haar\s+register|voorzieningsfondsen\s+onder|'
    r'verzekeringsinstellingen\s+onder|geldtransactiekantoren\s+in|kredietinstellingen\s+in|'
    r'laatstelijk|\(S\.B\.|No\.\s*\d|\d+\s+van\s+de)', re.I)

ROMAN_SECTION = re.compile(r'^[IVX]{1,4}\s*[.)]?\s+([A-Z].*)$')


def looks_like_section(line):
    """A standalone ALL-CAPS heading such as 'VERZEKERINGSINSTELLINGEN'."""
    if is_address(line) or ENTRY.match(line):
        return False
    letters = [c for c in line if c.isalpha()]
    if len(letters) < 6:
        return False
    return all(c.isupper() for c in letters)


SIGNOFF = re.compile(r'^[A-Z][a-z]+,\s*\d{1,2}\s+(?:' + '|'.join(DUTCH_MONTHS) + r')\s+\d{4}\s*$', re.I)
DISSOLVING = re.compile(r'in\s+proces\s+van\s+ontbinding', re.I)


def finish_entry(cur):
    """Split an entry's trailing lines into name-continuation vs address.

    Everything before the first address-looking line is part of the name (company
    names wrap across lines in these PDFs); that line and anything after it is the
    address.
    """
    split = len(cur['lines'])
    for i, ln in enumerate(cur['lines']):
        if is_address(ln):
            split = i
            break
    for ln in cur['lines'][:split]:
        cur['name'] = (cur['name'] + ' ' + ln).strip()
    cur['addr'] = cur['lines'][split:]
    return cur


def parse_pages(all_lines):
    """Turn the OCR'd lines of one PDF into entry dicts."""
    entries = []
    section = ''
    validity = ''
    cur = None
    in_signature = False

    def flush():
        if cur and cur['name']:
            entries.append(finish_entry(cur))

    for indent, line in all_lines:
        # the register date lives inside the preamble sentence, so read it first
        if not validity:
            mv = re.search(r'\bper\s+(\d{1,2}\s+[a-z]+\s+\d{4})', line, re.I)
            if mv:
                validity = parse_dutch_date(mv.group(1))

        if TITLE.match(line):
            continue
        if re.match(r'^-?\s*\d+\s*-?$', line):        # bare page number
            continue
        if PREAMBLE.match(line):
            continue

        # 'Paramaribo, 29 januari 2020' opens the closing signature block; skip
        # everything after it until a genuine numbered entry starts again.
        if SIGNOFF.match(line):
            flush()
            cur = None
            in_signature = True
            continue

        # ENTRY is tested before NOISE on purpose: one of the pension funds is
        # literally named 'STICHTING PENSIOENFONDS VAN DE CENTRALE BANK VAN
        # SURINAME', which a letterhead substring filter would otherwise delete.
        m = ENTRY.match(line)
        if m and int(m.group(1)) <= 99 and m.group(2):
            flush()
            in_signature = False
            cur = {'name': m.group(2).strip(), 'lines': [], 'addr': [],
                   'section': section, 'cancel': '', 'status': '', 'seq': int(m.group(1))}
            continue

        if in_signature:
            continue
        if NOISE.search(line):
            continue

        # ---- section heading: roman-numbered, or ALL-CAPS between two entries ----
        rs = ROMAN_SECTION.match(line)
        if rs:
            flush()
            cur = None
            section = rs.group(1).strip()
            continue
        # once the current entry already has a body line, a bare ALL-CAPS line is
        # the next section heading -- not a continuation of the previous name.
        if looks_like_section(line) and (cur is None or cur['lines']):
            flush()
            cur = None
            section = line.strip()
            continue

        if cur is None:
            continue

        rev = REVOKED.search(line)
        if rev:
            cur['cancel'] = parse_dutch_date(rev.group(1))
            continue
        if DISSOLVING.search(line):
            cur['status'] = 'In Liquidation'
            continue
        if re.match(r'^\(\s*onbestelbaar\s*\)?$', line, re.I):
            continue                                   # postal annotation, not data

        cur['lines'].append(line)

    flush()
    return entries, validity


# ------------------------------------------------ Step 5: run ----------------------------------------
def main():
    links = discover_pdf_links()
    missing = [nr for nr in REGDICT if nr not in links]
    if missing:
        print('WARNING: no PDF link found for ListNr {}'.format(missing))

    summary = {}
    for nr in sorted(REGDICT):
        meta = REGDICT[nr]
        dest = os.path.join(tempfolder, meta['file'])
        if nr in links:
            print('[{}] downloading {}'.format(nr, links[nr].rsplit('/', 1)[-1]))
            download_pdf(links[nr], dest)
        elif not os.path.exists(dest):
            print('[{}] SKIPPED - no url and no cached pdf'.format(nr))
            continue

        pages = render_pages(dest, os.path.join(scriptfolder, '_debug', 'pages'))
        # OCR is the slow part (~1 min/page); cache it so the parser can be
        # re-run without paying for it again. Delete _debug/*.json to force a redo.
        cache = os.path.join(scriptfolder, '_debug', '{}_lines.json'.format(meta['file'][:-4]))
        if os.path.exists(cache) and not os.environ.get('SR_CBSU_REOCR'):
            with open(cache, encoding='utf-8') as fh:
                lines = [tuple(x) for x in json.load(fh)]
        else:
            lines = []
            for p in pages:
                lines.extend(ocr_page(p))
            with open(cache, 'w', encoding='utf-8') as fh:
                json.dump(lines, fh, ensure_ascii=False)
        entries, validity = parse_pages(lines)
        print('[{}] {} - {} pages, {} entries'.format(nr, meta['ListName'], len(pages), len(entries)))
        summary[nr] = len(entries)

        for e in entries:
            # City comes from whichever address line actually names a district --
            # addresses wrap, and the district is usually on the last line.
            city = ''
            for ln in reversed(e['addr']):
                mcity = DISTRICT_RE.search(ln)
                if mcity:
                    city = mcity.group(1)
                    break
            cleaned = []
            for ln in e['addr']:
                head = split_address(ln)[0]
                head = re.sub(r',?\s*(?:district\s+)?' + re.escape(city) + r'\s*,?\s*$', '',
                              head, flags=re.I).strip(' ,') if city else head.strip(' ,')
                if head:
                    cleaned.append(head)
            addr1 = cleaned[0] if cleaned else ''
            addr2 = ', '.join(cleaned[1:]) if len(cleaned) > 1 else ''

            sqldict['Name'].append(e['name'])
            sqldict['Address_1'].append(addr1)
            sqldict['Address_2'].append(addr2)
            sqldict['City'].append(city)
            sqldict['Cntry'].append('SR')
            sqldict['CoType'].append(e['section'])
            sqldict['License_Type'].append(e['section'])
            # Not every entry on these lists is a live licence:
            #  - '(Ingetrokken d.d. <date>)' = licence revoked on that date
            #  - the section 'SPAAR- EN KREDIETCOOPERATIES DIE NIET MEER
            #    OPERATIONEEL ZIJN' = registered but no longer operating
            if e['cancel']:
                sqldict['RegulationType'].append('Withdrawn')
                sqldict['CancellationDate'].append(e['cancel'])
            elif re.search(r'NIET\s+MEER\s+OPERATIONEEL', e['section'], re.I):
                sqldict['RegulationType'].append('Not Operational')
                sqldict['CancellationDate'].append('')
            elif e['status']:
                sqldict['RegulationType'].append(e['status'])   # 'In Liquidation'
                sqldict['CancellationDate'].append('')
            else:
                sqldict['RegulationType'].append('Regulated')
                sqldict['CancellationDate'].append('')
            sqldict['RegCtry'].append('SR')
            sqldict['RegCode'].append('CBSU')
            sqldict['ListCode'].append(nr)
            sqldict['ListName'].append(meta['ListName'])
            sqldict['ListLabel'].append(meta['ListLabel'])
            sqldict['ListLanguage'].append('NL')
            sqldict['ListValidityDate'].append(validity)
            sqldict['ListProcessDate'].append(processdate)
            bourange_same_length_array(sqldict)

    # ------ Final step we will save the df to .xlsx file ----
    os.chdir(scriptfolder)
    df = pd.DataFrame(sqldict)
    df = df[df['Name'] != '']
    df = df[df['RegulationType'] == 'Regulated']
    df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)
    print('\nSaved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))
    for nr, n in sorted(summary.items()):
        print('  ListNr {}: {} rows'.format(nr, n))
    return df


if __name__ == '__main__':
    main()
