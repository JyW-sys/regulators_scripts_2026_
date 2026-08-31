#---- Begin_Librairie ----
# CR SUGEVAL - Registro Nacional de Valores e Intermediarios
# DECD-6825
#
# NOTE ON THE SOURCE HOST (2026-08-20):
#   The URL in the Jira ticket, https://aplicaciones.sugeval.fi.cr/..., is DEAD.
#   TCP :443 connects but the TLS handshake is reset by peer on both A records.
#   The registry now lives on https://serviciosexternos.sugeval.fi.cr/RNVIWeb/...
#   The category paths are harvested at runtime from https://www.sugeval.fi.cr/
#   so that a further re-platforming shows up as a loud SKIPPED, not silent zeros.
#
# The grid is a DataTables widget hydrated by a POST to
#   /RNVIWeb/BackendAPI/ObtenerDatosPrincipal/<alias>
# where <alias> is the form attribute data-alias-consulta on the category page,
# and the POST carries the page's __RequestVerificationToken (anti-CSRF).
# The response body is DOUBLE-ENCODED JSON (a JSON string containing JSON).

import os
import re
import json
import time
import datetime
import unicodedata

import requests
import pandas as pd

requests.packages.urllib3.disable_warnings()

#---- Begin_fileName ----

regulatorName = 'CR SUGEVAL'

print("Running {} Web Scraping Tool v.2.0".format(regulatorName))

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')

filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":", ".")[:-7])

try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))  ## production environment (.py)
except NameError:
    scriptfolder = os.getcwd()  ## notebook environment

os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder')
if not os.path.exists(tempfolder):
    os.mkdir(tempfolder)

#---- Begin_Variable ----

BASE = 'https://serviciosexternos.sugeval.fi.cr'
INDEX = 'https://www.sugeval.fi.cr/'
ENDPOINT = BASE + '/RNVIWeb/BackendAPI/ObtenerDatosPrincipal/{alias}'

HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'),
    'Accept-Language': 'es-CR,es;q=0.9',
}

# The ticket explicitly asks to skip these three categories.
SKIP_CATEGORIES = {'agentescorredores', 'sociedadesfiduciarias', 'sociedadestitularizadoras'}
# Aggregate landing page, not a category (it is the URL quoted on the ticket).
NOT_A_CATEGORY = {'todosparticipantes'}

# Filter sent to the backend. CodEstado 'I' = INSCRITO (currently registered).
QUERY_PARAMS = {"IdParticipante": "0", "CodEstado": "I", "FechaDesde": "",
                "FechaHasta": "", "EstadoParaBolsa": "0"}
URL_PARAMS = ["0", "I", "", "", "0"]

# Human-readable label per category slug (Typology).
CATEGORY_LABEL = {
    'AuditoresExternos':  'Auditores externos',
    'Calificadoras':      'Calificadoras de riesgo',
    'Custodios':          'Custodios',
    'Emisores':           'Emisores',
    'GruposFinancieros':  'Grupos financieros',
    'OtrosParticipantes': 'Otros participantes',
    'ProveedoresPrecios': 'Proveedor de precios',
    'PuestosBolsa':       'Puestos de bolsa',
    'SAFI':               'Sociedades administradoras de fondos de inversion',
}

# ---- THE FIXED 43-KEY SCHEMA. DO NOT ADD / REMOVE / RENAME A SINGLE KEY. ----
sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
          'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
          'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
          'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
          'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
          'Phone - Mother company': []}

SCHEMA_KEYS = list(sqldict.keys())

LIST_NAME = 'Registro Nacional de Valores e Intermediarios'
LIST_CODE = '1'
LIST_LABEL = '4'   # SUGEVAL is the securities supervisor -> "everything else"

#---- Begin_Function ----

def add_row(**kw):
    """Single write path for the output. Appends to EVERY one of the 43 keys on
    EVERY record, so the columns can never drift out of alignment. Raises on an
    unknown key so a typo fails loudly instead of silently dropping data."""
    unknown = set(kw) - set(SCHEMA_KEYS)
    if unknown:
        raise KeyError('add_row got key(s) not in the 43-key schema: {}'.format(sorted(unknown)))
    for key in SCHEMA_KEYS:
        sqldict[key].append(str(kw.get(key, '') if kw.get(key, '') is not None else '').strip())


def norm(text):
    """Accent- and case-insensitive normalisation for label matching (Spanish)."""
    if text is None:
        return ''
    text = unicodedata.normalize('NFKD', str(text))
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    return unicodedata.normalize('NFKC', text).strip().lower()


def clean(value):
    """The backend pads fixed-width DB columns with trailing spaces."""
    if value is None:
        return ''
    return re.sub(r'\s+', ' ', str(value)).strip()


def make_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    s.verify = False   # corporate TLS proxy: a cert error is the proxy, not the site
    return s


def harvest_categories(session):
    """Resolve the category paths from the regulator's own index page every run.
    Never hard-code the enumeration - this repo has been bitten by that twice."""
    r = session.get(INDEX, timeout=90)
    r.raise_for_status()
    found = sorted(set(re.findall(
        r'https://serviciosexternos\.sugeval\.fi\.cr(/RNVIWeb/Participantes/[A-Za-z]+)', r.text)))
    if not found:
        print("SKIPPED - no anchor on {} pointing at /RNVIWeb/Participantes/ . "
              "The site has probably been re-platformed again.".format(INDEX))
        return []
    cats = []
    for path in found:
        slug = path.rsplit('/', 1)[1]
        n = norm(slug)
        if n in SKIP_CATEGORIES:
            print("   skipping (ticket says skip): {}".format(slug))
            continue
        if n in NOT_A_CATEGORY:
            print("   skipping (aggregate landing page, not a category): {}".format(slug))
            continue
        cats.append((slug, BASE + path))
    return cats


def fetch_category(session, slug, url):
    """GET the category page for its CSRF token + query alias, then POST for the grid rows."""
    page = session.get(url, timeout=120)
    if page.status_code != 200:
        print("   SKIPPED - {} returned HTTP {}".format(slug, page.status_code))
        return []
    html = page.text
    tok = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', html)
    alias = re.search(r'data-alias-consulta="([^"]+)"', html)
    if not tok or not alias:
        print("   SKIPPED - {}: no __RequestVerificationToken / data-alias-consulta on the page "
              "(soft 404 or markup change)".format(slug))
        return []

    data = [('__RequestVerificationToken', tok.group(1)),
            ('parametros', json.dumps(QUERY_PARAMS))]
    for v in URL_PARAMS:
        data.append(('urlParametros[]', v))
    data.append(('esGet', 'false'))

    resp = session.post(ENDPOINT.format(alias=alias.group(1)), data=data,
                        headers={'X-Requested-With': 'XMLHttpRequest', 'Referer': url},
                        timeout=180)
    if resp.status_code != 200:
        print("   SKIPPED - {}: backend returned HTTP {}".format(slug, resp.status_code))
        return []
    return decode_payload(resp.text, slug)


def decode_payload(text, slug):
    """The endpoint returns DOUBLE-ENCODED JSON: a JSON string whose content is JSON."""
    try:
        payload = json.loads(text)
    except ValueError:
        print("   SKIPPED - {}: response was not JSON (bot-defence challenge?): {}".format(slug, text[:120]))
        return []
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError:
            print("   SKIPPED - {}: inner payload was not JSON".format(slug))
            return []
    if payload is None:
        print("   SKIPPED - {}: backend returned null".format(slug))
        return []
    if not isinstance(payload, list):
        print("   SKIPPED - {}: unexpected payload type {}".format(slug, type(payload).__name__))
        return []
    return payload


def fetch_category_browser(slug, url):
    """Fallback: drive a real browser and capture the same XHR. Used only if the
    plain-requests path yields nothing - the site sits behind F5 Shape/BIG-IP
    (/TSPD/...), which may start challenging scripted sessions at any time."""
    try:
        from DrissionPage import ChromiumPage, ChromiumOptions
    except ImportError:
        print("   DrissionPage not installed - no browser fallback available")
        return []
    page = None
    try:
        co = ChromiumOptions().auto_port()
        co.set_argument('--ignore-certificate-errors')
        co.headless(True)
        page = ChromiumPage(co)
        page.set.timeouts(base=40, page_load=120)
        page.listen.start(targets='ObtenerDatosPrincipal', res_type=['XHR', 'Fetch'])
        page.get(url)
        try:
            page.ele('#principalConsultar', timeout=15).click()
        except Exception:
            pass
        for packet in page.listen.steps(timeout=45):
            body = packet.response.body
            return decode_payload(body if isinstance(body, str) else json.dumps(body), slug)
    except Exception as exc:
        print("   browser fallback failed for {}: {}".format(slug, str(exc)[:160]))
    finally:
        if page is not None:
            try:
                page.quit()
            except Exception:
                pass
    return []

#---- Begin_MainLoop ----

session = make_session()

print("\n[INFO] Harvesting category links from {} ...".format(INDEX))
categories = harvest_categories(session)
print("[INFO] {} in-scope categories: {}".format(len(categories), [c for c, _ in categories]))

percat = {}

for i, (slug, url) in enumerate(categories, start=1):
    print("\n[INFO] {}/{}  {}".format(i, len(categories), slug))
    rows = fetch_category(session, slug, url)
    if not rows:
        print("   plain requests returned 0 rows -> trying browser fallback")
        rows = fetch_category_browser(slug, url)

    typology = CATEGORY_LABEL.get(slug, slug)
    kept = 0
    for item in rows:
        name = clean(item.get('NombreParticipante'))
        if not name:
            continue
        add_row(
            Name=name,
            Typology=typology,
            CoType=clean(item.get('Rol')),
            License_Type=clean(item.get('Regulador')),
            InternalID_1=clean(item.get('IdParticipante')),
            InternalID_1_type='Codigo de participante SUGEVAL' if clean(item.get('IdParticipante')) else '',
            InternalID_2=clean(item.get('CodRol')),
            InternalID_2_type='Codigo de rol' if clean(item.get('CodRol')) else '',
            Cntry='CR',
            RegulationType='Regulated',
            RegCtry='CR',
            RegCode='SUGEVAL',
            ListCode=LIST_CODE,
            ListLabel=LIST_LABEL,
            ListName=LIST_NAME,
            ListLanguage='ES',
            ListProcessDate=processdate,
        )
        kept += 1
    percat[slug] = kept
    print("   rows kept: {}".format(kept))
    time.sleep(1)

print("\n[INFO] ---- per-category reconciliation ----")
for slug, n in percat.items():
    print("   {:22s} {:5d}".format(slug, n))
print("   {:22s} {:5d}".format('TOTAL', sum(percat.values())))

#---- Begin_writer and save df to excel ----

os.chdir(scriptfolder)

df = pd.DataFrame(sqldict)

assert list(df.columns) == SCHEMA_KEYS, 'output columns drifted from the 43-key schema'

df = df[df['Name'] != '']

df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)

print('\nSaved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))
