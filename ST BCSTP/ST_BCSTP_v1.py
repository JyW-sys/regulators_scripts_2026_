# -*- coding: utf-8 -*-
# ------------------------------------------------------------------
# ST BCSTP  -  Banco Central de São Tomé e Príncipe
# Source: https://www.bcstp.st
# Jira:   DECD-5814  (epic DECD-3438, Regulators 2026 - Internal Crawlers)
#
# Six lists (from the Jira description):
#   1  Bancos Comerciais (Commercial Banks)           cod=BAN   ListLabel 1
#   2  Empresas de Seguro (Insurance Companies)        cod=SEG   ListLabel 2
#   3  Casas de Câmbio (Exchange Houses)               cod=CAM   ListLabel 4
#   4  Instituições de Microfinanças (Microfinance)    cod=MIC   ListLabel 4  (NEW)
#   5  Prestadores de Serviços de Pagamento (PSPs)     cod=PSP   ListLabel 4  (NEW)
#   6  Operadores de Sistema de Pagamento (PSOs)       cod=OSP   ListLabel 4  (NEW)
#
# How the site works (no Selenium needed):
#   * Each list page (Instituicoes-Financeiras-Detalhes?cod=XXX for lists 1-3,
#     Instituicoes_financeiras_mais.aspx?cod=XXX for lists 4-6) renders a
#     <select id="Inst_select"> whose <option> value is the entity id and whose
#     option TEXT is the entity name (option value 0 = "Selecionar" placeholder).
#   * Picking an entity fires inst_selection(), a POST to
#     I_Function.aspx/inst_selected with JSON {"value": "<id>"}; the JSON reply's
#     .d field is an HTML fragment with the entity's licence date, activity type
#     and a contacts table (Local | CP Nº | Endereço | Telefone | Fax | E-Mail).
#   * Both page templates share the same Inst_select control and the same
#     inst_selected endpoint, so one code path handles all six lists.
#
# ListLabel rule (per project convention): 1 = bank, 2 = insurance,
#   3 = bank & insurance, 4 = other. Banks(1)=1, Insurance(2)=2, the rest=4.
# All entities are currently-licensed -> RegulationType = "Regulated".
# ------------------------------------------------------------------
import os
import re
import json
import time
import datetime
import requests
import urllib3
from bs4 import BeautifulSoup
import pandas as pd

urllib3.disable_warnings()

regulatorName = "ST BCSTP"
print(f"Running {regulatorName} Web Scraping Tool v.1.0")

scriptfolder = os.path.dirname(os.path.abspath(__file__))
tempfolder = os.path.join(scriptfolder, "tempfolder")
os.makedirs(tempfolder, exist_ok=True)

BASE = "https://www.bcstp.st"
DETAIL_URL = BASE + "/I_Function.aspx/inst_selected"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RegulatorBot/1.0"}

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

PROCESS_DATE = datetime.datetime.now().strftime('%Y-%m-%d')

# The six lists, in Jira ListNr order: (ListCode, cod, page template, ListLabel, EN name)
LISTS = [
    (1, "BAN", "Instituicoes-Financeiras-Detalhes",     1, "Commercial Banks"),
    (2, "SEG", "Instituicoes-Financeiras-Detalhes",     2, "Insurance Companies"),
    (3, "CAM", "Instituicoes-Financeiras-Detalhes",     4, "Exchange Houses"),
    (4, "MIC", "Instituicoes_financeiras_mais.aspx",    4, "Microfinance Institutions"),
    (5, "PSP", "Instituicoes_financeiras_mais.aspx",    4, "Payment Service Providers"),
    (6, "OSP", "Instituicoes_financeiras_mais.aspx",    4, "Payment System Operators"),
]

# Portuguese "Tipo de Actividade" -> English CoType. Falls back to the original
# Portuguese string for any value not listed here.
ACTIVITY_EN = {
    "banco comercial": "Commercial Bank",
    "banco comercial e de investimento": "Commercial and Investment Bank",
    "ramos gerais & vida": "Non-life and Life Insurance",
    "ramos gerais": "Non-life Insurance",
    "casa de câmbio": "Exchange House",
    "venda e compra de divisas": "Foreign Exchange Trading",
    "microfinanças": "Microfinance",
    "instituição de pagamento e emissor de moeda eletrónica":
        "Payment Institution and E-Money Issuer",
    "instituição de pagamentos de envio e recepção de fundos":
        "Payment Institution (Funds Transfer)",
    "operador de sistema de pagamento": "Payment System Operator",
}

EMAIL_RE = re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')


def blank_row():
    return {c: '' for c in COLUMNS}


def clean(v):
    """Trim and treat the site's '.'/'-' placeholders as empty."""
    v = re.sub(r'\s+', ' ', (v or '')).strip()
    return '' if v in ('.', '-', '') else v


def translate_activity(pt):
    return ACTIVITY_EN.get((pt or '').strip().lower(), pt.strip())


def to_iso_date(dmy):
    """'27/05/2003' -> '2003-05-27'; return '' if unparseable."""
    m = re.match(r'\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*$', dmy or '')
    if not m:
        return ''
    d, mo, y = m.groups()
    return f"{y}-{int(mo):02d}-{int(d):02d}"


def clean_phone(v):
    """Drop a leading 'Tel:' label and trailing separators; keep digits/()+/- ."""
    v = re.sub(r'(?i)\btel\.?\s*:?', '', v or '')
    v = v.strip(' .,-–')
    return re.sub(r'\s+', ' ', v).strip()


def get_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    s.verify = False
    return s


def fetch(sess, method, url, retries=3, **kw):
    for i in range(retries):
        try:
            r = sess.request(method, url, timeout=60, **kw)
            r.raise_for_status()
            r.encoding = "utf-8"
            return r
        except Exception as e:
            print(f"   retry {i+1}/{retries} for {url} ({method}): {e}")
            time.sleep(2)
    raise RuntimeError(f"Failed to fetch {url}")


def list_entities(sess, page, cod):
    """Return [(entity_id, name), ...] from a list page's Inst_select control,
    skipping the value-0 'Selecionar' placeholder."""
    r = fetch(sess, "GET", f"{BASE}/{page}?cod={cod}")
    soup = BeautifulSoup(r.text, "html.parser")
    sel = soup.find("select", id="Inst_select")
    if not sel:
        return []
    out = []
    for o in sel.find_all("option"):
        val = (o.get("value") or "").strip()
        name = o.get_text(" ", strip=True)
        if val and val != "0" and name:
            out.append((val, name))
    return out


def entity_detail(sess, entity_id):
    """POST the inst_selected endpoint and parse the returned HTML fragment into
    {activity, licence_date, local, cp, endereco, telefone, fax, email}."""
    r = fetch(sess, "POST", DETAIL_URL,
              data=json.dumps({"value": str(entity_id)}),
              headers={**HEADERS, "Content-Type": "application/json; charset=utf-8",
                       "X-Requested-With": "XMLHttpRequest"})
    html = r.json().get("d", "") or ""
    soup = BeautifulSoup(html, "html.parser")

    # label|value rows (Data de Licença, Tipo de Actividade, ...)
    kv = {}
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) == 2:
            kv[tds[0].get_text(" ", strip=True)] = tds[1].get_text(" ", strip=True)

    # contacts table: header row containing 'Endereço' followed by the data row.
    # Take the head-office ("Sede") row; fall back to the first data row.
    contact = {}
    trs = soup.find_all("tr")
    for idx, tr in enumerate(trs):
        heads = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if "Endereço" in heads:
            for drow in trs[idx + 1:]:
                vals = [td.get_text(" ", strip=True) for td in drow.find_all("td")]
                if len(vals) == len(heads):
                    row = dict(zip(heads, vals))
                    if not contact:
                        contact = row
                    if re.search(r'sede', row.get("Local", ""), re.I):
                        contact = row
                        break
            break

    return {
        "activity": kv.get("Tipo de Actividade", ""),
        "licence_date": kv.get("Data de Licença", ""),
        "local": contact.get("Local", ""),
        "cp": contact.get("CP Nº", ""),
        "endereco": contact.get("Endereço", ""),
        "telefone": contact.get("Telefone", ""),
        "fax": contact.get("Fax", ""),
        "email": contact.get("E-Mail", ""),
    }


def scrape_list(sess, list_code, cod, page, list_label, list_name):
    ents = list_entities(sess, page, cod)
    print(f"[List {list_code}] {list_name} ({cod}) -> {len(ents)} entities")
    out = []
    for entity_id, name in ents:
        d = entity_detail(sess, entity_id)

        cp = clean(d["cp"])
        addr2 = f"CP {cp}" if cp else ""          # Caixa Postal (postal box)

        # the E-Mail cell sometimes actually holds a website (no '@')
        raw_mail = clean(d["email"])
        email, website = "", ""
        if raw_mail:
            m = EMAIL_RE.search(raw_mail)
            if m:
                email = m.group(0)
            elif re.search(r'(www\.|https?://|\.\w{2,3}$)', raw_mail, re.I):
                website = raw_mail

        r = blank_row()
        r.update({
            "ListLabel": list_label,
            "Name": name,
            "CoType": translate_activity(d["activity"]),
            "Address_1": clean(d["endereco"]),
            "Address_2": addr2,
            "City": "São Tomé",
            "Cntry": "ST",
            "Phone": clean_phone(d["telefone"]),
            "Fax": clean(d["fax"]),
            "Website": website,
            "Email": email,
            "RegulationDate": to_iso_date(d["licence_date"]),
            "ListCode": list_code,
            "ListName": list_name,
        })
        out.append(r)
    return out


# ==================================================================
# RUN
# ==================================================================
sess = get_session()
all_rows = []
for list_code, cod, page, list_label, list_name in LISTS:
    all_rows += scrape_list(sess, list_code, cod, page, list_label, list_name)

# common fields
for r in all_rows:
    r["RegCtry"] = "ST"
    r["RegCode"] = "BCSTP"
    r["RegulationType"] = "Regulated"
    r["ListLanguage"] = "PT"
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
    sub = df[df['ListCode'] == code]
    print(f"  List {code}: {len(sub)}  ({sub['ListName'].iloc[0]})")
print("Output:", outfile)

# tempfolder is unused by this scraper; clear anything left behind
for rem in os.listdir(tempfolder):
    os.remove(os.path.join(tempfolder, rem))
