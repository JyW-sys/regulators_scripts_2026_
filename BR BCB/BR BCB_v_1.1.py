# %%

#------------------------------------------------ Begin_Librairie ----------------------------------------

from selenium import webdriver

from selenium.webdriver.common.keys import Keys

from selenium.webdriver.common.by import By

from bs4 import BeautifulSoup

import zipfile

import pandas as pd

from pandas import ExcelWriter

import datetime

from selenium import webdriver

from time import sleep

import re

import os



from selenium.webdriver.chrome.service import Service as ChromeService

from webdriver_manager.chrome import ChromeDriverManager



# %%

#------------------------------------------------ Begin_ fileName ----------------------------------------

regulatorName = 'BR BCB' ## change to current controller name

print(f"Running {regulatorName} Web Scraping Tool v.1.1")

now=datetime.datetime.now()

filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":",".")[:-7])

#scriptfolder = f"C:\\Users\\siewekoa\\OneDrive - moodys.com\\Desktop\\My_data\\Project_work\\scripts_regulator\\{regulatorName}" ## to comment for the production environment

scriptfolder=os.path.dirname(os.path.abspath(__file__)) ## to decomment for the production environment

os.chdir(scriptfolder)

writer = ExcelWriter(filename)

tempfolder=os.path.join(scriptfolder, 'tempfolder') #if files are downloaded during the process



if os.path.exists(tempfolder):

    for rem in os.listdir(tempfolder):

        os.remove(os.path.join(tempfolder, rem))

else:

    os.mkdir(tempfolder)



# %%

#------------------------------------------------ Begin_chromedriver ----------------------------------------

#Starting Chrome driver, set to download files in tempfolder

chromeOptions = webdriver.ChromeOptions()

prefs = {"plugins.always_open_pdf_externally": True,

		 "download.prompt_for_download": False,

		 "download.default_directory" : tempfolder}

chromeOptions.add_experimental_option("prefs",prefs)



#driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chromeOptions )

#driver = webdriver.Chrome(executable_path="..\\chromedriver.exe",options=chromeOptions)

driver = webdriver.Chrome(options=chromeOptions)

driver.maximize_window()





# %%

#------------------------------------------------ Begin_Variable ----------------------------------------

regdict={'BR BCB 1': ['conglomerado', 'conglomerado'], 

		 'BR BCB 2': ['banco', 'banco'], 

		 'BR BCB 3': ['cooperativa', 'cooperativa'], 

		 'BR BCB 4': ['sociedade', 'sociedade'], 

		 'BR BCB 5': ['admConsorcio', 'consorcio'], 

		 'BR BCB 8': ['https://www.bcb.gov.br/en/statistics/evolutionmonthnfs'] }

#regdict={ 'BR BCB 8': ['https://www.bcb.gov.br/en/statistics/evolutionmonthnfs'], 'BR BCB 4': ['sociedade', 'sociedade']}



sqldict={'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [], 

		  'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [], 

		  'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [], 

		  'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],

		  'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [], 

		  'Phone - Mother company': [], 'Check': []}



ISO= {"": "", 'NAN': '', 'OTHER': '', "AFGHANISTAN": "AF", "ÅLAND ISLANDS": "AX", "ALBANIA": "AL", "ALGERIA": "DZ", "AMERICAN SAMOA": "AS", "ANDORRA": "AD", "ANGOLA": "AO", "ANGUILLA": "AI", "ANTARCTICA": "AQ", "ANTIGUA AND BARBUDA": "AG", "ARGENTINA": "AR", "ARMENIA": "AM", "ARUBA": "AW", "AUSTRALIA": "AU", "AUSTRIA": "AT", "AZERBAIJAN": "AZ", "BAHAMAS, THE": "BS", "BAHRAIN": "BH", "BANGLADESH": "BD", "BARBADOS": "BB", "BELARUS": "BY", "BELGIUM": "BE", "BELIZE": "BZ", "BENIN": "BJ", "BERMUDA": "BM", "BHUTAN": "BT", "BOLIVIA": "BO", "BONAIRE, SINT EUSTATIUS AND SABA": "BQ", "BOSNIA AND HERZEGOVINA": "BA", "BOTSWANA": "BW", "BOUVET ISLAND": "BV", "BRAZIL": "BR", "BRITISH INDIAN OCEAN TERRITORY": "IO", "BRUNEI": "BN", "BULGARIA": "BG", "BURKINA FASO": "BF", "BURUNDI": "BI", "CABO VERDE": "CV", "CAMBODIA": "KH", "CAMEROON, UNITED REPUBLIC OF": "CM", "CANADA": "CA", "CAYMAN ISLANDS": "KY", "CENTRAL AFRICAN REPUBLIC": "CF", "CHAD": "TD", "CHILE": "CL", "CHINA, PEOPLES REPUBLIC OF": "CN","CHINA": "CN", "CHRISTMAS ISLAND": "CX", "COCOS (KEELING) ISLANDS": "CC", "COLOMBIA": "CO", "COMOROS": "KM", "CONGO": "CG", "CONGO, DEMOCRATIC REPUBLIC OF THE": "CD", "COOK ISLANDS": "CK", "COSTA RICA": "CR", "CÔTE D'IVOIRE": "CI", "CROATIA": "HR", "CUBA": "CU", "CURACAO, BONAIRE, SABA, ST. MARTIN & ST.": "CW", "CYPRUS": "CY", "CZECH REPUBLIC": "CZ", "DENMARK": "DK", "DJIBOUTI": "DJ", "DOMINICA": "DM", "DOMINICAN REPUBLIC": "DO", "ECUADOR": "EC", "EGYPT": "EG", "EL SALVADOR": "SV", "EQUATORIAL GUINEA": "GQ", "ERITREA": "ER", "ESTONIA": "EE", "ESWATINI": "SZ", "ETHIOPIA": "ET", "FALKLAND ISLANDS (MALVINAS)": "FK", "FAROE ISLANDS": "FO", "FIJI": "FJ", "FINLAND": "FI", "FRANCE": "FR", "FRENCH GUIANA": "GF", "FRENCH POLYNESIA": "PF", "FRENCH SOUTHERN TERRITORIES": "TF", "GABON": "GA", "GAMBIA": "GM", "GEORGIA": "GE", 'GEORGIA/GRUZINSKAYA': 'GE', "GERMANY": "DE", "GHANA": "GH", "GIBRALTAR": "GI", "GREECE": "GR", "GREENLAND": "GL", "GRENADA": "GD", "GUADELOUPE": "GP", "GUAM": "GU", "GUATEMALA": "GT", "GUERNSEY": "GG", "GUINEA": "GN", "GUINEA-BISSAU": "GW", "GUYANA": "GY", "HAITI": "HT", "HEARD ISLAND AND MCDONALD ISLANDS": "HM", "HOLY SEE": "VA", "HONDURAS": "HN", "HONG KONG": "HK", "HUNGARY": "HU", "ICELAND": "IS", "INDIA": "IN", "INDONESIA": "ID", "IRAN": "IR", "IRAQ": "IQ", "IRELAND": "IE", "ISLE OF MAN": "IM", "ISRAEL": "IL", "ITALY": "IT", "JAMAICA": "JM", "JAPAN": "JP", "JERSEY": "JE", "JORDAN": "JO", "KAZAKHSTAN": "KZ", "KENYA": "KE", "KIRIBATI": "KI", """KOREA (DEMOCRATIC PEOPLE'S REPUBLIC OF)""": "KP", "KOREA, SOUTH": "KR", "SOUTH KOREA": "KR", "KUWAIT": "KW", "KYRGYZSTAN": "KG", "LAO PEOPLE'S DEMOCRATIC REPUBLIC": "LA", "LATVIA": "LV", "LEBANON": "LB", "LESOTHO": "LS", "LIBERIA": "LR", "LIBYA": "LY", "LIECHTENSTEIN": "LI", "LITHUANIA": "LT", "LUXEMBOURG": "LU", "MACAU": "MO", "MADAGASCAR": "MG", "MALAWI": "MW", "MALAYSIA": "MY", "MALDIVES": "MV", "MALI": "ML", "MALTA": "MT", "MARSHALL ISLANDS": "MH", "MARTINIQUE": "MQ", "MAURITANIA": "MR", "MAURITIUS": "MU", "MAYOTTE": "YT", "MEXICO": "MX", "FEDERATED STATES OF MICRONESIA": "FM", "MOLDOVA, REPUBLIC OF": "MD", "MONACO": "MC", "MONGOLIA": "MN", "MONTENEGRO": "ME", "MONTSERRAT": "MS", "MOROCCO": "MA", "MOZAMBIQUE": "MZ", "MYANMAR": "MM", "NAMIBIA": "NA", "NAURU": "NR", "NEPAL": "NP", "NETHERLANDS": "NL", "NEW CALEDONIA": "NC", "NEW ZEALAND": "NZ", "NICARAGUA": "NI", "NIGER": "NE", "NIGERIA": "NG", "NIUE": "NU", "NORFOLK ISLAND": "NF", "NORTH MACEDONIA": "MK", "NORTHERN MARIANA ISLANDS": "MP", "NORWAY": "NO", "OMAN": "OM", "PAKISTAN": "PK", "PALAU": "PW", "PALESTINE, STATE OF": "PS", "PANAMA": "PA", "PAPUA NEW GUINEA": "PG", "PARAGUAY": "PY", "PERU": "PE", "PHILIPPINES": "PH", "PITCAIRN": "PN", "POLAND": "PL", "PORTUGAL": "PT", "PUERTO RICO": "PR", "QATAR": "QA", "RÉUNION": "RE", "ROMANIA": "RO", "RUSSIA": "RU", "RWANDA": "RW", "SAINT BARTHÉLEMY": "BL", "SAINT HELENA, ASCENSION AND TRISTAN DA CUNHA": "SH", "SAINT KITTS AND NEVIS": "KN", "SAINT LUCIA": "LC", "SAINT MARTIN (FRENCH PART)": "MF", "SAINT PIERRE AND MIQUELON": "PM", "SAINT VINCENT AND THE GRENADINES": "VC", "SAMOA": "WS", "SAN MARINO": "SM", "SAO TOME AND PRINCIPE": "ST", "SAUDI ARABIA": "SA", "SENEGAL": "SN", "SERBIA": "RS", "SEYCHELLES": "SC", "SIERRA LEONE": "SL", "SINGAPORE": "SG", "SINT MAARTEN (DUTCH PART)": "SX", "SLOVAKIA": "SK", "SLOVAK REPUBLIC": "SK", "SLOVENIA": "SI", "SOLOMON ISLANDS": "SB", "SOMALIA": "SO", "SOUTH AFRICA": "ZA", "SOUTH GEORGIA AND THE SOUTH SANDWICH ISLANDS": "GS", "SOUTH SUDAN": "SS", "SPAIN": "ES", "SRI LANKA": "LK", "SUDAN": "SD", "SURINAME": "SR", "SVALBARD AND JAN MAYEN": "SJ", "SWEDEN": "SE", "SWITZERLAND": "CH", "SYRIAN ARAB REPUBLIC": "SY", "TAIWAN": "TW",'TAIWAN,  REPUBLIC OF CHINA': 'TW' ,"TAJIKISTAN": "TJ", "TANZANIA, UNITED REPUBLIC OF": "TZ", "THAILAND": "TH", "TIMOR-LESTE": "TL", "TOGO": "TG", "TOKELAU": "TK", "TONGA": "TO", "TRINIDAD AND TOBAGO": "TT", "TUNISIA": "TN", "TURKEY": "TR", "TURKMENISTAN": "TM", "TURKS & CAICOS ISLANDS": "TC", "TUVALU": "TV", "UGANDA": "UG", "UKRAINE": "UA", "UNITED ARAB EMIRATES": "AE", "UNITED KINGDOM OF GREAT BRITAIN AND NORTHERN IRELAND": "GB", "UNITED STATES": "US", 'USA': 'US', "UNITED STATES MINOR OUTLYING ISLANDS": "UM", "URUGUAY": "UY", "UZBEKISTAN": "UZ", "VANUATU": "VU", "VENEZUELA": "VE", "VIETNAM": "VN", "BRITISH VIRGIN ISLANDS": "VG", "VIRGIN ISLANDS OF THE U.S.": "VI", "WALLIS AND FUTUNA": "WF", "WESTERN SAHARA": "EH", "YEMEN": "YE", "ZAMBIA": "ZM", "ZIMBABWE": "ZW", "ENGLAND": "GB", "UNITED KINGDOM": "GB", "UNITED KINGDOM (OTHER)": "GB", "FRANCE (OTHER)": "FR", "WALES": "GB", "CONGO (KINSHASA)": "CD", "CONGO (BRAZZAVILLE)": "CD", "SCOTLAND": "GB", "ITALY (OTHER)": "IT", "INDONESIA (OTHER)": "ID", "INDIA (OTHER)": "IN", "MOROCCO (OTHER)": "MA", "NEW ZEALAND (OTHER)": "NZ", "SWITZERLAND (OTHER)": "CH", "MALAYSIA (OTHER)": "MY", "NETHERLANDS ANTILLES": "AN", "TRINIDAD & TOBAGO (OTHER)": "TT", "CHANNEL ISLANDS": "GB", "UNITED ARAB EMIRATES (OTHER)": "AE", "DENMARK (OTHER)": "DK", "COMORO ISLANDS": "KM", "MACEDONIA (FORMER YUGOSLAV REPUBLIC OF)": "MK", "SERBIA AND MONTENEGRO(FORMER YUGOSLAVIA)": "CS", "TRINIDAD": "TT", "ETHIOPIA (OTHER)": "ET", "IVORY COAST": "CI", "DUBAI": "AE", "BRITISH WEST INDIES (OTHER)": "VG", "SWAZILAND": "SZ", 'UNITED KINGDOM  (OTHER)': 'GB'}

STATES={'': '', 'NaN': '', 'AC': 'Rio Branco', 'AL': 'Maceió', 'AP': 'Macapá', 'AM': 'Manaus', 'BA': 'Salvador', 'CE': 'Fortaleza', 'DF': 'Brasília', 'ES': 'Vitória', 'GO': 'Goiânia', 'MA': 'São Luís', 'MT': 'Cuiabá', 'MS': 'Campo Grande', 'MG': 'Belo Horizonte', 'PA': 'Belém', 'PB': 'João Pessoa', 'PR': 'Curitiba', 'PE': 'Recife', 'PI': 'Teresina', 'RJ': 'Rio de Janeiro', 'RN': 'Natal', 'RS': 'Porto Alegre', 'RO': 'Porto Velho', 'RR': 'Boa Vista', 'SC': 'Florianópolis', 'SP': 'São Paulo', 'SE': 'Aracaju', 'TO': 'Palmas'}

processdate=now.strftime('%Y-%m-%d')



# %%

#------------------------------------------------ Begin_Fouction ----------------------------------------

def bourange_same_length_array(sqldict) :

    maxlen = len(sqldict['ListProcessDate'])

    for key, val in sqldict.items():

        if len(sqldict[key]) != maxlen:

            empty = []

            total_empty = maxlen - len(sqldict[key])

            for i in range(total_empty):

                empty.append('')

            sqldict[key]=sqldict[key]+empty

    return sqldict





def click_on_cookies(web_driver):

    try:

        try:

            web_driver.find_element(By.XPATH,f'//*[@class="msg-cookies card border-0"]//*/button[contains(text(),"Prosseguir")]').click()

        except:

            web_driver.find_element(By.XPATH,f'//*[@class="msg-cookies card border-0"]//*/button[contains(text(),"Continue")]').click()

        

        print("[INFO] : - Click cookies")



    except Exception as err:

        print('[ERROR] : - Failed to click "Prosseguir" button on the cookies banner:', err)





def check_dowload_files(tempfolder, fileType ):



    for time in range(10):

        if len([ele for ele in os.listdir(tempfolder) if '.crdownload' not in ele and '.tmp' not in ele]) != 0 :

            print(f"[INFO] : - {fileType} file = {os.listdir(tempfolder)})")

            break

        else:

            print(f"[INFO] : - Download {fileType} file ... (wait {time*2}/20 s)")

            sleep(2)

    else:

        raise Exception(f'[ERROR] : - Failed to Download {fileType} file. Run Script again' )





# %%

#------------------------------------------------ Begin_Main ----------------------------------------

for k, reg in enumerate(regdict):

	print(f"[INFO] : Working {k+1}/{len(regdict)} _({reg})_ ")

	driver.get('about:blank')

	sleep(2)

	namereg=[]

	if 'http' in regdict[reg][0]:## open chart sheet from zip file last file in list 

		for times in range(30):

			try:

				driver.get(regdict[reg][0])

				sleep(5)

				break

			except Exception as error:

				print(error)

				driver.get('about:blank')

				sleep(2)

		else:

			raise Exception('Failed to load list :' , reg)

		

		soup = BeautifulSoup(driver.page_source, 'html.parser')

		if soup.find('div', {'class':'msg-cookies card border-0'}):

			click_on_cookies(driver)



		sleep(2)

		zip_urls = [ele['href'] for ele in soup.find_all('a', href=True) if '.zip' in ele['href'].lower() and '20' in ele['href']]

		zip_numbers = [re.search(r'(20\d+)\.zip', ele) for ele in zip_urls]

		zip_numbers = [int(ele.group(1)) for ele in zip_numbers]

		zip_url = zip_urls[zip_numbers.index(max(zip_numbers))]

		driver.get(zip_url)



		check_dowload_files(tempfolder, "zip" )

		file = os.listdir(tempfolder)[0]

		filePath = os.path.join(tempfolder, file)



		with zipfile.ZipFile(filePath, 'r') as zip_ref:

			zip_ref.extractall(tempfolder)

			print(f"[INFO] : - Zip extraction file = {zip_ref.filelist[0].filename}")



		datafile=list(filter(lambda x: '.xlsx' in x  and 'Charts' in x, os.listdir(tempfolder)))

		filePath = os.path.join(tempfolder, datafile[0])

		filedf=pd.read_excel(filePath, sheet_name='chart 10', header=None, dtype=str)

		filedf.dropna(how='all', axis=1, inplace=True)

		filedf.dropna(subset= [2], inplace=True)

		filedf.fillna('', inplace=True)

		filedf.columns = filedf.iloc[0]

		filedf.columns=list(map(lambda x: str(x).strip(), filedf.columns))

		filedf = filedf[1:]

		filedf.replace('\n',' ', regex=True, inplace=True)

		filedf.replace('\r',' ', regex=True, inplace=True)

		filedf.replace('\t',' ', regex=True, inplace=True)

		filedf.replace('  ',' ', regex=True, inplace=True)

		filedf.replace('NaN','', regex=True, inplace=True)

		filedf.drop(filedf[filedf['Tipo de Pessoa']=='Física'].index, inplace=True)

		filedf.reset_index(drop=True, inplace=True)

		print(f'[INFO] : - DataFrame "{datafile[0]}" containe = {filedf.shape}')

		for column in filedf.columns:

			filedf[column].str.strip()

		for row in range(len(filedf['State'])):



			sqldict['Cntry'].append('BR')

			sqldict['ListProcessDate'].append(processdate)

			sqldict['RegCtry'].append(reg.split()[0])

			sqldict['RegCode'].append(reg.split()[1])

			sqldict['ListCode'].append(reg.split()[2])

			sqldict['RegulationType'].append('Regulated')



			sqldict['Name'].append(filedf['Name of Representative'][row].strip())

			sqldict['Name - Mother Company'].append(filedf['Foreign Institution'][row].strip())

			sqldict['Address_1'].append(filedf['Lograd Principal'][row].strip())

			sqldict['Address_2'].append(filedf['Endereço Principal'][row].strip())

			sqldict['Zip'].append(filedf['CEP Principal'][row].strip())

			sqldict['InternalID_1'].append(filedf['CPF/CNPJ'][row].strip())

			sqldict['InternalID_1_type'].append('CNPJ Number')

			try:

				sqldict['Cntry - Mother company'].append(ISO[filedf['Country of Origin'][row].strip()])

			except:

				print('[ERROR] : - Failed to append ISO code (Mother Company): ', filedf['Country of Origin'][row])

				sqldict['Cntry - Mother company'].append('')

			for key in sqldict.keys():

				if len(sqldict[key])<len(sqldict['ListProcessDate']):

					sqldict[key].append('')

		#print(filedf.columns.tolist())

	else:

		for times in range(30):

			try:

				driver.get('https://www.bcb.gov.br/estabilidadefinanceira/relacao_instituicoes_funcionamento')

				sleep(3)

				break

			except:

				driver.get('about:blank')

		else:

			raise Exception('Failed to load list :' , reg)

		sleep(1)



		soup = BeautifulSoup(driver.page_source, 'html.parser')

		if soup.find('div', {'class':'msg-cookies card border-0'}):

			click_on_cookies(driver)



		try:

			driver.find_element(By.XPATH, '//button[contains(text(),"Prosseguir")]').click()

		except:

			pass

		driver.switch_to.frame(driver.find_element(By.XPATH, '//iframe[@width="100%"]'))

		sleep(2)

		

		scroll_option = driver.find_element(By.XPATH, f'//*[@id="{regdict[reg][0]}"]/option[2]').click()

		#driver.execute_script("arguments[0].click();", scroll_option)

		sleep(0.5)

		ok_button = driver.find_element(By.XPATH, f'''//button[@ng-click="baixarArquivo('{regdict[reg][1]}');"]''').click()

		#driver.execute_script("arguments[0].click();", ok_button)

		

		check_dowload_files(tempfolder, "zip" )

		file = os.listdir(tempfolder)[0]

		filePath = os.path.join(tempfolder, file)



		with zipfile.ZipFile(filePath, 'r') as zip_ref:

			zip_ref.extractall(tempfolder)

			print(f"[INFO] : - Zip extraction file = {zip_ref.filelist[0].filename}")

		sleep(0.5)



		datafile=list(filter(lambda x: '.xlsx' in x or '.csv' in x, os.listdir(tempfolder)))



		filePath = os.path.join(tempfolder, datafile[0])

		if '.xlsx' in datafile[0]:

			filedf=pd.read_excel(filePath, header=None, dtype=str)

		else:

			filedf=pd.read_csv(filePath, header=None, dtype=str)



		filedf.dropna(subset= [1], inplace=True)

		filedf.fillna('', inplace=True)

		filedf.columns = filedf.iloc[0]

		filedf.columns=list(map(lambda x: str(x).strip(), filedf.columns))

		filedf = filedf[1:]

		filedf.replace('\n',' ', regex=True, inplace=True)

		filedf.replace('\r',' ', regex=True, inplace=True)

		filedf.replace('\t',' ', regex=True, inplace=True)

		filedf.replace('  ',' ', regex=True, inplace=True)

		filedf.replace('NaN','', regex=True, inplace=True)

		filedf.reset_index(drop=True, inplace=True)

		print(f'[INFO] : - DataFrame "{datafile[0]}" containe = {filedf.shape}')

		for column in filedf.columns:

			try:

				filedf[column].str.strip()

			except:

				pass

		columns=filedf.columns.tolist()

		for row in range(len(filedf['UF'])):

			sqldict['Cntry'].append('BR')

			sqldict['ListProcessDate'].append(processdate)

			sqldict['RegCtry'].append(reg.split()[0])

			sqldict['RegCode'].append(reg.split()[1])

			sqldict['ListCode'].append(reg.split()[2])

			sqldict['RegulationType'].append('Regulated')



			if 'ENDEREÇO' in columns:

				sqldict['Address_1'].append(filedf['ENDEREÇO'][row])

			if 'COMPLEMENTO' in columns:

				sqldict['Address_2'].append(filedf['COMPLEMENTO'][row])

			if 'CIDADE' in columns:

				sqldict['City'].append(filedf['CIDADE'][row])

			if 'CEP' in columns:

				sqldict['Zip'].append(filedf['CEP'][row])

			if 'NOME INSTITUIÇÃO' in columns:

				sqldict['Name'].append(filedf['NOME INSTITUIÇÃO'][row])

			if 'NOME PARTICIPANTE' in columns:

				sqldict['Name'].append(filedf['NOME PARTICIPANTE'][row])



			if 'NOME DO PARTICIPANTE' in columns:

				sqldict['Name'].append(filedf['NOME DO PARTICIPANTE'][row])



			if 'CNPJ PARTICIPANTE' in columns:

				sqldict['InternalID_1'].append(filedf['CNPJ PARTICIPANTE'][row])

				sqldict['InternalID_1_type'].append('CNPJ Number')

			if 'CNPJ' in columns:

				sqldict['InternalID_1'].append(filedf['CNPJ'][row])

				sqldict['InternalID_1_type'].append('CNPJ Number')

			if 'FONE' in columns:

				sqldict['Phone'].append(filedf['FONE'][row])

			if 'TELEFONE' in columns:

				sqldict['Phone'].append(filedf['TELEFONE'][row])

			if 'E-MAIL' in columns:

				sqldict['Email'].append(filedf['E-MAIL'][row])

			if 'SÍTIO NA INTERNET' in columns:

				sqldict['Website'].append(filedf['SÍTIO NA INTERNET'][row])

			if 'SITIO NA INTERNET' in columns:

				sqldict['Website'].append(filedf['SITIO NA INTERNET'][row])

			if 'NOME DO CONGLOMERADO' in columns:

				sqldict['Name - Mother Company'].append(filedf['NOME DO CONGLOMERADO'][row])

			for key in sqldict.keys():

				if len(sqldict[key])<len(sqldict['ListProcessDate']):

					sqldict[key].append('')



	sqldict = bourange_same_length_array(sqldict)

	for rem in os.listdir(tempfolder):

		os.remove(os.path.join(tempfolder, rem))



# %%

#------------------------------------------------ Begin_writer and save df to excel  ----------------------------------------

os.chdir(scriptfolder)

df=pd.DataFrame(sqldict)

df.to_excel(writer, 'SQL Ready', index=False)

writer.save()

writer.close()

driver.quit()

sleep(3)


    