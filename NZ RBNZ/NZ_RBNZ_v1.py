#Prister Miriam , Nathanael Khurshudyan

from bs4 import BeautifulSoup
import datetime
import pandas as pd 
from pandas import ExcelWriter
from selenium import webdriver
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from time import sleep
import os

print("Running NZ RBNZ Web Scraping Tool v.1.0")

now=datetime.datetime.now()
filename= 'NZ RBNZ SQL Ready {}.xlsx'.format(str(now).replace(":",".")[:-7])
writer = ExcelWriter(filename)

scriptfolder=os.path.dirname(os.path.abspath(__file__))
os.chdir(scriptfolder)
tempfolder=os.path.join(scriptfolder, 'tempfolder') #if files are downloaded during the process

regdict={'NZ RBNZ 3': 'https://www.rbnz.govt.nz/regulation-and-supervision/banks/register',
         'NZ RBNZ 4': 'https://www.rbnz.govt.nz/regulation-and-supervision/insurers/licensing/register',
         'NZ RBNZ 5': 'https://www.rbnz.govt.nz/regulation-and-supervision/insurers/licensing/cancelled-licences'}

os.chdir(scriptfolder)
#print('The current folder is: {}\nThe temp folder is: {}'.format(scriptfolder, tempfolder))
chromeOptions = webdriver.ChromeOptions()
prefs = {"download.default_directory" : tempfolder, 
		"plugins.always_open_pdf_externally": True}
chromeOptions.add_experimental_option("prefs", prefs)
driver = webdriver.Chrome(options=chromeOptions)
driver.maximize_window()

sqldict={'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [], 
		  'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [], 
		  'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [], 
		  'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
		  'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [], 
		  'Phone - Mother company': [], 'Check': []}
try:
	os.mkdir(tempfolder)
except:
	prevfiles=os.listdir(tempfolder)
	os.chdir(tempfolder)
	for prf in prevfiles:
		os.remove(prf)
	print('The directory tempfolder already exists.')
os.chdir(tempfolder)##only if files are going to be downloaded here
process_date=now.strftime('%Y-%m-%d')

for reg in regdict:
    print('Working with {}'.format(reg))
    driver.get(regdict[reg])
    sleep(3)
    soup=BeautifulSoup(driver.page_source,"html.parser")
    div=soup.find("div",{"class":"table-responsive"})
    tbody=div.find("tbody")
    trs=tbody.find_all("tr")
    for tr in trs:
        tds=tr.find_all("td")
        sqldict["ListProcessDate"].append(process_date)
        sqldict["RegCtry"].append("NZ")
        sqldict["RegCode"].append("RBNZ")
        sqldict["ListCode"].append(reg.split(" ")[-1])
        sqldict["Name"].append(tds[0].text.strip())
        if "Cancellation" in div.text:
            sqldict["CancellationDate"].append(tds[1].text.strip())
            sqldict["RegulationType"].append('Cancelled')
        else:
            sqldict["RegulationDate"].append(tds[1].text.strip())
            sqldict["RegulationType"].append('Supervised')
        sqldict["Cntry"].append("NZ")
        if tds[0].find("a") is not None:             
            sqldict["Website"].append(tds[0].find("a",href=True)["href"])
        for key in sqldict.keys():
                if len(sqldict[key])<len(sqldict["Name"]):
                   sqldict[key].append("")
            

os.chdir(scriptfolder)
df=pd.DataFrame(sqldict)
df.to_excel(writer, 'SQL Ready', index=False)

writer.save()
writer.close()

sleep(3)

driver.quit()
    
    