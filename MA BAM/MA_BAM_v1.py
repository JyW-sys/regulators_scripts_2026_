# -*- coding: utf-8 -*-
# ------------------------------------------------------------------
# MA BAM  -  Bank Al-Maghrib (central bank of Morocco)
# Source: https://www.bkam.ma
# Jira:   DECD-5811  (epic DECD-3438, Regulators 2026 - Internal Crawlers)
#
# One list (Jira ListNr 1): "List of approved credit institutions".
#   The list is Annexe 2 ("Liste des etablissements de credit et organismes
#   assimiles") inside the annual banking-supervision report PDF. The scraper
#   finds the most recent report ("... exercice <YYYY>"), downloads its PDF, and
#   extracts every entity from Annexe 2 (name + head-office address), grouped by
#   the annexe's French sub-categories.
#
# Parsing notes (this is a two-sided report, so page margins alternate):
#   * Entity rows are read from the ruled table (horizontal rules bound each
#     entity, so multi-line names/addresses stay in one cell). The name/address
#     column split is the ruled vertical line, detected PER PAGE.
#   * Category sub-headers (Banques, SociAtes de financement, ...) sit OUTSIDE
#     the ruled cells, so they are read from text and each entity row is assigned
#     to the nearest header above it (carried across page breaks) - same y-anchor
#     technique as NP NRB.
#
# Category -> ListLabel: banks / participatory / offshore = 1, everything else
# (finance companies, micro-credit associations, payment institutions) = 4.
# ------------------------------------------------------------------
import os
import re
import time
import datetime
import requests
import urllib3
import pdfplumber
import pandas as pd
from bs4 import BeautifulSoup

urllib3.disable_warnings()

regulatorName = "MA BAM"
print(f"Running {regulatorName} Web Scraping Tool v.1.0")

scriptfolder = os.path.dirname(os.path.abspath(__file__))
tempfolder = os.path.join(scriptfolder, "tempfolder")
os.makedirs(tempfolder, exist_ok=True)

BASE = "https://www.bkam.ma"
REPORT_INDEX = (BASE + "/fr/Publications-et-recherche/Publications-institutionnelles/"
                "Rapport-annuel-sur-la-supervision-bancaire")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RegulatorBot/1.0"}

COLUMNS = ['bvdid', 'priority', 'ListLabel', 'Typology', 'EntryType', 'Name',
           'InternalID_1', 'InternalID_1_type', 'InternalID_2', 'InternalID_2_type',
           'InternalID_3', 'InternalID_3_type', 'CoType', 'License_Type',
           'Address_1', 'Address_2', 'City', 'Zip', 'Cntry', 'Phone', 'Fax',
           'Website', 'Email', 'RegulationType', 'RegulationTypeCode',
           'RegulationDate', 'CancellationDate', 'RegCtry', 'RegCode', 'ListCode',
           'ListLanguage', 'ListValidityDate', 'ListName', 'ListProcessDate',
           'LEI Code', 'BIC SWIFT Code', 'Name - Mother Company',
           'Address_1 - Mother company', 'Address_2 -  Mother company',
           'City - Mother company', 'Zip - Mother company', 'Cntry - Mother company',
           'Phone - Mother company']

PROCESS_DATE = datetime.datetime.now().strftime('%Y-%m-%d')
LIST_CODE = 1
LIST_NAME = "List of approved credit institutions"

# French sub-category prefix -> (English CoType, ListLabel). Longer/more specific
# prefixes first so "banques offshore" and "...participatives" win over "banques".
CATS = [
    ("banques et fenêtres participatives", "Participatory Bank", 1),
    ("banques offshore", "Offshore Bank", 1),
    ("banques", "Bank", 1),
    ("sociétés de crédit à la consommation", "Consumer Credit Company", 4),
    ("sociétés de crédit immobilier", "Real Estate Credit Company", 4),
    ("sociétés d’affacturage", "Factoring Company", 4),
    ("sociétés d'affacturage", "Factoring Company", 4),
    ("sociétés de crédit-bail", "Leasing Company", 4),
    ("sociétés de cautionnement", "Guarantee Company", 4),
    ("autres sociétés de financement", "Other Finance Company", 4),
    ("associations de micro-crédit", "Micro-Credit Association", 4),
    # the two sub-sections that sit at the top of the Annexe-3 page, above the
    # "Annexe 3" title (must precede the bare "etablissements de paiement" key so
    # "Autres etablissements de paiement ..." isn't shadowed):
    ("autres établissements de paiement", "Specialized Funds Transfer Establishment", 4),
    ("autres établissements de crédit", "Other Credit Institution", 4),
    ("etablissements de paiement", "Payment Institution", 4),
]
# sentinel: once the "Annexe 3" title is reached, stop emitting rows (the count
# table below it is not part of the Annexe-2 entity listing).
STOP = object()
SKIP = re.compile(r'^(dénomination sociale|adresse du siège social|annexe|annexes|'
                  r'bank al-maghrib)\b', re.I)


def catmatch(text):
    tl = re.sub(r'\s+', ' ', (text or '').lower()).strip()
    for key, en, lab in CATS:
        if tl.startswith(key):
            return (en, lab)
    return None


def blank_row():
    return {c: '' for c in COLUMNS}


def text_lines(page, tol=3):
    """Cluster words into visual lines -> [{'text','top'}]. Replaces
    page.extract_text_lines() for older pdfplumber (< 0.7.1) that lacks it."""
    if hasattr(page, "extract_text_lines"):
        return page.extract_text_lines()
    buckets = {}
    for w in page.extract_words():
        buckets.setdefault(round(w['top'] / tol), []).append(w)
    out = []
    for key in sorted(buckets):
        ws = sorted(buckets[key], key=lambda w: w['x0'])
        out.append({'text': ' '.join(w['text'] for w in ws),
                    'top': min(w['top'] for w in ws)})
    return out


def row_top(row_obj):
    """Top y of a find_tables() row, robust across pdfplumber versions."""
    try:
        return row_obj.bbox[1]
    except Exception:
        cells = [c for c in getattr(row_obj, "cells", []) if c]
        return min(c[1] for c in cells) if cells else 0


def get(url, retries=3, **kw):
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=120, verify=False, **kw)
            r.raise_for_status()
            return r
        except Exception as e:
            print(f"   retry {i+1}/{retries} for {url}: {e}")
            time.sleep(2)
    raise RuntimeError(f"Failed to fetch {url}")


def find_latest_report_pdf():
    """From the report index, pick the newest 'exercice <YYYY>' sub-page and
    return its /content/download/....pdf link."""
    soup = BeautifulSoup(get(REPORT_INDEX).text, "html.parser")
    best_year, best_href = -1, None
    for a in soup.find_all("a", href=True):
        m = re.search(r'supervision-bancaire[-/].*?exercice[-_](\d{4})', a["href"], re.I)
        if m and int(m.group(1)) > best_year:
            best_year, best_href = int(m.group(1)), a["href"]
    if not best_href:
        raise RuntimeError("No 'exercice <year>' report sub-page found")
    print(f"   latest report: exercice {best_year}")
    sub = best_href if best_href.startswith("http") else BASE + best_href
    ssoup = BeautifulSoup(get(sub).text, "html.parser")
    for a in ssoup.find_all("a", href=True):
        if "/content/download/" in a["href"] and ".pdf" in a["href"].lower():
            url = a["href"] if a["href"].startswith("http") else BASE + a["href"]
            return requests.utils.requote_uri(url), best_year
    raise RuntimeError(f"No PDF download link on {sub}")


def download_report():
    url, year = find_latest_report_pdf()
    dest = os.path.join(tempfolder, "bam_report.pdf")
    r = get(url)
    with open(dest, "wb") as fh:
        fh.write(r.content)
    if r.content[:4] != b"%PDF":
        raise RuntimeError(f"Downloaded file is not a PDF (from {url})")
    return dest, year


def page_geometry(page):
    """Return [left_border, mid_separator, right_border] for the 2-column table,
    derived from the ruled lines (works despite alternating page margins)."""
    hl = [l for l in page.lines if abs(l['top'] - l['bottom']) < 2]
    vl = sorted(set(round(l['x0']) for l in page.lines if abs(l['x0'] - l['x1']) < 2))
    lb = min(l['x0'] for l in hl)
    rb = max(l['x1'] for l in hl)
    mid = [x for x in vl if 250 <= x <= 320]
    return [lb, (min(mid) if mid else (lb + rb) / 2), rb]


def annexe2_page_range(pdf):
    """First page of 'Annexe 2. Liste des etablissements ...' up to (excl.) Annexe 3."""
    start = None
    for pi, page in enumerate(pdf.pages):
        txt = page.extract_text() or ''
        if start is None and re.search(r'Annexe\s*2\.\s*Liste des établissements', txt, re.I):
            start = pi
        elif start is not None and re.search(r'Annexe\s*3', txt, re.I):
            # include the Annexe-3 page: its top holds the last two Annexe-2
            # sub-sections (above the "Annexe 3" title). parse stops at that title.
            return range(start, pi + 1)
    if start is None:
        raise RuntimeError("Annexe 2 not found in report PDF")
    return range(start, len(pdf.pages))


def city_from_address(addr):
    """Head-office city = last '-'-separated segment, skipping postal codes/B.P."""
    segs = [s.strip(' ,') for s in re.split(r'\s-\s|,', addr) if s.strip(' ,')]
    for seg in reversed(segs):
        if re.fullmatch(r'\d[\d\s]*', seg):        # postal code
            continue
        if re.search(r'\bB\.?P\b', seg, re.I) and re.search(r'\d', seg):
            continue
        return seg
    return ''


def parse_annexe2(pdf):
    rows = []
    cur = None
    for pi in annexe2_page_range(pdf):
        if cur is STOP:
            break
        page = pdf.pages[pi]
        events = []
        for ln in text_lines(page):
            t = ln['text']
            if re.search(r'Annexe\s*3', t, re.I):          # end of Annexe 2
                events.append((ln['top'], 'hdr', STOP))
                continue
            if SKIP.match(t.strip()):
                continue
            if not re.search(r'\d', t) and catmatch(t):
                events.append((ln['top'], 'hdr', catmatch(t)))
        ts = {"vertical_strategy": "explicit",
              "explicit_vertical_lines": page_geometry(page),
              "horizontal_strategy": "lines", "snap_tolerance": 4}
        for tbl in page.find_tables(ts):
            for robj, r in zip(tbl.rows, tbl.extract()):
                name = re.sub(r'\s+', ' ', (r[0] or '').replace('\n', ' ')).strip()
                addr = re.sub(r'\s+', ' ', (r[1] or '').replace('\n', ' ')).strip() \
                    if len(r) > 1 else ''
                if (name + addr).strip():
                    events.append((row_top(robj), 'row', (name, addr)))
        events.sort(key=lambda e: e[0])

        for _, kind, pl in events:
            if kind == 'hdr':
                cur = pl
                if cur is STOP:            # reached "Annexe 3" - stop emitting
                    break
                continue
            name, addr = pl
            combined = (name + ' ' + addr).strip()
            if SKIP.match(name):
                continue
            if not re.search(r'\d', combined) and catmatch(combined):   # header slipped into a cell
                cur = catmatch(combined)
                continue
            if cur is None or cur is STOP or re.fullmatch(r'\d{1,4}', combined):  # preamble / page num / post-Annexe-3
                continue
            if not name:                    # address-only continuation row
                if rows:
                    rows[-1]["Address_1"] = (rows[-1]["Address_1"] + ' ' + addr).strip()
                continue
            cotype, listlabel = cur
            r = blank_row()
            r.update({
                "ListLabel": listlabel,
                "Typology": cotype,
                "Name": name,
                "CoType": cotype,
                "Address_1": addr,
                "City": city_from_address(addr),
                "Cntry": "MA",
                "ListCode": LIST_CODE,
                "ListName": LIST_NAME,
            })
            rows.append(r)
    return rows


# ==================================================================
# RUN
# ==================================================================
print("[MA BAM] locating & downloading latest supervision report ...")
pdf_path, report_year = download_report()
print("[MA BAM] parsing Annexe 2 ...")
with pdfplumber.open(pdf_path) as pdf:
    all_rows = parse_annexe2(pdf)

for r in all_rows:
    r["City"] = city_from_address(r["Address_1"])   # recompute after any continuation merges
    r["RegCtry"] = "MA"
    r["RegCode"] = "BAM"
    r["RegulationType"] = "Regulated"
    r["ListLanguage"] = "FR"
    r["ListValidityDate"] = f"{report_year}-12-31"
    r["ListProcessDate"] = PROCESS_DATE

df = pd.DataFrame(all_rows).reindex(columns=COLUMNS, fill_value="")
now = datetime.datetime.now()
outfile = os.path.join(
    scriptfolder,
    "{} SQL Ready {}.xlsx".format(regulatorName, str(now).replace(":", ".")[:-7]))
df.to_excel(outfile, sheet_name="SQL Ready", index=False)

print("\n==== SUMMARY ====")
print("Total rows:", len(df))
for typ in df['CoType'].unique():
    print(f"  {typ}: {len(df[df['CoType'] == typ])}")
print("Output:", outfile)

for rem in os.listdir(tempfolder):
    os.remove(os.path.join(tempfolder, rem))
