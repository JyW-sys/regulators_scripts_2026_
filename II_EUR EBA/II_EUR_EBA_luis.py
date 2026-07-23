# %%

#Developed by LLZ

#updated by Anicet

#updated on 08/02/2024

# %%

#------------------------------------------------ Begin_Librairie ----------------------------------------

from selenium import webdriver

from selenium.webdriver.common.by import By

from selenium.webdriver.support.ui import WebDriverWait

from selenium.webdriver.support import expected_conditions as EC

from selenium.webdriver.common.action_chains import ActionChains

from selenium.webdriver.common.keys import Keys

import pandas as pd

from time import sleep

import datetime

from bs4 import BeautifulSoup

from pandas import ExcelWriter

import os

import zipfile

import json



# %%

#------------------------------------------------ Begin_ fileName ----------------------------------------

regulatorName = 'II_EUR EBA' ## change to current controller name



print(f"Running {regulatorName} Web Scraping Tool v.1.4")

now=datetime.datetime.now()

filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":",".")[:-7])

scriptfolder = f"C:\\Users\\siewekoa\\OneDrive - moodys.com\\Desktop\\My_data\\Project_work\\scripts_regulator\\{regulatorName}" ## to comment for the production environment

scriptfolder=os.path.dirname(os.path.abspath(__file__)) ## to decomment for the production environment

#os.chdir(scriptfolder)

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

#------------------------------------------------ Begin_Variable ----------------------------------------

regdict = {'II_EUR EBA 1': {'CRD Credit institution': '//*[@aria-label="CRD Credit Institution"]/span',

                            'EEA Branch'            :'//*[@aria-label="EEA Branch"]/span',

                            'Non-EEA Branch'        : '//*[@aria-label="Non-EEA Branch"]/span'},



          'II_EUR EBA 2' : 'https://euclid.eba.europa.eu/register/pir/registerDownload'}



regwait3 = {'CRD Credit institution': '//app-app-entity-search/form/p-card/div/div/div/p-card[2]/div/div/div/p-button[1]/button',

         'EEA Branch': '//app-app-entity-search/form/p-card/div/div/div/p-card[3]/div/div/div/p-button[1]/button/span[2]',

         'Non-EEA Branch': '//app-app-entity-search/form/p-card/div/div/div/p-card[4]/div/div/div/p-button[1]/button'}



entity_types = {'PSD_PI': 'Payment Institution', 'PSD_EPI': 'Exempted Payment Institution', 'PSD_EMI': 'Electronic Money Institution',

                'PSD_EEMI': 'Exempted Electronic Money Institution', 'PSD_AISP': 'Account Information Service Provider', 'PSD_EXC': 'Service provider excluded from the scope of PSD2',

                'PSD_ENL': "Natural or Legal Person", 'PSD_BR': 'Branch', 'PSD_AG': 'Agent'}



sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],

          'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],

          'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],

          'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],

          'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],

          'Phone - Mother company': [], 'Check': []}



processdate = now.strftime('%Y-%m-%d')



# %%

#------------------------------------------------ Begin_Fouction ----------------------------------------

def click_on_cookies(web_driver):

    try:

        web_driver.find_element(By.XPATH,'//cookie-law/cookie-law-component/div/div/a').click()

    except Exception as err:

        print("[ERROR] : Failed to click 'X' on the cookies banner", err)



def move_to_xpath(web_driver, xpath):

    '''

    This function locate us at the bottom of the page where we normally find: "For the more security, speed and the best experience using this website please use Chrome (latest version)."

    '''

    try:

        action.move_to_element(web_driver.find_element(By.XPATH,xpath)).perform()

    except:

        print("[ERROR] : II_EUR EBA - Failed to move to xpath", xpath)



def page_has_loaded(driver, timeout, POLL_FREQUENCY, XPATH):

    for time in range(10):

        try:

            sleep(2)

            element_present = EC.presence_of_element_located((By.XPATH, XPATH))

            #element_present = EC.element_to_be_clickable((By.XPATH, XPATH))

            wait=WebDriverWait(driver, timeout, POLL_FREQUENCY).until(element_present)

            break

        except:

            print(f"[ERROR] : Retrying {time+1}/10 to find element in this page: {XPATH} ")

            sleep(1)    

    else:

        raise Exception('[ERROR] : Failed to get presence for this element in this page:')

    return driver.find_element(By.XPATH, XPATH)



# %%

#------------------------------------------------ Begin_Main ----------------------------------------

for k, reg in enumerate(regdict):

    print('Working with {}.'.format(reg))

    action = ActionChains(driver)

    if reg == 'II_EUR EBA 1':

        for t, typology in enumerate(regdict[reg]):

            names = []

            clinks=[]

            driver.get('about:blank')

            driver.get('https://euclid.eba.europa.eu/register/cir/search')

            sleep(3)

            soup = BeautifulSoup(driver.page_source, 'html.parser')

            if soup.find('cookie-law-component'):

                click_on_cookies(driver)

            sleep(3)

            move_to_xpath(driver, "//div[@class='alert alert-warning']/p")

            page_has_loaded(driver, 20, 20, "//app-disclaimer-page/div/p-button/button").click()

            page_has_loaded(driver, 20, 20, "//p-dropdown//label").click()

            page_has_loaded(driver, 20, 20, regdict[reg][typology]).click()

            driver.find_element(By.TAG_NAME,'body').send_keys(Keys.CONTROL + Keys.END)

            move_to_xpath(driver, regwait3[typology])

            sleep(1)

            page_has_loaded(driver, 20, 20, regwait3[typology]).click()

            sleep(5)

            tpages = page_has_loaded(driver, 20, 20, '//*[@id="search-results-table"]/div/div[2]').text

            tpages = tpages.strip().split()

            tpages = int(tpages[-1])

            if tpages%10==0:

                pages = int(tpages/10)

            else:

                pages = (tpages//10 ) + 1

            waitmaintable=WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, '//*[@id="search-results-table"]/div/div[1]/table/thead/tr')))

            soup = BeautifulSoup(driver.page_source, 'html.parser')

            headers = soup.find('thead', {"class":"ui-table-thead"}).find_all('th')

            headers=[header.text.strip() for header in headers]

            nameix = headers.index('Name')

            for page in range(pages):

                clickwait=WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, '//*[@id="search-results-table"]/div/p-paginator[1]/div/a[3]/span')))

                print(f"[INFO] : Gathering entities {k+1}/{len(regdict)} _({reg})_ | typology {t+1}/{len(regdict[reg])} | Page {page+1}/{pages}")

                sleep(0.5)

                soup = BeautifulSoup(driver.page_source, 'html.parser')

                soup = soup.find('div', {'class':'ui-table-wrapper ng-star-inserted'})

                trs = soup.find('tbody').find_all('tr')

                for tr in trs:

                    tds = tr.find_all('td')

                    clinks.append('https://euclid.eba.europa.eu'+tds[nameix].find('a', href=True)['href'])

                    names.append(tds[nameix].text.strip())

                if page<pages:

                    page_has_loaded(driver, 20, 10, '//*[@id="search-results-table"]/div/p-paginator[1]/div/a[3]/span').click()

                else:

                    pass

            for i, link in enumerate(clinks):

                

                print(f"[INFO] : {k+1}/{len(regdict)} _({reg})_ | typology {t+1}/{len(regdict[reg])} ({typology}) | Working link {i+1}/{len(clinks)} ")

                sqldict['Name'].append(names[i])

                sqldict['ListProcessDate'].append(processdate)

                sqldict['RegulationType'].append('Authorised')

                sqldict['RegCtry'].append('II_EUR')

                sqldict['RegCode'].append('EBA')

                sqldict['ListCode'].append('1')

                sqldict['Typology'].append(typology)

                driver.get('about:blank')

                driver.get(link)

                page_has_loaded(driver, 20, 10, '/html/body/app-root/app-cir/div[1]/div/app-disclaimer-page/div/p-button/button').click()

                

                for time in range(10):

                    try:

                        element = page_has_loaded(driver, 20, 10, "//app-app-entity-view//label")

                        break

                    except:

                        sleep(2)

                else:

                    raise Exception(reg, 'Failed to get information for entity, url:', link)

                soup = BeautifulSoup(driver.page_source, "html.parser")

                

                divs = soup.find_all('div',  {'class':'ui-card-body'})

                try :

                    data_div = [d for d in divs if 'Name' in d.text and 'Type' in d.text][0] #if the code fails here means that there is no name in the table hence there is an issue with the site or the code

                    rows = data_div.find_all("div", {"class":"form-group"})

                    for row in rows:

                        label = row.find('label').text.strip()

                        value = row.find('div').text.strip() #, {'class': 'property-value'} # the class property-value is not present for mother company name

                        if label == 'Town' and len(sqldict['City'])<len(sqldict['ListProcessDate']):

                            sqldict['City'].append(value)

                        elif label == 'Country of Residence' and len(sqldict['Cntry'])<len(sqldict['ListProcessDate']):

                            span = row.find('div', {'class': 'property-value'}).find('span')

                            country = span['class'][-1].split('-')[-1].upper() #tranforming: 'flag-icon flag-icon-it'>>>['flag-icon', 'flag-icon-it']>>>'flag-icon-it'>>>'IT'

                            sqldict['Cntry'].append(country)

                        elif label == 'National Reference Code' and len(sqldict['InternalID_2'])<len(sqldict['ListProcessDate']):

                            sqldict['InternalID_2'].append(value)

                            sqldict['InternalID_2_type'].append('National Reference Code')

                        elif 'LEI' in label : #and len(sqldict['LEI Code'])<len(sqldict['ListProcessDate']):

                            sqldict['LEI Code'].append(value)

                        elif 'Name of' in label and 'establishing ' in label and len(sqldict['Name - Mother Company'])<len(sqldict['ListProcessDate']):

                            sqldict['Name - Mother Company'].append(value)

                        elif 'Country' in label and 'establishing' in label and len(sqldict['Cntry - Mother company'])<len(sqldict['ListProcessDate']):

                            span = row.find('div', {'class': 'property-value'}).find('span')

                            country_mother_company = span['class'][-1].split('-')[-1].upper()

                            sqldict['Cntry - Mother company'].append(country_mother_company)

                except Exception as e:

                    # print(f"[ERROR] : Failed is link {i+1}/{len(clinks)} : {link}.\n{' '*10}NameError :\n{' '*10}{e}  ")

                    raise Exception(f"[ERROR] : Failed is link {i+1}/{len(clinks)} : {link}.\n{' '*10}NameError :\n{' '*10}{e}  ")



                for key in sqldict:

                    if len(sqldict[key])<len(sqldict['Name']):

                        sqldict[key].append('')

                #driver.back()

    elif reg == 'II_EUR EBA 2':

        print(f"[INFO] : Gathering entities ({k+1}/{len(regdict)}) {reg} ")

        driver.get(regdict[reg])

        sleep(3)

        soup = BeautifulSoup(driver.page_source, 'html.parser')

        if soup.find('cookie-law-component'):

                click_on_cookies(driver)

        driver.find_element(By.TAG_NAME,'body').send_keys(Keys.CONTROL + Keys.END)

        page_has_loaded(driver, 20, 10, "//span[text()='Download']").click()



        for time in range(50):

            if len([ele for ele in os.listdir(tempfolder) if '.crdownload' not in ele and '.tmp' not in ele]) != 0 :

                print(f"[INFO] : PDF file = {os.listdir(tempfolder)})")

                zip_file = os.path.join(tempfolder, os.listdir(tempfolder)[0])

                break

            else:

                print(f"[INFO] : Download json file... (wait {time*2}/100 s)")

                sleep(2)

        else:

            raise Exception(f'[ERROR] : Failed to Download PDF file for {reg}. Run Script again' )



        json_file =''

        

        with zipfile.ZipFile(zip_file, 'r') as zip_ref:

            FileNames = zip_ref.namelist()

            for fileName in FileNames:

                if fileName.endswith('.json'):

                    zip_ref.extract(fileName, tempfolder)

                    json_file = fileName

                    #print(json_file)



        print(f"[INFO] : Extract json file = {json_file})")

        os.remove(zip_file)

        json_file = os.path.join(tempfolder, json_file)

        with open(os.path.join(scriptfolder, json_file), 'rb') as f_in:

            json_data = json.load(f_in)

        os.remove(json_file)

        description = json_data[0]

        entities = json_data[1]

        #print(len(entities))

        print(f"[INFO] : Len entities json file = {len(entities)})")

        for entity in entities:# range(len(entities)): #range(1000):

            typology = entity['EntityType']

            if (typology != 'PSD_BR') and (typology != 'PSD_AG') :

                sqldict['Typology'].append(entity_types[entity['EntityType']])

                #regulator = entity['CA_OwnerID']

                #sqldict['RegCtry'].append(regulator.split('_')[0])

                #sqldict['RegCode'].append(regulator.split('_')[1])

                sqldict['RegCtry'].append('II_EUR')

                sqldict['ListProcessDate'].append(processdate)

                sqldict['RegCode'].append('EBA')

                sqldict['ListCode'].append('2')

                eba_entity_code = entity['EntityCode']

                sqldict['InternalID_1_type'].append('EBA Entity Code')

                sqldict['InternalID_1'].append(eba_entity_code)

                

                properties = entity['Properties']

                entity_dict = dict()

                for prop in properties:

                    for key in prop:

                        entity_dict[key] = prop[key]

                name = entity_dict['ENT_NAM']

                if type(name) is list: #sometimes we have a list like this: ['name with bulgarian/russian characters', 'international name'] instead of a single name, we take the second element

                    name = name[-1]

                #name = bytes(name, 'utf-8') #for testing pourposes

                sqldict['Name'].append(name)

                if 'ENT_NAT_REF_COD' in entity_dict:

                    sqldict['InternalID_2_type'].append('National Reference Code')

                    sqldict['InternalID_2'].append(entity_dict['ENT_NAT_REF_COD'])

                if 'ENT_ADD' in entity_dict:

                    sqldict['Address_1'].append(entity_dict['ENT_ADD'])

                if 'ENT_TOW_CIT_RES' in entity_dict:

                    sqldict['City'].append(entity_dict['ENT_TOW_CIT_RES'])

                if 'ENT_POS_COD' in entity_dict:

                    sqldict['Zip'].append(entity_dict['ENT_POS_COD'])

                if 'ENT_COU_RES' in entity_dict:

                    sqldict['Cntry'].append(entity_dict['ENT_COU_RES'])

                if 'ENT_AUT' in entity_dict:

                    auth_dates = entity_dict['ENT_AUT'] #still running if odd amount of dates; even if it cancelled

                    if len(auth_dates)%2 == 1: #odd number

                        sqldict['RegulationDate'].append(auth_dates[-1])

                        sqldict['RegulationType'].append('Authorised')

                    else:

                        sqldict['RegulationDate'].append(auth_dates[-2])

                        sqldict['CancellationDate'].append(auth_dates[-1])

                        sqldict['RegulationType'].append('Cancelled')

                else:

                    #sqldict['RegulationType'].append('***Authorised')

                    sqldict['RegulationType'].append(entity_dict['DER_CHI_ENT_AUT'])

                for key in sqldict:

                    if len(sqldict[key])<len(sqldict['Name']):

                        sqldict[key].append('')



# %%

#------------------------------------------------ Begin_writer and save df to excel  ----------------------------------------

os.chdir(scriptfolder)

df=pd.DataFrame(sqldict)

df.to_excel(writer, 'SQL Ready', index=False)

writer.save()

writer.close()

driver.quit()

sleep(3)
    