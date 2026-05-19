from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import pandas as pd
from time import sleep
import datetime
from bs4 import BeautifulSoup
from pandas import ExcelWriter
import os
import logging
import sys
from contextlib import redirect_stderr
import io

logging.basicConfig(filename= r'C:\Users\LaraZenl\Desktop\regulators_project\error.log', level=logging.ERROR, format='%(message)s %(asctime)s', datefmt='%m/%d/%Y %I:%M:%S %p')
f = io.StringIO()
log = logging.getLogger('Control_Room')
log.addHandler(logging.StreamHandler(stream=f))

def exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
       # Let the system handle things like CTRL+C
       sys.__excepthook__(*args)
    log.error(msg='<br>', exc_info=(exc_type, exc_value, exc_traceback)) #using the message (kwarg) to create new lines in logs.html
sys.excepthook = exception_handler
#####
print("Running CA AMF Web Scraping Tool v.1.0")
scriptfolder=os.path.dirname(os.path.abspath(__file__))
os.chdir(scriptfolder)

now=datetime.datetime.now()
filename= 'CA AMF data {}.xlsx'.format(str(now).replace(":",".")[:-7])
writer = ExcelWriter(filename)	

reglist=['CA AMF 1', 'CA AMF 2', 'CA AMF 3', 'CA AMF 4']
regdict={'CA AMF 1': ['//*[@id="ui-id-4"]/div[4]/div[2]/label', '//*[@id="TypeInstitution"]/option[1]'], 'CA AMF 2': ['//*[@id="ui-id-4"]/div[2]/div[2]/label', ''], 
		 'CA AMF 3': ['//*[@id="ui-id-4"]/div[4]/div[2]/label', '//*[@id="TypeInstitution"]/option[4]'],'CA AMF 4': ['//*[@id="ui-id-4"]/div[3]/div[2]/label', '']}

catlist1 = ['English name', 'French name', 'Québec enterprise number (NEQ)','Client Number', 'Type of institution', 'Origin of charter',
			'Date of constitution/incorporation','Issuance of initial licence', 'Sector of activity', 'Membership']

catlist2 = ['HO Address Line 1', 'HO Address Line 2', 'HO Address Line 3', 'HO Country', 'HO Phone', 'HO Fax', 'HO Web','CPB Address Line 1', 
			'CPB Address Line 2','CPB Address Line 3','CPB Country', 'CPB Phone', 'CPB Fax', 'CPB Web']



driver=webdriver.Chrome()			
driver.set_window_size(1920, 1080)
action = ActionChains(driver)
for reg in reglist:
	print('Working with {}.'.format(reg))

	clinks=[]
	xname=[]

	xenname=[]
	xfrechname=[]
	xneq=[]
	xclnum=[]
	xtype=[]
	xorigin=[]
	xdateconst=[]
	xissuance=[]
	xsector=[]
	xmemb=[]
	hoal1=[]
	hoal2=[]
	hoal3=[]
	hocountry=[]
	hophone=[]
	hofax=[]
	howeb=[]
	cpbal1=[]
	cpbal2=[]
	cpbal3=[]
	cpbcountry=[]
	cpbphone=[]
	cpbfax=[]
	cpbweb=[]
	xdepoinst=[]
	

	driver.get('https://lautorite.qc.ca/en/general-public/registers/register-insurers-deposit-institutions-and-trust-companies/')
	sleep(1)
	body = driver.find_element(By.XPATH, '/html/body')
	body.click()
	ActionChains(driver).send_keys(Keys.PAGE_DOWN).perform()
#	sharestring = driver.find_element(By.XPATH, "/html/body/div[1]/div/div/div/div/div[2]/div[3]/h2")
#										   	   '/html/body/div[1]/div/div/div/div/div[2]/div[3]/h2'
#	action.move_to_element(sharestring).perform()	
	iframe= driver.find_element(By.XPATH, "//iframe[@width='965']")
	driver.switch_to.frame(iframe)
	driver.find_element(By.PARTIAL_LINK_TEXT, 'Search by type of institution').click()
	sleep(1)
	driver.find_element(By.XPATH, regdict[reg][0]).click()
	sleep(1)
	if len(regdict[reg][1])>0:
		driver.find_element(By.XPATH, regdict[reg][1]).click()
		sleep(1)
	driver.find_element(By.XPATH, "//*[@id='btnRecherche']").click()
	sleep(3)
	
	html=driver.page_source
	soup=BeautifulSoup(html, 'html.parser')
	souptable=soup.find("table", {"id":"searchResultsTable"})
	urldata=souptable.find_all("a", href=True)
	for url in urldata:
		clinks.append('https://registres-public.lautorite.qc.ca'+url['href'])
		xname.append(url.text.strip())
	sleep(1)
	for link in range(len(clinks)):
		print('Working on entity {} out of {}. (Reg code: {})'.format(link+1,len(clinks), reg))
		driver.get(clinks[link])
		sleep(2)
		tempdict={}
		cat=[]
		val=[]
		htmlfirm=driver.page_source
		soupfirm=BeautifulSoup(htmlfirm, 'html.parser')
		soupfirm=soupfirm.find('div', {"class":"search-results"})
		table0=str(soupfirm)[:str(soupfirm).find('<table class')]
		table0=BeautifulSoup(table0, 'html.parser')
		t0values=table0.find_all("p")
		for valx in t0values:
			if len(valx.text.strip())>0:
				value=valx.text.strip()
				if 'Member caisse' in value or 'Non-member' in value:
					cat.append('Membership')
					val.append(value)
				else:
					tempcatval=value.split(":")
					cat.append(tempcatval[0].strip())
					val.append(tempcatval[1].replace('(Québec Enterprise Register)','').strip())
		for c in range(len(cat)):
			tempdict[cat[c]]=val[c]
		for ca in catlist1:
			if ca not in tempdict:
				tempdict[ca]=''

		xenname.append(tempdict[catlist1[0]])
		xfrechname.append(tempdict[catlist1[1]])
		xneq.append(tempdict[catlist1[2]])
		xclnum.append(tempdict[catlist1[3]])
		xtype.append(tempdict[catlist1[4]])
		xorigin.append(tempdict[catlist1[5]])
		xdateconst.append(tempdict[catlist1[6]].replace('Amalgamated',''))
		xissuance.append(tempdict[catlist1[7]])
		xsector.append(tempdict[catlist1[8]])
		xmemb.append(tempdict[catlist1[9]])
		
		tables=soupfirm.find_all("table", {"class":"table table-striped table-bordered"}) #at <th> is the title of the table
		for table in tables:
			if table.find("th").text.strip()=='Head office':
				holist=[]
				for elem in table.find_all("span"):
					holist.append(elem.text.strip())
				try:
					telindex=holist.index('Telephone')
					hophone.append(holist[telindex+1])
					if telindex==4:
						hoal1.append(holist[0])
						hoal2.append(holist[1])
						hoal3.append(holist[2])
						hocountry.append(holist[3])
					else:
						hoal1.append(holist[0])
						hoal2.append('')
						hoal3.append(holist[1])
						hocountry.append(holist[2])
				except:
						if len(holist)>=4:
							hoal1.append(holist[0])
							hoal2.append(holist[1])
							hoal3.append(holist[2])
							hocountry.append(holist[3])
						else:
							hoal1.append(holist[0])
							hoal2.append('')
							hoal3.append(holist[1])
							hocountry.append(holist[2])
				try:
					faxindex=holist.index('Fax')
					hofax.append(holist[faxindex+1])
				except:
					hofax.append('')
				try:
					webindex=holist.index('Website')
					howeb.append(holist[webindex+1])
				except:
					howeb.append('')

			else:
				if 'Chief place of bus' in table.find("th").text.strip():
					cpblist=[]
					for elem in table.find_all("span"):
						cpblist.append(elem.text.strip())
					try:
						telindex2=cpblist.index('Telephone')
						cpbphone.append(cpblist[telindex2+1])
						if telindex2==4:
							cpbal1.append(cpblist[0])
							cpbal2.append(cpblist[1])
							cpbal3.append(cpblist[2])
							cpbcountry.append(cpblist[3])
						else:
							cpbal1.append(cpblist[0])
							cpbal2.append('')
							cpbal3.append(cpblist[1])
							cpbcountry.append(cpblist[2])
					except:
						if cpblist>=4:
							cpbal1.append(cpblist[0])
							cpbal2.append(cpblist[1])
							cpbal3.append(cpblist[2])
							cpbcountry.append(cpblist[3])
						else:
							cpbal1.append(cpblist[0])
							cpbal2.append('')
							cpbal3.append(cpblist[1])
							cpbcountry.append(cpblist[2])
					try:
						faxindex2=cpblist.index('Fax')
						cpbfax.append(cpblist[faxindex2+1])
					except:
						cpbfax.append('')
					try:
						webinde2x=cpblist.index('Website')
						cpbweb.append(cpblist[webindex2+1])
					except:
						cpbweb.append('')

				else:
					if 'Deposit institution' in table.find("th").text.strip():
						xdepoinst.append(table.find("td").text.strip())
					else:
						pass
			if len(hoal1)<len(xneq):
				hoal1.append('')
			if len(hoal2)<len(xneq):
				hoal2.append('')
			if len(hoal3)<len(xneq):
				hoal3.append('')
			if len(hocountry)<len(xneq):
				hocountry.append('')
			if len(hophone)<len(xneq):
				hophone.append('')
			if len(hofax)<len(xneq):
				hofax.append('')
			if len(howeb)<len(xneq):
				howeb.append('')
			if len(cpbal1)<len(xneq):
				cpbal1.append('')
			if len(cpbal2)<len(xneq):
				cpbal2.append('')
			if len(cpbal3)<len(xneq):
				cpbal3.append('')
			if len(cpbcountry)<len(xneq):
				cpbcountry.append('')
			if len(cpbphone)<len(xneq):
				cpbphone.append('')
			if len(cpbfax)<len(xneq):
				cpbfax.append('')
			if len(cpbweb)<len(xneq):
				cpbweb.append('')
			if len(xdepoinst)<len(xneq):
				xdepoinst.append('')


	if len(hoal1)>len(xneq):
		hoal1.pop(0)
	if len(hoal2)>len(xneq):
		hoal2.pop(0)
	if len(hoal3)>len(xneq):
		hoal3.pop(0)
	if len(hocountry)>len(xneq):
		hocountry.pop(0)
	if len(hophone)>len(xneq):
		hophone.pop(0)
	if len(hofax)>len(xneq):
		hofax.pop(0)
	if len(howeb)>len(xneq):
		howeb.pop(0)
	if len(cpbal1)>len(xneq):
		cpbal1.pop(0)
	if len(cpbal2)>len(xneq):
		cpbal2.pop(0)
	if len(cpbal3)>len(xneq):
		cpbal3.pop(0)
	if len(cpbcountry)>len(xneq):
		cpbcountry.pop(0)
	if len(cpbphone)>len(xneq):
		cpbphone.pop(0)
	if len(cpbfax)>len(xneq):
		cpbfax.pop(0)
	if len(cpbweb)>len(xneq):
		cpbweb.pop(0)
	if len(xdepoinst)>len(xneq):
		xdepoinst.pop(0)
	df=pd.DataFrame({'Name': xname,'English name': xenname, 'French name': xfrechname, 'Québec enterprise number (NEQ)': xneq,
					'Client Number': xclnum, 'Type of institution': xtype, 'Origin of charter': xorigin, 'Date of constitution/incorporation': xdateconst,
					'Issuance of initial licence': xissuance, 'Sector of activity': xsector, 'Membership': xmemb, 'HO Address Line 1': hoal1,
					'HO Address Line 2': hoal2,'HO Address Line 3': hoal3, 'HO Country': hocountry, 'HO Phone': hophone, 'HO Fax': hofax,
					'HO Web': howeb, 'CPB Address Line 1': cpbal1, 'CPB Address Line 2': cpbal2, 'CPB Address Line 3': cpbal3,
					'CPB Country': cpbcountry, 'CPB Phone': cpbphone, 'CPB Fax': cpbfax, 'CPB Web': cpbweb, 'Deposit institution': xdepoinst})
	df.to_excel(writer, reg)
sleep(1)

writer.save()

sleep(3)

driver.quit()

endtime=datetime.datetime.now()
difference=endtime-now
difference=difference.total_seconds()
file = open(filename.replace('data', 'time').replace('xlsx','txt'),'w') 
file.write("Start: {} | End: {} | Total: {} hours and {} minutes".format(now, endtime, difference//3600, (difference%3600)/60))
file.close() 
    