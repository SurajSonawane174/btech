-- ============================================================
-- CEMS AI Automation Layer — Schema
-- Matches comment_extractor.py's real COLUMNS output exactly:
--   sr_no, praj_document_number, praj_revision_number,
--   customer_document_number, customer_revision, page_sheet,
--   comment_id, actual_extracted_comment, snapshot_file,
--   name_of_person_commented, email_of_person_commented,
--   date_of_comment, time_of_comment, comment_color,
--   is_client_comment, comment_category, is_handwritten,
--   extraction_confidence_percent, annotation_type,
--   classification_method, comment_source
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TYPE comment_category AS ENUM ('technical', 'aesthetic', 'repeated', 'uncategorized');
CREATE TYPE comment_status   AS ENUM ('open', 'in_review', 'resolved', 'reopened', 'closed');
CREATE TYPE resolution_source AS ENUM ('manual', 'ai_suggested', 'ai_accepted_as_is');
CREATE TYPE user_role        AS ENUM ('admin', 'reviewer', 'viewer');

-- ------------------------------------------------------------
-- RBAC — minimal but real: roles + project-scoped membership
-- ------------------------------------------------------------

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    display_name    VARCHAR(255),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE projects (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_code    VARCHAR(64) UNIQUE NOT NULL,
    project_name    VARCHAR(255),
    client_name     VARCHAR(255),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- A user's role is scoped PER PROJECT (reviewer on Project A can be
-- viewer-only on Project B) — this is what makes it RBAC and not
-- just a global permission flag.
CREATE TABLE project_memberships (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    role            user_role NOT NULL DEFAULT 'viewer',
    granted_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, project_id)
);

CREATE INDEX idx_memberships_user ON project_memberships(user_id);
CREATE INDEX idx_memberships_project ON project_memberships(project_id);

-- ------------------------------------------------------------
-- DOCUMENTS / REVISIONS
-- ------------------------------------------------------------

CREATE TABLE documents (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id       UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    drawing_number   VARCHAR(128) NOT NULL,
    document_title    VARCHAR(255),
    discipline        VARCHAR(64),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, drawing_number)
);

CREATE TABLE revisions (
    id                        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id               UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    praj_revision_number      VARCHAR(32),
    customer_document_number  VARCHAR(128),
    customer_revision         VARCHAR(32),
    source_pdf_path           TEXT,
    processed_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    total_comments             INTEGER DEFAULT 0,
    UNIQUE (document_id, praj_revision_number)
);

CREATE INDEX idx_revisions_document_id ON revisions(document_id);

-- ------------------------------------------------------------
-- COMMENTS — field-for-field match to comment_extractor.py's COLUMNS
-- ------------------------------------------------------------

CREATE TABLE comments (
    id                              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    revision_id                     UUID NOT NULL REFERENCES revisions(id) ON DELETE CASCADE,
    sr_no                           INTEGER,
    comment_uid                     VARCHAR(128) NOT NULL,   -- comment_id in source CSV
    page_sheet                      INTEGER,
    actual_extracted_comment        TEXT NOT NULL,
    snapshot_file                   TEXT,
    name_of_person_commented        VARCHAR(128),
    email_of_person_commented       VARCHAR(255),
    date_of_comment                 VARCHAR(32),
    time_of_comment                 VARCHAR(32),
    comment_color                   VARCHAR(32),
    is_client_comment               BOOLEAN DEFAULT false,
    comment_category                comment_category DEFAULT 'uncategorized',
    is_handwritten                  BOOLEAN DEFAULT false,
    extraction_confidence_percent   INTEGER,
    annotation_type                 VARCHAR(32),   -- native / vision / ocr etc, from source
    classification_method           VARCHAR(32),   -- gemini / rule_based / repeated
    comment_source                  VARCHAR(32),   -- native / vision / ocr_box / ocr_page
    visual_feature                  VARCHAR(255),  -- what the snapshot shows being marked (enrichment)

    status                          comment_status DEFAULT 'open',
    cluster_id                      UUID,
    embedded                        BOOLEAN DEFAULT false,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (revision_id, comment_uid)
);

CREATE INDEX idx_comments_revision_id  ON comments(revision_id);
CREATE INDEX idx_comments_category     ON comments(comment_category);
CREATE INDEX idx_comments_status       ON comments(status);
CREATE INDEX idx_comments_source       ON comments(comment_source);
CREATE INDEX idx_comments_embedded     ON comments(embedded) WHERE embedded = false;

-- ------------------------------------------------------------
-- LIGHTWEIGHT PROPERTY GRAPH (Stage 4) — entities + typed edges,
-- living in Postgres rather than a dedicated graph DB for now.
-- Queryable via recursive CTEs; swappable for Neo4j later without
-- changing the extraction/writer contract.
-- ------------------------------------------------------------

CREATE TABLE entities (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type     VARCHAR(64) NOT NULL,   -- equipment_id, drawing_ref, spec_ref, system, material
    entity_value    VARCHAR(255) NOT NULL,
    project_id      UUID REFERENCES projects(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, entity_type, entity_value)
);

CREATE TABLE comment_entity_edges (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    comment_id      UUID NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
    entity_id       UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    confidence      INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (comment_id, entity_id)
);

CREATE INDEX idx_entity_edges_comment ON comment_entity_edges(comment_id);
CREATE INDEX idx_entity_edges_entity  ON comment_entity_edges(entity_id);
CREATE INDEX idx_entities_project     ON entities(project_id);

-- ------------------------------------------------------------
-- RESOLUTIONS (Stage 3 target)
-- ------------------------------------------------------------

CREATE TABLE resolutions (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    comment_id              UUID NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
    resolution_text         TEXT NOT NULL,
    resolved_by             VARCHAR(128),
    source                  resolution_source DEFAULT 'manual',
    ai_recommendation_text  TEXT,
    ai_confidence_percent   INTEGER,
    ai_cited_standards      TEXT[],
    ai_similar_comment_ids  UUID[],
    resolved_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_resolutions_comment_id ON resolutions(comment_id);

-- ------------------------------------------------------------
-- STANDARDS CORPUS (Stage 2 — Agentic RAG target)
-- ------------------------------------------------------------

CREATE TABLE standards_documents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title           VARCHAR(255) NOT NULL,
    code_reference  VARCHAR(64),
    discipline      VARCHAR(64),
    file_path       TEXT,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE standards_chunks (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    standards_document_id   UUID NOT NULL REFERENCES standards_documents(id) ON DELETE CASCADE,
    chunk_index             INTEGER NOT NULL,
    chunk_text              TEXT NOT NULL,
    page_number             INTEGER,
    section_reference       VARCHAR(128),
    embedded                BOOLEAN DEFAULT false,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_standards_chunks_document_id ON standards_chunks(standards_document_id);

-- ------------------------------------------------------------
-- AGENTIC RAG TRACE LOG — every retrieval step logged for the
-- faithfulness self-check and for showing Vahida/PRAJ exactly
-- HOW the agent reasoned, not just its final answer.
-- ------------------------------------------------------------

CREATE TABLE rag_query_traces (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    comment_id          UUID REFERENCES comments(id) ON DELETE CASCADE,
    original_query       TEXT NOT NULL,
    decomposed_subqueries TEXT[],
    retrieval_hops       JSONB,          -- [{hop: 1, query: ..., chunks_retrieved: [...]}, ...]
    faithfulness_passed  BOOLEAN,
    faithfulness_notes   TEXT,
    final_answer         TEXT,
    cited_chunk_ids       UUID[],
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- CLUSTERS
-- ------------------------------------------------------------

CREATE TABLE comment_clusters (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id        UUID REFERENCES projects(id) ON DELETE CASCADE,
    label             VARCHAR(255),
    description       TEXT,
    algorithm         VARCHAR(32) DEFAULT 'hdbscan',
    member_count      INTEGER DEFAULT 0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE comments
    ADD CONSTRAINT fk_comments_cluster
    FOREIGN KEY (cluster_id) REFERENCES comment_clusters(id) ON DELETE SET NULL;

-- ------------------------------------------------------------
-- VIEWS
-- ------------------------------------------------------------

CREATE VIEW project_comment_summary AS
SELECT
    p.project_code,
    p.project_name,
    COUNT(c.id)                                                   AS total_comments,
    COUNT(c.id) FILTER (WHERE c.comment_category = 'technical')   AS technical_count,
    COUNT(c.id) FILTER (WHERE c.comment_category = 'aesthetic')   AS aesthetic_count,
    COUNT(c.id) FILTER (WHERE c.comment_category = 'repeated')    AS repeated_count,
    COUNT(c.id) FILTER (WHERE c.classification_method = 'gemini') AS gemini_classified,
    COUNT(c.id) FILTER (WHERE c.classification_method = 'rule_based') AS rule_based_classified,
    COUNT(c.id) FILTER (WHERE c.comment_source = 'vision')        AS vision_extracted,
    COUNT(c.id) FILTER (WHERE c.status = 'open')                  AS open_count,
    COUNT(c.id) FILTER (WHERE c.status = 'resolved')              AS resolved_count
FROM projects p
JOIN documents d  ON d.project_id  = p.id
JOIN revisions r  ON r.document_id = d.id
JOIN comments c   ON c.revision_id = r.id
GROUP BY p.id, p.project_code, p.project_name;
