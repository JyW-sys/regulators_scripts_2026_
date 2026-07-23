# -*- coding: utf-8 -*-
# ------------------------------------------------------------------
# PE SBS  -  Superintendencia de Banca, Seguros y AFP (Peru)
# Source: https://www.sbs.gob.pe/supervisados-y-registros/empresas-supervisadas
# Jira:   DECD-4818  (epic DECD-3438, Regulators 2026 - Crawlers)
#
# Three source mechanisms, all server-rendered (no Selenium needed):
#
#   GROUP A (15 directorio lists)  -> each page embeds an iframe whose src
#       is a data endpoint:
#           /app/sadel/Paginas/Redir/ListarFuncionarios.aspx?codTpEntidad=<CODE>
#       which returns a plain HTML table:
#           Entidad | Cargo | Funcionario | Direccion | Telefono | Fax | Fecha
#       (multiple rows per entity - one per officer; we de-dup by Entidad).
#
#   LIST 17  "Representantes de Empresas del Exterior" -> free-text HTML:
#           <span class="subsubtitulo"> = entity name
#           <span class="JERF_texto1">  = <br>-separated fields
#                                         (Domicilio:, Telf:, E-mail:)
#
#   LIST 19  "Cooperativas de Ahorro y Credito (COOPAC)" -> the page links to
#       a monthly PDF (documentos.aspx?cod=COOPAC002 -> 302 -> *.PDF) holding
#       a ruled table parsed with pdfplumber.
#
# The whole site is served as cp1252 despite declaring utf-8, so we force
# r.encoding = "cp1252".
# ------------------------------------------------------------------
import os
import re
import io
import time
import datetime
import requests
import urllib3
from bs4 import BeautifulSoup
import pandas as pd
import pdfplumber

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

regulatorName = "PE SBS"
print(f"Running {regulatorName} Web Scraping Tool v.1.0")

scriptfolder = os.path.dirname(os.path.abspath(__file__))
tempfolder = os.path.join(scriptfolder, "tempfolder")
os.makedirs(tempfolder, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RegulatorBot/1.0"}
DIR_BASE = "https://www.sbs.gob.pe/supervisados-y-registros/empresas-supervisadas/"
ENDPOINT = "https://www.sbs.gob.pe/app/sadel/Paginas/Redir/ListarFuncionarios.aspx?codTpEntidad={}"

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

# regdict parsed from the Jira description (DECD-4818).
# GROUP A lists carry their codTpEntidad endpoint code; the two special
# lists (17 text, 19 pdf) are flagged with handler="text"/"pdf".
regdict = {
    1:  {"ListName": "Empresas Bancarias",                       "code": "B"},
    2:  {"ListName": "Empresas De Seguros",                      "code": "S"},
    3:  {"ListName": "Administradoras De Fondos De Pensiones",   "code": "FP"},
    4:  {"ListName": "Empresas Financieras",                     "code": "F"},
    6:  {"ListName": "Cajas Rurales De Ahorro Y Credito",        "code": "R"},
    7:  {"ListName": "Cajas Municipales",                        "code": "C"},
    8:  {"ListName": "Empresas De Creditos",                     "code": "E"},
    9:  {"ListName": "Cajas Y Derramas",                         "code": "DE"},
    10: {"ListName": "Empresa De Transferencia De Fondos",       "code": "TF"},
    11: {"ListName": "Empresas Afianzadoras Y De Garantias",     "code": "G"},
    12: {"ListName": "Almacenes Generales De Deposito",          "code": "AG"},
    13: {"ListName": "Empresa De Transporte, Custodia Y Administracion De Numerario", "code": "TC"},
    14: {"ListName": "Empresa De Servicios Fiduciarios",         "code": "FD"},
    15: {"ListName": "Fondo De Cajas Municipales",               "code": "FF"},
    17: {"ListName": "Representantes De Empresas Del Exterior",  "handler": "text",
         "url": DIR_BASE + "directorio-de-otras-empresas-supervisadas/representantes-de-empresas-del-exterior"},
    18: {"ListName": "Empresas Administradoras Hipotecarias",    "code": "AH"},
    19: {"ListName": "Cooperativas De Ahorro Y Credito",         "handler": "pdf",
         "url": "https://www.sbs.gob.pe/app/coopac_web_doc/Paginas/documentos.aspx?cod=COOPAC002"},
}


def get(url, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=60, verify=False)
            r.raise_for_status()
            return r
        except Exception as e:
            print(f"   retry {i + 1}/{retries} for {url}: {e}")
            time.sleep(2)
    raise RuntimeError(f"Failed to fetch {url}")


def fix_mojibake(s):
    """The Representantes page mixes latin-1 and UTF-8 bytes, so some chars
    arrive as UTF-8 misread under cp1252 (e.g. 'Perú' -> 'PerÃº'). Re-decode
    only the Ã/Â lead-byte sequences; leave already-correct chars (ó, Ñ) alone."""
    def repl(m):
        try:
            return m.group(0).encode("cp1252").decode("utf-8")
        except Exception:
            return m.group(0)
    return re.sub(r"[ÂÃ][\x80-\xff]", repl, str(s))


def city_from_address(addr):
    """SBS addresses end '<street>, <district>, <province>, <department>'.
    The district is the most city-like field -> 3rd segment from the end."""
    parts = [p.strip() for p in str(addr).split(",") if p.strip()]
    if len(parts) >= 3:
        return parts[-3]
    return parts[-1] if parts else ""


# ---- GROUP A: directorio table via the codTpEntidad endpoint ----
def scrape_table(code):
    r = get(ENDPOINT.format(code))
    r.encoding = "cp1252"
    tables = pd.read_html(io.StringIO(r.text))
    df = tables[0]
    df.columns = [str(c).strip() for c in df.columns]
    # drop the blank spacer rows between entities
    df = df[df["Entidad"].notna() & (df["Entidad"].astype(str).str.strip() != "")]
    # one record per entity: first non-empty value of each field
    def first_valid(s):
        for v in s:
            if pd.notna(v) and str(v).strip():
                return str(v).strip()
        return ""
    recs = []
    for name, g in df.groupby("Entidad", sort=False):
        addr = first_valid(g.get("Dirección", g.get("Direccion", pd.Series(dtype=str))))
        phone = first_valid(g.get("Teléfono", g.get("Telefono", pd.Series(dtype=str))))
        # phones come from read_html as floats ('6194160.0') -> trim the .0
        phone = re.sub(r"\.0$", "", phone)
        fax = re.sub(r"\.0$", "", first_valid(g.get("Fax", pd.Series(dtype=str))))
        recs.append({
            "Name": str(name).strip(),
            "Address_1": addr,
            "City": city_from_address(addr),
            "Phone": phone,
            "Fax": fax,
            "Cntry": "PE",
        })
    return recs


# ---- LIST 17: free-text representatives ----
def scrape_text(url):
    r = get(url)
    r.encoding = "cp1252"
    soup = BeautifulSoup(r.text, "html.parser")
    recs = []
    for title in soup.select("span.subsubtitulo"):
        name = title.get_text(" ", strip=True)
        if not name:
            continue
        row = title.find_parent("tr")
        body = None
        if row:
            nxt = row.find_next_sibling("tr")
            if nxt:
                body = nxt.select_one("span.JERF_texto1")
        if body is None:
            continue
        lines = [ln.strip() for ln in body.get_text("\n").split("\n") if ln.strip()]
        dom = telf = email = res = ""
        for ln in lines:
            low = ln.lower()
            if low.startswith("domicilio"):
                dom = ln.split(":", 1)[-1].strip()
            elif low.startswith("telf") or low.startswith("tel"):
                telf = ln.split(":", 1)[-1].strip()
            elif low.startswith("e-mail") or low.startswith("email") or low.startswith("correo"):
                email = ln.split(":", 1)[-1].strip()
            elif "res. sbs" in low:
                m = re.search(r"N[°ºo]?\s*([\d\-/]+)", ln)
                res = m.group(1) if m else ln
        a = body.select_one('a[href^="mailto:"]')
        if a and not email:
            email = a.get_text(strip=True)
        recs.append({
            "Name": name,
            "Address_1": dom,
            "City": city_from_address(dom),
            "Phone": telf,
            "Email": email,
            "InternalID_1": res,
            "InternalID_1_type": "Resolucion SBS" if res else "",
            "Cntry": "PE",
        })
    return recs


# ---- LIST 19: COOPAC monthly PDF ----
def scrape_pdf(url):
    r = get(url)
    pdf_path = os.path.join(tempfolder, "PE_SBS_COOPAC.pdf")
    with open(pdf_path, "wb") as f:
        f.write(r.content)
    recs = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for tbl in page.extract_tables():
                for row in tbl:
                    cells = [(c or "").replace("\n", " ").strip() for c in row]
                    if len(cells) < 9:
                        continue
                    nro, name, ruc, _nivel, reg, fecha, _ops, region, prov = cells[:9]
                    if not re.fullmatch(r"\d+", nro):   # skip header / blank rows
                        continue
                    recs.append({
                        "Name": name,
                        "InternalID_1": ruc,
                        "InternalID_1_type": "RUC" if ruc else "",
                        "InternalID_2": reg,
                        "InternalID_2_type": "N de Registro COOPAC" if reg else "",
                        "RegulationDate": fecha,
                        "City": prov,
                        "Address_1": region,
                        "Cntry": "PE",
                    })
    # pdfplumber detects overlapping table regions per page, so every COOPAC
    # comes out twice; RUC is the unique key -> keep first occurrence each.
    seen, unique = set(), []
    for rec in recs:
        key = rec["InternalID_1"] or rec["Name"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(rec)
    return unique


# ------------------------------------------------------------------
rows = []
list_counts = []  # (list_nr, n) for the summary
process_date = datetime.date.today().isoformat()

for list_nr, info in regdict.items():
    handler = info.get("handler", "table")
    print(f"[List {list_nr}] {info['ListName']} ({handler}) ...")
    try:
        if handler == "table":
            recs = scrape_table(info["code"])
        elif handler == "text":
            recs = scrape_text(info["url"])
        else:
            recs = scrape_pdf(info["url"])
    except Exception as e:
        print(f"   !! list {list_nr} failed: {e}")
        list_counts.append((list_nr, 0))
        continue
    for rec in recs:
        rec["ListCode"] = list_nr
        rec["ListName"] = info["ListName"]
        rec["ListLabel"] = info["ListName"]
        # rec["ListLanguage"] = "ES"
        rec["RegulationType"] = "Regulated"
        rec["RegCtry"] = "PE"
        rec["RegCode"] = "SBS"
        rec["ListProcessDate"] = process_date
        rows.append(rec)
    print(f"   {len(recs)} entities")
    list_counts.append((list_nr, len(recs)))

# Build the DataFrame strictly on the fixed schema.
df = pd.DataFrame(rows)
df = df.reindex(columns=COLUMNS, fill_value="")

# Normalize mixed-encoding artifacts across all text columns.
for col in df.columns:
    if df[col].dtype == object:
        df[col] = df[col].map(lambda v: fix_mojibake(v) if isinstance(v, str) else v)

now = datetime.datetime.now()
outfile = os.path.join(
    scriptfolder,
    "{} SQL Ready {}.xlsx".format(regulatorName, str(now).replace(":", ".")[:-7]),
)
df.to_excel(outfile, "SQL Ready", index=False)

print("\n==== SUMMARY ====")
print("Total rows:", len(df))
print("Columns:", len(df.columns))
for list_nr, n in list_counts:
    print(f"  List {list_nr:<3} {regdict[list_nr]['ListName'][:45]:<45} {n:>4}")
print("Output:", outfile)
