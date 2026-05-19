from selenium import webdriver 
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
from pandas import ExcelWriter
import datetime
from time import sleep
import os

print("Running BA FBIH Web Scraping Tool v.1.0")
now=datetime.datetime.now()

scriptfolder=os.path.dirname(os.path.abspath(__file__))
os.chdir(scriptfolder)

filename= 'BA FBIH data {}.xlsx'.format(str(now).replace(":",".")[:-7])
writer = ExcelWriter(filename)

reglist=['BA FBIH 1', 'BA FBIH 2', 'BA FBIH 3']
regdict={'BA FBIH 1': '//*[@id="category-list"]/div/div[1]/div/a', 'BA FBIH 2': '//*[@id="category-list"]/div/div[2]/div/a', 
		 'BA FBIH 3': '//*[@id="category-list"]/div/div[3]/div/a'}

driver = webdriver.Chrome()
driver.maximize_window()

catlist=["Director", "Address", "Phone", "Fax", "E-mail", "Web"]
for reg in reglist:
	print('Working with {}.'.format(reg))

	xname=[]
	xupdate=[]
	xtype=[]
	typelinks=[]
	xhead=[]
	xaddr=[]
	xphone=[]
	xfax=[]
	xemail=[]
	xweb=[]

	clinks=[]

	driver.get("https://www.fba.ba/")
	sleep(1)
	driver.get('https://www.fba.ba/change-language/eng/home')
	sleep(1)
	driver.get('https://www.fba.ba/eng/institutions')
	sleep(1)
	driver.find_element(By.XPATH, regdict[reg]).click()
	sleep(1)
	soup=BeautifulSoup(driver.page_source, "html.parser")
	soup=soup.find("div", {"id":"category-list"})
	types=soup.find_all("a", href=True)
	if reg=="BA FBIH 1":
		pagination=soup.find("ul",  {"class":"pagination"})
		pagination=pagination.find_all("a")
		if len(pagination)>0:##xpath for page 2 '//*[@id="category-list"]/div[2]/div/ul/li[2]/a'
			totalpages=int(pagination[-1].text.strip())
		else:
			totalpages=1
		sleep(1.5)
		entities=[]
		res=driver.page_source
		soup=BeautifulSoup(res, "html.parser")
		soup=soup.find("div", {"id":"category-list"})
		entities=soup.find_all("a", href=True)
		for entity in entities:
			if "javascript" in entity['href']:
				break
			xname.append(entity.text.strip())
			xtype.append("")
			clinks.append('https://www.fba.ba'+entity['href'])
		if totalpages==2:#if page>0:
			entities=[]
			xpath='//*[@id="category-list"]/div[2]/div/ul/li[{}]/a'.format(totalpages)
			driver.find_element(By.XPATH, xpath).click()
			###only for the case of Banks category which is following an unstructured design:
			sleep(1.5)
			soup=BeautifulSoup(driver.page_source, "html.parser")
			soup=soup.find("div", {"id":"category-list"})
			types=soup.find("a", href=True)
			temptype=types.text.strip()
			driver.get('https://www.fba.ba'+types['href'])
			sleep(1.5)
			soup=BeautifulSoup(driver.page_source, "html.parser")
			soup=soup.find("div", {"id":"category-list"})
			entities=soup.find_all("a", href=True)
			for entity in entities:
				if "javascript" in entity['href']:
					break
				xname.append(entity.text.strip())
				xtype.append(temptype)
				clinks.append('https://www.fba.ba'+entity['href'])
				####end
		for link in range(len(clinks)):
			print('Working with firm {} out of {}. (Reg: {})'.format(link+1, len(clinks), reg))
			cat=[]
			val=[]
			tempdict={}
			driver.get(clinks[link])
			sleep(1)
			driver.find_element(By.XPATH, '/html/body/header/div/div/div[3]/ul/li[4]/a').click()
			sleep(1)
			res3=driver.page_source
			soup3=BeautifulSoup(res3, "html.parser")## " | " for last update INFORMISANJE
			article=soup3.find("article")
			articles=str(article).replace("<br/>", "***").replace("<br>", "***").replace("\n", "").replace("https://", "").replace("http://", "").replace("Board:", "Director:").replace("Direktor", "Director").replace("Adresa", "Address").replace("Telefon", "Phone").replace('Adress', "Address")
			articles=BeautifulSoup(articles, "html.parser")
			articles=articles.text.split("***")
			if "informisanje" in articles[0] and "|" in articles[0]:
				tempd=""
				articles[0]=articles[0][articles[0].find("informisanje"):]
				tempv=articles[0].find("|")
				tempd=articles[0][tempv+1:tempv+12]
				xupdate.append(tempd)
			else:
				xupdate.append("")
			for art in articles:
				if ":" in art:
					temp=art.split(":")
					for catl in catlist:
						if catl in temp[0]:
							cat.append(catl)
							val.append(temp[1].strip())
							break
			for v in range(len(val)):
				for ca in catlist:
					val[v]=val[v].replace(ca,"")
			for ca in range(len(cat)):
				tempdict[cat[ca]]=val[ca]
			for c in catlist:
				if c not in tempdict:
					tempdict[c]=""
			xhead.append(tempdict[catlist[0]])
			xaddr.append(tempdict[catlist[1]])
			xphone.append(tempdict[catlist[2]])
			xfax.append(tempdict[catlist[3]])
			xemail.append(tempdict[catlist[4]])
			xweb.append(tempdict[catlist[5]])
	else:	
		for typex in types:		
			print('Working with {}. (Reg: {})'.format(typex.text.strip(), reg))
			#clinks=[]
			if "javascript" in typex['href']:
				break
			typelinks.append('https://www.fba.ba'+typex['href'])
			for tlink in range(len(typelinks)):
				entities=[]
				clinks=[]
				driver.get(typelinks[tlink])
				sleep(1)
				res2=driver.page_source
				soup2=BeautifulSoup(res2, "html.parser")
				soup2=soup2.find("div", {"id":"category-list"})
				entities=soup2.find_all("a", href=True)
			for entity in entities:
				#######
				pagination=soup.find("ul",  {"class":"pagination"})
				pagination=pagination.find_all("a")
				if len(pagination)>0:##xpath for page 2 '//*[@id="category-list"]/div[2]/div/ul/li[2]/a'
					totalpages=int(pagination[-1].text.strip())
				else:
					totalpages=1
				######
				if "javascript" in entity['href']:
					break
				if len(entity.text.strip())>3: #due to errors on the site with empty name placeholders
					xname.append(entity.text.strip())
					xtype.append(types[tlink].text.strip())
					clinks.append('https://www.fba.ba'+entity['href'])
			for link in range(len(clinks)):####<br> slice for better results
				print('Working with firm {} out of {}. (Reg: {} - {})'.format(link+1, len(clinks), reg, typex.text.strip()))
				cat=[]
				val=[]
				tempdict={}
				driver.get(clinks[link])
				sleep(1)
				driver.find_element(By.XPATH, '/html/body/header/div/div/div[3]/ul/li[4]/a').click()
				sleep(1)
				res3=driver.page_source
				soup3=BeautifulSoup(res3, "html.parser")
				article=soup3.find("article")
				articles=str(article).replace("<br/>", "***").replace("<br>", "***").replace("\n", "").replace("https://", "").replace("http://", "").replace("Board:", "Director:").replace("Direktor", "Director").replace("Adresa", "Address").replace("Telefon", "Phone").replace('Adress', "Address")
				articles=BeautifulSoup(articles, "html.parser")
				articles=articles.text.split("***")
				if "informisanje" in articles[0] and "|" in articles[0]:
					tempd=""
					articles[0]=articles[0][articles[0].find("informisanje"):]
					tempv=articles[0].find("|")
					tempd=articles[0][tempv+1:tempv+12]
					xupdate.append(tempd)
				else:
					xupdate.append("")
				for art in articles:
					if ":" in art:
						temp=art.split(":")
						for catl in catlist:
							if catl in temp[0]:
								cat.append(catl)
								val.append(temp[1].strip())
								break
				for v in range(len(val)):
					for ca in catlist:
						val[v]=val[v].replace(ca,"")
				for ca in range(len(cat)):
					tempdict[cat[ca]]=val[ca]
				for c in catlist:
					if c not in tempdict:
						tempdict[c]=""
				xhead.append(tempdict[catlist[0]])
				xaddr.append(tempdict[catlist[1]])
				xphone.append(tempdict[catlist[2]])
				xfax.append(tempdict[catlist[3]])
				xemail.append(tempdict[catlist[4]])
				xweb.append(tempdict[catlist[5]])
	#print(xname)
	#print(xtype)
	#print(xhead)
	#print(xaddr)
	#print(xphone)
	#print(xfax)
	#print(xemail)
	#print(xweb)
	#print(len(xname))
	#print(len(xtype))
	#print(len(xhead))
	#print(len(xaddr))
	#print(len(xphone))
	#print(len(xfax))
	#print(len(xemail))
	#print(len(xweb))
	
	df=pd.DataFrame({'Name': xname, 'Type': xtype, "Last update": xupdate, 'Head': xhead, 'Address': xaddr,'Phone': xphone,'Fax': xfax,'Email': xemail,'Web': xweb})
	df.to_excel(writer, reg)

writer.save()
writer.close()
sleep(3)

driver.quit()

    
    