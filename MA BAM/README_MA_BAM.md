# MA BAM — Bank Al-Maghrib (Morocco)

- **Jira:** DECD-5811 (epic DECD-3438, Regulators 2026 – Internal Crawlers)
- **Source site:** https://www.bkam.ma
- **Language:** French (translate entity fields → English)
- **RegCtry / RegCode:** MA / BAM
- **RegulationType:** Regulated

## Lists (from Jira ticket)

| ListNr | ListName | URL | Notes |
|---|---|---|---|
| 1 | List of approved credit institutions | https://www.bkam.ma/Publications-et-recherche/Publications-institutionnelles/Rapport-annuel-sur-la-supervision-bancaire | Download the most recent PDF; extract entities from tables in "Annexe 2. Liste des établissements de crédit et organismes assimilés" |

## Status
- [x] v1 scraper built — `MA_BAM_v1.py` (2026-07-01)
- [x] Validated vs Annexe 2 — 102 credit institutions (report exercice 2024)

## Implementation notes (v1)
- Finds the newest "…supervision-bancaire…exercice-<YYYY>" report sub-page, then its
  `/content/download/…​.pdf` link; downloads and parses Annexe 2 only (auto-locates the
  "Annexe 2. Liste des établissements de crédit" pages, stops before Annexe 3).
- Two-sided report → alternating margins: name/address column split (ruled vertical line) is
  detected **per page** from the ruled-line geometry.
- Hybrid parse: entity rows from the ruled table (keeps multi-line names/addresses intact),
  French category sub-headers read from text and assigned to rows by y-position (carried across
  pages) — same technique as NP NRB.
- Category → ListLabel: Bank/Participatory/Offshore = 1; finance cos / micro-credit / payment = 4.
- Counts by category match Annexe 3's official figures (Offshore 6, Micro-Credit 11, Consumer 12,
  Leasing 8, Real Estate 2, Guarantee 1, Factoring 3). Bank 27 / Participatory 9 are the full
  named listing (regional Banque Populaire units + participatory windows), as Annexe 2 publishes.
- No dates in Annexe 2 → RegulationDate blank; ListValidityDate set to `<year>-12-31`.
- The last two Annexe-2 sub-sections ("Autres établissements de paiement spécialisés … transfert
  de fonds" = 2, and "Autres établissements de crédit" = 2, e.g. CDG / SNGFE) sit at the TOP of the
  Annexe-3 page, above the "Annexe 3" title. The page range includes that page and parsing STOPS at
  the "Annexe 3" title so the count table below it is not ingested. Total 102 (98 + these 4).
