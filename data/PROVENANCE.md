# Data provenance

## Query dates

All RIPEstat and PeeringDB calls were made in August 2026. The archived outputs
in `out/` and `out2/` are snapshots of that state.

| Output | Source | Endpoint | Retrieved |
|---|---|---|---|
| `out/ua_asns_monthly.csv` | RIPEstat | `country-asns`, lod=0, monthly 2021-01 to 2026-08 | 2026-08 |
| `out/ua_peeringdb.csv` | PeeringDB | `/api/net?org__country=UA` | 2026-08 |
| `out2/prefix_outcomes.csv` | RIPEstat | `announced-prefixes`, `prefix-overview` | 2026-08 |
| `out2/*_geo*.csv` | RIPEstat | prefix geolocation | 2026-08 |

## Analysis window

- `T0 = 2024-09-01T00:00` — last full month before the tax change
- `T1 = 2026-08-01T00:00` — present
- Prefix recovery window at T0: 2024-08-01 to 2024-09-30
- Policy date: 2024-10-01 (simplified tax regime withdrawn)

## Known gaps

`2024-08-01` is missing from the monthly series: the RIPEstat call failed and the
script recorded a null rather than retrying. It falls in the pre-policy period,
immediately before the intervention date. The pre-period slope is therefore
reported across four specifications rather than as a point estimate.

## Why re-running gives different numbers

BGP is a live system. A prefix dark today may be announced next week; an AS
counted as departed may return. PeeringDB records are edited by their owners.
Any figure derived from these APIs is a statement about a moment, not a constant.
The scripts document how the snapshots were produced; the snapshots themselves
are the evidence.

## Not included

Interview material, provider contact details, and field notes are outside this
repository. The acquirer and seller lists derived at prefix level are public
routing data and are included; anything obtained under an interview consent
agreement is not.
