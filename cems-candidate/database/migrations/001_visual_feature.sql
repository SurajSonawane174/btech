-- Existing databases were created from the init-only schema.sql; apply once:
--   docker exec -i cems_postgres psql -U cems -d cems < database/migrations/001_visual_feature.sql
ALTER TABLE comments ADD COLUMN IF NOT EXISTS visual_feature VARCHAR(255);
