# ------------------------------------------------ Import Lib ----------------------------------------
import os
import time
import datetime
import requests
import pandas as pd
from bs4 import BeautifulSoup

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ------------------------------------------------ Begin_ fileName ----------------------------------------
regulatorName = 'SV SSF'  # Superintendencia del Sistema Financiero (El Salvador)

print(f"Running {regulatorName} Web Scraping Tool v.1.0")

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":", ".")[:-7])

# ------ define the workspace path -----
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))  # production environment (.py)
except NameError:
    scriptfolder = os.getcwd()  # notebook environment
os.chdir(scriptfolder)

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                         '(KHTML, like Gecko) Chrome/120 Safari/537.36'}

# ------------------------------------------------ sqldict (DO NOT CHANGE STRUCTURE) ----------------------------------------
sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}


def bourange_same_length_array(sqldict):
    maxlen = max(len(v) for v in sqldict.values())
    for key in sqldict:
        if len(sqldict[key]) != maxlen:
            sqldict[key].extend([''] * (maxlen - len(sqldict[key])))
    return sqldict


def get_soup(url, tries=4):
    """GET with verify=False + desktop UA. Retries the flaky corporate proxy."""
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, headers=HEADERS, verify=False, timeout=60)
            r.raise_for_status()
            return BeautifulSoup(r.text, 'html.parser')
        except Exception as e:
            last = e
            time.sleep(3)
    raise last


# ---- field parser: turns a block of "label / value" text lines into address/website/phone/email ----
CARE = {'dirección': 'address', 'direccion': 'address',
        'sitio web': 'website', 'página web': 'website', 'pagina web': 'website', 'web': 'website',
        'teléfono': 'phone', 'telefono': 'phone', 'tel': 'phone',
        'correo': 'email', 'correo electrónico': 'email', 'email': 'email', 'e-mail': 'email'}
# labels whose value we deliberately drop (people / fax etc.) so they are not mistaken for data
IGNORE = {'presidente', 'presidenta', 'presidente ejecutivo', 'director ejecutivo', 'directora ejecutiva',
          'gerente general', 'gerente gral', 'gerente gral.', 'director', 'directora',
          'apoderado', 'fax', 'vicepresidente'}


def parse_fields(lines):
    f = {'address': '', 'website': '', 'phone': '', 'email': ''}
    pending = None  # field awaiting its value on the next line ('__ig__' = ignore next value)
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith('ver junta') or low.startswith('(ver junta'):
            pending = None
            continue
        if ':' in line:
            lab, _, val = line.partition(':')
            labn = lab.strip().lower()
            val = val.strip()
            if labn in CARE:
                fld = CARE[labn]
                if val:
                    if not f[fld]:
                        f[fld] = val
                    pending = None
                else:
                    pending = fld
            elif labn in IGNORE:
                pending = None
            else:
                # colon inside a value (e.g. address "No.:100") -> belongs to the pending field
                if pending and pending != '__ig__' and not f[pending]:
                    f[pending] = line
                pending = None
            continue
        labn = low.rstrip(':').strip()
        if labn in CARE:
            pending = CARE[labn]
            continue
        if labn in IGNORE:
            pending = '__ig__'
            continue
        if pending and pending != '__ig__':
            if not f[pending]:
                f[pending] = line
            pending = None
        else:
            pending = None
    return f


# ---- appends one entity to sqldict with all the mandatory constants filled in ----
def add_entity(name, listname, listcode, listlabel, fields=None, cotype=''):
    fields = fields or {}
    sqldict['Name'].append(name)
    sqldict['CoType'].append(cotype)
    sqldict['Address_1'].append(fields.get('address', ''))
    sqldict['Phone'].append(fields.get('phone', ''))
    sqldict['Website'].append(fields.get('website', ''))
    sqldict['Email'].append(fields.get('email', ''))
    sqldict['Cntry'].append('SV')
    sqldict['RegulationType'].append('Regulated')
    sqldict['RegCtry'].append('SV')
    sqldict['RegCode'].append('SSF')
    sqldict['ListCode'].append(listcode)
    sqldict['ListName'].append(listname)
    sqldict['ListLabel'].append(listlabel)
    sqldict['ListLanguage'].append('ES')
    sqldict['ListProcessDate'].append(processdate)
    bourange_same_length_array(sqldict)


def content_lines(content):
    return [x for x in content.get_text('\n', strip=True).split('\n') if x.strip()]


# entity names / field markers used by the "one accordion == one entity" pages
def scrape_accordion_title_list(url, listname, listcode, listlabel):
    """Pages where each .elementor-accordion-item is ONE entity (title = name, content = details)."""
    soup = get_soup(url)
    seen = set()
    n = 0
    for it in soup.select('.elementor-accordion-item'):
        te = it.select_one('.elementor-accordion-title')
        if not te:
            continue
        name = te.get_text(' ', strip=True)
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        content = it.select_one('.elementor-tab-content')
        fields = parse_fields(content_lines(content)) if content else {}
        add_entity(name, listname, listcode, listlabel, fields)
        n += 1
    return n


def scrape_nested_accordion(url, listname, listcode, listlabel):
    """Pages where each .elementor-accordion-item is a CATEGORY holding many entities.
    Entity names are <h4>/<h5>/<h6> headings (list 9) or <li> items (list 10);
    field lines are <p> elements that follow a name until the next name."""
    soup = get_soup(url)
    seen = set()
    n = 0
    for it in soup.select('.elementor-accordion-item'):
        te = it.select_one('.elementor-accordion-title')
        category = te.get_text(' ', strip=True) if te else ''
        # strip a leading "N. " numbering used on the securities page
        if category[:2].strip().rstrip('.').isdigit():
            category = category.split('.', 1)[1].strip()
        content = it.select_one('.elementor-tab-content')
        if not content:
            continue
        cur_name = None
        cur_lines = []

        def flush():
            nonlocal cur_name, cur_lines, n
            if cur_name and cur_name.lower() not in seen:
                seen.add(cur_name.lower())
                add_entity(cur_name, listname, listcode, listlabel,
                           parse_fields(cur_lines), cotype=category)
                n += 1
            cur_name, cur_lines = None, []

        for el in content.find_all(['h2', 'h3', 'h4', 'h5', 'h6', 'li', 'p']):
            txt = el.get_text(' ', strip=True)
            if not txt:
                continue
            if el.name in ('h2', 'h3', 'h4', 'h5', 'h6', 'li'):
                flush()
                cur_name = txt
            else:  # <p> -> a detail line for the current entity
                cur_lines.append(txt)
        flush()
    return n


def scrape_table_heading_list(url, listname, listcode, listlabel):
    """Pages where each entity is a <table> and its name is the heading just before it (list 4)."""
    soup = get_soup(url)
    seen = set()
    n = 0
    for t in soup.find_all('table'):
        head = t.find_previous(['h2', 'h3', 'h4', 'h5'])
        name = head.get_text(' ', strip=True) if head else ''
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        fields = parse_fields(content_lines(t))
        add_entity(name, listname, listcode, listlabel, fields)
        n += 1
    return n


# ------------------------------------------------ Begin_ scraping ----------------------------------------
counts = {}

# 1 - Bancos privados (banks) -> ListLabel 1  (accordion title = name, table detail)
counts['1 Bancos privados'] = scrape_accordion_title_list(
    'https://ssf.gob.sv/bancos/', 'Bancos privados', 1, 1)

# 2 - Bancos cooperativos (banks) -> ListLabel 1  (TWO pages merged: authorised + not authorised)
c2 = scrape_accordion_title_list(
    'https://ssf.gob.sv/2021/12/08/bancos-cooperativos-autorizados-para-captar-depositos-del-publico/',
    'Bancos cooperativos', 2, 1)
c2 += scrape_accordion_title_list(
    'https://ssf.gob.sv/2021/12/07/bancos-cooperativos-sin-autorizacion-para-captar-depositos-del-publico/',
    'Bancos cooperativos', 2, 1)
counts['2 Bancos cooperativos'] = c2

# 3 - Bancos estatales (state banks) -> ListLabel 1
counts['3 Bancos estatales'] = scrape_accordion_title_list(
    'https://ssf.gob.sv/bancos-estatales/', 'Bancos estatales', 3, 1)

# 4 - Sucursales de bancos extranjeros (foreign bank branches) -> ListLabel 1  (heading + table)
counts['4 Sucursales de bancos extranjeros'] = scrape_table_heading_list(
    'https://ssf.gob.sv/sucursales-de-bancos-extranjeros/', 'Sucursales de bancos extranjeros', 4, 1)

# 5 - Sociedades proveedoras de dinero electronico (e-money) -> ListLabel 4
counts['5 Sociedades proveedoras de dinero electronico'] = scrape_accordion_title_list(
    'https://ssf.gob.sv/2021/12/08/sociedades-proveedoras-de-dinero-electronico/',
    'Sociedades proveedoras de dinero electronico', 5, 4)

# 6 - Sociedades de Ahorro y Credito (savings & credit) -> ListLabel 1
counts['6 Sociedades de Ahorro y Credito'] = scrape_accordion_title_list(
    'https://ssf.gob.sv/sociedades-de-ahorro-y-credito/', 'Sociedades de Ahorro y Credito', 6, 1)

# 7 - Sociedades de seguros y fianzas (insurance) -> ListLabel 2
counts['7 Seguros y fianzas'] = scrape_accordion_title_list(
    'https://ssf.gob.sv/2021/12/08/entidades-autorizadas-para-operar-como-sociedades-de-seguros-y-fianzas/',
    'Entidades autorizadas para operar como sociedades de seguros y fianzas', 7, 2)

# 8 - Casas de cambio (exchange houses) -> ListLabel 4
counts['8 Casas de cambio'] = scrape_accordion_title_list(
    'https://ssf.gob.sv/2022/01/03/entidades-autorizadas-para-operar-como-casas-de-cambio/',
    'Entidades autorizadas para operar como casas de cambio', 8, 4)

# 9 - Mercado de valores (securities) -> ListLabel 4  (nested: category accordions, entities in <h5>)
counts['9 Mercado de valores'] = scrape_nested_accordion(
    'https://ssf.gob.sv/2022/01/03/entidades-autorizadas-para-operar-en-el-mercado-de-valores/',
    'Entidades autorizadas para operar en el mercado de valores', 9, 4)

# 10 - Sistema previsional (pensions) -> ListLabel 4  (nested: category accordions, entities in <li>)
counts['10 Sistema previsional'] = scrape_nested_accordion(
    'https://ssf.gob.sv/2022/01/03/entidades-autorizadas-del-sistema-previsional/',
    'Entidades autorizadas del sistema previsional', 10, 4)

print('\n---- rows per list ----')
for k, v in counts.items():
    print(f'  {k}: {v}')
print(f'  TOTAL: {sum(counts.values())}')

# ------------------------------------------------ save df to excel ----------------------------------------
os.chdir(scriptfolder)
df = pd.DataFrame(sqldict)
df = df[df['Name'] != '']
df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)
print('\nSaved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))
