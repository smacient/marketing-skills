---
name: whatsapp-incrementality
description: Measure the true incrementality of WhatsApp marketing (broadcasts, sale blasts, abandoned-cart, reorder/replenishment and win-back journeys) from a WhatsApp platform's message export plus a store orders export. Uses Meta's own failure codes as natural control groups (131049 per-user marketing cap, 130472 random experiment holdout) to estimate how many orders would NOT have happened without the message, versus what the platform dashboard or UTMs attribute. Works with exports from any WhatsApp platform built on Meta's API (e.g. BiteSpeed, Interakt, Wati, AiSensy, Gallabox, Limechat) and Shopify or WooCommerce orders. Use when someone asks whether their WhatsApp journeys or broadcasts actually work, wants to check WhatsApp attribution or incrementality, asks "how many of these orders would have happened anyway", wants to know which customer segments to message, or wants to set up a WhatsApp holdout test.
---

# WhatsApp Incrementality

Platform dashboards and UTMs count orders that happened after a message. This skill counts the
orders the message caused, using control groups Meta already created inside the message log. Everything runs locally on the user's CSVs.

## Requirements

Python 3.10+ with `pandas`, `numpy`, `openpyxl` (`pip install -r requirements.txt`, inside a venv).

Two exports from the user:

1. **Message log** (one row per message per recipient) from the WhatsApp platform. Needed:
   recipient phone, campaign or journey name (or one file per campaign), sent time, delivered
   time (blank if not delivered), and the **failure reason**. Optional: read, clicked,
   platform-attributed order id and value.
2. **Orders** from the store (Shopify: Orders export): order id, created time, value, any phone
   columns (customer, shipping, billing), and status columns for excluding cancelled/refunded.

## Privacy rules (non-negotiable)

- Work only on local files. Never upload exports anywhere.
- Never print, quote or paste phone numbers into the conversation or any report. Report
  aggregates only.

## Workflow

### 1. Profile and map columns

```bash
python scripts/profile_inputs.py --messages "<message export(s)>" --orders "<orders export(s)>" --out <work folder>
```

It lists every column with samples, guesses the mapping, checks whether Meta failure codes
are present and writes a draft `config.json`. **Show the user the proposed mapping and confirm it
before running.** Check in particular:

- **Date formats**: set `dayfirst` true for DD/MM exports (common in India), false for Shopify ISO.
- **Phone columns**: list every phone column in the orders file under `orders.columns.phones`; the
  last 10 digits are matched (`phone_digits`).
- **Exclusions**: `orders.exclude_if` should drop cancelled, voided, refunded and test orders.
- **No campaign column**: set `campaign_from_filename: true` when each file is one campaign.

### 2. Gate: can history be measured?

If the profiler finds **neither 131049 nor 130472**, the export has no natural control. Say so
plainly: past sends cannot be measured this way. Skip to step 6 (set up a holdout) and stop. Do
not estimate incrementality without a control group.

### 3. Ask the questions the analysis needs

Ask only what the data cannot tell you:

- Which campaigns belong together (e.g. launch + reminder + last-day waves of one sale) ->
  `campaign_groups`.
- For sale broadcasts, the outcome window: sale length plus about 2 days -> `group_windows`.
  Journeys use `windows_days` (default 3, 7, 14) so pull-forward shows up.
- Cost per delivered marketing message (India marketing is roughly Rs 0.86 + GST; ask for their
  rate card) -> `cost_per_message`.
- Optional: contribution per order after product cost, logistics and discount ->
  `margin_per_order`. Without it, verdicts use lift only and report cost per incremental order.

### 4. Run

```bash
python scripts/run_analysis.py <work folder>/config.json
```

Writes `whatsapp_incrementality.xlsx` (Summary, Lift_by_window, Segments, Checks,
Delivery_and_caps, Data_quality, Method) and `whatsapp_incrementality_report.md`.

### 5. Check before reporting

Read the Data_quality and Checks tabs first:

| Check | Healthy | If not |
|---|---|---|
| share_of_messaged_people_found_in_orders | above ~50% for buyer lists | phone columns or digits are wrong; fix mapping and rerun |
| share_of_messaged_with_control | above 50% | too few capped people in key segments; treat as indicative |
| Placebo (pre-period lift) | near zero, inside its CI | groups differed before the message; say so prominently |
| Random-holdout estimate | same direction and range as capped estimate | the capped estimate may be inflated by engagement bias; lean on the lower figure |

Known bias: Meta caps less-engaged users more, so the capped comparison tends to **overstate**
lift. The random holdout is unbiased but small and noisy. Report both and say which way the
bias runs. See `references/methodology.md`.

### 6. Report to the user

Lead with the verdict table, then:

- Platform-attributed vs incremental orders per campaign (the headline gap).
- Which segments respond (the Segments tab: recency x order count). Report what this brand's data
  shows; do not assume a pattern seen at other brands.
- Journeys flagged RETIME OR STOP for pull-forward: lift that is gone by day 14 moved orders earlier.
- Cost per incremental order against their margin.
- Concrete actions: who to keep messaging, who to drop, what to retime, and a holdout plan.

Verdicts: KEEP, TEST WITH HOLDOUT, RETIME OR STOP, STOP OR FIX, FIX (COSTS MORE THAN IT EARNS),
NOT MEASURABLE FROM HISTORY.

### 7. Set up holdouts going forward

```bash
python scripts/holdout_split.py <send list.csv> --phone-col "<column>" --pct 10 --salt "<campaign-name>"
```

Writes `_SEND.csv` and `_HOLDOUT_do_not_message.csv`. Same salt = same split, so the read-out is
reproducible. Recommend 10% for journeys and broadcasts, 20% for segments whose lift is unproven.

## Testing the skill

`python scripts/make_synthetic.py <folder>` builds a dataset with known effects (a sale with
segment-specific lift, a pull-forward reorder journey, a no-effect cart journey, and an
engagement-biased cap). Run the pipeline on it and compare against `truth.json`.

## Limits to state in every report

- Lift is measured on store orders matched by phone. Orders placed under another number are missed on both sides.
- Capped people may still receive other campaigns in the window, which pulls lift toward zero.
- Short windows on the last wave of a multi-wave sale understate that wave.
- This measures messages actually sent. It says nothing about segments never messaged.
