# %%

#------------------------------------------------ Begin_Librairie ----------------------------------------

import pandas as pd

from bs4 import BeautifulSoup

from time import sleep

from datetime import datetime

from pandas import ExcelWriter

from selenium import webdriver

from selenium.webdriver.common.by import By

import datetime

import os

from selenium.webdriver.chrome.service import Service as ChromeService



# %%

# %%

#------------------------------------------------ Begin_ fileName ----------------------------------------
regulatorName = 'CA AMF'

print(f"Running{regulatorName} Web Scraping Tool v.1.0")


now=datetime.datetime.now()

filename= 'CA AMF Data {}.xlsx'.format(str(now).replace(":",".")[:-7])


#scriptfolder = f"C:\\Users\\wuj1\\OneDrive - moodys.com\\Desktop\\Regulator\\{regulatorName}" ## to comment for the local environment

scriptfolder=os.path.dirname(os.path.abspath(__file__)) ## to decomment for the production environment

os.chdir(scriptfolder)

writer = ExcelWriter(filename)

tempfolder=os.path.join(scriptfolder, 'tempfolder') 



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

        web_driver.find_element(By.XPATH,f'//*[@id="ccc-notify-accept"]/span[contains(text(),"Accept")]').click()

    except Exception as err:

        print('[ERROR] : Failed to click "I Accept" button on the cookies banner:', err)
        

# Define a function to scroll to the bottom of the page

def scroll_to_bottom(driver):

    # Get scroll height

    last_height = driver.execute_script("return document.body.scrollHeight")



    while True:

        # Scroll down to the bottom

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        # Wait to load the page

        sleep(3)
        # Calculate new scroll height and compare with last scroll height

        new_height = driver.execute_script("return document.body.scrollHeight")

        if new_height == last_height:

            break

        last_height = new_height

def click_element_by_xpath(driver, xpath):

    # Find the element and click

    element = driver.find_element(By.XPATH, xpath)

    element.click()
    

def click_on_cookies(web_driver):

    try:

        web_driver.find_element(By.XPATH,f'//*[@id="cookiesjsr"]/div/div/div/div/div[2]/button[2]').click()
        print('[Success] : Success to Click Cookie')

    except Exception as err:

        print('[ERROR] : Failed to click "I Accept" button on the cookies banner:', err)
        

def scrollinAndClick(xpath,key_press=False):
    if len(xpath) != 0 :
        for times in range(60):
            try:
                driver.find_element(By.XPATH, xpath).click()
                sleep(1)
                break
            except:
                print(f"[ERROR] : trying {times+1}/10 to key press 'DOWN' (scrolling)")
                sleep(1)
                if key_press:                    
                    driver.find_element(By.TAG_NAME, 'body').send_keys(key_press)
        else:   
            raise Exception(f'[ERROR] : Failed scrollin Or Click on xpath element : {xpath}')

# %%

#------------------------------------------------ Begin_Variable ----------------------------------------

# Find the inner web link into Browser-devTools-Network, because use the link will not show cookie, avoid one click

mainAddress = 'https://registres-public.lautorite.qc.ca/1A/Regs.RegistreWeb.Web/en/InstitutionsFinancieres'

regdict={

        'CA AMF 1': 'https://registres-public.lautorite.qc.ca/1A/Regs.RegistreWeb.Web/en/InstitutionsFinancieres',

        'CA AMF 2': 'https://registres-public.lautorite.qc.ca/1A/Regs.RegistreWeb.Web/en/InstitutionsFinancieres',
        
        'CA AMF 3': 'https://registres-public.lautorite.qc.ca/1A/Regs.RegistreWeb.Web/en/InstitutionsFinancieres',
        
        'CA AMF 4': 'https://registres-public.lautorite.qc.ca/1A/Regs.RegistreWeb.Web/en/InstitutionsFinancieres',
        
        }



Typology={'CA AMF 1': 'Deposit institutions',

        'CA AMF 2': 'List of trust companies',
        
        'CA AMF 3': 'List of savings companies',
        
        'CA AMF 4': 'List of insurers'}



sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [], 

         'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [], 

         'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [], 

         'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],

         'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [], 

         'Phone - Mother company': [], 'Check': []}



processdate = now.strftime('%Y-%m-%d')

# %%

#------------------------------------------------ Begin_Main ----------------------------------------

driver.get(mainAddress)

sleep(3)

scroll_to_bottom(driver)
click_element_by_xpath(driver, '//*[@id="ui-id-5"]')
sleep(3)
click_element_by_xpath(driver,'//*[@id="ui-id-6"]/a[2]') 

sleep(5)

excel_file = os.listdir(tempfolder)[0]
filePath = os.path.join(tempfolder, excel_file)
data = pd.read_excel(filePath,engine='xlrd', usecols='B:H', skiprows=10, nrows=476)


for type, name, deposits  in zip(data['Type of institution'], data['French name'], data['Authorized to solicit and receive deposits in Québec']):

    sqldict['ListProcessDate'].append(processdate)
    sqldict['Typology'].append(type)
    sqldict['Name'].append(name)
    sqldict['RegulationType'].append('Authorized')
    sqldict['RegCtry'].append('CA')
    sqldict['RegCode'].append('AMF')
    
    if deposits == 'Yes':
        sqldict['ListCode'].append('1')
    else:
        if type=='Trust company':
            sqldict['ListCode'].append('2')
        elif type == "Savings company":
            sqldict['ListCode'].append('3')
        else:
            sqldict['ListCode'].append('4')
            
            

for rem in os.listdir(tempfolder):
    os.remove(os.path.join(tempfolder, rem))

          
            
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
    



