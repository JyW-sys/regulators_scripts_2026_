# Regulator Project

Web scraping pipeline for regulatory, banking, and financial-institution websites worldwide. Each country/agency has its own folder (e.g. `US FDIC`, `GB FCAUK`, `HK HKMA`) named `<CC> <AGENCY>` containing the scraper(s) for that regulator.

## DON'T CHANGE

the sqldict must be follow this strcture! YOU CANNOT CHANGE!
sqldict={'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [], 
          'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [], 
          'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [], 
          'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
          'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [], 
          'Phone - Mother company': []}

## DON'T FORGET

- Based on Jira tickets to built or update the each regulator .md file, that named `README_<CC>_<AGENCY>`, like README_CV_BCV.md in CV BCV folder.
- Don't forget add RegulationType information, normally (if the entity is positive,) we set 'Regulated', but there're also other situation, we discuss by case
- Don't forget add ListProcessDate infomation also, normally we use this format code to generate the date, for example:
`now=datetime.datetime.now()` 
`processdate = now.strftime('%Y-%m-%d')`
`saldict['ListProcessDate'].append(processdate)`



## Layout

- `Template/` — starting notebooks for new regulators (`TEMPLATE_Regulator_scraping.ipynb`, `TEMPLATE_web_scaping.ipynb`, `PDF-Scraping-Regulators-Notebook.ipynb`). Do not edit; copy into a new agency folder.
- use global Python environment



## Conventions

- Prefer the patterns in `Template/` notebooks when starting a new regulator.
- Return extracted records as `list[dict]` with `snake_case` keys (see `html-element-extraction` skill for the field vocabulary).
- Never commit scraped output files or credentials.
- Don't remeber fill the ListLable, based on the ListName,  **ListLabel = 1 for bank lists, 2 for insurance, 3 for bank & insurance, 4 for everything else.**
- The output file need to save the Each Regulator Folder rather than tempfolder in Each Regulator Folder, for example as code sample

```python
# ------ At first we will define the workspace path ----- 
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__)) ## production environment (.py)
except NameError:
    scriptfolder = os.getcwd() ## notebook environment

os.chdir(scriptfolder)

# ------ Final step we will save the df to .xlsx file ---- 
os.chdir(scriptfolder)
df=pd.DataFrame(sqldict)

df = df[df['Name']!='']

df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)

print('Saved {} rows to {}'.format(len(df), os.path.join(tempfolder, filename)))

```
