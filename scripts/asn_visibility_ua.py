#!/usr/bin/env python3
"""
asn_visibility_ua.py

Vitalii Atanasov, 2026
Part of a research project on market consolidation and network redundancy in
Ukraine's fixed-line ISP sector, 2021-2026.
https://github.com/vitaliiatanasov/ua-isp-consolidation

Measures the gap between MARKET visibility and ROUTING visibility in the
Ukrainian fixed-line ISP market.

Produces three numbers:

  1. Registered vs routed ASNs for UA, monthly, 2021-01 .. present  (RIPEstat)
  2. How many of those ASNs are actually ACCESS PROVIDERS rather than
     hosting / content / enterprise networks                        (PeeringDB)
  3. The resulting share of NCEC reporting entities that hold an ASN
     of their own -- i.e. the ceiling on what routing data can see.

Sources are public and unauthenticated.

    pip install requests pandas matplotlib
    python3 asn_visibility_ua.py

Outputs into ./out/ :
    ua_asns_monthly.csv     registered + routed ASN series
    ua_peeringdb.csv        UA networks with info_type classification
    ua_summary.json         the headline numbers
    ua_asn_visibility.png   two-panel chart
"""

import json
import os
import sys
import time
from datetime import date

import pandas as pd
import requests

OUT = "out"
UA = "ua"
START_YEAR, START_MONTH = 2021, 1
UA_TZ_SAFE_HOUR = "T00:00"          # RIS dumps land at 00:00 / 08:00 / 16:00 UTC
POLICY_DATE = "2024-10-01"          # simplified tax regime withdrawn
INVASION_DATE = "2022-02-24"

# NCEC reference point. This counts entities that filed reporting form 1-T for
# fixed internet access in the stated cumulative period. It is not a count of
# registered providers: the register and the reporting population are different
# objects and the difference is the subject of this work.
#
# 3386 = respondents, cumulative Q1-4 2024, read from the panel's show-as-table
#        export, captured 2026-09-02. Source row and precision are in
#        data/nkek-fixed-access-observations.csv; see data/PROVENANCE.md.
#
# Earlier value 3443, used up to commit 36c8d7b, was the Q1-2 2024 slice as
# published in the press citing NCEC in October 2024. The same slice reads 3450
# on the panel in September 2026, the seven-entity difference being late filings.
# It was superseded here because it is a half-year slice under an annual label.
REPORTING_ENTITIES = {
    "2024-12-31": 3386,
}

UA_AGENT = {"User-Agent": "asn-visibility-research/1.0 (academic use)"}


# ----------------------------------------------------------------------
# 1. RIPEstat: registered vs routed ASNs, monthly
# ----------------------------------------------------------------------
def month_starts(y0, m0):
    today = date.today()
    y, m = y0, m0
    while (y, m) <= (today.year, today.month):
        yield f"{y:04d}-{m:02d}-01"
        m += 1
        if m == 13:
            y, m = y + 1, 1


def fetch_country_asns(country=UA, sleep=0.4):
    """RIPEstat country-asns, lod=0 -> {'registered': N, 'routed': N}."""
    url = "https://stat.ripe.net/data/country-asns/data.json"
    rows = []
    for d in month_starts(START_YEAR, START_MONTH):
        params = {
            "resource": country,
            "query_time": d + UA_TZ_SAFE_HOUR,
            "lod": 0,
            "sourceapp": "asn-visibility-research",
        }
        try:
            r = requests.get(url, params=params, headers=UA_AGENT, timeout=45)
            r.raise_for_status()
            payload = r.json()["data"]["countries"][0]["stats"]
            rows.append(
                {
                    "date": d,
                    "registered": payload.get("registered"),
                    "routed": payload.get("routed"),
                }
            )
            print(f"  {d}  registered={payload.get('registered'):>5}  "
                  f"routed={payload.get('routed'):>5}")
        except Exception as e:                      # keep going on gaps
            print(f"  {d}  FAILED: {e}", file=sys.stderr)
            rows.append({"date": d, "registered": None, "routed": None})
        time.sleep(sleep)

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df["dark"] = df["registered"] - df["routed"]     # allocated but unannounced
    return df


# ----------------------------------------------------------------------
# 2. PeeringDB: which UA networks are access providers
# ----------------------------------------------------------------------
# PeeringDB info_type values. The first group is what an end-user ISP looks
# like; everything else is hosting, content, enterprise, academic, exchange.
ACCESS_TYPES = {"Cable/DSL/ISP", "NSP", "Non-Profit"}


def fetch_peeringdb():
    """All PeeringDB networks registered in Ukraine, with info_type."""
    url = "https://www.peeringdb.com/api/net"
    r = requests.get(url, params={"org__country": "UA", "depth": 0},
                     headers=UA_AGENT, timeout=90)
    r.raise_for_status()
    nets = r.json()["data"]
    df = pd.DataFrame(
        [
            {
                "asn": n.get("asn"),
                "name": n.get("name"),
                "info_type": n.get("info_type") or "(unset)",
                "info_scope": n.get("info_scope"),
                "created": n.get("created"),
            }
            for n in nets
        ]
    )
    print(f"  PeeringDB: {len(df)} UA networks")
    if not df.empty:
        print(df["info_type"].value_counts().to_string())
    return df


# ----------------------------------------------------------------------
# 3. Synthesis
# ----------------------------------------------------------------------
def summarise(asns: pd.DataFrame, pdb: pd.DataFrame) -> dict:
    latest = asns.dropna(subset=["routed"]).iloc[-1]
    routed = int(latest["routed"])
    registered = int(latest["registered"])

    pdb_total = len(pdb)
    pdb_access = int(pdb["info_type"].isin(ACCESS_TYPES).sum()) if pdb_total else 0
    access_share = pdb_access / pdb_total if pdb_total else float("nan")

    # PeeringDB covers only networks that chose to register there -- it skews
    # toward peering-active operators. Treat the share as an ESTIMATOR of the
    # access-provider fraction among routed ASNs, not as a census.
    est_access_asns = round(routed * access_share) if pdb_total else None

    providers = list(REPORTING_ENTITIES.values())[-1]

    out = {
        "as_of": str(latest["date"].date()),
        "asns_registered_ua": registered,
        "asns_routed_ua": routed,
        "asns_allocated_but_dark": registered - routed,
        "peeringdb_ua_networks": pdb_total,
        "peeringdb_access_type": pdb_access,
        "peeringdb_access_share": round(access_share, 4) if pdb_total else None,
        "estimated_access_provider_asns": est_access_asns,
        "ncec_reporting_entities": providers,
        "ncec_reporting_slice": "respondents, Q1-4 2024, table export, captured 2026-09-02",
        "share_of_providers_holding_own_asn": (
            round(est_access_asns / providers, 4) if est_access_asns else None
        ),
        "upper_bound_if_all_routed_were_isps": round(routed / providers, 4),
    }

    # Movement across the tax-policy date
    for label, cutoff in (("pre_policy", "2024-09-01"), ("post_policy_12m", "2025-09-01")):
        row = asns[asns["date"] == pd.Timestamp(cutoff)]
        if not row.empty and pd.notna(row.iloc[0]["routed"]):
            out[f"routed_{label}"] = int(row.iloc[0]["routed"])
    if "routed_pre_policy" in out and "routed_post_policy_12m" in out:
        out["routed_change_12m_after_policy"] = (
            out["routed_post_policy_12m"] - out["routed_pre_policy"]
        )
    return out


def plot(asns: pd.DataFrame, summary: dict, path: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(9, 8), sharex=True,
        gridspec_kw={"height_ratios": [2, 1]}
    )

    ax1.plot(asns["date"], asns["registered"], lw=1.8, label="Registered (RIR)")
    ax1.plot(asns["date"], asns["routed"], lw=1.8, label="Routed (seen in BGP)")
    for d, txt in ((INVASION_DATE, "full-scale invasion"),
                   (POLICY_DATE, "simplified regime withdrawn")):
        ax1.axvline(pd.Timestamp(d), color="0.4", ls="--", lw=1)
        ax1.text(pd.Timestamp(d), ax1.get_ylim()[1], f"  {txt}",
                 rotation=90, va="top", ha="left", fontsize=8, color="0.3")

    prov = summary.get("ncec_reporting_entities")
    if prov:
        ax1.axhline(prov, color="firebrick", ls=":", lw=1.5)
        ax1.text(asns["date"].iloc[2], prov,
                 f"  Entities filing 1-T for fixed access, 2024: {prov:,}",
                 va="bottom", fontsize=8, color="firebrick")

    ax1.set_ylabel("Autonomous systems, Ukraine")
    ax1.set_title("Market visibility vs routing visibility, Ukraine 2021–2026",
                  loc="left", fontsize=12)
    ax1.legend(frameon=False, fontsize=9)
    ax1.grid(alpha=0.25)

    ax2.plot(asns["date"], asns["dark"], lw=1.6, color="darkslategray")
    ax2.set_ylabel("Allocated but\nnot announced")
    ax2.grid(alpha=0.25)
    ax2.xaxis.set_major_locator(mdates.YearLocator())
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    fig.tight_layout()
    fig.savefig(path, dpi=170)
    print(f"  wrote {path}")


def replot():
    """Redraw the chart from the archived outputs, without touching the network.

    The reference figure and the labels derived from it change more often than
    the routing snapshot does. Refetching to redraw would replace the snapshot,
    so this path reads what is already in out/ and calls the same plot().
    """
    asns = pd.read_csv(f"{OUT}/ua_asns_monthly.csv", parse_dates=["date"])
    with open(f"{OUT}/ua_summary.json") as f:
        summary = json.load(f)
    print(f"[replot] routing snapshot as_of {summary['as_of']}, "
          f"reference figure {summary['ncec_reporting_entities']:,}")
    plot(asns, summary, f"{OUT}/ua_asn_visibility.png")


def main():
    os.makedirs(OUT, exist_ok=True)

    print("[1/3] RIPEstat country-asns, monthly ...")
    asns = fetch_country_asns()
    asns.to_csv(f"{OUT}/ua_asns_monthly.csv", index=False)

    print("[2/3] PeeringDB UA networks ...")
    try:
        pdb = fetch_peeringdb()
    except Exception as e:
        print(f"  PeeringDB failed ({e}); continuing without classification",
              file=sys.stderr)
        pdb = pd.DataFrame(columns=["asn", "name", "info_type"])
    pdb.to_csv(f"{OUT}/ua_peeringdb.csv", index=False)

    print("[3/3] Summary ...")
    summary = summarise(asns, pdb)
    with open(f"{OUT}/ua_summary.json", "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    plot(asns, summary, f"{OUT}/ua_asn_visibility.png")


if __name__ == "__main__":
    if "--replot" in sys.argv:
        replot()
    else:
        main()
