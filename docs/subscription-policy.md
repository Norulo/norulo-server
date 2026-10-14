# Subscription allowance decision, 2026-10-14

The user increased the existing Creem subscription prices and authorized the
allowance changes and production publication. The anonymous production catalog
confirmed all four prices before any application change.

| Plan | Monthly price | Annual price | Retained expenses | Projects | Jev calls |
| --- | --- | --- | --- | --- | --- |
| Free | $0 | — | 300 | 3 | 20 one-time trials |
| Pro | $4.99 | $49.99 | 20,000 | 20 | 1,089/month |
| Max | $12.99 | $129.99 | 200,000 | 100 | 4,358/month |

Prices are provider facts, not hardcoded application defaults. Existing product
bindings and signed-webhook entitlement controls remain authoritative. Catalog
GETs can refresh an expired verified provider-price cache; this release does not
create a checkout, charge an account, or edit a customer subscription.

## Expense capacity

Max doubles from 100,000 to 200,000 retained expenses, ten times Pro. Capacity
combines project, shared-pool and generated recurring expenses across the Owner's
ledger, including archived projects. The existing 10,000 writes/month limit for
both paid tiers stays in place. If all those writes create retained expenses,
200,000 places cover about 20 months of additions; this is a capacity illustration,
not measured user demand or a retention-time guarantee. Edits and other writes
also consume that shared write allowance.

This moderate increase supports longer history without multiplying request or
scheduler throughput. Projects stay at 3/20/100 because no usage evidence supports
a change. Increasing capacity needs no schema migration, record rewrite or usage
reset. Larger retained ledgers can increase aggregate-query reads and storage;
the release makes no performance SLA at the new boundary.

[Cloudflare's D1 pricing](https://developers.cloudflare.com/d1/platform/pricing/)
meters actual rows read/written and stored bytes, not the configured record cap.
Additional indexes also contribute written rows. Raising the cap does not itself
create 100,000 records, and the existing write-rate controls remain enforced.

## Jev allowance and cost

[TypeSafe's current model reference](https://docs.typesafe.ai/models), checked on
2026-10-14, lists pinned `jev-1.13.0` at $0.042 per million input tokens, with
free output and a 64k input context. This agrees with the application's existing
pricing constant. No paid inference was needed for this investigation.

The application reserves 2,753 micro-USD before each model dispatch, using the
conservative 65,536-token interpretation. It retains the reservation rather than
refunding it from an estimated response cost. Pro's unchanged $3 cap therefore
admits at most 1,089 fresh calls from an unused month; Max's $12 cap admits at most
4,358. Save assistance, automatic category selection and explicit review share
the Owner's allowance. These are reservation-based bounds, not promised successful
expenses or measurements of the provider's final bill.

The selected $12 matches the requested Max benefit and makes its model allowance
four times Pro. It has no cash value, does not roll over, and resets by UTC
calendar month even with annual billing. Existing reservations remain consumed
when the cap increases; monthly usage is not cleared.

At the stated prices, annual revenue averages about $4.17/month for Pro and
$10.83/month for Max before payment fees and other costs. If actual provider
spend ever matched the full $12 Max allowance, annual revenue would not cover it.
The conservative reservation usually exceeds actual short-request cost, but no
customer usage evidence establishes a gross margin here. Evaluate actual billed
provider cost alongside retained reservations during ordinary operation; the
allowance must not be described as a dollar payout or guaranteed provider spend.

## Verification scope

Local regression checks cover the final 200,000th record, denial of the next,
downgrade history preservation, the exact $12 monthly model boundary, Owner/member
authority, month reset, and monthly versus annual display of provider prices.
Production verification reads the deployed settings and public catalog. The only production database change is the additive 0015 lifetime counter migration; no
production fixture, manual scheduler invocation, email send,
paid inference or customer subscription mutation is needed.

## Count-based Jev update

Free receives 20 lifetime calls per Owner, shared by members and API keys. It may toggle Jev. One admitted model attempt consumes one call even on failure; unavailable/disabled paths do not reserve. Paid counts are floor(3000000/2753)=1089 and floor(12000000/2753)=4358 per UTC month. Internal legacy reservations are retained; nonmultiple historical usage rounds up for count projection and admission. A constrained v15 column in the existing atomic quota write persists Free use through months, upgrades/downgrades and project/expense deletion. Billing, pricing, settings, review and six locales display counts. Old USD contract fields remain deprecated compatibility metadata only.
