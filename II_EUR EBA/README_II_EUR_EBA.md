# II_EUR EBA Regulatory Lists

European Banking Authority (EBA) — EUCLID public register (https://euclid.eba.europa.eu/register/).
Both lists are retrieved over plain HTTP with `requests` — **no Selenium/browser needed**. The Angular
search UI is backed by JSON endpoints that can be called directly:

- **ListCode 1 (CIR)** — `POST /register/api/search/entities` with body
  `{"$and":[{"_messagetype":"EUCLIDMD"},{"_payload.EntityType":"<TYPE>"}]}`. One POST per EntityType
  returns the *complete* set (the API has no result cap and no pagination; the SPA pages client-side).
- **ListCode 2 (PIR)** — `GET /register/api/filemetadata` returns the golden-copy metadata; build the zip
  URL as `golden_copy_path_context + latest_version_relative_zip_path`, download the zip, and parse the
  inner `download-PSDMD-<ts>.json` (`data[0]` = disclaimer, `data[1]` = entities).

| RegCtry | RegCode | ListNr | ListName | URL | Comments |
|---------|---------|--------|----------|-----|----------|
| II_EUR | EBA | 1 | Credit Institutions Register (CIR) | https://euclid.eba.europa.eu/register/cir/search | JSON search API (`_messagetype=EUCLIDMD`). ~4,491 entities across three Typologies: CRD Credit Institution (~3,662), EEA Branch (~733), Non-EEA Branch (~96). RegulationType = `Authorised`. Non-EEA branches carry the head-office institution name/country (mother-company fields). No bulk-download file exists for CIR. |
| II_EUR | EBA | 2 | Payment Institutions Register (PIR) | https://euclid.eba.europa.eu/register/pir/registerDownload | PSDMD golden-copy zip via `/register/api/filemetadata`. ~6,344 entities after excluding agents (PSD_AG) and branches (PSD_BR). Typologies: Payment / Exempted Payment / (Exempted) Electronic Money Institution, AISP, PSD2-excluded provider, Natural or Legal Person. RegulationType derived from `ENT_AUT` date parity (`Authorised` / `Cancelled`). No LEI is published in PSDMD. |

**Notes**
- `ENT_NAM` is occasionally list-valued (non-Latin name variants) — the scraper keeps the last element.
- `ENT_AUT` is always a list of ISO dates: odd count ⇒ active (`RegulationDate` = last date, `Authorised`);
  even count ⇒ `RegulationDate` = `[-2]`, `CancellationDate` = `[-1]`, `Cancelled`.
- Country (`ENT_COU_RES`) is already an ISO-2 code; `EntityCode` → `InternalID_1` (type `EBA Entity Code`);
  `ENT_NAT_REF_COD` → `InternalID_2` (type `National Reference Code`).
