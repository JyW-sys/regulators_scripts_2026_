# -*- coding: utf-8 -*-
# ------------------------------------------------------------------
# DO SSDO  -  Superintendencia de Seguros de la Republica Dominicana
# Source: https://sis.gob.do/companias-aseguradoras-y-reaseguradoras/
# Jira:   DECD-4396  (epic DECD-3438, Regulators 2026 - Crawlers)
#
# The page is behind a Cloudflare "Just a moment..." challenge, so plain
# requests gets a 403. We use DrissionPage (real Chrome) to pass Cloudflare
# - the same approach already used by CW CBCSCW in this project - then parse
# the rendered HTML with BeautifulSoup.
#
# Layout: ONE <table>, 2 columns per row, each <td> is a full company block:
#     <strong>Name</strong><br>
#     address line<br> address line<br>
#     Tel.: (809) ... . Fax: (809) ...<br>
#     Email: <a href="mailto:..">..</a>[<br> www.site]
#
# Lists (from the Jira description):
#   ListNr 1  "Companias Aseguradoras"  -> the single table on the page
# ------------------------------------------------------------------
import os
import re
import time
import datetime
import pandas as pd
from bs4 import BeautifulSoup
from DrissionPage import ChromiumPage, ChromiumOptions
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

regulatorName = "DO SSDO"
print(f"Running {regulatorName} Web Scraping Tool v.1.0")

scriptfolder = os.path.dirname(os.path.abspath(__file__))
tempfolder = os.path.join(scriptfolder, "tempfolder")
os.makedirs(tempfolder, exist_ok=True)

URL = "https://sis.gob.do/companias-aseguradoras-y-reaseguradoras/"

# regdict parsed from the Jira description (DECD-4396)
regdict = {
    1: {"ListName": "Companias Aseguradoras",
        "URL": URL,
        "Comments": "Extract all entities from the table"},
}

# SQL-Ready column order. THIS IS THE FIXED PROJECT SCHEMA (see CLAUDE.md) -
# do NOT add, remove, or reorder keys. Note the double space in
# 'Address_2 -  Mother company'.
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


def fetch_html(url, timeout=120):
    """Open Chrome via DrissionPage, pass Cloudflare, return rendered HTML."""
    opt = ChromiumOptions().headless(False)
    dp = ChromiumPage(opt)
    try:
        dp.get(url)
        waited = 0
        while waited < timeout:
            time.sleep(3); waited += 3
            if "Just a moment" not in dp.title and dp.s_ele("tag:table"):
                break
        html = dp.html
    finally:
        dp.quit()
    return html


PHONE_RE = re.compile(r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}")


def phones(s):
    """Pull all phone-shaped numbers out of a string, joined with ' '."""
    return " ".join(PHONE_RE.findall(s))


def parse_cell(td):
    """Parse one company <td> block into mapped fields."""
    name_el = td.find("strong") or td.find("b")
    name = name_el.get_text(" ", strip=True).replace("\xa0", " ") if name_el else ""

    mail = td.find("a", href=lambda h: h and h.lower().startswith("mailto:"))
    email = mail.get_text(strip=True) if mail else ""

    # turn <br> into newlines so we keep the line structure
    for br in td.find_all("br"):
        br.replace_with("\n")
    lines = [ln.replace("\xa0", " ").strip() for ln in td.get_text("\n").split("\n") if ln.strip()]

    phone = fax = website = ""
    addr_lines = []
    for ln in lines:
        low = ln.lower()
        if ln == name:
            continue
        if low.startswith("tel"):                       # "Tel.: x . Fax: y" or "Tels.: a b"
            tel_part = re.split(r"fax\b", ln, flags=re.I)[0]
            fax_part = ln[len(tel_part):]
            phone = phones(tel_part)
            fax = phones(fax_part)
        elif low.startswith("fax"):
            fax = phones(ln)
        elif low.startswith("email") or "@" in ln:
            continue                                    # email taken from mailto link
        elif low.startswith("www") or low.startswith("http"):
            website = ln
        else:
            addr_lines.append(ln)

    address = " ".join(addr_lines)
    # City = comma-segment just before the R.D./D.N. country marker, else a
    # known city token, else blank.
    city = ""
    parts = [p.strip() for p in address.split(",") if p.strip()]
    for i, p in enumerate(parts):
        if re.match(r"^(r\.?\s*d\.?|d\.?\s*n\.?|rep[uú]blica)", p.lower()):
            if i > 0:
                city = parts[i - 1]
            break
    if not city:
        for p in parts:
            if "santo domingo" in p.lower() or "santiago" in p.lower():
                city = p
                break

    if website and not website.lower().startswith("http"):
        website = "https://" + website.lstrip("/")

    return {"Name": name, "Address_1": address, "City": city, "Cntry": "DO",
            "Phone": phone, "Fax": fax, "Email": email, "Website": website}


# ---- scrape ---------------------------------------------------------------
html = fetch_html(URL)
soup = BeautifulSoup(html, "html.parser")
table = soup.find("table")
if table is None:
    raise RuntimeError("No table found - Cloudflare may not have cleared.")

process_date = datetime.date.today().isoformat()
rows = []
for td in table.find_all("td"):
    if not td.get_text(strip=True):
        continue                                        # skip empty filler cells
    rec = parse_cell(td)
    if not rec["Name"]:
        continue
    rec.update({
        "Typology": "Compania Aseguradora/Reaseguradora",
        "ListCode": 1,
        "ListName": regdict[1]["ListName"],
        "RegCtry": "DO",
        "RegCode": "SSDO",
        "RegulationType": "Regulated",
        "ListProcessDate": process_date,
    })
    rows.append(rec)

df = pd.DataFrame(rows)
df = df.reindex(columns=COLUMNS, fill_value="")     # enforce exact fixed schema

now = datetime.datetime.now()
outfile = os.path.join(
    scriptfolder,
    "{} SQL Ready {}.xlsx".format(regulatorName, str(now).replace(":", ".")[:-7]),
)
df.to_excel(outfile, "SQL Ready", index=False)

# ---- generate name-list PDF (same reportlab pattern as CV BCV) ------------
arial_path = r"C:\Windows\Fonts\arial.ttf"
if os.path.exists(arial_path):
    pdfmetrics.registerFont(TTFont("ArialUni", arial_path))
    FONT_NAME = "ArialUni"
else:
    FONT_NAME = "Helvetica"


def safe_filename(name):
    name = str(name).strip()
    return re.sub(r'[\\/:*?"<>|]+', "_", name) or "UNKNOWN"


def draw_header(c, y):
    c.setFont(FONT_NAME, 14)
    c.drawString(72, y, "Name")
    c.line(72, y - 4, 540, y - 4)
    c.setFont(FONT_NAME, 12)
    return y - 24


def export_list_to_pdf(data_list, pdf_filename):
    c = canvas.Canvas(pdf_filename, pagesize=letter)
    c.setFont(FONT_NAME, 12)
    x = 72
    y = draw_header(c, 740)
    max_lines_per_page = 32
    line_count = 0
    for item in data_list:
        c.drawString(x, y, str(item))
        y -= 20
        line_count += 1
        if line_count >= max_lines_per_page:
            c.showPage()
            c.setFont(FONT_NAME, 12)
            y = draw_header(c, 740)
            line_count = 0
    c.save()


# One PDF per (RegCtry, ListCode) pair, written next to the xlsx in DO SSDO.
base_name = os.path.splitext(outfile)[0]
for (regctry, list_code), group in df.groupby(["RegCtry", "ListCode"], dropna=False):
    items = group["Name"].dropna().astype(str).tolist()
    if not items:
        continue
    pdf_path = f"{base_name} - {safe_filename(regctry)}-{safe_filename(list_code)}.pdf"
    export_list_to_pdf(items, pdf_path)
    print(f"[INFO] wrote {len(items)} names -> {os.path.basename(pdf_path)}")

print("\n==== SUMMARY ====")
print("Total rows:", len(df))
print("Columns:", len(df.columns))
print("Output:", outfile)
