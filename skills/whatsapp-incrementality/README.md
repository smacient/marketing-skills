# /whatsapp-incrementality

Measures how many orders your WhatsApp broadcasts and journeys caused, and sets that against what the platform dashboard credits them with.

Most WhatsApp platforms and UTMs count any order placed within a few days of a message being read or clicked. That includes everyone who was going to buy anyway. This skill uses two control groups Meta already creates inside every WhatsApp message log:

- **131049, per-user marketing cap**: people on your list who never received the message because Meta capped them.
- **130472, random experiment holdout**: people Meta randomly held out.

It compares their store orders with the orders of people who did receive the message, within the same recency and order-history segments.

No API or MCP connector required. Everything runs locally on two CSV exports, and no phone numbers are sent anywhere.

A plain-language version of the method, for teams that want to do it by hand, is in [`guide/`](guide/).

---

## What you get

- A verdict per campaign or journey:
  - **KEEP**: clear lift that pays for itself.
  - **TEST WITH HOLDOUT**: positive but within noise.
  - **RETIME OR STOP**: the message only moves orders a few days earlier.
  - **STOP OR FIX**: no measurable lift.
  - **NOT MEASURABLE FROM HISTORY**: the export has no control group.
- Platform-attributed vs incremental orders, cost per incremental order, and contribution after message cost.
- Lift by customer segment (recency x order count), so you can see which customers the messages move.
- Checks:
  - A placebo period, run before any message was sent.
  - The random-holdout estimate, to compare with the capped estimate.
  - Cap rate by send day.
- An Excel workbook and a markdown report.

## Prerequisites

1. Python 3.10+ in a venv: `pip install -r requirements.txt`
2. **Message log export** from your WhatsApp platform (BiteSpeed, Interakt, Wati, AiSensy, Gallabox, Limechat or any other built on Meta's API). One row per message, with:
   - recipient phone
   - campaign or journey name (or one file per campaign)
   - sent time
   - delivered time
   - **failure reason**: check that your export includes it. Without it, past sends cannot be measured and the skill helps you set up a holdout instead.
3. **Orders export** from Shopify, WooCommerce or similar: order id, created time, value, phone columns, and cancelled or refunded status.

## Usage

```
/whatsapp-incrementality
```

Then point Claude at the two exports. It profiles them, proposes a column mapping for you to confirm, asks which campaigns belong together and what a message costs, then runs.

Manual invocation:

```bash
python scripts/profile_inputs.py --messages "exports/messages/*.csv" --orders "exports/orders.csv" --out work
python scripts/run_analysis.py work/config.json
python scripts/holdout_split.py next_send_list.csv --phone-col "Phone" --pct 10 --salt "festive-2026"
```

Test it on synthetic data with known answers:

```bash
python scripts/make_synthetic.py demo
python scripts/run_analysis.py demo/config.json
```

## Files

```
whatsapp-incrementality/
├── SKILL.md
├── requirements.txt
├── scripts/
│   ├── profile_inputs.py   column discovery + draft config
│   ├── run_analysis.py     the analysis, workbook and report
│   ├── holdout_split.py    reproducible send / holdout split for future campaigns
│   └── make_synthetic.py   test data with known true effects
├── references/
│   ├── methodology.md      estimators, checks and which way the bias runs
│   └── config-template.json
└── guide/                  step-by-step guide (markdown + PDF)
```

## Caveats

- **The capped group is not random.** Meta caps less-engaged users more, so this comparison tends to overstate lift. The random-holdout check is unbiased but small. The report shows both.
- **Matching is by phone.** Orders placed under another number are missed on both sides.
- **For decisions that matter, confirm with a planned random holdout.** The skill sets one up for you.
