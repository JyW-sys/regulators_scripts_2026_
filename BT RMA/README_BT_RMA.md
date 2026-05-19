# BT RMA Regulatory Lists

Source: Jira [DECD-4169](https://moodysdatapipeline.atlassian.net/browse/DECD-4169) — Royal Monetary Authority of Bhutan (RMA).

| RegCtry | RegCode | ListNr | ListName | URL | Comments |
|---------|---------|--------|----------|-----|----------|
| BT | RMA | 1 | List of "Financial Institutions" | https://www.rma.org.bt/ | At the bottom of the main page, lines under "Banks" and "Non-Banks". |
| BT | RMA | 2 | List of "Microfinance Institutions" | https://www.rma.org.bt/ | At the bottom of the main page, lines under "Microfinance Institutions". |
| BT | RMA | 3 | List of "Registered Private Money Lenders" | https://www.rma.org.bt/ | At the bottom of the main page, follow the PDF link "Registered Private Money Lenders" and add all entries. Use the Business name as `Name`. |

## Extracted fields

Per request, only the following source fields are kept per record:

- `Name` — entity name (Business name for list 3).
- `Address_1` — primary address. When the source shows multiple addresses for a single entity, only the first one is kept.

All other `sqldict` columns are present in the SQL Ready export but populated empty or with constants (`RegCtry=BT`, `RegCode=RMA`, `ListCode`, `ListName`, `RegulationType='Regulated'`, `ListProcessDate`).
