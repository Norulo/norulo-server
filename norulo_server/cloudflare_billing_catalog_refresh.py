"""Refresh the public price catalog from configured Creem product IDs only."""
from __future__ import annotations

# Creem is the source of truth for prices. Keep each verified snapshot only
# briefly, so a price edited in Creem reaches Pricing within a minute while
# bursts of page views still share one set of product reads.
CATALOG_TTL_SECONDS = 60

from .cloudflare_billing_catalog import read_public_plan
from .cloudflare_billing_catalog_write import D1BillingCatalogTransactions
from .cloudflare_creem_gateway import product_bindings


async def read_or_refresh_catalog(*, binding, gateway, headers, products: dict | None, now: int):
    ids = product_bindings(products)
    if products == {}:
        return await read_public_plan(binding=binding, headers=headers, now=now,
            payments_disabled=True)
    if not ids or set(products) != {"pro", "max"}:
        return 503, {"error": {"code": "BILLING_CATALOG_UNAVAILABLE", "diagnostic": "PRODUCT_BINDINGS_INVALID"}}
    if not any(ids.values()):
        return await read_public_plan(binding=binding, headers=headers, now=now,
            payments_disabled=True)
    row = await binding.prepare("""SELECT expires_at,source_revision,updated_at
        FROM billing_public_catalog WHERE id=1""").first()
    # Judge freshness by when Creem was last read, so snapshots stored under an
    # older, longer expiry are replaced on the next request.
    if (row and int(row["expires_at"]) > now
            and int(row["updated_at"]) > now - CATALOG_TTL_SECONDS):
        return await read_public_plan(binding=binding, headers=headers, now=now)
    fetched = {}
    for product_id in {item for values in ids.values() for item in values.values()}:
        fetched[product_id] = await gateway.product(product_id)
    revision = max(now, int(row["source_revision"]) + 1) if row else max(1, now)
    try:
        await D1BillingCatalogTransactions(binding).stage_from_products(
            configured_ids=ids, fetched_products=fetched, source_revision=revision,
            now=now, expires_at=now + CATALOG_TTL_SECONDS)
    except Exception:
        # A concurrent request may have published a newer snapshot first;
        # serve that one, and fail only when no fresh catalog exists.
        status, payload = await read_public_plan(binding=binding, headers=headers, now=now)
        if status == 200:
            return status, payload
        raise
    return await read_public_plan(binding=binding, headers=headers, now=now)
