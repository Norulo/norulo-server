# Restricted ledger reads

A valid API key can grant access to 100 project IDs. Expanding all of them in
one SQL statement exceeds D1's 100 bound-parameter limit once owner, cursor,
limit or optional filters are included. The previous implementation affected
project lists and their repository bindings, expense and recurring-rule lists,
all three reports, and both initial and continuation CSV queries. Even a
one-item public page could fail. An empty project grant with shared access off
also produced an impossible `INDEXED BY ... AND 0` CSV query.

`cloudflare_ledger_filters.py` divides the validated grant into disjoint groups
of at most 50 IDs. Each public read includes all groups in the same batch as
its existing credential, actor, owner and membership snapshot. A shared pool
appears in one group only. Empty grants still validate the authority snapshot.
No key restriction, role, input limit or financial record is changed.

Lists fetch a prefix of `limit + 1` from each group, merge by ID, and then apply
the global limit and cursor. Project bindings follow the same grant groups.
Reports preserve integer quotient/remainder aggregation and reconstruct exact,
separate per-currency totals across groups. CSV merges up to 250 ordered rows
per group by `(occurred_on, id)` and seeks every group after the global cursor
on each following page. Every page validates the original authority again;
revocation or membership changes fail before that page is returned.

The worst affected query now binds 59 scalar values, including every expense
filter and the continuation cursor. Scalar-IN accounting reserves unsuccessful
index probes as well as physical rows for SELECTs. Plain text and JSON envelopes
remain unchanged. No schema migration, new secret, client update or automatic
GitHub credential refresh is required.

## Verification

The dated native evidence records the pre-change SQLite and production D1
failures and the post-change local boundary matrix. Unit checks include global
pagination across grant groups, no duplicate shared totals, amounts above the
JavaScript safe aggregate boundary, CSV escaping and continuation, removed and
other-owner records, maximum-length grant IDs, current membership and key
scope/restriction/revocation changes.

Run the native D1 boundary check after installing the frozen Server and Worker
dependencies:

```sh
python scripts/check-ledger-read-native-runtime.py --output work/read-boundaries.json
```

It copies synthetic local fixtures into a fresh Miniflare/workerd D1, executes
the canonical CPython handlers through the real D1 JavaScript boundary, compares
complete responses and CSV money/order, and validates native metadata with the
unchanged product accounting journal. Fixture setup costs are recorded
separately from read requests. This check does not claim Python Worker HTTP/FFI
coverage; the existing GitHub native Worker harness provides that separate proof.

Production checks use authenticated read endpoints and finite SELECT-only D1
probes. No production fixture, API key, model request, provider rotation or
financial write is needed. A normal production connection without a long grant
does not establish HTTP acceptance for a 100-project restricted key; that
boundary remains covered by the local canonical-handler/native-D1 matrix.
