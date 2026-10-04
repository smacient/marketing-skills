"""Measure the incrementality of WhatsApp broadcasts and journeys.

Uses the natural control groups Meta creates inside every WhatsApp message log:
  * 131049 "healthy ecosystem engagement": Meta's per-user marketing cap. The person was on
    your list but never received the message. Usable control, not random (skews less engaged).
  * 130472 "part of an experiment": Meta's random holdout. Small but truly random.

For each campaign group it compares store orders (not platform attribution) of people who
received a message against people who were capped, inside recency x frequency strata, over
one or more outcome windows. It adds a placebo check (same comparison before any message),
a random-holdout check, message cost, cost per incremental order and a verdict.

Usage:
    python run_analysis.py config.json
Config: see references/config-template.json. Outputs an Excel workbook and a markdown report.
"""
from __future__ import annotations

import glob
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

R_BUCKETS = [(60, "R1 0-60d"), (120, "R2 61-120d"), (240, "R3 121-240d"), (365, "R4 241-365d"), (10**9, "R5 365d+")]
NEVER = "R0 never bought"


# ----------------------------------------------------------------------------- loading

def read_files(patterns, base: Path) -> pd.DataFrame:
    frames = []
    for pat in patterns:
        p = Path(pat)
        hits = sorted(glob.glob(str(p if p.is_absolute() else base / p)))
        if not hits:
            raise SystemExit(f"no files match {pat}")
        for f in hits:
            df = pd.read_excel(f, dtype=str) if f.lower().endswith((".xlsx", ".xls")) else pd.read_csv(f, dtype=str, keep_default_na=False)
            df["__file"] = Path(f).stem
            frames.append(df)
    return pd.concat(frames, ignore_index=True)


_ZERO_PM = re.compile(r"\b0:(\d{2}(?::\d{2})?)\s*([pP][mM])")


def parse_dt(s: pd.Series, dayfirst: bool, fmt: str | None) -> pd.Series:
    s = s.fillna("").astype(str).str.strip().replace({"": None, "nan": None, "NaT": None})
    # Some exporters write 12:47 pm as '0:47 pm'.
    s = s.map(lambda v: _ZERO_PM.sub(r"12:\1 \2", v) if isinstance(v, str) else v)
    if fmt:
        out = pd.to_datetime(s, format=fmt, errors="coerce")
    else:
        out = pd.to_datetime(s, errors="coerce", dayfirst=dayfirst, format="mixed")
    if getattr(out.dt, "tz", None) is not None:
        out = out.dt.tz_localize(None)
    return out


_HASHED = re.compile(r"^[0-9a-f]{24}$")


def norm_phone(s: pd.Series, digits: int) -> pd.Series:
    """Last N digits of a raw phone, or the code itself if pseudonymize.py already hashed it."""
    raw = s.fillna("").astype(str).str.strip()
    hashed = raw.str.match(_HASHED)
    d = raw.str.replace(r"\.0$", "", regex=True).str.replace(r"\D", "", regex=True)
    d = d.where(d.str.len() >= digits).str[-digits:]
    return raw.where(hashed, d).where(hashed | d.notna())


def load_messages(cfg, base):
    m = cfg["messages"]
    c = m["columns"]
    raw = read_files(m["files"], base)
    camp = raw["__file"] if m.get("campaign_from_filename") or not c.get("campaign") else raw[c["campaign"]]
    out = pd.DataFrame({
        "phone": norm_phone(raw[c["phone"]], cfg.get("phone_digits", 10)),
        "campaign": camp.astype(str).str.strip(),
        "sent_at": parse_dt(raw[c["sent_at"]], m.get("dayfirst", True), m.get("datetime_format")),
        "delivered_at": parse_dt(raw[c["delivered_at"]], m.get("dayfirst", True), m.get("datetime_format")) if c.get("delivered_at") else pd.NaT,
    })
    reason = raw[c["failure_reason"]].fillna("").astype(str) if c.get("failure_reason") else pd.Series("", index=raw.index)
    capped = "|".join(re.escape(p) for p in cfg.get("capped_patterns", ["131049", "healthy ecosystem"]))
    hold = "|".join(re.escape(p) for p in cfg.get("holdout_patterns", ["130472", "part of an experiment"]))
    out["capped"] = reason.str.contains(capped, case=False, regex=True)
    out["holdout"] = reason.str.contains(hold, case=False, regex=True)
    out["failed_other"] = out["delivered_at"].isna() & ~out["capped"] & ~out["holdout"] & reason.str.strip().ne("")
    if c.get("attributed_order_id"):
        a = raw[c["attributed_order_id"]].fillna("").astype(str).str.strip()
        out["attributed"] = a.ne("") & a.ne("nan")
    else:
        out["attributed"] = False
    out["attributed_value"] = pd.to_numeric(raw[c["attributed_order_value"]], errors="coerce").fillna(0) if c.get("attributed_order_value") else 0.0
    groups = cfg.get("campaign_groups") or {}
    rev = {camp_name: g for g, names in groups.items() for camp_name in names}
    out["group"] = out["campaign"].map(lambda x: rev.get(x, x))
    dq = {"message_rows": len(out), "message_rows_no_phone": int(out["phone"].isna().sum()),
          "message_rows_no_sent_at": int(out["sent_at"].isna().sum()),
          "failure_reason_column": bool(c.get("failure_reason")),
          "rows_capped_131049": int(out["capped"].sum()), "rows_holdout_130472": int(out["holdout"].sum())}
    return out.dropna(subset=["phone", "sent_at"]), dq


def load_orders(cfg, base):
    o = cfg["orders"]
    c = o["columns"]
    raw = read_files(o["files"], base)
    keep = pd.Series(True, index=raw.index)
    for rule in o.get("exclude_if", []):
        col = raw[rule["column"]].fillna("").astype(str).str.strip()
        if rule.get("not_empty"):
            keep &= col.eq("") | col.str.lower().isin(["nan", "none", "false", "0"])
        if "in" in rule:
            keep &= ~col.str.lower().isin([v.lower() for v in rule["in"]])
    raw = raw[keep]
    phone_cols = c["phones"] if isinstance(c["phones"], list) else [c["phones"]]
    base_df = pd.DataFrame({
        "order_id": raw[c["order_id"]].astype(str),
        "created_at": parse_dt(raw[c["created_at"]], o.get("dayfirst", False), o.get("datetime_format")),
        "value": pd.to_numeric(raw[c["order_value"]], errors="coerce").fillna(0) if c.get("order_value") else 0.0,
    })
    parts = [base_df.assign(phone=norm_phone(raw[pc], cfg.get("phone_digits", 10))) for pc in phone_cols]
    orders = pd.concat(parts).dropna(subset=["phone", "created_at"]).drop_duplicates(["order_id", "phone"])
    dq = {"order_rows_kept": int(keep.sum()), "order_rows_excluded": int((~keep).sum()),
          "orders_with_phone": int(orders["order_id"].nunique())}
    return orders, dq


# ----------------------------------------------------------------------------- episodes

def build_episodes(msgs: pd.DataFrame, cfg) -> pd.DataFrame:
    """One row per (group, phone, episode). A new episode starts when a send comes more than
    `episode_gap_days` after the previous send, so a multi-wave sale is one exposure per person."""
    gap_default = cfg.get("episode_gap_days", 14)
    gw = cfg.get("group_windows") or {}
    m = msgs.sort_values(["group", "phone", "sent_at"]).copy()
    gap_days = m["group"].map(lambda g: max(gap_default, gw.get(g, 0)))
    prev = m.groupby(["group", "phone"])["sent_at"].shift()
    new = prev.isna() | ((m["sent_at"] - prev).dt.total_seconds() > gap_days * 86400)
    m["ep"] = new.cumsum()
    m["dlv"] = m["delivered_at"].notna()
    ep = m.groupby("ep").agg(group=("group", "first"), phone=("phone", "first"), start=("sent_at", "min"),
                             sends=("sent_at", "size"), delivered_msgs=("dlv", "sum"),
                             capped_msgs=("capped", "sum"), any_hold=("holdout", "any"),
                             attributed_orders=("attributed", "sum"), attributed_value=("attributed_value", "sum"))
    ep["arm"] = np.select([ep["delivered_msgs"] > 0, ep["capped_msgs"] > 0, ep["any_hold"]], ["T", "C", "X"], "O")
    return ep.drop(columns="any_hold").reset_index(drop=True)


def attach_history_and_outcomes(ep: pd.DataFrame, orders: pd.DataFrame, windows: list[int]) -> pd.DataFrame:
    o = orders[["phone", "order_id", "created_at", "value"]].drop_duplicates(["phone", "order_id"])
    m = ep[["phone", "start"]].reset_index().merge(o, on="phone", how="left")
    before = m[m["created_at"] < m["start"]]
    hist = before.groupby("index").agg(prior_orders=("order_id", "nunique"), last_order=("created_at", "max"))
    ep = ep.join(hist)
    ep["prior_orders"] = ep["prior_orders"].fillna(0).astype(int)
    rec = (ep["start"] - ep["last_order"]).dt.days
    ep["r_bucket"] = np.where(ep["prior_orders"].eq(0), NEVER,
                              pd.cut(rec, [-1] + [b for b, _ in R_BUCKETS], labels=[l for _, l in R_BUCKETS]).astype(str))
    ep["f_bucket"] = np.select([ep["prior_orders"].eq(0), ep["prior_orders"].eq(1), ep["prior_orders"].eq(2)],
                               ["F0", "F1", "F2"], "F3+")
    for w in windows:
        span = pd.Timedelta(days=w)
        post = m[(m["created_at"] >= m["start"]) & (m["created_at"] < m["start"] + span)]
        pre = m[(m["created_at"] < m["start"]) & (m["created_at"] >= m["start"] - span)]
        a = post.groupby("index").agg(o=("order_id", "nunique"), v=("value", "sum"))
        b = pre.groupby("index").agg(o=("order_id", "nunique"))
        ep[f"orders_{w}"] = a["o"].reindex(ep.index).fillna(0)
        ep[f"value_{w}"] = a["v"].reindex(ep.index).fillna(0)
        ep[f"pre_orders_{w}"] = b["o"].reindex(ep.index).fillna(0)
    return ep


# ----------------------------------------------------------------------------- lift

def stratified_lift(d: pd.DataFrame, ycol: str, vcol: str | None, min_ctrl: int, ctrl: str = "C"):
    """Incremental buyers / orders / value of arm T vs a control arm, summed over strata.
    Buyer CI uses the stratified binomial variance."""
    d = d[d["arm"].isin(["T", ctrl])].copy()
    d["buyer"] = (d[ycol] > 0).astype(float)
    g = d.groupby(["r_bucket", "f_bucket", "arm"]).agg(n=("buyer", "size"), b=("buyer", "sum"),
                                                     o=(ycol, "sum"), v=(vcol, "sum") if vcol else (ycol, "size"))
    g = g.unstack("arm")
    res = {"nT": 0, "nT_covered": 0, "nC": 0, "incr_buyers": 0.0, "incr_orders": 0.0, "incr_value": 0.0, "var": 0.0,
           "bT": 0.0, "bC_scaled": 0.0}
    rows = []
    for idx, r in g.iterrows():
        nT, nC = r.get(("n", "T"), 0) or 0, r.get(("n", ctrl), 0) or 0
        nT, nC = (0 if pd.isna(nT) else nT), (0 if pd.isna(nC) else nC)
        res["nT"] += nT
        res["nC"] += nC
        if nT == 0 or nC < min_ctrl:
            continue
        pT, pC = r[("b", "T")] / nT, r[("b", ctrl)] / nC
        oT, oC = r[("o", "T")] / nT, r[("o", ctrl)] / nC
        vT, vC = (r[("v", "T")] / nT, r[("v", ctrl)] / nC) if vcol else (0, 0)
        res["nT_covered"] += nT
        res["incr_buyers"] += nT * (pT - pC)
        res["incr_orders"] += nT * (oT - oC)
        res["incr_value"] += nT * (vT - vC)
        res["var"] += nT ** 2 * (pT * (1 - pT) / nT + pC * (1 - pC) / nC)
        res["bT"] += nT * pT
        res["bC_scaled"] += nT * pC
        rows.append({"r_bucket": idx[0], "f_bucket": idx[1], "nT": int(nT), "nC": int(nC),
                     "conv_T_pct": 100 * pT, "conv_C_pct": 100 * pC, "lift_pp": 100 * (pT - pC),
                     "ci95_pp": 196 * math.sqrt(pT * (1 - pT) / nT + pC * (1 - pC) / nC),
                     "incr_buyers": nT * (pT - pC), "incr_orders": nT * (oT - oC), "incr_value": nT * (vT - vC)})
    res["ci95_buyers"] = 1.96 * math.sqrt(res["var"])
    return res, pd.DataFrame(rows)


def random_holdout_lift(d: pd.DataFrame, ycol: str):
    """Intention-to-treat against Meta's random holdout (130472).

    The holdout is random across everyone on the list, so it must be compared with everyone
    else on the list (delivered AND capped), not with delivered only: delivered people are the
    ones Meta did not cap, i.e. the more engaged. ITT lift x list size = incremental buyers from
    sending the campaign, with no stratification needed and no engagement bias."""
    lst, x = d[d["arm"].isin(["T", "C"])], d[d["arm"] == "X"]
    if len(x) == 0 or len(lst) == 0:
        return {"nX": len(x), "buyers_X": 0, "incr_buyers_vs_random": None, "ci95": None}
    pL, pX = (lst[ycol] > 0).mean(), (x[ycol] > 0).mean()
    se = math.sqrt(pL * (1 - pL) / len(lst) + pX * (1 - pX) / len(x))
    return {"nX": len(x), "buyers_X": int((x[ycol] > 0).sum()), "incr_buyers_vs_random": len(lst) * (pL - pX),
            "ci95": 1.96 * se * len(lst)}


def verdict(r, margin, pull_forward, placebo_flag, cov_share, nC):
    if nC < 100 or cov_share < 0.5:
        return "NOT MEASURABLE FROM HISTORY", "Too few capped/holdout recipients to compare. Start a 10% random holdout (holdout_split.py)."
    if pull_forward:
        return "RETIME OR STOP", "Clear lift in the first days that is gone by the longer window: it moves orders earlier, it does not create them."
    point, ci = r["incr_buyers"], r["ci95_buyers"]
    if point <= 0 or (point - ci <= 0 and point < 0.5 * ci):
        return "STOP OR FIX", "No measurable extra orders: these people buy at about the same rate without the message."
    if point - ci <= 0:
        return "TEST WITH HOLDOUT", "Positive but within noise. Keep sending with a 10-20% holdout to confirm."
    if margin is not None and r["contribution_after_cost"] is not None and r["contribution_after_cost"] < 0:
        return "FIX (COSTS MORE THAN IT EARNS)", "Real lift, but message cost exceeds the margin on the extra orders. Narrow the audience."
    note = "Clear lift."
    if placebo_flag:
        note += " Placebo gap is large: groups differed before the message, treat with caution."
    return "KEEP", note


# ----------------------------------------------------------------------------- main

def main(cfg_path: str) -> int:
    cfg_file = Path(cfg_path).resolve()
    cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    base = cfg_file.parent
    windows = sorted(set(cfg.get("windows_days", [3, 7, 14])))
    gw = cfg.get("group_windows") or {}
    min_ctrl = cfg.get("min_control", 20)
    cost = cfg.get("cost_per_message")
    margin = cfg.get("margin_per_order")
    out_dir = Path(cfg.get("output_dir", "incrementality_output"))
    out_dir = out_dir if out_dir.is_absolute() else base / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    msgs, dq_m = load_messages(cfg, base)
    orders, dq_o = load_orders(cfg, base)
    all_w = sorted(set(windows) | set(gw.values()))
    ep = build_episodes(msgs, cfg)
    ep = attach_history_and_outcomes(ep, orders, all_w)
    matched = ep["phone"].isin(set(orders["phone"])).mean()

    summary, by_window, segments, checks, delivery = [], [], [], [], []
    for g, d in ep.groupby("group"):
        wins = sorted({w for w in windows if g not in gw or w < gw[g]} | ({gw[g]} if g in gw else set()))
        primary = gw.get(g, max(windows))
        arms = d["arm"].value_counts()
        nT, nC, nX = int(arms.get("T", 0)), int(arms.get("C", 0)), int(arms.get("X", 0))
        delivered_msgs = int(d["delivered_msgs"].sum())
        msg_cost = delivered_msgs * cost if cost is not None else None
        res_by_w = {}
        for w in wins:
            r, strata = stratified_lift(d, f"orders_{w}", f"value_{w}", min_ctrl)
            pl, _ = stratified_lift(d, f"pre_orders_{w}", None, min_ctrl)
            res_by_w[w] = r
            by_window.append({"campaign_group": g, "window_days": w, "messaged": nT, "capped": nC,
                              "incr_buyers": r["incr_buyers"], "ci95_buyers": r["ci95_buyers"],
                              "incr_orders": r["incr_orders"], "incr_value": r["incr_value"],
                              "placebo_incr_buyers": pl["incr_buyers"], "placebo_ci95": pl["ci95_buyers"],
                              "share_of_messaged_covered": r["nT_covered"] / nT if nT else 0})
            if w == primary:
                rnd = random_holdout_lift(d, f"orders_{w}")
                checks.append({"campaign_group": g, "window_days": w,
                               "placebo_incr_buyers": pl["incr_buyers"], "placebo_ci95": pl["ci95_buyers"],
                               "incr_buyers_vs_capped": r["incr_buyers"], "random_holdout_n": rnd["nX"],
                               "random_holdout_buyers": rnd["buyers_X"],
                               "incr_buyers_vs_random": rnd["incr_buyers_vs_random"], "random_ci95": rnd["ci95"]})
                if not strata.empty:
                    seg = strata.copy()
                    seg.insert(0, "campaign_group", g)
                    seg.insert(1, "window_days", w)
                    segments.append(seg)
                placebo_flag = (abs(pl["incr_buyers"]) > pl["ci95_buyers"]) and (abs(pl["incr_buyers"]) > 0.5 * abs(r["incr_buyers"]))
        r = res_by_w[primary]
        short = res_by_w[min(wins)]
        pull = (min(wins) < primary and short["incr_buyers"] > 0
                and r["incr_buyers"] < 0.5 * short["incr_buyers"] and short["incr_buyers"] - short["ci95_buyers"] > 0)
        r["contribution_after_cost"] = (r["incr_orders"] * margin - (msg_cost or 0)) if margin is not None else None
        cov = r["nT_covered"] / nT if nT else 0
        v, why = verdict(r, margin, pull, placebo_flag, cov, nC + nX)
        attr = int(d["attributed_orders"].sum())
        summary.append({"campaign_group": g, "verdict": v, "why": why, "primary_window_days": primary,
                        "people_messaged": nT, "people_capped": nC, "people_random_holdout": nX,
                        "platform_attributed_orders": attr if attr else None,
                        "incremental_orders": round(r["incr_orders"], 1),
                        "incremental_buyers": round(r["incr_buyers"], 1), "ci95_buyers": round(r["ci95_buyers"], 1),
                        "incremental_share_of_attributed": round(r["incr_orders"] / attr, 3) if attr else None,
                        "incremental_value": round(r["incr_value"]),
                        "delivered_messages": delivered_msgs, "message_cost": round(msg_cost) if msg_cost is not None else None,
                        "cost_per_incremental_order": round(msg_cost / r["incr_orders"]) if msg_cost and r["incr_orders"] > 0 else None,
                        "contribution_after_cost": round(r["contribution_after_cost"]) if r["contribution_after_cost"] is not None else None,
                        "share_of_messaged_with_control": round(cov, 3)})
        dd = d.assign(day=d["start"].dt.date)
        for day, x in dd.groupby("day"):
            s = x["sends"].sum()
            delivery.append({"campaign_group": g, "first_send_day": day, "people": len(x),
                             "capped_people_pct": round(100 * (x["arm"] == "C").mean(), 1), "messages": int(s)})

    S = pd.DataFrame(summary).sort_values("incremental_orders", ascending=False)
    W, C, D = pd.DataFrame(by_window), pd.DataFrame(checks), pd.DataFrame(delivery)
    G = pd.concat(segments) if segments else pd.DataFrame()
    dq = {**dq_m, **dq_o, "episodes": len(ep), "share_of_messaged_people_found_in_orders": round(float(matched), 3)}
    DQ = pd.DataFrame(list(dq.items()), columns=["check", "value"])

    xlsx = out_dir / "whatsapp_incrementality.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        S.to_excel(xw, sheet_name="Summary", index=False)
        W.round(2).to_excel(xw, sheet_name="Lift_by_window", index=False)
        if not G.empty:
            G.round(2).to_excel(xw, sheet_name="Segments", index=False)
        C.round(2).to_excel(xw, sheet_name="Checks", index=False)
        D.to_excel(xw, sheet_name="Delivery_and_caps", index=False)
        DQ.to_excel(xw, sheet_name="Data_quality", index=False)
        pd.DataFrame({"note": METHOD_NOTES}).to_excel(xw, sheet_name="Method", index=False)
        for ws in xw.book.worksheets:
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = min(60, max(12, max(len(str(c.value or "")) for c in col[:50]) + 2))
    (out_dir / "whatsapp_incrementality_report.md").write_text(render_md(S, W, C, G, dq), encoding="utf-8")
    print(S[["campaign_group", "verdict", "people_messaged", "people_capped", "incremental_orders",
             "ci95_buyers", "platform_attributed_orders", "cost_per_incremental_order"]].to_string(index=False))
    print(f"\nwritten: {xlsx}\n         {out_dir / 'whatsapp_incrementality_report.md'}")
    return 0


METHOD_NOTES = [
    "Unit: one person per campaign group per episode (sends within the episode gap count as one exposure).",
    "Arms: T = at least one message delivered; C = never delivered, capped by Meta (131049); X = never delivered, Meta random holdout (130472). Other failures are excluded.",
    "Outcome: any store order matched on phone within N days of the episode's first send. Platform attribution is not used for lift.",
    "Strata: recency since last order before the send (never, 0-60, 61-120, 121-240, 241-365, 365+ days) x prior orders (0, 1, 2, 3+). Strata with fewer than min_control capped people are skipped; coverage shows how much of the messaged group was measured.",
    "Incremental = sum over strata of messaged n x (messaged rate - capped rate). 95% CI on buyers from the stratified binomial variance.",
    "Placebo: the same comparison on the N days before the send. A gap far from zero means the groups differed before any message.",
    "Random-holdout check: everyone on the list (delivered + capped) vs the 130472 group, scaled to list size (intention to treat). Valid without stratification because the holdout is random; usually wide because the holdout is small.",
    "Bias: Meta caps less engaged users more, so the capped comparison can overstate lift. Agreement with the random holdout is the check.",
    "Pull-forward: if lift at the shortest window is clear but falls below half by the primary window, the message moves orders earlier rather than creating them.",
    "Contamination: a capped person may still receive other campaigns in the window, which biases lift toward zero.",
]


def _fmt(x, nd=0):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    return f"{x:,.{nd}f}" if isinstance(x, (int, float, np.floating, np.integer)) else str(x)


def render_md(S, W, C, G, dq):
    L = ["# WhatsApp incrementality report", "",
         "Incremental = orders that would not have happened without the message, measured against people Meta "
         "blocked from receiving it (131049) inside the same list, matched on recency and order history.", "",
         "## Verdicts", "",
         "| Campaign | Verdict | Messaged | Capped | Incremental orders | 95% CI (buyers) | Platform-attributed | Cost per incremental order |",
         "|---|---|---|---|---|---|---|---|"]
    for r in S.itertuples():
        L.append(f"| {r.campaign_group} | {r.verdict} | {_fmt(r.people_messaged)} | {_fmt(r.people_capped)} | "
                 f"{_fmt(r.incremental_orders, 1)} | +/-{_fmt(r.ci95_buyers, 1)} | {_fmt(r.platform_attributed_orders)} | "
                 f"{_fmt(r.cost_per_incremental_order)} |")
    L += ["", "Why:", ""] + [f"- **{r.campaign_group}**: {r.why}" for r in S.itertuples()]
    L += ["", "## Lift by window", "", "| Campaign | Window (days) | Incremental buyers | 95% CI | Placebo |", "|---|---|---|---|---|"]
    for r in W.itertuples():
        L.append(f"| {r.campaign_group} | {r.window_days} | {_fmt(r.incr_buyers, 1)} | +/-{_fmt(r.ci95_buyers, 1)} | {_fmt(r.placebo_incr_buyers, 1)} |")
    L += ["", "## Random-holdout check", "", "| Campaign | Incremental buyers vs capped | vs random holdout (95% CI) | Random holdout size |", "|---|---|---|---|"]
    for r in C.itertuples():
        L.append(f"| {r.campaign_group} | {_fmt(r.incr_buyers_vs_capped, 1)} | {_fmt(r.incr_buyers_vs_random, 1)} (+/-{_fmt(r.random_ci95, 1)}) | {_fmt(r.random_holdout_n)} |")
    if not G.empty:
        top = G.sort_values("lift_pp", ascending=False).head(10)
        L += ["", "## Segments with the highest lift", "", "| Campaign | Recency | Orders | Messaged conv % | Capped conv % | Lift pp |", "|---|---|---|---|---|---|"]
        for r in top.itertuples():
            L.append(f"| {r.campaign_group} | {r.r_bucket} | {r.f_bucket} | {r.conv_T_pct:.2f} | {r.conv_C_pct:.2f} | {r.lift_pp:+.2f} |")
    L += ["", "## Data quality", ""] + [f"- {k}: {v}" for k, v in dq.items()]
    L += ["", "## Method and caveats", ""] + [f"- {n}" for n in METHOD_NOTES]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(1)
    raise SystemExit(main(sys.argv[1]))
