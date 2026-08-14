# -*- coding: utf-8 -*-
# ------------------------------------------------------------------
# EG FRAEG - Financial Regulatory Authority, Egypt
# Source: https://fra.gov.eg/
# Jira:   DECD-6365  (epic DECD-3438, Regulators 2026 - Crawlers)
#
# Lists (from the Jira description, DECD-6365):
#   ListNr 1  Egyptian Insurance Companies
#             https://fra.gov.eg/en/<insurance registers>/?taxonomy_filter=
#             company_records_1_1_3_3&filtered_type=insurance-and-reinsurance-companies
#             -> paginated HTML grid (3 pages, 20/20/7 = 47 rows). Jira asks for
#                the company name (grid column 2) and the address (grid column 4),
#                TRANSLATED from Arabic to English into `Name`, with the Arabic
#                originals copied to the Mother Company columns.
#                Each grid row links to a /company_records/ detail page which also
#                publishes the registration number, licence number + licence date,
#                phone, fax, website, e-mail and the licensed activity - those are
#                harvested too and mapped onto the matching SQL-Ready columns.
#   ListNr 2  Foreign Reinsurance Brokers  (NEW LIST)
#             FRA-Foreign-Reinsurance-Brokers-Non-Resident-List-June-2026-1.pdf
#             -> single-page text PDF, 30 rows, 7 columns.
#   ListNr 3  FRA Reinsurance Companies  (NEW LIST)
#             FRA-Reinsurance-companies-Its-Branches-List-June-2026-1.pdf
#             -> 10-page text PDF holding TWO numbered tables:
#                  p1-p8  "FRA Reinsurance Companies List 2026"  serials 1-151
#                  p9-p10 "FRA Reinsurers' Branches List 2026"   serials 1-44
#                Both are extracted under ListCode 3 (the Jira row points at the
#                one file); the branch table rows carry EntryType = 'Branch'.
#
# Extraction notes
# ----------------
# * ListNr 1 is Arabic. Company names come from a curated Arabic->English map
#   (NAME_EN_OVERRIDE) so brand spellings are correct - machine translation gets
#   e.g. MAPFRE, SACE, Orope and KAF wrong. Where FRA itself publishes an English
#   name (field "اسم الشركة بالانجليزية", 8 records) that value wins over
#   everything else. Anything not covered falls back to Google MT, so a company
#   added to the register after this build still produces an English `Name`.
#   Addresses are machine-translated (Google) and cached in
#   tempfolder/translation_cache.json so re-runs are byte-stable. Ship that cache
#   with the script: when it is complete the provider is never imported at all,
#   so the run works offline and on a machine with no translation library.
#
# v2 (control-server fixes)
# -------------------------
# * Translation provider switched from deep_translator to googletrans, which is
#   what every other translating scraper in this project uses (YE CBYE, SD CBOS,
#   LB BLI, CN CSRC) and is already present on the control server. Both the 3.x
#   synchronous and the 4.x asyncio APIs are supported, detected at run time -
#   the version string is unreliable (the 4.0.2 distribution reports 3.4.0).
#   deep_translator is kept as a fallback provider.
# * stdout is forced to UTF-8. On a cp1252 Windows console the old translation
#   warning printed the Arabic source and raised UnicodeEncodeError from inside
#   the exception handler, killing the whole run instead of degrading to the
#   Arabic original as designed. That print no longer echoes source text.
# * The FRA register itself lists Misr Insurance, Misr Life Insurance, Suez Canal
#   Insurance and Mohandes Insurance TWICE (rows 6-9 Arabic record, rows 44-47
#   English record). Both are kept: the output row count must match the source.
# * ListNr 3 is parsed from word coordinates, not from extract_table(): the
#   COUNTRY cell is a merged cell spanning a whole country group, so the group
#   boundaries are taken from the full-width horizontal rules and the country /
#   country-rating is broadcast to every reinsurer inside the group. Serial
#   continuity (1..151 and 1..44, no gaps, no duplicates) is asserted at the end.
# * ListNr 3 carries two footnotes naming further entities allowed to write
#   reinsurance business in Egypt (Lloyd's, Arab War Risks Insurance Syndicate
#   (AWRIS), Assuranceforeningen Skuld (Gjensidig), Gard Marine & Energy
#   Insurance (Europe) AS, NorthStandard Limited). They sit outside the numbered
#   table and are NOT emitted as rows - see README_EG_FRAEG.md.
# * fra.gov.eg blocked plain requests before 2026-08-06; it answers 200 with a
#   desktop User-Agent from the current network. No DrissionPage needed.
# ------------------------------------------------------------------
import io
import os
import re
import sys
import json
import time
import asyncio
import inspect
import datetime
import unicodedata

import requests
import pandas as pd
import pdfplumber
from bs4 import BeautifulSoup

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Windows consoles default to cp1252, which cannot encode Arabic. Without this,
# any print() carrying source text - including the translation warning below -
# raises UnicodeEncodeError and kills the run.
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

regulatorName = "EG FRAEG"
print("Running {} Web Scraping Tool v.2.0".format(regulatorName))

# ------ At first we will define the workspace path -----
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))   # production (.py)
except NameError:
    scriptfolder = os.getcwd()                                   # notebook
os.chdir(scriptfolder)
tempfolder = os.path.join(scriptfolder, "tempfolder")
os.makedirs(tempfolder, exist_ok=True)

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
}

L1_BASE = ("https://fra.gov.eg/en/%D8%B3%D8%AC%D9%84%D8%A7%D8%AA-%D9%81%D9%8A-"
           "%D9%85%D8%AC%D8%A7%D9%84-%D8%A7%D9%84%D8%AA%D8%A3%D9%85%D9%8A%D9%86/")
L1_QUERY = ("?taxonomy_filter=company_records_1_1_3_3"
            "&filtered_type=insurance-and-reinsurance-companies")

regdict = {
    1: {"ListName": "Egyptian Insurance Companies",
        "URL": L1_BASE + L1_QUERY,
        "Comments": ("Extract the entities from the table (Company name in column 2 and "
                     "address in column 4), translate from Arabic to English and add to "
                     "the column Name in our template Excel file. The Arabic versions can "
                     "be copied to the Mother Company columns.")},
    2: {"ListName": "Foreign Reinsurance Brokers",
        "URL": ("https://fra.gov.eg/wp-content/uploads/2026/06/"
                "FRA-Foreign-Reinsurance-Brokers-Non-Resident-List-June-2026-1.pdf"),
        "Comments": "NEW LIST! Extract the entities from the pdf."},
    3: {"ListName": "FRA Reinsurance Companies",
        "URL": ("https://fra.gov.eg/wp-content/uploads/2026/06/"
                "FRA-Reinsurance-companies-Its-Branches-List-June-2026-1.pdf"),
        "Comments": "NEW LIST! Extract the entities from the pdf."},
}

# ListLabel - 1 bank, 2 insurance, 3 bank & insurance, 4 everything else.
# All three FRA lists are insurance / reinsurance registers.
LIST_LABEL = {1: 2, 2: 2, 3: 2}

# Row counts verified against the live sources on 2026-08-06.
# ListNr 3 = 151 reinsurance companies + 44 reinsurers' branches.
EXPECTED = {1: 47, 2: 30, 3: 195}

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

now = datetime.datetime.now()
PROCESS_DATE = now.strftime('%Y-%m-%d')
REG_CTRY, REG_CODE = regulatorName.split(" ", 1)      # 'EG', 'FRAEG'

# Both PDFs are stamped "Update 24 June 2026" on their last page.
PDF_VALIDITY = "2026-06-24"

SESSION = requests.Session()
SESSION.headers.update(HEADERS)
SESSION.verify = False


# ==================================================================
# Arabic helpers + translation
# ==================================================================
ARABIC_RE = re.compile(r'[؀-ۿݐ-ݿ]')
# tatweel, Arabic diacritics, and the bidi/format marks fra.gov.eg leaks into
# some of its fields (LRM/RLM/ZWJ) - all stripped before a dictionary lookup.
_STRIP_CHARS = re.compile(r'[ـً-ْ​-‏‪-‮﻿]')


def has_arabic(text):
    return bool(ARABIC_RE.search(text or ""))


def clean_text(text):
    """Normalise a raw field: NFKC, drop bidi/diacritic noise, collapse spaces."""
    if text is None:
        return ""
    t = unicodedata.normalize("NFKC", str(text))
    t = _STRIP_CHARS.sub("", t)
    t = t.replace("\r", " ").replace("\n", " ")
    return re.sub(r'\s+', ' ', t).strip()


def norm_ar(text):
    """Lookup key for NAME_EN_OVERRIDE - unifies the alef / ya / ta-marbuta
    spelling variants FRA mixes between the grid and the detail pages."""
    t = clean_text(text)
    t = re.sub(r'[آأإٱ]', 'ا', t)   # آ أ إ ٱ -> ا
    t = t.replace('ى', 'ي')                        # ى -> ي
    t = t.replace('ة', 'ه')                        # ة -> ه
    return t


# Curated Arabic -> English company names for ListNr 1. Machine translation is
# only used for entries that are not in this map (i.e. companies FRA adds later).
NAME_EN_OVERRIDE = {
    'مكتب تمثيل شركة مارش ميدل ايست ليمتد':
        'Marsh Middle East Limited Representative Office',
    'مكتب تمثيل شركة فريمير لخدمات التامين واعادة التامين':
        'Fremier Insurance and Reinsurance Services Representative Office',
    'مكتب مابفرى اسيستنثيا كومبانيا انترناثيونال':
        'MAPFRE Asistencia Compania Internacional Representative Office',
    'مكتب تمثيل شركة اتلانتيك رى Atlantic Re':
        'Atlantic Re Representative Office',
    'مكتب تمثيل شركة ساتشى اس بى ايه لخدمات تأمين التجارة الخارجية SACE S.P.A':
        'SACE S.p.A. Foreign Trade Insurance Services Representative Office',
    'Misr Insurance':
        'Misr Insurance Company',
    'Misr Life Insurance':
        'Misr Life Insurance Company',
    'SCI – Suez Canal Insurance':
        'Suez Canal Insurance Company (SCI)',
    'Mohandes Insurance co\u200e\u200e':
        'Mohandes Insurance Company',
    'شركة الدلتا للتأمين':
        'Delta Insurance Company',
    'جى أى جى للتأمين- مصر':
        'GIG Insurance - Egypt',
    'شركة متلايف لتأمينات الحياه':
        'MetLife Life Insurance Company',
    'شركة أكســــا لتأمينات الحياه مصر':
        'AXA Life Insurance Company - Egypt',
    'شركة اليانز للتأمين- مصر':
        'Allianz Insurance Company - Egypt',
    'شركة تشب للتأمين مصر':
        'Chubb Insurance Egypt',
    'شركة اليانز لتأمينات الحياه - مصر':
        'Allianz Life Insurance Company - Egypt',
    'شركة رويال للتأمين':
        'Royal Insurance Company',
    'سلامة للتأمين التكافلى - مصر':
        'Salama Takaful Insurance - Egypt',
    'شركة تشب لتأمينات الحياه - مصر':
        'Chubb Life Insurance Company - Egypt',
    'شركة كيو ان بى لتأمينات الحياه':
        'QNB Life Insurance Company',
    'شركة بوبا ايجيبت للتأمين':
        'Bupa Egypt Insurance Company',
    'المصرية للتأمين التكافلى على الممتلكات والمسئوليا':
        'Egyptian Takaful Insurance Company - Property and Liabilities',
    'جى أى جى مصر _ حياه تكافل':
        'GIG Egypt - Life Takaful',
    'شركة وثاق للتامين التكافلى - مصر':
        'Wethaq Takaful Insurance Company - Egypt',
    'شركة اسكان للتأمين':
        'Iskan Insurance Company',
    'شركة آروب للتأمين على الحياة - مصر':
        'Orope Life Insurance Company - Egypt',
    'شركة آروب لتأمينات الممتلكات والمسئوليات':
        'Orope Property and Liabilities Insurance Company',
    'الشركة اللبنانيه السويسريه تكافل - مصر':
        'Lebanese Swiss Takaful Company - Egypt',
    'شركة طوكيو مارين مصر جنرال تكافل':
        'Tokio Marine Egypt General Takaful Company',
    'شركة كاف لتأمينات الحياه':
        'KAF Life Insurance Company',
    'اورينت للتامين - مصر':
        'Orient Insurance - Egypt',
    'قناة السويس لتأمينات الحياة':
        'Suez Canal Life Insurance Company',
    'شركة الدلتا لتأمينات الحياة':
        'Delta Life Insurance Company',
    'شركة المهندس لتأمينات الحياة "ش.م.م"':
        'Mohandes Life Insurance Company S.A.E.',
    'شركة أكســـا للتأمين مصر':
        'AXA Insurance Company - Egypt',
    'الشركة المصرية الإماراتية تكافل حياة _ سلامه':
        'Egyptian Emirati Life Takaful Company - Salama',
    'شركة مصر للتأمين التكافلى - ممتلكات ومسئوليات':
        'Misr Takaful Insurance Company - Property and Liabilities',
    'ثروة لتأمينات الحياة sarwa life insurance company':
        'Sarwa Life Insurance Company',
    'ثروه للتأمينsarwa insurance company':
        'Sarwa Insurance Company',
    'الشركة الوطنية للتأمين':
        'National Insurance Company',
    'شركة مدى للتأمين MADA Insurance Company':
        'MADA Insurance Company',
    'الوفاء لتأمينات الحياة_مصر':
        'Al Wafaa Life Insurance - Egypt',
    'مصر للتأمين التكافلى حياة':
        'Misr Takaful Life Insurance Company',
    'Misr Insurance':
        'Misr Insurance Company',
    'Misr Life Insurance':
        'Misr Life Insurance Company',
    'SCI – Suez Canal Insurance':
        'Suez Canal Insurance Company (SCI)',
    'Mohandes Insurance co\u200e\u200e':
        'Mohandes Insurance Company',
}

NAME_EN_OVERRIDE = {norm_ar(k): v for k, v in NAME_EN_OVERRIDE.items()}

# ---- machine-translation helper (addresses + any uncovered name) -------------
_CACHE_PATH = os.path.join(tempfolder, "translation_cache.json")
try:
    with open(_CACHE_PATH, encoding="utf-8") as fh:
        _CACHE = json.load(fh)
except Exception:
    _CACHE = {}

_translate_call = None


def _make_googletrans():
    """googletrans is the project-standard provider (YE CBYE, SD CBOS, LB BLI,
    CN CSRC all use it). Its 3.x API is synchronous and its 4.x API is asyncio,
    and the version string cannot be trusted to tell them apart - the 4.0.2
    distribution still reports googletrans.__version__ == '3.4.0' - so the API
    shape is detected from the function object itself."""
    from googletrans import Translator

    if inspect.iscoroutinefunction(Translator.translate):        # 4.x, asyncio
        async def _run(text):
            async with Translator() as tr:
                return (await tr.translate(text, src='ar', dest='en')).text
        return lambda text: asyncio.run(_run(text))

    translator = Translator()                                    # 3.x, synchronous
    return lambda text: translator.translate(text, src='ar', dest='en').text


def _make_deep_translator():
    from deep_translator import GoogleTranslator
    return GoogleTranslator(source='ar', target='en').translate


# Tried in order; the first provider that imports wins for the rest of the run.
PROVIDERS = (("googletrans", _make_googletrans),
             ("deep_translator", _make_deep_translator))


def _provider_translate(text):
    """Arabic -> English via whichever provider this machine has."""
    global _translate_call
    if _translate_call is None:
        errors = []
        for name, factory in PROVIDERS:
            try:
                _translate_call = factory()
                print("   translation provider: {}".format(name))
                break
            except Exception as exc:
                errors.append("{} ({}: {})".format(name, type(exc).__name__, exc))
        else:
            raise ImportError("no translation provider available - " + "; ".join(errors))
    return _translate_call(text)


def translate_text(text, retries=3):
    """Arabic -> English with an on-disk cache. Returns '' only when the source
    is empty; on a provider outage the original Arabic is returned unchanged so
    a row is never silently lost."""
    src = clean_text(text)
    if not src or not has_arabic(src):
        return src
    if src in _CACHE:
        return _CACHE[src]
    for attempt in range(retries):
        try:
            out = clean_text(_provider_translate(src))
            if out:
                _CACHE[src] = out
                return out
        except Exception as exc:
            if attempt == retries - 1:
                # Report the fault, not the Arabic source - this print runs inside
                # an exception handler, so it must never be able to raise itself.
                print("   !! translation failed ({}: {}) - keeping the Arabic "
                      "original".format(type(exc).__name__, str(exc)[:120]))
            time.sleep(1.5 * (attempt + 1))
    return src


def save_cache():
    with open(_CACHE_PATH, "w", encoding="utf-8") as fh:
        json.dump(_CACHE, fh, ensure_ascii=False, indent=1)


def english_name(arabic_name, site_english=""):
    """FRA's own English name wins; then the curated map; then MT."""
    site_english = clean_text(site_english)
    if site_english and not has_arabic(site_english):
        return site_english
    key = norm_ar(arabic_name)
    if key in NAME_EN_OVERRIDE:
        return NAME_EN_OVERRIDE[key]
    return translate_text(arabic_name)


# ==================================================================
# Field normalisers
# ==================================================================
# fra.gov.eg stores several websites / e-mails with the dots replaced by the
# digit 0 ("www.sci-egypt0com", "misrins3@tedata0net0eg"). A literal 0 in front
# of a TLD is not a valid host, so this is repaired.
_DOT_FIX = re.compile(r'0(?=(?:com|net|org|eg|gov))')


def fix_contact(value):
    v = clean_text(value).replace(" ", "")
    if not v:
        return ""
    return _DOT_FIX.sub(".", v)


def fix_phone(value):
    """Strip the dangling separators FRA leaves around its numbers
    ('-7605445-'); a pair such as '24517620-24517622' is left intact."""
    v = clean_text(value).replace(" ", "").strip("-/.,")
    return "" if not any(ch.isdigit() for ch in v) else v


# The licensed-activity field only ever takes these three values; FRA's own
# English records render them as below, so machine translation is not used.
ACTIVITY_EN = {
    "مكاتب التمثيل": "Representative Office",
    "تأمينات الممتلكات": "Property Insurance",
    "تأمينات الأشخاص": "Life Insurance",
}
ACTIVITY_EN = {norm_ar(k): v for k, v in ACTIVITY_EN.items()}


def activity_en(value):
    value = clean_text(value)
    return ACTIVITY_EN.get(norm_ar(value), translate_text(value))


def norm_date(value):
    """-> YYYY-MM-DD for the ISO and the DD/MM/YYYY shapes FRA publishes."""
    v = clean_text(value)
    if not v:
        return ""
    m = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', v)
    if m:
        return "{}-{:02d}-{:02d}".format(m.group(1), int(m.group(2)), int(m.group(3)))
    m = re.match(r'^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$', v)
    if m:
        return "{}-{:02d}-{:02d}".format(m.group(3), int(m.group(2)), int(m.group(1)))
    return v


# District -> governorate. The register writes the governorate explicitly on
# most rows; when it does not, the Cairo/Giza district is the fallback.
GOVERNORATES = ["Cairo", "Giza", "Alexandria", "Port Said", "Suez", "Ismailia"]
DISTRICT_CITY = [
    ("Mohandiseen", "Giza"), ("Mohandeseen", "Giza"), ("Mohandessin", "Giza"),
    ("Dokki", "Giza"), ("Agouza", "Giza"), ("Smart Village", "Giza"),
    ("Zamalek", "Cairo"), ("Maadi", "Cairo"), ("Heliopolis", "Cairo"),
    ("Nasr City", "Cairo"), ("M Nasr", "Cairo"), ("Madinat Nasr", "Cairo"),
    ("City Stars", "Cairo"), ("Katameya", "Cairo"),
    ("Fifth Settlement", "Cairo"), ("New Cairo", "Cairo"),
    ("Qasr El Nil", "Cairo"), ("Kasr El-Nile", "Cairo"), ("Talaat Harb", "Cairo"),
    ("Downtown", "Cairo"), ("Ramlet Boulak", "Cairo"), ("Nile City", "Cairo"),
    ("Cairo Festival", "Cairo"), ("Teseen", "Cairo"),
]


def city_from_address(address_en):
    a = address_en or ""
    hits = [(pos, g) for pos, g in
            [(a.lower().rfind(g.lower()), g) for g in GOVERNORATES] if pos >= 0]
    if hits:
        return max(hits)[1]                       # last governorate mentioned wins
    low = a.lower()
    for token, city in DISTRICT_CITY:
        if token.lower() in low:
            return city
    return ""


# Countries appearing in the two PDFs -> ISO-3166 alpha-2.
COUNTRY_ISO = {
    "algeria": "DZ", "australia": "AU", "austria": "AT", "bahrain": "BH",
    "barbados": "BB", "belgium": "BE", "bermuda": "BM", "brazil": "BR",
    "canada": "CA", "cayman islands": "KY", "china": "CN", "cyprus": "CY",
    "denmark": "DK", "egypt": "EG", "france": "FR", "germany": "DE",
    "greece": "GR", "guernsey": "GG", "hong kong": "HK", "india": "IN",
    "indonesia": "ID", "ireland": "IE", "italy": "IT", "japan": "JP",
    "jordan": "JO", "kenya": "KE", "korea": "KR", "south korea": "KR",
    "kuwait": "KW", "lebanon": "LB", "liechtenstein": "LI",
    "luxembourg": "LU", "luxemborg": "LU", "malaysia": "MY", "malta": "MT",
    "mauritius": "MU", "mexico": "MX", "morocco": "MA", "netherlands": "NL",
    "nigeria": "NG", "norway": "NO", "oman": "OM", "pakistan": "PK",
    "poland": "PL", "portugal": "PT", "qatar": "QA", "russia": "RU",
    "saudi arabia": "SA", "singapore": "SG", "slovenia": "SI",
    "south africa": "ZA", "spain": "ES", "sweden": "SE", "switzerland": "CH",
    "taiwan": "TW", "thailand": "TH", "togo": "TG", "tunisia": "TN",
    "turkey": "TR",
    "u.a.e": "AE", "uae": "AE", "united arab emirates": "AE",
    "uk": "GB", "u.k": "GB", "united kingdom": "GB",
    "u.s.a": "US", "usa": "US", "united states": "US",
    "vietnam": "VN", "zimbabwe": "ZW",
}
_UNMAPPED_COUNTRIES = set()


def iso2(country_name):
    key = clean_text(country_name).lower().strip(" .")
    if not key:
        return ""
    if key in COUNTRY_ISO:
        return COUNTRY_ISO[key]
    _UNMAPPED_COUNTRIES.add(country_name)
    return ""


# ==================================================================
# Row factory
# ==================================================================
def base_row(list_nr):
    row = {c: "" for c in COLUMNS}
    row.update({
        "ListLabel": LIST_LABEL[list_nr],
        "RegulationType": "Regulated",
        "RegCtry": REG_CTRY,
        "RegCode": REG_CODE,
        "ListCode": list_nr,
        "ListName": regdict[list_nr]["ListName"],
        "ListProcessDate": PROCESS_DATE,
    })
    return row


all_rows = []


# ==================================================================
# ListNr 1 - Egyptian Insurance Companies (paginated Arabic HTML grid)
# ==================================================================
print("\n[1/3] {} ...".format(regdict[1]["ListName"]))


def list1_grid():
    """Every row of the paginated register grid, plus its detail-page URL."""
    out = []
    page = 1
    while True:
        url = regdict[1]["URL"] if page == 1 else "{}page/{}/{}".format(
            L1_BASE, page, L1_QUERY)
        resp = SESSION.get(url, timeout=60)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        table = BeautifulSoup(resp.text, "html.parser").find("table")
        rows = []
        if table:
            for tr in table.find_all("tr")[1:]:
                tds = tr.find_all("td")
                if len(tds) < 5:
                    continue
                link = tds[1].find("a")
                rows.append({
                    "no": clean_text(tds[0].get_text(" ", strip=True)),
                    "name_ar": clean_text(tds[1].get_text(" ", strip=True)),
                    "addr_ar": clean_text(tds[3].get_text(" ", strip=True)),
                    "url": link["href"] if link and link.has_attr("href") else "",
                })
        if not rows:
            break
        print("   page {}: {} rows".format(page, len(rows)))
        out.extend(rows)
        page += 1
        if page > 25:                      # pagination guard
            raise RuntimeError("ListNr 1 pagination did not terminate")
    return out


def list1_detail(url):
    """label -> value for every 2- and 4-cell row of the detail page tables."""
    if not url:
        return {}
    resp = SESSION.get(url, timeout=60)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")
    kv = {}
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [clean_text(c.get_text(" ", strip=True))
                     for c in tr.find_all(["td", "th"])]
            if len(cells) >= 2 and cells[0]:
                kv.setdefault(cells[0], cells[1])
            if len(cells) >= 4 and cells[2]:
                kv.setdefault(cells[2], cells[3])
    return kv


# Detail-page labels (Arabic) -> what they mean.
F_NAME_AR = "اسم الشركة"                    # company name
F_NAME_OFFICE = "اسم المكتب"                 # representative-office name
F_NAME_EN = "اسم الشركة بالانجليزية"          # FRA's own English name
F_ADDRESS = "العنوان"
F_COMPANY_NO = "رقم الشركة"
F_OFFICE_NO = "رقم المكتب"
F_LICENCE_NO = "رقم الترخيص"
F_DECISION_NO = "قرار الهيئة بالترخيص"        # licensing decision no. (offices)
F_LICENCE_DATE = "تاريخ الترخيص"
F_DECISION_DATE = "تاريخ القرار"             # licensing decision date (offices)
F_PHONE = "تليفون"
F_FAX = "فاكس"
F_WEBSITE = "الموقع الالكتروني"
F_EMAIL = "البريد الالكتروني"
F_ACTIVITY = "اسم النشاط"

grid = list1_grid()
print("   {} grid rows; fetching detail pages ...".format(len(grid)))

for i, item in enumerate(grid, 1):
    detail = list1_detail(item["url"])
    time.sleep(0.2)

    # The grid appends "الممثل القانوني : <person>" (legal representative) to the
    # office names - that is not part of the entity name.
    raw_name = detail.get(F_NAME_AR) or detail.get(F_NAME_OFFICE) or item["name_ar"]
    name_ar = clean_text(re.split(r'الممثل القانوني', raw_name)[0].strip(" :"))
    addr_ar = clean_text(detail.get(F_ADDRESS) or item["addr_ar"])

    name_en = english_name(name_ar, detail.get(F_NAME_EN, ""))
    addr_en = translate_text(addr_ar)
    activity = activity_en(detail.get(F_ACTIVITY, ""))

    row = base_row(1)
    row["Name"] = name_en
    row["License_Type"] = activity
    row["Address_1"] = addr_en
    row["City"] = city_from_address(addr_en)
    row["Cntry"] = "EG"
    row["Phone"] = fix_phone(detail.get(F_PHONE, ""))
    row["Fax"] = fix_phone(detail.get(F_FAX, ""))
    row["Website"] = fix_contact(detail.get(F_WEBSITE, ""))
    row["Email"] = fix_contact(detail.get(F_EMAIL, ""))

    reg_no = clean_text(detail.get(F_COMPANY_NO) or detail.get(F_OFFICE_NO, ""))
    if reg_no:
        row["InternalID_1"] = reg_no
        row["InternalID_1_type"] = ("Company Registration Number"
                                    if detail.get(F_COMPANY_NO) else "Office Number")
    lic_no = clean_text(detail.get(F_LICENCE_NO) or detail.get(F_DECISION_NO, ""))
    if lic_no:
        row["InternalID_2"] = lic_no
        row["InternalID_2_type"] = ("Licence Number" if detail.get(F_LICENCE_NO)
                                    else "Licensing Decision Number")
    row["RegulationDate"] = norm_date(detail.get(F_LICENCE_DATE)
                                      or detail.get(F_DECISION_DATE, ""))

    # Jira: "The Arabic versions can be copied to the Mother Company columns."
    row["Name - Mother Company"] = name_ar
    row["Address_1 - Mother company"] = addr_ar

    row["ListLanguage"] = "AR"
    all_rows.append(row)

    if i % 10 == 0 or i == len(grid):
        print("   detail {}/{}".format(i, len(grid)))

save_cache()


# ==================================================================
# PDF download helper
# ==================================================================
def download(url, target):
    path = os.path.join(tempfolder, target)
    resp = SESSION.get(url, timeout=120)
    resp.raise_for_status()
    with open(path, "wb") as fh:
        fh.write(resp.content)
    print("   downloaded {} ({:,} bytes)".format(target, len(resp.content)))
    return path


# ==================================================================
# ListNr 2 - Foreign Reinsurance Brokers (single-page text PDF)
# ==================================================================
print("\n[2/3] {} ...".format(regdict[2]["ListName"]))
pdf2 = download(regdict[2]["URL"], "EG_FRAEG_list2_foreign_reinsurance_brokers.pdf")

with pdfplumber.open(pdf2) as pdf:
    table2 = []
    for page in pdf.pages:
        for tbl in page.extract_tables():
            table2.extend(tbl)

# Locate the header row, then take everything under it whose first cell is a number.
hdr_idx = next(i for i, r in enumerate(table2)
               if r and clean_text(r[0]) == "Reg. No.")
header2 = [clean_text(c) for c in table2[hdr_idx]]
assert header2[:7] == ["Reg. No.", "Company Name", "Country", "Regulatory Authority",
                       "Address", "Director", "Authorization Date"], header2

for raw in table2[hdr_idx + 1:]:
    cells = [clean_text(c) for c in raw]
    if not cells or not cells[0].isdigit():
        continue
    row = base_row(2)
    row["InternalID_1"] = cells[0]
    row["InternalID_1_type"] = "FRA Registration Number"
    row["Name"] = cells[1]
    row["Cntry"] = iso2(cells[2])
    row["License_Type"] = "Foreign Reinsurance Broker (Non-Resident)"
    row["Address_1"] = cells[4]
    row["RegulationDate"] = norm_date(cells[6])
    row["ListLanguage"] = "EN"
    row["ListValidityDate"] = PDF_VALIDITY
    all_rows.append(row)

print("   {} broker rows".format(sum(1 for r in all_rows if r["ListCode"] == 2)))


# ==================================================================
# ListNr 3 - FRA Reinsurance Companies + Reinsurers' Branches (10-page PDF)
# ==================================================================
print("\n[3/3] {} ...".format(regdict[3]["ListName"]))
pdf3 = download(regdict[3]["URL"], "EG_FRAEG_list3_reinsurance_companies.pdf")

# Header / footnote lines that are not entities.
L3_NOISE = re.compile(
    r'(List 2026|^SER\b|^Serial\b|^COUNTRY\b|^REINSURER\b|^RATING\b|^Rate\b|'
    r'S&Ps|A\.M\b|^Fitch\b|^Moody|^Financial\b|^Credit\b|^NOTE\b|^Update\b)', re.I)


def column_bounds(page):
    """x positions of the vertical rules -> column boundaries."""
    xs = sorted({round(e['x0'], 1) for e in page.edges if e['orientation'] == 'v'})
    bounds = []
    for x in xs:
        if not bounds or x - bounds[-1] > 3:
            bounds.append(x)
    return bounds


def group_bounds(page):
    """y positions of the FULL-WIDTH horizontal rules. The COUNTRY cell is merged
    across a country's block, so these rules delimit the country groups."""
    ys = sorted({round(e['top'], 1) for e in page.edges
                 if e['orientation'] == 'h' and e['x0'] < 30 and e['x1'] > 800})
    bounds = []
    for y in ys:
        if not bounds or y - bounds[-1] > 3:
            bounds.append(y)
    return bounds


def page_lines(page):
    """Words clustered into visual lines (the serial digit and its company name
    are not always on exactly the same `top`, so cluster with a tolerance)."""
    words = sorted(page.extract_words(), key=lambda w: (w['top'], w['x0']))
    lines = []
    for w in words:
        if lines and w['top'] - lines[-1][0] < 4:
            lines[-1][1].append(w)
        else:
            lines.append([w['top'], [w]])
    return [(top, sorted(ws, key=lambda w: w['x0'])) for top, ws in lines]


parsed3 = []
with pdfplumber.open(pdf3) as pdf:
    for pno, page in enumerate(pdf.pages, 1):
        section = ("Branch" if "Branches List" in (page.extract_text() or "")
                   else "Company")
        cols = column_bounds(page)
        groups = group_bounds(page)
        if len(cols) < 5:
            raise RuntimeError("ListNr 3 page {}: unexpected column rules".format(pno))

        raw_lines = []
        for top, words in page_lines(page):
            def cell(idx):
                lo, hi = cols[idx], cols[idx + 1]
                return clean_text(" ".join(w['text'] for w in words
                                           if lo - 2 <= w['x0'] < hi - 1))
            joined = " ".join(w['text'] for w in words)
            if L3_NOISE.search(joined):
                continue
            gid = max([j for j, y in enumerate(groups) if top >= y - 1] or [0])
            raw_lines.append({"page": pno, "section": section, "group": (pno, gid),
                              "ser": cell(0), "country": cell(1),
                              "rate": cell(2), "name": cell(3)})

        # broadcast the merged COUNTRY / country-rating cell over its group
        by_group = {}
        for ln in raw_lines:
            if ln["country"]:
                slot = by_group.setdefault(ln["group"], {"country": "", "rate": ""})
                slot["country"] = (slot["country"] + " " + ln["country"]).strip()
                slot["rate"] = ln["rate"] or slot["rate"]
        for ln in raw_lines:
            if not ln["name"] or not ln["ser"].isdigit():
                continue                      # footnote wrap / stray text
            slot = by_group.get(ln["group"], {})
            ln["country"] = slot.get("country", ln["country"])
            ln["rate"] = slot.get("rate", ln["rate"])
            parsed3.append(ln)

# serial continuity check - the strongest signal that nothing was dropped
for section, label in (("Company", "reinsurance companies"),
                       ("Branch", "reinsurers' branches")):
    sers = [int(r["ser"]) for r in parsed3 if r["section"] == section]
    gaps = sorted(set(range(1, max(sers) + 1)) - set(sers)) if sers else []
    dups = sorted({s for s in sers if sers.count(s) > 1})
    print("   {}: {} rows, serials 1-{}, gaps {}, duplicates {}".format(
        label, len(sers), max(sers) if sers else 0, gaps or "none", dups or "none"))
    if gaps or dups:
        raise RuntimeError("ListNr 3 {}: serial continuity broken".format(label))

for rec in parsed3:
    row = base_row(3)
    row["Name"] = rec["name"]
    row["Cntry"] = iso2(rec["country"])
    # NOTE: the PDF's "SER." column is a positional line number, not a registry
    # identifier, so it is deliberately NOT written to InternalID_1.
    if rec["section"] == "Branch":
        row["EntryType"] = "Branch"
        row["License_Type"] = "Reinsurer's Branch"
    else:
        row["License_Type"] = "Reinsurance Company"
    row["ListLanguage"] = "EN"
    row["ListValidityDate"] = PDF_VALIDITY
    all_rows.append(row)


# ==================================================================
# ------ Final step we will save the df to .xlsx file ----
# ==================================================================
os.chdir(scriptfolder)
sqldict = {col: [r[col] for r in all_rows] for col in COLUMNS}
df = pd.DataFrame(sqldict)
df = df[df['Name'] != '']

filename = "{} SQL Ready {}.xlsx".format(regulatorName, str(now).replace(":", ".")[:-7])
outfile = os.path.join(scriptfolder, filename)
df.to_excel(outfile, sheet_name='SQL Ready', index=False)

print("\n" + "=" * 62)
print("Saved {} rows to {}".format(len(df), outfile))

counts = df.groupby("ListCode")["Name"].count().to_dict()
bad = []
for list_nr in sorted(regdict):
    got, exp = counts.get(list_nr, 0), EXPECTED[list_nr]
    flag = "OK" if got == exp else "<-- MISMATCH"
    if got != exp:
        bad.append(list_nr)
    print("  ListCode {}: {:>3} rows (expected {:>3}) {}  {}".format(
        list_nr, got, exp, flag, regdict[list_nr]["ListName"]))

if _UNMAPPED_COUNTRIES:
    print("  !! countries with no ISO-2 mapping: {}".format(
        sorted(_UNMAPPED_COUNTRIES)))
if bad:
    print("!! row-count mismatch on ListCode(s) {} - source structure changed".format(bad))
else:
    print("All list row counts match the source.")
print("=" * 62)
