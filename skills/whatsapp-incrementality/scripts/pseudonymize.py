"""Make WhatsApp and order exports safe to analyse: no phone numbers, names, emails or addresses.

Run this yourself, before giving any file to Claude. It writes cleaned copies where:
  * every phone column is replaced by a keyed hash (HMAC-SHA256 of the last 10 digits),
    so the same number gets the same code in both files and the join still works;
  * columns that hold names, emails, addresses or notes are dropped;
  * any run of 8+ digits left inside other text (e.g. an error message quoting the number)
    is replaced with [number].

Why a secret key and not a plain hash: there are only ~10 billion 10-digit numbers, so a plain
SHA-256 of a phone number can be reversed by hashing every possible number. With a secret key
that never leaves your machine, the codes cannot be reversed without it. Keep the key file
private and reuse it for every export you want to join.

Phone columns are found from header names and from values that look like phone numbers; the
column names that were hashed, dropped and kept are printed so you can check them.

Usage:
    python pseudonymize.py <file> [<file> ...] --out <folder> [--key-file pseudonym.key]
           [--phone-cols "WA ID"] [--drop "Customer Notes"] [--keep "Tags"]
    # each input becomes <folder>/<name>_safe.csv; the key is created on first run

Only column names and row counts are printed, never values.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import re
import secrets
from pathlib import Path

import pandas as pd

PHONE_COL = re.compile(r"phone|mobile|recipient|whats.?app|msisdn|contact.?number|^to$|^number$", re.I)
PII_COL = re.compile(
    r"name|e-?mail|address|street|city|zip|postal|pin.?code|province|company|note|tag|"
    r"ip.?address|browser|landing|referr|customer(?!.?(type|segment|status))|contact|user|"
    r"first|last|gender|birth|dob|^id$|billing|shipping",
    re.I)
KEEP_ALWAYS = re.compile(r"order.?(id|name|number)|campaign|template|journey|flow|status|financial|cancel|"
                         r"created|date|time|_at$|^sent|deliver|read|click|fail|error|reason|total|value|price|"
                         r"amount|discount|product|sku|quantity|lineitem", re.I)
NO_SCRUB = re.compile(r"created|date|time|_at$|^sent|deliver|^read|click|total|value|price|amount|quantity|"
                      r"order.?(id|name|number)|^id$", re.I)
LONG_DIGITS = re.compile(r"\+?\d[\d\s-]{6,}\d")
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", re.I)
ORDER_NAME = re.compile(r"^#?[A-Za-z]{0,6}-?\d+$")


def looks_like_order_names(col: pd.Series) -> bool:
    """Shopify's 'Name' column is the order number (#1001). Elsewhere 'Name' is a person."""
    v = col.replace("", pd.NA).dropna().astype(str).str.strip().head(500)
    return len(v) > 0 and v.str.match(ORDER_NAME).mean() >= 0.9


PHONE_VALUE = re.compile(r"^\+?\d[\d\s-]{8,14}\d$")


def looks_like_phones(col: pd.Series) -> bool:
    """Catches phone columns with unusual headers ('WA ID', 'Customer'). Checked locally, never printed."""
    v = col.replace("", pd.NA).dropna().astype(str).str.strip().head(500)
    return len(v) > 0 and v.str.match(PHONE_VALUE).mean() >= 0.8


def mostly_emails(col: pd.Series) -> bool:
    v = col.replace("", pd.NA).dropna().astype(str).head(500)
    return len(v) > 0 and v.str.contains(EMAIL).mean() >= 0.3


def load_key(path: Path) -> bytes:
    if path.exists():
        return bytes.fromhex(path.read_text().strip())
    key = secrets.token_bytes(32)
    path.write_text(key.hex())
    print(f"created secret key {path} (keep it private, reuse it for every export)")
    return key


def hash_phone(v, key: bytes, digits: int):
    d = re.sub(r"\D", "", str(v or ""))
    if len(d) < digits:
        return ""
    return hmac.new(key, d[-digits:].encode(), hashlib.sha256).hexdigest()[:24]


def scrub(v):
    if not isinstance(v, str) or not v:
        return v
    return LONG_DIGITS.sub(lambda m: "[number]" if len(re.sub(r"\D", "", m.group())) >= 8 else m.group(), v)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--key-file", default="pseudonym.key")
    ap.add_argument("--digits", type=int, default=10)
    ap.add_argument("--keep", default="", help="comma-separated column names to keep even if they look personal")
    ap.add_argument("--phone-cols", default="", help="comma-separated phone column names, if not detected automatically")
    ap.add_argument("--drop", default="", help="comma-separated extra columns to drop")
    a = ap.parse_args()
    key = load_key(Path(a.key_file))
    keep_extra = {c.strip().lower() for c in a.keep.split(",") if c.strip()}
    phone_extra = {c.strip().lower() for c in a.phone_cols.split(",") if c.strip()}
    drop_extra = {c.strip().lower() for c in a.drop.split(",") if c.strip()}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for f in a.files:
        p = Path(f)
        df = pd.read_excel(p, dtype=str) if p.suffix.lower() in (".xlsx", ".xls") else pd.read_csv(p, dtype=str, keep_default_na=False)
        hashed, dropped, kept = [], [], []
        for c in list(df.columns):
            lc = c.lower()
            if lc in phone_extra or (lc not in keep_extra and (
                    PHONE_COL.search(c) or (not KEEP_ALWAYS.search(c) and looks_like_phones(df[c])))):
                df[c] = df[c].map(lambda v: hash_phone(v, key, a.digits))
                hashed.append(c)
            elif lc == "name" and lc not in drop_extra and looks_like_order_names(df[c]):
                kept.append(c)  # Shopify order number such as #1001
            elif lc in drop_extra or (lc not in keep_extra and (
                    (PII_COL.search(c) and not KEEP_ALWAYS.search(c)) or mostly_emails(df[c]))):
                df = df.drop(columns=c)
                dropped.append(c)
            else:
                if not NO_SCRUB.search(c):
                    df[c] = df[c].map(scrub)
                kept.append(c)
        dest = out / f"{p.stem}_safe.csv"
        df.to_csv(dest, index=False)
        print(f"\n{p.name}: {len(df):,} rows -> {dest.name}")
        print(f"  phone columns hashed : {', '.join(hashed) or 'NONE FOUND: rerun with --phone-cols "<your phone column>"'}")
        print(f"  personal columns dropped: {', '.join(dropped) or '-'}")
        print(f"  kept (long numbers inside free text replaced): {', '.join(kept)}")
    print("\nGive Claude only the *_safe.csv files. Never share the key file.")


if __name__ == "__main__":
    main()
