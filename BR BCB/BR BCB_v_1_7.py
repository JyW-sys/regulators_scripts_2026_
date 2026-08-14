#------------------------------------------------ Begin_Librairie ----------------------------------------

import os
import re
import io
import glob
import time
import shutil
import zipfile
import datetime
import unicodedata
from time import sleep

import requests
import urllib3
import pandas as pd
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


#------------------------------------------------ Begin_ fileName ----------------------------------------

regulatorName = 'BR BCB'

print('Running {} Web Scraping Tool v.1.7'.format(regulatorName))

now = datetime.datetime.now()

filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":", ".")[:-7])

# ------ At first we will define the workspace path -----
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))  ## production environment (.py)
except NameError:
    scriptfolder = os.getcwd()  ## notebook environment

os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder')  # files are downloaded during the process

if os.path.exists(tempfolder):
    shutil.rmtree(tempfolder)
os.makedirs(tempfolder)

HEADLESS = True


#------------------------------------------------ Begin_chromedriver ----------------------------------------

def start_driver(download_dir):
    chromeOptions = Options()
    if HEADLESS:
        chromeOptions.add_argument('--headless=new')
    chromeOptions.add_argument('--no-sandbox')
    chromeOptions.add_argument('--disable-dev-shm-usage')
    chromeOptions.add_argument('--window-size=1600,1400')
    prefs = {"plugins.always_open_pdf_externally": True,
             "download.prompt_for_download": False,
             "download.default_directory": download_dir,
             'profile.default_content_setting_values.automatic_downloads': 1}
    chromeOptions.add_experimental_option("prefs", prefs)
    drv = webdriver.Chrome(options=chromeOptions)
    try:
        drv.execute_cdp_cmd('Page.setDownloadBehavior',
                            {'behavior': 'allow', 'downloadPath': download_dir})
    except Exception:
        pass
    return drv


#------------------------------------------------ Begin_Variable ----------------------------------------

# ListNr -> ListName / URL / Comments  (parsed from the Jira subtask description table)
regdict = {
    1: {"ListName": "Conglomerados",
        "URL": "https://www.bcb.gov.br/estabilidadefinanceira/relacao_instituicoes_funcionamento",
        "Comments": 'Please select the corresponding list, choose the latest date available and click in "Baixar arquivo".'},
    2: {"ListName": "Bancos comerciais, múltiplos e Caixa Econômica",
        "URL": "https://www.bcb.gov.br/estabilidadefinanceira/relacao_instituicoes_funcionamento",
        "Comments": 'Please select the corresponding list, choose the latest date available and click in "Baixar arquivo".'},
    3: {"ListName": "Cooperativas de crédito",
        "URL": "https://www.bcb.gov.br/estabilidadefinanceira/relacao_instituicoes_funcionamento",
        "Comments": 'Please select the corresponding list, choose the latest date available and click in "Baixar arquivo".'},
    4: {"ListName": "Bancos de Investimento, Bancos de Desenvolvimento, Sociedades Corretoras de TVM e Câmbio, "
                    "Sociedades Distribuidoras de TVM, Sociedades de Crédito, Financiamento e Investimento, "
                    "Sociedades de Crédito Imobiliário e APE, Sociedades de Arrendamento Mercantil, "
                    "Sociedades de Investimento, Sociedades de Crédito ao Microempreendedor, Agências de Fomento, "
                    "Companhias Hipotecárias e Instituições de Pagamento",
        "URL": "https://www.bcb.gov.br/estabilidadefinanceira/relacao_instituicoes_funcionamento",
        "Comments": 'Please select the corresponding list, choose the latest date available and click in "Baixar arquivo".'},
    5: {"ListName": "Administradoras de consórcios",
        "URL": "https://www.bcb.gov.br/estabilidadefinanceira/relacao_instituicoes_funcionamento",
        "Comments": 'Please select the corresponding list, choose the latest date available and click in "Baixar arquivo".'},
    8: {"ListName": "Supervised institutions - Foreign Institutions in Brazil",
        "URL": "https://www.bcb.gov.br/en/statistics/evolutionmonthnfs",
        "Comments": "BR BCB 8 is chart 10 - Representative of Foreign institutions in the Country"},
}

# The 5 ng-select widgets on the "relacao_instituicoes_funcionamento" page appear in this order.
# Verified against the <h*> heading that sits above each widget.
NGSELECT_ORDER = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5}

Typology = {k: v['ListName'] for k, v in regdict.items()}

# ListLabel = 1 bank / 2 insurance / 3 bank & insurance / 4 everything else
ListLabel = {1: 1, 2: 1, 3: 1, 4: 1, 5: 4, 8: 1}

ListLanguage = {1: 'PT', 2: 'PT', 3: 'PT', 4: 'PT', 5: 'PT', 8: 'EN'}

sqldict={'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
          'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
          'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
          'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
          'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
          'Phone - Mother company': []}

SQL_COLUMNS = list(sqldict.keys())

ISO= {"": "", 'NAN': '', 'OTHER': '', "AFGHANISTAN": "AF", "ÅLAND ISLANDS": "AX", "ALBANIA": "AL", "ALGERIA": "DZ", "AMERICAN SAMOA": "AS", "ANDORRA": "AD", "ANGOLA": "AO", "ANGUILLA": "AI", "ANTARCTICA": "AQ", "ANTIGUA AND BARBUDA": "AG", "ARGENTINA": "AR", "ARMENIA": "AM", "ARUBA": "AW", "AUSTRALIA": "AU", "AUSTRIA": "AT", "AZERBAIJAN": "AZ", "BAHAMAS, THE": "BS", "BAHRAIN": "BH", "BANGLADESH": "BD", "BARBADOS": "BB", "BELARUS": "BY", "BELGIUM": "BE", "BELIZE": "BZ", "BENIN": "BJ", "BERMUDA": "BM", "BHUTAN": "BT", "BOLIVIA": "BO", "BONAIRE, SINT EUSTATIUS AND SABA": "BQ", "BOSNIA AND HERZEGOVINA": "BA", "BOTSWANA": "BW", "BOUVET ISLAND": "BV", "BRAZIL": "BR", "BRITISH INDIAN OCEAN TERRITORY": "IO", "BRUNEI": "BN", "BULGARIA": "BG", "BURKINA FASO": "BF", "BURUNDI": "BI", "CABO VERDE": "CV", "CAMBODIA": "KH", "CAMEROON, UNITED REPUBLIC OF": "CM", "CANADA": "CA", "CAYMAN ISLANDS": "KY", "CENTRAL AFRICAN REPUBLIC": "CF", "CHAD": "TD", "CHILE": "CL", "CHINA, PEOPLES REPUBLIC OF": "CN","CHINA": "CN", "CHRISTMAS ISLAND": "CX", "COCOS (KEELING) ISLANDS": "CC", "COLOMBIA": "CO", "COMOROS": "KM", "CONGO": "CG", "CONGO, DEMOCRATIC REPUBLIC OF THE": "CD", "COOK ISLANDS": "CK", "COSTA RICA": "CR", "CÔTE D'IVOIRE": "CI", "CROATIA": "HR", "CUBA": "CU", "CURACAO, BONAIRE, SABA, ST. MARTIN & ST.": "CW", "CYPRUS": "CY", "CZECH REPUBLIC": "CZ", "DENMARK": "DK", "DJIBOUTI": "DJ", "DOMINICA": "DM", "DOMINICAN REPUBLIC": "DO", "ECUADOR": "EC", "EGYPT": "EG", "EL SALVADOR": "SV", "EQUATORIAL GUINEA": "GQ", "ERITREA": "ER", "ESTONIA": "EE", "ESWATINI": "SZ", "ETHIOPIA": "ET", "FALKLAND ISLANDS (MALVINAS)": "FK", "FAROE ISLANDS": "FO", "FIJI": "FJ", "FINLAND": "FI", "FRANCE": "FR", "FRENCH GUIANA": "GF", "FRENCH POLYNESIA": "PF", "FRENCH SOUTHERN TERRITORIES": "TF", "GABON": "GA", "GAMBIA": "GM", "GEORGIA": "GE", 'GEORGIA/GRUZINSKAYA': 'GE', "GERMANY": "DE", "GHANA": "GH", "GIBRALTAR": "GI", "GREECE": "GR", "GREENLAND": "GL", "GRENADA": "GD", "GUADELOUPE": "GP", "GUAM": "GU", "GUATEMALA": "GT", "GUERNSEY": "GG", "GUINEA": "GN", "GUINEA-BISSAU": "GW", "GUYANA": "GY", "HAITI": "HT", "HEARD ISLAND AND MCDONALD ISLANDS": "HM", "HOLY SEE": "VA", "HONDURAS": "HN", "HONG KONG": "HK", "HUNGARY": "HU", "ICELAND": "IS", "INDIA": "IN", "INDONESIA": "ID", "IRAN": "IR", "IRAQ": "IQ", "IRELAND": "IE", "ISLE OF MAN": "IM", "ISRAEL": "IL", "ITALY": "IT", "JAMAICA": "JM", "JAPAN": "JP", "JERSEY": "JE", "JORDAN": "JO", "KAZAKHSTAN": "KZ", "KENYA": "KE", "KIRIBATI": "KI", """KOREA (DEMOCRATIC PEOPLE'S REPUBLIC OF)""": "KP", "KOREA, SOUTH": "KR", "SOUTH KOREA": "KR", "KUWAIT": "KW", "KYRGYZSTAN": "KG", "LAO PEOPLE'S DEMOCRATIC REPUBLIC": "LA", "LATVIA": "LV", "LEBANON": "LB", "LESOTHO": "LS", "LIBERIA": "LR", "LIBYA": "LY", "LIECHTENSTEIN": "LI", "LITHUANIA": "LT", "LUXEMBOURG": "LU", "MACAU": "MO", "MADAGASCAR": "MG", "MALAWI": "MW", "MALAYSIA": "MY", "MALDIVES": "MV", "MALI": "ML", "MALTA": "MT", "MARSHALL ISLANDS": "MH", "MARTINIQUE": "MQ", "MAURITANIA": "MR", "MAURITIUS": "MU", "MAYOTTE": "YT", "MEXICO": "MX", "FEDERATED STATES OF MICRONESIA": "FM", "MOLDOVA, REPUBLIC OF": "MD", "MONACO": "MC", "MONGOLIA": "MN", "MONTENEGRO": "ME", "MONTSERRAT": "MS", "MOROCCO": "MA", "MOZAMBIQUE": "MZ", "MYANMAR": "MM", "NAMIBIA": "NA", "NAURU": "NR", "NEPAL": "NP", "NETHERLANDS": "NL", "NEW CALEDONIA": "NC", "NEW ZEALAND": "NZ", "NICARAGUA": "NI", "NIGER": "NE", "NIGERIA": "NG", "NIUE": "NU", "NORFOLK ISLAND": "NF", "NORTH MACEDONIA": "MK", "NORTHERN MARIANA ISLANDS": "MP", "NORWAY": "NO", "OMAN": "OM", "PAKISTAN": "PK", "PALAU": "PW", "PALESTINE, STATE OF": "PS", "PANAMA": "PA", "PAPUA NEW GUINEA": "PG", "PARAGUAY": "PY", "PERU": "PE", "PHILIPPINES": "PH", "PITCAIRN": "PN", "POLAND": "PL", "PORTUGAL": "PT", "PUERTO RICO": "PR", "QATAR": "QA", "RÉUNION": "RE", "ROMANIA": "RO", "RUSSIA": "RU", "RWANDA": "RW", "SAINT BARTHÉLEMY": "BL", "SAINT HELENA, ASCENSION AND TRISTAN DA CUNHA": "SH", "SAINT KITTS AND NEVIS": "KN", "SAINT LUCIA": "LC", "SAINT MARTIN (FRENCH PART)": "MF", "SAINT PIERRE AND MIQUELON": "PM", "SAINT VINCENT AND THE GRENADINES": "VC", "SAMOA": "WS", "SAN MARINO": "SM", "SAO TOME AND PRINCIPE": "ST", "SAUDI ARABIA": "SA", "SENEGAL": "SN", "SERBIA": "RS", "SEYCHELLES": "SC", "SIERRA LEONE": "SL", "SINGAPORE": "SG", "SINT MAARTEN (DUTCH PART)": "SX", "SLOVAKIA": "SK", "SLOVAK REPUBLIC": "SK", "SLOVENIA": "SI", "SOLOMON ISLANDS": "SB", "SOMALIA": "SO", "SOUTH AFRICA": "ZA", "SOUTH GEORGIA AND THE SOUTH SANDWICH ISLANDS": "GS", "SOUTH SUDAN": "SS", "SPAIN": "ES", "SRI LANKA": "LK", "SUDAN": "SD", "SURINAME": "SR", "SVALBARD AND JAN MAYEN": "SJ", "SWEDEN": "SE", "SWITZERLAND": "CH", "SYRIAN ARAB REPUBLIC": "SY", "TAIWAN": "TW",'TAIWAN,  REPUBLIC OF CHINA': 'TW' ,"TAJIKISTAN": "TJ", "TANZANIA, UNITED REPUBLIC OF": "TZ", "THAILAND": "TH", "TIMOR-LESTE": "TL", "TOGO": "TG", "TOKELAU": "TK", "TONGA": "TO", "TRINIDAD AND TOBAGO": "TT", "TUNISIA": "TN", "TURKEY": "TR", "TURKMENISTAN": "TM", "TURKS & CAICOS ISLANDS": "TC", "TUVALU": "TV", "UGANDA": "UG", "UKRAINE": "UA", "UNITED ARAB EMIRATES": "AE", "UNITED KINGDOM OF GREAT BRITAIN AND NORTHERN IRELAND": "GB", "UNITED STATES": "US", 'USA': 'US', "UNITED STATES MINOR OUTLYING ISLANDS": "UM", "URUGUAY": "UY", "UZBEKISTAN": "UZ", "VANUATU": "VU", "VENEZUELA": "VE", "VIETNAM": "VN", "BRITISH VIRGIN ISLANDS": "VG", "VIRGIN ISLANDS OF THE U.S.": "VI", "WALLIS AND FUTUNA": "WF", "WESTERN SAHARA": "EH", "YEMEN": "YE", "ZAMBIA": "ZM", "ZIMBABWE": "ZW", "ENGLAND": "GB", "UNITED KINGDOM": "GB", "UNITED KINGDOM (OTHER)": "GB", "FRANCE (OTHER)": "FR", "WALES": "GB", "CONGO (KINSHASA)": "CD", "CONGO (BRAZZAVILLE)": "CD", "SCOTLAND": "GB", "ITALY (OTHER)": "IT", "INDONESIA (OTHER)": "ID", "INDIA (OTHER)": "IN", "MOROCCO (OTHER)": "MA", "NEW ZEALAND (OTHER)": "NZ", "SWITZERLAND (OTHER)": "CH", "MALAYSIA (OTHER)": "MY", "NETHERLANDS ANTILLES": "AN", "TRINIDAD & TOBAGO (OTHER)": "TT", "CHANNEL ISLANDS": "GB", "UNITED ARAB EMIRATES (OTHER)": "AE", "DENMARK (OTHER)": "DK", "COMORO ISLANDS": "KM", "MACEDONIA (FORMER YUGOSLAV REPUBLIC OF)": "MK", "SERBIA AND MONTENEGRO(FORMER YUGOSLAVIA)": "CS", "TRINIDAD": "TT", "ETHIOPIA (OTHER)": "ET", "IVORY COAST": "CI", "DUBAI": "AE", "BRITISH WEST INDIES (OTHER)": "VG", "SWAZILAND": "SZ", 'UNITED KINGDOM  (OTHER)': 'GB','BAHAMAS':'BS'}

processdate = now.strftime('%Y-%m-%d')

HTTP_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                              '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'}


#------------------------------------------------ Begin_Fouction ----------------------------------------

def norm(text):
    """Accent-stripped, whitespace-collapsed, upper-cased key used to match column headers."""
    text = unicodedata.normalize('NFKD', str(text))
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r'\s+', ' ', text).strip().upper()


def clean(value):
    """Trim the fixed-width padding BCB ships in every cell."""
    if value is None:
        return ''
    text = str(value)
    if text.lower() in ('nan', 'nat', 'none'):
        return ''
    text = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    return re.sub(r'\s+', ' ', text).strip()


def add_row(**kwargs):
    """Append one aligned record; every sqldict key always grows by exactly one."""
    for key in SQL_COLUMNS:
        sqldict[key].append(kwargs.get(key, ''))


def join_parts(*parts, **kwargs):
    sep = kwargs.get('sep', ', ')
    return sep.join([p for p in [clean(x) for x in parts] if p])


def format_cnpj(value):
    """BCB publishes the 8-digit CNPJ root, dotted on some lists ('00.000.000') and bare on others.

    Strip the formatting so InternalID_1 is comparable across all six lists.
    """
    text = clean(value)
    digits = re.sub(r'\D', '', text)
    return digits if digits else text


def format_zip(value):
    digits = re.sub(r'\D', '', clean(value))
    if len(digits) == 8:
        return digits[:5] + '-' + digits[5:]
    return clean(value)


def format_phone(ddd, number):
    """BCB stores DDD and the subscriber number zero-padded in separate columns."""
    area = clean(ddd).lstrip('0')
    num = clean(number).lstrip('0')
    if not num:
        return ''
    if not area:
        return num
    if area in ('800', '300', '500'):        # non-geographic prefixes
        return '0{} {}'.format(area, num)
    return '({}) {}'.format(area, num)


def iso_country(name):
    key = norm(name)
    if key in ISO:
        return ISO[key]
    return clean(name)


def parse_position_date(raw):
    """'Posição: 30.6.2026' -> '2026-06-30'   |   'Position: 05.31.2026' -> '2026-05-31'"""
    text = clean(raw)
    m = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', text)
    if not m:
        return ''
    a, b, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    day, month = (a, b) if a > 12 else (b, a)   # PT files are d.m.Y, the EN chart file is m.d.Y
    try:
        return datetime.date(year, month, day).strftime('%Y-%m-%d')
    except ValueError:
        return ''


def parse_iso_date(raw):
    text = clean(raw)
    if not text:
        return ''
    try:
        return pd.to_datetime(text).strftime('%Y-%m-%d')
    except Exception:
        return text


def click_on_cookies(web_driver):
    for xpath in ["//button[contains(.,'Aceitar cookies')]",
                  "//button[contains(.,'Accept cookies')]",
                  "//*[@class='msg-cookies card border-0']//button[last()]"]:
        try:
            element = web_driver.find_element(By.XPATH, xpath)
            web_driver.execute_script("arguments[0].click();", element)
            print('[INFO] : - Click cookies')
            sleep(2)
            return
        except Exception:
            continue
    print('[INFO] : - No cookie banner found')


def check_dowload_files(folder, fileType, timeout=90):
    """Wait until a completed (non .crdownload) file of a stable size lands in folder."""
    last_size = -1
    for attempt in range(timeout // 2):
        files = [f for f in os.listdir(folder) if not f.endswith(('.crdownload', '.tmp'))]
        if files:
            size = os.path.getsize(os.path.join(folder, files[0]))
            if size > 0 and size == last_size:
                print('[INFO] : - {} file = {}'.format(fileType, files))
                return os.path.join(folder, files[0])
            last_size = size
        else:
            print('[INFO] : - Download {} file ... (wait {}/{} s)'.format(fileType, attempt * 2, timeout))
        sleep(2)
    raise Exception('[ERROR] : - Failed to Download {} file. Run Script again'.format(fileType))


def read_bcb_sheet(path):
    """BCB institution workbooks: 9 banner rows, then the header row, then data, then a FONTE footer.

    Returns (DataFrame with normalised column keys, position date string).
    """
    raw = pd.read_excel(path, sheet_name=0, header=None, dtype=str)

    validity = ''
    for value in raw.iloc[:9, 0].tolist():
        parsed = parse_position_date(value)
        if parsed:
            validity = parsed
            break

    header_idx = None
    for i in range(len(raw)):
        if raw.iloc[i].notna().sum() >= 3:
            header_idx = i
            break
    if header_idx is None:
        raise Exception('[ERROR] : - Could not locate the header row in {}'.format(path))

    columns = [norm(c) for c in raw.iloc[header_idx].tolist()]
    data = raw.iloc[header_idx + 1:].copy()
    data.columns = columns
    data = data.loc[:, [c for c in columns if c and c != 'NAN']]

    # drop the trailing "FONTE: ..." note and any fully blank separator rows
    first_col = data.columns[0]
    data = data[data[first_col].notna()]
    data = data[~data[first_col].astype(str).str.upper().str.strip().str.startswith('FONTE')]
    data = data.fillna('')
    data.reset_index(drop=True, inplace=True)
    return data, validity


def col(data, *names):
    """Exact-match column lookup over normalised header keys; '' when absent."""
    for name in names:
        if name in data.columns:
            return data[name]
    return pd.Series([''] * len(data), index=data.index)


def download_lists_1_to_5(folder):
    """Drive the Angular page: for each of the 5 widgets pick the newest date and download the ZIP.

    Returns {ListNr: path_to_xlsx}.
    """
    results = {}
    driver = start_driver(folder)
    try:
        driver.get(regdict[1]['URL'])
        sleep(12)
        click_on_cookies(driver)

        WebDriverWait(driver, 30).until(
            EC.presence_of_all_elements_located((By.TAG_NAME, 'ng-select')))
        selects = driver.find_elements(By.TAG_NAME, 'ng-select')
        buttons = driver.find_elements(By.XPATH, "//button[contains(normalize-space(.),'Baixar arquivo')]")
        print('[INFO] : - Found {} ng-select widgets and {} download buttons'.format(len(selects), len(buttons)))
        if len(selects) != 5 or len(buttons) != 5:
            raise Exception('[ERROR] : - Page layout changed: expected 5 selects/buttons, '
                            'got {}/{}'.format(len(selects), len(buttons)))

        for index in sorted(NGSELECT_ORDER):
            listnr = NGSELECT_ORDER[index]
            print('[INFO] : - Processing {} {}'.format(regulatorName, listnr))

            work = os.path.join(folder, 'list{}'.format(listnr))
            if os.path.exists(work):
                shutil.rmtree(work)
            os.makedirs(work)
            driver.execute_cdp_cmd('Page.setDownloadBehavior',
                                   {'behavior': 'allow', 'downloadPath': work})

            # the dropdown only opens when the inner container is clicked
            container = selects[index].find_element(By.CSS_SELECTOR, '.ng-select-container')
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", container)
            sleep(1)
            container.click()
            sleep(2)

            options = WebDriverWait(driver, 20).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, 'ng-dropdown-panel .ng-option')))
            newest = options[0].text.strip()          # options are sorted newest first
            print('[INFO] : -   latest available date = {}'.format(newest))
            driver.execute_script("arguments[0].click();", options[0])
            sleep(1.5)

            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", buttons[index])
            sleep(1)
            driver.execute_script("arguments[0].click();", buttons[index])

            archive = check_dowload_files(work, 'ZIP (list {})'.format(listnr))
            with zipfile.ZipFile(archive, 'r') as zip_ref:
                zip_ref.extractall(work)
                print('[INFO] : - Zip extraction file = {}'.format(zip_ref.filelist[0].filename))

            sheets = [f for f in os.listdir(work) if f.lower().endswith(('.xlsx', '.xls'))]
            if not sheets:
                raise Exception('[ERROR] : - No .xlsx found for list {}'.format(listnr))
            results[listnr] = os.path.join(work, sheets[0])
    finally:
        driver.quit()
    return results


def download_list_8(folder):
    """The monthly-statistics page publishes one 'Charts in spreadsheets' ZIP per month."""
    work = os.path.join(folder, 'list8')
    os.makedirs(work, exist_ok=True)

    links = []
    driver = start_driver(work)
    try:
        for year in (now.year, now.year - 1):
            driver.get('{}?ano={}'.format(regdict[8]['URL'], year))
            sleep(12)
            click_on_cookies(driver)
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            links = re.findall(r'https?://[^\s"\']*evolutionmonthnfs/z(\d{6})\.zip', str(soup))
            if links:
                break
    finally:
        driver.quit()

    if not links:
        raise Exception('[ERROR] : - No "Charts in spreadsheets" ZIP link found on the statistics page')

    latest = max(links)
    url = 'https://www.bcb.gov.br/content/statistics/evolutionmonthnfs/z{}.zip'.format(latest)
    print('[INFO] : - List 8 latest reference month = {} -> {}'.format(latest, url))

    response = requests.get(url, headers=HTTP_HEADERS, verify=False, timeout=180)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
        zip_ref.extractall(work)
        print('[INFO] : - Zip extraction file = {}'.format(zip_ref.filelist[0].filename))

    sheets = [f for f in os.listdir(work) if f.lower().endswith(('.xlsx', '.xls'))]
    if not sheets:
        raise Exception('[ERROR] : - No .xlsx found for list 8')
    return os.path.join(work, sheets[0])


#------------------------------------------------ Begin_Main ----------------------------------------

print('Working with lists 1-5')
paths = download_lists_1_to_5(tempfolder)

# ---------- List 1 : Conglomerados ----------
listnr = 1
data, validity = read_bcb_sheet(paths[listnr])
print('[INFO] : - List {} : {} rows (position {})'.format(listnr, len(data), validity))
for group, klass, cnpj, name, role, start, uf in zip(
        col(data, 'NOME DO CONGLOMERADO'),
        col(data, 'CLASSE DO CONGLOMERADO'),
        col(data, 'CNPJ PARTICIPANTE'),
        col(data, 'NOME DO PARTICIPANTE'),
        col(data, 'TIPO PARTICIPACAO'),
        col(data, 'DATA INICIO'),
        col(data, 'UF')):
    add_row(**{
        'ListLabel': ListLabel[listnr],
        'Typology': Typology[listnr],
        'Name': clean(name),
        'InternalID_1': format_cnpj(cnpj),
        'InternalID_1_type': 'CNPJ' if format_cnpj(cnpj) else '',
        'CoType': clean(klass),
        'License_Type': clean(role),
        'Address_2': clean(uf),
        'Cntry': 'BR',
        'RegulationType': 'Regulated',
        'RegulationDate': parse_iso_date(start),
        'RegCtry': 'BR',
        'RegCode': 'BCB',
        'ListCode': listnr,
        'ListLanguage': ListLanguage[listnr],
        'ListValidityDate': validity,
        'ListName': regdict[listnr]['ListName'],
        'ListProcessDate': processdate,
        'Name - Mother Company': clean(group),
    })

# ---------- Lists 2, 3, 4, 5 : institution directories ----------
for listnr in (2, 3, 4, 5):
    data, validity = read_bcb_sheet(paths[listnr])
    print('[INFO] : - List {} : {} rows (position {})'.format(listnr, len(data), validity))

    for i in range(len(data)):
        row = data.iloc[i]

        def cell(*names):
            for name in names:
                if name in data.columns:
                    return clean(row[name])
            return ''

        name = cell('NOME INSTITUICAO')
        segment = cell('SEGMENTO')
        klass = cell('CLASSE')                       # cooperatives: Singular / Central / Confederacao
        criterion = cell('CRITERIO DE ASSOCIACAO')   # cooperatives
        category = cell('CATEG COOP SING')           # cooperatives
        affiliation = cell('FILIACAO')               # cooperatives -> central body
        commercial = cell('CART COMERCIAL')          # banks: commercial portfolio Sim/Nao

        license_bits = [b for b in (category, criterion) if b]
        if commercial:
            license_bits.append('Carteira Comercial: {}'.format(commercial))

        add_row(**{
            'ListLabel': ListLabel[listnr],
            'Typology': Typology[listnr],
            'EntryType': 'Head Office',
            'Name': name,
            'InternalID_1': format_cnpj(cell('CNPJ')),
            'InternalID_1_type': 'CNPJ' if format_cnpj(cell('CNPJ')) else '',
            'InternalID_2': cell('MUNICIPIO IBGE'),
            'InternalID_2_type': 'IBGE Municipality Code' if cell('MUNICIPIO IBGE') else '',
            'CoType': segment or klass or ('Administradora de Consórcio' if listnr == 5 else ''),
            'License_Type': ' | '.join(license_bits),
            'Address_1': cell('ENDERECO'),
            'Address_2': join_parts(cell('COMPLEMENTO'), cell('BAIRRO'), cell('UF')),
            'City': cell('MUNICIPIO', 'MUNICIPIO ', 'CIDADE'),
            'Zip': format_zip(cell('CEP')),
            'Cntry': 'BR',
            'Phone': format_phone(cell('DDD'), cell('TELEFONE', 'FONE')),
            'Website': cell('SITIO NA INTERNET'),
            'Email': cell('E-MAIL'),
            'RegulationType': 'Regulated',
            'RegCtry': 'BR',
            'RegCode': 'BCB',
            'ListCode': listnr,
            'ListLanguage': ListLanguage[listnr],
            'ListValidityDate': validity,
            'ListName': regdict[listnr]['ListName'],
            'ListProcessDate': processdate,
            'Name - Mother Company': affiliation,
        })

# ---------- List 8 : chart 10, representatives of foreign institutions ----------
listnr = 8
print('Working with list {} {}'.format(regulatorName, listnr))
chart_path = download_list_8(tempfolder)

sheet = None
for candidate in ('chart 10', 'quadro 10', 'Chart 10', 'Quadro 10'):
    try:
        sheet = pd.read_excel(chart_path, sheet_name=candidate, header=None, dtype=str)
        print('[INFO] : - Using sheet "{}"'.format(candidate))
        break
    except Exception:
        continue
if sheet is None:
    raise Exception('[ERROR] : - Neither "chart 10" nor "quadro 10" found in {}'.format(chart_path))

validity = ''
for value in sheet.iloc[:8].values.ravel().tolist():
    parsed = parse_position_date(value)
    if parsed:
        validity = parsed
        break

# exact cell match, otherwise the "Chart 10 - Representatives of Foreign Institutions ..." title row wins
header_idx = None
for i in range(len(sheet)):
    if 'FOREIGN INSTITUTION' in [norm(v) for v in sheet.iloc[i].tolist()]:
        header_idx = i
        break
if header_idx is None:
    raise Exception('[ERROR] : - Could not locate the chart 10 header row')

columns = [norm(c) for c in sheet.iloc[header_idx].tolist()]
chart = sheet.iloc[header_idx + 1:].copy()
chart.columns = columns
chart = chart.loc[:, [c for c in columns if c and c != 'NAN']]
chart = chart[chart['FOREIGN INSTITUTION'].notna()]
# drop the "Source: Unicad" / "Obs.: 1/ ..." footnotes
chart = chart[~chart['FOREIGN INSTITUTION'].astype(str).str.upper().str.strip()
              .str.startswith(('SOURCE', 'OBS', 'FONTE'))]
chart = chart.fillna('')
chart.reset_index(drop=True, inplace=True)
print('[INFO] : - List {} : {} rows (position {})'.format(listnr, len(chart), validity))

for i in range(len(chart)):
    row = chart.iloc[i]

    def cell8(*names):
        for name in names:
            if name in chart.columns:
                return clean(row[name])
        return ''

    person_type = cell8('TIPO DE PESSOA')            # Juridica (company) / Fisica (individual)
    document = cell8('CPF/CNPJ')
    representative = cell8('NAME OF REPRESENTATIVE')

    add_row(**{
        'ListLabel': ListLabel[listnr],
        'Typology': Typology[listnr],
        'EntryType': 'Representative: {}'.format(representative) if representative else 'Representative',
        'Name': cell8('FOREIGN INSTITUTION'),
        'InternalID_1': format_cnpj(document),
        'InternalID_1_type': ('CPF' if person_type.upper().startswith('F') else 'CNPJ') if document else '',
        'CoType': person_type,
        'License_Type': 'Representative Office',
        'Address_1': cell8('LOGRAD PRINCIPAL'),
        'Address_2': join_parts(cell8('ENDERECO PRINCIPAL'), cell8('BAIRRO PRINCIPAL'), cell8('UF PRINCIPAL')),
        'City': cell8('MUNICIPALITY', 'MUNICIPIO PRINCIPAL'),
        'Zip': format_zip(cell8('CEP PRINCIPAL')),
        'Cntry': iso_country(cell8('COUNTRY OF ORIGIN')),
        'Phone': cell8('TEL_COM'),
        'RegulationType': 'Regulated',
        'RegCtry': 'BR',
        'RegCode': 'BCB',
        'ListCode': listnr,
        'ListLanguage': ListLanguage[listnr],
        'ListValidityDate': validity,
        'ListName': regdict[listnr]['ListName'],
        'ListProcessDate': processdate,
    })


#------------------------------------------------ Begin_writer and save df to excel  ----------------------------------------

os.chdir(scriptfolder)

df = pd.DataFrame(sqldict)

df = df[df['Name'] != '']

df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)

print('Saved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))
print(df.groupby('ListCode').size().to_string())

shutil.rmtree(tempfolder, ignore_errors=True)
