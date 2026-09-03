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
| `data/nkek-fixed-access-observations.csv` | NCEC dashboard, tab «Фікс. доступ до Інтернету» | show-as-table export | 2026-09-02 |
| `data/nkek-fixed-access-dashboard.json` | as above | provenance, derived values, regulatory context | 2026-09-02 |

## The NCEC reference figure

`out/ua_summary.json` carries two capture dates. The routing figures are the
August 2026 snapshot. The denominator, 3,386 entities filing form 1-T for fixed
access in 2024, was read from the regulator's table export on 2 September 2026.
Its source row, precision class and capture code are in the observations CSV.

The figure counts respondents, meaning entities that filed for the stated
cumulative period. It is not a count of registered providers. The register and
the reporting population are different objects, and the gap between them is the
subject of this work rather than an inconvenience in it.

Up to commit 36c8d7b this repository used 3,443, which is the Q1-2 2024 slice as
published in the press citing NCEC in October 2024. The same slice reads 3,450 on
the panel in September 2026; the seven-entity difference is late filings, about
two tenths of a percent over twenty-three months. Neither is wrong. Both are
half-year values, and they sat under an annual label, so the annual slice
replaced them. The summary was recomputed from the archived outputs rather than
by refetching, so the routing snapshot is untouched.

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
