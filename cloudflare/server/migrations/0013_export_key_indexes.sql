-- Preserve the public occurred_on,id CSV order and seek past each page cursor.
-- This adds one maintained index; it does not rewrite expense business rows.
CREATE INDEX expenses_owner_export_date
  ON expenses(owner_id, occurred_on, id) WHERE deleted_at IS NULL;
-- Match the existing newest-first active API-key list and its page cursor.
CREATE INDEX idx_api_keys_user_active_created
  ON api_keys(user_id, created_at DESC, id DESC) WHERE revoked_at IS NULL;
