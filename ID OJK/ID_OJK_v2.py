# -*- coding: utf-8 -*-
"""
ID OJK - Otoritas Jasa Keuangan (Indonesia).  Jira DECD-6836.

13 lists, four different source shapes:
  A  direct .xlsx link on the landing page          lists 1, 3, 4
  B  inline HTML table                              list 2
  C  article index -> article -> postback download  lists 5, 7, 8, 9, 10, 11, 12, 13
  D  folder postback -> C, five sub-categories      list 6

Nothing about "which file is the most recent" is hard-coded: OJK republishes every one of
these directories under a new name each period.  The period is parsed out of the link TEXT
(the href lies - see README) and the maximum wins.

Python 3.8 compatible (production is Windows / py3.8 / cp1252 console).
Never print raw scraped text - ASCII slugs and counts only.
"""

#---- Begin_Librairie ----
import os
import re
import io
import sys
import ast
import time
import hashlib
import json
import unicodedata
import datetime
import calendar
import warnings

import requests
import urllib3
import pandas as pd
from bs4 import BeautifulSoup

try:
    from urllib.parse import urljoin, urlparse, unquote
except ImportError:                                            # pragma: no cover (py2)
    from urlparse import urljoin, urlparse                     # type: ignore
    from urllib import unquote                                 # type: ignore

urllib3.disable_warnings()
warnings.simplefilter('ignore')


#---- Begin_fileName ----
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
filename = 'ID OJK SQL Ready ' + now.strftime('%Y%m%d') + '.xlsx'


#---- Begin_Variable ----
sqldict={'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
          'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
          'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
          'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
          'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
          'Phone - Mother company': []}

SCHEMA_KEYS = list(sqldict.keys())
assert len(SCHEMA_KEYS) == 43, 'schema must be exactly 43 keys, got {}'.format(len(SCHEMA_KEYS))

# columns Excel would happily turn into floats / strip leading zeros
TEXT_COLS = ['InternalID_1', 'InternalID_2', 'InternalID_3', 'Zip', 'Phone', 'Fax',
             'Zip - Mother company', 'Phone - Mother company', 'ListCode']

REGCTRY = 'ID'          # hard-coded constants, never derived by splitting a folder name
REGCODE = 'OJK'
CNTRY = 'ID'
REGULATION_TYPE = 'Regulated'
LIST_LANGUAGE = 'ID'

BASE = 'https://www.ojk.go.id'

# Set OJK_WAYBACK=1 to run the whole pipeline against Wayback Machine snapshots instead of the
# live host.  Diagnostic only - the archive does not hold the current data files.
USE_WAYBACK = os.environ.get('OJK_WAYBACK', '') == '1'
WAYBACK_PREFIX = 'https://web.archive.org/web/2id_/'

# ---------------------------------------------------------------- list configuration -------
# kind:      'direct' (A) | 'table' (B) | 'article' (C) | 'folders' (D)
# keyword:   optional regex the ARTICLE LINK TEXT must match (list 13 mixes two series)
LISTS = [
    dict(nr=1, label='1', kind='direct',
         name='List of Commercial Banks and Sharia Banks',
         cotype='Commercial Bank / Sharia Bank',
         url=BASE + '/id/kanal/perbankan/data-dan-statistik/Pages/Daftar-Alamat-Kantor-Pusat-Bank-Umum-Dan-Syariah.aspx'),
    dict(nr=2, label='1', kind='table',
         name='List of Representative Offices of Foreign Banks in Indonesia',
         cotype='Representative Office of Foreign Bank',
         url=BASE + '/id/kanal/perbankan/data-dan-statistik/Pages/Daftar-Alamat-Kantor-Perwakilan-Bank-di-Luar-Negeri.aspx'),
    dict(nr=3, label='1', kind='direct',
         name='List of Rural Bank (BPR)',
         cotype='Rural Bank (BPR)',
         url=BASE + '/id/kanal/perbankan/data-dan-statistik/Pages/Daftar-Alamat-Kantor-Pusat-BPR.aspx'),
    dict(nr=4, label='1', kind='direct',
         name='List of Sharia Rural Banks (BPRS)',
         cotype='Sharia Rural Bank (BPRS)',
         url=BASE + '/id/kanal/perbankan/data-dan-statistik/Pages/Daftar-Alamat-Kantor-Pusat-BPRS.aspx'),
    dict(nr=5, label='4', kind='article',
         name='List of Securities Company',
         cotype='Securities Company',
         url=BASE + '/id/kanal/pasar-modal/data-dan-statistik/data-perusahaan-efek/Default.aspx'),
    dict(nr=6, label='4', kind='folders',
         name='List of Capital Market Players in Indonesia',
         cotype='Capital Market Player',
         url=BASE + '/id/Fungsi-Utama/Pasar-Modal/Informasi-Pasar-Modal/Daftar-Pelaku-Pasar-Modal-Indonesia/Default.aspx'),
    dict(nr=7, label='2', kind='article',
         name='List of Insurance Companies',
         cotype='Insurance Company',
         url=BASE + '/id/kanal/iknb/data-dan-statistik/direktori/asuransi/Default.aspx'),
    dict(nr=8, label='4', kind='article',
         name='List of Guarantee Companies',
         cotype='Guarantee Company',
         url=BASE + '/id/Fungsi-Utama/Perasuransian-Penjaminan-Dana-Pensiun/Informasi-PPDP/Direktori-Lembaga-Penjaminan/Default.aspx'),
    dict(nr=9, label='4', kind='article',
         name='List of Pension Funds',
         cotype='Pension Fund',
         url=BASE + '/id/kanal/iknb/data-dan-statistik/direktori/dana-pensiun/Default.aspx'),
    dict(nr=10, label='2', kind='article',
         name='List of Insurance Brokerage Companies, Reinsurance Brokerage Companies, and Insurance Loss Adjusters',
         cotype='Insurance / Reinsurance Broker / Loss Adjuster',
         url=BASE + '/id/Fungsi-Utama/Perasuransian-Penjaminan-Dana-Pensiun/Informasi-PPDP/Direktori-Jasa-Penunjang-Asuransi/Default.aspx'),
    dict(nr=11, label='4', kind='article',
         name='List of Financing Institutions',
         cotype='Financing Institution',
         url=BASE + '/id/kanal/iknb/data-dan-statistik/direktori/lembaga-pembiayaan/Default.aspx'),
    dict(nr=12, label='4', kind='article',
         name='List of Microfinance Institutions',
         cotype='Microfinance Institution',
         url=BASE + '/id/kanal/iknb/data-dan-statistik/direktori/direktori-lkm/Default.aspx'),
    dict(nr=13, label='4', kind='article',
         name='List of Digital Financial Asset Trading Providers',
         cotype='Digital Financial Asset Trading Provider',
         keyword=r'perdagangan\s+aset\s+keuangan\s+digital',
         url=BASE + '/id/Fungsi-Utama/ITSK/Perizinan-ITSK-Aset-Keuangan-Digital-Aset-Kripto/Default.aspx'),
]

# ---------------------------------------------------------------- Indonesian periods --------
ID_MONTHS = {
    'januari': 1, 'jan': 1,
    'februari': 2, 'pebruari': 2, 'feb': 2, 'febr': 2,
    'maret': 3, 'mar': 3,
    'april': 4, 'apr': 4,
    'mei': 5,
    'juni': 6, 'jun': 6,
    'juli': 7, 'jul': 7,
    'agustus': 8, 'agt': 8, 'ags': 8, 'agu': 8,
    'september': 9, 'sept': 9, 'sep': 9,
    'oktober': 10, 'okt': 10, 'oct': 10,
    'november': 11, 'nop': 11, 'nov': 11,
    'desember': 12, 'des': 12, 'dec': 12,
}
ROMAN_Q = {'i': 1, 'ii': 2, 'iii': 3, 'iv': 4}

# list 2 group headers -> ISO2 of the parent bank's home country
COUNTRY_ID = {
    'jepang': 'JP', 'india': 'IN', 'amerika': 'US', 'amerika serikat': 'US',
    'belanda': 'NL', 'perancis': 'FR', 'prancis': 'FR', 'jerman': 'DE',
    'uni emirat arab': 'AE', 'spanyol': 'ES', 'korea selatan': 'KR', 'korea': 'KR',
    'taiwan': 'TW', 'thailand': 'TH', 'italia': 'IT', 'china': 'CN', 'cina': 'CN',
    'inggris': 'GB', 'singapura': 'SG', 'malaysia': 'MY', 'australia': 'AU',
    'swiss': 'CH', 'belgia': 'BE', 'kanada': 'CA', 'hongkong': 'HK', 'hong kong': 'HK',
    'arab saudi': 'SA', 'qatar': 'QA', 'turki': 'TR', 'rusia': 'RU', 'filipina': 'PH',
    'vietnam': 'VN', 'austria': 'AT', 'denmark': 'DK', 'swedia': 'SE', 'norwegia': 'NO',
    'finlandia': 'FI', 'portugal': 'PT', 'yunani': 'GR', 'polandia': 'PL', 'mesir': 'EG',
    'afrika selatan': 'ZA', 'brasil': 'BR', 'brazil': 'BR', 'meksiko': 'MX',
    'pakistan': 'PK', 'bangladesh': 'BD', 'sri lanka': 'LK', 'mauritius': 'MU',
    'luksemburg': 'LU', 'irlandia': 'IE', 'selandia baru': 'NZ', 'brunei': 'BN',
    'kamboja': 'KH', 'myanmar': 'MM', 'laos': 'LA', 'timor leste': 'TL',
}

# ------------------------------------------------- header label -> schema field (ordered) ---
# Matched against the NORMALISED header (lowercase, punctuation collapsed).  Order matters:
# the first pattern that matches wins, so put the specific ones first.
HEADER_RULES = [
    (r'^no\.?$|^nomor$|^no urut$|^urut$|^no\.? urut$', ''),          # row number - ignore
    (r'sandi', 'InternalID_1'),
    (r'\bnpwp\b', 'InternalID_3'),
    (r'(nomor|no|nomer|no\.)\s*(dan tanggal\s*)?(izin|ijin|kep|sk|keputusan|pendaftaran|stt|registrasi|induk berusaha|nib)'
     r'|izin usaha|surat keputusan|nomor pendaftaran', 'InternalID_2'),
    (r'(tanggal|tgl)\s*(dan nomor\s*)?(izin|ijin|kep|sk|keputusan|pendaftaran|efektif|berdiri|pendirian|berlaku|terbit)',
     'RegulationDate'),
    (r'(tanggal|tgl)\s*(cabut|pencabutan|berakhir)', 'CancellationDate'),
    (r'kode pos|kodepos|kd\.? pos|\bzip\b|pos code', 'Zip'),
    (r'\bfax\b|faks|faksimil|facsimile', 'Fax'),
    (r'telepon|telp|\btlp\b|\bphone\b|\bhp\b|kontak', 'Phone'),
    (r'e ?mail|surel', 'Email'),
    (r'website|situs|\bweb\b|homepage|\burl\b', 'Website'),
    (r'nama.*alamat', 'Name'),                                       # combined column -> Name
    (r'\bkota\b|kabupaten|\bkab\b|kotamadya|domisili', 'City'),
    (r'provinsi|propinsi|wilayah', 'Address_2'),
    (r'alamat|address', 'Address_1'),
    (r'\bnama\b|perusahaan|penyelenggara|emiten|lembaga|institusi|badan usaha|pelaku', 'Name'),
    (r'jenis|bentuk|status|klasifikasi|kategori|\btipe\b|golongan', 'License_Type'),
]

# what the header row of a real data sheet must contain at least one of
HEADER_MUST_HAVE = re.compile(r'nama|perusahaan|alamat|penyelenggara|emiten|lembaga', re.I)

# A section heading that ends the positive register.  OJK appends the revoked companies to
# the BOTTOM of the same sheet, under their own heading and their own repeated header row -
# list 5's 'Perusahaan Efek' carries two of them ('Cabut Izin Usaha Pada Tahun 2025' with 5
# companies, '... Tahun 2026' with 3) and 'PPE Khusus' carries one.  Without this they were
# emitted as Regulated.  Everything from the heading down is dropped, which also disposes of
# the repeated 'No. | Nama Perusahaan Efek' header underneath it.
#
# NOT a stop word: 'Masih dalam proses persetujuan pencatatan di OJK', the yellow-highlight
# legend.  What is pending there is the *pencatatan* (recording of a data change), not the
# licence - those rows sit in the main register with a full licence number - so they stay.
SECTION_STOP = re.compile(r'cabut\s+izin|pencabutan\s+izin|izin\s+.*dicabut', re.I)

# List 6 only.  'Wakil Agen Penjual Efek Reksa Dana' is the register of individual SELLING
# AGENTS (natural persons), not companies - the ticket owner ruled it out of scope on
# 2025-12-03, keeping the other three sub-folders of 'Pelaku Perorangan Pasar Modal'.
# Anchored on 'wakil' so it cannot also swallow 'Agen Penjual Efek Reksa Dana' itself.
FOLDER_SKIP = re.compile(r'^\s*wakil\b', re.I)
FOLDER_MAX_DEPTH = 3

# A folder whose children are all bare years - 'Profesi Penunjang Pasar Modal' files each
# profession's register that way, 2019 through 2026.  Only the newest year holds the
# current register; the older folders are the same register at earlier dates, so descending
# into all of them would emit every person once per year.
YEAR_FOLDER_RE = re.compile(r'^\s*(20\d{2})\s*$')

# OJK's own empty-folder message.  A folder that publishes nothing is not a scrape failure
# and must not be dumped as one - 'Profesi Penunjang Pasar Modal / Akuntan' is simply empty.
EMPTY_FOLDER_RE = re.compile(r'no\s+article\s+available|tidak\s+ada\s+artikel', re.I)


#---- Begin_Function_text ----
ZERO_WIDTH = u'​‌‍﻿­'


def clean(v):
    """Scrub a scraped cell: NFKC, kill zero-width/NBSP, collapse whitespace."""
    if v is None:
        return ''
    try:
        if isinstance(v, float) and pd.isna(v):
            return ''
    except Exception:
        pass
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.strftime('%Y-%m-%d')
    s = v if isinstance(v, str) else str(v)
    if s.lower() in ('nan', 'nat', 'none'):
        return ''
    s = unicodedata.normalize('NFKC', s)
    for ch in ZERO_WIDTH:
        s = s.replace(ch, '')
    s = s.replace(u'\xa0', ' ')
    s = re.sub(r'\s+', ' ', s).strip()
    if s in ('-', '--', '.', '_', 'n/a', 'N/A', 'NA'):
        return ''
    return s


def norm(v):
    """Normalised header label: lowercase, punctuation -> space, collapsed."""
    s = clean(v).lower()
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def slug(v, n=60):
    """ASCII-only, printable rendering.  The production console is cp1252 - raw Indonesian
    text (and anything the site hands us) must never reach print()."""
    s = clean(v)
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    s = re.sub(r'[^A-Za-z0-9 ._()\-/]+', '?', s)
    return s[:n]


def is_mojibake(s):
    return bool(re.search(r'[�]|Ã.|â€|ï¿½', s or ''))


#---- Begin_Function_schema ----
def add_row(**kw):
    """Single funnel into sqldict.  Appends to EVERY one of the 43 keys; raises on an
    unknown key so the schema cannot drift, and asserts the columns stay in sync."""
    unknown = set(kw) - set(SCHEMA_KEYS)
    if unknown:
        raise KeyError('add_row got key(s) not in the 43-key schema: {}'.format(sorted(unknown)))
    for k in SCHEMA_KEYS:
        val = kw.get(k, '')
        sqldict[k].append('' if val is None else str(val))
    lens = set(len(v) for v in sqldict.values())
    if len(lens) != 1:
        raise AssertionError('sqldict columns fell out of sync: {}'.format(sorted(lens)))


#---- Begin_Function_period ----
def _last_day(y, m):
    return calendar.monthrange(y, m)[1]


def parse_period(text):
    """Parse an Indonesian period out of link text.  Returns (y, m, d) or None.

    Handles, in this order of precedence:
        'Posisi 21 April 2026' / '21 April 2026'   -> (2026, 4, 21)
        'Triwulan III 2025' / 'Triwulan II Tahun 2024'
        'Desember 2025'
        '122025' / '2025-12'
        bare '2025'
    """
    s = clean(text).lower()
    if not s:
        return None
    mon = r'(januari|februari|pebruari|maret|april|mei|juni|juli|agustus|september|oktober|november|nopember|desember|jan|feb|febr|mar|apr|jun|jul|agt|ags|agu|sept|sep|okt|oct|nop|nov|des|dec)'

    m = re.search(r'\b(\d{1,2})\s+' + mon + r'\s+(\d{4})\b', s)
    if m:
        d, mo, y = int(m.group(1)), ID_MONTHS.get(m.group(2)), int(m.group(3))
        if mo and 1 <= d <= _last_day(y, mo):
            return (y, mo, d)

    m = re.search(r'triwulan\s+(iv|iii|ii|i)\b(?:\s+tahun)?\s+(\d{4})', s)
    if m:
        q, y = ROMAN_Q[m.group(1)], int(m.group(2))
        mo = q * 3
        return (y, mo, _last_day(y, mo))

    m = re.search(r'\b' + mon + r'\s*(?:tahun\s*)?(\d{4})\b', s)
    if m:
        mo, y = ID_MONTHS.get(m.group(1)), int(m.group(2))
        if mo:
            return (y, mo, _last_day(y, mo))

    m = re.search(r'\b(\d{4})\s*[-/]\s*(\d{1,2})\b', s)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            return (y, mo, _last_day(y, mo))

    # Compact dates inside a file name, which is all list 6's leaf files carry:
    # '20241108 Penyelenggara SCF Berizin.pdf' and '310126_Statistik Notaris.pdf'.
    # Both are validated as real calendar dates, so a licence or decree number of the
    # same length cannot be mistaken for one.  Below the named-month rules on purpose:
    # a date written out in words is always the better evidence.
    m = re.search(r'\b(20\d{2})(\d{2})(\d{2})\b', s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= _last_day(y, mo):
            return (y, mo, d)

    m = re.search(r'\b(\d{2})(\d{2})(\d{2})_', s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), 2000 + int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= _last_day(y, mo):
            return (y, mo, d)

    m = re.search(r'\b(20\d{2})\b', s)
    if m:
        y = int(m.group(1))
        return (y, 12, 31)
    return None


def period_iso(p):
    if not p:
        return ''
    return '%04d-%02d-%02d' % p


def to_iso_date(v):
    """Best-effort date -> YYYY-MM-DD.  Returns '' when it is not a date."""
    if v is None:
        return ''
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.strftime('%Y-%m-%d')
    s = clean(v)
    if not s:
        return ''
    m = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})', s)
    if m:
        return '%04d-%02d-%02d' % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r'^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$', s)
    if m:                                    # Indonesian order is dd-mm-yyyy
        return '%04d-%02d-%02d' % (int(m.group(3)), int(m.group(2)), int(m.group(1)))
    p = parse_period(s)
    if p and re.search(r'\d{1,2}\s+\w+\s+\d{4}', s):
        return period_iso(p)
    return ''


#---- Begin_Function_transport ----
# ONE acceptance test for downloaded bytes, used by BOTH the retry loop and the parse-time
# assert.  If these two ever differ, a WAF error page gets accepted as "nearly right" and the
# parser takes the blame for the transport's failure.
XLSX_MAGIC = b'PK\x03\x04'
XLS_MAGIC = b'\xd0\xcf\x11\xe0'
PDF_MAGIC = b'%PDF'


def file_kind(blob):
    """'xlsx' | 'xls' | 'pdf' | '' - by magic bytes, never by file extension."""
    if not blob or len(blob) < 512:
        return ''
    head = blob[:4]
    if head == XLSX_MAGIC:
        return 'xlsx'
    if head == XLS_MAGIC:
        return 'xls'
    if head == PDF_MAGIC or blob[:2048].find(PDF_MAGIC) >= 0:
        return 'pdf'
    return ''


WAF_MARKERS = ('the requested url was rejected', 'support id', 'access denied',
               'request rejected', 'incapsula', 'attention required')


def page_problem(html):
    """'' when the HTML is a usable OJK page, else a short ASCII reason.
    Same function is used by the fetch loop and by the parse-time assert."""
    if not html or len(html) < 2000:
        return 'too-short:{}'.format(len(html or ''))
    low = html[:200000].lower()
    for mark in WAF_MARKERS:
        if mark in low:
            return 'waf:' + mark.replace(' ', '-')
    if 'aspnetform' not in low and 'class="content"' not in low and "class='content'" not in low:
        return 'no-aspnet-form-and-no-content-div'
    return ''


def dump_fail(tag, payload, landed_url):
    """Dump the failing bytes/HTML plus the URL we actually landed on, so a production
    failure is diagnosable without a re-run."""
    try:
        base = os.path.join(tempfolder, 'FAIL_' + re.sub(r'[^A-Za-z0-9_.-]+', '_', tag)[:80])
        mode, data = ('wb', payload) if isinstance(payload, bytes) else ('w', payload)
        f = io.open(base + ('.bin' if mode == 'wb' else '.html'), mode,
                    **({} if mode == 'wb' else {'encoding': 'utf-8', 'errors': 'replace'}))
        f.write(data)
        f.close()
        f = io.open(base + '.url.txt', 'w', encoding='utf-8')
        f.write(landed_url or '')
        f.close()
        print('    [dump] {}'.format(slug(os.path.basename(base))))
    except Exception as exc:
        print('    [dump failed] {}'.format(type(exc).__name__))


def wb(url):
    return WAYBACK_PREFIX + url if USE_WAYBACK else url


#---- Begin_Cache ----
# A development cache, OFF unless OJK_CACHE=1 is set.  It exists for one reason: debugging a
# parser must never cost the regulator a request.  A production run makes one pass over the
# site; a debugging session re-runs the same list ten times, and the difference is what gets
# a scraper noticed.  Deliberately opt-in, so a scheduled production run can never serve
# stale data by accident.  Delete tempfolder/httpcache to force a refetch.
CACHE_DIR = os.path.join(tempfolder, 'httpcache')
CACHE_ON = os.environ.get('OJK_CACHE') == '1'


def _cache_path(kind, key):
    return os.path.join(
        CACHE_DIR, '%s_%s' % (kind, hashlib.sha1(key.encode('utf-8')).hexdigest()[:16]))


def cache_get(kind, key):
    """(payload, landed_url) or None.  payload is bytes for files, text for pages."""
    if not CACHE_ON:
        return None
    p = _cache_path(kind, key)
    if not (os.path.isfile(p + '.body') and os.path.isfile(p + '.url')):
        return None
    with open(p + '.body', 'rb') as fh:
        body = fh.read()
    with io.open(p + '.url', encoding='utf-8') as fh:
        landed = fh.read().strip()
    print('    [cache] {} {}'.format(kind, slug(key, 90)))
    return (body if kind.endswith('file') else body.decode('utf-8', 'replace')), landed


def cache_put(kind, key, payload, landed):
    if not CACHE_ON:
        return
    if not os.path.isdir(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    p = _cache_path(kind, key)
    with open(p + '.body', 'wb') as fh:
        fh.write(payload if isinstance(payload, bytes) else payload.encode('utf-8'))
    with io.open(p + '.url', 'w', encoding='utf-8') as fh:
        fh.write(landed or '')


def postback_key(page_url, extra):
    """What identifies a postback response: the page it was fired from and the control that
    fired.  __VIEWSTATE is deliberately not part of the key - it changes on every fetch of
    the same page and would make the cache always miss."""
    return '{}|{}|{}'.format(page_url, extra.get('__EVENTTARGET', ''),
                             extra.get('__EVENTARGUMENT', ''))
#---- End_Cache ----


class Transport(object):
    """requests first; DrissionPage/Chromium only if requests cannot get a usable page.
    v1 used Selenium throughout, which suggests plain requests may not suffice in
    production - but we do not pay for a browser until we have to."""

    RETRY_STATUSES = (0, 403, 408, 429, 500, 502, 503, 504)

    def __init__(self):
        self.mode = 'requests'
        self.page = None
        self.dldir = os.path.join(tempfolder, 'downloads')
        if not os.path.isdir(self.dldir):
            os.makedirs(self.dldir)
        self.sess = requests.Session()
        self.sess.headers.update({
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                           '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'id-ID,id;q=0.9,en;q=0.8',
        })

    # ------------------------------------------------------------------ browser -----------
    def _browser(self):
        if self.page is None:
            from DrissionPage import ChromiumPage, ChromiumOptions
            co = ChromiumOptions()
            co.headless(False)
            co.auto_port(True)          # NOT set_user_data_path() - breaks DrissionPage 4.1.1.4
            self.page = ChromiumPage(co)
            try:
                self.page.set.download_path(self.dldir)
            except Exception:
                pass
        return self.page

    def _browser_html(self, url):
        pg = self._browser()
        pg.get(url)
        for _ in range(20):
            html = pg.html or ''
            if not page_problem(html):
                return html, pg.url
            time.sleep(1)
        return pg.html or '', pg.url

    # ------------------------------------------------------------------ pages -------------
    def html(self, url, tries=3):
        """Fetch a page.  Raises RuntimeError after dumping, if no usable page comes back."""
        hit = cache_get('page', url)
        if hit is not None:
            return hit
        last, landed = '', url
        for attempt in range(tries):
            if self.mode == 'requests':
                try:
                    r = self.sess.get(wb(url), timeout=90, verify=False)
                    status, last, landed = r.status_code, r.text, r.url
                except Exception as exc:
                    status, last, landed = 0, '', url
                    print('    [http] {} attempt {}'.format(type(exc).__name__, attempt + 1))
                if last and not page_problem(last):
                    cache_put('page', url, last, landed)
                    return last, landed
                if status not in self.RETRY_STATUSES and status != 200:
                    print('    [http] status {}'.format(status))
            else:
                try:
                    last, landed = self._browser_html(wb(url))
                    if not page_problem(last):
                        cache_put('page', url, last, landed)
                        return last, landed
                except Exception as exc:
                    print('    [browser] {}'.format(type(exc).__name__))
            if attempt == tries - 2 and self.mode == 'requests':
                print('    [escalate] requests -> browser')
                self.mode = 'browser'
            time.sleep(2 + 3 * attempt)
        dump_fail('page_' + urlparse(url).path.strip('/').replace('/', '_'), last, landed)
        raise RuntimeError('no usable page: {}'.format(slug(url, 120)))

    # ------------------------------------------------------------------ files -------------
    def file_at(self, url, tries=3):
        """GET a file by href (pattern A).  Validated with file_kind()."""
        hit = cache_get('file', url)
        if hit is not None:
            return hit[0]
        last = b''
        for attempt in range(tries):
            try:
                r = self.sess.get(wb(url), timeout=180, verify=False)
                last = r.content
                if file_kind(last):
                    cache_put('file', url, last, url)
                    return last
                print('    [file] status {} len {} not-a-file'.format(r.status_code, len(last)))
            except Exception as exc:
                print('    [file] {} attempt {}'.format(type(exc).__name__, attempt + 1))
            time.sleep(2 + 3 * attempt)
        dump_fail('file_' + os.path.basename(urlparse(url).path), last, url)
        return b''

    def postback(self, page_url, html, extra, tries=3):
        """Replay an ASP.NET WebForms postback with requests: echo every hidden input back,
        then add the control that 'fired'.  Returns (bytes, text, landed_url) - bytes when
        the response is a file, text when it is another page."""
        ckey = postback_key(page_url, extra)
        hit = cache_get('pbfile', ckey)
        if hit is not None:
            return hit[0], '', hit[1]
        hit = cache_get('pbpage', ckey)
        if hit is not None:
            return b'', hit[0], hit[1]

        soup = BeautifulSoup(html, 'html.parser')
        form = soup.find('form', id='aspnetForm') or soup.find('form')
        if form is None:
            raise RuntimeError('no <form> on page {}'.format(slug(page_url, 100)))
        action = urljoin(page_url, form.get('action') or page_url)
        data = {}
        for inp in form.find_all('input'):
            nm = inp.get('name')
            if not nm:
                continue
            if (inp.get('type') or 'text').lower() in ('submit', 'button', 'image',
                                                       'checkbox', 'radio', 'file'):
                continue
            data[nm] = inp.get('value') or ''
        for sel in form.find_all('select'):
            nm = sel.get('name')
            if nm:
                opt = sel.find('option', selected=True) or sel.find('option')
                data[nm] = (opt.get('value') if opt else '') or ''
        data.setdefault('__EVENTTARGET', '')
        data.setdefault('__EVENTARGUMENT', '')
        data.update(extra)

        headers = {'Referer': page_url,
                   'Content-Type': 'application/x-www-form-urlencoded',
                   'Origin': BASE}
        last_txt, landed = '', action
        for attempt in range(tries):
            try:
                r = self.sess.post(wb(action), data=data, headers=headers,
                                   timeout=180, verify=False)
                landed = r.url
                if file_kind(r.content):
                    cache_put('pbfile', ckey, r.content, landed)
                    return r.content, '', landed
                last_txt = r.text
                if not page_problem(last_txt):
                    cache_put('pbpage', ckey, last_txt, landed)
                    return b'', last_txt, landed
                print('    [postback] {}'.format(page_problem(last_txt)))
            except Exception as exc:
                print('    [postback] {} attempt {}'.format(type(exc).__name__, attempt + 1))
            time.sleep(2 + 3 * attempt)
        dump_fail('postback_' + os.path.basename(urlparse(page_url).path), last_txt, landed)
        return b'', '', landed

    def click_download(self, page_url, ctrl_name, tries=2):
        """Browser fallback for a download button: click it and watch the download dir."""
        pg = self._browser()
        for attempt in range(tries):
            try:
                pg.get(wb(page_url))
                before = set(os.listdir(self.dldir))
                ele = pg.ele('@name={}'.format(ctrl_name), timeout=15)
                if not ele:
                    return b''
                ele.click()
                for _ in range(120):
                    time.sleep(1)
                    new = [f for f in os.listdir(self.dldir) if f not in before]
                    done = [f for f in new if not f.endswith(('.crdownload', '.tmp'))]
                    if done:
                        time.sleep(1)
                        path = os.path.join(self.dldir, done[0])
                        blob = io.open(path, 'rb').read()
                        if file_kind(blob):
                            return blob
            except Exception as exc:
                print('    [click] {} attempt {}'.format(type(exc).__name__, attempt + 1))
        return b''


#---- Begin_Function_discovery ----
FILE_EXT_RE = re.compile(r'\.(xlsx|xlsm|xls|pdf)(\?|$)', re.I)


def content_scope(soup):
    """The OJK content <div>.  Falls back to the whole document."""
    cands = soup.find_all('div', class_='content')
    if not cands:
        return soup
    return max(cands, key=lambda d: len(d.find_all('a', href=True)) + 5 * len(d.find_all('table')))


def discover_direct(html, page_url):
    """Pattern A: the landing page holds exactly one link and it IS the workbook.
    The filename is never hard-coded - OJK swaps this single link in place each period."""
    scope = content_scope(BeautifulSoup(html, 'html.parser'))
    out = []
    for a in scope.find_all('a', href=True):
        href = a['href']
        if FILE_EXT_RE.search(href):
            text = clean(a.get_text(' ', strip=True)) or unquote(os.path.basename(urlparse(href).path))
            out.append(dict(text=text, url=urljoin(page_url, href),
                            period=parse_period(text) or parse_period(unquote(href))))
    return out


def discover_articles(html, page_url, keyword=None):
    """Pattern C: the archive index.  Returns every dated article link with its parsed
    period.  Position 0 is NOT reliably the newest - list 9 and list 13 both prove it - so
    the caller takes the max, and the period comes from the link TEXT because the href
    year is sometimes simply wrong (list 13: text 'Januari 2026', href '...-2025.aspx')."""
    soup = BeautifulSoup(html, 'html.parser')
    scope = content_scope(soup)
    ul = scope.find('ul')
    anchors = ul.find_all('a', href=True) if ul else scope.find_all('a', href=True)
    if not anchors:
        anchors = scope.find_all('a', href=True)
    rx = re.compile(keyword, re.I) if keyword else None
    out = []
    for a in anchors:
        href = a['href']
        text = clean(a.get_text(' ', strip=True))
        if not text or href.startswith('#'):
            continue
        if 'javascript:' in href.lower():
            continue
        if not href.lower().endswith('.aspx') and not FILE_EXT_RE.search(href):
            continue
        if rx and not rx.search(text):
            continue
        out.append(dict(text=text, url=urljoin(page_url, href), period=parse_period(text)))
    return out


def discover_folders(html):
    """Pattern D (list 6): the first <ul> is five __doPostBack folder links, no hrefs."""
    soup = BeautifulSoup(html, 'html.parser')
    scope = content_scope(soup)
    ul = scope.find('ul')
    anchors = ul.find_all('a', href=True) if ul else scope.find_all('a', href=True)
    out = []
    for a in anchors:
        m = re.search(r"__doPostBack\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]*)['\"]", a['href'])
        if m:
            out.append(dict(text=clean(a.get_text(' ', strip=True)),
                            target=m.group(1), argument=m.group(2)))
    return out


def newest_year_folder(folders):
    """The one folder to descend into when a folder is filed by year, else None."""
    years = []
    for f in folders:
        m = YEAR_FOLDER_RE.match(f.get('text') or '')
        if not m:
            return None
        years.append((int(m.group(1)), f))
    return max(years, key=lambda t: t[0])[1] if years else None


def pick_latest(items):
    """Max by parsed period.  Items with no period sort last, and index is the tiebreak so
    the site's own order still decides between two files of the same period."""
    if not items:
        return None
    scored = []
    for i, it in enumerate(items):
        p = it.get('period')
        scored.append(((1 if p else 0, p or (0, 0, 0), -i), it))
    scored.sort(key=lambda t: t[0], reverse=True)
    return scored[0][1]


def download_buttons(html):
    """The article page's download controls.  There is NO href - the file is an ASP.NET
    submit input whose @value is the filename and whose @name is the postback target.
    An article may publish several files (list 10 published 3); all of them are taken."""
    soup = BeautifulSoup(html, 'html.parser')
    seen, out = set(), []
    box = soup.find('div', id='div-download-counter')
    scopes = [box] if box else []
    scopes.append(soup)
    for sc in scopes:
        for inp in sc.find_all('input'):
            nm = inp.get('name')
            val = clean(inp.get('value'))
            if not nm or nm in seen:
                continue
            cls = ' '.join(inp.get('class') or [])
            is_dl = ('download-counter' in cls) or (sc is box) or bool(FILE_EXT_RE.search(val))
            if not is_dl:
                continue
            if (inp.get('type') or '').lower() not in ('submit', 'button', ''):
                continue
            seen.add(nm)
            out.append(dict(name=nm, value=val or 'download'))
        if out:
            break
    return out


# The folder tree uses TWO different javascript: wrappers, and they are not interchangeable.
# A folder anchor is a plain  __doPostBack('target','')  - discover_folders handles those.
# A FILE anchor inside a folder is
#   WebForm_DoPostBackWithOptions(new WebForm_PostBackOptions(
#       "ctl00$...$listFolder", "", false, "", "<absolute url of the .xlsx>", false, true))
# discover_folders' regex does not match it (no __doPostBack) and discover_articles rejects it
# (the href is javascript:, not an .aspx), so list 6 read as "no article links" and the whole
# list came out missing.  The 5th positional argument is a plain absolute URL to the file, so
# no third postback is needed - a straight GET is enough.
PB_OPTIONS_RE = re.compile(
    r'WebForm_PostBackOptions\('
    r'\s*"([^"]*)"\s*,'          # 1 target
    r'\s*"([^"]*)"\s*,'          # 2 argument
    r'\s*[^,]*,'                 #   performValidation
    r'\s*"[^"]*"\s*,'            #   validationGroup
    r'\s*"([^"]*)"',             # 3 actionUrl -- the file
    re.I)


def postback_files(html, page_url):
    """File links published straight inside a folder, with no article page in between."""
    soup = BeautifulSoup(html, 'html.parser')
    out = []
    for a in soup.find_all('a', href=True):
        m = PB_OPTIONS_RE.search(a['href'].strip())
        if not m:
            continue
        url = m.group(3).strip()
        if not FILE_EXT_RE.search(url):
            continue
        text = (clean(a.get_text(' ', strip=True)) or
                unquote(os.path.basename(urlparse(url).path)))
        out.append(dict(text=text, url=urljoin(page_url, url),
                        target=m.group(1).strip(), argument=m.group(2).strip(),
                        period=parse_period(text)))
    return out


def direct_files_on_article(html, page_url):
    """Some article pages just link the file.  Cheaper than a postback, so try it first."""
    soup = BeautifulSoup(html, 'html.parser')
    out = []
    for a in soup.find_all('a', href=True):
        if FILE_EXT_RE.search(a['href']):
            out.append(dict(text=clean(a.get_text(' ', strip=True)) or
                            unquote(os.path.basename(urlparse(a['href']).path)),
                            url=urljoin(page_url, a['href'])))
    return out


#---- Begin_Function_parse ----
def field_for_header(label):
    h = norm(label)
    if not h:
        return ''
    for pat, field in HEADER_RULES:
        if re.search(pat, h):
            return field
    return ''


ROWNUM_HEADER_RE = re.compile(HEADER_RULES[0][0])


def map_headers(cells):
    """column index -> schema field.  Label-driven, never positional: v1 broke when OJK
    inserted a column.  First column to claim a field keeps it (so PROVINSI wins over
    WILAYAH KERJA OJK, both of which map to Address_2)."""
    colmap, taken = {}, set()
    for i, c in enumerate(cells):
        f = field_for_header(c)
        if f and f not in taken:
            colmap[i] = f
            taken.add(f)
    # Some sheets title the name column after the entity type instead of 'Nama', and no
    # label rule can enumerate those.  'Bank Kustodian.xlsx' and 'Daftar Wali Amanat.xlsx'
    # are the SAME nine-column sheet - Alamat, Kota, Provinsi, Kode Pos, Telepon,
    # Faksimili, E-mail - and differ only in cell 0, which reads 'Bank Kustodian' on one
    # and 'Nama' on the other.  The first was being thrown away whole.  So when a row is
    # otherwise unmistakably a header (3+ recognised fields) yet claims no Name, the first
    # unclaimed label that is not the row-number column is the name column.  This can only
    # rescue a sheet that find_header_row would have discarded outright.
    if 'Name' not in taken and len(taken) >= 3:
        for i, c in enumerate(cells):
            c = clean(c)
            if i in colmap or not c or ROWNUM_HEADER_RE.search(norm(c)):
                continue
            colmap[i] = 'Name'
            break
    return colmap


def find_header_row(frame, limit=25):
    """Index of the header row, or -1.  A sheet with no recognisable header row is not a
    data sheet - this is what rejects list 3's junk 'Sheet1'/'Sheet2' lookup tables
    without needing a hard-coded sheet allow-list."""
    best, best_n = -1, 0
    for i in range(min(limit, len(frame))):
        cells = [clean(c) for c in frame.iloc[i].tolist()]
        joined = ' '.join(cells)
        if not HEADER_MUST_HAVE.search(joined):
            continue
        cm = map_headers(cells)
        if 'Name' not in cm.values():
            continue
        n = len(set(cm.values()))
        if n > best_n:
            best, best_n = i, n
    return best if best_n >= 2 else -1


def rows_from_frame(frame, hdr, colmap):
    """Data rows below the header.  Section-header rows (a single populated cell outside
    the Name column) are NOT junk: in list 1 they carry the bank category, which becomes
    License_Type for every row beneath them."""
    name_cols = [i for i, f in colmap.items() if f == 'Name']
    name_col = name_cols[0] if name_cols else None
    out, section = [], ''
    for i in range(hdr + 1, len(frame)):
        cells = [clean(c) for c in frame.iloc[i].tolist()]
        filled = [j for j, c in enumerate(cells) if c]
        if not filled:
            continue
        # A revoked-licence section closes the sheet.  Guarded on <=2 populated cells so a
        # company whose name happened to contain the words could never end the parse.
        if len(filled) <= 2 and SECTION_STOP.search(' '.join(cells[j] for j in filled)):
            print('      stop at revoked-licence section, {} rows kept'.format(len(out)))
            break
        # A lone populated cell is a heading, never an entity - an entity always carries at
        # least one more field (licence no., address, category).  This holds wherever the
        # cell sits: list 5's footnote legend ('Masih dalam proses persetujuan pencatatan di
        # OJK', 'Update data') is written INTO the Name column and was being emitted as two
        # companies on each of its two sheets.  Only a heading outside the Name column
        # carries a category forward - list 1's bank groupings.
        if len(filled) == 1:
            if filled[0] != name_col:
                section = cells[filled[0]]
            continue
        rec = {'_section': section}
        for j, f in colmap.items():
            if j < len(cells):
                rec[f] = cells[j]
        if not clean(rec.get('Name', '')):
            continue
        out.append(rec)
    return out


def parse_workbook(blob, label=''):
    """Every sheet of an .xls/.xlsx.  Sheet names are NEVER hard-coded - list 1's sheet was
    'daftar' in 2023 and 'Daftar Bank Umum' later."""
    kind = file_kind(blob)
    if kind not in ('xlsx', 'xls'):
        raise AssertionError('not a workbook: kind={} len={} label={}'.format(
            kind or 'none', len(blob or b''), slug(label)))
    xl = pd.ExcelFile(io.BytesIO(blob))
    recs = []
    for sh in xl.sheet_names:
        try:
            frame = xl.parse(sh, header=None, dtype=object)
        except Exception as exc:
            print('      sheet {} unreadable ({})'.format(slug(sh, 30), type(exc).__name__))
            continue
        if frame.empty:
            continue
        hdr = find_header_row(frame)
        if hdr < 0:
            print('      sheet {} : no header row, skipped'.format(slug(sh, 30)))
            continue
        cm = map_headers([clean(c) for c in frame.iloc[hdr].tolist()])
        got = rows_from_frame(frame, hdr, cm)
        # merged "category" cells are common in OJK directories; a no-op when not merged
        last = ''
        for r in got:
            if r.get('License_Type'):
                last = r['License_Type']
            elif last:
                r['License_Type'] = last
            r['_sheet'] = clean(sh)
        print('      sheet {} : {} rows'.format(slug(sh, 30), len(got)))
        recs.extend(got)
    return recs


def merge_split_columns(frame):
    """Fold pdfplumber's phantom columns together.

    pdfplumber derives one column grid per table from every x-boundary it finds, so a
    CENTRED header label and its LEFT-ALIGNED data can land in two different columns of that
    grid.  List 11 came out 21 columns wide with the seven labels at 1, 4, 7, 10, 13, 16, 19
    and the seven data fields at 0, 3, 6, 9, 12, 15, 18 - consistently one column apart.
    map_headers keyed the colmap off the label positions, every lookup hit an empty cell,
    every row lost its Name, and the list emitted 0 rows while looking perfectly healthy.

    Two adjacent columns that never both carry a value in the same row cannot be two real
    columns, so they are folded into one.  A genuine pair (however sparse) collides on at
    least one row and is left alone."""
    cols = list(frame.columns)
    if len(cols) < 2:
        return frame
    groups = [[cols[0]]]
    for c in cols[1:]:
        cur = groups[-1]
        clash = any(
            any(clean(frame.iloc[i][g]) for g in cur) and clean(frame.iloc[i][c])
            for i in range(len(frame)))
        (groups.append([c]) if clash else cur.append(c))
    if len(groups) == len(cols):
        return frame
    data = []
    for i in range(len(frame)):
        row = []
        for g in groups:
            vals = [v for v in (clean(frame.iloc[i][c]) for c in g) if v]
            row.append(vals[0] if vals else '')
        data.append(row)
    return pd.DataFrame(data)


def parse_pdf(blob, label=''):
    """Table extraction from a PDF (list 13)."""
    kind = file_kind(blob)
    if kind != 'pdf':
        raise AssertionError('not a pdf: kind={} len={} label={}'.format(
            kind or 'none', len(blob or b''), slug(label)))
    import pdfplumber
    recs = []
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        colmap, section = None, ''
        for page in pdf.pages:
            for tbl in (page.extract_tables() or []):
                frame = pd.DataFrame(tbl)
                if frame.empty:
                    continue
                frame = merge_split_columns(frame)
                hdr = find_header_row(frame, limit=4)
                if hdr >= 0:
                    colmap = map_headers([clean(c) for c in frame.iloc[hdr].tolist()])
                    got = rows_from_frame(frame, hdr, colmap)
                elif colmap:
                    got = rows_from_frame(frame, -1, colmap)   # continuation page
                else:
                    continue
                for r in got:
                    r['_sheet'] = 'pdf'
                recs.extend(got)
        if not recs:
            recs = poster_rows(pdf)
    print('      pdf : {} rows'.format(len(recs)))
    return recs


# 'S-14/D.07/2025 (1 Februari 2025)' / 'KEP-17/D.07/2026 (25 Mei 2026)'
DECREE_RE = re.compile(r'^((?:S|KEP)-\d+/[A-Za-z0-9.]+/\d{4})\s*\(([^)]*)\)\s*$')


def poster_lines(page, tol=3.0, gutter=18.0):
    """The page's words regrouped into (column, top, text) lines.

    Reading order matters and extract_text() gets it wrong here: it walks the page by y, so
    it interleaves the two poster columns and welds the left entity's name onto the right
    entity's licence line.

    A line is only cut in two where the words actually leave a gutter across the page
    middle.  Cutting on the mid-line itself is what a first attempt did, and it destroyed
    every CENTRED line - the category heading 'Pedagang Aset Keuangan Digital' came out as
    'Pedagang Aset' + 'Keuangan Digital', and pages 4-6, which are laid out as one centred
    column, lost all their entities because each name was filed under a different column
    from its own decree line."""
    mid = page.width / 2.0
    rows = {}
    for w in page.extract_words() or []:
        rows.setdefault(round(w['top'] / tol), []).append(w)
    lines = []
    for _, ws in rows.items():
        ws.sort(key=lambda w: w['x0'])
        cut, widest = None, gutter
        for i in range(1, len(ws)):
            gap = ws[i]['x0'] - ws[i - 1]['x1']
            if gap >= widest and ws[i - 1]['x1'] <= mid <= ws[i]['x0']:
                cut, widest = i, gap
        if cut is not None:                       # both columns wrote on this line
            parts = [(0, ws[:cut]), (1, ws[cut:])]
        elif ws[0]['x0'] >= mid:                  # right column only
            parts = [(1, ws)]
        else:                                     # left column only, or centred full width
            parts = [(0, ws)]                     # headings and pages 4-6 land here
        for col, part in parts:
            if part:
                lines.append((col, min(w['top'] for w in part),
                              clean(' '.join(w['text'] for w in part))))
    lines.sort(key=lambda t: (t[0], t[1]))
    return lines


def poster_rows(pdf):
    """List 13's fallback parser.

    'Daftar Penyelenggara Perdagangan Aset Keuangan Digital' is published as a designed
    poster, not a table: 6 pages, six images each, zero ruling lines, the entities laid out
    in two free-text columns.  extract_tables() returns only decoration, so the generic path
    emitted 0 rows and the list read as 'missing'.

    An entity is a run of lines opening with 'PT ' and closed by its decree line; the caps
    lines are the repeated poster title, and the remaining Title Case line is the category."""
    recs, section = [], ''
    for page in pdf.pages:
        pending, head = [], []
        for _col, _top, text in poster_lines(page):
            if not text:
                continue
            m = DECREE_RE.match(text)
            if m:
                name = clean(' '.join(pending))
                pending = []
                if not name.startswith('PT'):
                    continue
                recs.append({'_sheet': 'pdf', '_section': section, 'Name': name,
                             'License_Type': section, 'InternalID_2': clean(m.group(1)),
                             'RegulationDate': clean(m.group(2))})
                continue
            if text.startswith('PT '):
                pending, head = [text], []
                continue
            if pending:
                pending.append(text)
                continue
            if text.upper() == text:            # the repeated all-caps poster title
                continue
            # A category heading, which wraps over two lines on pages 5 and 6 ('Lembaga
            # Kliring Penjaminan dan Penyelesaian' / 'Perdagangan Aset Keuangan Digital').
            # Consecutive heading lines accumulate; the next 'PT ' closes the heading.
            head.append(text)
            section = re.sub(r'\s*\(\d+\)\s*$', '', ' '.join(head))  # drop ' (2)' counter
    return recs


FAX_SPLIT = re.compile(r'\b(?:fax|faks|faksimili?|facsimile)\b\s*[:.\-]?\s*', re.I)


def split_phone_fax(v):
    s = clean(v)
    if not s:
        return '', ''
    parts = FAX_SPLIT.split(s)
    if len(parts) > 1:
        phone = clean(parts[0].rstrip(' ;,/'))
        fax = clean(' '.join(parts[1:]))
        return phone, fax
    return s, ''


def parse_list2_table(html):
    """Pattern B (list 2): the only list with no download.  4 columns
    No. | Nama | Alamat | Telepon, with single-cell COUNTRY group headers between blocks
    and U+200B zero-width spaces sprinkled through every cell."""
    soup = BeautifulSoup(html, 'html.parser')
    scope = content_scope(soup)
    table = scope.find('table')
    if table is None:
        raise AssertionError('list 2: no <table> in content div')
    recs, country, colmap = [], '', None
    for tr in table.find_all('tr'):
        cells = [clean(td.get_text(' ', strip=True)) for td in tr.find_all(['td', 'th'])]
        if not cells:
            continue
        filled = [c for c in cells if c]
        if not filled:
            continue
        if len(filled) == 1 and len(cells) <= 2:
            country = filled[0]
            continue
        if colmap is None:
            cm = map_headers(cells)
            if 'Name' in cm.values():
                colmap = cm
                continue
        if len(filled) == 1:            # a lone country header inside a full-width row
            country = filled[0]
            continue
        cm = colmap or {0: '', 1: 'Name', 2: 'Address_1', 3: 'Phone'}
        rec = {}
        for j, f in cm.items():
            if f and j < len(cells):
                rec[f] = cells[j]
        if not clean(rec.get('Name', '')):
            continue
        rec['Phone'], rec['Fax'] = split_phone_fax(rec.get('Phone', ''))
        rec['_country'] = country
        recs.append(rec)
    return recs


#---- Begin_Function_emit ----
BAD_NAME_WORDS = set(['yes', 'no', 'ya', 'tidak', 'none', 'nan', 'nat', 'null', 'total',
                      'jumlah', 'keterangan', 'nama', 'no', 'nomor', 'alamat', 'telepon',
                      'kosong', 'n a', 'lain lain', 'jumlah total'])


def name_problem(name):
    """'' when Name is a plausible entity name, else an ASCII reason.

    Row counts alone do NOT validate an extraction - a sibling regulator once reconciled
    997/997 rows with Name full of 'Yes'/'No'.  This is the content test, and it is applied
    twice: as a skip filter at emit time and as a hard assert over the finished DataFrame.
    """
    s = clean(name)
    if not s:
        return 'empty'
    if len(s) < 3:
        return 'too-short'
    if re.match(r'^[\d\s.,/\-]+$', s):
        return 'no-letters'
    if re.match(r'^\d+([.,]\d+)?$', s):
        return 'bare-number'
    if re.match(r'^\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}$', s) or re.match(r'^\d{4}-\d{2}-\d{2}', s):
        return 'looks-like-date'
    if re.match(r'^\d+(\.\d+)?[eE][+-]?\d+$', s):
        return 'float-notation'
    if norm(s) in BAD_NAME_WORDS:
        return 'boilerplate'
    return ''


def compact_ids(rec):
    """Collapse whatever IDs the file happened to carry into slots 1..3, in order of
    usefulness, each with its own _type label."""
    cands = []
    if clean(rec.get('InternalID_1', '')):
        cands.append((clean(rec['InternalID_1']), 'Sandi Bank (OJK bank code)'))
    if clean(rec.get('InternalID_2', '')):
        cands.append((clean(rec['InternalID_2']), 'OJK Licence / Decree Number'))
    if clean(rec.get('InternalID_3', '')):
        cands.append((clean(rec['InternalID_3']), 'NPWP (Tax ID)'))
    out = {}
    for i, (val, typ) in enumerate(cands[:3]):
        out['InternalID_%d' % (i + 1)] = val
        out['InternalID_%d_type' % (i + 1)] = typ
    return out


STATS = {}


def bump(key, n=1):
    STATS[key] = STATS.get(key, 0) + n


def emit(rec, cfg, validity, license_extra='', cotype_extra=''):
    """One source record -> one sqldict row.  Returns True if written."""
    name = clean(rec.get('Name', ''))
    why = name_problem(name)
    if why:
        bump('skip_' + why)
        return False

    phone = clean(rec.get('Phone', ''))
    fax = clean(rec.get('Fax', ''))
    if phone and not fax:
        phone, fax = split_phone_fax(phone)
    fax = re.sub(r'^(fax|faks|faksimili?)\s*[:.\-]?\s*', '', fax, flags=re.I).strip()

    lic = clean(rec.get('License_Type', '')) or clean(rec.get('_section', '')) or license_extra
    cot = cfg['cotype'] + (' - ' + cotype_extra if cotype_extra else '')

    row = dict(
        ListLabel=cfg['label'],
        Name=name,
        CoType=cot,
        License_Type=lic,
        Address_1=clean(rec.get('Address_1', '')),
        Address_2=clean(rec.get('Address_2', '')),
        City=clean(rec.get('City', '')),
        Zip=clean(rec.get('Zip', '')),
        Cntry=CNTRY,
        Phone=phone,
        Fax=fax,
        Website=clean(rec.get('Website', '')),
        Email=clean(rec.get('Email', '')),
        RegulationType=REGULATION_TYPE,
        RegulationDate=to_iso_date(rec.get('RegulationDate', '')),
        CancellationDate=to_iso_date(rec.get('CancellationDate', '')),
        RegCtry=REGCTRY,
        RegCode=REGCODE,
        ListCode=str(cfg['nr']),
        ListLanguage=LIST_LANGUAGE,
        ListValidityDate=validity,
        ListName=cfg['name'],
        ListProcessDate=processdate,
    )
    row.update(compact_ids(rec))
    if rec.get('_country'):
        row['Cntry - Mother company'] = COUNTRY_ID.get(norm(rec['_country']), '')
    add_row(**row)
    bump('list_%02d' % cfg['nr'])
    return True


#---- Begin_Function_lists ----
class ListFailure(Exception):
    """A list could not be resolved or parsed.  Carries enough ASCII detail to diagnose a
    failure on a machine nobody is watching."""
    pass


FAILURES = []


def _fetch_file_for(tr, article_url, article_html, btn, tag):
    """Get one file off an article page.  requests postback first, browser click second.
    Both paths are accepted by the SAME test - file_kind() - so a WAF page can never be
    mistaken for 'nearly a file'."""
    blob, txt, landed = tr.postback(article_url, article_html, {btn['name']: btn['value']})
    if file_kind(blob):
        return blob
    print('    [postback gave no file] trying browser click')
    blob = tr.click_download(article_url, btn['name'])
    if file_kind(blob):
        return blob
    dump_fail('nofile_' + tag, txt or b'', landed or article_url)
    return b''


def parse_blob(blob, label):
    kind = file_kind(blob)
    if kind == 'pdf':
        return parse_pdf(blob, label)
    return parse_workbook(blob, label)


def handle_article_page(tr, cfg, art, subcat=''):
    """Article page -> every file it publishes -> records."""
    html, landed = tr.html(art['url'])
    problem = page_problem(html)
    if problem:
        raise ListFailure('list {} article page unusable ({}) url={} bytes={}'.format(
            cfg['nr'], problem, slug(art['url'], 120), len(html or '')))

    validity = period_iso(art.get('period'))
    recs = []

    for a in direct_files_on_article(html, landed):
        blob = tr.file_at(a['url'])
        if file_kind(blob):
            recs.extend(parse_blob(blob, a['text']))

    if not recs:
        btns = download_buttons(html)
        if not btns:
            dump_fail('nobutton_list{}'.format(cfg['nr']), html, landed)
            raise ListFailure(
                'list {} : no download control found on article page. url={} bytes={}'.format(
                    cfg['nr'], slug(art['url'], 120), len(html or '')))
        print('    {} download button(s)'.format(len(btns)))
        for b in btns:
            tag = 'list{}_{}'.format(cfg['nr'], re.sub(r'[^A-Za-z0-9]+', '_', slug(b['value'], 40)))
            blob = _fetch_file_for(tr, landed, html, b, tag)
            if not file_kind(blob):
                print('    [no file] {}'.format(slug(b['value'], 50)))
                continue
            recs.extend(parse_blob(blob, b['value']))

    for r in recs:
        r.setdefault('_subcat', subcat)
    return recs, validity


def do_list(tr, cfg):
    """Resolve and parse one list.  Never returns silently with zero rows."""
    nr = cfg['nr']
    print('  [list {:02d}] {}'.format(nr, slug(cfg['name'], 70)))
    html, landed = tr.html(cfg['url'])
    problem = page_problem(html)
    if problem:
        raise ListFailure('list {} landing page unusable ({}) url={} bytes={}'.format(
            nr, problem, slug(cfg['url'], 120), len(html or '')))

    written = 0

    if cfg['kind'] == 'table':
        recs = parse_list2_table(html)
        if not recs:
            dump_fail('list{}_table'.format(nr), html, landed)
            raise ListFailure('list {} : inline table parsed 0 rows. url={} bytes={}'.format(
                nr, slug(cfg['url'], 120), len(html or '')))
        validity = ''
        for r in recs:
            written += 1 if emit(r, cfg, validity) else 0

    elif cfg['kind'] == 'direct':
        files = discover_direct(html, landed)
        if not files:
            dump_fail('list{}_nolink'.format(nr), html, landed)
            raise ListFailure(
                'list {} : no .xls/.xlsx link on landing page. url={} bytes={}'.format(
                    nr, slug(cfg['url'], 120), len(html or '')))
        target = pick_latest(files)
        print('    file: {}'.format(slug(target['text'], 70)))
        blob = tr.file_at(target['url'])
        if not file_kind(blob):
            raise ListFailure('list {} : download is not a workbook. url={} bytes={}'.format(
                nr, slug(target['url'], 120), len(blob or b'')))
        validity = period_iso(target.get('period'))
        for r in parse_blob(blob, target['text']):
            written += 1 if emit(r, cfg, validity) else 0

    elif cfg['kind'] == 'article':
        arts = discover_articles(html, landed, cfg.get('keyword'))
        if not arts:
            dump_fail('list{}_noarticle'.format(nr), html, landed)
            raise ListFailure(
                'list {} : no dated article links found{}. url={} bytes={}'.format(
                    nr, ' matching keyword' if cfg.get('keyword') else '',
                    slug(cfg['url'], 120), len(html or '')))
        art = pick_latest(arts)
        print('    latest of {}: {} -> {}'.format(
            len(arts), slug(art['text'], 60), period_iso(art.get('period')) or 'no-period'))
        recs, validity = handle_article_page(tr, cfg, art)
        for r in recs:
            written += 1 if emit(r, cfg, validity) else 0

    elif cfg['kind'] == 'folders':
        folders = discover_folders(html)
        if not folders:
            dump_fail('list{}_nofolder'.format(nr), html, landed)
            raise ListFailure(
                'list {} : no __doPostBack folder links found. url={} bytes={}'.format(
                    nr, slug(cfg['url'], 120), len(html or '')))
        print('    {} sub-categories'.format(len(folders)))
        sub_ok, leaves = 0, 0
        # A folder is not always one postback away from its articles.  'Pelaku Perorangan
        # Pasar Modal' holds four more folders and NO articles of its own, so a single-level
        # descent found nothing there and the whole list read as missing.  Queue of
        # (label, folder, parent html, parent landed url, depth).
        queue = [(fo['text'], fo, html, landed, 1) for fo in folders]
        while queue:
            label, fo, par_html, par_landed, depth = queue.pop(0)
            tag = re.sub(r'[^A-Za-z0-9]+', '_', slug(label, 40))
            pad = '  ' * (depth - 1)
            print('    {}- {}'.format(pad, slug(label, 60)))
            if FOLDER_SKIP.search(fo['text']):
                print('    {}  skipped, out of scope (DECD-6836)'.format(pad))
                continue
            _b, sub_html, sub_landed = tr.postback(
                par_landed, par_html,
                {'__EVENTTARGET': fo['target'], '__EVENTARGUMENT': fo['argument']})
            if not sub_html or page_problem(sub_html):
                dump_fail('list6_folder_' + tag, sub_html or '', sub_landed)
                print('    {}  [FAILED] sub-category page unusable'.format(pad))
                continue
            # Three shapes can sit under a folder, tried cheapest first: the file itself,
            # an article page that then publishes the file, or yet another folder.
            files = postback_files(sub_html, sub_landed or par_landed)
            arts = [] if files else discover_articles(sub_html, sub_landed or par_landed)
            if not files and not arts:
                nested = discover_folders(sub_html)
                newest = newest_year_folder(nested) if nested else None
                if newest is not None:
                    # A vintage, not a category, so the year does not join the label - it
                    # would otherwise land in CoType and split one profession into eight.
                    print('    {}  filed by year ({}), taking {}'.format(
                        pad, len(nested), newest['text']))
                    queue.append((label, newest, sub_html, sub_landed or par_landed,
                                  depth + 1))
                    continue
                if nested and depth < FOLDER_MAX_DEPTH:
                    print('    {}  {} nested folders'.format(pad, len(nested)))
                    for nf in nested:
                        queue.append((label + ' / ' + nf['text'], nf,
                                      sub_html, sub_landed or par_landed, depth + 1))
                    continue
                scope_text = content_scope(
                    BeautifulSoup(sub_html, 'html.parser')).get_text(' ', strip=True)
                if EMPTY_FOLDER_RE.search(scope_text):
                    print('    {}  empty on the site, nothing published'.format(pad))
                    continue
                dump_fail('list6_noart_' + tag, sub_html, sub_landed)
                print('    {}  [FAILED] no article links in sub-category'.format(pad))
                continue
            leaves += 1
            if files:
                f = pick_latest(files)
                print('    {}  latest of {} file(s): {}'.format(
                    pad, len(files), slug(f['text'], 55)))
                blob = tr.file_at(f['url'])
                if not file_kind(blob):
                    dump_fail('list6_nofile_' + tag, sub_html, f['url'])
                    print('    {}  [FAILED] {} is not a workbook/pdf ({} bytes)'.format(
                        pad, slug(f['text'], 40), len(blob or b'')))
                    continue
                recs = parse_blob(blob, f['text'])
                validity = period_iso(f.get('period'))
                for r in recs:
                    r.setdefault('_subcat', label)
            else:
                art = pick_latest(arts)
                print('    {}  latest of {}: {}'.format(pad, len(arts), slug(art['text'], 55)))
                try:
                    recs, validity = handle_article_page(tr, cfg, art, subcat=label)
                except ListFailure as exc:
                    print('    {}  [FAILED] {}'.format(pad, slug(str(exc), 140)))
                    continue
            n = 0
            for r in recs:
                n += 1 if emit(r, cfg, validity, cotype_extra=label) else 0
            print('    {}  {} rows'.format(pad, n))
            written += n
            sub_ok += 1 if n else 0
        if not sub_ok:
            raise ListFailure(
                'list 6 : {} sub-categories, {} reached a file, none yielded rows. '
                'url={}'.format(len(folders), leaves, slug(cfg['url'], 120)))

    else:
        raise ListFailure('list {} : unknown kind {}'.format(nr, cfg['kind']))

    if written == 0:
        raise ListFailure('list {} : resolved its source but emitted 0 rows - the parser '
                          'found no usable Name column. url={}'.format(nr, slug(cfg['url'], 120)))
    print('    => {} rows'.format(written))
    return written


#---- Begin_MainLoop ----
def main(only=None):
    tr = Transport()
    counts = {}
    for cfg in LISTS:
        if only and cfg['nr'] not in only:
            continue
        try:
            counts[cfg['nr']] = do_list(tr, cfg)
        except ListFailure as exc:
            FAILURES.append((cfg['nr'], slug(str(exc), 300)))
            print('  [LIST {:02d} FAILED] {}'.format(cfg['nr'], slug(str(exc), 250)))
        except Exception as exc:
            FAILURES.append((cfg['nr'], '{}: {}'.format(type(exc).__name__, slug(str(exc), 250))))
            print('  [LIST {:02d} ERROR] {}: {}'.format(cfg['nr'], type(exc).__name__,
                                                        slug(str(exc), 220)))
    try:
        if tr.page is not None:
            tr.page.quit()
    except Exception:
        pass
    return counts


#---- Begin_QA ----
def qa_dataframe(df):
    """Content validation.  Row counts alone prove nothing - these test what is IN the
    cells.  Every one of these assertions is designed to be able to FAIL; see the
    self-test at the bottom of this file, which feeds each of them known-bad input."""
    assert list(df.columns) == SCHEMA_KEYS, 'column order drifted from the 43-key schema'
    assert len(df) > 0, 'no rows at all'

    bad = []
    for i, nm in enumerate(df['Name'].tolist()):
        why = name_problem(nm)
        if why:
            bad.append((i, why, slug(nm, 40)))
    assert not bad, 'Name column holds {} unusable value(s), e.g. {}'.format(
        len(bad), bad[:5])

    moj = [slug(v, 40) for v in df['Name'].tolist() if is_mojibake(v)]
    assert not moj, 'mojibake in Name: {}'.format(moj[:5])

    for col, want in (('RegCtry', REGCTRY), ('RegCode', REGCODE), ('Cntry', CNTRY),
                      ('RegulationType', REGULATION_TYPE), ('ListProcessDate', processdate),
                      ('ListLanguage', LIST_LANGUAGE)):
        vals = set(df[col].unique().tolist())
        assert vals == set([want]), '{} should be only {!r}, got {}'.format(
            col, want, sorted(vals)[:5])

    labels = set(df['ListLabel'].unique().tolist())
    assert labels <= set(['1', '2', '3', '4']), 'bad ListLabel values: {}'.format(sorted(labels))

    codes = set(df['ListCode'].unique().tolist())
    assert all(re.match(r'^\d{1,2}$', c) for c in codes), 'ListCode must stay a digit string'

    for c in ('ListName', 'CoType'):
        assert not (df[c] == '').any(), '{} is empty on some rows'.format(c)


def digit_fingerprint(df):
    """Which TEXT_COLS cells are digit strings, and what they are.  Compared before and
    after the Excel round-trip: 40003764029 must not come back as 4.000376e+10, and
    '0271' must not come back as '271'."""
    fp = {}
    for c in TEXT_COLS:
        fp[c] = dict((i, v) for i, v in enumerate(df[c].tolist())
                     if isinstance(v, str) and re.match(r'^\d+$', v))
    return fp


def write_output(df):
    for c in TEXT_COLS:
        df[c] = df[c].astype(str).replace('nan', '').replace('None', '')
    before = digit_fingerprint(df)

    out = os.path.join(scriptfolder, filename)          # NOT tempfolder
    df.to_excel(out, sheet_name='SQL Ready', index=False)
    print('Saved {} rows to {}'.format(len(df), slug(out, 160)))

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
DO_RUN = (__name__ == '__main__'
          and os.environ.get('OJK_NO_RUN', '') != '1'
          and os.environ.get('OJK_SELFTEST', '') != '1')

if DO_RUN:
    print('ID OJK / DECD-6836  process date {}'.format(processdate))
    counts = main()

    print('')
    print('--- per-list rows ---')
    for cfg in LISTS:
        print('  list {:02d} : {}'.format(cfg['nr'], counts.get(cfg['nr'], 0)))
    for k in sorted(STATS):
        if k.startswith('skip_'):
            print('  {} : {}'.format(k, STATS[k]))

    df = pd.DataFrame(sqldict)
    df = df[df['Name'] != '']
    df = df.reset_index(drop=True)
    qa_dataframe(df)
    write_output(df)

    if FAILURES:
        print('')
        print('!!! {} of {} lists FAILED - see tempfolder dumps !!!'.format(
            len(FAILURES), len(LISTS)))
        for nr, msg in FAILURES:
            print('  list {:02d}: {}'.format(nr, msg))
        sys.exit(2)


#---- Begin_SelfTest ----
# Runs with:  OJK_SELFTEST=1 python ID_OJK_v2.py
# Drives every parser over saved fixtures in tempfolder/fixtures/ (Wayback HTML + three real
# OJK workbooks) and, crucially, feeds each content assertion KNOWN-BAD input to prove it can
# actually fail.  An assertion that cannot fail manufactures false confidence.
# No network is used, so this is runnable on a machine that cannot reach ojk.go.id.
FIXDIR = os.path.join(tempfolder, 'fixtures')


def _fx(name):
    return io.open(os.path.join(FIXDIR, name), encoding='utf-8', errors='replace').read()


def _fxb(name):
    return io.open(os.path.join(FIXDIR, name), 'rb').read()


def selftest():
    ok, fail = [], []

    def check(label, cond, detail=''):
        (ok if cond else fail).append(label)
        print('  {} {} {}'.format('PASS' if cond else 'FAIL', label, detail))

    print('== schema ==')
    check('43 keys', len(SCHEMA_KEYS) == 43, str(len(SCHEMA_KEYS)))
    check('key order', SCHEMA_KEYS[0] == 'bvdid' and SCHEMA_KEYS[-1] == 'Phone - Mother company')
    try:
        add_row(NotAField='x')
        check('add_row rejects unknown key', False, 'it did NOT raise')
    except KeyError:
        check('add_row rejects unknown key', True)
    n0 = len(sqldict['Name'])
    add_row(Name='PT SELFTEST', RegCtry=REGCTRY)
    check('add_row fills all 43', set(len(v) for v in sqldict.values()) == set([n0 + 1]))
    for k in SCHEMA_KEYS:
        sqldict[k].pop()

    print('== period parsing ==')
    cases = [('Direktori Asuransi Triwulan III 2025', (2025, 9, 30)),
             ('Direktori Asuransi Triwulan II Tahun 2024', (2024, 6, 30)),
             ('Direktori Dana Pensiun Desember 2025', (2025, 12, 31)),
             ('Daftar ... Posisi 21 April 2026', (2026, 4, 21)),
             ('Data Perusahaan Efek - Februari 2026', (2026, 2, 28)),
             ('Daftar Alamat Kantor Pusat BPR - Desember 2025.xlsx', (2025, 12, 31))]
    for txt, want in cases:
        check('period ' + slug(txt, 44), parse_period(txt) == want, str(parse_period(txt)))
    check('newest wins over position 0',
          pick_latest([dict(text='November 2024', period=parse_period('November 2024')),
                       dict(text='Januari 2025', period=parse_period('Januari 2025'))
                       ])['text'] == 'Januari 2025')

    print('== discovery over fixtures ==')
    for nm, nr in (('list01.html', 1), ('list03.html', 3), ('list04.html', 4)):
        got = discover_direct(_fx(nm), BASE + '/x/y.aspx')
        check('list %d direct link' % nr, len(got) == 1 and got[0]['period'] is not None,
              slug(got[0]['text'], 55) if got else 'none')
    for nm, nr, want_min in (('list05.html', 5, 10), ('list07.html', 7, 10),
                             ('list08.html', 8, 10), ('list09.html', 9, 10),
                             ('list11.html', 11, 10), ('list12.html', 12, 10)):
        arts = discover_articles(_fx(nm), BASE + '/x/y.aspx')
        best = pick_latest(arts)
        check('list %d articles' % nr, len(arts) >= want_min and best and best['period'],
              '{} links, latest {} = {}'.format(len(arts), slug(best['text'], 42) if best else '-',
                                                period_iso(best['period']) if best else '-'))
    arts13 = discover_articles(_fx('list13.html'), BASE + '/x/y.aspx',
                               LISTS[12].get('keyword'))
    best13 = pick_latest(arts13)
    check('list 13 keyword filter drops ITSK + the criteria PDF',
          bool(best13) and 'ITSK' not in best13['text'] and '.pdf' not in best13['text'].lower(),
          '{} kept, latest {}'.format(len(arts13), slug(best13['text'], 50) if best13 else '-'))
    unfiltered = discover_articles(_fx('list13.html'), BASE + '/x/y.aspx')
    check('list 13 filter is not a no-op', len(unfiltered) > len(arts13),
          '{} unfiltered vs {} filtered'.format(len(unfiltered), len(arts13)))
    folders = discover_folders(_fx('list06.html'))
    check('list 6 sub-categories', len(folders) == 5,
          ' | '.join(slug(f['text'], 26) for f in folders))
    for nm in ('art07.html', 'art10.html'):
        btns = download_buttons(_fx(nm))
        check('%s download buttons' % nm, len(btns) >= 1,
              ' | '.join(slug(b['value'], 40) for b in btns))

    print('== workbook parsing (real OJK files) ==')
    r1 = parse_workbook(_fxb('list01_bankumum_Feb2023.xlsx'), 'list1')
    # 106, not the 111 this asserted before 2026-09-03.  The sheet's own numbering runs to
    # 106 data rows; the extra five were the footnotes at the bottom of the file - lines
    # like '*) PT Bank Harda Internasional Tbk berubah nama menjadi ...' - which sit alone
    # IN the Name column and were being emitted as banks.  name_problem() cannot catch them:
    # they are long, full of letters and contain real bank names.  Dropping every lone
    # populated cell, wherever it sits, is what removes them.
    check('list 1 rows', len(r1) == 106, str(len(r1)))
    check('list 1 last row is a bank, not a footnote',
          bool(r1) and not r1[-1]['Name'].startswith(('*', ')')), slug(r1[-1]['Name'], 45))
    check('list 1 section -> License_Type',
          bool(r1) and r1[0].get('_section') == 'BANK UMUM PERSERO', slug(r1[0].get('_section', '')))
    check('list 1 fields', bool(r1) and all(r1[0].get(f) for f in
                                            ('Name', 'Address_1', 'Phone', 'Fax', 'Website')))
    r3 = parse_workbook(_fxb('list03_bpr_Des2024.xlsx'), 'list3')
    check('list 3 rows', len(r3) == 1356, str(len(r3)))
    check('list 3 junk sheets rejected by header detection', len(r3) < 1400)
    check('list 3 SANDI -> InternalID_1', bool(r3) and r3[0].get('InternalID_1') == '600001',
          str(r3[0].get('InternalID_1')))
    check('list 3 City/Address_2', bool(r3) and r3[0].get('City') == 'KOTA SURABAYA'
          and r3[0].get('Address_2', '').startswith('PROVINSI'))
    r4 = parse_workbook(_fxb('list04_bprs_Jun2025.xlsx'), 'list4')
    check('list 4 rows', len(r4) == 173, str(len(r4)))

    print('== list 2 inline table ==')
    r2 = parse_list2_table(_fx('list02.html'))
    check('list 2 rows', len(r2) >= 20, str(len(r2)))
    check('list 2 zero-width stripped', all(u'​' not in r.get('Name', '') for r in r2))
    check('list 2 country captured', all(r.get('_country') for r in r2),
          slug(r2[0].get('_country', '')) if r2 else '')
    check('list 2 country maps to ISO2',
          all(COUNTRY_ID.get(norm(r['_country'])) for r in r2),
          ','.join(sorted(set(COUNTRY_ID.get(norm(r['_country']), '?' + slug(r['_country'], 12))
                              for r in r2))))
    fax_rows = [r for r in r2 if r.get('Fax')]
    check('list 2 fax split out of Telepon', len(fax_rows) >= 2,
          '{} rows carry a fax'.format(len(fax_rows)))

    print('== content assertions FIRE on known-bad input (anti-vacuity) ==')
    for bad, why in [('', 'empty'), ('12', 'too-short'), ('123456', 'no-letters'),
                     ('4.000376e+10', 'float-notation'), ('12/03/2024', 'looks-like-date'),
                     ('Yes', 'boilerplate'), ('Nama', 'boilerplate')]:
        got = name_problem(bad)
        check('name_problem(%r) fires' % slug(bad, 16), got != '', 'reason=' + (got or 'NONE'))
    check('name_problem accepts a real name',
          name_problem('PT BANK RAKYAT INDONESIA (PERSERO) Tbk') == '')

    good = pd.DataFrame(dict((k, ['']) for k in SCHEMA_KEYS))
    good['Name'] = ['PT BANK TEST']
    good['RegCtry'] = [REGCTRY]; good['RegCode'] = [REGCODE]; good['Cntry'] = [CNTRY]
    good['RegulationType'] = [REGULATION_TYPE]; good['ListProcessDate'] = [processdate]
    good['ListLanguage'] = [LIST_LANGUAGE]; good['ListLabel'] = ['1']; good['ListCode'] = ['1']
    good['ListName'] = ['x']; good['CoType'] = ['y']
    good = good[SCHEMA_KEYS]
    try:
        qa_dataframe(good)
        check('qa_dataframe passes clean data', True)
    except AssertionError as exc:
        check('qa_dataframe passes clean data', False, slug(str(exc), 90))

    for mutate, label in [
            (lambda d: d.assign(Name=['Yes']), 'Name=Yes'),
            (lambda d: d.assign(Name=['4.000376e+10']), 'Name=float'),
            (lambda d: d.assign(Name=['2024-01-01']), 'Name=date'),
            (lambda d: d.assign(RegCode=['WRONG']), 'RegCode wrong'),
            (lambda d: d.assign(ListLabel=['9']), 'ListLabel=9'),
            (lambda d: d.assign(CoType=['']), 'CoType empty'),
            (lambda d: d.assign(Name=[u'PT BANK Ã©TEST']), 'mojibake')]:
        try:
            qa_dataframe(mutate(good.copy()))
            check('qa_dataframe rejects ' + label, False, 'it did NOT raise')
        except AssertionError:
            check('qa_dataframe rejects ' + label, True)

    print('== Excel text round-trip fires on real coercion risk ==')
    rt = good.copy()
    rt['InternalID_1'] = ['40003764029']; rt['Zip'] = ['02710']; rt['Phone'] = ['0215245006']
    saved_name = filename
    try:
        globals()['filename'] = 'SELFTEST_roundtrip.xlsx'
        path = write_output(rt.copy())
        back = pd.read_excel(path, dtype=str).fillna('')
        check('IDs survive Excel as digit strings',
              back['InternalID_1'][0] == '40003764029' and back['Zip'][0] == '02710'
              and back['Phone'][0] == '0215245006',
              '{} / {} / {}'.format(back['InternalID_1'][0], back['Zip'][0], back['Phone'][0]))
        os.remove(path)
        # Prove the round-trip check is NOT vacuous, i.e. that there is a real coercion it
        # catches.  Measured on this machine: a long all-digit ID (40003764029) actually
        # survives pandas -> openpyxl -> pandas(dtype=str) intact, so scientific notation is
        # NOT the reproducible hazard here.  Leading zeros are: an unpinned Zip of 02710 is
        # written as the number 2710 and comes back as '2710'.  That is the failure mode the
        # TEXT_COLS pinning exists to prevent, so that is what the probe uses.
        p2 = os.path.join(tempfolder, 'SELFTEST_unpinned.xlsx')
        b2 = good.copy()
        b2['Zip'] = [2710]                      # what an unpinned '02710' becomes
        b2.to_excel(p2, index=False)
        rb = pd.read_excel(p2, dtype=str).fillna('')
        damaged = rb['Zip'][0] != '02710'
        check('unpinned Zip IS damaged by Excel (so the round-trip check can fail)',
              damaged, "'02710' came back as " + repr(str(rb['Zip'][0])))
        # and the comparison used by write_output would flag exactly that
        bef = digit_fingerprint(good.assign(Zip=['02710']))
        aft = digit_fingerprint(rb)
        check('digit_fingerprint comparison detects it',
              bef['Zip'].get(0) != aft['Zip'].get(0),
              '{} vs {}'.format(bef['Zip'].get(0), aft['Zip'].get(0)))
        os.remove(p2)
    finally:
        globals()['filename'] = saved_name

    print('')
    print('SELFTEST: {} passed, {} failed'.format(len(ok), len(fail)))
    for f in fail:
        print('  FAILED: {}'.format(f))
    return len(fail)


if os.environ.get('OJK_SELFTEST', '') == '1':
    sys.exit(1 if selftest() else 0)
