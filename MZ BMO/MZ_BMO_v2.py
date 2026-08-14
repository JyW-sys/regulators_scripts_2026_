# -*- coding: utf-8 -*-
# ------------------------------------------------------------------
# MZ BMO  -  Banco de Mocambique (Bank of Mozambique)
# Source page: https://www.bancomoc.mz/en/areas-of-expertise/licensing/licensing-of-institutions/
# Jira:   DECD-6332  (epic DECD-3438, Regulators 2026 - Crawlers)
#
# v2 changes vs v1 (v1 output was rejected):
#   1. Name is now the ORIGINAL PORTUGUESE name, verbatim from the source file.
#      v1 machine-translated it into English, which destroyed proper nouns
#      ("Cota Cambios" -> "Cota Exchange", "Caixa Mulher" -> "Women's Fund",
#      "Sociedade Interbancaria de Mocambique" -> "Interbank Company of
#      Mozambique"). House convention for Portuguese/Spanish regulators
#      (ST BCSTP, ES BES) is original-language Name.
#   2. 'Name - Mother Company' is left blank. v1 stuffed the Portuguese name
#      into it for all 53 rows; that column is for a genuine parent company,
#      and this source publishes no ownership data.
#   3. The sheet's own column-header row ("Nr | Sigla | Nome da Instituicao |
#      ...") is now explicitly skipped instead of relying on it happening to
#      appear before the first category header.
#   4. The download to use is chosen by the REFERENCE PERIOD in the link title
#      ("... - Janeiro 2025"), not by the publication date. The site re-publishes
#      old files (the 2021 file carries a later publish date than the 2023 one),
#      so a publish-date sort can pick a stale list.
#   5. City extraction: an explicit "Cidade/Vila/Distrito de X" marker in the
#      entity's own address now captures ANY place name, not only names present
#      in a hard-coded gazetteer.
#   6. Rows are emitted in Jira ListNr order (1..9) rather than sheet order.
#   7. ListValidityDate is derived from the file's reference month (end of
#      month) instead of being hard-coded.
#
# Per the Jira Comments field for ListNr 1 ("Download the most recent Excel
# file from the 'List of authorised institutions' and extract the entities
# from each list under the listName category"): the page's "List of authorised
# institutions" section links several dated .xls downloads; the scraper picks
# the one with the most recent reference period (currently "Relacao das ICSF em
# Funcionamento - Janeiro 2025") and mines ALL 9 Jira lists out of its single
# "Relacao ICSF" sheet -- the 9 ListNr categories are exactly the top-level
# section headers in that sheet (Bancos, Microbancos, Cooperativas de Credito,
# ..., Casas de Cambio).
#
# Sheet layout (header row: Nr | Sigla | Nome da Instituicao | Sede | Actividades):
#   - A "header" row is any row whose "Nome da Instituicao" cell is empty.
#     Its label sits in whichever of the Nr/Sigla columns is non-empty.
#   - Top-level category headers (e.g. "Bancos") start a new ListNr/ListName.
#   - "Categoria de ..." headers (only under the payments section) start a
#     payment sub-type used for CoType.
#   - "Cidade de X" / "Provincia de X" headers set a fallback City for the
#     entities that follow, until the next header.
#   - A data row has Nr (int), Sigla (optional abbreviation), Nome da
#     Instituicao (entity name), Sede (one free-text blob mixing address /
#     phone / fax / e-mail-or-website), and Actividades -- multi-paragraph
#     legal boilerplate identical within a category, not mapped to any field.
#
# Language handling (Portuguese source):
#   Name         -> original Portuguese, verbatim (whitespace/comma tidy only)
#   Address_1    -> kept in Portuguese (postal form)
#   CoType       -> English institution-type descriptor (controlled vocabulary)
#   License_Type -> original Portuguese category label from the sheet
#   ListLanguage -> 'PT'
# ------------------------------------------------------------------
import os
import re
import datetime
import requests
import urllib3
import pandas as pd
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

regulatorName = "MZ BMO"
print(f"Running {regulatorName} Web Scraping Tool v.2.0")

# ------ workspace path -------------------------------------------------
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))
except NameError:
    scriptfolder = os.getcwd()
os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, "tempfolder")
os.makedirs(tempfolder, exist_ok=True)

PAGE_URL = "https://www.bancomoc.mz/en/areas-of-expertise/licensing/licensing-of-institutions/"
SITE_ROOT = "https://www.bancomoc.mz"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
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


def blank_row():
    return {c: '' for c in COLUMNS}


# ==================================================================
# STEP 1 - find and download the "List of authorised institutions" .xls
#          with the most recent REFERENCE PERIOD
# ==================================================================
PT_MONTHS = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
    "outubro": 10, "novembro": 11, "dezembro": 12,
}
PUBDATE_RE = re.compile(r"^\s*(\d{1,2}-\d{1,2}-\d{4})")
YEAR_RE = re.compile(r"\b(20\d{2})\b")


def _reference_period(title):
    """(year, month) reference period announced in a download's link text.

    'Relacao das ICSF em Funcionamento - Janeiro 2025' -> (2025, 1)
    'Relacao das ICSF em funcionamento em 2024'        -> (2024, 12)
    A title with no year at all sorts last.
    """
    low = title.lower()
    years = YEAR_RE.findall(title)
    if not years:
        return (0, 0)
    year = int(years[-1])
    for name, num in PT_MONTHS.items():
        if re.search(r"\b" + name + r"\b", low):
            return (year, num)
    return (year, 12)


def _publish_date(title):
    m = PUBDATE_RE.search(title)
    if not m:
        return datetime.datetime.min
    try:
        return datetime.datetime.strptime(m.group(1), "%d-%m-%Y")
    except ValueError:
        return datetime.datetime.min


def find_latest_xls():
    r = requests.get(PAGE_URL, headers=HEADERS, verify=False, timeout=60)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    h3 = None
    for h in soup.find_all("h3"):
        if "List of authorised institutions" in h.get_text():
            h3 = h
            break
    if h3 is None:
        raise RuntimeError("Could not find 'List of authorised institutions' heading on the page")

    # Download blocks are the <a> elements that follow the heading in document
    # order, up to the next <h3> (which starts the microcredit-operators list).
    candidates = []
    for el in h3.find_all_next():
        if el.name == "h3":
            break
        if el.name == "a" and el.get("href", "").lower().endswith((".xls", ".xlsx")):
            title = re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()
            href = el["href"]
            if href.startswith("/"):
                href = SITE_ROOT + href
            candidates.append((title, href))
    if not candidates:
        raise RuntimeError("No .xls/.xlsx download links found under 'List of authorised institutions'")

    candidates.sort(key=lambda t: (_reference_period(t[0]), _publish_date(t[0])), reverse=True)
    title, href = candidates[0]
    return title, href, _reference_period(title)


def download_xls(url):
    dest = os.path.join(tempfolder, "MZ_BMO_licensed_institutions.xls")
    r = requests.get(url, headers={**HEADERS, "Referer": PAGE_URL}, verify=False, timeout=90)
    r.raise_for_status()
    with open(dest, "wb") as fh:
        fh.write(r.content)
    return dest


def month_end(year, month):
    if year == 0:
        return ""
    if month == 12:
        return datetime.date(year, 12, 31).isoformat()
    return (datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)).isoformat()


# ==================================================================
# STEP 2 - category (ListNr) / payment sub-type / city-header maps
# ==================================================================
# Portuguese header text as it appears in the sheet -> Jira ListNr
CATEGORY_MAP = {
    "Bancos": 1,
    "Microbancos": 2,
    "Cooperativas de Crédito": 3,
    "Sociedades corretoras": 4,
    "Sociedades de Investimento": 5,
    "Empresas Prestadoras de Serviços de Pagamentos": 6,
    "Sociedades Finaceiras de Corretagem": 7,
    "Sociedades Emitentes ou Gestoras de Cartões de Crédito": 8,
    "Casas de Câmbio": 9,
}
# reverse map: ListNr -> original Portuguese header label (used for License_Type)
PT_LABEL_BY_LISTNR = {v: k for k, v in CATEGORY_MAP.items()}

# ListLabel: 1 = bank, 2 = insurance, 3 = bank & insurance, 4 = everything else.
# Bancos / Microbancos / Cooperativas de Credito are deposit-taking credit
# institutions -> 1. No insurance list is published by BM -> no 2 or 3.
LISTLABEL_BY_LISTNR = {1: 1, 2: 1, 3: 1, 4: 4, 5: 4, 6: 4, 7: 4, 8: 4, 9: 4}

# ListNr -> (Jira ListName verbatim, default English CoType)
LISTNR_INFO = {
    1: ("Bancos", "Bank"),
    2: ("Microbancos", "Microbank"),
    3: ("Cooperativas de Crédito", "Credit Cooperative"),
    4: ("Sociedades corretoras", "Brokerage Company"),
    5: ("Sociedades de Investimento", "Investment Company"),
    6: ("Empresas Prestadoras de Serviços de Pagamentos", None),  # CoType from sub-category
    7: ("Sociedades Finaceiras de Corretagem", "Brokerage Finance Company"),
    8: ("Sociedades Emitentes ou Gestoras de Cartoes de Credito", "Credit Card Issuer/Manager"),
    9: ("Casas de Câmbio", "Foreign Exchange Bureau"),
}

PAYMENT_SUBCAT_EN = {
    "categoria de instituições de moeda electrónica": "Electronic Money Institution",
    "categoria de agregadores de pagamentos": "Payment Aggregator",
    "categoria de instituições de transferência de fundos": "Money Transfer Institution",
}

SHEET_HEADER_TOKENS = {"nome da instituição", "nome da instituicao", "sede", "sigla", "actividades"}
CITY_HEADER_RE = re.compile(r"^(Cidade|Prov[ií]ncia)\s+d[aeo]s?\s+(.+)$", re.IGNORECASE)
CITY_TYPO_FIX = {"cabo delegado": "Cabo Delgado"}

# ==================================================================
# STEP 3 - "Sede" free-text blob -> Address_1 / City / Phone / Fax / Email / Website
# ==================================================================
# Multi-word / accented place names that a single-token capture would clip.
GAZETTEER = ["Cabo Delgado", "Xai-Xai", "Maputo", "Matola", "Beira", "Chimoio",
             "Pemba", "Nacala", "Angónia", "Caia", "Nampula", "Lichinga",
             "Morrumbene", "Quelimane", "Tete", "Sofala", "Manica", "Niassa",
             "Inhambane", "Gaza", "Zambézia", "Cuamba", "Montepuez", "Dondo"]
GAZETTEER_RE = re.compile(r"\b(" + "|".join(re.escape(c) for c in GAZETTEER) + r")\b",
                          re.IGNORECASE)

# An explicit "Cidade de X" / "Vila de X" / "Distrito de X" marker inside the
# entity's own address is the strongest signal, and unlike v1 it is no longer
# restricted to gazetteer members (v1 returned nothing for towns it had not
# been told about). One capitalised token is captured: every multi-word place
# in this source ("Cabo Delgado") only ever appears as a section header, and a
# greedy multi-token capture would swallow the trailing "Telf"/"Tel" label.
# "Provincia de X" is deliberately ranked BELOW a bare gazetteer hit: a province
# is not a city, so a real town named in the address wins (e.g. Servcred is in
# "Cidade de Lichinga, Provincia do Niassa" -> Lichinga).
PLACE_TOKEN = r"([A-ZÁÀÂÃÉÊÍÓÔÕÚÜÇ][A-Za-zÁÀÂÃÉÊÍÓÔÕÚÜÇáàâãéêíóôõúüç'\-]+)"
INLINE_CITY_RE = re.compile(r"(?:Cidade|Vila|Distrito)\s+d[aeo]s?\s+" + PLACE_TOKEN,
                            re.IGNORECASE)
INLINE_PROVINCE_RE = re.compile(r"Prov[ií]ncia\s+d[aeo]s?\s+" + PLACE_TOKEN,
                                re.IGNORECASE)

TELFAX_NORMALIZE_RE = re.compile(r"(?:Tel(?:efone)?|Telef|Telf)\.?\s*/\s*Fax\.?:?", re.IGNORECASE)
LABEL_RE = re.compile(r"(TELFAX|Telefones?|Telef|Telf|Tel|Celular|Cel|Fax)\.?:?", re.IGNORECASE)
MAIL_RE = re.compile(r"E[\s\-]*mail\.?:?\s*", re.IGNORECASE)
TRAILING_DIGITS_RE = re.compile(r"(\d[\d/;\-\s]{5,}\d)\s*$")
STRIP_CHARS = " ,;:.-*/–—"


def clean_text(s):
    s = (s or "").strip()
    s = s.replace("–", "-").replace("—", "-")   # en/em dash -> hyphen
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+,", ",", s)
    s = re.sub(r",(?=\S)", ", ", s)      # ensure a space after a comma
    return s.strip()


def clean_name(s):
    """Portuguese name, verbatim apart from whitespace/comma tidying."""
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+,", ",", s)
    s = re.sub(r",(?=\S)", ", ", s)
    return s.strip()


def normalise_place(token):
    token = (token or "").strip(STRIP_CHARS)
    if not token:
        return ""
    fixed = CITY_TYPO_FIX.get(token.lower())
    if fixed:
        return fixed
    if token.isupper():          # "MAPUTO" -> "Maputo"
        return token.title()
    return token


def city_from_address(raw):
    """Best city/town named inside the entity's own 'Sede' text ('' if none)."""
    text = raw or ""
    m = INLINE_CITY_RE.search(text)
    if m:
        return normalise_place(m.group(1))
    m = GAZETTEER_RE.search(text)
    if m:
        return normalise_place(m.group(1))
    m = INLINE_PROVINCE_RE.search(text)
    if m:
        return normalise_place(m.group(1))
    return ""


def parse_sede(raw):
    """Split the 'Sede' blob into (address, city, phone, fax, email, website)."""
    text = raw or ""
    text = TELFAX_NORMALIZE_RE.sub("TELFAX:", text)
    text = text.replace("–", "-").replace("—", "-")

    city = city_from_address(raw or "")

    # e-mail / website (independent pass; BM writes both behind an "E-mail:" label)
    email, website = "", ""
    m_mail = MAIL_RE.search(text)
    if m_mail:
        rest = text[m_mail.end():]
        cut = rest.find(",")
        val = (rest if cut == -1 else rest[:cut]).strip(STRIP_CHARS)
        if "@" in val:
            email = val
        elif val:
            website = val

    matches = list(LABEL_RE.finditer(text))
    if not matches:
        address = clean_text(text.strip(STRIP_CHARS))
        phone = ""
        m_tail = TRAILING_DIGITS_RE.search(address)
        if m_tail:
            phone = m_tail.group(1).strip()
            address = address[:m_tail.start()].strip(STRIP_CHARS)
        return clean_text(address), city, phone, "", email, website

    address = clean_text(text[:matches[0].start()].strip(STRIP_CHARS))
    phone_parts, fax_parts = [], []
    for i, m in enumerate(matches):
        label = m.group(1).upper()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        comma_idx = text.find(",", start, end)
        if comma_idx != -1:
            end = comma_idx
        value = re.sub(r"\s+", " ", text[start:end].strip(STRIP_CHARS)).strip()
        if not value:
            continue
        if label == "TELFAX":
            phone_parts.append(value)
            fax_parts.append(value)
        elif label == "FAX":
            fax_parts.append(value)
        else:   # TEL / TELF / TELEF / TELEFONE(S) / CEL / CELULAR
            phone_parts.append(value)

    phone = "; ".join(dict.fromkeys(p for p in phone_parts if p))
    fax = "; ".join(dict.fromkeys(f for f in fax_parts if f))
    return address, city, phone, fax, email, website


# ==================================================================
# STEP 4 - walk the sheet and build rows
# ==================================================================
def pick_sheet(xls_path):
    xl = pd.ExcelFile(xls_path)
    for name in xl.sheet_names:
        if "icsf" in name.lower():
            return name
    return xl.sheet_names[0]


def scrape():
    title, xls_url, ref_period = find_latest_xls()
    print(f"[MZ BMO] selected download: {title}")
    print(f"[MZ BMO] url: {xls_url}")
    xls_path = download_xls(xls_url)
    print(f"[MZ BMO] downloaded to {xls_path}")

    validity_date = month_end(*ref_period)
    sheet = pick_sheet(xls_path)
    df_raw = pd.read_excel(xls_path, sheet_name=sheet, header=None)
    print(f"[MZ BMO] sheet '{sheet}' -> {df_raw.shape[0]} raw rows, "
          f"reference period {ref_period[0]}-{ref_period[1]:02d}")

    process_date = datetime.datetime.now().strftime('%Y-%m-%d')

    rows_by_list = {nr: [] for nr in LISTNR_INFO}
    current_listnr = None
    current_payment_cotype = None
    current_city = ""

    for i in range(len(df_raw)):
        nr_col = df_raw.iat[i, 1] if df_raw.shape[1] > 1 else None
        sigla_col = df_raw.iat[i, 2] if df_raw.shape[1] > 2 else None
        name_col = df_raw.iat[i, 3] if df_raw.shape[1] > 3 else None
        sede_col = df_raw.iat[i, 4] if df_raw.shape[1] > 4 else None

        name_val = name_col if pd.notna(name_col) else None

        # --- the sheet's own column-header row is not an entity ------------
        if name_val is not None and str(name_val).strip().lower() in SHEET_HEADER_TOKENS:
            continue

        if name_val is None:
            # header / separator row - its label sits in nr_col or sigla_col
            label = None
            if pd.notna(nr_col) and isinstance(nr_col, str):
                label = nr_col.strip()
            elif pd.notna(sigla_col) and isinstance(sigla_col, str):
                label = sigla_col.strip()
            if not label:
                continue    # blank spacer row

            if label in CATEGORY_MAP:
                current_listnr = CATEGORY_MAP[label]
                current_payment_cotype = None
                current_city = ""
                continue

            if label.lower().startswith("categoria de"):
                key = label.strip(" ;").lower()
                current_payment_cotype = PAYMENT_SUBCAT_EN.get(key, label.strip(" ;"))
                current_city = ""
                continue

            m_city = CITY_HEADER_RE.match(label)
            if m_city:
                current_city = normalise_place(m_city.group(2))
                continue

            # unrecognised header text - ignore (defensive)
            print(f"[MZ BMO] WARNING: unrecognised header row {i}: {label!r}")
            continue

        # ---- data row -----------------------------------------------------
        if current_listnr is None:
            print(f"[MZ BMO] WARNING: entity before any category header, row {i}")
            continue

        pt_name = clean_name(str(name_val))
        if not pt_name:
            continue

        sigla = clean_name(str(sigla_col)) if pd.notna(sigla_col) else ""
        address, city_in_address, phone, fax, email, website = parse_sede(
            str(sede_col) if pd.notna(sede_col) else "")
        # A place named in the entity's own address is more granular than the
        # section's city/province grouping header, so it wins; the header is
        # only a fallback for entities whose address names no place at all.
        city = city_in_address or current_city

        list_name, default_cotype = LISTNR_INFO[current_listnr]
        cotype = current_payment_cotype if current_listnr == 6 else default_cotype

        pt_category_label = PT_LABEL_BY_LISTNR.get(current_listnr, "")
        license_type = pt_category_label
        if current_listnr == 6 and current_payment_cotype:
            license_type = f"{pt_category_label} - {current_payment_cotype}"

        r = blank_row()
        r.update({
            "ListLabel": LISTLABEL_BY_LISTNR.get(current_listnr, 4),
            "Name": pt_name,                       # original Portuguese, verbatim
            "InternalID_1": sigla,
            "InternalID_1_type": "Sigla" if sigla else "",
            "CoType": cotype or "",
            "License_Type": license_type,
            "Address_1": address,
            "City": city,
            "Cntry": "MZ",
            "Phone": phone,
            "Fax": fax,
            "Website": website,
            "Email": email,
            "RegulationType": "Regulated",
            "RegCtry": "MZ",
            "RegCode": "BMO",
            "ListCode": current_listnr,
            "ListLanguage": "PT",
            "ListValidityDate": validity_date,
            "ListName": list_name,
            "ListProcessDate": process_date,
        })
        rows_by_list[current_listnr].append(r)

    # emit in Jira ListNr order 1..9
    rows = []
    counts = {}
    for nr in sorted(LISTNR_INFO):
        rows.extend(rows_by_list[nr])
        counts[nr] = len(rows_by_list[nr])
    return rows, counts


rows, counts = scrape()

df = pd.DataFrame(rows)
df = df.reindex(columns=COLUMNS, fill_value="")     # enforce exact fixed schema
df = df[df["Name"] != ""]

now = datetime.datetime.now()
filename = "{} SQL Ready {}.xlsx".format(regulatorName, str(now).replace(":", ".")[:-7])
outfile = os.path.join(scriptfolder, filename)
df.to_excel(outfile, sheet_name="SQL Ready", index=False)

print("\n==== SUMMARY ====")
print("Total rows:", len(df))
print("By ListCode:")
for nr in sorted(LISTNR_INFO):
    print(f"  List {nr} ({LISTNR_INFO[nr][0]}): {counts.get(nr, 0)}")
print("Columns:", len(df.columns))
print('Saved {} rows to {}'.format(len(df), outfile))
