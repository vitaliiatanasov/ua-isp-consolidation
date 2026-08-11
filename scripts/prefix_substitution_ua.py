#!/usr/bin/env python3
"""
prefix_substitution_ua.py

Vitalii Atanasov, 2026
Part of a research project on market consolidation and network redundancy in
Ukraine's fixed-line ISP sector, 2021-2026.
https://github.com/vitaliiatanasov/ua-isp-consolidation

Follow-up to asn_visibility_ua.py.

The AS-count series showed no acceleration after the October 2024 tax change.
That null result has one obvious alternative explanation: SUBSTITUTION. When a
small provider is bought, the physical network survives and its address space
keeps being announced -- but now from the acquirer's autonomous system. The
count of active ASNs falls by one; the topology, as seen in BGP, looks fine;
and an independent operator has disappeared without leaving a trace in the
metric.

This script tests that directly:

  1. Take the set of Ukrainian ASNs announcing routes at T0 (before the policy)
     and at T1 (now). The difference is the list of ASNs that went dark.
  2. For each departed ASN, recover the prefixes it was announcing at T0.
  3. Ask who, if anyone, announces those prefixes today.

Each prefix then falls into one of three outcomes:

     ABSORBED  -- announced today from a different origin AS
                  => consolidation, invisible to AS counts
     DARK      -- not announced by anyone
                  => genuine loss of reachable network
     RETURNED  -- same origin again (transient outage, not an exit)

The split between ABSORBED and DARK is the finding. It also produces a named
list of acquirers ranked by absorbed address space -- i.e. an interview list.

    pip install requests pandas
    python3 prefix_substitution_ua.py

Outputs into ./out2/ :
    departed_asns.csv        ASNs announcing at T0 but not at T1
    prefix_outcomes.csv      one row per prefix, with outcome and new origin
    acquirers.csv            acquiring ASNs ranked by absorbed IPv4 addresses
    substitution_summary.json
"""

import ipaddress
import json
import os
import re
import sys
import time
from collections import defaultdict

import pandas as pd
import requests

OUT = "out2"
BASE = "https://stat.ripe.net/data"
AGENT = {"User-Agent": "prefix-substitution-research/1.0 (academic use)"}
SLEEP = 0.4

T0 = "2024-09-01T00:00"          # last full month before the tax change
T1 = "2026-08-01T00:00"          # present
T0_WINDOW = ("2024-08-01", "2024-09-30")   # window for recovering prefixes

MAX_ASNS = None                 # set to an int to test on a subset first


def get(path, **params):
    params.setdefault("sourceapp", "prefix-substitution-research")
    r = requests.get(f"{BASE}/{path}/data.json", params=params,
                     headers=AGENT, timeout=60)
    r.raise_for_status()
    return r.json()["data"]


# ----------------------------------------------------------------------
# 1. Which ASNs stopped announcing between T0 and T1
# ----------------------------------------------------------------------
def _as_set(blob):
    """country-asns lod=1 returns ASN lists in a few shapes. Normalise."""
    if blob is None:
        return set()
    if isinstance(blob, str):
        items = re.split(r"[,\s]+", blob)
    elif isinstance(blob, (list, tuple)):
        items = blob
    else:
        items = []
    out = set()
    for x in items:
        m = re.search(r"(\d+)", str(x))
        if m:
            out.add(int(m.group(1)))
    return out


def routed_asns(query_time):
    d = get("country-asns", resource="ua", lod=1, query_time=query_time)
    c = d["countries"][0]
    blob = c.get("routed")
    s = _as_set(blob)
    if not s:
        raise RuntimeError(
            f"could not parse routed ASN list at {query_time}; "
            f"got type {type(blob)} -> {str(blob)[:200]}"
        )
    return s


# ----------------------------------------------------------------------
# 2. What each departed ASN was announcing at T0
# ----------------------------------------------------------------------
def prefixes_at_t0(asn):
    d = get("announced-prefixes", resource=f"AS{asn}",
            starttime=T0_WINDOW[0], endtime=T0_WINDOW[1])
    return [p["prefix"] for p in d.get("prefixes", []) if p.get("prefix")]


# ----------------------------------------------------------------------
# 3. Who announces those prefixes now
# ----------------------------------------------------------------------
def current_origin(prefix):
    """-> (announced: bool, origin_asn: int|None, holder: str|None)"""
    d = get("prefix-overview", resource=prefix, max_related=0)
    asns = d.get("asns") or []
    if not d.get("announced") or not asns:
        return False, None, None
    return True, int(asns[0]["asn"]), asns[0].get("holder")


def addresses(prefix):
    try:
        return ipaddress.ip_network(prefix, strict=False).num_addresses
    except ValueError:
        return 0


def is_v4(prefix):
    return ":" not in prefix


# ----------------------------------------------------------------------
def main():
    os.makedirs(OUT, exist_ok=True)

    print(f"[1/3] routed ASN sets at {T0} and {T1} ...")
    a0 = routed_asns(T0)
    time.sleep(SLEEP)
    a1 = routed_asns(T1)
    departed = sorted(a0 - a1)
    arrived = sorted(a1 - a0)
    print(f"  T0={len(a0)}  T1={len(a1)}  departed={len(departed)}  new={len(arrived)}")

    pd.DataFrame({"asn": departed}).to_csv(f"{OUT}/departed_asns.csv", index=False)

    todo = departed[:MAX_ASNS] if MAX_ASNS else departed

    print(f"[2/3] recovering prefixes for {len(todo)} departed ASNs ...")
    asn_prefixes = {}
    for i, asn in enumerate(todo, 1):
        try:
            px = prefixes_at_t0(asn)
            asn_prefixes[asn] = px
            print(f"  [{i}/{len(todo)}] AS{asn}: {len(px)} prefixes")
        except Exception as e:
            print(f"  [{i}/{len(todo)}] AS{asn}: FAILED {e}", file=sys.stderr)
            asn_prefixes[asn] = []
        time.sleep(SLEEP)

    total_px = sum(len(v) for v in asn_prefixes.values())
    print(f"[3/3] checking current origin of {total_px} prefixes ...")

    rows = []
    n = 0
    for asn, pxs in asn_prefixes.items():
        for px in pxs:
            n += 1
            try:
                ann, origin, holder = current_origin(px)
            except Exception as e:
                print(f"  {px}: FAILED {e}", file=sys.stderr)
                ann, origin, holder = None, None, None
            if ann is None:
                outcome = "ERROR"
            elif not ann:
                outcome = "DARK"
            elif origin == asn:
                outcome = "RETURNED"
            else:
                outcome = "ABSORBED"
            rows.append({
                "old_asn": asn,
                "prefix": px,
                "family": "ipv4" if is_v4(px) else "ipv6",
                "addresses": addresses(px) if is_v4(px) else 0,
                "outcome": outcome,
                "new_origin_asn": origin,
                "new_origin_holder": holder,
            })
            if n % 25 == 0:
                print(f"  {n}/{total_px}")
            time.sleep(SLEEP)

    df = pd.DataFrame(rows)
    df.to_csv(f"{OUT}/prefix_outcomes.csv", index=False)

    # ---- aggregate -------------------------------------------------
    v4 = df[df.family == "ipv4"]
    by_outcome = df.outcome.value_counts().to_dict()
    addr_by_outcome = v4.groupby("outcome").addresses.sum().to_dict()

    acq = (v4[v4.outcome == "ABSORBED"]
           .groupby(["new_origin_asn", "new_origin_holder"], dropna=False)
           .agg(prefixes=("prefix", "count"),
                addresses=("addresses", "sum"),
                sellers=("old_asn", "nunique"))
           .reset_index()
           .sort_values("addresses", ascending=False))
    acq.to_csv(f"{OUT}/acquirers.csv", index=False)

    absorbed = by_outcome.get("ABSORBED", 0)
    dark = by_outcome.get("DARK", 0)
    denom = absorbed + dark

    top_share = None
    if len(acq):
        tot = acq.addresses.sum()
        if tot:
            top_share = round(acq.head(5).addresses.sum() / tot, 4)

    summary = {
        "t0": T0, "t1": T1,
        "routed_asns_t0": len(a0),
        "routed_asns_t1": len(a1),
        "asns_departed": len(departed),
        "asns_new": len(arrived),
        "prefixes_checked": int(len(df)),
        "outcomes": by_outcome,
        "ipv4_addresses_by_outcome": {k: int(v) for k, v in addr_by_outcome.items()},
        "absorbed_share_of_resolved_prefixes": (
            round(absorbed / denom, 4) if denom else None
        ),
        "distinct_acquirers": int(len(acq)),
        "top5_acquirer_share_of_absorbed_addresses": top_share,
    }
    with open(f"{OUT}/substitution_summary.json", "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if len(acq):
        print("\nTop acquirers:")
        print(acq.head(15).to_string(index=False))


if __name__ == "__main__":
    main()
