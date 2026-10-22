# ADR 0001: Data sources and ingestion rules

- Status: Accepted
- Date: 2026-10-22

## Context

The project needs real data that changes every day, free to use and without personal data.
Candidates were tested on 2026-10-22 from a local machine (status 200 on all of them).
Findings from the tests and from the official documentation:

- Coinbase Exchange `candles`: hourly candles for BTC-USD, 7 days returned with no gaps.
  Rows come in descending order. At most 300 candles per request. The documentation warns that
  historical data may be incomplete. Public limit: 10 requests per second per IP.
- Binance `klines` (`data-api.binance.vision`): same 7 days with no gaps, ascending order,
  prices as strings, accepted `limit=1000`. The pair is BTCUSDT, and USDT is not USD.
- BCB PTAX (`CotacaoDolarPeriodo`): one row per business day (closing bulletin), Brasilia time,
  no rows on weekends or holidays. Dataset license: ODbL.
- Data licence for crypto prices (Coinbase and Binance APIs) is NOT confirmed.

## Decision

1. Primary crypto source: Coinbase Exchange, USD pairs, 1-hour candles.
2. Binance is optional and not part of the MVP. It may be added later as a price reconciliation test.
3. Dollar rate: BCB PTAX, daily closing bulletin.
4. Only closed candles are ingested (the current hour is never loaded).
5. All timestamps are stored in UTC.
6. Each candle uses the last PTAX already published at that moment. The same-day PTAX is not
   used before it exists (avoids look-ahead). Weekends and holidays reuse the last published value.
7. The public repository contains code and very small samples only. No raw data is committed.

## Consequences

- Backfill needs pagination in windows of up to 300 hours and deduplication on (pair, candle start).
- Candle and PTAX timezones differ, so the join rule must be tested in dbt.
- The licence question stays open. Until it is resolved, published dashboards must avoid
  redistributing raw exchange data.
- Using one exchange is a single point of failure and its prices are venue-specific.
