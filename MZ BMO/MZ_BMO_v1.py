# -*- coding: utf-8 -*-
# ------------------------------------------------------------------
# MZ BMO  -  Banco de Mocambique (Bank of Mozambique)
# Source page: https://www.bancomoc.mz/en/areas-of-expertise/licensing/licensing-of-institutions/
# Jira:   DECD-6332  (epic DECD-3438, Regulators 2026 - Crawlers)
#
# Plain `requests` (desktop UA, verify=False) works directly on this site --
# no Cloudflare/WAF challenge was encountered, so DrissionPage is not needed.
#
# Per the Jira Comments field for ListNr 1 ("Download the most recent Excel
# file from the 'List of authorised institutions' and extract the entities
# from each list under the listName category"): the page's "List of
# authorised institutions" section links several dated .xls downloads; the
# scraper picks the most recently published one (currently
# "Relacao das ICSF em Funcionamento - Janeiro 2025", published 14-04-2025)
# and mines ALL 9 Jira lists out of its single "Relacao ICSF" sheet -- the
# 9 ListNr categories are exactly the top-level section headers in that
# sheet (Bancos, Microbancos, Cooperativas de Credito, ..., Casas de Cambio).
#
# Sheet layout (header row: Nr | Sigla | Nome da Instituicao | Sede | Actividades):
#   - A "header" row is any row whose "Nome da Instituicao" cell is empty.
#     Its label sits in whichever of the Nr/Sigla columns is non-empty.
#   - Top-level category headers (e.g. "Bancos") start a new ListNr/ListName.
#   - "Categoria de ..." headers (only under the payments section) start a
#     payment sub-type used for CoType.
#   - "Cidade de X" / "Provincia de X" headers set the City for entities
#     until the next header (used for Cooperativas/Investimento/Cartoes/Cambio,
#     which have no address-line phone/fax label to infer a city from).
#   - A data row has Nr (int), Sigla (optional abbreviation), Nome da
#     Instituicao (entity name), Sede (one free-text blob mixing address /
#     phone / fax / e-mail-or-website), and (Bancos only) Actividades -- a
#     multi-paragraph legal boilerplate identical for every bank, not mapped
#     to any output field.
#
# Translation (Portuguese source; see README "Translation approach"):
#   Name        -> English translation (descriptive institution-type words
#                  translated via a phrase dictionary; brand/proper-noun
#                  parts of the name are left as-is)
#   Name - Mother Company -> the original Portuguese name, verbatim
#   Address_1   -> kept in Portuguese (street/avenue addresses are not
#                  meaningfully translatable; this is also the form the
#                  address would need for postal use in Mozambique)
#   ListLanguage -> 'PT' (matches ST BCSTP, the other Portuguese-language
#                  regulator in this batch)
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
print(f"Running {regulatorName} Web Scraping Tool v.1.0")

# ------ workspace path -------------------------------------------------
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))
except NameError:
    scriptfolder = os.getcwd()
os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, "tempfolder")
os.makedirs(tempfolder, exist_ok=True)

PAGE_URL = "https://www.bancomoc.mz/en/areas-of-expertise/licensing/licensing-of-institutions/"
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
# STEP 1 - find and download the most recent "List of authorised institutions" .xls
# ==================================================================
def find_latest_xls_url():
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
    # The download blocks are the sibling <div class="download"> elements that
    # follow the heading (in document order) until the next <h3>.
    candidates = []
    for el in h3.find_all_next():
        if el.name == "h3":
            break
        if el.name == "a" and el.get("href", "").lower().endswith((".xls", ".xlsx")):
            date_p = el.find("p", class_="download__date")
            date_txt = date_p.get_text(strip=True) if date_p else ""
            href = el["href"]
            if href.startswith("/"):
                href = "https://www.bancomoc.mz" + href
            candidates.append((date_txt, href))
    if not candidates:
        raise RuntimeError("No .xls/.xlsx download links found under 'List of authorised institutions'")

    def parse_date(d):
        try:
            return datetime.datetime.strptime(d, "%d-%m-%Y")
        except Exception:
            return datetime.datetime.min

    candidates.sort(key=lambda t: parse_date(t[0]), reverse=True)
    return candidates[0][1]


def download_xls(url):
    fname = "MZ_BMO_licensed_institutions.xls"
    dest = os.path.join(tempfolder, fname)
    r = requests.get(url, headers={**HEADERS, "Referer": PAGE_URL}, verify=False, timeout=60)
    r.raise_for_status()
    with open(dest, "wb") as fh:
        fh.write(r.content)
    return dest


# ==================================================================
# STEP 2 - translation helpers (Portuguese -> English)
# ==================================================================
# Longest/most-specific phrases first; word-boundary, case-insensitive.
NAME_PHRASES = [
    ("Banco Internacional de", "International Bank of"),
    ("Banco Comercial e de Investimentos", "Commercial and Investment Bank"),
    ("Banco Nacional de Investimento", "National Investment Bank"),
    (r"Banco Societé Generale", "Société Générale Bank"),
    ("Banco BIG", "BIG Bank"),
    ("Banco Letshego", "Letshego Bank"),
    ("Banco", "Bank"),
    ("Microbanco de Apoio aos Investimentos", "Investment Support Microbank"),
    ("Microbanco", "Microbank"),
    ("Cooperativa de Poupança e Crédito", "Savings and Credit Cooperative"),
    ("Cooperativa de Crédito dos Micro-empresários de", "Micro-entrepreneurs Credit Cooperative of"),
    ("Cooperativa de Crédito das Mulheres de", "Women's Credit Cooperative of"),
    ("Cooperativa [Dd]e Crédito", "Credit Cooperative"),
    ("Caixa de Poupança Postal de", "Postal Savings Fund of"),
    ("Caixa das Mulheres de", "Women's Fund of"),
    ("Caixa Mulher", "Women's Fund"),
    ("Caixa Financeira de", "Finance Fund of"),
    ("Sociedade Financeira de Corretagem", "Brokerage Finance Company"),
    ("Sociedade Corretora", "Brokerage Company"),
    ("Sociedade de Investimento", "Investment Company"),
    ("Sociedade Interbancária de", "Interbank Company of"),
    ("Tecnologias e Serviços de Pagamentos", "Payment Technologies and Services"),
    ("Casas? de Câmbios?", "Exchange House"),
    ("Carteira Móvel", "Mobile Wallet"),
    ("Mundo de Câmbios", "World Exchange"),
    ("Mundial Câmbios", "Worldwide Exchange"),
    ("Multicâmbios", "Multi-Exchange"),
    ("Cota Câmbios", "Cota Exchange"),
    ("Nova Cambios", "New Exchange"),
    ("Finanças", "Finance"),
    (r"Mcb", "Microbank"),
    ("Moçambique", "Mozambique"),
]

# Known source-file typos in brand names that are safe/well-known enough to
# correct in the English Name column (kept unmodified in the PT mother-company
# column). See README "Translation approach" for the judgment call.
NAME_FIXUPS = {
    "Acess Bank Mozambique, SA": "Access Bank Mozambique, SA",
}


def clean_name(s):
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+,", ",", s)
    s = re.sub(r",(?=\S)", ", ", s)   # ensure a space after commas
    return s.strip()


def translate_name(pt_name):
    name = clean_name(pt_name)
    en = name
    for pt, enw in NAME_PHRASES:
        en = re.sub(r"\b" + pt + r"\b", enw, en, flags=re.IGNORECASE)
    en = re.sub(r"\bLda\b\.?", "Ltd", en)
    en = re.sub(r"\s+", " ", en).strip()
    en = NAME_FIXUPS.get(en, en)
    return en


# ==================================================================
# STEP 3 - top-level category (ListNr) + payment sub-type + city-header maps
# ==================================================================
# Portuguese header text (as it appears in the sheet) -> ListNr
CATEGORY_MAP = {
    "Bancos": 1,
    "Microbancos": 2,
    "Empresas Prestadoras de Serviços de Pagamentos": 6,
    "Cooperativas de Crédito": 3,
    "Sociedades Emitentes ou Gestoras de Cartões de Crédito": 8,
    "Sociedades de Investimento": 5,
    "Sociedades Finaceiras de Corretagem": 7,
    "Sociedades corretoras": 4,
    "Casas de Câmbio": 9,
}
# reverse map: ListNr -> original Portuguese header label (for License_Type)
PT_LABEL_BY_LISTNR = {v: k for k, v in CATEGORY_MAP.items()}
# ListNr -> ListLabel (1=bank, 2=insurance, 3=bank&insurance, 4=other)
LISTLABEL_BY_LISTNR = {1: 1, 2: 1, 3: 1, 4: 4, 5: 4, 6: 4, 7: 4, 8: 4, 9: 4}

# ListNr -> (Jira ListName verbatim, English CoType default)
LISTNR_INFO = {
    1: ("Bancos", "Bank"),
    2: ("Microbancos", "Microbank"),
    3: ("Cooperativas de Crédito", "Credit Cooperative"),
    4: ("Sociedades corretoras", "Brokerage Company"),
    5: ("Sociedades de Investimento", "Investment Company"),
    6: ("Empresas Prestadoras de Serviços de Pagamentos", None),  # CoType from payment sub-category
    7: ("Sociedades Finaceiras de Corretagem", "Brokerage Finance Company"),
    8: ("Sociedades Emitentes ou Gestoras de Cartoes de Credito", "Credit Card Issuer/Manager"),
    9: ("Casas de Câmbio", "Foreign Exchange Bureau"),
}

PAYMENT_SUBCAT_EN = {
    "categoria de instituições de moeda electrónica": "Electronic Money Institution",
    "categoria de agregadores de pagamentos": "Payment Aggregator",
    "categoria de instituições de transferência de fundos": "Money Transfer Institution",
}

CITY_HEADER_RE = re.compile(r"^(Cidade|Prov[ií]ncia)\s+de\s+(.+)$", re.IGNORECASE)
CITY_TYPO_FIX = {"cabo delegado": "Cabo Delgado"}

# ==================================================================
# STEP 4 - "Sede" free-text blob -> Address_1 / City / Phone / Fax / Email / Website
# ==================================================================
GAZETTEER = ["Maputo", "Matola", "Beira", "Chimoio", "Pemba", "Nacala",
             "Angónia", "Caia", "Nampula", "Lichinga", "Morrumbene",
             "Xai-Xai", "Quelimane", "Tete", "Sofala", "Manica",
             "Cabo Delgado"]
GAZETTEER_RE = re.compile(r"\b(" + "|".join(re.escape(c) for c in GAZETTEER) + r")\b", re.IGNORECASE)
# An explicit "Cidade de X" / "Vila de X" / "Distrito de X" / "Provincia de/do X"
# marker inside the entity's own address text is a stronger signal than a bare
# gazetteer word match: a bare search can be fooled by a place-name-like word
# that is actually part of a business name (e.g. "Manica Shopping Center" in an
# address whose real city, named later via "Cidade de Chimoio", is Chimoio).
# So we try the marker-qualified match first and only fall back to a bare
# search if no such marker is present.
INLINE_MARKER_CITY_RE = re.compile(
    r"(?:Cidade|Vila|Distrito|Prov[ií]ncia)\s+d[aeo]\s+(" + "|".join(re.escape(c) for c in GAZETTEER) + r")",
    re.IGNORECASE,
)

TELFAX_NORMALIZE_RE = re.compile(r"(?:Tel(?:efone)?|Telef|Telf)\.?\s*/\s*Fax\.?:?", re.IGNORECASE)
LABEL_RE = re.compile(r"(TELFAX|Telefones?|Telef|Telf|Tel|Celular|Cel|Fax)\.?:?", re.IGNORECASE)
MAIL_RE = re.compile(r"E[\s\-]*mail\.?:?\s*", re.IGNORECASE)
TRAILING_DIGITS_RE = re.compile(r"(\d[\d/;\-\s]{5,}\d)\s*$")


def parse_sede(raw):
    """Split the 'Sede' blob into (address, city_guess, phone, fax, email, website)."""
    text = raw or ""
    text = TELFAX_NORMALIZE_RE.sub("TELFAX:", text)
    text = text.replace("–", "-").replace("—", "-")   # normalize en/em-dash

    city_guess = ""
    m_city = INLINE_MARKER_CITY_RE.search(raw or "") or GAZETTEER_RE.search(raw or "")
    if m_city:
        key = m_city.group(1).lower()
        city_guess = CITY_TYPO_FIX.get(key, m_city.group(1).title() if "-" not in m_city.group(1) else m_city.group(1))
        if key == "cabo delgado":
            city_guess = "Cabo Delgado"

    # e-mail / website (independent pass on the original text)
    email, website = "", ""
    m_mail = MAIL_RE.search(text)
    if m_mail:
        rest = text[m_mail.end():]
        cut = rest.find(",")
        val = (rest if cut == -1 else rest[:cut]).strip(" ;:.-")
        if "@" in val:
            email = val
        else:
            website = val

    matches = list(LABEL_RE.finditer(text))
    if not matches:
        address = text.strip(" ,;-")
        phone = ""
        m_tail = TRAILING_DIGITS_RE.search(address)
        if m_tail:
            phone = m_tail.group(1).strip()
            address = address[:m_tail.start()].strip(" ,;-")
        return address, city_guess, phone, "", email, website

    address = text[:matches[0].start()].strip(" ,;-")
    phone_parts, fax_parts = [], []
    for i, m in enumerate(matches):
        label = m.group(1).upper()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        comma_idx = text.find(",", start, end)
        if comma_idx != -1:
            end = comma_idx
        value = text[start:end].strip(" ;,:.-/")
        if not value:
            continue
        if label == "TELFAX":
            phone_parts.append(value)
            fax_parts.append(value)
        elif label == "FAX":
            fax_parts.append(value)
        else:  # TEL / TELF / TELEF / TELEFONE(S) / CEL / CELULAR
            phone_parts.append(value)

    phone = "; ".join(dict.fromkeys(p for p in phone_parts if p))
    fax = "; ".join(dict.fromkeys(p for p in fax_parts if p))
    return address, city_guess, phone, fax, email, website


# ==================================================================
# STEP 5 - walk the sheet and build rows
# ==================================================================
def scrape():
    xls_url = find_latest_xls_url()
    print(f"[MZ BMO] latest 'List of authorised institutions' file: {xls_url}")
    xls_path = download_xls(xls_url)
    print(f"[MZ BMO] downloaded to {xls_path}")

    df_raw = pd.read_excel(xls_path, sheet_name="Relação ICSF", header=None)

    process_date = datetime.date.today().isoformat()
    rows = []

    current_listnr = None
    current_payment_cotype = None
    current_city = ""
    counts = {}

    for i in range(len(df_raw)):
        nr_col = df_raw.iat[i, 1] if df_raw.shape[1] > 1 else None
        sigla_col = df_raw.iat[i, 2] if df_raw.shape[1] > 2 else None
        name_col = df_raw.iat[i, 3] if df_raw.shape[1] > 3 else None
        sede_col = df_raw.iat[i, 4] if df_raw.shape[1] > 4 else None

        name_val = name_col if pd.notna(name_col) else None

        if name_val is None:
            # header / separator row - label sits in nr_col or sigla_col
            label = None
            if pd.notna(nr_col) and isinstance(nr_col, str):
                label = nr_col.strip()
            elif pd.notna(sigla_col) and isinstance(sigla_col, str):
                label = sigla_col.strip()
            if not label:
                continue  # blank spacer row

            if label in CATEGORY_MAP:
                current_listnr = CATEGORY_MAP[label]
                current_payment_cotype = None
                current_city = ""
                continue

            if label.lower().startswith("categoria de"):
                key = label.rstrip(" ;").lower()
                current_payment_cotype = PAYMENT_SUBCAT_EN.get(key, label)
                current_city = ""
                continue

            m_city = CITY_HEADER_RE.match(label)
            if m_city:
                raw_city = m_city.group(2).strip()
                current_city = CITY_TYPO_FIX.get(raw_city.lower(), raw_city)
                continue

            # unrecognized header text - ignore (defensive; shouldn't happen)
            continue

        # ---- data row -------------------------------------------------
        if current_listnr is None:
            continue  # entity found before any recognized category header (shouldn't happen)

        pt_name = clean_name(str(name_val))
        if not pt_name:
            continue

        en_name = translate_name(pt_name)
        sigla = clean_name(str(sigla_col)) if pd.notna(sigla_col) else ""

        address, city_guess, phone, fax, email, website = parse_sede(str(sede_col) if pd.notna(sede_col) else "")
        # Prefer a city/town name actually found in the entity's own address
        # text (more granular, e.g. "Pemba"/"Beira"/"Chimoio") over the
        # section's city/province grouping header (coarser, e.g. "Cabo
        # Delgado"/"Sofala"/"Manica" province), falling back to the header
        # only when the address text names no specific place.
        city = city_guess or current_city

        list_name, default_cotype = LISTNR_INFO[current_listnr]
        cotype = current_payment_cotype if current_listnr == 6 else default_cotype

        pt_category_label = PT_LABEL_BY_LISTNR.get(current_listnr, "")
        license_type = pt_category_label
        if current_listnr == 6 and current_payment_cotype:
            license_type = f"{pt_category_label} – {current_payment_cotype}"

        r = blank_row()
        r.update({
            "ListLabel": LISTLABEL_BY_LISTNR.get(current_listnr, 4),
            "Name": en_name,
            "Name - Mother Company": pt_name,
            "InternalID_1": sigla,
            "InternalID_1_type": "Sigla" if sigla else "",
            "CoType": cotype or "",
            "License_Type": license_type,
            "Address_1": address,
            "City": city,
            "Cntry": "MZ",
            "Phone": phone,
            "Fax": fax,
            "Email": email,
            "Website": website,
            "RegulationType": "Regulated",
            "RegCtry": "MZ",
            "RegCode": "BMO",
            "ListCode": current_listnr,
            "ListName": list_name,
            "ListLanguage": "PT",
            "ListValidityDate": "2025-01-01",
            "ListProcessDate": process_date,
        })
        rows.append(r)
        counts[current_listnr] = counts.get(current_listnr, 0) + 1

    return rows, counts


rows, counts = scrape()

df = pd.DataFrame(rows)
df = df.reindex(columns=COLUMNS, fill_value="")     # enforce exact fixed schema
df = df[df["Name"] != ""]

now = datetime.datetime.now()
outfile = os.path.join(
    scriptfolder,
    "{} SQL Ready {}.xlsx".format(regulatorName, str(now).replace(":", ".")[:-7]),
)
df.to_excel(outfile, sheet_name="SQL Ready", index=False)

print("\n==== SUMMARY ====")
print("Total rows:", len(df))
print("By ListCode:")
for nr in sorted(LISTNR_INFO):
    print(f"  List {nr} ({LISTNR_INFO[nr][0]}): {counts.get(nr, 0)}")
print("Columns:", len(df.columns))
print("Output:", outfile)
