"""Split a send list into SEND and HOLDOUT files with a fixed, reproducible random split.

The split is a hash of (salt + last 10 digits of the phone), so the same person always lands in
the same group for a given salt, and the post-campaign read can recompute it.

Usage:
    python holdout_split.py <list.csv> --phone-col "Phone" --pct 10 --salt "festive-2026"
Writes <list>_SEND.csv and <list>_HOLDOUT_do_not_message.csv next to the input.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import pandas as pd


def bucket(phone: str, salt: str) -> int:
    return int(hashlib.sha256(f"{salt}|{phone}".encode()).hexdigest(), 16) % 100


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("list_csv")
    ap.add_argument("--phone-col", required=True)
    ap.add_argument("--pct", type=float, default=10)
    ap.add_argument("--salt", required=True, help="one salt per campaign; reuse it for the read-out")
    ap.add_argument("--digits", type=int, default=10)
    a = ap.parse_args()
    src = Path(a.list_csv)
    df = pd.read_csv(src, dtype=str, keep_default_na=False)
    p10 = df[a.phone_col].str.replace(r"\D", "", regex=True).str[-a.digits:]
    hold = p10.map(lambda p: bucket(p, a.salt) < a.pct)
    df[~hold].to_csv(src.with_name(src.stem + "_SEND.csv"), index=False)
    df[hold].to_csv(src.with_name(src.stem + "_HOLDOUT_do_not_message.csv"), index=False)
    print(f"{len(df):,} rows -> send {int((~hold).sum()):,}, holdout {int(hold.sum()):,} ({hold.mean():.1%}), salt '{a.salt}'")


if __name__ == "__main__":
    main()
