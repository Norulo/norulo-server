# Status monitoring ownership

The Web Worker previously owned Cloudflare GraphQL queries, the analytics
credential, MCP health probing, aggregation and caching. These are backend
responsibilities. They now live in `cloudflare_status_traffic.py` on Server.
The existing browser status screen and its version-1 data contract are retained.

Web forwards GET/HEAD `/status/traffic.json` through `NORULO_SERVER` to the same
Server path. The target is fixed; query parameters, browser cookies, presented
credentials and client cache directives are stripped. Only Accept and the
Cloudflare ingress address are forwarded. There is no external-fetch fallback
or retry. Binding failures return explicit 503 unavailability.

Server owns optional `NORULO_CF_ANALYTICS_TOKEN` (Account Analytics: Read) and
the public `NORULO_CF_ACCOUNT_ID`. The user migrated the same-named Secret;
deployment inherits its current binding without reading/copying its value.
Web needs neither analytics variable. Server returns only 168 hourly activity
levels and coarse error levels per public service ID, MCP reachability and the
latest scheduler outcome. Provider text, account/script IDs and counts stay
private. Diagnostics use fixed operation/reason codes and numeric HTTP status.

The endpoint retains production network/credential frequency admission, while
running before D1/DO and product activation. It never queries ledger storage,
creates fixtures, refreshes identity, invokes models or mutates business data.
Fixed upstream URLs reject redirects, use a five-second abort signal and bound
response bodies to 1 MiB. Independent scheduler failure leaves traffic usable;
missing/failed traffic never becomes a healthy empty heatmap.

Successful public summaries expire after ten minutes. Unknown/configuration
failures expire after one minute. Browser TTL is at most five minutes and never
outlives the original summary expiry. Native Cache API hits preserve expiry;
isolate memo stores only serialized public data, never request objects or IO
promises. Mode/account/credential changes partition the internal cache key.
Cache operations are best effort; concurrent misses may perform duplicate
queries. This remains a Server-hosted status endpoint: observing a complete
Server failure independently would require a separate monitor.

The responsibility audit also checked GitHub identity refresh, permissions,
API-key scopes, expense rules, quota enforcement and provider credentials.
Server already owns their authoritative checks. Web validation, calendar
selectors, display transforms and the single refresh orchestration remain
client concerns; they do not replace Server enforcement. No additional proven
backend responsibility was found in those inspected paths.

Validation: `pytest tests`, Web `npm run check` and `npm run check:workers`, plus
`node scripts/check-status-native-runtime.cjs /absolute/new/scratch-directory`.
The native runner uses the canonical Python entry/module with synthetic
intercepted outbound responses and zero storage bindings. Release evidence
records the actual production versions, readback and remaining limitations.
