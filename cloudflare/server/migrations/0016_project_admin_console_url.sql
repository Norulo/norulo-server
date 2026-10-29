-- Optional third project link. Existing rows stay NULL; no backfill or rewrite.
ALTER TABLE ledger_projects ADD COLUMN admin_console_url TEXT
  CHECK (admin_console_url IS NULL OR length(CAST(admin_console_url AS BLOB)) BETWEEN 1 AND 2048);
