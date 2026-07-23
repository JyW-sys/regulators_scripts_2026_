# -*- coding: utf-8 -*-
# ------------------------------------------------------------------
# MR CBMAU  -  Banque Centrale de Mauritanie
# Source: https://www.bcm.mr  (SPA; content served by Drupal at bo.bcm.mr)
# Jira:   DECD-5810  (epic DECD-3438, Regulators 2026 - Internal Crawlers)
#
# Three lists (Jira), all reachable from node 826 "Etablissements agrees":
#   1  Banques agrees                         -> inline PNG (image_0)  OCR  ListLabel 1
#   2  Etablissements de paiement / e-monnaie -> inline PNG (image_2)  OCR  ListLabel 4
#   3  Institutions de Microfinance (IMF)     -> text PDF (Denomination col) ListLabel 4
#
# The public page https://www.bcm.mr/page/etablissements-agrees/826 is a React
# SPA; its body comes from the Drupal JSON:API:
#   https://bo.bcm.mr/fr/jsonapi/node/page?filter[drupal_internal__nid]=826
# field_content.value is HTML holding the two inline <img> (lists 1 & 2) and the
# IMF PDF <a> (list 3). We read those URLs from the API so filenames can change.
#
# OCR (lists 1 & 2) uses the project's bundled Tesseract on the Windows box
# (Tesseract-OCR\ + tessdata\ at the repo root). The IMF PDF (list 3) is a real
# text PDF, so it is parsed with pdfplumber and needs no OCR.
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

regulatorName = "MR CBMAU"
print(f"Running {regulatorName} Web Scraping Tool v.1.0")

scriptfolder = os.path.dirname(os.path.abspath(__file__))
projectroot = os.path.dirname(scriptfolder)               # ...\Regulator
tempfolder = os.path.join(scriptfolder, "tempfolder")
os.makedirs(tempfolder, exist_ok=True)

BO = "https://bo.bcm.mr"
NODE_API = BO + "/fr/jsonapi/node/page?filter%5Bdrupal_internal__nid%5D=826"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RegulatorBot/1.0"}

# --- Tesseract wiring (bundled Windows binary at the repo root) -------------
# Lists 1 & 2 are scanned/rendered tables extracted with img2table (the project's
# established scanned-table tool, see LC FSRALC / GN BCRG), which shells out to
# the tesseract binary - so put the bundled Tesseract-OCR dir on PATH.
import pytesseract
_tessdir = os.path.join(projectroot, "Tesseract-OCR")
if os.path.isdir(_tessdir):
    os.environ["PATH"] = _tessdir + os.pathsep + os.environ.get("PATH", "")
    os.environ["TESSDATA_PREFIX"] = os.path.join(projectroot, "tessdata")
    pytesseract.pytesseract.tesseract_cmd = os.path.join(_tessdir, "tesseract.exe")
OCR_LANG = "fra+eng"

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

LIST_NAMES = {
    1: "Banques agréées par la Banque Centrale de Mauritanie",
    2: "Etablissements de paiement et de monnaie électronique agréés par la Banque Centrale de Mauritanie",
    3: "Institutions de Microfinance (IMF) agréées par la Banque Centrale de Mauritanie",
}
# List 2 French category -> English CoType
CAT2_EN = {
    "etablissement de paiement": "Payment Institution",
    "etablissement de monnaie electronique": "Electronic Money Institution",
    "transfert de fonds": "Funds Transfer",
}


def blank_row():
    return {c: '' for c in COLUMNS}


def get(url, retries=3, extra_headers=None):
    headers = {**HEADERS, **(extra_headers or {})}
    for i in range(retries):
        try:
            r = requests.get(url, headers=headers, timeout=90, verify=False)
            r.raise_for_status()
            return r
        except Exception as e:
            print(f"   retry {i+1}/{retries} for {url}: {e}")
            time.sleep(2)
    raise RuntimeError(f"Failed to fetch {url}")


def fetch_sources():
    """From the Drupal node, return (banks_png_url, payment_png_url, imf_pdf_url)."""
    data = get(NODE_API, extra_headers={"Accept": "application/vnd.api+json"}).json()
    node = data["data"][0] if isinstance(data["data"], list) else data["data"]
    html = node["field_content"]["value"]
    soup = BeautifulSoup(html, "html.parser")
    imgs = [i["src"] for i in soup.find_all("img", src=True)]
    banks = next((u for u in imgs if "image_0" in u), None)
    payment = next((u for u in imgs if "image_2" in u), None)
    pdf = None
    for a in soup.find_all("a", href=True):
        if ".pdf" in a["href"].lower() and "imf" in a["href"].lower():
            pdf = a["href"]
            break
    absolute = lambda u: u if not u or u.startswith("http") else BO + u
    return absolute(banks), absolute(payment), absolute(pdf)


def download(url, name):
    dest = os.path.join(tempfolder, name)
    with open(dest, "wb") as fh:
        fh.write(get(url).content)
    return dest


# ==================================================================
# OCR helpers  (img2table + Tesseract, the project's scanned-table pattern)
# ==================================================================
def extract_image_table(png):
    """Return the largest table on a bordered image as a list of row-cell lists
    (each cell a clean string), using img2table's TesseractOCR."""
    from img2table.ocr import TesseractOCR
    from img2table.document import Image as I2TImage
    ocr = TesseractOCR(n_threads=1, lang=OCR_LANG)
    tables = I2TImage(png).extract_tables(ocr=ocr, implicit_rows=False,
                                          borderless_tables=False)
    if not tables:
        raise RuntimeError(f"no table detected in {os.path.basename(png)}")
    df = max(tables, key=lambda t: t.df.shape[0]).df
    rows = []
    for _, row in df.iterrows():
        rows.append([('' if c is None else str(c)).replace('\n', ' ').strip()
                     for c in row.tolist()])
    return rows


def scrape_list1_banks(png):
    """3-column bordered table: Nom de l'institution | Code BANKxxx | Short Name."""
    out = []
    for cells in extract_image_table(png):
        name = cells[0] if len(cells) > 0 else ''
        code = cells[1] if len(cells) > 1 else ''
        short = cells[2] if len(cells) > 2 else ''
        name = re.sub(r'\s+', ' ', name).strip()
        if not name or name.lower().startswith("nom de"):     # skip header/empties
            continue
        r = blank_row()
        r.update({
            "ListLabel": 1, "CoType": "Bank", "Name": name,
            "InternalID_1": code.strip(), "InternalID_1_type": "BCM Institution Code",
            "InternalID_2": short.strip(), "InternalID_2_type": "Short Name",
            "City": "Nouakchott", "Cntry": "MR",
            "ListCode": 1, "ListName": LIST_NAMES[1],
        })
        out.append(r)
    return out


def scrape_list2_payment(png):
    """2-column bordered table: Noms de l'etablissement | Categorie etablissement."""
    out = []
    for cells in extract_image_table(png):
        name = re.sub(r'\s+', ' ', cells[0] if cells else '').strip()
        cat = re.sub(r'\s+', ' ', cells[1] if len(cells) > 1 else '').strip()
        if not name or name.lower().startswith("noms de"):     # skip header/empties
            continue
        norm = lambda s: re.sub(r'[éè]', 'e', s.lower())
        if norm(name) in CAT2_EN:      # section-separator row (name == category), not an entity
            continue
        cat_key = norm(cat)
        cotype = CAT2_EN.get(cat_key, cat)
        r = blank_row()
        r.update({
            "ListLabel": 4, "CoType": cotype, "Typology": cat, "Name": name,
            "City": "Nouakchott", "Cntry": "MR",
            "ListCode": 2, "ListName": LIST_NAMES[2],
        })
        out.append(r)
    return out


def scrape_list3_imf(pdf_path):
    """Text PDF, 3 columns (Categorie | Sigle | Denomination)."""
    out = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for t in page.extract_tables():
                for row in t:
                    cells = [(c or "").replace("\n", " ").strip() for c in row]
                    if len(cells) < 3:
                        continue
                    cat, sigle, denom = cells[0], cells[1], cells[2]
                    if not denom or denom.lower() == "dénomination":
                        continue
                    r = blank_row()
                    r.update({
                        "ListLabel": 4, "CoType": "Microfinance Institution",
                        "Typology": f"Catégorie {cat}" if cat else "",
                        "Name": denom,
                        "InternalID_1": sigle, "InternalID_1_type": "Sigle",
                        "City": "Nouakchott", "Cntry": "MR",
                        "ListCode": 3, "ListName": LIST_NAMES[3],
                    })
                    out.append(r)
    return out


# ==================================================================
# RUN
# ==================================================================
print("[MR CBMAU] reading source URLs from Drupal JSON:API ...")
banks_url, payment_url, imf_url = fetch_sources()
print(f"   banks img:   {banks_url}")
print(f"   payment img: {payment_url}")
print(f"   imf pdf:     {imf_url}")

all_rows = []
skipped = []

print("[List 1] Banques agréées (OCR) ...")
try:
    p = download(banks_url, "list1_banks.png")
    r1 = scrape_list1_banks(p); print(f"   {len(r1)} banks"); all_rows += r1
except Exception as e:
    print(f"   !! LIST 1 SKIPPED (needs Windows Tesseract): {e}"); skipped.append(1)

print("[List 2] Etablissements de paiement (OCR) ...")
try:
    p = download(payment_url, "list2_payment.png")
    r2 = scrape_list2_payment(p); print(f"   {len(r2)} entities"); all_rows += r2
except Exception as e:
    print(f"   !! LIST 2 SKIPPED (needs Windows Tesseract): {e}"); skipped.append(2)

print("[List 3] Institutions de Microfinance (PDF) ...")
try:
    p = download(imf_url, "list3_imf.pdf")
    r3 = scrape_list3_imf(p); print(f"   {len(r3)} IMF"); all_rows += r3
except Exception as e:
    print(f"   !! LIST 3 SKIPPED: {e}"); skipped.append(3)

for r in all_rows:
    r["RegCtry"] = "MR"
    r["RegCode"] = "CBMAU"
    r["RegulationType"] = "Regulated"
    r["ListLanguage"] = "FR"
    r["ListProcessDate"] = PROCESS_DATE

df = pd.DataFrame(all_rows).reindex(columns=COLUMNS, fill_value="")
now = datetime.datetime.now()
outfile = os.path.join(
    scriptfolder,
    "{} SQL Ready {}.xlsx".format(regulatorName, str(now).replace(":", ".")[:-7]))
df.to_excel(outfile, sheet_name="SQL Ready", index=False)

print("\n==== SUMMARY ====")
print("Total rows:", len(df))
for code in sorted(df['ListCode'].unique()):
    print(f"  List {code}: {len(df[df['ListCode'] == code])}")
if skipped:
    print(f"  !! INCOMPLETE - lists {skipped} not produced on this machine "
          f"(run on the Windows server with bundled Tesseract-OCR).")
print("Output:", outfile)

for rem in os.listdir(tempfolder):
    os.remove(os.path.join(tempfolder, rem))
