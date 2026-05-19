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

import re

import pdfplumber

from selenium.webdriver.chrome.service import Service as ChromeService



# %%

#------------------------------------------------ Begin_ fileName ----------------------------------------
regulatorName = 'GB PRA'

print(f"Running{regulatorName} Web Scraping Tool v.1.0")


now=datetime.datetime.now()

filename= 'GB PRA Data {}.xlsx'.format(str(now).replace(":",".")[:-7])

scriptfolder = f"C:\\Users\\wuj1\\OneDrive - moodys.com\\Desktop\\Regulator\\{regulatorName}" ## to comment for the local environment

#scriptfolder=os.path.dirname(os.path.abspath(__file__)) ## to decomment for the production environment

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

        web_driver.find_element(By.XPATH,f'//*[@id="modal-content-id-1"]/footer/div/button[3]').click()
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

#------------------------------------------------ Begin_Variable ----------------------------------------

# Find the inner web link into Browser-devTools-Network, because use the link will not show cookie, avoid one click

# mainAddress = 'https://registres-public.lautorite.qc.ca/1A/Regs.RegistreWeb.Web/en/InstitutionsFinancieres'

regdict={

          'GB PRA 1': 'https://www.bankofengland.co.uk/prudential-regulation/authorisations/which-firms-does-the-pra-regulate',
          
          'GB PRA 13': 'https://www.bankofengland.co.uk/prudential-regulation/authorisations/which-firms-does-the-pra-regulate',

          'GB PRA 2': 'https://www.bankofengland.co.uk/prudential-regulation/authorisations/which-firms-does-the-pra-regulate',
        
         'GB PRA 3': 'https://www.bankofengland.co.uk/prudential-regulation/authorisations/which-firms-does-the-pra-regulate',
        
        # # 'GB PRA 4': 'https://www.bankofengland.co.uk/prudential-regulation/authorisations/which-firms-does-the-pra-regulate',
        
        # # 'GB PRA 5': 'https://www.bankofengland.co.uk/prudential-regulation/authorisations/which-firms-does-the-pra-regulate',
        
        # # 'GB PRA 6': 'https://www.bankofengland.co.uk/prudential-regulation/authorisations/which-firms-does-the-pra-regulate',
        
        # # 'GB PRA 7': 'https://www.bankofengland.co.uk/prudential-regulation/authorisations/which-firms-does-the-pra-regulate',
        
        # # 'GB PRA 8': 'https://www.bankofengland.co.uk/prudential-regulation/authorisations/which-firms-does-the-pra-regulate',
        
        # # 'GB PRA 9': 'https://www.bankofengland.co.uk/prudential-regulation/authorisations/which-firms-does-the-pra-regulate',
        
         'GB PRA 10': 'https://www.bankofengland.co.uk/prudential-regulation/authorisations/which-firms-does-the-pra-regulate',
        
         'GB PRA 11': 'https://www.bankofengland.co.uk/prudential-regulation/authorisations/which-firms-does-the-pra-regulate',
        
         'GB PRA 12': 'https://www.bankofengland.co.uk/prudential-regulation/authorisations/which-firms-does-the-pra-regulate',
        
        
         'GB PRA 14': 'https://www.bankofengland.co.uk/prudential-regulation/authorisations/which-firms-does-the-pra-regulate',
        
         'GB PRA 15': 'https://register.fca.org.uk/s/search?predefined=BHC',
        
        }



Typology={
        'GB PRA 1': 'Authorised UK Insurers',

        'GB PRA 2': 'Authorised Insurers Incorporated In Gibraltar',
        
        'GB PRA 13': 'Insurers Incorporated In The EEA With Deemed Part Iva Permission In The SRO',
        
        'GB PRA 3': 'Banks incorporated in Gibraltar entitled to accept deposits through a branch in the UK',
        
        'GB PRA 4': 'Banks incorporated in the EEA entitled to accept deposits in the UK while in the Temporary Permissions Regime (TPR)',
        
        'GB PRA 5': 'Banks incorporated in the EEA entitled to accept deposits through a branch in the UK while in Supervised Run Off (SRO)',
        
        'GB PRA 6': 'Banks incorporated in the United Kingdom',
        
        'GB PRA 7': 'Banks incorporated outside the EEA authorised to accept deposits through a branch in the UK',
        
        'GB PRA 8': 'Banks incorporated outside the UK authorised to accept deposits through a branch in the UK',
        
        'GB PRA 9': 'Building Societies incorporated in the UK',
        
        'GB PRA 10': 'Building Societies incorporated in the United Kingdom (based on PRA authorisation status)',
        
        'GB PRA 11': 'Designated Investment Firms',
        
        'GB PRA 12': 'Individual RFBs',
        
        'GB PRA 14': 'UK Authorised Credit Unions',
        
        'GB PRA 15': 'Parent Financial Holding Companies/Parent Mixed Financial Holding Companies',
        }



sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [], 

         'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [], 

         'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [], 

         'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],

         'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [], 

         'Phone - Mother company': [], 'Check': []}



processdate = now.strftime('%Y-%m-%d')



# %%

#------------------------------------------------ Begin_Main ----------------------------------------

for k,reg in enumerate(regdict):
    print(f"[INFO] : Working {k+1}/{len(regdict)} _({reg})_ ")   

    
    # List of Parent Financial Holding Companies/Parent Mixed Financial Holding Companies
    # Except List code 15, the rest of list need to be cope with PDF document
    if reg == 'GB PRA 15':
        driver.get(regdict[reg])
        sleep(4)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        click_on_cookies(driver)
        sleep(4)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        click_element_by_xpath(driver, '//*[@id="bhc-data-resultcountselect-button"]')
        print(f"[INFO] : Click Show All Button _({reg})_ ")  
        driver.maximize_window()
        sleep(4)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        table = soup.find("table")
        rows = table.find_all('tr', class_='data-table__row')
        
        filtered_rows = []
        for row in rows:
            tds = row.find_all('td')
            # Check if any td element has non-empty text
            if any(td.text.strip() != '' for td in tds):
                filtered_rows.append(row)
        print(f'[INFO] : - Data Scrapping = {len(filtered_rows)} | {reg}')    
                
        for i,row in enumerate(filtered_rows):
            tds = row.find_all('td')
            
            for i, td in enumerate(tds):
                if td.text!='':
                    if i == 0:
                        sqldict['Name'].append(tds[i].find_all('span')[-1].text.strip())
                    elif i ==1:
                        sqldict['InternalID_1'].append(tds[i].find_all('span')[-1].text.strip())
                        sqldict['InternalID_1_type'].append('Reference Number')
                    elif i ==2:
                        sqldict['RegulationType'].append(tds[i].find_all('span')[-1].text.strip())
                    elif i ==3:
                        sqldict['RegulationDate'].append(tds[i].find_all('span')[-1].text.strip())
                    elif i ==4:
                        sqldict['CancellationDate'].append(tds[i].find_all('span')[-1].text.strip())
                    elif i ==5:
                        sqldict['Cntry'].append(tds[i].find_all('span')[-1].text.strip())

            sqldict['ListProcessDate'].append(processdate)
            sqldict['RegCtry'].append(reg.split(' ')[0]) 

            sqldict['RegCode'].append(reg.split(' ')[1])

            sqldict['ListCode'].append(reg.split(' ')[-1])
            sqldict['Typology'].append(Typology[reg])
    elif reg == 'GB PRA 1' or reg == 'GB PRA 2' or  reg == 'GB PRA 13':
        driver.get(regdict[reg])
        sleep(4)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        try:
            # try to click cookie
            click_element_by_xpath(driver,'/html/body/div/div[1]/div/div/table/tbody/tr[2]/td[3]/button')
            print(f"[INFO] : Click Cookie _({reg})_ ")  
        except:
            pass
        sleep(4)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Click Insurance Sector
        click_element_by_xpath(driver, '//*[@id="main-content"]/section[3]/div/div[1]/div[2]/ul/li[5]/a')
        sleep(4)
        print(f"[INFO] : {Typology[reg]} _({reg})_ ")  
        click_element_by_xpath(driver,'//*[@id="item-10"]/div[1]/h3/button')
        if reg == 'GB PRA 1':
            # Click List of UK Insurers
            sleep(3)
            #file = driver.find_element(By.XPATH, '//*[@id="main-content"]/section[8]/div/div[1]/div[2]/ul/li[1]').click()
            file = driver.find_element(By.XPATH, '//*[@id="content-item-10"]/div[1]/ul/li[1]/a').click()
        elif reg == 'GB PRA 2':
            sleep(3)
            file = driver.find_element(By.XPATH, '//*[@id="content-item-10"]/div[1]/ul/li[3]/a').click()
        elif reg == 'GB PRA 13':
            sleep(3)
            file = driver.find_element(By.XPATH, '//*[@id="content-item-10"]/div[1]/ul/li[2]/a').click()
            
        for times in range(50):
            dl_files = [os.path.join(tempfolder, f) for f in os.listdir(tempfolder)]
            if len(dl_files)>0 and not dl_files[0].endswith('.tmp') and not dl_files[0].endswith('.crdownload'):
                break
            sleep(3)
        else:
            raise Exception(f'{regulatorName} - Failed to download file - '+reg)
        pages_text = list()
        bold_lines = list()
        with pdfplumber.open(dl_files[0]) as pdf:
            for page in pdf.pages:
                bold_text = page.filter(lambda obj: obj["object_type"] == "char" and "Bold" in obj["fontname"]).extract_text()
                if bold_text is not None:
                    bold_lines.extend([ele.strip() for ele in bold_text.split('\n') if len(ele) > 0])            
                pages_text.append(page.extract_text().strip())

        all_text = '\n'.join(pages_text)
        publish_date  = ''
        for i in os.listdir(tempfolder)[0].split('-')[-2:]:
            publish_date+=i
        lines = [ele.strip() for ele in all_text.split('\n') if len(ele.strip()) > 0]
        
        for item in lines:

            if '-' in item: 
                #content_before = re.split(r'[X-]', item)
                if ( reg == 'GB PRA 1') or ( reg == 'GB PRA 13') :
                    match = re.match(r'^(.*?\d{4,})(.*)$', item)
                    if match:
                        # Extract the parts before and after the number
                        content_before = match.group(1).strip()

                        if content_before.strip() != '':
                            content_text = re.sub(r'\b\d{6}\b', '', content_before)
                            id_FRN= re.findall(r'\b\d{6,}\b', content_before)
                            for FRN in id_FRN:
                                sqldict['InternalID_1'].append(FRN)
                            #print((content_text))
                            sqldict['Name'].append(content_text)
                            sqldict['ListProcessDate'].append(processdate)
                                                
                        sqldict['RegCtry'].append(reg.split(' ')[0]) 

                        sqldict['RegCode'].append(reg.split(' ')[1])

                        sqldict['ListCode'].append(reg.split(' ')[-1])
                        sqldict['Typology'].append(Typology[reg])

                        sqldict['RegulationType'].append('AUTHORISED')

                        sqldict['RegulationDate'].append(publish_date[:-4])
                        
                        sqldict['InternalID_1_type'].append('FRN')
                elif ( reg == 'GB PRA 2'):
                    match = re.match(r'^(.*?\d{4,})(.*)$', item)
                    if match:
                        content_before = match.group(2).strip()
                        id_FRN= match.group(1).strip()
                        sqldict['InternalID_1'].append(id_FRN)
                        sqldict['InternalID_1_type'].append('FRN')
                        names = ''
                        for name in content_before.split(' ')[:-18]:
                            names+=name+' '

                        sqldict['Name'].append(names)
                        sqldict['ListProcessDate'].append(processdate)

                        sqldict['RegCtry'].append(reg.split(' ')[0]) 

                        sqldict['RegCode'].append(reg.split(' ')[1])

                        sqldict['ListCode'].append(reg.split(' ')[-1])
                        sqldict['Typology'].append(Typology[reg])

                        sqldict['RegulationType'].append('AUTHORISED')
                        sqldict['RegulationDate'].append(publish_date[:-4])
                
        
        
        for rem in os.listdir(tempfolder):
            os.remove(os.path.join(tempfolder, rem)) 
    elif reg == 'GB PRA 10' or reg == 'GB PRA 12':
        
        driver.get(regdict[reg])
        sleep(4)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        try:
            # try to click cookie
            click_element_by_xpath(driver,'/html/body/div/div[1]/div/div/table/tbody/tr[2]/td[3]/button')
            print(f"[INFO] : Click Cookie _({reg})_ ")  
        except:
            pass
        sleep(4)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Click Building Societies Sector
        click_element_by_xpath(driver, '//*[@id="main-content"]/section[3]/div/div[1]/div[2]/ul/li[2]/a')
        print(f"[INFO] : Click {Typology[reg]} _({reg})_ ")  
        sleep(3)
        
        
        if reg == 'GB PRA 10':
            file = driver.find_element(By.XPATH, '//*[@id="main-content"]/section[5]/div/div[1]/div[2]/ul/li/a').click()
        elif reg  == 'GB PRA 12':
            file = driver.find_element(By.XPATH, '//*[@id="main-content"]/section[5]/div/div[1]/div[4]/ul/li/a').click()
            
        
        for times in range(50):
            dl_files = [os.path.join(tempfolder, f) for f in os.listdir(tempfolder)]
            if len(dl_files)>0 and not dl_files[0].endswith('.tmp') and not dl_files[0].endswith('.crdownload'):
                break
            sleep(3)
        else:
            raise Exception(f'{regulatorName} - Failed to download file - '+reg)
        
        if reg == 'GB PRA 10':
            pages_text = list()
            bold_lines = list()
            with pdfplumber.open(dl_files[0]) as pdf:
                for page in pdf.pages:
                    bold_text = page.filter(lambda obj: obj["object_type"] == "char" and "Bold" in obj["fontname"]).extract_text()
                    if bold_text is not None:
                        bold_lines.extend([ele.strip() for ele in bold_text.split('\n') if len(ele) > 0])            
                    pages_text.append(page.extract_text().strip())

            all_text = '\n'.join(pages_text)
            lines = [ele.strip() for ele in all_text.split('\n') if len(ele.strip()) > 0]
            
            contents = lines[len(bold_lines)+1:]
            
            for item in lines[len(bold_lines)+1:-1]:
                id = item.split(' ')[-1]
                name = re.sub(id, '', item)
                sqldict['Name'].append(name)
                sqldict['ListProcessDate'].append(processdate)
                sqldict['InternalID_1'].append(id)
                sqldict['InternalID_1_type'].append('InternalID')
                sqldict['RegCtry'].append(reg.split(' ')[0]) 
                sqldict['RegCode'].append(reg.split(' ')[1])
                sqldict['ListCode'].append(reg.split(' ')[-1])
                sqldict['Typology'].append(Typology[reg])

                sqldict['RegulationType'].append('Regulated')
                sqldict['RegulationDate'].append(lines[-1].split(' ')[0])
            for rem in os.listdir(tempfolder):
                os.remove(os.path.join(tempfolder, rem)) 
                
        elif reg  == 'GB PRA 12':
            publish_date  = ''
            pages_text = list()
            bold_lines = list()
            table = list()
            for i in os.listdir(tempfolder)[0].split('-')[-2:]:
                publish_date+=i
            with pdfplumber.open(dl_files[0]) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables(table_settings={})
                    for table in tables[1:]:
                        if (table[0]==['', '']) :
                            row_content = table[1:]    
                            for index, row in row_content:
                                sqldict['Name'].append(row)
                                sqldict['ListProcessDate'].append(processdate)
                                if index!=None:
                                    #print(row[0])
                                    Group_name = index
                                    #print('-------Group Name:', Group_name)
                                    sqldict['Name - Mother Company'].append(Group_name)
                                    
                                else:
                                    index = Group_name
                                    #print('**********',index)
                                    sqldict['Name - Mother Company'].append(index)
                                sqldict['RegCtry'].append(reg.split(' ')[0]) 
                                sqldict['RegCode'].append(reg.split(' ')[1])
                                sqldict['ListCode'].append(reg.split(' ')[-1])
                                sqldict['Typology'].append(Typology[reg])

                                sqldict['RegulationType'].append('Regulated')
                                sqldict['RegulationDate'].append(publish_date[:-4])       

                        elif (table[0]==['', '','']):
                            row_content = table[2:]    
                            #print(row_content)
                            for index, row,empty in row_content:
                                # print(row)
                                sqldict['Name'].append(row)   
                                sqldict['ListProcessDate'].append(processdate)
                                if index!=None:
                                    #print(row[0])
                                    Group_name = index
                                    #print('-------Group Name:', Group_name)
                                    sqldict['Name - Mother Company'].append(Group_name)
                                else:
                                    index = Group_name
                                    #print('**********',index)
                                    sqldict['Name - Mother Company'].append(index)
                                sqldict['RegCtry'].append(reg.split(' ')[0]) 
                                sqldict['RegCode'].append(reg.split(' ')[1])
                                sqldict['ListCode'].append(reg.split(' ')[-1])
                                sqldict['Typology'].append(Typology[reg])

                                sqldict['RegulationType'].append('Regulated')
                                sqldict['RegulationDate'].append(publish_date[:-4])                            
        
    
        for rem in os.listdir(tempfolder):
            os.remove(os.path.join(tempfolder, rem))         
    elif reg == 'GB PRA 14':
        driver.get(regdict[reg])
        sleep(4)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        try:
            # try to click cookie
            click_element_by_xpath(driver,'/html/body/div/div[1]/div/div/table/tbody/tr[2]/td[3]/button')
            print(f"[INFO] : Click Cookie _({reg})_ ")  
        except:
            pass
        sleep(4)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Click Insurance Sector
        click_element_by_xpath(driver, '//*[@id="main-content"]/section[3]/div/div[1]/div[2]/ul/li[7]/a')
        print(f"[INFO] : {Typology[reg]} _({reg})_ ") 
        sleep(3)
        file = driver.find_element(By.XPATH, '//*[@id="main-content"]/section[10]/div/div[1]/div[2]/ul/li/a').click()
        
        for times in range(50):
            dl_files = [os.path.join(tempfolder, f) for f in os.listdir(tempfolder)]
            if len(dl_files)>0 and not dl_files[0].endswith('.tmp') and not dl_files[0].endswith('.crdownload'):
                break
            sleep(3)
        else:
            raise Exception(f'{regulatorName} - Failed to download file - '+reg)
        pages_text = list()
        bold_lines = list()
        with pdfplumber.open(dl_files[0]) as pdf:
            for page in pdf.pages:
                bold_text = page.filter(lambda obj: obj["object_type"] == "char" and "Bold" in obj["fontname"]).extract_text()
                if bold_text is not None:
                    bold_lines.extend([ele.strip() for ele in bold_text.split('\n') if len(ele) > 0])            
                pages_text.append(re.sub(bold_text,'',page.extract_text().strip()))


        all_text = '\n'.join(pages_text)
        lines = [ele.strip() for ele in all_text.split('\n') if len(ele.strip()) > 0]
        date = lines[-1]
        for item in lines[3:-1]:
            #print(item)
            id = item.split(' ')[-1]
            if len(id)>3:
                name = re.sub(id, '', item)
                # print(name)
                # print(id)
                sqldict['Name'].append(name)
                sqldict['ListProcessDate'].append(processdate)
                sqldict['InternalID_1'].append(id)
                sqldict['InternalID_1_type'].append('InternalID')
                sqldict['RegCtry'].append(reg.split(' ')[0]) 
                sqldict['RegCode'].append(reg.split(' ')[1])
                sqldict['ListCode'].append(reg.split(' ')[-1])
                sqldict['Typology'].append(Typology[reg])

                sqldict['RegulationType'].append('Regulated')
                sqldict['RegulationDate'].append(date.split(' ')[0])
    elif reg == 'GB PRA 11':
        driver.get(regdict[reg])
        sleep(4)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        try:
            # try to click cookie
            click_element_by_xpath(driver,'/html/body/div/div[1]/div/div/table/tbody/tr[2]/td[3]/button')
            print(f"[INFO] : Click Cookie _({reg})_ ")  
        except:
            pass
        sleep(4)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Click Investment Sector
        click_element_by_xpath(driver, '//*[@id="main-content"]/section[3]/div/div[1]/div[2]/ul/li[6]/a')
        print(f"[INFO] : {Typology[reg]} _({reg})_ ")  
        sleep(3)
        file = driver.find_element(By.XPATH, '//*[@id="main-content"]/section[9]/div/div[1]/div[2]/ul/li/a').click()
        
        for times in range(50):
            dl_files = [os.path.join(tempfolder, f) for f in os.listdir(tempfolder)]
            if len(dl_files)>0 and not dl_files[0].endswith('.tmp') and not dl_files[0].endswith('.crdownload'):
                break
            sleep(3)
        else:
            raise Exception(f'{regulatorName} - Failed to download file - '+reg)
        pages_text = list()
        bold_lines = list()
        with pdfplumber.open(dl_files[0]) as pdf:
            for page in pdf.pages:
                bold_text = page.filter(lambda obj: obj["object_type"] == "char" and "Bold" in obj["fontname"]).extract_text()
                if bold_text is not None:
                    bold_lines.extend([ele.strip() for ele in bold_text.split('\n') if len(ele) > 0])            
                pages_text.append(re.sub(bold_text,'',page.extract_text().strip()))


        all_text = '\n'.join(pages_text)
        lines = [ele.strip() for ele in all_text.split('\n') if len(ele.strip()) > 0]
        date = ''
        for i in bold_lines[0].split(' ')[-3:]:
            date+=i+' '
        
        for line in lines[:-1]:
            id = line.split(' ')[0]
            name = re.sub(id,'',line)
            
            #print(name)
            sqldict['Name'].append(name)
            sqldict['ListProcessDate'].append(processdate)
            sqldict['InternalID_1'].append(id)
            sqldict['InternalID_1_type'].append('FRN')
            sqldict['RegCtry'].append(reg.split(' ')[0]) 
            sqldict['RegCode'].append(reg.split(' ')[1])
            sqldict['ListCode'].append(reg.split(' ')[-1])
            sqldict['Typology'].append(Typology[reg])

            sqldict['RegulationType'].append('Regulated')
            sqldict['RegulationDate'].append(date)
    elif reg == 'GB PRA 3':
        driver.get(regdict[reg])
        sleep(4)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        try:
            # try to click cookie
            click_element_by_xpath(driver,'/html/body/div/div[1]/div/div/table/tbody/tr[2]/td[3]/button')
            print(f"[INFO] : Click Cookie _({reg})_ ")  
        except:
            pass
        sleep(4)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Click Bank Sector
        click_element_by_xpath(driver, '//*[@id="main-content"]/section[4]/div/div[1]/div[2]/ul/li/a')
        print(f"[INFO] : {Typology[reg]} _({reg})_ ")  
        sleep(3)
        file = driver.find_element(By.XPATH, '//*[@id="main-content"]/section[9]/div/div[1]/div[2]/ul/li/a').click()
        
        for times in range(50):
            dl_files = [os.path.join(tempfolder, f) for f in os.listdir(tempfolder)]
            if len(dl_files)>0 and not dl_files[0].endswith('.tmp') and not dl_files[0].endswith('.crdownload'):
                break
            sleep(3)
        else:
            raise Exception(f'{regulatorName} - Failed to download file - '+reg)
        pages_text = list()
        bold_lines = list()
        categorys = []
        with pdfplumber.open(dl_files[0]) as pdf:
            for page in pdf.pages:
                bold_text_category = ''
                for obj in page.chars:
        
                    if obj["object_type"] == "char" and "Bold" in obj["fontname"]:
                        #print(obj)
                        #print(obj["fontname"])  # Print the font name
                        if obj["text"] and obj['top']>50:
                            bold_text_category+=obj["text"]
                categorys.append(bold_text_category)
                pages_text.append(page.extract_text().strip())


        all_text = '\n'.join(pages_text)
        publish_date  = ''
        for i in os.listdir(tempfolder)[0].split('-')[-2:]:
            publish_date+=i
        lines = [ele.strip() for ele in all_text.split('\n') if len(ele.strip()) > 0]

        clear_categorys = []
        for i in categorys:
            if i!='':
                clear_categorys.append(i)
        print(clear_categorys)
        print(len(clear_categorys))

        page_category = []
        for index, line in enumerate(lines):
            if any(clear_category.strip() in line for clear_category in clear_categorys):
                page_category.append(index)

                            
        for i in range(len(page_category)):
            print(i)
            print(f' ================= {lines[page_category[i]]} ===================')
            
            if 'gibraltar' in lines[page_category[i]].lower():
                
                reg = 'GB PRA 3'
        
                print(f'Range {page_category[i]+1} to {page_category[i+1]}')
                #print(lines[page_category[i]+1:page_category[i+1]-3])
                contents = lines[page_category[i]+1:page_category[i+1]]
                for content in contents[:-3]:
                    id = content.split(' ')[-1]
                    name = re.sub(id,'',content)
                    sqldict['InternalID_1'].append(id)
                    sqldict['InternalID_1_type'].append('InternalID')
                    sqldict['Name'].append(name)
                    sqldict['ListProcessDate'].append(processdate)

                    sqldict['RegCtry'].append(reg.split(' ')[0]) 

                    sqldict['RegCode'].append(reg.split(' ')[1])

                    sqldict['ListCode'].append(reg.split(' ')[-1])
                    sqldict['Typology'].append(Typology[reg])

                    sqldict['RegulationType'].append('Regulated')
                    #sqldict['RegulationDate'].append(contents[-1].split(' ')[0])
            
            elif 'SRO' in lines[page_category[i]]:
                
                reg = 'GB PRA 4'
        
                print(f'Range {page_category[i]+1} to End')
                #print(lines[page_category[i]+1:page_category[i+1]-3])
                contents = lines[page_category[i]+1:]
                for content in contents[:-3]:
                    id = content.split(' ')[-1]
                    name = re.sub(id,'',content)
                    sqldict['Name'].append(name)
                    sqldict['ListProcessDate'].append(processdate)
                    sqldict['InternalID_1'].append(id)
                    sqldict['InternalID_1_type'].append('InternalID')

                    sqldict['RegCtry'].append(reg.split(' ')[0]) 

                    sqldict['RegCode'].append(reg.split(' ')[1])

                    sqldict['ListCode'].append(reg.split(' ')[-1])
                    sqldict['Typology'].append(Typology[reg])

                    sqldict['RegulationType'].append('Regulated')
                    #sqldict['RegulationDate'].append(contents[-1].split(' ')[0])
            
            elif 'overseas' in lines[page_category[i]].lower():
                reg = 'GB PRA 8'
                print(f'Range {page_category[i]+1} to {page_category[i+1]}')
                contents = lines[page_category[i]+1:page_category[i+1]]
                for content in contents[:-3]:
                    id = content.split(' ')[-1]
                    try:
                        if len(id)>3 and int(id):
                            name = re.sub(id,'',content)
                            print(name)
                            sqldict['Name'].append(name)
                            sqldict['ListProcessDate'].append(processdate)
                            sqldict['InternalID_1'].append(id)
                            sqldict['InternalID_1_type'].append('InternalID')
                            sqldict['RegCtry'].append(reg.split(' ')[0]) 

                            sqldict['RegCode'].append(reg.split(' ')[1])

                            sqldict['ListCode'].append(reg.split(' ')[-1])
                            sqldict['Typology'].append(Typology[reg])

                            sqldict['RegulationType'].append('Regulated')
                            #sqldict['RegulationDate'].append(contents[-1].split(' ')[0])
                    except:
                        continue
                

            elif i == 0:
                reg = 'GB PRA 6'
                print(f'Range {page_category[i]+1} to {page_category[i+1]}')
                contents = lines[page_category[i]+1:page_category[i+1]]
                for content in contents[:-3]:
                    id = content.split(' ')[-1]
                    try:
                        if len(id)>3 and int(id):
                            name = re.sub(id,'',content)
                            print(name)
                            sqldict['Name'].append(name)
                            sqldict['InternalID_1'].append(id)
                            sqldict['InternalID_1_type'].append('InternalID')
                            sqldict['ListProcessDate'].append(processdate)

                            sqldict['RegCtry'].append(reg.split(' ')[0]) 

                            sqldict['RegCode'].append(reg.split(' ')[1])

                            sqldict['ListCode'].append(reg.split(' ')[-1])
                            sqldict['Typology'].append(Typology[reg])

                            sqldict['RegulationType'].append('Regulated')
                            print(content)
                            #sqldict['RegulationDate'].append(contents[-1].split(' ')[0])
                    except:
                        continue
  
        
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
    

