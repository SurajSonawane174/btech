-- ============================================================
-- Migration 001: provenance / identity / reply-thread columns on comments
--
-- STATUS: PROPOSED. Not applied automatically by any script, not referenced by schema.sql's
-- docker init, and ingest.py does NOT write these columns yet (it ignores extra CSV columns).
-- Until a follow-up change wires ingest to it, these values exist only in the extractor CSV/JSON.
--
-- Backward compatible and non-destructive:
--   * only ADD COLUMN IF NOT EXISTS, every column nullable, no defaults that rewrite rows,
--     no constraint, index or type change on existing columns;
--   * existing rows get NULL; existing queries, inserts (db.insert_comments_bulk) and the
--     Qdrant payload are unaffected;
--   * safe to run twice.
-- Impact: a brief ACCESS EXCLUSIVE lock on comments while the catalog is updated (adding a
-- nullable column without a default does not rewrite the table).
-- Rollback: ALTER TABLE comments DROP COLUMN <name> for each column below (drops that data).
--
-- Apply manually, after a backup, to a database you own:
--   psql -h localhost -U cems -d <db> -f database/migrations/001_comment_provenance_columns.sql
-- ============================================================

ALTER TABLE comments ADD COLUMN IF NOT EXISTS position_key          VARCHAR(32);   -- P###-R###-C###
ALTER TABLE comments ADD COLUMN IF NOT EXISTS drawing_number_source VARCHAR(32);   -- filename / title_block / pdf_metadata / unresolved
ALTER TABLE comments ADD COLUMN IF NOT EXISTS revision_source       VARCHAR(32);
ALTER TABLE comments ADD COLUMN IF NOT EXISTS source_file_sha256    CHAR(64);
ALTER TABLE comments ADD COLUMN IF NOT EXISTS metadata_notes        TEXT;
ALTER TABLE comments ADD COLUMN IF NOT EXISTS duplicate_of_uid      VARCHAR(128);  -- comment_uid of the first occurrence (CSV column duplicate_of)
ALTER TABLE comments ADD COLUMN IF NOT EXISTS reply_count           INTEGER;
ALTER TABLE comments ADD COLUMN IF NOT EXISTS replies_json          JSONB;         -- [{author, date, time, text, state, reply_type, page}]
ALTER TABLE comments ADD COLUMN IF NOT EXISTS reply_link_status     VARCHAR(32);   -- '' / parent_missing / malformed_reference / cycle
