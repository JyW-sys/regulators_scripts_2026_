# %%

#------------------------------------------------ Begin_Librairie ----------------------------------------

from selenium import webdriver

from selenium.webdriver.common.by import By

import pandas as pd

from time import sleep

import datetime

from bs4 import BeautifulSoup

from pandas import ExcelWriter

import os

import requests

from zipfile import ZipFile



# %%

#------------------------------------------------ Begin_ fileName ----------------------------------------

regulatorName = 'US FED' ## change to current controller name



print(f"Running {regulatorName} Web Scraping Tool v.1.2")

now=datetime.datetime.now()

filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":",".")[:-7])

#scriptfolder = f"C:\\Users\\siewekoa\\OneDrive - moodys.com\\Desktop\\My_data\\Project_work\\scripts_regulator\\{regulatorName}" ## to comment for the production environment

scriptfolder=os.path.dirname(os.path.abspath(__file__)) ## to decomment for the production environment

os.chdir(scriptfolder)

writer = ExcelWriter(filename, engine='openpyxl')

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

regdict={

    'US FED 1': 'https://www.federalreserve.gov/releases/lbr/current/default.htm', 

    'US FED 2': 'https://www.fdic.gov/regulations/resources/minority/mdi.html', 

    'US FED 3': 'https://www.federalreserve.gov/releases/iba/', 

    # 'US FED 4': 'https://www.ffiec.gov/npw/FinancialReport/DataDownload',  # Non-operational : this link contains a capchat page

    'US FED 5': 'https://www.federalreserve.gov/supervisionreg/large-institution-supervision.htm'

        }

         

sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],

          'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],

          'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],

          'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],

          'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],

          'Phone - Mother company': [], 'Check': []}



ISO = {'ARGENTINA': 'AR', 'AUSTRALIA': 'AU', 'AUSTRIA': 'AT', 'BAHRAIN': 'BH', 'BELGIUM': 'BE', 'BRAZIL': 'BR', 

       'CANADA': 'CA', 'CHILE': 'CL', 'CHINA, PEOPLES REPUBLIC OF': 'CN', 'COLOMBIA': 'CO', 

       'CURACAO, BONAIRE, SABA, ST. MARTIN & ST.': 'CW', 'ECUADOR': 'EC', 'EGYPT': 'EG', 'FINLAND': 'FI', 'FRANCE': 'FR', 

       'GERMANY': 'DE', 'HONDURAS': 'HN', 'HONG KONG': 'HK', 'INDIA': 'IN', 'INDONESIA': 'ID', 'IRELAND': 'IE', 

       'ISRAEL': 'IL', 'ITALY': 'IT', 'JAMAICA': 'JM', 'JAPAN': 'JP', 'JORDAN': 'JO', 'KOREA, SOUTH': 'KR', 'KUWAIT': 'KW', 

       'LUXEMBOURG': 'LU', 'MALAYSIA': 'MY', 'MEXICO': 'MX', 'MOROCCO (OTHER)': 'MA', 'NETHERLANDS': 'NL', 'NIGERIA': 'NG', 

       'NORWAY': 'NO', 'PAKISTAN': 'PK', 'PANAMA': 'PA', 'PERU': 'PE', 'PHILIPPINES': 'PH', 'PORTUGAL': 'PT', 

       'SAUDI ARABIA': 'SA', 'SINGAPORE': 'SG', 'SOUTH AFRICA': 'ZA', 'SPAIN': 'ES', 'SWEDEN': 'SE', 'SWITZERLAND': 'CH', 

       'TAIWAN': 'TW', 'THAILAND': 'TH', 'TURKEY': 'TR', 'UKRAINE': 'UA', 'UNITED ARAB EMIRATES': 'AE', 

       'UNITED KINGDOM': 'UK', 'UNITED STATES': 'US', 'URUGUAY': 'UY', 'VIETNAM': 'VN'}



US_FED_2 = ['NAME', 'CITY', 'STATE', 'DATE', 'CERT', 'CLASS', 'REGULATOR', 'MIN_STATUS_Alpha', 'MIN_STATUS_OWNERSHIP TYPE_Numeric', 'FDIC_REGION', 'TOTAL_ASSETS']



processdate = now.strftime('%Y-%m-%d')

empty_ = ''



# %%

#------------------------------------------------ Begin_Fouction ----------------------------------------

def download_file(url):

    local_filename = url.split('/')[-1].split('?')[0]

    with requests.get(url) as r:

        with open(local_filename, 'wb') as f:

            f.write(r.content)

    return local_filename



def extract_zipFile(zipfile, select_file, dst):

    with ZipFile(zipfile, 'r') as zipObj:

        FileNames = zipObj.namelist()

        for fileName in FileNames:

            if fileName == select_file:

                zipObj.extract(fileName, dst)



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



def check_dowload_files(tempfolder, fileType, wait_time=10):

    for time in range(wait_time):

        if len([ele for ele in os.listdir(tempfolder) if '.crdownload' not in ele and '.tmp' not in ele]) != 0 :

            print(f"[INFO] : - {fileType} file = {os.listdir(tempfolder)[0]}")

            break

        else:

            print(f"[INFO] : - Download {fileType} file ... (wait {time*2}/{wait_time*2} s)")

            sleep(2)

    else:

        raise Exception(f'[ERROR] : - Failed to Download {fileType} file. Run Script again' )



# %%

#------------------------------------------------ Begin_Main ----------------------------------------

for k, reg in enumerate(regdict):

    print(f"[INFO] : Working {k+1}/{len(regdict)} | {reg} ")

    driver.get(regdict[reg])

    sleep(3)

    

    if reg == 'US FED 1':

        soup=BeautifulSoup(driver.page_source, 'html.parser')

        table = soup.find("table",{"cellspacing":"0"})

        trs = table.find_all('tr')

        print(f'[INFO] : - Data Scrapping = {len(trs)} | {reg}')            

        for i in range(1,len(trs)):

            tds = trs[i].find_all('td')

            sqldict['Name'].append(tds[0].text.strip())

            sqldict['InternalID_1'].append(tds[2].text.strip())

            sqldict['InternalID_1_type'].append('Bank ID')

            sqldict['Address_1'].append(tds[3].text.strip())

            sqldict['Typology'].append(tds[4].text.strip())

            sqldict['ListProcessDate'].append(processdate)

            sqldict['RegulationType'].append('Regulated')

            sqldict['RegCtry'].append('US')

            sqldict['RegCode'].append('FED')

            sqldict['Cntry'].append('US')

            sqldict['ListCode'].append(reg[-1])

        

        sqldict = bourange_same_length_array(sqldict)



    elif reg == 'US FED 2':

        soup=BeautifulSoup(driver.page_source, 'html.parser')

        table = soup.find("ul",{"class":"glossary"})

        lis = table.find_all('li')

        driver.find_element(By.XPATH, '//*[@id="content"]/div/ul[1]/li[%d]/a'%len(lis)).click()

        check_dowload_files(tempfolder, 'xlsx')

        file = os.listdir(tempfolder)[0]

        filePath = os.path.join(tempfolder, file)

        df = pd.read_excel(filePath)

        df.columns = US_FED_2

        df = df.fillna("")

        df = df[1:] #take the data less the header row

        df = df.reset_index(drop=True)

        

        print(f'[INFO] : - Scrapping "{file}" containe = {df.shape}  | {reg}')

        for index, row in df.iterrows() :

            if len(str(row['NAME'])) > 0:

                sqldict['Name'].append(str(row['NAME']))

                sqldict['InternalID_1'].append(str(row['CERT']))

                sqldict['InternalID_1_type'].append('CERT')

                sqldict['RegulationDate'].append(str(row['DATE'])[0:4]+"-"+str(row['DATE'])[4:6]+"-"+str(row['DATE'])[6:8] )

                sqldict['ListProcessDate'].append(processdate)

                sqldict['RegulationType'].append('Regulated')

                sqldict['RegCtry'].append(reg.split(' ')[0]) 

                sqldict['RegCode'].append(reg.split(' ')[1])

                sqldict['ListCode'].append(reg.split(' ')[-1])

                sqldict['City'].append(str(row['CITY']))

                sqldict['Cntry'].append('US')

                sqldict['Address_1'].append( ( str(row['STATE'])+","+str(row['CITY']) ))

                sqldict['Typology'].append(str(row['CLASS']))



        sqldict = bourange_same_length_array(sqldict)

        

    elif reg == 'US FED 3':

        soup=BeautifulSoup(driver.page_source, 'html.parser')

        bloc = soup.find("div",{"id":"content"})

        cells = bloc.find_all("div",{"class":"col-xs-12 col-md-6"}) 

        # This xpath could need maintenance (to check) !!!!

        driver.find_element(By.XPATH,'//*[@id="content"]/div[4]/div/div/div/ul/li[1]/a').click()

        sleep(3)

        driver.find_element(By.PARTIAL_LINK_TEXT ,'By Country').click()

        sleep(3)

        soup=BeautifulSoup(driver.page_source, 'html.parser')

        ps=soup.find_all("p",{"class":"ST4"})

        tables = soup.find_all("table",{"border":"1"})

        

        for i in range(len(ps)):

            country = ps[i].text.replace('COUNTRY:','').strip()

            trs = tables[i].find_all('tr')



            print(f'[INFO] : - Data Scrapping in table {i+1}/{len(ps)} = {len(trs)} | {reg}') 

            for j in range(1,len(trs)):

                tds = trs[j].find_all('td')

                

                if len(tds) > 2:

                    sqldict['Name'].append(' '.join([el.strip() for el in tds[1].text.strip().splitlines()]))

                    sqldict['Name - Mother Company'].append(' '.join([el.strip() for el in tds[0].text.strip().splitlines()]))

                    sqldict['Address_1'].append(tds[2].text.strip())

                    sqldict['ListProcessDate'].append(processdate)

                    sqldict['RegulationType'].append('Regulated')

                    sqldict['RegCtry'].append('US')

                    sqldict['RegCode'].append('FED')

                    sqldict['Cntry'].append(ISO.get(country))

                    sqldict['ListCode'].append(reg[-1])

            

                    sqldict = bourange_same_length_array(sqldict)

                else:

                    pass

        

    elif reg == 'US FED 4':

        

        driver.find_element(By.XPATH,'/html/body/div[4]/div[2]/div[4]/div[2]/div/ul/li[1]/button/span').click() # This xpath could need maintenance (to check) !!!!

        check_dowload_files(tempfolder, 'zip', 20)

        file = os.listdir(tempfolder)[0]

        filePath = os.path.join(tempfolder, file)

        extract_zipFile(filePath, "CSV_ATTRIBUTES_ACTIVE.CSV", tempfolder)

        csv_file = os.path.join(tempfolder, list(filter(lambda x:x.endswith(".CSV"), os.listdir(tempfolder)))[0] )

        df = pd.read_csv(csv_file)

        df = df.fillna("")



        print(f'[INFO] : - Scrapping "CSV_ATTRIBUTES_ACTIVE.CSV" containe = {df.shape} | {reg}')

        for index, row in df.iterrows() :

            if len(str(row['NM_SHORT'])) > 0:

            #if df.ENTITY_TYPE[i].strip() == 'FHD':

                sqldict['Name'].append(str(row['NM_SHORT']))

                sqldict['Name - Mother Company'].append(str(row['NM_LGL']))

                sqldict['Address_1'].append( str(row['STREET_LINE1'])+","+str(row['CITY'])+","+str(row['CNTRY_NM']) ) 

                sqldict['Typology'].append(str(row['ENTITY_TYPE']))

                sqldict['InternalID_1'].append(str(row['#ID_RSSD']))

                sqldict['InternalID_1_type'].append('ID_RSSD')

                sqldict['ListProcessDate'].append(processdate)

                sqldict['RegulationType'].append('Regulated')

                sqldict['RegCtry'].append('US')

                sqldict['RegCode'].append('FED')

                sqldict['Cntry'].append('US')

                sqldict['City'].append(str(row['CITY']))

                sqldict['Zip'].append(str(row['ZIP_CD']))

                sqldict['ListCode'].append(reg[-1])

                if (str(row['URL']) != '0')  and len(str(row['URL'])) > 0 :

                    sqldict['Website'].append(str(row['URL']))

                else:

                    sqldict['Website'].append('')

                

        sqldict = bourange_same_length_array(sqldict)

        

    elif reg == 'US FED 5':

        soup=BeautifulSoup(driver.page_source, 'html.parser')

        bloc = soup.find("div",{"class":"col-xs-12 col-sm-8 col-md-8"})

        uls = bloc.find_all("ul")

        lis = uls[0].find_all("li")

        

        print(f'[INFO] : - Data Scrapping = {len(lis)} | {reg}')

        for i in range(len(lis)):

            sqldict['Name'].append(lis[i].text.strip())

            sqldict['ListProcessDate'].append(processdate)

            sqldict['RegulationType'].append('Regulated')

            sqldict['RegCtry'].append('US')

            sqldict['RegCode'].append('FED')

            sqldict['Cntry'].append('US')

            sqldict['ListCode'].append(reg[-1])

                

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
    