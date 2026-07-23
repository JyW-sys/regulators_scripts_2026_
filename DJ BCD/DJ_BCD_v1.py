# -*- coding: utf-8 -*-
# ------------------------------------------------------------------
# DJ BCD  -  Banque Centrale de Djibouti
# Source: https://banque-centrale.dj/les-etablissements-agrees/
# Jira:   DECD-4395  (epic DECD-3438, Regulators 2026 - Crawlers)
#
# Fully server-rendered (no Cloudflare / JS) -> plain requests + BeautifulSoup.
# The page holds 7 TablePress tables (<table class="tablepress">), each headed
# by its category name. They map onto the 4 Jira lists:
#
#   List 1 Etablissements Bancaires            -> Banques conventionnelles,
#                                                 Emetteurs de monnaie electronique,
#                                                 Fenetres islamiques, Banques islamiques
#   List 2 Micro Finance                       -> Institutions de microfinance
#   List 3 Institutions Financieres Specialisees -> Institutions financieres specialisees
#   List 4 Auxiliaires Financiers              -> Auxiliaires financiers
#
# Two header schemas exist, so columns are mapped by header NAME, not position.
# ------------------------------------------------------------------
import os
import re
import unicodedata
import datetime
import requests
import urllib3
import pandas as pd
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

regulatorName = "DJ BCD"
print(f"Running {regulatorName} Web Scraping Tool v.1.0")

scriptfolder = os.path.dirname(os.path.abspath(__file__))
tempfolder = os.path.join(scriptfolder, "tempfolder")
os.makedirs(tempfolder, exist_ok=True)

URL = "https://banque-centrale.dj/les-etablissements-agrees/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RegulatorBot/1.0"}

# regdict parsed from the Jira description (DECD-4395)
regdict = {
    1: {"ListName": "Etablissements Bancaires"},
    2: {"ListName": "Micro Finance"},
    3: {"ListName": "Institutions Financieres Specialisees"},
    4: {"ListName": "Auxiliaires Financiers"},
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


def deaccent(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()


def list_for_category(name):
    """Map a table's category heading to its Jira ListNr (1-4)."""
    n = deaccent(name)
    if "microfinance" in n:
        return 2
    if "specialis" in n:
        return 3
    if "auxiliaires" in n:
        return 4
    if any(k in n for k in ["conventionnelles", "monnaie", "emetteurs", "fenetres", "islamiques"]):
        return 1
    return None


def col_index(headers, *keywords):
    """Return index of the first header containing any keyword (deaccented)."""
    for i, h in enumerate(headers):
        hd = deaccent(h)
        if any(k in hd for k in keywords):
            return i
    return None


# ---- scrape ---------------------------------------------------------------
r = requests.get(URL, headers=HEADERS, timeout=60, verify=False)
r.raise_for_status()
r.encoding = "utf-8"
soup = BeautifulSoup(r.text, "html.parser")

process_date = datetime.date.today().isoformat()
rows = []
section_counts = []

for table in soup.select("table.tablepress"):
    heading = table.find_previous(["h1", "h2"])
    category = heading.get_text(" ", strip=True) if heading else ""
    list_nr = list_for_category(category)
    if list_nr is None:
        continue

    thead = table.find("thead")
    headers = [th.get_text(" ", strip=True) for th in thead.find_all("th")] if thead else []
    i_name = col_index(headers, "nom", "raison sociale")
    i_sigle = col_index(headers, "sigle")
    i_addr = col_index(headers, "adresse", "siege social")
    i_phone = col_index(headers, "telephone")
    i_agr = col_index(headers, "agrement")

    body = table.find("tbody")
    n = 0
    for tr in (body.find_all("tr") if body else []):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
        if not cells:
            continue
        name = cells[i_name].strip() if i_name is not None and i_name < len(cells) else ""
        if not name:
            continue
        sigle = cells[i_sigle].strip() if i_sigle is not None and i_sigle < len(cells) else ""
        addr = cells[i_addr].strip() if i_addr is not None and i_addr < len(cells) else ""
        phone = cells[i_phone].strip() if i_phone is not None and i_phone < len(cells) else ""
        agr = cells[i_agr].strip() if i_agr is not None and i_agr < len(cells) else ""

        rows.append({
            "Name": name,
            "InternalID_1": sigle,
            "InternalID_1_type": "Sigle" if sigle else "",
            "Address_1": addr,
            "City": "Djibouti",
            "Cntry": "DJ",
            "Phone": phone,
            "RegulationDate": agr,
            "Typology": category,
            "ListCode": list_nr,
            "ListName": regdict[list_nr]["ListName"],
            "ListLabel": regdict[list_nr]["ListName"],
            "RegCtry": "DJ",
            "RegCode": "BCD",
            "ListProcessDate": process_date,
        })
        n += 1
    section_counts.append((list_nr, category, n))

df = pd.DataFrame(rows)
df = df.reindex(columns=COLUMNS, fill_value="")     # enforce exact fixed schema

now = datetime.datetime.now()
outfile = os.path.join(
    scriptfolder,
    "{} SQL Ready {}.xlsx".format(regulatorName, str(now).replace(":", ".")[:-7]),
)
df.to_excel(outfile, "SQL Ready", index=False)

print("\n==== SUMMARY ====")
print("Total rows:", len(df), "| Columns:", len(df.columns))
for list_nr, cat, n in section_counts:
    print(f"  List {list_nr}  {cat[:45]:45} {n:>3}")
print("Output:", outfile)
