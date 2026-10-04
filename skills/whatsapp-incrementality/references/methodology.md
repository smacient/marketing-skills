# Methodology

## The question

Attribution answers "which orders came after a message". Incrementality answers "which orders
would not have happened without it". Platforms report the first, typically any order within 72
hours of a read or click. That includes everyone who was going to buy anyway.

## Natural control groups in a WhatsApp log

Every message sent through Meta's WhatsApp Business API that fails returns a Meta error code.
Two codes create control groups for free:

| Code | Meta's text | What it means | Control quality |
|---|---|---|---|
| 131049 | "This message was not delivered to maintain healthy ecosystem engagement." | Meta caps marketing messages per user across all businesses | Large, same list and send time, **not random**: Meta caps less-engaged users more |
| 130472 | "User's number is part of an experiment." | Meta randomly holds some users out of marketing messages | **Random**, but small (low single-digit % of a list) |

People who failed for other reasons (invalid number, opted out, blocked) are excluded.

## Unit, arms and outcome

- **Unit**: a person within a campaign group within an episode. Sends to the same person within
  the episode gap (default 14 days, at least the sale window) count as one exposure.
- **Arms**: T delivered at least once; C never delivered, capped at least once; X never
  delivered, only the random holdout code.
- **Outcome**: any store order on the person's phone within N days of the first send. Platform
  attribution is not used.

## Estimators

**Capped comparison (primary, stratified).** People are split into strata by recency (days since
last order before the send: never, 0-60, 61-120, 121-240, 241-365, 365+) and prior order count
(0, 1, 2, 3+). Within each stratum:

    incremental = messaged n x (messaged conversion - capped conversion)

summed over strata with at least `min_control` capped people. The 95% interval on buyers uses
the stratified binomial variance. `share_of_messaged_with_control` shows how much of the messaged
group was measured.

**Random holdout (check, intention-to-treat).** Because the holdout is random across the whole
list, it is compared with everyone else on the list, delivered and capped together:

    incremental = list size x (list conversion - holdout conversion)

Comparing it with delivered-only would reintroduce the engagement bias, since delivered people
are by definition the ones Meta did not cap.

**Placebo.** The capped comparison repeated on the N days before the send. It should be near zero.

**Pull-forward.** If lift is clearly positive at the shortest window but below half of that by
the primary window, the message moved orders earlier rather than creating them.

## Which way the bias runs

Capped users are less engaged and buy less, so a capped control has a lower baseline than the
messaged group would have had without messages. The capped comparison therefore **overstates**
lift. In the synthetic test (5 seeds, cap strongly tied to engagement) the capped estimate
averaged ~45% above truth while the random-holdout estimate averaged within ~12% of truth with
wide intervals. In real data the cap/engagement link is weaker; the gap between the two
estimates is the best available read on how much it matters for a given brand.

## Reading the result

- Report platform-attributed vs incremental side by side.
- Prefer conclusions that hold on both estimators.
- Segment results drive targeting: message the strata with clear lift, drop the ones without.
- For anything material, confirm with a planned random holdout (`holdout_split.py`).
