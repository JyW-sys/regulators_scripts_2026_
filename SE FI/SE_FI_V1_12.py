# %%

#------------------------------------------------ Begin_Librairie ----------------------------------------

import os

import pandas as pd 

from time import sleep

from bs4 import BeautifulSoup

from selenium import webdriver

from selenium.webdriver.common.by import By

from pandas import ExcelWriter

from selenium.webdriver.chrome.options import Options

import datetime



from selenium.webdriver.chrome.service import Service as ChromeService

#from webdriver_manager.chrome import ChromeDriverManager



# %%

#------------------------------------------------ Begin_ fileName ----------------------------------------

regulatorName = 'SE FI' ## change to current controller name



print(f"Running {regulatorName} Web Scraping Tool v.1.2")

now=datetime.datetime.now()

filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":",".")[:-7])

# scriptfolder = f"C:\\Users\\wuj1\\OneDrive - moodys.com\\Desktop\\Regulator\\{regulatorName}" ## to comment for the local environment

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

driver = webdriver.Chrome(options=chromeOptions)

driver.maximize_window()



# %%

#------------------------------------------------ Begin_Variable ----------------------------------------

regdict={'SE FI 1': 'https://www.fi.se/en/our-registers/company-register/?huvudkategori=Bank&area=#results', 

         'SE FI 5': 'https://www.fi.se/en/our-registers/company-register/?huvudkategori=Bank%2C+utl%C3%A4ndska&area=#results', 

         'SE FI 7': 'https://www.fi.se/en/our-registers/company-register/?huvudkategori=Betaltj%C3%A4nstf%C3%B6retag&area=#results', 

         'SE FI 10': 'https://www.fi.se/en/our-registers/company-register/?huvudkategori=Betaltj%C3%A4nstf%C3%B6retag%2C+utl%C3%A4ndska&area=#results', 

         'SE FI 13': 'https://www.fi.se/en/our-registers/company-register/?huvudkategori=Fondbolag%2FAIF-f%C3%B6rvaltare&area=#results', 

         'SE FI 16': 'https://www.fi.se/en/our-registers/company-register/?huvudkategori=Fond&area=#results', 

         'SE FI 18': 'https://www.fi.se/en/our-registers/company-register/?huvudkategori=Fondf%C3%B6retag%2Fbolag%2FAIF-f%C3%B6rvaltare%2C+utl%C3%A4ndska&area=#results', 

         'SE FI 20': 'https://www.fi.se/en/our-registers/company-register/?huvudkategori=Fond%2C+utl%C3%A4ndska&area=#results', 

         'SE FI 21': 'https://www.fi.se/en/our-registers/company-register/?huvudkategori=F%C3%B6rs%C3%A4kringsf%C3%B6retag&area=#results', 

         'SE FI 24': 'https://www.fi.se/en/our-registers/company-register/?huvudkategori=F%C3%B6rs%C3%A4kringsf%C3%B6retag%2C+utl%C3%A4ndska&area=#results', 

         'SE FI 25': 'https://www.fi.se/en/our-registers/company-register/?huvudkategori=Konsumentkreditinstitut&area=#results', 

         'SE FI 27': 'https://www.fi.se/en/our-registers/company-register/?huvudkategori=Hypoteksinstitut&area=#results', 

         'SE FI 28': 'https://www.fi.se/en/our-registers/company-register/?huvudkategori=Kreditmarknadsf%C3%B6retag&area=#results', 

         'SE FI 30': 'https://www.fi.se/en/our-registers/company-register/?huvudkategori=Kreditmarknadsf%C3%B6retag%2C+utl%C3%A4ndska&area=#results', 

         'SE FI 32': 'https://www.fi.se/en/our-registers/company-register/?huvudkategori=Utgivare+av+elektroniska+pengar&area=#results', 

         'SE FI 39': 'https://www.fi.se/en/our-registers/company-register/?huvudkategori=%C3%96vriga+institut&area=#results'}



sqldict={'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [], 

          'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [], 

          'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [], 

          'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],

          'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [], 

          'Phone - Mother company': [], 'Check': []}



ISO= {"": "", 'NAN': '', 'OTHER': '', "AFGHANISTAN": "AF", "ÅLAND ISLANDS": "AX", "ALBANIA": "AL", "ALGERIA": "DZ", "AMERICAN SAMOA": "AS", "ANDORRA": "AD", "ANGOLA": "AO", "ANGUILLA": "AI", "ANTARCTICA": "AQ", "ANTIGUA AND BARBUDA": "AG", "ARGENTINA": "AR", "ARMENIA": "AM", "ARUBA": "AW", "AUSTRALIA": "AU", "AUSTRIA": "AT", "AZERBAIJAN": "AZ", "BAHAMAS, THE": "BS", "BAHRAIN": "BH", "BANGLADESH": "BD", "BARBADOS": "BB", "BELARUS": "BY", "BELGIUM": "BE", "BELIZE": "BZ", "BENIN": "BJ", "BERMUDA": "BM", "BHUTAN": "BT", "BOLIVIA": "BO", "BONAIRE, SINT EUSTATIUS AND SABA": "BQ", "BOSNIA AND HERZEGOVINA": "BA", "BOTSWANA": "BW", "BOUVET ISLAND": "BV", "BRAZIL": "BR", "BRITISH INDIAN OCEAN TERRITORY": "IO", "BRUNEI": "BN", "BULGARIA": "BG", "BURKINA FASO": "BF", "BURUNDI": "BI", "CABO VERDE": "CV", "CAMBODIA": "KH", "CAMEROON, UNITED REPUBLIC OF": "CM", "CANADA": "CA", "CAYMAN ISLANDS": "KY", "CENTRAL AFRICAN REPUBLIC": "CF", "CHAD": "TD", "CHILE": "CL", "CHINA, PEOPLES REPUBLIC OF": "CN","CHINA": "CN", "CHRISTMAS ISLAND": "CX", "COCOS (KEELING) ISLANDS": "CC", "COLOMBIA": "CO", "COMOROS": "KM", "CONGO": "CG", "CONGO, DEMOCRATIC REPUBLIC OF THE": "CD", "COOK ISLANDS": "CK", "COSTA RICA": "CR", "CÔTE D'IVOIRE": "CI", "CROATIA": "HR", "CUBA": "CU", "CURACAO, BONAIRE, SABA, ST. MARTIN & ST.": "CW", "CYPRUS": "CY", "CZECH REPUBLIC": "CZ", "DENMARK": "DK", "DJIBOUTI": "DJ", "DOMINICA": "DM", "DOMINICAN REPUBLIC": "DO", "ECUADOR": "EC", "EGYPT": "EG", "EL SALVADOR": "SV", "EQUATORIAL GUINEA": "GQ", "ERITREA": "ER", "ESTONIA": "EE", "ESWATINI": "SZ", "ETHIOPIA": "ET", "FALKLAND ISLANDS (MALVINAS)": "FK", "FAROE ISLANDS": "FO", "FIJI": "FJ", "FINLAND": "FI", "FRANCE": "FR", "FRENCH GUIANA": "GF", "FRENCH POLYNESIA": "PF", "FRENCH SOUTHERN TERRITORIES": "TF", "GABON": "GA", "GAMBIA": "GM", "GEORGIA": "GE", 'GEORGIA/GRUZINSKAYA': 'GE', "GERMANY": "DE", "GHANA": "GH", "GIBRALTAR": "GI", "GREECE": "GR", "GREENLAND": "GL", "GRENADA": "GD", "GUADELOUPE": "GP", "GUAM": "GU", "GUATEMALA": "GT", "GUERNSEY": "GG", "GUINEA": "GN", "GUINEA-BISSAU": "GW", "GUYANA": "GY", "HAITI": "HT", "HEARD ISLAND AND MCDONALD ISLANDS": "HM", "HOLY SEE": "VA", "HONDURAS": "HN", "HONG KONG": "HK", "HUNGARY": "HU", "ICELAND": "IS", "INDIA": "IN", "INDONESIA": "ID", "IRAN": "IR", "IRAQ": "IQ", "IRELAND": "IE", "ISLE OF MAN": "IM", "ISRAEL": "IL", "ITALY": "IT", "JAMAICA": "JM", "JAPAN": "JP", "JERSEY": "JE", "JORDAN": "JO", "KAZAKHSTAN": "KZ", "KENYA": "KE", "KIRIBATI": "KI", """KOREA (DEMOCRATIC PEOPLE"S REPUBLIC OF)""": "KP", "KOREA, SOUTH": "KR", "KUWAIT": "KW", "KYRGYZSTAN": "KG", "LAO PEOPLE'S DEMOCRATIC REPUBLIC": "LA", "LATVIA": "LV", "LEBANON": "LB", "LESOTHO": "LS", "LIBERIA": "LR", "LIBYA": "LY", "LIECHTENSTEIN": "LI", "LITHUANIA": "LT", "LUXEMBOURG": "LU", "MACAU": "MO", "MADAGASCAR": "MG", "MALAWI": "MW", "MALAYSIA": "MY", "MALDIVES": "MV", "MALI": "ML", "MALTA": "MT", "MARSHALL ISLANDS": "MH", "MARTINIQUE": "MQ", "MAURITANIA": "MR", "MAURITIUS": "MU", "MAYOTTE": "YT", "MEXICO": "MX", "FEDERATED STATES OF MICRONESIA": "FM", "MOLDOVA, REPUBLIC OF": "MD", "MONACO": "MC", "MONGOLIA": "MN", "MONTENEGRO": "ME", "MONTSERRAT": "MS", "MOROCCO": "MA", "MOZAMBIQUE": "MZ", "MYANMAR": "MM", "NAMIBIA": "NA", "NAURU": "NR", "NEPAL": "NP", "NETHERLANDS": "NL", "NEW CALEDONIA": "NC", "NEW ZEALAND": "NZ", "NICARAGUA": "NI", "NIGER": "NE", "NIGERIA": "NG", "NIUE": "NU", "NORFOLK ISLAND": "NF", "NORTH MACEDONIA": "MK", "NORTHERN MARIANA ISLANDS": "MP", "NORWAY": "NO", "OMAN": "OM", "PAKISTAN": "PK", "PALAU": "PW", "PALESTINE, STATE OF": "PS", "PANAMA": "PA", "PAPUA NEW GUINEA": "PG", "PARAGUAY": "PY", "PERU": "PE", "PHILIPPINES": "PH", "PITCAIRN": "PN", "POLAND": "PL", "PORTUGAL": "PT", "PUERTO RICO": "PR", "QATAR": "QA", "RÉUNION": "RE", "ROMANIA": "RO", "RUSSIA": "RU", "RWANDA": "RW", "SAINT BARTHÉLEMY": "BL", "SAINT HELENA, ASCENSION AND TRISTAN DA CUNHA": "SH", "SAINT KITTS AND NEVIS": "KN", "SAINT LUCIA": "LC", "SAINT MARTIN (FRENCH PART)": "MF", "SAINT PIERRE AND MIQUELON": "PM", "SAINT VINCENT AND THE GRENADINES": "VC", "SAMOA": "WS", "SAN MARINO": "SM", "SAO TOME AND PRINCIPE": "ST", "SAUDI ARABIA": "SA", "SENEGAL": "SN", "SERBIA": "RS", "SEYCHELLES": "SC", "SIERRA LEONE": "SL", "SINGAPORE": "SG", "SINT MAARTEN (DUTCH PART)": "SX", "SLOVAKIA": "SK", "SLOVAK REPUBLIC": "SK", "SLOVENIA": "SI", "SOLOMON ISLANDS": "SB", "SOMALIA": "SO", "SOUTH AFRICA": "ZA", "SOUTH GEORGIA AND THE SOUTH SANDWICH ISLANDS": "GS", "SOUTH SUDAN": "SS", "SPAIN": "ES", "SRI LANKA": "LK", "SUDAN": "SD", "SURINAME": "SR", "SVALBARD AND JAN MAYEN": "SJ", "SWEDEN": "SE", "SWITZERLAND": "CH", "SYRIAN ARAB REPUBLIC": "SY", "TAIWAN": "TW",'TAIWAN,  REPUBLIC OF CHINA': 'TW' ,"TAJIKISTAN": "TJ", "TANZANIA, UNITED REPUBLIC OF": "TZ", "THAILAND": "TH", "TIMOR-LESTE": "TL", "TOGO": "TG", "TOKELAU": "TK", "TONGA": "TO", "TRINIDAD AND TOBAGO": "TT", "TUNISIA": "TN", "TURKEY": "TR", "TURKMENISTAN": "TM", "TURKS & CAICOS ISLANDS": "TC", "TUVALU": "TV", "UGANDA": "UG", "UKRAINE": "UA", "UNITED ARAB EMIRATES": "AE", "UNITED KINGDOM OF GREAT BRITAIN AND NORTHERN IRELAND": "GB", "UNITED STATES": "US", "UNITED STATES MINOR OUTLYING ISLANDS": "UM", "URUGUAY": "UY", "UZBEKISTAN": "UZ", "VANUATU": "VU", "VENEZUELA": "VE", "VIETNAM": "VN", "BRITISH VIRGIN ISLANDS": "VG", "VIRGIN ISLANDS OF THE U.S.": "VI", "WALLIS AND FUTUNA": "WF", "WESTERN SAHARA": "EH", "YEMEN": "YE", "ZAMBIA": "ZM", "ZIMBABWE": "ZW", "ENGLAND": "GB", "UNITED KINGDOM": "GB", "UNITED KINGDOM (OTHER)": "GB", "FRANCE (OTHER)": "FR", "WALES": "GB", "CONGO (KINSHASA)": "CD", "CONGO (BRAZZAVILLE)": "CD", "SCOTLAND": "GB", "ITALY (OTHER)": "IT", "INDONESIA (OTHER)": "ID", "INDIA (OTHER)": "IN", "MOROCCO (OTHER)": "MA", "NEW ZEALAND (OTHER)": "NZ", "SWITZERLAND (OTHER)": "CH", "MALAYSIA (OTHER)": "MY", "NETHERLANDS ANTILLES": "AN", "TRINIDAD & TOBAGO (OTHER)": "TT", "CHANNEL ISLANDS": "GB", "UNITED ARAB EMIRATES (OTHER)": "AE", "DENMARK (OTHER)": "DK", "COMORO ISLANDS": "KM", "MACEDONIA (FORMER YUGOSLAV REPUBLIC OF)": "MK", "SERBIA AND MONTENEGRO(FORMER YUGOSLAVIA)": "CS", "TRINIDAD": "TT", "ETHIOPIA (OTHER)": "ET", "IVORY COAST": "CI", "DUBAI": "AE", "BRITISH WEST INDIES (OTHER)": "VG", "SWAZILAND": "SZ", 'UNITED KINGDOM  (OTHER)': 'GB'}



processdate = now.strftime('%Y-%m-%d')



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



# %%

#------------------------------------------------ Begin_Main ----------------------------------------

for k, reg in enumerate(regdict):

    print(f"[INFO] : Working {k+1}/{len(regdict)} _({reg})_ ")

    clinks=[]

    Names=[]

    CorporateID = []

    driver.get(regdict[reg])

    sleep(4)

    soup=BeautifulSoup(driver.page_source, 'html.parser')



    if "We did not find any matches" in soup.text:

        print(f'[ERROR] : No entities in this regcode. (Regcode: {reg})')

        asx = []

        clinks = []

    else:

        soup=soup.find("table", {"id":"institut", "class":"grouped"})

        soup=soup.find("tbody")

        tds=soup.find_all("td")



    for td in tds :

        if td.find("a") == None:

            CorporateID.append(td.text.replace("\n", "").strip())

        else:

            a = td.find("a")

            Names.append(a.text.strip())

            clinks.append('https://www.fi.se/en/our-registers/company-register/' + a['href'] if a['href'][0] != "/" else "https://www.fi.se" + a['href'])



    for link in range(len(clinks)):

        Attributs = ['Address', 'Telephone', 'Category', 'Other business', 'Corporate ID number', 'LEI code', 'FI identification number', 'Status']

        valueTab = ['']*len(Attributs)



        print(f"[INFO] : - Scraping {link+1}/{len(clinks)} | {reg} ")

        for tries in range(10):

            try:

                driver.get(clinks[link])

                sleep(2)

                if driver.page_source != None:

                    break

            except:

                print(f'[ERROR] : Failed to get entity page, retrying {tries}/10...')

                sleep(2)

        else:

            raise Exception(f"ResponseError: Failed after retrying click 10 times. link = {clinks[link]}")



        soup2=BeautifulSoup(driver.page_source, 'html.parser')

        soup2=soup2.find("dl", {"class":"funky"})



        try:

            items = soup2.findChildren()

        except:

             raise Exception(f"[INFO] : - Scraping {link+1}/{len(clinks)} | {reg}")

        



        for i, item in enumerate(items):

            if str(item).find('</dt>') != -1 :

                ValAttribut = []

                for j in range(i+1, len(items)):

                    if str(items[j]).find('</dd>') != -1 :

                        ValAttribut.append(items[j].text.replace("\n", '').strip())



                    if str(items[j]).find('</dt>') != -1 :

                        break

                valueTab[Attributs.index(item.text)] = ' '.join(ValAttribut)



        sqldict['Name'].append(Names[link])

        sqldict['Address_1'].append(valueTab[0])

        try:

            sqldict['City'].append(valueTab[0].split(' ')[-2])        

            sqldict['Cntry'].append(valueTab[0].split(' ')[-1])

        except:

            sqldict['City'].append('')        

            sqldict['Cntry'].append('')

        sqldict['Phone'].append(valueTab[1])

        #sqldict['Typology'].append(valueTab[2])

        sqldict['InternalID_1_type'].append('Corporate ID number')

        sqldict['InternalID_1'].append(valueTab[4])

        sqldict['InternalID_2_type'].append('FI identification number')

        sqldict['InternalID_2'].append(valueTab[6])

        sqldict['LEI Code'].append(valueTab[5])

        sqldict['RegulationType'].append(valueTab[7].split(',')[0])

        sqldict['RegulationDate'].append(valueTab[7].split(',')[1])



        sqldict['ListProcessDate'].append(processdate)

        sqldict['RegCtry'].append(reg.split(' ')[0]) 

        sqldict['RegCode'].append(reg.split(' ')[1])

        sqldict['ListCode'].append(reg.split(' ')[-1])



        # if link == 10 :

        #     break



    sqldict = bourange_same_length_array(sqldict)



# %%

#------------------------------------------------ Begin_writer and save df to excel  ----------------------------------------

os.chdir(scriptfolder)

df=pd.DataFrame(sqldict)

df.to_excel(writer, 'SQL Ready', index=False)

writer.save()

writer.close()

driver.quit()

sleep(3)


    