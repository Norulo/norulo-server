-- Latest successful expense writer only. Existing rows remain unknown; no
-- financial rewrite, historical backfill or additional per-operation row.
ALTER TABLE expenses ADD COLUMN last_source_json TEXT
  CHECK (last_source_json IS NULL OR
    (typeof(last_source_json)='text' AND length(last_source_json)<=2048
      AND json_valid(last_source_json) AND json_type(last_source_json)='object'));
