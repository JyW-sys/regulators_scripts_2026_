#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FI FINFSA -- Finanssivalvonta (Finnish Financial Supervisory Authority),
"Supervised entities" register, read from the public JSON API.

Jira: https://moodysdatapipeline.atlassian.net/browse/DECD-6744

v3 changes vs v2:
  * FIXES THE CRASH.  v2 died with KeyError: 'address'.  The API dropped the
    flat address fields; they now live in nested arrays -- see NOTE below.
  * 'Removed from the register' (group 4951) is now EXCLUDED, per the ticket.
    v2 requested 4951 and then tagged those rows RegulationType='Removed'.
  * Phone / Website are no longer emitted -- the API has no replacement for
    the old 'telephone' / 'wwwAddress' fields (measured, see NOTE).
  * businessIdentityCode is None (JSON null) for 123 entities; v2 tested
    against the *string* 'None' and would have written the literal None.
  * ListName / ListLanguage filled (v2 left both empty on every row).
  * Selenium removed entirely (v2 opened Chrome and never used it).
  * scriptfolder resolved per project convention (no hard-coded C:\\ path).
  * writer.save() removed -- pandas 2.x deleted ExcelWriter.save().
  * Non-schema 'Check' column dropped from sqldict.
  * THE GROUP LIST IS NO LONGER ENUMERATED.  v2 built the request from a
    hard-coded list of 121 group codes; that list had gone stale and was
    silently losing 8 entities -- see "Why no Groups parameter" below.  v3
    asks for the whole register and subtracts group 4951 instead.

NOTE -- measured against the live API on 2026-08-13, not assumed:

  Schema.  A record's keys are now:
      groups, personsInCharge, supervisorsInFSA,
      authorisationsAndOtherOperationGrounds, providedServices, funds,
      principalOfAnAgent, tiedAgents, companyName, auxiliaryName,
      marketingName, businessIdentityCode, homeState,
      postalAddress, visitingAddress, headOfficeAddress, officeAddress
  The four *Address keys are ARRAYS of {address, zipCode, city, country}.
  Coverage over the in-scope records: postalAddress is by far the most
  complete, then visiting, then head office, then office.
  'telephone' and 'wwwAddress' are simply gone -- there is no replacement.

  Why no Groups parameter.  Sending v2's 121 group codes returns 953 rows,
  but the site itself reports 961 with "Removed from the register" unticked.
  The 8 missing entities sit in two groups FIN-FSA created after v2 was
  written, so v2's list never asked for them:

      4989  Foreign credit services' branches in Finland from EEA countries
      4990  Credit servicers

      Axactor Finland Oy, CapFore Oy, Intrum Oy, Kredinor Oy,
      Lowell Suomi Oy, Lowell Suomi Oy (Lowell Danmark A/S),
      Myntro Collect Oy, PRA Suomi Oy

  Measured 2026-08-13:

      no Groups parameter at all ................ 1007
      v2's 121 codes ............................  953
      v2's codes + 4951 .........................  999
      v2's codes + 4989 + 4990 ..................  961   <- matches the site
      1007 minus entities whose ONLY group is
      4951 (46 of them) .........................  961   <- matches the site

  So 999 was never a server cap either; it is simply what v2's stale list plus
  4951 happens to add up to.  Hand-maintaining group codes is the defect, and
  the bare call cannot go stale, so v3 makes the bare call.
"""

# ------------------------------------------------ Begin_Librairie ----------------------------------------

import datetime
import os

import pandas as pd
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ------------------------------------------------ Begin_fileName ----------------------------------------

regulatorName = 'FI FINFSA'

print("Running {} Web Scraping Tool v.3.0".format(regulatorName))

now = datetime.datetime.now()
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":", ".")[:-7])
processdate = now.strftime('%Y-%m-%d')

try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))   # production environment (.py)
except NameError:
    scriptfolder = os.getcwd()                                  # notebook environment

os.chdir(scriptfolder)
tempfolder = os.path.join(scriptfolder, 'tempfolder')

if os.path.exists(tempfolder):
    for rem_file in os.listdir(tempfolder):
        os.remove(os.path.join(tempfolder, rem_file))
else:
    os.mkdir(tempfolder)

# ------------------------------------------------ Begin_Varible ----------------------------------------

sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}

API_URL = 'https://www.finanssivalvonta.fi/api/supervised-entity-api/v1/all-supervised-entities'

LIST_NAME = 'Supervised entities'
LIST_CODE = '1'

# The API is called with NO Groups parameter at all, which returns every
# supervised entity (1007 on 2026-08-13).  The in-scope population is then
# obtained by dropping the entities whose ONLY group is 4951 -- which is
# exactly what the site's own "Removed from the register" checkbox does.
#
# KNOWN_GROUPS is NOT used to build the request.  It is v2's group list, kept
# only so that a group the register adds later is PRINTED as a notice.  This
# is not hypothetical: requesting v2's list explicitly returned 953 rows while
# the site showed 961, because groups 4989 "Foreign credit services' branches
# in Finland from EEA countries" and 4990 "Credit servicers" were created
# after v2 was written and were therefore never asked for.  Enumerating group
# codes by hand is exactly the bug; the bare call cannot go stale.
KNOWN_GROUPS = [1000, 1100, 1110, 1120, 1130, 1140, 1150, 1160, 1200, 1210, 1220, 1230,
          1240, 1250, 4900, 1300, 1400, 1410, 1420, 1430, 4941, 4943, 1600, 1610,
          1620, 1630, 1640, 1650, 1660, 4910, 4948, 4984, 4985, 2000, 2100, 2200,
          2400, 2600, 2610, 2630, 4976, 4978, 4979, 4980, 4981, 4965, 4966, 4967,
          4971, 2500, 4942, 4982, 2700, 2710, 2730, 4936, 4937, 4938, 4939, 4940,
          4968, 4986, 4987, 4988, 3000, 3100, 3200, 3210, 3220, 3300, 3310, 3320,
          3330, 3340, 3350, 3360, 3370, 3400, 3410, 3420, 3430, 3440, 3500, 3510,
          3520, 3600, 3610, 3620, 4935, 4983, 3700, 3800, 4800, 4805, 4925, 4930,
          4970, 4810, 4915, 4920, 4815, 4820, 4870, 4952, 4953, 4954, 4955, 4960,
          4961, 4962, 4963, 4964, 4949, 4950, 4969, 4973, 4974, 4975, 4000, 4100,
          4200]

EXCLUDED_GROUP = 4951          # "Removed from the register" -- must never appear

# Site row counts seen on 2026-08-13, printed against the live numbers so a
# collapse is obvious.  961 is what the register itself reports with the
# "Removed from the register" box unticked.
BASELINE_ALL = 1007
BASELINE_IN_SCOPE = 961

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
}

# ------------------------------------------------ Begin_Fonction ----------------------------------------


def bourange_same_length_array(sqldict):

    maxlen = len(sqldict['ListProcessDate'])

    for key, val in sqldict.items():

        if len(sqldict[key]) != maxlen:

            empty = []

            total_empty = maxlen - len(sqldict[key])

            for i in range(total_empty):

                empty.append('')

            sqldict[key] = sqldict[key] + empty

    return sqldict


def clean(value):
    """JSON null / the literal string 'None' / whitespace all become ''."""
    if value is None:
        return ''
    value = str(value).strip()
    if value in ('None', 'null'):
        return ''
    return value


def fetch_all():
    """Every supervised entity, in one call, with no Groups filter.

    Asking for no groups returns the whole register, so no group code has to
    be enumerated and a category added by FIN-FSA later is picked up
    automatically.  Any group that KNOWN_GROUPS has not seen before is
    reported, purely as a heads-up that the register has grown.
    """
    response = requests.get(API_URL, params=[('Lang', '2')], headers=HEADERS,
                            verify=False, timeout=180)
    if response.status_code != 200:
        raise RuntimeError('Failed to retrieve data: HTTP {}'.format(response.status_code))

    records = response.json()

    known = set(KNOWN_GROUPS) | {EXCLUDED_GROUP}
    fresh = {}
    for entity in records:
        for group in entity.get('groups') or []:
            number = group.get('groupNumber')
            if number is not None and number not in known:
                fresh[number] = clean(group.get('groupName'))

    if fresh:
        print('\n[NOTE] the register now has {} group(s) that KNOWN_GROUPS does not '
              'list.  They ARE included -- this is only a heads-up:'.format(len(fresh)))
        for number in sorted(fresh):
            print('   {} {}'.format(number, fresh[number]))

    return records


def first_address(entity):
    """Return the best available address block.

    The old flat address/zipCode/city fields are gone.  Four nested arrays
    replace them; postal is the most complete (939/953), so it is preferred,
    then visiting, then head office, then office.
    """
    for key in ('postalAddress', 'visitingAddress', 'headOfficeAddress', 'officeAddress'):
        block = entity.get(key) or []
        if block:
            return block[0], key
    return {}, ''


def join_names(items, field):
    """authorisationsAndOtherOperationGrounds / groups -> a single string."""
    out = []
    for item in items or []:
        value = clean(item.get(field))
        if value and value not in out:
            out.append(value)
    return ' | '.join(out)


# ------------------------------------------------ Begin_Main ----------------------------------------

print('\nFetching the whole register in one call (no Groups filter) ...')

data = fetch_all()

print('\n{} entities returned (site baseline {})'.format(len(data), BASELINE_ALL))

skipped_excluded = 0
no_address = 0

for entity in data:

    groups = entity.get('groups') or []

    # This is THE in-scope filter, not a safety net: the request above asks for
    # everything, so 4951 "Removed from the register" arrives with the rest and
    # is dropped here.  Only entities whose ONLY group is 4951 are dropped --
    # an entity that is also in a live group is still supervised.  (Measured
    # 2026-08-13: 0 entities carry 4951 alongside another group, but the site's
    # own checkbox behaves this way, so the rule is written this way too.)
    group_numbers = [g.get('groupNumber') for g in groups]
    if group_numbers and set(group_numbers) == {EXCLUDED_GROUP}:
        skipped_excluded += 1
        continue

    name = clean(entity.get('companyName'))
    if not name:
        continue

    address_block, address_source = first_address(entity)
    if not address_source:
        no_address += 1

    sqldict['ListProcessDate'].append(processdate)
    sqldict['Name'].append(name)
    sqldict['Typology'].append(clean(groups[0].get('groupName')) if groups else '')
    sqldict['License_Type'].append(
        join_names(entity.get('authorisationsAndOtherOperationGrounds'), 'authorisationName'))
    sqldict['InternalID_1'].append(clean(entity.get('businessIdentityCode')))
    sqldict['InternalID_1_type'].append('Business Identity Code')
    sqldict['Address_1'].append(clean(address_block.get('address')))
    sqldict['Zip'].append(clean(address_block.get('zipCode')))
    sqldict['City'].append(clean(address_block.get('city')))
    sqldict['Cntry'].append(clean(entity.get('homeState')))
    sqldict['RegulationType'].append('Regulated')
    sqldict['RegCtry'].append('FI')
    sqldict['RegCode'].append('FINFSA')
    sqldict['ListCode'].append(LIST_CODE)
    sqldict['ListName'].append(LIST_NAME)
    sqldict['ListLanguage'].append('EN')          # the API is queried with Lang=2 (English)

    sqldict = bourange_same_length_array(sqldict)

print('{} rows built ({} entities dropped as "Removed from the register", '
      '{} with no address block at all)'.format(
          len(sqldict['ListProcessDate']), skipped_excluded, no_address))

print('\nAgainst the 2026-08-13 site baseline:')
print('  whole register   baseline {:>5}  now {:>5}'.format(BASELINE_ALL, len(data)))
print('  in scope         baseline {:>5}  now {:>5}'.format(
    BASELINE_IN_SCOPE, len(sqldict['ListProcessDate'])))
if len(sqldict['ListProcessDate']) != BASELINE_IN_SCOPE:
    print('  [NOTE] the in-scope count has moved.  That is normal when FIN-FSA '
          'adds or removes entities -- compare against the site before assuming '
          'a scraping fault.')

# ------------------------------------------------ Begin_writer and save df to excel  ----------------------------------------

os.chdir(scriptfolder)

df = pd.DataFrame(sqldict)

df = df[df['Name'] != '']

df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)

print('\nSaved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))

print('\nRows per list:')
print(df.groupby(['ListCode', 'ListName']).size().rename('rows').reset_index().to_string(index=False))

print('\nField completeness:')
for column in ('Name', 'InternalID_1', 'Address_1', 'City', 'Zip', 'Cntry', 'Typology', 'License_Type'):
    print('  {:<14} {:>4}/{}'.format(column, int((df[column] != '').sum()), len(df)))
