# Is WhatsApp really bringing you sales?

*A simple guide to finding out, no data team needed*

## The problem

Your WhatsApp tool tells you how many orders came from your messages. But it counts anyone who ordered after reading a message, including people who were going to buy anyway.

What you want to know is how many of those orders happened only because you sent the message.

When we checked this for one D2C brand:

- The WhatsApp tool credited a sale campaign with 453 orders. About 256 happened because of the messages.
- Messages to people who had never bought brought in zero extra orders.
- A "time to reorder" reminder got people to order a few days sooner, but no extra orders overall.
- Loyal customers who hadn't ordered in 4 to 8 months responded the most. Recent buyers ordered the same with or without a message.

## The simple idea

Compare two groups of similar customers:

- **Group A** got your message
- **Group B** did not

If Group A orders more, the difference is what your message earned.

You may already have a Group B. WhatsApp limits how many brand messages a person can receive in a day, so on every campaign some of your customers never get your message. In your message report, these show up as "failed", with a reason like *"not delivered to maintain healthy ecosystem engagement"*. Those people are your Group B.

If your report doesn't show the failure reason, skip to **Option 3**.

## Option 1: Let Claude do it (easiest, about an hour)

1. **Download two reports.**
   - From your WhatsApp tool: the message report for the campaign or journey you want to check.
   - From Shopify (or your store): an orders export for the same period plus two weeks.
2. **Open Claude** with the free `whatsapp-incrementality` skill installed.
3. **Tell Claude** where the two files are and say: *"Check if this WhatsApp campaign actually brought in extra sales."*
4. **Answer a few questions.** Claude will ask which campaign is which and what a message costs you (about Rs 1 in India).
5. **Read the verdict.** For each campaign you get: orders the tool claimed, orders the messages caused, and **Keep, Fix or Stop**.

Everything runs on your own computer. Your customer data stays with you.

## Option 2: Do it in Google Sheets (about half a day)

Take one sale campaign to start.

**Step 1. Put both reports in one sheet**, on two tabs: *Messages* and *Orders*.

**Step 2. Make phone numbers match.** WhatsApp might show 919876543210 while Shopify shows +91 98765 43210. Add a column on both tabs that keeps only the last 10 digits.

**Step 3. Sort people into two groups** on the Messages tab:

- **Got it**: the message was delivered.
- **Didn't get it**: the message failed with the *"healthy ecosystem"* reason.
- Ignore every other kind of failure, such as wrong numbers or people not on WhatsApp.

**Step 4. Mark who ordered.** For each person, check the Orders tab: did they place an order between the day the message went out and two days after the sale ended? Mark Yes or No.

**Step 5. Compare the two groups.**

| | People | Ordered | % who ordered |
|---|---|---|---|
| Got it | 10,000 | 300 | 3.0% |
| Didn't get it | 2,000 | 40 | 2.0% |

The message added 1 percentage point. So out of the 10,000 who got it, about **100 orders** came from the message. The other 200 would have happened anyway.

**Step 6. Repeat for each type of customer.** Do steps 4 and 5 separately for:

- people who bought in the last 4 months
- people who last bought 4 to 12 months ago
- people who last bought over a year ago
- people who have never bought

You will usually find one or two groups that respond strongly, and others that don't move at all.

**Step 7. Decide.**

| What you see | What to do |
|---|---|
| Clear extra orders, and a message costs less than an order earns you | **Keep** sending to this group |
| Small difference, hard to tell | **Test** again with Option 3 |
| No difference | **Stop** messaging this group, or change the offer |
| Extra orders in the first 2-3 days, gone by 2 weeks | **Retime it**: people ordered sooner, not more |

## Option 3: Start fresh with your next campaign (simplest of all)

Before your next broadcast or journey goes out:

1. Take your send list.
2. Randomly set aside **1 in every 10 people**. Don't message them.
3. After the campaign, compare how many people ordered in each group, as in Step 5.

It's the cleanest test you can run. Do it on every campaign and you'll know what WhatsApp is earning.

## Five mistakes to avoid

1. **Trusting the dashboard number.** "Orders after a message" are not "orders because of a message".
2. **Comparing your message list with everyone else.** Your list is your best customers. Of course they buy more.
3. **Counting order confirmation messages as sales.** Those people had already bought.
4. **Checking only the first 3 days.** A reminder that makes people order sooner looks great on day 3 and does nothing by day 14.
5. **Sending your biggest blast on the busiest day.** On crowded sale days, WhatsApp blocks more messages. In our case 43% were blocked on a sale's last day, against 14% on its first.

*Want the shortcut? Comment on the post and I'll send you the free Claude skill that does all of this for you.*
