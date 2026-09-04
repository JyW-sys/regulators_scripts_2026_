# -*- coding: utf-8 -*-
"""
BD IDRABD - Insurance Development and Regulatory Authority (Bangladesh).  Jira DECD-6974.

5 lists, all served by ONE JSON endpoint:

    POST https://idra.org.bd/idra-cms/api/v1/portal/getElement/<slug>

`<slug>` is the last path segment of the public page URL, percent-encoded exactly as it
appears in the browser address bar (the slugs are Bengali).  The response carries the whole
table twice as raw HTML: `body` (Bengali) and `body_en` (English).  No auth, no cookie, no
token - but it MUST be a POST.  A GET returns 401, which is what made v1's successor look
unreachable.

Why v1 is dead: idra.org.bd was rebuilt as a Nuxt 3 SPA.  All five `/site/page/<uuid>/-`
URLs hard-coded in BD_IDRABD_v1.ipynb now return HTTP 404, and the public pages contain zero
<table> tags because the content is client-rendered.  v1 also parsed cells by inline CSS
width (`td style="width:180px"`), which no longer exists.  Both the transport and the parsing
had to be replaced; the list definitions (5 lists, same names) did not change.

Python 3.8 compatible (production is Windows / py3.8 / cp1252 console).
Never print raw scraped text - ASCII slugs and counts only.
"""

#---- Begin_Librairie ----
import os
import io
import re
import sys
import json
import datetime
import warnings

import requests
import urllib3
import pandas as pd
from bs4 import BeautifulSoup

urllib3.disable_warnings()
warnings.simplefilter('ignore')

try:                                    # corporate TLS proxy on the dev Mac
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
except Exception:
    pass


#---- Begin_fileName ----
regulatorName = 'BD IDRABD'

try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))   ## production environment (.py)
except NameError:
    scriptfolder = os.getcwd()                                  ## notebook environment

os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder')
if not os.path.isdir(tempfolder):
    os.makedirs(tempfolder)

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(':', '.')[:-7])


#---- Begin_Variable ----
API = 'https://idra.org.bd/idra-cms/api/v1/portal/getElement/'

# The public page URL for each list, exactly as given in DECD-6974.  The slug the API wants
# is the last path segment of these, so nothing else is hard-coded.
regdict = {
    'BD IDRABD 1': 'https://idra.org.bd/page/%E0%A6%B2%E0%A6%BE%E0%A6%87%E0%A6%AB-%E0%A6%AC%E0%A7%80%E0%A6%AE%E0%A6%BE%E0%A6%95%E0%A6%BE%E0%A6%B0%E0%A7%80-%E0%A6%AA%E0%A7%8D%E0%A6%B0%E0%A6%A4%E0%A6%BF%E0%A6%B7%E0%A7%8D%E0%A6%A0%E0%A6%BE%E0%A6%A8%E0%A6%B8%E0%A6%AE%E0%A7%82%E0%A6%B9-5',
    'BD IDRABD 2': 'https://idra.org.bd/page/%E0%A6%A8%E0%A6%A8-%E0%A6%B2%E0%A6%BE%E0%A6%87%E0%A6%AB-%E0%A6%AC%E0%A7%80%E0%A6%AE%E0%A6%BE%E0%A6%95%E0%A6%BE%E0%A6%B0%E0%A7%80-7',
    'BD IDRABD 3': 'https://idra.org.bd/page/%E0%A6%B2%E0%A6%BE%E0%A6%87%E0%A6%AB-46',
    'BD IDRABD 4': 'https://idra.org.bd/page/%E0%A6%A8%E0%A6%A8-%E0%A6%B2%E0%A6%BE%E0%A6%87%E0%A6%AB-19',
    'BD IDRABD 5': 'https://idra.org.bd/page/%E0%A6%87%E0%A6%A8%E0%A7%8D%E0%A6%B8%E0%A7%8D%E0%A6%AF%E0%A7%81%E0%A6%B0%E0%A6%9F%E0%A7%87%E0%A6%95-%E0%A6%AA%E0%A7%8D%E0%A6%B0%E0%A6%A4%E0%A6%BF%E0%A6%B7%E0%A7%8D%E0%A6%A0%E0%A6%BE%E0%A6%A8%E0%A6%B8%E0%A6%AE%E0%A7%82%E0%A6%B9%E0%A7%87%E0%A6%B0-%E0%A6%A4%E0%A6%BE%E0%A6%B2%E0%A6%BF%E0%A6%95%E0%A6%BE',
}

ListNames = {
    'BD IDRABD 1': 'List of Life Insurers',
    'BD IDRABD 2': 'List of Non-Life Insurers',
    'BD IDRABD 3': 'List of Life Bancassurance Institutions',
    'BD IDRABD 4': 'List of Non-Life Bancassurance Institutions',
    'BD IDRABD 5': 'List of Authorized Insurtech Institutions',
}

# ListLabel: 1 = bank, 2 = insurance, 3 = bank & insurance, 4 = everything else.
# Lists 1/2 are risk carriers -> 2.  Lists 3/4 are BANKS licensed by the insurance regulator
# to distribute insurance (bancassurance corporate agents) -> 3.  List 5 are insurance
# intermediaries, not carriers -> 2, following the ID OJK precedent in this repo.
# See README "ListLabel justification" - lists 3, 4 and 5 need ticket-owner confirmation.
ListLabels = {
    'BD IDRABD 1': '2',
    'BD IDRABD 2': '2',
    'BD IDRABD 3': '3',
    'BD IDRABD 4': '3',
    'BD IDRABD 5': '2',
}

CoTypes = {
    'BD IDRABD 1': 'Life Insurer',
    'BD IDRABD 2': 'Non-Life Insurer',
    'BD IDRABD 3': 'Bank',
    'BD IDRABD 4': 'Bank',
    'BD IDRABD 5': 'Insurtech Company',
}

LicenseTypes = {
    'BD IDRABD 1': 'Life Insurance',
    'BD IDRABD 2': 'Non-Life Insurance',
    'BD IDRABD 3': 'Life Bancassurance Corporate Agent',
    'BD IDRABD 4': 'Non-Life Bancassurance Corporate Agent',
    'BD IDRABD 5': 'Authorized Insurtech',
}

# The 43-key schema.  FIXED - do not add, remove or rename a key.
sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}

SCHEMA_KEYS = list(sqldict.keys())
assert len(SCHEMA_KEYS) == 43, 'schema must have exactly 43 keys, found {}'.format(len(SCHEMA_KEYS))

# Columns Excel would otherwise turn into floats / strip leading zeros from.
TEXT_COLS = ['InternalID_1', 'InternalID_2', 'InternalID_3', 'Zip', 'Phone', 'Fax',
             'ListCode', 'ListLabel']

STATS = {}
FAILURES = []


#---- Begin_Fonction ----
BENGALI_RE = re.compile(u'[ঀ-৿]')
BN_DIGITS = {u'০': '0', u'১': '1', u'২': '2', u'৩': '3', u'৪': '4',
             u'৫': '5', u'৬': '6', u'৭': '7', u'৮': '8', u'৯': '9'}


def clean(v):
    """Collapse whitespace, drop zero-width junk and lone dashes."""
    if v is None:
        return ''
    s = u'{}'.format(v)
    s = s.replace(u'​', '').replace(u'﻿', '').replace(u'\xa0', ' ')
    s = re.sub(r'[\r\t]', ' ', s)
    s = re.sub(r'[ ]{2,}', ' ', s).strip()
    if s in ('-', '--', 'N/A', 'n/a', '.', 'nil', 'Nil'):
        return ''
    return s


def ascii_slug(v, n=70):
    """cp1252-safe rendering for console output.  NEVER print raw scraped text."""
    return u'{}'.format(v).encode('ascii', 'replace').decode('ascii')[:n]


def bn_to_ascii_digits(s):
    out = []
    for ch in u'{}'.format(s):
        out.append(BN_DIGITS.get(ch, ch))
    return ''.join(out)


def is_bengali(s):
    return bool(BENGALI_RE.search(u'{}'.format(s)))


def to_iso_date(v):
    """'05/02/2024' (dd/mm/yyyy, Bengali digits accepted) -> '2024-02-05'."""
    s = bn_to_ascii_digits(clean(v))
    m = re.search(r'(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{4})', s)
    if not m:
        return ''
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return ''
    try:
        return datetime.date(y, mo, d).isoformat()
    except ValueError:
        return ''


def license_key(v):
    """Join key shared by the Bengali and English renderings: 'NN/YYYY'."""
    s = bn_to_ascii_digits(clean(v))
    m = re.search(r'(\d{1,3})\s*/\s*(\d{4})', s)
    if not m:
        return ''
    return '{:02d}/{}'.format(int(m.group(1)), m.group(2))


def is_mojibake(s):
    return any(bad in u'{}'.format(s) for bad in (u'Ã©', u'â', u'Â '))


def add_row(**kw):
    """Single funnel into sqldict.  Raises on any key outside the fixed 43."""
    for k in kw:
        if k not in sqldict:
            raise KeyError('field {!r} is not part of the 43-key schema'.format(k))
    for k in SCHEMA_KEYS:
        sqldict[k].append(clean(kw.get(k, '')))
    lens = set(len(v) for v in sqldict.values())
    assert len(lens) == 1, 'schema columns went out of sync: {}'.format(sorted(lens))


# ---- translation -------------------------------------------------------------------
# The cache below was produced with googletrans (bn -> en) against the live site and is
# baked in so the production run needs NO translation library and NO network call for it.
# googletrans is used only as a fallback for strings the site adds later.
# NOT pure machine output: six entries were corrected by hand on 2026-09-02 against the
# Bangladesh Insurance Association directory and the companies' own sites, because
# googletrans had translated the proper noun instead of transliterating it --
#   Sandhani (was 'Thanthi'), Jiban Bima Corporation (was 'Life Insurance Corporation',
#   which collided with the different company LIC of Bangladesh), Pragati (was
#   'Progress'), Akij (was 'Akiz'), Alpha (was 'Alfa'), Fareast (was 'Far East').
# Two addresses carrying the same proper nouns were corrected with them.  Do not
# regenerate this cache from googletrans without re-applying these; validate_content()
# asserts the bad forms never come back.
TRANSLATIONS = json.loads(u'''{
"আকিজ তাকাফুল লাইফ ইন্স্যুরেন্স পিএলসি": "Akij Takaful Life Insurance Plc",
"আজিজ ভবন (৬ষ্ঠ তলা), ৯৩ মতিঝিল বা/এ, ঢাকা-১০০০, বাংলাদেশ।": "Aziz Bhawan (6th Floor), 93 Motijheel B/A, Dhaka-1000, Bangladesh.",
"আজিজ ভবন (৯ম তলা), ৯৩ মতিঝিল বানিজ্যিক এলাকা, ঢাকা-১০০০": "Aziz Bhawan (9th Floor), 93 Motijheel Commercial Area, Dhaka-1000",
"আমেরিকান লাইফ ইন্স্যুরেন্স কোম্পানী (মেটলাইফ)": "American Life Insurance Company (MetLife)",
"আলফা ইসলামী লাইফ ইনস্যুরেন্স পিএলসি": "Alpha Islami Life Insurance Plc",
"আস্থা লাইফ ইন্স্যুরেন্স কোম্পানী লিমিটেড": "Astha Life Insurance Company Limited",
"আস্থা লাইফ ইন্স্যুরেন্স কোম্পানী লিমিটেড এসকেএস টাওয়ার (লেভেল- ১২) ৭ ভিআইপি রোড, মহাখালী ঢাকা- ১২০৬": "Astha Life Insurance Company Limited SKS Tower (Level-12) 7 VIP Road, Mohakhali Dhaka-1206",
"ইউসিবি ব্যাংক পিএলসি": "UCB Bank Plc",
"ইসলাম টাওয়ার, ৯ম তলা, ৪৬৪/এইচ, ডিআইটি রোড, পশ্চিম রামপুরা, ঢাকা-১২১৯": "Islam Tower, 9th Floor, 464/H, DIT Road, West Rampura, Dhaka-1219",
"ইস্টার্ন ব্যাংক পিএলসি": "Eastern Bank Plc",
"উদয় টাওয়ার (৮ম তলা), ৫৭-৫৭এ, গুলশান এভিনিউ, গুলশান, ঢাকা": "Uday Tower (8th Floor), 57-57A, Gulshan Avenue, Gulshan, Dhaka",
"এ.জে. টাওয়ার, লেভেল: ২-৪ এন্ড ৬-১৩, প্লট- ৪, সোনারগাঁও লিংক রোড, কাওরান বাজার, ঢাকা-১২১৫": "A.J. Tower, Level: 2-4 & 6-13, Plot-4, Sonargaon Link Road, Kawran Bazar, Dhaka-1215",
"এনআরবি ইসলামিক লাইফ ইন্স্যুরেন্স পিএলসি": "NRB Islamic Life Insurance Plc",
"এনএলআই টাওয়ার, ৫৪-৫৫, কাজী নজরুল ইসলাম এভিনিউ, কারওয়ান বাজার, ঢাকা-১২১৫।": "NLI Tower, 54-55, Kazi Nazrul Islam Avenue, Karwan Bazar, Dhaka-1215.",
"এল্লাল চেম্বার (২য় তলা) 11 মতিঝিল সি/এ, ঢাকা-১০০০।": "Ellal Chamber (2nd Floor) 11 Motijheel C/A, Dhaka-1000.",
"গাউছে পাক ভবন(১৪ তলা) , ২৮/জি/১ টয়েনবী সার্কুলার রোড , মতিঝিল বা/এ , ঢাকা -১০০০।": "Gauche Pak Building (14th Floor), 28/G/1 Toynbee Circular Road, Motijheel B/A, Dhaka-1000.",
"গার্ডিয়ান লাইফ ইন্স্যুরেন্স লিমিটেড": "GUARDIAN LIFE INSURANCE LIMITED",
"গোল্ডেন লাইফ ইন্স্যুরেন্স লিমিটেড": "GOLDEN LIFE INSURANCE LIMITED",
"চার্টার্ড লাইফ ইন্স্যুরেন্স পিএলসি.": "Chartered Life Insurance plc.",
"জাতীয় স্কাউট ভবন, ( ৯ম তলা) 60 আঞ্জুমান মফিদুল ইসলাম রোড, কাকরাইল , ঢাকা-১০০০": "National Scout Building, (9th Floor) 60 Anjuman Mofidul Islam Road, Kakrail, Dhaka-1000",
"জাহাঙ্গীর টাওয়ার (৭ম তলা), ১০ কারওয়ান বাজার": "Jahangir Tower (7th Floor), 10 Karwan Bazar",
"জীবন বীমা কর্পোরেশন": "Jiban Bima Corporation",
"জেনিথ ইসলামী লাইফ ইন্স্যুরেন্স পিএলসি": "Zenith Islami Life Insurance Plc",
"ট্রপিক্যাল মোল্লা টাওয়ার (৫ম তলা), মধ্য বাড্ডা, (১৫/১-১৫/৪ বীর উত্তম রফিকুল ইসলাম এভিনিউ) ঢাকা-১২১২ ।": "Tropical Molla Tower (5th Floor), Madhya Badda, (15/1-15/4 Bir Uttam Rafiqul Islam Avenue) Dhaka-1212.",
"ট্রাস্ট ইসলামী লাইফ ইনসিওরেন্স পিএলসি": "Trust Islami Life Insurance Plc",
"ডাচ-বাংলা ব্যাংক পিএলসি": "Dutch-Bangla Bank Plc",
"ডায়মন্ড লাইফ ইনসিওরেন্স কোম্পানি লিমিটেড": "Diamond Life Insurance Company Limited",
"ডেল্‌টা লাইফ ইনসিওরেন্স কোম্পানী লিমিটেড": "Delta Life Insurance Company Limited",
"ডেল্‌টা লাইফ টাওয়ার, প্লট-৩৭, রোড-৯০, গুলশান-২, ঢাকা-১২১২": "Delta Life Tower, Plot-37, Road-90, Gulshan-2, Dhaka-1212",
"নাভানা-জহুরা স্কয়ার, (লেভেল-৭), ২৮ কাজী নজরুল ইসলাম এভিনিউ, বাংলামটর, ঢাকা-১০০০": "Navana-Jahura Square, (Level-7), 28 Kazi Nazrul Islam Avenue, Banglamator, Dhaka-1000",
"ন্যাশনাল লাইফ ইন্স্যুরেন্স পিএলসি": "National Life Insurance Plc",
"পদ্মা ইসলামী লাইফ ইনসিওরেন্স লিঃ": "Padma Islami Life Insurance Ltd",
"পদ্মা লাইফ টাওয়ার, ১১৫ কাজী নজরুল ইসলাম এভিনিউ, বাংলামটর, ঢাকা-১০০০।": "Padma Life Tower, 115 Kazi Nazrul Islam Avenue, Banglamator, Dhaka-1000.",
"পপুলার লাইফ ইনস্যুরেন্স পিএলসি.": "Popular Life Insurance Plc.",
"পল্টন চায়না টাউন (১৭ তলা-পশ্চিম টাওয়ার), ৬৭/১, নয়াপল্টন (ভিআইপি রোড), ঢাকা-১০০০": "Paltan China Town (17th Floor-West Tower), 67/1, Naya Paltan (VIP Road), Dhaka-1000",
"পুলিশ প্লাজা কনকর্ড, টাওয়ার-০২, লেভেল-১৩, প্লট-২, রোড-১৪৪, গুলশান, ঢাকা-১২১২": "Police Plaza Concord, Tower-02, Level-13, Plot-2, Road-144, Gulshan, Dhaka-1212",
"পূবালী ব্যাংক পিএলসি": "Pubali Bank Plc",
"প্রগতি ইন্স্যুরেন্স ভবন (6ষ্ঠ তলা), 20-21 কাওরান বাজার, ঢাকা-1215.": "Pragati Insurance Bhawan (6th Floor), 20-21 Kawran Bazar, Dhaka-1215.",
"প্রগতি লাইফ ইন্স্যুরেন্স পিএলসি.": "Pragati Life Insurance Plc.",
"প্রগ্রেসিভ লাইফ ইনসিওরেন্স কোম্পানী লিঃ": "Progressive Life Insurance Company Ltd",
"প্রাইম ইসলামী লাইফ ইন্স্যুরেন্স লিমিটেড": "Prime Islami Life Insurance Limited",
"প্রাইম ব্যাংক পিএলসি": "Prime Bank Plc",
"প্রিন্টার্স বিল্ডিং (৭ম তলা), ৫ রাজউক এভিনিউ (দৈনিক বাংলা মোড় সংলগ্ন), মতিঝিল বা/এ, ঢাকা-১০০০।": "Printers Building (7th Floor), 5 Rajuk Avenue (Next to Dainik Bangla Mor), Motijheel B/A, Dhaka-1000.",
"প্রিমিয়ার ব্যাংক পিএলসি": "Premier Bank Plc",
"প্রোটেক্টিভ ইসলামী লাইফ ইন্স্যু্রেন্স লিমিটেড": "Protective Islami Life Insurance Limited",
"ফারইস্ট ইসলামী লাইফ ইন্স্যুরেন্স কোম্পানী লিমিটেড": "Fareast Islami Life Insurance Company Limited",
"ফারইস্ট টাওয়ার (লেভেল-১৮), ৩৫ তোপখানা রোড, ঢাকা-১০০০।": "Fareast Tower (Level-18), 35 Topkhana Road, Dhaka-1000.",
"ফিনিক্স ভবন (৪র্থ তলা), ১২ দিলকুশা বা/এ, ঢাকা -১০০০": "Phoenix Building (4th Floor), 12 Dilkusha B/A, Dhaka-1000",
"বায়রা লাইফ ইন্সিওরেন্স কোম্পানী লিমিটেড": "Baira Life Insurance Company Limited",
"বিটিএ টাওয়ার, 29, কামাল আতাতুর্ক এভিনিউ, রোড-17, বা/এ, বনানি, ঢাকা-1213.": "BTA Tower, 29, Kamal Ataturk Avenue, Road-17, B/A, Banani, Dhaka-1213.",
"বেঙ্গল ইসলামি লাইফ ইন্স্যুরেন্স লিমিটেড": "Bengal Islami Life Insurance Limited",
"বেস্ট লাইফ ইন্স্যুরেন্স লিমিটেড": "BEST LIFE INSURANCE LIMITED",
"ব্রাক ব্যাংক পিএলসি": "BRAC Bank Plc",
"মার্কেন্টাইল ইসলামী লাইফ ইন্স্যুরেন্স লিমিটেড": "Mercantile Islami Life Insurance Limited",
"মাহতাব সেন্টার, 9ম তলা, 177 শহীদ সৈয়দ নজরুল ইসলাম শরণী, ঢাকা 1000": "Mahtab Centre, 9th Floor, 177 Shaheed Syed Nazrul Islam Sarani, Dhaka 1000",
"মিউচুয়াল ট্রাস্ট ব্যাংক": "Mutual Trust Bank",
"মিডল্যান্ড ব্যংক পিএলসি": "Midland Bank plc",
"মেঘনা লাইফ ইনস্যুরেন্স পিএলসি": "Meghna Life Insurance Plc",
"মেঘনা লাইফ-কর্ণফুলী বীমা ভবন, ১১/বি ও ১১/ডি, টয়েনবী সার্কুলার রোড, মতিঝিল বা/এ, ঢাকা-১০০০।": "Meghna Life-Karnaphuli Bima Bhawan, 11/B & 11/D, Toynbee Circular Road, Motijheel B/A, Dhaka-1000.",
"মেটলাইফ বিল্ডিং, ১৮-২০ মতিঝিল বা/এ, ঢাকা-১০০০।": "Metlife Building, 18-20 Motijheel B/A, Dhaka-1000.",
"যমুনা ব্যাংক পিএলসি": "Jamuna Bank Plc",
"যমুনা লাইফ ইনসিওরেন্স কোম্পানি লিমিটেড": "Jamuna Life Insurance Company Limited",
"রূপালী বীমা ভবন, ৭ রাজউক এভিনিউ, ঢাকা-১০০০। বর্ধিত: ৬৮/বি, ডিআইটি রোড, মালিবাগ, ঢাকা-১২১৯।": "Rupali Bima Bhavan, 7 Rajuk Avenue, Dhaka-1000. Extension: 68/B, DIT Road, Malibagh, Dhaka-1219.",
"রূপালী লাইফ ইন্স্যুরেন্স পিএলসি": "Rupali Life Insurance Plc",
"রূপালী লাইফ টাওয়ার, 50 কাকরাইল, ঢাকা-1000": "Rupali Life Tower, 50 Kakrail, Dhaka-1000",
"লাইফ ইন্স্যুরেন্স কর্পোরেশন (এল আই সি)অফ বাংলাদেশ লিমিটেড": "Life Insurance Corporation (LIC) of Bangladesh Limited",
"শান্তা ওয়েস্টার্ন টাওয়ার, লেভেল ১০, ১৮৬ বীর উত্তম মীর শওকত সড়ক (তেজগাঁও), ঢাকা।": "Shanta Western Tower, Level 10, 186 Bir Uttam Mir Shaukat Road (Tezgaon), Dhaka.",
"শান্তা লাইফ ইন্স্যুরেন্স পিএলসি": "Shanta Life Insurance Plc",
"সন্ধানী লাইফ ইনস্যুরেন্স কোং লিঃ": "Sandhani Life Insurance Co. Ltd",
"সন্ধানী লাইফ টাওয়ার, রাজউক প্লট নং-৩৪, বাংলামটর, ঢাকা- ১০০০।": "Sandhani Life Tower, Rajuk Plot No-34, Bangla Motor, Dhaka-1000.",
"সানফ্লাওয়ার লাইফ ইন্স্যুরেন্স কোম্পানি লিমিটেড": "SUNFLOWER LIFE INSURANCE COMPANY LIMITED",
"সানমুন স্টার টাওয়ার (১৫তম তলা), ৩৭ দিলকুসা - ঢাকা- ১০০০": "Sunmoon Star Tower (15th Floor), 37 Dilkusa - Dhaka - 1000",
"সানলাইফ ইনসিওরেন্স কোম্পানী লিমিটেড": "Sunlife Insurance Company Limited",
"সিটি ব্যাংক পিএলসি": "City Bank Plc",
"সোনালী লাইফ ইন্স্যুরেন্স পিএলসি": "Sonali Life Insurance Plc",
"স্ট্যান্ডার্ড  চাটার্ড ব্যাংক": "Standard Chartered Bank",
"স্বদেশ ইসলামী লাইফ ইন্স্যুরেন্স কোম্পানী লিমিটেড": "Swadesh Islami Life Insurance Company Limited",
"হোমল্যান্ড লাইফ ইন্স্যুরেন্স কোম্পানী লিমিটেড": "Homeland Life Insurance Company Limited",
"১০০, এইচ আর কমপ্লেক্স (৬ষ্ঠ তলা), বীব উত্তম এ কে খন্দকার রোড, মহাখালী, বা/এ, ঢাকা-1212।": "100, HR Complex (6th Floor), Beeb Uttam AK Khandkar Road, Mohakhali, B/A, Dhaka-1212.",
"১৫, দিলখুশা,ঢাকা-১০০০": "15, Dilkhusha, Dhaka-1000",
"২৪ মতিঝিল বা/এ": "24 Motijheel or/a",
"৩৬, কাকরাইল, ঢাকা-১০০০।": "36, Kakrail, Dhaka-1000.",
"৩৬, দিলকুশা, পিপলস ইনস্যুরেন্স ভবন (১৮তলা) ঢাকা ১০০০।": "36, Dilkusha, People's Insurance Building (18th floor) Dhaka 1000.",
"৪১/৬ কালভার্ট রোড, পুরানা পল্টন, ঢাকা-১০০০।": "41/6 Calvert Road, Purana Paltan, Dhaka-1000."
}''')

_live_translator = None
_translate_dead = False


def translate_bn(text):
    """Return English for a Bengali string.  Cache first, live provider only on a miss.

    Returns (english, was_translated).  On total failure the ORIGINAL Bengali is returned
    with was_translated=False, so a dead translation provider degrades the data instead of
    killing the run.
    """
    global _live_translator, _translate_dead
    s = clean(text)
    if not s or not is_bengali(s):
        return s, False
    if s in TRANSLATIONS:
        return TRANSLATIONS[s], True
    if _translate_dead:
        STATS['translate_miss'] = STATS.get('translate_miss', 0) + 1
        return s, False
    try:
        import asyncio
        import inspect
        from googletrans import Translator
        if _live_translator is None:
            _live_translator = Translator()
        fn = _live_translator.translate
        if inspect.iscoroutinefunction(fn):          # googletrans 4.x is async
            res = asyncio.get_event_loop().run_until_complete(fn(s, src='bn', dest='en'))
        else:                                        # googletrans 3.x is sync
            res = fn(s, src='bn', dest='en')
        out = clean(res.text)
        if out and not is_bengali(out):
            TRANSLATIONS[s] = out
            STATS['translate_live'] = STATS.get('translate_live', 0) + 1
            return out, True
    except Exception as exc:
        _translate_dead = True
        print('[WARN] : translation provider unavailable ({}); '
              'un-cached Bengali strings will be kept as-is'.format(type(exc).__name__))
    STATS['translate_miss'] = STATS.get('translate_miss', 0) + 1
    return s, False


# ---- address helpers ---------------------------------------------------------------
BD_CITIES = ['Dhaka', 'Chattogram', 'Chittagong', 'Khulna', 'Rajshahi', 'Sylhet',
             'Barishal', 'Barisal', 'Rangpur', 'Mymensingh', 'Gazipur', 'Narayanganj',
             'Cumilla', 'Comilla', 'Bogura', 'Jashore', 'Jessore']


def split_city_zip(address):
    """Bangladesh postcodes are 4 digits and are written 'Dhaka-1000' / 'Dhaka 1000'."""
    a = bn_to_ascii_digits(clean(address))
    if not a:
        return '', ''
    city = ''
    for c in BD_CITIES:
        if re.search(r'\b' + c + r'\b', a, re.I):
            city = c
            break
    zip_code = ''
    if city:
        m = re.search(r'\b' + city + r'\b\s*[-,–]?\s*(\d{4})\b', a, re.I)
        if m:
            zip_code = m.group(1)
    if not zip_code:
        m = re.search(r'\b(\d{4})\b\s*\.?\s*$', a)
        if m:
            zip_code = m.group(1)
    return city, zip_code


PHONE_RE = re.compile(r'(?:\+?88[\s-]?)?0?\d[\d\s\-()]{6,}\d')
WEB_RE = re.compile(r'(?:https?://|www\.)[\w\-.]+\.[A-Za-z]{2,}(?:/\S*)?', re.I)
MAIL_RE = re.compile(r'[\w.\-+]+@[\w.\-]+\.[A-Za-z]{2,}')
ORDINAL_FRAGMENTS = ('th', 'st', 'nd', 'rd', '&', ',')

# List 2 packs the whole entity into one cell as stacked <p> blocks, and 8 of the 46 names
# wrap onto a second block that holds nothing but the corporate suffix
# ("Asia Pacific General Insurance" / "PLC").  Without this the Name is silently truncated.
NAME_SUFFIX_RE = re.compile(
    r'^(plc|ltd|limited|company|company limited|co|co\. ltd|corporation|'
    r'insurance plc|general insurance plc|plc limited)\.?$', re.I)


def cell_lines(cell):
    """A cell's visible lines.  IDRA uses stacked <p> blocks, not <br>."""
    txt = cell.get_text('\n')
    return [clean(p) for p in txt.split('\n') if clean(p)]


def rejoin_ordinals(parts):
    """'Rupayan trade cen', 'th', 'Floor), 114-115...' is ONE address broken by a <sup>."""
    out = []
    for p in parts:
        if out and p.strip().lower() in ORDINAL_FRAGMENTS:
            out[-1] = out[-1] + p.strip()
        elif out and re.match(r'^(th|st|nd|rd)\b', p.strip(), re.I):
            out[-1] = out[-1] + p.strip()
        else:
            out.append(p)
    return out


#---- Begin_Fetch ----
HEADERS = {
    'user-agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'),
    'accept': 'application/json, text/plain, */*',
    'origin': 'https://idra.org.bd',
    'referer': 'https://idra.org.bd/',
}


def find_key(obj, key):
    """The API wraps the payload differently per deployment; find the field wherever it is."""
    if isinstance(obj, dict):
        if key in obj and obj[key]:
            return obj[key]
        for v in obj.values():
            got = find_key(v, key)
            if got:
                return got
    elif isinstance(obj, list):
        for v in obj:
            got = find_key(v, key)
            if got:
                return got
    return None


def fetch_element(page_url):
    """POST the page slug to the portal API and return the decoded JSON."""
    slug = page_url.rstrip('/').split('/')[-1]
    url = API + slug
    last = None
    for attempt in range(3):
        try:
            r = requests.post(url, headers=HEADERS, verify=False, timeout=60)
            if r.status_code == 200 and r.text.strip().startswith(('{', '[')):
                return r.json()
            last = 'HTTP {}'.format(r.status_code)
        except Exception as exc:
            last = type(exc).__name__
    raise RuntimeError('getElement failed for slug {} ({})'.format(ascii_slug(slug, 40), last))


def table_rows(html):
    """Return the data table's rows as lists of cells.  One table per payload."""
    if not html:
        return []
    soup = BeautifulSoup(html, 'html.parser')
    for br in soup.find_all('br'):
        br.replace_with('\n')
    table = soup.find('table')
    if table is None:
        return []
    return [tr.find_all(['td', 'th']) for tr in table.find_all('tr')]


def entity_rows(rows):
    """Drop the header and any 1-cell continuation row (list 4 has three of them)."""
    return [r for r in rows[1:] if len(r) > 1]


#---- Begin_Main ----
def base(reg, language):
    return dict(
        ListLabel=ListLabels[reg],
        CoType=CoTypes[reg],
        License_Type=LicenseTypes[reg],
        Cntry='BD',
        RegulationType='Regulated',
        RegCtry=reg.split()[0],
        RegCode=reg.split()[1],
        ListCode=reg.split()[2],
        ListName=ListNames[reg],
        ListLanguage=language,
        ListProcessDate=processdate,
    )


def do_list_1(reg, payload):
    """Life insurers.  11 columns, Bengali only - `body_en` is Bengali too (verified:
    36/36 names still Bengali), so names and addresses are machine-translated."""
    rows = entity_rows(table_rows(find_key(payload, 'body')))
    n = 0
    for r in rows:
        if len(r) < 7:
            continue
        name_bn = clean(r[1].get_text(' '))
        addr_bn = clean(r[2].get_text(' '))
        if not name_bn:
            continue
        name, ok_n = translate_bn(name_bn)
        addr, _ = translate_bn(addr_bn)
        city, zip_code = split_city_zip(addr)
        phone = bn_to_ascii_digits(clean(r[5].get_text(' '))) if len(r) > 5 else ''
        email = clean(r[6].get_text(' ')) if len(r) > 6 else ''
        m = MAIL_RE.search(email)
        add_row(Name=name,
                Address_1=addr,
                City=city,
                Zip=zip_code,
                Phone=phone,
                Email=m.group(0) if m else '',
                # 'BN' flags a machine-translated name, i.e. NOT the regulator's own English.
                **dict(base(reg, 'EN' if not ok_n else 'BN')))
        n += 1
    return n


def do_list_2(reg, payload):
    """Non-life insurers.  3 columns; name + address + phone + website are stacked <p>
    blocks inside ONE cell, and the CEO block is a second cell."""
    rows = entity_rows(table_rows(find_key(payload, 'body_en')))
    n = 0
    for r in rows:
        if len(r) < 2:
            continue
        parts = rejoin_ordinals(cell_lines(r[1]))
        if not parts:
            continue
        name = parts[0]
        rest = parts[1:]
        # Re-attach a name that wrapped onto its own <p> ("... Insurance" + "PLC").
        while rest and NAME_SUFFIX_RE.match(rest[0]):
            name = '{} {}'.format(name, rest[0]).strip()
            rest = rest[1:]
            STATS['list2_name_rejoined'] = STATS.get('list2_name_rejoined', 0) + 1
        website, phone, addr_bits = '', [], []
        for p in rest:
            if MAIL_RE.search(p) and not website:
                continue
            if WEB_RE.search(p) and not MAIL_RE.search(p):
                website = WEB_RE.search(p).group(0)
            elif re.search(r'\d', p) and PHONE_RE.search(p) and len(re.sub(r'\D', '', p)) >= 7 \
                    and not re.search(r'(floor|road|avenue|plot|house|level|block|lane|tower|building)', p, re.I):
                phone.append(re.sub(r'^\s*(tel|phone|mobile|cell)[-:. ]*', '', p, flags=re.I))
            else:
                addr_bits.append(p)
        address = ', '.join(addr_bits)
        address = re.sub(r'\s*,\s*,', ',', address).strip(' ,')
        city, zip_code = split_city_zip(address)

        email = ''
        if len(r) > 2:
            ceo = ' '.join(cell_lines(r[2]))
            m = MAIL_RE.search(ceo)
            if m:
                email = m.group(0)
        if not email:
            m = MAIL_RE.search(' '.join(parts))
            if m:
                email = m.group(0)

        add_row(Name=name,
                Address_1=address,
                City=city,
                Zip=zip_code,
                Phone='; '.join(phone)[:100],
                Website=website,
                Email=email,
                **base(reg, 'EN'))
        n += 1
    return n


def do_bancassurance(reg, payload, license_prefix):
    """Lists 3 and 4.  6 columns: SL | Corporate Agent | Partner insurer | License no |
    Issue date | Hotline.

    `body` is authoritative for row identity - verified on list 3, where `body_en` is STALE
    (9 rows vs 12) and misses the three 2025 licensees.  English names are joined in from
    `body_en` on the license number; whatever has no English match is translated.
    """
    bn_rows = entity_rows(table_rows(find_key(payload, 'body')))
    en_rows = entity_rows(table_rows(find_key(payload, 'body_en')))

    en_by_key = {}
    for r in en_rows:
        if len(r) < 4:
            continue
        k = license_key(r[3].get_text(' '))
        if k:
            en_by_key[k] = r

    if len(en_rows) != len(bn_rows):
        STATS['stale_en_{}'.format(reg.split()[2])] = '{} en vs {} bn'.format(len(en_rows), len(bn_rows))

    n = 0
    for r in bn_rows:
        if len(r) < 6:
            continue
        key = license_key(r[3].get_text(' '))
        match = en_by_key.get(key)

        if match is not None:
            name = clean(match[1].get_text(' '))
            translated = False
        else:
            name, ok = translate_bn(clean(r[1].get_text(' ')))
            translated = ok
            STATS['bn_only_{}'.format(reg.split()[2])] = STATS.get('bn_only_{}'.format(reg.split()[2]), 0) + 1
        if not name:
            continue

        internal = '{}{}'.format(license_prefix, key) if key else ''
        date_cell = match[4] if match is not None else r[4]
        hot_cell = match[5] if match is not None else r[5]
        phone = bn_to_ascii_digits(clean(hot_cell.get_text(' ')))

        add_row(Name=name,
                InternalID_1=internal,
                InternalID_1_type='License Number',
                Phone=phone,
                RegulationDate=to_iso_date(date_cell.get_text(' ')),
                **dict(base(reg, 'BN' if translated else 'EN')))
        n += 1
    return n


def do_list_5(reg, payload):
    """Insurtech.  6 columns: Serial | Company | Address | CEO | Mobile | Email."""
    rows = entity_rows(table_rows(find_key(payload, 'body_en')))
    n = 0
    for r in rows:
        if len(r) < 3:
            continue
        name = clean(r[1].get_text(' '))
        if not name:
            continue
        addr = clean(r[2].get_text(' '))
        city, zip_code = split_city_zip(addr)
        phone = bn_to_ascii_digits(clean(r[4].get_text(' '))) if len(r) > 4 else ''
        email = ''
        if len(r) > 5:
            m = MAIL_RE.search(clean(r[5].get_text(' ')))
            if m:
                email = m.group(0)
        add_row(Name=name, Address_1=addr, City=city, Zip=zip_code,
                Phone=phone, Email=email, **base(reg, 'EN'))
        n += 1
    return n


HANDLERS = {
    'BD IDRABD 1': lambda reg, p: do_list_1(reg, p),
    'BD IDRABD 2': lambda reg, p: do_list_2(reg, p),
    'BD IDRABD 3': lambda reg, p: do_bancassurance(reg, p, 'Corporate Agent '),
    'BD IDRABD 4': lambda reg, p: do_bancassurance(reg, p, ''),
    'BD IDRABD 5': lambda reg, p: do_list_5(reg, p),
}

# Row counts observed on the live site on 2026-09-02, used as a drift alarm (warn, not fail).
EXPECTED = {'BD IDRABD 1': 36, 'BD IDRABD 2': 46, 'BD IDRABD 3': 12,
            'BD IDRABD 4': 7, 'BD IDRABD 5': 7}


def main():
    counts = {}
    for k, reg in enumerate(regdict):
        print('[INFO] : Working {}/{} _({})_ '.format(k + 1, len(regdict), reg))
        try:
            payload = fetch_element(regdict[reg])
            body = find_key(payload, 'body')
            rows = table_rows(body)
            if not rows:
                raise RuntimeError('no <table> in the getElement payload')
            n = HANDLERS[reg](reg, payload)
            counts[reg] = n
            site_rows = len(entity_rows(rows))
            print('[INFO] : - {} -> {} rows (site table shows {} entity rows)'.format(
                reg, n, site_rows))
            if n != site_rows:
                print('[WARN] : - ROW COUNT MISMATCH on {}: emitted {} vs table {}'.format(
                    reg, n, site_rows))
            exp = EXPECTED.get(reg)
            if exp is not None and n != exp:
                print('[WARN] : - drift on {}: got {}, expected {} (site may have changed)'.format(
                    reg, n, exp))
        except Exception as exc:
            counts[reg] = 0
            FAILURES.append(reg)
            print('[FAIL] : - {} FAILED: {}: {}'.format(reg, type(exc).__name__,
                                                        ascii_slug(str(exc), 120)))
    return counts


#---- Begin_QA ----
def name_problem(name):
    s = clean(name)
    if not s:
        return 'empty'
    if re.match(r'^[\d.,/\-]+$', s):
        return 'numeric-only'
    if re.match(r'^\d+\.?\d*e[+-]\d+$', s, re.I):
        return 'scientific-notation'
    if s.lower() in ('yes', 'no', 'name', 'sl', 'n/a', 'true', 'false'):
        return 'placeholder'
    if to_iso_date(s):
        return 'looks-like-a-date'
    if is_mojibake(s):
        return 'mojibake'
    if len(s) < 3:
        return 'too-short'
    return ''


def qa_dataframe(df):
    problems = []
    for i, v in enumerate(df['Name'].tolist()):
        p = name_problem(v)
        if p:
            problems.append((i, p, ascii_slug(v, 40)))
    assert not problems, 'Name column content failures: {}'.format(problems[:5])

    for col, want in (('RegCtry', 'BD'), ('RegCode', 'IDRABD'), ('Cntry', 'BD'),
                      ('RegulationType', 'Regulated')):
        bad = sorted(set(df[col]) - set([want]))
        assert not bad, '{} must be {!r}, found {}'.format(col, want, bad[:5])

    assert set(df['ListCode']) <= set(['1', '2', '3', '4', '5']), 'unexpected ListCode'
    assert set(df['ListLabel']) <= set(['1', '2', '3', '4']), 'unexpected ListLabel'
    assert (df['ListProcessDate'] == processdate).all(), 'ListProcessDate not uniform'
    assert list(df.columns) == SCHEMA_KEYS, 'column order drifted from the 43-key schema'

    moji = [ascii_slug(v, 40) for c in df.columns for v in df[c].tolist() if is_mojibake(v)]
    assert not moji, 'mojibake found: {}'.format(moji[:5])

    # googletrans translates a proper noun instead of transliterating it, which is much
    # worse than a clumsy transliteration: 'Life Insurance Corporation' for the state-owned
    # Jiban Bima Corporation collides with the genuinely different 'Life Insurance
    # Corporation (LIC) of Bangladesh Limited', and 'Thanthi' for Sandhani matches nothing
    # at all.  The six below were corrected by hand against the Bangladesh Insurance
    # Association directory and the companies' own sites, and are pinned in TRANSLATIONS.
    # This guard fires if the live-translation fallback ever re-introduces one, which it
    # would do silently the moment IDRA edits a cached string.
    banned = ['Thanthi', 'Akiz', 'Alfa Islami', 'Progress Life', 'Far East Islami']
    hits = ['{}: {}'.format(c, ascii_slug(v, 60))
            for c in ('Name', 'Address_1') for v in df[c].tolist()
            for b in banned if b in v]
    assert not hits, 'known-bad machine translation is back: {}'.format(hits[:5])
    assert (df['Name'] != 'Life Insurance Corporation').all(), \
        "'Life Insurance Corporation' is the mistranslation of Jiban Bima Corporation"
    print('QA: {} rows passed content checks'.format(len(df)))


def digit_fingerprint(df):
    fp = {}
    for c in TEXT_COLS:
        fp[c] = dict((i, v) for i, v in enumerate(df[c].tolist())
                     if v and re.search(r'\d', u'{}'.format(v)))
    return fp


def write_output(df):
    for c in TEXT_COLS:
        df[c] = df[c].astype(str).replace('nan', '').replace('None', '')
    before = digit_fingerprint(df)

    out = os.path.join(scriptfolder, filename)          # NOT tempfolder
    df.to_excel(out, sheet_name='SQL Ready', index=False)
    print('Saved {} rows to {}'.format(len(df), ascii_slug(out, 160)))

    back = pd.read_excel(out, sheet_name='SQL Ready', dtype=str).fillna('')
    assert len(back) == len(df), 'round-trip lost rows: {} -> {}'.format(len(df), len(back))
    assert list(back.columns) == SCHEMA_KEYS, 'round-trip changed the column order'
    after = digit_fingerprint(back)
    for c in TEXT_COLS:
        lost = [(i, before[c][i], after[c].get(i)) for i in before[c]
                if after[c].get(i) != before[c][i]]
        assert not lost, '{} did not survive Excel as text, e.g. {}'.format(c, lost[:3])
    print('Round-trip OK: {} columns pinned to text, {} digit cells verified'.format(
        len(TEXT_COLS), sum(len(v) for v in before.values())))
    return out


#---- Begin_Run ----
DO_RUN = (__name__ == '__main__' and os.environ.get('IDRA_NO_RUN', '') != '1')

if DO_RUN:
    print('BD IDRABD / DECD-6974  process date {}'.format(processdate))
    counts = main()

    print('')
    print('--- per-list rows ---')
    for reg in regdict:
        print('  {} : {}'.format(reg, counts.get(reg, 0)))
    for k in sorted(STATS):
        print('  {} : {}'.format(k, STATS[k]))

    df = pd.DataFrame(sqldict)
    df = df[df['Name'] != '']
    df = df.reset_index(drop=True)
    qa_dataframe(df)
    write_output(df)

    if FAILURES:
        print('[FAIL] : {} list(s) failed: {}'.format(len(FAILURES), ', '.join(FAILURES)))
        sys.exit(2)
