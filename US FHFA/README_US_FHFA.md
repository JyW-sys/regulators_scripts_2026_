# US FHFA Regulatory Lists

Source: Jira [DECD-4946](https://moodysdatapipeline.atlassian.net/browse/DECD-4946) — Federal Housing Finance Agency (FHFA), Federal Home Loan Bank (FHLB) membership.

| RegCtry | RegCode | ListNr | ListName | URL | Comments |
|---------|---------|--------|----------|-----|----------|
| US | FHFA | 1 | Federal Home Loan Bank Membership | https://www.fhfa.gov/data/fhlb-membership | Open the most recent `.xlsx` file and extract all entities from it. |

## How it works

`US_FHFA_v1.py`:

1. Fetches the membership page and auto-selects the **most recent** workbook by parsing the quarter/year from each `.xlsx` link (e.g. `fhlb_members_q12026.xlsx` → Q1 2026). No Selenium, no captcha — a plain `requests` download.
2. Reads the `MembershipOpenGovt` sheet (the second sheet, `Field Definitions`, is the data dictionary and is ignored).
3. Maps every member to the `sqldict` structure and writes a `SQL Ready` xlsx.

## Field mapping

| Source column | sqldict field | Notes |
|---|---|---|
| MEMBER_NAME | `Name` | |
| FHFA_ID | `InternalID_1` (+ `_type` = `FHFA ID`) | regulator's own member id, always present |
| CERT / FED_ID / NCUA_ID / NAIC_ID | `InternalID_2`, `InternalID_3` (+ `_type`) | member-type specific — banks carry FDIC Certificate + Federal Reserve ID, credit unions carry NCUA Charter Number, insurers carry NAIC Company Code. Whichever exist fill slots 2–3. |
| MEM_TYPE | `CoType` | Commercial Bank / Credit Union / Insurance Company / Savings Bank / Saving Associate / CDFI |
| CHAR_TYPE | `License_Type` | Federal / State / National charter |
| CITY | `City` | |
| STATE | `Address_2` | two-letter state (no street address is published) |
| ZIP | `Zip` | |
| MEM_DATE | `RegulationDate` | membership date, verbatim from source |
| — | `Cntry` | constant `United States` |
| — | `RegulationType` | constant `Regulated` |
| — | `RegCtry` / `RegCode` / `ListCode` / `ListName` / `ListProcessDate` | constants from `regdict` / run date |

The `DISTRICT` column (FHLB district) is not an entity-identifying field and is not exported.

## Result (Q1 2026 run)

- **6,327** entities, 100% non-empty on `Name`, `City`, `Zip`, `Cntry`, `InternalID_1`.
- Secondary IDs: 3,984 FDIC Certificate, 1,638 NCUA Charter, 619 NAIC — no row needs more than two secondary IDs.
- No encoding artifacts.
