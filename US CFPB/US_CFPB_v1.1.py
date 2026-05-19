# %%

#------------------------------------------------ Begin_Librairie ----------------------------------------

from bs4 import BeautifulSoup

import datetime

import pandas as pd

from pandas import ExcelWriter

from selenium import webdriver

from selenium.webdriver.common.by import By

from time import sleep

import os



# %%

#------------------------------------------------ Begin_ fileName ----------------------------------------

regulatorName = 'US CFPB' ## change to current controller name



print(f"Running {regulatorName} Web Scraping Tool v.1.1")

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

#------------------------------------------------ Begin_Variable ----------------------------------------

regdict = {

    'US CFPB 1': 'https://www.consumerfinance.gov/policy-compliance/guidance/supervision-examinations/institutions/',

    #'US CFPB 2': 'https://www.consumerfinance.gov/policy-compliance/guidance/supervision-examinations/',

    }



sqldict={'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [], 

		  'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [], 

		  'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [], 

		  'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],

		  'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [], 

		  'Phone - Mother company': [], 'Check': []}



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



def click_element(driver, XPATH, Msg=None):

    for time in range(10):

        try:

            driver.find_element(By.XPATH, XPATH).click()

            if Msg!=None:

                print(f"[INFO] : - {Msg}")

            break

        except:

            print(f"[ERROR] : - Retrying {time+1}/10 to click element in this page: {XPATH} ")

            sleep(1)

    else:

        raise Exception('[ERROR] : Failed to get presence for this element in this page:')



def check_dowload_files(tempfolder, fileType, wait_time=10):

    for time in range(wait_time):

        if len([ele for ele in os.listdir(tempfolder) if '.crdownload' not in ele and '.tmp' not in ele]) != 0 :

            print(f"[INFO] : - {fileType} file = {os.listdir(tempfolder)})")

            break

        else:

            print(f"[INFO] : - Download {fileType} file ... (wait {time*2}/20 s)")

            sleep(2)

    else:

        raise Exception(f'[ERROR] : Failed to Download {fileType} file. Run Script again' )

    return  os.listdir(tempfolder)[0]



# %%

#------------------------------------------------ Begin_Main ----------------------------------------

for k, reg in enumerate(regdict):

	print(f"[INFO] : Working {k+1}/{len(regdict)} | {reg} ")

	driver.get(regdict[reg])

	sleep(4)

	soup = BeautifulSoup(driver.page_source, 'html.parser')

	click_element(driver, '//*[@id="content_main"]//*/span[contains(text(),"Current list Excel")]', 'Clik on Excel file ')



	file =  check_dowload_files(tempfolder, "Excel" )

	filePath = os.path.join(tempfolder, file)

	df = pd.read_excel(filePath)

	df.columns = ['ID', 'Institution', 'City', 'State', 'Regulator', 'Total_Assets']

	df = df[2:]

	df = df.reset_index(drop=True)



	print(f"[INFO] : -- DataFrame '{file}' | containe = {df.shape}")

	for index, row in df.iterrows():

		sqldict['Name'].append(row['Institution'])

		# sqldict['Typology'].append(row['Regulator'])

		sqldict['City'].append(row['City'])

		sqldict['RegulationType'].append('Supervised')

		sqldict['InternalID_1_type'].append('ID')

		sqldict['InternalID_1'].append(row['ID'])

		sqldict["Cntry"].append("US")  



		sqldict['ListProcessDate'].append(processdate)

		sqldict['RegCtry'].append(reg.split(' ')[0])

		sqldict['RegCode'].append(reg.split(' ')[1])

		sqldict['ListCode'].append(reg.split(' ')[-1])



	sqldict = bourange_same_length_array(sqldict)

	for del_file in os.listdir(tempfolder):

		os.remove(os.path.join(tempfolder, del_file))



# %%

#------------------------------------------------ Begin_writer and save df to excel  ----------------------------------------

os.chdir(scriptfolder)

df=pd.DataFrame(sqldict)

df.to_excel(writer, 'SQL Ready', index=False)

writer.save()

writer.close()

driver.quit()

sleep(3)
    