---
name: norulo-reports
description: Analyze Norulo project spending, shared costs, category breakdowns, trends, recurring rules, and expense exports. Use for cost analysis, spending summaries, monthly reports, or comparing project costs.
---

# Read Norulo costs

Start with connection_status. If unconnected, follow ../norulo-connect/SKILL.md. Use live Norulo tools as the evidence. Do not fabricate amounts, return mock data as real, or treat missing authorization as zero spending.

Resolve the requested project or shared target, date range, and currency. Use the user's local timezone for relative dates; state the exact date range. Inspect tool date-boundary semantics before choosing from/to and use consistent filters across comparisons. Resolve project IDs with listLedgerProjects and follow pagination when necessary.

Choose the smallest set of reads that answers the question:

- getLedgerSummary for totals and summary metrics.
- getLedgerCategoriesReport for category breakdowns.
- getLedgerTimeseries for daily or monthly trends.
- listExpenses and getExpense for supporting line items; follow cursor pagination when completeness matters.
- listRecurringExpenseRules for rule inventory; do not equate scheduled amounts with expenses already recorded.
- listLedgerActivity for a requested project or shared-target change history.
- exportExpenses for a requested export, using the actual returned file/link behavior.

Use server totals where supplied; a partial list page is not a ledger total. Do not combine amounts in different currencies or imply an exchange rate. Show each currency separately. Do not add shared costs to a project or allocate them without an explicit allocation method. For percentages and changes, compare the same population, filters, currencies, and comparable periods. When the baseline is zero, report the absolute change rather than an infinite or invented percentage.

Lead with the result, followed by the date range and scope. Include only the supporting breakdown needed, with record identifiers or links actually returned by Norulo. Separate recorded expenses, future recurring estimates, and hypotheses about causes. Missing records, permission failures, and incomplete pagination must be stated when they limit the answer. Generating a report must not modify, review, recategorize, or remove ledger records.
