# ADR 0002: Extraction runs in Airflow, not in Databricks

- Status: Accepted
- Date: 2026-10-22

## Context

The Databricks Free Edition documentation says outbound internet access is limited to a
small set of trusted domains, without listing them. We tested it instead of assuming.

Test (2026-10-22): a Python notebook on serverless compute called the Coinbase ticker
endpoint and the BCB PTAX endpoint with `requests` (10 second timeout).
Both calls failed in about one second with `ConnectionError` caused by `NameResolutionError`,
so the hostnames `api.exchange.coinbase.com` and `olinda.bcb.gov.br` could not be resolved.

The same calls work from a local machine (see ADR 0001).

## Decision

1. Extraction (calls to Coinbase and BCB) runs in Airflow, on the local machine.
2. The extractor writes raw JSON files, partitioned by date and hour, and uploads them to a
   Unity Catalog Volume (landing zone) using the Databricks API.
3. Databricks only processes data that is already inside the workspace (bronze and silver).
4. The Databricks token is read from environment variables (`.env`), never committed.

## Consequences

- The pipeline only runs while the local machine is on. Backfill (Airflow catchup) recovers missed periods.
- A personal access token is needed for the upload. It expires in 7 days and must be revoked at the end.
- Extraction code lives in `src/market_data/` as plain Python, so it can move into Databricks
  later if a workspace with open internet access becomes available.
- Only a serverless notebook was tested. Results may differ in other workspace types.
