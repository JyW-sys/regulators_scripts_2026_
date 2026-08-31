#---- Begin_Librairie ----
# -*- coding: utf-8 -*-
"""
CR SUGESE - Superintendencia General de Seguros (Costa Rica)
Jira: DECD-6821

7 lists.  Lists 1-4 live in Microsoft Power BI "publish to web" reports and are
extracted through the public Power BI REST API (modelsAndExploration ->
conceptualschema -> querydata).  Lists 5-7 are plain HTML tables.

NOTE (2026-08): sugese.fi.cr was migrated to a new Adobe AEM platform.  The URLs
quoted in the Jira ticket (/seccion-mercado-seguros/...) all return HTTP 404.
The scraper resolves the new /cr/es/mercado-seguros/*.html pages and reads the
Power BI report links straight off them, so a further re-shuffle of the report
tokens will be picked up automatically.
"""
import os
import re
import json
import uuid
import base64
import datetime
import unicodedata

import requests
import pandas as pd
from bs4 import BeautifulSoup

requests.packages.urllib3.disable_warnings()


#---- Begin_fileName ----
# ------ At first we will define the workspace path -----
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))  ## production environment (.py)
except NameError:
    scriptfolder = os.getcwd()  ## notebook environment

os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder')
if not os.path.exists(tempfolder):
    os.makedirs(tempfolder)

regulatorName = 'CR SUGESE'  ## change to current controller name
now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(':', '.')[:-7])


#---- Begin_Variable ----
BASE = 'https://www.sugese.fi.cr'
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

RegCtry = 'CR'
RegCode = 'SUGESE'
ListLanguage = 'ES'

sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}

# reg key -> landing page on the new AEM site
urls = {
    regulatorName + ' 1': BASE + '/cr/es/mercado-seguros/aseguradoras.html',
    regulatorName + ' 2': BASE + '/cr/es/mercado-seguros/sociedades-agencia.html',
    regulatorName + ' 3': BASE + '/cr/es/mercado-seguros/sociedades-corredoras.html',
    regulatorName + ' 4': BASE + '/cr/es/mercado-seguros/operadores-de-seguros-autoexpedibles.html',
    regulatorName + ' 5': BASE + '/cr/es/mercado-seguros/seguros-transfronterizos.html',
    regulatorName + ' 6': BASE + '/cr/es/mercado-seguros/grupos-financieros.html',
    regulatorName + ' 7': BASE + '/cr/es/mercado-seguros/autorizaciones-condicionadas.html',
}

ListName = {
    regulatorName + ' 1': 'Aseguradoras',
    regulatorName + ' 2': 'Sociedades agencias de seguros',
    regulatorName + ' 3': 'Sociedades corredoras',
    regulatorName + ' 4': 'Operadores Activos de Seguros Autoexpedibles',
    regulatorName + ' 5': 'Proveedores de seguros transfronterizos',
    regulatorName + ' 6': 'Grupos financieros',
    regulatorName + ' 7': 'Autorizaciones condicionadas',
}

# 1 = bank, 2 = insurance, 3 = bank & insurance, 4 = everything else.
# SUGESE is the insurance supervisor -> lists 1-5 and 7 are insurance.
# List 6 "Grupos financieros" holds non-insurance group members (fund manager,
# brokerage house, health services company) -> 4.
ListLabel = {
    regulatorName + ' 1': '2',
    regulatorName + ' 2': '2',
    regulatorName + ' 3': '2',
    regulatorName + ' 4': '2',
    regulatorName + ' 5': '2',
    regulatorName + ' 6': '4',
    regulatorName + ' 7': '2',
}

# Only the "activas / activos" Power BI report of each page is in scope
# (the "canceladas / inactivas / suspendidos" ones are excluded).
PBI_REPORT_LABEL = {
    regulatorName + ' 1': 'aseguradoras activas',
    regulatorName + ' 2': 'sociedades agencia activas',
    regulatorName + ' 3': 'sociedades corredoras activas',
    regulatorName + ' 4': 'operadores de seguros autoexpedibles activos',
}

# Power BI fact table per list, discovered from the model's conceptual schema.
PBI_ENTITY_HINT = {
    regulatorName + ' 1': 'InformacionAseguradorasActivas',
    regulatorName + ' 2': 'InformacionSociedadesAgenciasActivas',
    regulatorName + ' 3': 'InformacionSociedadesCorredorasActivas',
    regulatorName + ' 4': 'InformacionOperadoresAutoexpediblesActivos',
}

# Companion (non-DES) table carrying licence + authorisation dates, joined by
# Power BI through the model relationships.
PBI_SIDE_HINT = {
    regulatorName + ' 1': 'Aseguradoras Activas',
    regulatorName + ' 2': 'Agencias activas',
    regulatorName + ' 3': 'Corredoras activas',
}

# Jurisdiccion (list 5) / Domicilio (list 6) free text -> ISO country code
SPANISH_MONTHS = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
                  'julio': 7, 'agosto': 8, 'septiembre': 9, 'setiembre': 9, 'octubre': 10,
                  'noviembre': 11, 'diciembre': 12}

CNTRY_MAP = {
    'costa rica': 'CR',
    'estados unidos de america': 'US',
    'estados unidos': 'US',
    'espana': 'ES',
    'panama': 'PA',
    'colombia': 'CO',
    'mexico': 'MX',
    'reino unido': 'GB',
    'suiza': 'CH',
    'alemania': 'DE',
    'francia': 'FR',
    'bermudas': 'BM',
}


#---- Begin_Function ----
def strip_accents(text):
    """Fold accents so free-text look-ups are robust."""
    if not text:
        return ''
    return ''.join(c for c in unicodedata.normalize('NFKD', text)
                   if not unicodedata.combining(c))


def clean(value):
    """Normalise any scraped cell to a tidy single-line string."""
    if value is None:
        return ''
    if isinstance(value, float) and value != value:  # NaN
        return ''
    text = unicodedata.normalize('NFKC', str(value))
    text = text.replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    if text.lower() in ('nan', 'none', 'n/a', 'na', 'no aplica', '-', '--'):
        return ''
    return text


def add_row(reg, **kw):
    """Append one record, filling EVERY key of sqldict so columns cannot drift."""
    row = {k: '' for k in sqldict}
    row['RegCtry'] = RegCtry
    row['RegCode'] = RegCode
    row['ListCode'] = reg.split(' ')[-1]
    row['ListName'] = ListName[reg]
    row['ListLabel'] = ListLabel[reg]
    row['ListLanguage'] = ListLanguage
    row['ListProcessDate'] = processdate
    row['RegulationType'] = 'Regulated'
    row['Cntry'] = RegCtry
    for key, value in kw.items():
        if key not in row:
            raise KeyError('Unknown sqldict column: %s' % key)
        row[key] = clean(value)
    for key in sqldict:
        sqldict[key].append(row[key])


def parse_date(value):
    """Return YYYY-MM-DD from the many shapes SUGESE uses, else ''.

    Handles: '18/06/2009', '11/27/2009' (stray US order), epoch milliseconds,
    and multi-line blobs such as 'Generales:\\n19/02/2010\\nPersonales:\\n19/07/2011'
    (the earliest date found is kept).
    """
    if value is None or value == '':
        return ''
    # Power BI returns dates as epoch milliseconds
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.datetime.utcfromtimestamp(float(value) / 1000.0).strftime('%Y-%m-%d')
        except (ValueError, OSError, OverflowError):
            return ''
    text = str(value)
    found = []
    for a, b, y in re.findall(r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})', text):
        a, b, y = int(a), int(b), int(y)
        day, month = (a, b) if a > 12 else ((b, a) if b > 12 else (a, b))
        try:
            found.append(datetime.date(y, month, day))
        except ValueError:
            continue
    for y, m, d in re.findall(r'(\d{4})-(\d{2})-(\d{2})', text):
        try:
            found.append(datetime.date(int(y), int(m), int(d)))
        except ValueError:
            continue
    # Spanish long form, e.g. "Sesion 822-2009 del 11 de diciembre de 2009"
    for d, name, y in re.findall(r'(\d{1,2})\s+de\s+([a-zA-Zqrstà-ÿ]+)\s+de\s+(\d{4})',
                                 strip_accents(text).lower()):
        month = SPANISH_MONTHS.get(name)
        if month:
            try:
                found.append(datetime.date(int(y), month, int(d)))
            except ValueError:
                continue
    return min(found).strftime('%Y-%m-%d') if found else ''


def map_cntry(text, default=''):
    key = strip_accents(clean(text)).lower()
    for name, code in CNTRY_MAP.items():
        if name in key:
            return code
    return default


def get_soup(url):
    r = requests.get(url, headers={'User-Agent': UA}, verify=False, timeout=90)
    r.raise_for_status()
    return BeautifulSoup(r.content.decode('utf-8', 'replace'), 'html.parser')


# ----------------------------------------------------------------------------
# Power BI "publish to web" access layer
# ----------------------------------------------------------------------------
def pbi_headers(resource_key, json_body=False):
    headers = {'User-Agent': UA,
               'X-PowerBI-ResourceKey': resource_key,
               'Accept': 'application/json, text/plain, */*',
               'Origin': 'https://app.powerbi.com',
               'Referer': 'https://app.powerbi.com/',
               'ActivityId': str(uuid.uuid4()),
               'RequestId': str(uuid.uuid4())}
    if json_body:
        headers['Content-Type'] = 'application/json;charset=UTF-8'
    return headers


def pbi_resolve(token):
    """token from app.powerbi.com/view?r=... -> (resource_key, api_cluster, model_id)."""
    padded = token + '=' * (-len(token) % 4)
    resource_key = json.loads(base64.b64decode(padded))['k']
    view = requests.get('https://app.powerbi.com/view?r=' + token,
                        headers={'User-Agent': UA}, verify=False, timeout=90)
    view.raise_for_status()
    m = re.search(r"resolvedClusterUri\s*=\s*'([^']+)'", view.text)
    base = (m.group(1) if m else 'https://wabi-paas-1-scus-redirect.analysis.windows.net').rstrip('/')
    # the load-balancer host answers on '-redirect', the data plane on '-api'
    last = None
    for cluster in [base.replace('-redirect', '-api'), base]:
        r = requests.get(cluster + '/public/reports/' + resource_key +
                         '/modelsAndExploration?preferReadOnlySession=true',
                         headers=pbi_headers(resource_key), verify=False, timeout=90)
        last = r.status_code
        if r.status_code == 200:
            return resource_key, cluster, r.json()['models'][0]['id']
    raise RuntimeError('Power BI cluster resolution failed for %s (HTTP %s)' % (resource_key, last))


def pbi_schema(resource_key, cluster, model_id):
    """{entity name: [property names]} for the whole semantic model."""
    r = requests.post(cluster + '/public/reports/conceptualschema',
                      headers=pbi_headers(resource_key, True),
                      data=json.dumps({'modelIds': [model_id]}), verify=False, timeout=90)
    r.raise_for_status()
    entities = r.json()['schemas'][0]['schema']['Entities']
    return dict((e['Name'], [p['Name'] for p in e.get('Properties', [])]) for e in entities)


def pbi_query(resource_key, cluster, model_id, pairs, top=30000):
    """pairs = [(entity, property), ...]; Power BI auto-joins via model relationships."""
    entities = []
    for entity, _ in pairs:
        if entity not in entities:
            entities.append(entity)
    alias = dict((e, 'e%d' % i) for i, e in enumerate(entities))
    command = {'SemanticQueryDataShapeCommand': {
        'Query': {'Version': 2,
                  'From': [{'Name': alias[e], 'Entity': e, 'Type': 0} for e in entities],
                  'Select': [{'Column': {'Expression': {'SourceRef': {'Source': alias[e]}},
                                         'Property': p},
                              'Name': '%s.%s' % (alias[e], p)} for e, p in pairs]},
        'Binding': {'Primary': {'Groupings': [{'Projections': list(range(len(pairs)))}]},
                    'DataReduction': {'DataVolume': 4, 'Primary': {'Window': {'Count': top}}},
                    'Version': 1},
        'ExecutionMetricsKind': 1}}
    body = {'version': '1.0.0',
            'queries': [{'Query': {'Commands': [command]}, 'QueryId': '',
                         'ApplicationContext': {
                             'DatasetId': '00000000-0000-0000-0000-000000000000',
                             'Sources': [{'ReportId': '00000000-0000-0000-0000-000000000000'}]}}],
            'cancelQueries': [], 'modelId': model_id}
    r = requests.post(cluster + '/public/reports/querydata?synchronous=true',
                      headers=pbi_headers(resource_key, True),
                      data=json.dumps(body), verify=False, timeout=180)
    r.raise_for_status()
    return r.json()


def pbi_measure_text(resource_key, cluster, model_id, entity, prop):
    """Evaluate a model MEASURE (not a column) and return its raw JSON text.

    The report publishes its own refresh stamp as a measure, e.g.
    'Ultima fecha de actualizacion: 20/08/2026 04:30 am'.
    """
    command = {'SemanticQueryDataShapeCommand': {
        'Query': {'Version': 2,
                  'From': [{'Name': 'd', 'Entity': entity, 'Type': 0}],
                  'Select': [{'Measure': {'Expression': {'SourceRef': {'Source': 'd'}},
                                          'Property': prop},
                              'Name': 'd.' + prop}]},
        'Binding': {'Primary': {'Groupings': [{'Projections': [0]}]}, 'Version': 1},
        'ExecutionMetricsKind': 1}}
    body = {'version': '1.0.0',
            'queries': [{'Query': {'Commands': [command]}, 'QueryId': '',
                         'ApplicationContext': {
                             'DatasetId': '00000000-0000-0000-0000-000000000000',
                             'Sources': [{'ReportId': '00000000-0000-0000-0000-000000000000'}]}}],
            'cancelQueries': [], 'modelId': model_id}
    r = requests.post(cluster + '/public/reports/querydata?synchronous=true',
                      headers=pbi_headers(resource_key, True),
                      data=json.dumps(body), verify=False, timeout=120)
    r.raise_for_status()
    return r.text


def pbi_decode(response, names):
    """Decode Power BI's compressed DSR payload into list[dict].

    Each row carries only the values that changed: bitmask 'R' marks columns
    repeated from the previous row, bitmask 'Oe' marks nulls, and integer values
    are indexes into the per-column ValueDicts.
    """
    records = []
    dsr = response['results'][0]['result']['data']['dsr']
    for ds in dsr.get('DS', []):
        dicts = ds.get('ValueDicts', {})
        for ph in ds.get('PH', []):
            members = [k for k in ph if k.startswith('DM')]
            if not members:
                continue
            schema = None
            previous = {}
            for row in ph[members[0]]:
                if 'S' in row:
                    schema = row['S']
                if schema is None:
                    continue
                width = len(schema)
                values = row.get('C', [])
                repeat = row.get('R', 0)
                nulls = row.get('Ø', 0)
                resolved = []
                cursor = 0
                for i in range(width):
                    if repeat >> i & 1:
                        resolved.append(previous.get(i))
                    elif nulls >> i & 1:
                        resolved.append(None)
                    else:
                        resolved.append(values[cursor] if cursor < len(values) else None)
                        cursor += 1
                previous = dict(enumerate(resolved))
                record = {}
                for i in range(width):
                    value = resolved[i]
                    dict_name = schema[i].get('DN')
                    if dict_name and isinstance(value, int) and dict_name in dicts:
                        pool = dicts[dict_name]
                        value = pool[value] if 0 <= value < len(pool) else value
                    record[names[i] if i < len(names) else 'col%d' % i] = value
                records.append(record)
    return records


def pbi_fetch(reg, soup):
    """Locate the 'activas' report on the landing page and pull its fact table."""
    wanted = PBI_REPORT_LABEL[reg]
    token = None
    for a in soup.find_all('a', href=True):
        if 'powerbi.com' in a['href'] and 'r=' in a['href']:
            label = strip_accents(a.get_text(' ', strip=True)).lower()
            if strip_accents(wanted) in label:
                token = a['href'].split('r=', 1)[1].split('&')[0]
                break
    if token is None:
        raise RuntimeError('%s: no Power BI report labelled "%s" on %s' % (reg, wanted, urls[reg]))

    resource_key, cluster, model_id = pbi_resolve(token)
    schema = pbi_schema(resource_key, cluster, model_id)

    hint = PBI_ENTITY_HINT[reg]
    fact = next((e for e in schema if hint in e), None)
    if fact is None:
        raise RuntimeError('%s: entity matching "%s" not found in model %s' % (reg, hint, model_id))

    side = PBI_SIDE_HINT.get(reg)
    if side and side not in schema:
        side = None

    pairs = [(fact, p) for p in schema[fact] if p not in ('Llave',)]
    if side:
        pairs += [(side, p) for p in schema[side] if p not in ('Llave', 'CodAseguradora')]
    # de-duplicate the property names we hand to the decoder
    names, seen = [], {}
    for entity, prop in pairs:
        key = prop if prop not in seen else '%s#%d' % (prop, seen[prop])
        seen[prop] = seen.get(prop, 0) + 1
        names.append(key)

    response = pbi_query(resource_key, cluster, model_id, pairs)
    rows = pbi_decode(response, names)

    # "Ultima fecha de actualizacion: dd/mm/yyyy" published by the report itself,
    # exposed as a MEASURE on the FechaActualizacion table.
    validity = ''
    for entity in schema:
        if 'FechaActualizacion' not in entity:
            continue
        for prop in [p for p in schema[entity] if p.startswith('Mensaje')]:
            try:
                text = pbi_measure_text(resource_key, cluster, model_id, entity, prop)
            except Exception as exc:
                print('    ! update-stamp query failed ({}): {}'.format(prop, exc))
                continue
            hits = re.findall(r'\d{1,2}/\d{1,2}/\d{4}', text)
            if hits:
                validity = parse_date(hits[0])
                break
        if validity:
            break
    return rows, validity


def html_table(soup):
    """First real <table> on the page as (headers, list of row-value lists)."""
    for table in soup.find_all('table'):
        rows = table.find_all('tr')
        if len(rows) < 2:
            continue
        headers = [clean(c.get_text(' ', strip=True)) for c in rows[0].find_all(['th', 'td'])]
        body = []
        for tr in rows[1:]:
            cells = [clean(c.get_text(' ', strip=True)) for c in tr.find_all(['th', 'td'])]
            if any(cells):
                body.append(cells)
        if body:
            return headers, body
    return [], []


def col(headers, row, *candidates):
    """Fetch a cell by fuzzy header label so a column re-order cannot break us."""
    folded = [strip_accents(h).lower() for h in headers]
    for candidate in candidates:
        target = strip_accents(candidate).lower()
        for i, h in enumerate(folded):
            if target == h or target in h:
                return row[i] if i < len(row) else ''
    return ''


#---- Begin_MainLoop ----
counts = {}

for reg in sorted(urls):
    print('\n--- {} : {} ---'.format(reg, ListName[reg]))
    before = len(sqldict['Name'])
    soup = get_soup(urls[reg])
    number = reg.split(' ')[-1]

    if number in ('1', '2', '3', '4'):
        rows, validity = pbi_fetch(reg, soup)
        print('    Power BI rows returned: {}'.format(len(rows)))

        for r in rows:
            if number == '1':
                add_row(reg,
                        Name=r.get('RazonSocial'),
                        InternalID_1=r.get('Identificacion'),
                        InternalID_1_type='Trade Register Number',
                        InternalID_2=r.get('Licencia'),
                        InternalID_2_type='License Number',
                        CoType=r.get('Tipo entidad'),
                        License_Type=r.get('Categoria'),
                        Address_1=r.get('Direccion'),
                        Phone=r.get('Telefono'),
                        Email=r.get('CorreoElectronico'),
                        Website=r.get('Sitio web'),
                        RegulationDate=parse_date(r.get('Fecha inscripción')
                                                  or r.get('Fecha autorización')),
                        ListValidityDate=validity)
            elif number == '2':
                add_row(reg,
                        Name=r.get('RazonSocial'),
                        InternalID_1=r.get('Identificacion'),
                        InternalID_1_type='Trade Register Number',
                        InternalID_2=r.get('NumLicencia'),
                        InternalID_2_type='License Number',
                        License_Type=r.get('Exclusiva'),
                        Address_1=r.get('Direccion'),
                        Phone=r.get('Telefono'),
                        RegulationDate=parse_date(r.get('Fecha inscripción')
                                                  or r.get('Fecha autorización')),
                        ListValidityDate=validity,
                        # accrediting insurer - see README, to confirm with requester
                        **{'Name - Mother Company': r.get('AseguradoraAcredita')})
            elif number == '3':
                add_row(reg,
                        Name=r.get('RazonSocial'),
                        InternalID_1=r.get('Identificacion'),
                        InternalID_1_type='Trade Register Number',
                        InternalID_2=r.get('NumLicencia'),
                        InternalID_2_type='License Number',
                        Address_1=r.get('Direccion'),
                        Phone=r.get('Telefono'),
                        RegulationDate=parse_date(r.get('Fecha inscripción')
                                                  or r.get('Fecha autorización')),
                        ListValidityDate=validity)
            else:  # number == '4' - principal office only, per ticket comments
                add_row(reg,
                        Name=r.get('RazonSocialOperador'),
                        InternalID_1=r.get('IdentificacionOperador'),
                        InternalID_1_type='Trade Register Number',
                        InternalID_2=r.get('CodigoRegistro'),
                        InternalID_2_type='License Number',
                        Address_1=r.get('DireccionOficinaPrincipal'),
                        Address_2=r.get('ProvinciaOficinaPrincipal'),
                        City=r.get('CantonOficinaPrincipal'),
                        Phone=r.get('TelefonoOficinaPrincipal'),
                        Email=r.get('CorreoElectronicoOficinaPrincial'),
                        Website=r.get('SitioWebServicioAlCliente'),
                        RegulationDate=parse_date(r.get('FechaRegistro')),
                        ListValidityDate=validity,
                        **{'Name - Mother Company': r.get('Entidad')})

    else:
        headers, body = html_table(soup)
        print('    HTML table rows: {}'.format(len(body)))

        for row in body:
            if number == '5':
                # "Jurisdicción" is the home jurisdiction, not a street address:
                # it only feeds Cntry. Address_1 stays empty - the page publishes
                # no address for cross-border providers.
                jurisdiction = col(headers, row, 'Jurisdicción')
                add_row(reg,
                        Name=col(headers, row, 'Entidad'),
                        InternalID_1=col(headers, row, 'Código'),
                        InternalID_1_type='License Number',
                        License_Type=col(headers, row, 'Tipo de Licencia'),
                        Cntry=map_cntry(jurisdiction),
                        RegulationDate=parse_date(col(headers, row, 'Fecha Registro')),
                        ListValidityDate=parse_date(col(headers, row, 'Vigencia registro')))
            elif number == '6':
                domicile = col(headers, row, 'Domicilio')
                add_row(reg,
                        Name=col(headers, row, 'Entidad'),
                        Typology=col(headers, row, 'Supervisora'),
                        Address_1=col(headers, row, 'Dirección'),
                        Cntry=map_cntry(domicile, RegCtry),
                        RegulationDate=parse_date(col(headers, row, 'Incorporación')),
                        **{'Name - Mother Company': col(headers, row, 'Grupo')})
            else:  # number == '7'
                add_row(reg,
                        Name=col(headers, row, 'Entidad'),
                        InternalID_1=col(headers, row, 'Autorización'),
                        InternalID_1_type='License Number',
                        License_Type=col(headers, row, 'Tipo de Autorización'),
                        RegulationDate=parse_date(col(headers, row, 'Fecha de Autorización')))

    counts[reg] = len(sqldict['Name']) - before
    print('    rows added: {}'.format(counts[reg]))


#---- Begin_writer and save df to excel ----
os.chdir(scriptfolder)
df = pd.DataFrame(sqldict)

df = df[df['Name'] != '']

df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)

print('\n================ SUMMARY ================')
for reg in sorted(counts):
    print('  {:<14} {:<46} {:>5}'.format(reg, ListName[reg], counts[reg]))
print('  {:<61} {:>5}'.format('TOTAL rows written', len(df)))
print('Saved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))
