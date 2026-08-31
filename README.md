# Market consolidation and network redundancy in Ukraine, 2021–2026

Vitalii Atanasov · Kyiv · 2026

Routing-data analysis of what happened to Ukraine's small internet providers after
1 October 2024, when the State Tax Service withdrew their simplified tax regime.

**The headline result is negative, and that is the point.** The count of routed
Ukrainian autonomous systems shows no break at the policy date. It cannot: fewer
than a third of the country's fixed-access providers hold an autonomous system at
all. Routing data marks the boundary of what is observable in this industry, and
that boundary sits above the layer where the change is happening.

## Reproduce the published numbers

```bash
pip install -r requirements.txt
python3 scripts/verify_claims.py
```

Runs offline against the archived outputs in `out/` and `out2/`. Prints every
figure cited in the research proposal alongside the value computed from the data.
No network access, no API keys.

## What the analysis found

| | |
|---|---|
| Routed UA autonomous systems, Aug 2026 | 1,584 (2,016 registered) |
| Operators reporting fixed access, 2024 | 3,443 |
| Providers estimated to hold their own AS | 29.9% (PeeringDB-based, interval estimate) |
| ASes announcing at T0 but not at T1 | 181 |
| ASes with prefixes recovered | 179 of 181 (AS48880 and AS197710 returned none) |
| Decline, before / after Oct 2024 | −2.9 to −4.0 / −3.6 AS per month |
| Distinct market acquirers | 82; largest holds 12.7% of absorbed space |
| Acquirers buying from a single seller | 73 of 82 |
| Market-absorbed prefixes geolocating outside UA | 50 of 129, 29.1% of absorbed address space |
| Departed UA ASes resurfacing under Russian origin | 12 |

The trend difference across the policy date is not identified. Depending on how
the pre-period is bounded, the estimate shows either acceleration or deceleration;
the sign reverses. `verify_claims.py` prints all four specifications.

## Layout

```
scripts/asn_visibility_ua.py        registered vs routed AS series, PeeringDB classification
scripts/prefix_substitution_ua.py   what happened to the prefixes of departed ASes
scripts/geo_adjust_ua.py            separates occupation from market consolidation, offline
scripts/verify_claims.py            offline check of every published figure
data/PROVENANCE.md                  query dates, sources, why re-running gives different numbers
```

**`out/` — market vs routing visibility**

| File | Contents |
|---|---|
| `ua_asns_monthly.csv` | Registered and routed UA autonomous systems, monthly 2021-01 to 2026-08. `dark` = allocated but not announced. 2024-08 is null (query failure). |
| `ua_peeringdb.csv` | 288 UA-registered PeeringDB networks with `info_type` classification |
| `ua_summary.json` | Headline visibility figures. **Cited in the proposal.** |
| `ua_asn_visibility.png` | Two-panel chart of the series |

**`out2/` — what happened to departed ASes**

| File | Contents |
|---|---|
| `departed_asns.csv` | The 181 ASes announcing at T0 but not at T1 |
| `prefix_outcomes.csv` | One row per prefix (509: 416 IPv4, 93 IPv6), with outcome and new origin. Occupation not yet separated. |
| `absorbed_prefix_geo.csv` | Archived RIPEstat geolocation of all 163 absorbed prefixes, retrieved 2026-08. Input to the adjustment below. |
| `acquirer_countries.csv` | Archived country attribution per acquiring AS, retrieved 2026-08. Input to the adjustment below. |
| `prefix_outcomes_geo_adjusted.csv` | IPv4 only (416 rows), each prefix geolocated, RU-announced space split out in `outcome_adj`. Produced by `geo_adjust_ua.py`. |
| `acquirers_ru_filtered.csv` | Market acquirers, 82 rows. Produced by `geo_adjust_ua.py`. **Cited in the proposal.** |
| `ru_occupation_acquirers.csv` | The 17 Russian holders announcing appropriated UA space. Produced by `geo_adjust_ua.py`. |
| `substitution_summary_ru_adjusted.json` | Occupation separated. Produced by `geo_adjust_ua.py`. **Cited in the proposal.** |
| `acquirers.csv` | Raw acquirer ranking, 97 rows. **Superseded** — see below. |
| `substitution_summary.json` | Raw script output. **Superseded** — see below. |
| `prefix_substitution_raw_run.log` | Full console record of the substitution run. Its closing summary block prints the *pre-adjustment* figures (97 acquirers, 163 absorbed) — this is the raw run, kept for audit, not the reported result. |

Dependency order:

```
prefix_outcomes.csv + absorbed_prefix_geo.csv  ->  geo_adjust_ua.py  ->  *_geo_adjusted, acquirers_*, *_ru_adjusted
```

Every file cited in the proposal is either produced by a script above or marked
in the table as an archived lookup with a retrieval date.

## Method, in three steps

1. **Monthly series.** RIPEstat `country-asns` for UA, 2021-01 to 2026-08,
   registered and routed counts. Registered-minus-routed gives address space
   allocated but not announced.

2. **Who is actually an access provider.** Routed AS counts include hosting,
   content and enterprise networks. PeeringDB `info_type` classifies UA-registered
   networks; the access-provider share is applied to the routed count as an
   estimator. PeeringDB covers 288 of ~1,584 routed UA systems, so this is an
   estimator, not a census, and the derived share is reported as an interval in
   the proposal.

3. **Substitution.** For each AS announcing at 2024-09-01 but not at 2026-08-01,
   recover the prefixes it announced at T0 and ask who announces them now. Three
   outcomes: `ABSORBED` (different origin), `DARK` (nobody), `RETURNED` (same
   origin again). `geo_adjust_ua.py` then geolocates each absorbed prefix and
   splits appropriation in occupied territory out of the consolidation figures.

## Six things a reader should know before citing this

**`RETURNED` is a measurement artefact, and it sets the error rate.** 24 of the
181 "departed" ASes are still announcing at least one of their original prefixes
from the same origin. They were never absent; the single-instant snapshot caught
them mid-flap. That is a 13.3% false positive rate for the snapshot method, which
is why the proposal commits to a multi-month window instead. Under the stricter
definition — every prefix returned — the rate is 9.9%. The looser figure is
reported because a partially-returned AS is equally a false exit. The denominator
is the 181 departed ASes; prefixes were recovered for 179 of them, and against
that denominator the rate is 13.4%.

**Every published figure is IPv4-only.** `prefix_outcomes.csv` holds 509 rows: 416 IPv4 and 93 IPv6.
The adjusted files hold 416. `prefix_substitution_ua.py` assigns `addresses = 0`
to every IPv6 prefix by construction and sums addresses over IPv4 alone, so
address-weighted figures were already IPv4-only before any adjustment; dropping
the IPv6 rows makes the row population match the weighting. Prefix counts are not
comparable across families either — IPv6 blocks here run /29 to /48 against /17
to /32 for IPv4. The dropped rows were `DARK` 75, `ABSORBED` 11, `RETURNED` 7, so
the exclusion moves every prefix-weighted ratio below. It cannot move the
occupation split: geolocation was obtained for all 11 absorbed IPv6 prefixes and
none is RU (9 UA, 1 NL, 1 US).

**Absorbed share depends on the denominator.** Of prefixes whose fate resolves,
49.0% are absorbed; by IPv4 address count, 31.7%. Small providers hold small
blocks, so prefix-weighted and address-weighted answers differ. Neither is
reported as the headline finding, because both are lower bounds until covering
and more-specific announcements are checked: a block re-cut by its buyer is
currently misclassified `DARK`.

**Occupation is separated from market consolidation.** 23 absorbed prefixes
geolocate to Russia. These are not transactions; they are appropriation of
networks in occupied territory, and they are excluded from the consolidation
figures. Country is determined from the announced prefix, not from the acquiring
AS holder's registered country, because an AS registered anywhere can announce a
Ukrainian network. Two holders (INLAN, Perspektiva-TV) appear in **both** lists:
some of their prefixes geolocate to UA and some to RU. That is the classification
working as intended, not a duplicate.

**The geolocation criterion is applied asymmetrically.** 23 absorbed prefixes geolocate to RU and are excluded
as appropriation. 50 more geolocate to Germany, the United States, France, the
Czech Republic, Iran, Kyrgyzstan and elsewhere, and are retained in the
market-consolidation figure — 50 of 129 prefixes, 14,080 of 48,384 addresses,
29.1% of absorbed space. Either geolocation is informative about where a network
sits, in which case those 50 need an account and the consolidation figure is an
overstatement; or it is noisy for small blocks and reflects the acquirer's
infrastructure, in which case the RU exclusion rests on something other than
geolocation. Which reading holds is not settled here; both counts are above.

**Superseded files still in the tree, and why.**
`out2/substitution_summary.json` is the raw script output, with occupation not yet
separated (97 acquirers, 163 absorbed prefixes). `out2/acquirers.csv` is its
acquirer ranking, and the closing summary block of `out2/prefix_substitution_raw_run.log` prints the
same pre-adjustment numbers. All three are superseded by
`out2/substitution_summary_ru_adjusted.json` and `out2/acquirers_ru_filtered.csv`
(82 market acquirers, 129 absorbed prefixes), which are what the proposal cites.
The raw outputs are kept so the adjustment can be audited rather than taken on
trust — if you find 97 where the proposal says 82, you are reading the
pre-adjustment file.

## Limitations

Ukrainian registers are incomplete and define "provider" inconsistently, including
resellers with no infrastructure of their own, so part of the gap between the
market count and the routing count is definitional rather than empirical. Country
attribution of autonomous systems is administrative. The causal contribution of
consolidation is not identified and is not claimed. The monthly series is missing
2024-08 to a RIPEstat query failure — the month immediately before the policy
date, which is why the pre-period slope is reported across several specifications
rather than as a point estimate.

## Reproducing from live data

`scripts/asn_visibility_ua.py` and `scripts/prefix_substitution_ua.py` query
RIPEstat and PeeringDB directly. **Re-running them will not reproduce the numbers
above.** BGP is a live system: prefixes move, ASes return, PeeringDB records
change. The archived outputs in `out/` and `out2/` are the analysis; the scripts
are how it was produced. See `data/PROVENANCE.md` for query dates.

`scripts/geo_adjust_ua.py` makes no network calls and transforms archived files
only, so it reproduces its outputs exactly.

## License

Code MIT. Data CC BY 4.0. RIPEstat and PeeringDB data are redistributed under
their respective terms.
