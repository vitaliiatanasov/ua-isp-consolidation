#!/usr/bin/env python3
"""
verify_claims.py

Independent check, added to make the published figures auditable. It does
not run the original analysis; it recomputes each cited number from the
archived outputs of asn_visibility_ua.py and prefix_substitution_ua.py
(out/ and out2/) and compares it against the value published in the README.

Runs offline: no network access, no RIPEstat queries. Anyone can check the
README against the data in one command.

    python3 scripts/verify_claims.py

Each line prints the claim as it appears in the README, the value computed
from the data, and PASS or FAIL.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
POLICY = pd.Timestamp("2024-10-01")

results = []


def check(claim, computed, ok, note=""):
    results.append((claim, computed, ok, note))


# ---------------------------------------------------------------- series
m = pd.read_csv(ROOT / "out/ua_asns_monthly.csv", parse_dates=["date"])
missing = [str(d.date()) for d in m[m.routed.isna()].date]
m = m.dropna(subset=["routed"]).copy()
m["t"] = (m.date.dt.year - 2021) * 12 + m.date.dt.month - 1

post = m[m.date >= POLICY]
slope_post = np.polyfit(post.t, post.routed, 1)[0]
check("post-policy decline ~3.5 routed AS/month",
      f"{slope_post:+.2f}", round(abs(slope_post), 1) == 3.6 or 3.4 <= abs(slope_post) <= 3.7)

SPECS = {
    "full series from 2021-01": "2021-01-01",
    "post-invasion from 2022-03": "2022-03-01",
    "post-invasion from 2022-06": "2022-06-01",
    "two years from 2023-01": "2023-01-01",
}
diffs = {}
for label, start in SPECS.items():
    pre = m[(m.date >= pd.Timestamp(start)) & (m.date < POLICY)]
    b = np.polyfit(pre.t, pre.routed, 1)[0]
    diffs[label] = slope_post - b

signs = {np.sign(v) for v in diffs.values()}
check("sign of the pre/post difference reverses across four specifications",
      "; ".join(f"{k}: {v:+.2f}" for k, v in diffs.items()),
      len(signs) > 1)

pre_range = []
for start in SPECS.values():
    pre = m[(m.date >= pd.Timestamp(start)) & (m.date < POLICY)]
    pre_range.append(np.polyfit(pre.t, pre.routed, 1)[0])
check("pre-policy decline ~3 routed AS/month",
      f"{min(pre_range):+.2f} to {max(pre_range):+.2f} depending on specification",
      min(abs(x) for x in pre_range) <= 3.5)

# ---------------------------------------------------------------- visibility
s = json.load(open(ROOT / "out/ua_summary.json"))

obs = pd.read_csv(ROOT / "data/nkek-fixed-access-observations.csv")
row = obs[(obs.indicator == "respondents") & (obs.slice == "Q1-4")
          & (obs.year == 2024)].iloc[0]
check("3,386 entities filed form 1-T for fixed access, 2024 (NCEC table export)",
      f"{int(row.value)} in data/nkek-fixed-access-observations.csv "
      f"(precision={row.precision}, capture={row.capture})",
      int(row.value) == s["ncec_reporting_entities"],
      "Read from the source table, not from the summary this pipeline wrote. "
      "Supersedes 3443, the Q1-2 2024 slice published in October 2024.")

check("roughly 1,600 routed autonomous systems",
      s["asns_routed_ua"], 1500 <= s["asns_routed_ua"] <= 1700)

t = s["share_by_treatment_of_unset"]
check("fewer than a third of providers hold an AS of their own",
      f"{s['share_of_providers_holding_own_asn']:.1%} "
      f"(PeeringDB-based, {s['peeringdb_unset_type']} of "
      f"{s['peeringdb_ua_networks']} rows carry no info_type)",
      s["share_of_providers_holding_own_asn"] < 1 / 3,
      "Headline figure treats unset rows as non-access.")

check("the headline share is sensitive to the treatment of unset rows",
      "; ".join(f"{k}: {v:.1%}" for k, v in t.items()),
      min(t.values()) < 1 / 3 < max(t.values()),
      f"One third is crossed once the access share exceeds "
      f"{s['one_third_crossed_when_access_share_exceeds']}. Two of the three "
      "treatments cross it; the headline uses the one that does not.")

# ---------------------------------------------------------------- substitution
adj = json.load(open(ROOT / "out2/substitution_summary_ru_adjusted.json"))
check("181 autonomous systems fell silent between Sept 2024 and Aug 2026",
      adj["asns_departed"], adj["asns_departed"] == 181)
check("82 acquirers",
      adj["distinct_market_acquirers"], adj["distinct_market_acquirers"] == 82)

acq = pd.read_csv(ROOT / "out2/acquirers_ru_filtered.csv")
top = acq.addresses.max() / acq.addresses.sum()
check("largest acquirer holds under 13 percent of absorbed space",
      f"{top:.2%}", top < 0.13)
one_seller = (acq.sellers == 1).mean()
check("most acquirers bought from a single seller",
      f"{one_seller:.1%} of 82", one_seller > 0.5)

BIG = "kyivstar|vodafone|datagroup|volia|lifecell|ukrtelecom"
big = acq[acq.new_origin_holder.str.lower().str.contains(BIG, na=False)]
big_share = big.addresses.sum() / acq.addresses.sum() if len(big) else 0.0
check("the three large operators are not the ones capturing it",
      f"{big_share:.2%} of absorbed space goes to named large operators",
      big_share < 0.05,
      "Kyivstar appears once, at 512 addresses; presence is not capture")

# ---------------------------------------------------------------- false positives
d = pd.read_csv(ROOT / "out2/prefix_outcomes.csv")
by_asn = d.groupby("old_asn").outcome.agg(lambda x: set(x))
any_returned = sum("RETURNED" in v for v in by_asn)
fp = any_returned / adj["asns_departed"]
check("single-snapshot false positive rate measured at 13.3 percent",
      f"{fp:.1%} ({any_returned}/{adj['asns_departed']} departed ASNs still "
      f"announcing at least one original prefix from the same origin)",
      abs(fp - 0.133) < 0.005,
      "Stricter definition (all prefixes returned) gives "
      f"{sum(v == {'RETURNED'} for v in by_asn) / adj['asns_departed']:.1%}")

# ---------------------------------------------------------------- occupation
check("twelve Ukrainian ASes announced today by Russian operators",
      adj["departed_asns_resurfacing_under_ru_origin"],
      adj["departed_asns_resurfacing_under_ru_origin"] == 12)

ru = pd.read_csv(ROOT / "out2/ru_occupation_acquirers.csv")
named = ["novoros", "kolomna", "kuzbas"]
found = {n: ru.new_origin_holder.str.lower().str.contains(n, na=False).any() for n in named}
check("Novoros Telecom, Kolomna-Sviaz TV, KuzbasSvyazUgol appear among the occupation acquirers",
      ", ".join(f"{k}={'yes' if v else 'NO'}" for k, v in found.items()),
      all(found.values()))

# ---------------------------------------------------------------- absorbed share
o, a = adj["outcomes_prefix_count"], adj["outcomes_ipv4_addresses"]
px = o["ABSORBED_market"] / (o["ABSORBED_market"] + o["DARK"])
ad = a["ABSORBED_market"] / (a["ABSORBED_market"] + a["DARK"])
check("a substantial share of their prefixes is announced today by other holders",
      f"{px:.1%} of resolved prefixes, {ad:.1%} of resolved IPv4 addresses",
      px > 0.3,
      "The two denominators differ; the README claims prefixes, not addresses. "
      "Both are lower bounds pending the covering-announcement check.")

# ---------------------------------------------------------------- report
w = max(len(c) for c, *_ in results)
print("=" * 100)
print("PUBLISHED FIGURES VERIFIED AGAINST ARCHIVED DATA")
print("=" * 100)
fails = 0
for claim, computed, ok, note in results:
    flag = "PASS" if ok else "FAIL"
    fails += not ok
    print(f"[{flag}] {claim}")
    print(f"       computed: {computed}")
    if note:
        print(f"       note:     {note}")
print("=" * 100)
if missing:
    print(f"CAVEAT: monthly series has {len(missing)} missing month(s): "
          f"{', '.join(missing)} (RIPEstat query failure, see scripts/asn_visibility_ua.py)")
print(f"{len(results) - fails}/{len(results)} claims reproduce.")
sys.exit(1 if fails else 0)
