# %%

#------------------------------------------------ Begin_Librairie ----------------------------------------

import pandas as pd

from bs4 import BeautifulSoup

from time import sleep

from datetime import datetime

from pandas import ExcelWriter

from selenium import webdriver

from selenium.webdriver.common.by import By

from selenium.webdriver.common.keys import Keys

import datetime

import os

import re

import pdfplumber



# %%

#------------------------------------------------ Begin_ fileName ----------------------------------------

regulatorName = 'GB PRA' ## change to current controller name



print(f"Running {regulatorName} Web Scraping Tool v.1.1")

now=datetime.datetime.now()

filename = '{} data {}.xlsx'.format(regulatorName, str(now).replace(":",".")[:-7])

scriptfolder = f"C:\\Users\\wuj1\\OneDrive - Moody's\\Desktop\\Regulator\\{regulatorName}"
# scriptfolder=os.path.dirname(os.path.abspath(__file__)) ## to decomment for the production environment

os.chdir(scriptfolder)

writer = ExcelWriter(filename)

tempfolder=os.path.join(scriptfolder, 'tempfolder') #if files are downloaded during the process

if os.path.exists(tempfolder):

    for rem in os.listdir(tempfolder):

        os.remove(os.path.join(tempfolder, rem))

else:

    os.mkdir(tempfolder)



# %%

#Starting Chrome driver, set to download files in tempfolder

chromeOptions = webdriver.ChromeOptions()

prefs = {"plugins.always_open_pdf_externally": True,

		 "download.prompt_for_download": False,

		 "download.default_directory" : tempfolder,

         'profile.default_content_setting_values.automatic_downloads': 1 # Desable a Multiplefile download alert

         }

chromeOptions.add_argument("--disable-search-engine-choice-screen")

chromeOptions.add_experimental_option("prefs",prefs)

driver = webdriver.Chrome(options=chromeOptions)

driver.maximize_window()



# %%

#------------------------------------------------ Begin_Variable ----------------------------------------

regdict={

        'GB PRA 1': 'List of PRA-regulated insurers',

        'GB PRA 2': 'List of PRA-regulated insurers',

        'GB PRA 3': 'List of PRA-regulated Banks',

        # 'GB PRA 4': '',

        'GB PRA 5': 'List of PRA-regulated Banks',

        'GB PRA 6': 'List of PRA-regulated Banks',

        # 'GB PRA 7': '',

        'GB PRA 8': 'List of PRA-regulated Banks',

        'GB PRA 9': 'List of PRA-regulated Building Societies',

        # 'GB PRA 10': '', 

        'GB PRA 11': 'List of designated firms', 

        'GB PRA 12': 'List of ring-fenced bodies',

        'GB PRA 13': 'List of PRA-regulated insurers',

        'GB PRA 14': 'List of PRA-regulated credit unions', 

        'GB PRA 15': 'https://register.fca.org.uk/s/search?predefined=BHC',

        }



Typology={

        'GB PRA 1': 'List of Authorised Insurers Incorporated In Gibraltar',

        'GB PRA 2': 'List of Authorised UK Insurers',

        'GB PRA 3': 'List of Banks incorporated in Gibraltar entitled to accept deposits through a branch in the UK',

        'GB PRA 4': 'List of Banks incorporated in the EEA entitled to accept deposits in the UK while in the Temporary Permissions Regime (TPR)',

        'GB PRA 5': 'List of Banks incorporated in the EEA entitled to accept deposits through a branch in the UK while in Supervised Run Off (SRO)',

        'GB PRA 6': 'List of Banks incorporated in the United Kingdom',

        'GB PRA 7': 'List of Banks incorporated outside the EEA authorised to accept deposits through a branch in the UK',

        'GB PRA 8': 'List of Banks incorporated outside the UK authorised to accept deposits through a branch in the UK',

        'GB PRA 9': 'List of Building Societies incorporated in the UK',

        'GB PRA 10': 'List of Building Societies incorporated in the United Kingdom (based on PRA authorisation status)',

        'GB PRA 11': 'List of Designated Investment Firms',

        'GB PRA 12': 'List of Individual RFBs',

        'GB PRA 13': 'List of Insurers incorporated in the EEA entitled to carry out contracts of insurance through a branch in the UK while in Supervised Run Off (SRO)',

        'GB PRA 14': 'List of UK Authorised Credit Unions',

        'GB PRA 15': 'List of Parent Financial Holding Companies/Parent Mixed Financial Holding Companies',

        }



sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [], 

         'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [], 

         'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [], 

         'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],

         'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [], 

         'Phone - Mother company': [], 'Check': []}

    

processdate = now.strftime('%Y-%m-%d')



# %%

#------------------------------------------------ Begin_Fouction ----------------------------------------

def bourange_same_length_array(sqldict) :

    len_value=[]

    for key, value in sqldict.items():

        len_value.append(len(value))

    maxlen = max(len_value)

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

            print(f"[INFO] : -- {fileType} file = {os.listdir(tempfolder)})")

            break

        else:

            print(f"[INFO] : -- Download {fileType} file ... (wait {time*2}/20 s)")

            sleep(2)

    else:

        raise Exception(f'[ERROR] : - Failed to Download {fileType} file. Run Script again' )

    return  os.listdir(tempfolder)[0]



def click_element_by_xpath(driver, xpath):

    # Find the element and click

    element = driver.find_element(By.XPATH, xpath)

    element.click()

    

    

def click_on_cookies(xpath, Msg_accept='I Accept'):

    try:

        driver.find_element(By.XPATH,xpath).click()

        print(f'[INFO] : click "{Msg_accept}" button')

    except Exception :

        print(f'[ERROR] : Failed to click "{Msg_accept}" button on the cookies banner')

        



def scrollinAndClick(xpath):

    for times in range(60):

        try:

            driver.find_element(By.XPATH, xpath).click()

            sleep(1)

            break

        except:

            print(f"[ERROR] : trying {times+1}/10 to key press 'DOWN' (scrolling)")

            sleep(1)

            driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.DOWN)

    else:   

        raise Exception(f'[ERROR] : Failed scrollin Or Click on xpath element : {xpath}')



def selected_last_date(partial_xpath): 

    months = {

    'January'   :1, 'February'  :2, 'March'     :3, 'April'     :4, 'May'       :5, 'June'      :6, 

    'July'      :7, 'August'    :8, 'September' :9, 'October'   :10, 'November' :11, 'December' :12,

    }

    print(f"[INFO] : - Check last date. Wait...")

    for y in range(3):

        year = int(now.strftime('%Y')) -y

        for month, number in months.items():

            try:

                xpath = f'//*[@id="main-content"]//*/a[contains(normalize-space(.),"{partial_xpath} - {month} {year}")]'

                driver.find_element(By.XPATH, xpath).click()

                print(f"[INFO] : -- last date Selected is {number}-{year} | {driver.find_element(By.XPATH, xpath).text} ")

                stop = True

                break

            except :

                # print(f"[EROR] : - Failed to select date {month} {year}, trying next month")

                sleep(1)

        else:

            print(f"[INFO] : - No more months available for the year {year}")

            sleep(0.5)

            continue  



        if stop:

            break  



def find_line_number(file, key_word) :

    with open(file, "rb") as myfile:

        for i, line in enumerate(myfile):

            line = line.decode('UTF-8', errors='ignore').replace('\r\n', '').replace('"', '')

            if line.find(key_word) != -1:

                return i  

    raise ValueError(f"[ERROR] keyword not found in {file}: {key_word!r}")



# %%

#------------------------------------------------ Begin_Main ----------------------------------------

for k,reg in enumerate(regdict):



    print(f"[INFO] : Working {k+1}/{len(regdict)} _({reg})_ ")



    if reg in ['GB PRA 1', 'GB PRA 2', 'GB PRA 3', 'GB PRA 5', 'GB PRA 6', 'GB PRA 8', 'GB PRA 9', 'GB PRA 11', 'GB PRA 13', 'GB PRA 14'] :

        # driver.get(regdict[reg])

        driver.get('https://www.bankofengland.co.uk/prudential-regulation/authorisations/which-firms-does-the-pra-regulate')

        sleep(3)

        click_on_cookies('//*/button[contains(text(),"Accept recommended cookies")]')

        sleep(1)

        selected_last_date(regdict[reg])

        file =  check_dowload_files(tempfolder, "csv" )

        filePath = os.path.join(tempfolder, file)

        

        with_LEI = ['GB PRA 3', 'GB PRA 5', 'GB PRA 6', 'GB PRA 8', 'GB PRA 9', 'GB PRA 10', 'GB PRA 11']



        if reg == 'GB PRA 1':

            start = find_line_number(filePath, 'Insurers incorporated in Gibraltar authorised') + 2

            columns = ['Firm Name', 'FRN', 'Regulated Activities']

        elif reg == 'GB PRA 2':

            start = find_line_number(filePath, 'Insurers incorporated in the UK authorised') + 2

            columns = ['Firm Name', 'FRN', 'Regulated Activities']

        elif reg == 'GB PRA 3':

            start = find_line_number(filePath, 'Banks incorporated in Gibraltar authorised') + 2

            columns = ['Firm Name', 'FRN', 'LEI']

        elif reg == 'GB PRA 5':

            start = find_line_number(filePath, 'Banks incorporated in the EEA authorised') + 2

            columns = ['Firm Name', 'FRN', 'LEI']

        elif reg == 'GB PRA 6':

            start = find_line_number(filePath, 'Banks incorporated in the UK authorised to accept deposits') + 2

            columns = ['Firm Name', 'FRN', 'LEI']

        elif reg == 'GB PRA 8':

            start = find_line_number(filePath, 'Banks incorporated outside') + 2

            columns = ['Firm Name', 'FRN', 'LEI']

        elif reg == 'GB PRA 9':

            start = find_line_number(filePath, 'List of PRA-regulated Building Societies') + 2

            columns = ['Firm Name', 'FRN', 'LEI']

        elif reg == 'GB PRA 11':

            start = find_line_number(filePath, 'List of PRA-regulated Designated Investment Firms') + 2

            columns = ['Firm Name','FRN','LEI']

        elif reg == 'GB PRA 13':

            start = find_line_number(filePath, 'Insurers incorporated in the EEA entitled to carry') + 2

            columns = ['Firm Name', 'FRN', 'Regulated Activities'] 

        elif reg == 'GB PRA 14':

            start = find_line_number(filePath, 'Credit Unions incorporated in the UK') + 2

            columns = ['Firm Name', 'FRN']



        df = pd.read_csv(filePath)

        df.columns = columns

        df = df.fillna("")  # subsitute nan with empty strings

        df = df[start:]

        df = df[df['FRN'].notna() & (df['FRN'] != '')]

        # df = df.drop_duplicates(subset=["FRN"], keep="first", inplace=False, ignore_index=True)

        df = df.reset_index(drop=True)



        print(f"[INFO] : --- DataFrame '{file}' | containe = {df.shape}")

        for index, row in df.iterrows():

            if row['FRN'] != 'FRN' :

                sqldict['Name'].append(row['Firm Name'])

                sqldict['Typology'].append(Typology[reg])

                sqldict['RegulationType'].append('Supervised')

                sqldict['InternalID_1_type'].append('FRN')

                sqldict['InternalID_1'].append(row['FRN']) 

                sqldict['LEI Code'].append(row['LEI']) if reg in with_LEI else sqldict['LEI Code'].append('')

                sqldict['ListProcessDate'].append(processdate)

                sqldict['RegCtry'].append(reg.split(' ')[0])

                sqldict['RegCode'].append(reg.split(' ')[1])

                sqldict['ListCode'].append(reg.split(' ')[-1])

                sqldict = bourange_same_length_array(sqldict)

            else:

                break



        for rem in os.listdir(tempfolder):

            os.remove(os.path.join(tempfolder, rem)) 

          

    elif reg  == 'GB PRA 12':
        driver.get('https://www.bankofengland.co.uk/prudential-regulation/authorisations/which-firms-does-the-pra-regulate')
        sleep(3)
        click_on_cookies('//*/button[contains(text(),"Accept recommended cookies")]')
        sleep(1)
        scrollinAndClick(f"//a[contains(text(), '{regdict[reg]}')]")

        file =  check_dowload_files(tempfolder, "pdf" )

        filePath = os.path.join(tempfolder, file)

        publish_date  = ''

        pages_text = list()

        bold_lines = list()

        table = list()

        for i in os.listdir(tempfolder)[0].split('-')[-2:]:

            publish_date+=i

        with pdfplumber.open(filePath) as pdf:

            for page in pdf.pages:

                tables = page.extract_tables(table_settings={})

                for index,table in enumerate(tables[0]):

                    if table == ['',None,'',None]:

                        pass

                    else:

                        if table[0] == 'Banking Group':

                            pass

                        else:

                            #print(table)

                            if table[0] is not None:

                                banking_group = table[0]

                                RFBs = table[-1]

                            else:

                                RFBs = table[-1]

                            #print(banking_group)

                            sqldict['Name - Mother Company'].append(banking_group)

                            #print(RFBs)

                            sqldict['Name'].append(RFBs)

                            sqldict['RegCtry'].append(reg.split(' ')[0]) 

                            sqldict['RegCode'].append(reg.split(' ')[1])

                            sqldict['ListCode'].append(reg.split(' ')[-1])

                            sqldict['ListName'].append(Typology[reg])

                            sqldict['ListProcessDate'].append(processdate)

                            sqldict['RegulationType'].append('Regulated')

                            sqldict['RegulationDate'].append(publish_date[:-4])   

                             

                        sqldict = bourange_same_length_array(sqldict)



        for rem in os.listdir(tempfolder):

            os.remove(os.path.join(tempfolder, rem)) 

            

    elif reg == 'GB PRA 15':

        driver.get(regdict[reg])

        sleep(2)

        click_on_cookies('//*[@id="modal-content-id-1"]//*/button[contains(text(),"Allow All")]')

        sleep(1)

        soup = BeautifulSoup(driver.page_source, 'html.parser')

        click_element_by_xpath(driver, '//*[@id="bhc-data-resultcountselect-button"]') # Click Show All Button

        print(f"[INFO] : - Click Show All Button _({reg})_ ")  

        sleep(2)

        soup = BeautifulSoup(driver.page_source, 'html.parser')

        table = soup.find("table")

        hrefs = ['https://register.fca.org.uk/s/'+ a['href'][2:] for a in table.find_all('a')]

        print(f'[INFO] : -- Total link Scrapping = {len(hrefs)} | {reg}')    

                

        for i,href in enumerate(hrefs):

            driver.get(href)

            print(f'[INFO] : -- Scrapping link {i+1}/{len(hrefs)}') 

            sleep(2)

            soup = BeautifulSoup(driver.page_source, 'html.parser')

            Name = soup.find('div', {'id':'profile-header'}).find('h1').text.strip()

            details_content = soup.find('div', {'id':'who-is-this-details-content'}).find_all('p')



            if len(details_content) == 2:

                Phone = ''

                Email = ''

                Company_ref_number = details_content[1].text.strip() 

            elif len(details_content) == 3:

                Phone = details_content[1].text.replace('\xa0', ' ').strip()

                Email = ''

                Company_ref_number = details_content[2].text.strip()

            elif len(details_content) == 4:

                Phone = details_content[1].text.replace('\xa0', ' ').strip()

                Email = details_content[2].text.strip()

                Company_ref_number = details_content[3].text.strip()

                

            try:

                if len(soup.find('div', {'id':'who-is-this-details-content'}).find_all('a')) == 1 :

                    Website = ''

                    Registered_company_number = soup.find('div', {'id':'who-is-this-details-content'}).find_all('a')[0].text.split('.')[0].strip()

                else :

                    Website = soup.find('div', {'id':'who-is-this-details-content'}).find_all('a')[0]['href'][2:]

                    Registered_company_number = soup.find('div', {'id':'who-is-this-details-content'}).find_all('a')[1].text.split('.')[0].strip()

            except :

                continue



            for br in details_content[0].find_all('br') :

                br.replace_with('\n')



            Complet_Address = details_content[0].text.strip().split('\n')

            Address_2 = Complet_Address[1] if len(Complet_Address) > 4 else ''

            Address_1 = Complet_Address[0]

            City = Complet_Address[-3] 

            Zip = Complet_Address[-2]

            Cntry = Complet_Address[-1]



            sqldict['Name'].append(Name)

            sqldict['Address_1'].append(Address_1)

            sqldict['Address_2'].append(Address_2)

            sqldict['Zip'].append(Zip)

            sqldict['City'].append(City)

            sqldict['Typology'].append(Typology[reg])

            sqldict['RegulationType'].append('Supervised')

            sqldict['InternalID_1_type'].append('Reference Number')

            sqldict['InternalID_1'].append(Company_ref_number)

            sqldict['InternalID_2'].append(Registered_company_number) 

            sqldict["InternalID_2_type"].append("Registered number") 

            # sqldict['LEI Code'].append(row['ID_LEI'])

            sqldict['Website'].append(Website)

            sqldict['Phone'].append(Phone)

            sqldict['Cntry'].append(Cntry)

            sqldict['ListProcessDate'].append(processdate)

            sqldict['RegCtry'].append(reg.split(' ')[0])

            sqldict['RegCode'].append(reg.split(' ')[1])

            sqldict['ListCode'].append(reg.split(' ')[-1])



            sqldict = bourange_same_length_array(sqldict)



# %%

#------------------------------------------------ Begin_writer and save df to excel  ----------------------------------------

os.chdir(scriptfolder)

df=pd.DataFrame(sqldict)

df.to_excel(writer, 'SQL Ready', index=False)

writer.close()

driver.quit()

sleep(3)
    
    
    