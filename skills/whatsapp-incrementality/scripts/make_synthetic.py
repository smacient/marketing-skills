"""Generate a synthetic message log + orders file with KNOWN true effects, to test the method.

Built-in truths:
  * "Festive sale" broadcast (3 waves): true lift +4.0pp for customers 121-240 days since last
    order with 3+ orders, +1.5pp for other 121-365 day customers, +0.5pp for recent buyers,
    0 for never-bought leads.
  * "Reorder reminder" journey: +3pp within 3 days, fully pulled forward (no extra orders by day 14).
  * "Cart recovery" journey: no effect.
  * Meta cap (131049) hits less-engaged customers more often (introduces the known bias);
    2% of recipients land in Meta's random holdout (130472).

Usage:
    python make_synthetic.py <output folder> [--seed 7] [--customers 60000]
Writes messages.csv, orders.csv, config.json and truth.json.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--seed", type=int, default=7)
ap.add_argument("--customers", type=int, default=60000)
a = ap.parse_args()
rng = np.random.default_rng(a.seed)
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)

N = a.customers
T0 = datetime(2026, 1, 1)
SALE = datetime(2026, 8, 13, 9)
phones = np.array([f"91{9000000000 + i}" for i in range(N)])
engaged = rng.random(N)                       # 0..1 engagement score
in_meta_holdout = rng.random(N) < 0.03       # Meta holds a user out consistently, not per message
buyer = rng.random(N) < 0.8                   # 20% are leads with no orders
n_orders = np.where(buyer, rng.geometric(0.45, N), 0)
orders = []
oid = 1
last = {}
for i in np.where(buyer)[0]:
    days = np.sort(rng.integers(0, 590, n_orders[i]))  # history up to ~12 Aug 2026 minus margin
    for dd in days:
        t = datetime(2025, 1, 1) + timedelta(days=int(dd), hours=int(rng.integers(8, 23)))
        if t >= SALE - timedelta(days=1):
            continue
        orders.append((oid, t, phones[i], float(rng.integers(600, 1800)))); oid += 1
        last[i] = max(last.get(i, t), t)
hist = pd.DataFrame(orders, columns=["id", "created_at", "phone", "total"])
pc = hist.groupby("phone").agg(k=("id", "size"), last=("created_at", "max"))
rec = (SALE - pc["last"]).dt.days.reindex(phones).to_numpy()
k = pc["k"].reindex(phones).fillna(0).to_numpy()

def base_rate(i):  # chance of an order in a 13-day window without messages
    if k[i] == 0:
        return 0.005
    r = rec[i]
    b = 0.06 if r <= 120 else 0.012 if r <= 240 else 0.006 if r <= 365 else 0.002
    return b * (1 + 0.6 * engaged[i]) * (1.6 if k[i] >= 3 else 1.0)

def sale_lift(i):
    if k[i] == 0:
        return 0.0
    r = rec[i]
    if 121 <= r <= 240 and k[i] >= 3:
        return 0.04
    if 121 <= r <= 365:
        return 0.015
    if r <= 120:
        return 0.005
    return 0.001

msgs = []
truth_incr = 0.0
for wave, day in enumerate([0, 4, 10]):
    for i in range(N):
        if wave > 0 and rng.random() < 0.35:
            continue
        t = SALE + timedelta(days=day, minutes=int(rng.integers(0, 90)))
        p_cap = 0.08 + 0.35 * (1 - engaged[i]) + (0.15 if wave == 2 else 0)
        u = rng.random()
        if in_meta_holdout[i]:
            msgs.append((phones[i], "Festive sale", t, None, "(#130472) User's number is part of an experiment"))
        elif u < p_cap:
            msgs.append((phones[i], "Festive sale", t, None, "131049: This message was not delivered to maintain healthy ecosystem engagement."))
        else:
            msgs.append((phones[i], "Festive sale", t, t + timedelta(seconds=30), ""))
sm = pd.DataFrame(msgs, columns=["phone", "campaign", "sent", "delivered", "reason"])
got = sm[sm["delivered"].notna()].groupby("phone").size()
got_set = set(got.index)
sale_orders = []
for i in range(N):
    p = base_rate(i) + (sale_lift(i) if phones[i] in got_set else 0)
    if rng.random() < p:
        sale_orders.append((oid, SALE + timedelta(days=float(rng.uniform(0, 12.5))), phones[i], float(rng.integers(700, 1900)))); oid += 1
    if phones[i] in got_set:
        truth_incr += sale_lift(i)

# Reorder reminder journey (Sep): pull-forward only
jmsgs = []
J0 = datetime(2026, 9, 1, 10)
jr = rng.choice(np.where(k >= 1)[0], 8000, replace=False)
pull_true_3d = 0.0
for i in jr:
    t = J0 + timedelta(days=int(rng.integers(0, 20)), hours=int(rng.integers(0, 8)))
    u = rng.random()
    p_cap = 0.08 + 0.3 * (1 - engaged[i])
    if in_meta_holdout[i]:
        jmsgs.append([phones[i], "Reorder reminder", t, None, "130472 part of an experiment"]); deliv = False
    elif u < p_cap:
        jmsgs.append([phones[i], "Reorder reminder", t, None, "131049 healthy ecosystem engagement"]); deliv = False
    else:
        jmsgs.append([phones[i], "Reorder reminder", t, t + timedelta(seconds=20), ""]); deliv = True
    will_buy = rng.random() < 0.06 * (1 + 0.6 * engaged[i])
    if will_buy:
        lag = rng.uniform(0, 14)
        if deliv and rng.random() < 0.5:
            lag = rng.uniform(0, 2.5)       # same order, just earlier
        sale_orders.append((oid, t + timedelta(days=float(lag)), phones[i], 900.0)); oid += 1

# Cart recovery journey: no effect
for i in rng.choice(np.arange(N), 3000, replace=False):
    t = J0 + timedelta(days=int(rng.integers(0, 20)))
    u = rng.random()
    if in_meta_holdout[i]:
        jmsgs.append([phones[i], "Cart recovery", t, None, "130472 part of an experiment"])
    elif u < 0.23:
        jmsgs.append([phones[i], "Cart recovery", t, None, "131049 healthy ecosystem engagement"])
    else:
        jmsgs.append([phones[i], "Cart recovery", t, t + timedelta(seconds=20), ""])
    if rng.random() < 0.15:
        sale_orders.append((oid, t + timedelta(days=float(rng.uniform(0, 5))), phones[i], 1100.0)); oid += 1

sm = pd.concat([sm, pd.DataFrame(jmsgs, columns=sm.columns)], ignore_index=True)
allo = pd.concat([hist, pd.DataFrame(sale_orders, columns=hist.columns)])
allo["phone"] = "+" + allo["phone"].str[:2] + " " + allo["phone"].str[2:]   # different format on purpose
allo["financial_status"] = np.where(rng.random(len(allo)) < 0.02, "refunded", "paid")
allo.rename(columns={"id": "Name", "created_at": "Created at", "phone": "Phone", "total": "Total"}).to_csv(out / "orders.csv", index=False)
sm["sent"] = pd.to_datetime(sm["sent"]).dt.strftime("%d/%m/%Y, %I:%M:%S %p")
sm["delivered"] = pd.to_datetime(sm["delivered"]).dt.strftime("%d/%m/%Y, %I:%M:%S %p")
sm.rename(columns={"phone": "Recipient", "campaign": "Campaign", "sent": "Sent At", "delivered": "Delivered At",
                   "reason": "Fail Cause"}).to_csv(out / "messages.csv", index=False)

cfg = {
    "messages": {"files": ["messages.csv"], "dayfirst": True,
                 "columns": {"phone": "Recipient", "campaign": "Campaign", "sent_at": "Sent At",
                             "delivered_at": "Delivered At", "failure_reason": "Fail Cause"}},
    "orders": {"files": ["orders.csv"], "dayfirst": False,
               "columns": {"order_id": "Name", "created_at": "Created at", "phones": ["Phone"], "order_value": "Total"},
               "exclude_if": [{"column": "financial_status", "in": ["refunded", "voided"]}]},
    "phone_digits": 10, "windows_days": [3, 14], "group_windows": {"Festive sale": 13},
    "episode_gap_days": 14, "min_control": 20, "cost_per_message": 1.02, "margin_per_order": 300,
    "output_dir": "output",
}
(out / "config.json").write_text(json.dumps(cfg, indent=2))
truth = {"Festive sale": {"true_incremental_buyers_approx": round(truth_incr, 1),
                          "true_lift_pp_due_loyal_121_240d_3plus": 4.0},
         "Reorder reminder": "lift within 3 days, zero by 14 days (pull-forward)",
         "Cart recovery": "no effect",
         "bias": "capped recipients are less engaged, so capped-control estimates should read slightly high"}
(out / "truth.json").write_text(json.dumps(truth, indent=2))
print(f"wrote synthetic data to {out}: {len(sm):,} messages, {len(allo):,} orders")
print(json.dumps(truth, indent=2))
