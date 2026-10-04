"""Profile a WhatsApp message export and an orders export, and draft config.json.

Every WhatsApp platform names its columns differently. This script lists every column with
sample values, guesses which column is which, checks whether Meta's failure codes (131049,
130472) are present, and writes a draft config for you to confirm before running.

Usage:
    python profile_inputs.py --messages "<glob or file>" --orders "<glob or file>" --out <folder>
"""
from __future__ import annotations

import argparse
import glob
import json
import re
from pathlib import Path

import pandas as pd

GUESS = {
    "phone": [r"^recipient$", r"phone", r"mobile", r"whatsapp.?number", r"^to$", r"contact", r"number"],
    "campaign": [r"campaign", r"broadcast", r"journey", r"flow", r"template", r"automation"],
    "sent_at": [r"sent.?(at|on|time|date)", r"^sent$", r"created", r"timestamp", r"send.?time"],
    "delivered_at": [r"deliver"],
    "failure_reason": [r"fail.*(cause|reason|error)", r"error", r"reason", r"fail"],
    "read_at": [r"read"],
    "clicked_at": [r"click"],
    "attributed_order_id": [r"order.?id", r"order.?name", r"attributed.?order"],
    "attributed_order_value": [r"order.?value", r"revenue", r"attributed.?value"],
}
ORDER_GUESS = {
    "order_id": [r"^name$", r"order.?(id|name|number)", r"^id$"],
    "created_at": [r"created", r"order.?date", r"date"],
    "order_value": [r"^total$", r"total.?price", r"order.?(total|value)", r"amount", r"subtotal"],
}


def load(pattern):
    files = sorted(glob.glob(pattern))
    if not files:
        raise SystemExit(f"no files match {pattern}")
    frames = [pd.read_excel(f, dtype=str) if f.lower().endswith((".xlsx", ".xls"))
              else pd.read_csv(f, dtype=str, keep_default_na=False) for f in files]
    return files, pd.concat(frames, ignore_index=True)


def pick(cols, patterns, used):
    for pat in patterns:
        for c in cols:
            if c not in used and re.search(pat, c, re.I):
                return c
    return None


def describe(df, name):
    print(f"\n=== {name}: {len(df):,} rows, {len(df.columns)} columns")
    for c in df.columns:
        vals = df[c].replace("", pd.NA).dropna()
        sample = " | ".join(vals.astype(str).head(3).str.slice(0, 40))
        print(f"  {c[:38]:38s} filled {len(vals) / max(len(df), 1):5.0%}  e.g. {sample}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--messages", required=True)
    ap.add_argument("--orders", required=True)
    ap.add_argument("--out", default=".")
    a = ap.parse_args()
    mfiles, m = load(a.messages)
    ofiles, o = load(a.orders)
    describe(m, f"messages ({len(mfiles)} file(s))")
    describe(o, f"orders ({len(ofiles)} file(s))")

    used, mc = set(), {}
    for k, pats in GUESS.items():
        mc[k] = pick(list(m.columns), pats, used)
        if mc[k]:
            used.add(mc[k])
    used, oc = set(), {}
    for k, pats in ORDER_GUESS.items():
        oc[k] = pick(list(o.columns), pats, used)
        if oc[k]:
            used.add(oc[k])
    oc["phones"] = [c for c in o.columns if re.search(r"phone|mobile", c, re.I)]

    text = m.astype(str).apply(lambda s: s.str.cat(sep=" ")[:5_000_000])
    has49 = any(re.search(r"131049|healthy ecosystem", v, re.I) for v in text)
    has72 = any(re.search(r"130472|part of an experiment", v, re.I) for v in text)
    one_campaign_per_file = mc["campaign"] is None and len(mfiles) > 1

    print("\n=== Draft mapping (CONFIRM before running)")
    for k, v in mc.items():
        print(f"  messages.{k:24s} -> {v}")
    for k, v in oc.items():
        print(f"  orders.{k:26s} -> {v}")
    print(f"\n  Meta cap 131049 found:        {has49}")
    print(f"  Meta random holdout 130472:   {has72}")
    if not has49 and not has72:
        print("  WARNING: no Meta failure codes found. Past sends cannot be measured with natural controls;"
              " check the failure column, or start a holdout with holdout_split.py.")
    if one_campaign_per_file:
        print("  No campaign column: campaign names will come from file names.")

    cfg = {
        "messages": {"files": mfiles, "dayfirst": True, "campaign_from_filename": one_campaign_per_file,
                     "columns": {k: v for k, v in mc.items() if v}},
        "orders": {"files": ofiles, "dayfirst": False,
                   "columns": {"order_id": oc["order_id"], "created_at": oc["created_at"],
                               "phones": oc["phones"], "order_value": oc["order_value"]},
                   "exclude_if": [c for c in [
                       {"column": "Cancelled at", "not_empty": True} if "Cancelled at" in o.columns else None,
                       {"column": "Financial Status", "in": ["refunded", "voided"]} if "Financial Status" in o.columns else None,
                   ] if c]},
        "phone_digits": 10, "windows_days": [3, 7, 14], "group_windows": {}, "campaign_groups": {},
        "episode_gap_days": 14, "min_control": 20, "cost_per_message": None, "margin_per_order": None,
        "output_dir": "incrementality_output",
    }
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    camps = (pd.Series([Path(f).stem for f in mfiles]) if one_campaign_per_file else m[mc["campaign"]]).value_counts() if (one_campaign_per_file or mc["campaign"]) else pd.Series(dtype=int)
    print(f"\nCampaigns found: {len(camps)}")
    print(camps.head(30).to_string())
    print(f"\ndraft config written to {out / 'config.json'}")


if __name__ == "__main__":
    main()
