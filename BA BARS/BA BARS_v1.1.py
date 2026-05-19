from selenium import webdriver
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
from pandas import ExcelWriter
import datetime
from time import sleep
import os


print("Running BA BARS Web Scraping Tool v.1.0")
now=datetime.datetime.now()
scriptfolder=os.path.dirname(os.path.abspath(__file__))
os.chdir(scriptfolder)

filename= 'BA BARS SQL Ready {}.xlsx'.format(str(now).replace(":",".")[:-7])
writer = ExcelWriter(filename)

regdict={'BA BARS 1': 'https://abrs.ba/en/banks/c16', 'BA BARS 2': 'https://abrs.ba/en/category/c17'}

sqldict={'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [], 
		  'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [], 
		  'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [], 
		  'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
		  'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [], 
		  'Phone - Mother company': [], 'Check': []}
		  
driver = webdriver.Chrome()
driver.maximize_window()

processdate=now.strftime('%Y-%m-%d')

for reg in regdict:
	print('Working with {}.'.format(reg))
	driver.get(regdict[reg])
	sleep(3)
	soup=BeautifulSoup(driver.page_source, 'html.parser')
	block=soup.find("div", {"class":"row service-box margin-bottom-40"})
	boxes=block.find_all("a",  {"class":"thumbnail fancybox-button"}, href=True)
	if len(boxes)>0:
		for box in range(len(boxes)):
			sqldict['ListProcessDate'].append(processdate)
			sqldict['RegCtry'].append('BA')
			sqldict['RegCode'].append('BARS')
			sqldict['ListCode'].append(reg.split(' ')[-1])
			sqldict['RegulationType'].append('Regulated')
			driver.get(boxes[box]['href'])
			sleep(3)
			soup2=BeautifulSoup(driver.page_source, "html.parser")
			title=soup2.find("ul", {"class":"breadcrumb"})
			title=title.find_all("li")[3].text.strip()
			if "-" in title:
				sqldict['Name'].append(title.split("-")[0].strip())
				#xstatus.append(titlex[1].strip())
				print(title.split("-")[1].strip())
			else:
				sqldict['Name'].append(title.strip())
			soup2=soup2.find("div", {"class":"col-md-9 col-sm-12 padding-top-10"})
			soup2=soup2.find_all("div", {"class":"col-md-6 col-sm-6"})[1]
			for p in soup2.find_all("p"):
				p=p.text.replace("\n", "").replace("\t", "").replace("http://", "").replace("https://", "")
				catex=p.split(":", 1)[0].strip()
				data=p.split(":", 1)[1].strip()
				if 'Address' in catex and len(sqldict['ListProcessDate'])>len(sqldict['Address_1']):
					sqldict['Address_1'].append(data)
				elif 'Phone' in catex and len(sqldict['ListProcessDate'])>len(sqldict['Phone']):
					sqldict['Phone'].append(data)
				elif 'Fax' in catex and len(sqldict['ListProcessDate'])>len(sqldict['Fax']):
					sqldict['Fax'].append(data)
				elif 'Email' in catex and len(sqldict['ListProcessDate'])>len(sqldict['Email']):
					sqldict['Email'].append(data)
				elif 'Web' in catex and len(sqldict['ListProcessDate'])>len(sqldict['Website']):
					sqldict['Website'].append(data)
				elif 'Swift' in catex and len(sqldict['ListProcessDate'])>len(sqldict['BIC SWIFT Code']):
					sqldict['BIC SWIFT Code'].append(data)
				else:
					print(f'{reg}: not allocated to SQL Ready file: {p} with category: {catex} and data: {data}')
			for key in sqldict.keys():
				if len(sqldict['ListProcessDate'])>len(sqldict[key]):
					sqldict[key].append('')

df=pd.DataFrame(sqldict)
df.to_excel(writer, 'SQL', index=False)
writer.save()
writer.close()
sleep(3)

driver.quit()

endtime=datetime.datetime.now()
difference=endtime-now
difference=difference.total_seconds()
file = open(filename.replace('data', 'time').replace('xlsx','txt'),'w') 
file.write("Start: {} \nEnd:   {} \nTotal: {} hours, {} minutes and {} seconds.".format(str(now)[:-7], str(endtime)[:-7], int(difference//3600),int(difference%3600)//60,int(difference%3600)%60))
file.close()

    
    