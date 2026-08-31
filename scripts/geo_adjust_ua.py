#!/usr/bin/env python3
"""
geo_adjust_ua.py

Separates appropriation of networks in occupied territory from market
consolidation, and produces every adjusted output the proposal cites.

Reads two archived files and makes no network calls, so it reproduces its
outputs exactly:

    out2/prefix_outcomes.csv        raw output of prefix_substitution_ua.py
    out2/absorbed_prefix_geo.csv    RIPEstat geolocation of all 163 absorbed
                                    prefixes, retrieved 2026-08

    python3 scripts/geo_adjust_ua.py

Two filters:

IPv4 only. prefix_substitution_ua.py assigns addresses = 0 to every IPv6
prefix by construction (line 198) and aggregates address counts over IPv4
alone (line 211), so address-weighted figures were already IPv4-only. The 93
IPv6 rows are dropped here so the row population matches. Prefix counts are
not comparable across families either: IPv6 blocks in this set run /29 to /48
against /17 to /32 for IPv4. The exclusion cannot move the occupation split,
since none of the 11 absorbed IPv6 prefixes geolocates to RU.

RU-announced space split out. A prefix whose announced block geolocates to RU
is excluded from the consolidation figures as appropriation of a network in
occupied territory. Country comes
from the prefix, not from the acquiring AS holder's registered country: an AS
registered anywhere can announce a Ukrainian network.
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out2"

T0, T1 = "2024-09-01T00:00", "2026-08-01T00:00"
ROUTED_T0, ROUTED_T1, ASNS_NEW = 1661, 1584, 104

RAW = OUT / "prefix_outcomes.csv"
GEO = OUT / "absorbed_prefix_geo.csv"

OCCUPATION_COUNTRY = "RU"
KEEP_FAMILY = "ipv4"

IPV6_NOTE = (
    "IPv4 only. prefix_substitution_ua.py assigns addresses = 0 to every IPv6 "
    "prefix by construction and sums addresses over IPv4 alone, so "
    "address-weighted figures were already IPv4-only; the 93 IPv6 rows are "
    "dropped here so the row population matches. Prefix counts are not "
    "comparable across families: IPv6 blocks in this set run /29 to /48 "
    "against /17 to /32 for IPv4. None of the 11 absorbed IPv6 prefixes "
    "geolocates to RU, so the exclusion does not move the occupation split."
)

METHOD_NOTE = (
    "Country is determined by RIPEstat geolocation of the announced prefix "
    "itself, not by the acquiring AS holder's registered country: an AS "
    "registered elsewhere can still announce a UA-based network. Prefixes "
    "geolocating to RU are excluded from the consolidation finding as "
    "appropriation of networks in occupied territory. Prefixes geolocating to "
    "third countries are retained in the market set; see README on the asymmetry."
)

RETURNED_NOTE = (
    "RETURNED excluded from the finding by construction -- the same origin AS "
    "reappeared, i.e. observation noise at T0/T1, not an exit."
)


def main():
    raw = pd.read_csv(RAW)
    geo = pd.read_csv(GEO)

    dropped = raw[raw.family != KEEP_FAMILY]
    df = raw[raw.family == KEEP_FAMILY].merge(geo, on="prefix", how="left")

    is_occupation = (df.outcome == "ABSORBED") & (df.country == OCCUPATION_COUNTRY)
    df["outcome_adj"] = df.outcome.where(~is_occupation, "ABSORBED_RU_OCCUPATION")
    df.to_csv(OUT / "prefix_outcomes_geo_adjusted.csv", index=False)

    def acquirers(rows):
        g = (rows.groupby(["new_origin_asn", "new_origin_holder"], dropna=False)
                 .agg(prefixes=("prefix", "size"),
                      addresses=("addresses", "sum"),
                      sellers=("old_asn", "nunique"))
                 .reset_index()
                 .sort_values("addresses", ascending=False))
        g["new_origin_asn"] = g.new_origin_asn.astype(int)
        return g[["new_origin_asn", "new_origin_holder",
                  "prefixes", "addresses", "sellers"]]

    market = df[df.outcome_adj == "ABSORBED"]
    occupation = df[df.outcome_adj == "ABSORBED_RU_OCCUPATION"]

    acquirers(market).to_csv(OUT / "acquirers_ru_filtered.csv", index=False)
    acquirers(occupation).to_csv(OUT / "ru_occupation_acquirers.csv", index=False)

    px = df.outcome_adj.value_counts().to_dict()
    ad = df.groupby("outcome_adj").addresses.sum().astype(int).to_dict()
    resolved_px = px["ABSORBED"] + px["DARK"]
    resolved_ad = ad["ABSORBED"] + ad["DARK"]

    summary = {
        "t0": T0, "t1": T1,
        "routed_asns_t0": ROUTED_T0, "routed_asns_t1": ROUTED_T1,
        "asns_departed": int(len(pd.read_csv(OUT / "departed_asns.csv"))),
        "asns_departed_with_prefixes_recovered": int(raw.old_asn.nunique()),
        "asns_new": ASNS_NEW,
        "prefixes_checked_ipv4": int(len(df)),
        "prefixes_dropped_ipv6": int(len(dropped)),
        "returned_note": RETURNED_NOTE,
        "outcomes_prefix_count": {
            "DARK": px["DARK"],
            "ABSORBED_market": px["ABSORBED"],
            "ABSORBED_RU_occupation": px["ABSORBED_RU_OCCUPATION"],
            "RETURNED": px["RETURNED"],
        },
        "outcomes_ipv4_addresses": {
            "DARK": ad["DARK"],
            "ABSORBED_market": ad["ABSORBED"],
            "ABSORBED_RU_occupation": ad["ABSORBED_RU_OCCUPATION"],
            "RETURNED": ad["RETURNED"],
        },
        "absorbed_share_of_resolved_prefixes_market_only":
            round(px["ABSORBED"] / resolved_px, 4),
        "absorbed_share_of_resolved_addresses_market_only":
            round(ad["ABSORBED"] / resolved_ad, 4),
        "absorbed_share_if_RU_occupation_not_filtered":
            round((px["ABSORBED"] + px["ABSORBED_RU_OCCUPATION"])
                  / (px["ABSORBED"] + px["ABSORBED_RU_OCCUPATION"] + px["DARK"]), 4),
        "ru_occupation_share_of_resolved_addresses":
            round(ad["ABSORBED_RU_OCCUPATION"]
                  / (ad["ABSORBED"] + ad["ABSORBED_RU_OCCUPATION"] + ad["DARK"]), 4),
        "top5_market_acquirer_share_of_absorbed_addresses":
            round(market.groupby("new_origin_asn").addresses.sum().nlargest(5).sum()
                  / ad["ABSORBED"], 4),
        "distinct_market_acquirers": int(market.new_origin_asn.nunique()),
        "distinct_ru_occupation_acquirers": int(occupation.new_origin_asn.nunique()),
        "departed_asns_resurfacing_under_ru_origin": int(occupation.old_asn.nunique()),
        "departed_asns_resurfacing_under_ru_origin_list":
            sorted(int(x) for x in occupation.old_asn.unique()),
        "market_absorbed_prefixes_geolocating_outside_ua":
            int((market.country != "UA").sum()),
        "market_absorbed_addresses_geolocating_outside_ua":
            int(market.loc[market.country != "UA", "addresses"].sum()),
        "ipv6_note": IPV6_NOTE,
        "method_note": METHOD_NOTE,
    }
    with open(OUT / "substitution_summary_ru_adjusted.json", "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
