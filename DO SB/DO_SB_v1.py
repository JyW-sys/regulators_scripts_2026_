# -*- coding: utf-8 -*-
# ------------------------------------------------------------------
# DO SB  -  Superintendencia de Bancos de la Republica Dominicana
# Source: https://www.sb.gob.do/supervisados/
# Jira:   DECD-4397  (epic DECD-3438, Regulators 2026 - Crawlers)
#
# The supervisados site is fully server-rendered, so a simple
# requests + BeautifulSoup walk is enough (no Selenium / JS needed).
#
#   Each listing page -> entity cards (a.name_container) -> detail page.
#   Each detail page exposes its fields as repeated blocks:
#       <div class="info_title_value_container">
#           <label>Registro</label><span>H-001-1-00-0101</span>
#       </div>
#   We parse those label->value pairs and map the Spanish labels to the
#   project's SQL-Ready columns.
#
# Lists (from the Jira description):
#   ListNr 1  "Entidades Autorizadas"     -> 4 sections:
#                 - Entidades de Intermediacion Financiera
#                 - Entidades de Intermediacion Cambiaria
#                 - Fiduciarias
#                 - Sociedades de Informacion Crediticia
#   ListNr 2  "Oficinas de Representacion" -> oficinas-de-representacion
# ------------------------------------------------------------------
import os
import re
import time
import datetime
import requests
from bs4 import BeautifulSoup
import pandas as pd

regulatorName = "DO SB"
print(f"Running {regulatorName} Web Scraping Tool v.1.0")

scriptfolder = os.path.dirname(os.path.abspath(__file__))
tempfolder = os.path.join(scriptfolder, "tempfolder")
os.makedirs(tempfolder, exist_ok=True)

BASE = "https://www.sb.gob.do"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RegulatorBot/1.0"}

# regdict parsed from the Jira description (DECD-4397)
regdict = {
    1: {"ListName": "Entidades Autorizadas",
        "sections": [
            "/supervisados/entidades-de-intermediacion-financiera/",
            "/supervisados/entidades-de-intermediacion-cambiaria/",
            "/supervisados/fiduciarias/",
            "/supervisados/sociedades-de-informacion-crediticia/",
        ]},
    2: {"ListName": "Oficinas de Representacion",
        "sections": [
            "/supervisados/oficinas-de-representacion/",
        ]},
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


def get_soup(url, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=40)
            r.raise_for_status()
            r.encoding = "utf-8"
            return BeautifulSoup(r.text, "html.parser")
        except Exception as e:
            print(f"   retry {i+1}/{retries} for {url}: {e}")
            time.sleep(2)
    raise RuntimeError(f"Failed to fetch {url}")


def _links_on_page(soup):
    """Extract detail-page hrefs from the entity cards on one listing page."""
    out = []
    for card in soup.select(".entity_card"):
        a = card.select_one("a.name_container") or card.select_one("a.btn_details_container, .btn_details_container a")
        if a and a.get("href"):
            href = a["href"]
            out.append(href if href.startswith("http") else BASE + href)
    return out


def collect_detail_links(section_path, max_pages=50):
    """Return ALL detail-page URLs from a listing section, across pages.

    The site paginates with ?page=N (1-indexed: page 1 = entries 1-24,
    page 2 = 25-..). Non-paginated sections ignore ?page= and just repeat
    the same cards, while paginated sections clamp to the last page once you
    over-request. Both cases are handled uniformly by stopping as soon as a
    page contributes no NEW links.
    """
    seen, out = set(), []
    for page in range(1, max_pages + 1):
        sep = "&" if "?" in section_path else "?"
        soup = get_soup(f"{BASE}{section_path}{sep}page={page}")
        page_links = _links_on_page(soup)
        new = [l for l in page_links if l not in seen]
        if not new:                 # no progress -> last page reached
            break
        for l in new:
            seen.add(l); out.append(l)
    return out


def parse_detail(url, section_label):
    """Parse one entity detail page into a field dict."""
    soup = get_soup(url)
    fields = {}
    for box in soup.select(".info_title_value_container"):
        lab = box.find("label")
        val = box.find(["span", "a"])
        if lab:
            key = lab.get_text(strip=True)
            value = val.get_text(" ", strip=True) if val else ""
            if key and key not in fields:
                fields[key] = value

    # entity display name + type + status from the header
    name_el = soup.select_one(".entity_info_container > label") or soup.select_one(".name_container span")
    name = name_el.get_text(strip=True) if name_el else ""
    type_el = soup.select_one(".entity_type")
    etype = type_el.get_text(strip=True) if type_el else ""
    status_el = soup.select_one(".entity_status_container .value_entity")
    status = status_el.get_text(strip=True) if status_el else ""

    addr = fields.get("Oficina principal", "")
    # crude City = trailing comma segment of the address
    city = addr.split(",")[-1].strip() if addr else ""

    website = fields.get("Página web", "")
    if website and not website.lower().startswith("http"):
        website = "https://" + website.lstrip("/")

    return {
        "Name": name or fields.get("Razón social", ""),
        "Typology": etype,
        "CoType": '',
        "RegulationType": status,
        "InternalID_1": fields.get("Registro", ""),
        "InternalID_1_type": "Registro" if fields.get("Registro") else "",
        "InternalID_2": fields.get("RNC o cédula", ""),
        "InternalID_2_type": "RNC" if fields.get("RNC o cédula") else "",
        "Name - Mother Company": fields.get("Razón social", ""),
        "Address_1": addr,
        "City": city,
        "Cntry": "DO",
        "Phone": fields.get("Teléfonos", ""),
        "Website": website,
        "Email": fields.get("Correo electrónico", ""),
        # "License_Type": fields.get("Productos y servicios autorizados", ""),
    }


def section_label(path):
    return path.strip("/").split("/")[-1].replace("-", " ").title()


rows = []
section_counts = []  # (list_nr, section_label, n) - for the QA summary only
process_date = datetime.date.today().isoformat()

for list_nr, info in regdict.items():
    for sec in info["sections"]:
        sec_lbl = section_label(sec)
        print(f"[List {list_nr}] {sec_lbl} ...")
        detail_urls = collect_detail_links(sec)
        print(f"   {len(detail_urls)} entities")
        n = 0
        for u in detail_urls:
            try:
                rec = parse_detail(u, sec_lbl)
            except Exception as e:
                print(f"   !! failed {u}: {e}")
                continue
            rec["ListCode"] = list_nr
            rec["ListName"] = info["ListName"]
            rec["ListLabel"] = info["ListName"]
            rec["RegCtry"] = "DO"
            rec["RegCode"] = "SB"
            # rec["ListLanguage"] = "ES"
            rec["ListProcessDate"] = process_date
            rows.append(rec)
            n += 1
            time.sleep(0.2)
        section_counts.append((list_nr, sec_lbl, n))

# Build the DataFrame strictly on the fixed schema: reindex drops any stray
# keys and adds any missing column, preserving the exact column order.
df = pd.DataFrame(rows)
df = df.reindex(columns=COLUMNS, fill_value="")

now = datetime.datetime.now()
outfile = os.path.join(
    scriptfolder,
    "{} SQL Ready {}.xlsx".format(regulatorName, str(now).replace(":", ".")[:-7]),
)
df = df[df['RegulationType']=='Operando']
df['RegulationType'] = df['RegulationType'].str.replace('Operando','Regulated')  # drop parenthetical notes
df.to_excel(outfile, "SQL Ready", index=False)

# print("\n==== SUMMARY ====")
# print("Total rows:", len(df))
# print("Columns:", len(df.columns))
# for list_nr, sec_lbl, n in section_counts:
#     print(f"  List {list_nr}  {sec_lbl:<40} {n:>3}")
# print("Output:", outfile)
