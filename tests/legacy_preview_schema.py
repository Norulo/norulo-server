"""Keep dated preview upgrade/clear proofs on their reviewed v13 authority."""
def pin_v13_meter(monkeypatch):
    from norulo_server import cloudflare_preview_budget as budget
    from norulo_server import cloudflare_preview_schema as schema
    monkeypatch.setattr(budget, "SCHEMA_VERSION", schema.V13_SCHEMA_VERSION)
    monkeypatch.setattr(budget, "SCHEMA_FINGERPRINT", schema.V13_SCHEMA_FINGERPRINT)
    monkeypatch.setattr(budget, "SCHEMA_OBJECTS", schema.V13_SCHEMA_OBJECTS)
    monkeypatch.setattr(budget, "SCHEMA_SQL", schema.V13_SCHEMA_SQL)
