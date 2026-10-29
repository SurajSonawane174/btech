-- ============================================================
-- CEMS -- FINAL database schema (3 tables). This is the schema that is live;
-- the application code must match it. Do not add tables here.
--
--   documents  one row per document REVISION (Rev A and Rev B are two rows),
--              unique on (project, document number, revision, supplier, supplier PO)
--   users      login accounts; one global role per user (plain varchar)
--   comments   one row per extracted review comment, plus the AI draft and the
--              human-approved resolution
--
-- Vectors (comment embeddings, standards text) live in Qdrant only, keyed by
-- comments.id (bigint) and by integer standards chunk ids. No UUIDs, no pgvector.
-- ============================================================

CREATE SEQUENCE IF NOT EXISTS documents_id_seq;
CREATE SEQUENCE IF NOT EXISTS users_id_seq;
CREATE SEQUENCE IF NOT EXISTS comments_id_seq;

CREATE TABLE public.documents (
  id bigint NOT NULL DEFAULT nextval('documents_id_seq'::regclass),
  praj_document_number character varying NOT NULL,
  praj_revision_number character varying,
  customer_document_number character varying,
  customer_revision character varying,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  praj_project_number character varying NOT NULL,
  supplier_name character varying NOT NULL,
  supplier_po_number character varying NOT NULL,
  is_released boolean NOT NULL DEFAULT false,
  CONSTRAINT documents_pkey PRIMARY KEY (id),
  CONSTRAINT unique_doc_revision UNIQUE (praj_project_number, praj_document_number,
      praj_revision_number, supplier_name, supplier_po_number)
);

CREATE TABLE public.users (
  id bigint NOT NULL DEFAULT nextval('users_id_seq'::regclass),
  username character varying NOT NULL UNIQUE,
  email character varying NOT NULL UNIQUE,
  password_hash character varying NOT NULL,
  role character varying NOT NULL DEFAULT 'reviewer'::character varying,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT users_pkey PRIMARY KEY (id)
);

CREATE TABLE public.comments (
  id bigint NOT NULL DEFAULT nextval('comments_id_seq'::regclass),
  document_id bigint NOT NULL,
  comment_id character varying NOT NULL UNIQUE,
  page_sheet character varying,
  actual_extracted_comment text NOT NULL,
  snapshot_file character varying,
  name_of_person_commented character varying,
  comment_datetime timestamp without time zone,
  comment_color character varying,
  is_client_comment boolean NOT NULL DEFAULT false,
  comment_category character varying,
  is_handwritten boolean NOT NULL DEFAULT false,
  extraction_confidence_percent numeric,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  assigned_to bigint,
  target_closure_date date,
  status character varying NOT NULL DEFAULT 'open'::character varying,
  embedded boolean NOT NULL DEFAULT false,          -- synced to Qdrant?
  ai_suggested_resolution text,                     -- AI draft (never the final answer)
  ai_confidence_percent numeric,                    -- AI confidence heuristic, 0-100
  resolution_text text,                             -- final human-approved resolution
  resolved_at timestamp without time zone,          -- when it was resolved
  CONSTRAINT comments_pkey PRIMARY KEY (id),
  CONSTRAINT comments_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id),
  CONSTRAINT comments_assigned_to_fkey FOREIGN KEY (assigned_to) REFERENCES public.users(id)
);

ALTER SEQUENCE documents_id_seq OWNED BY public.documents.id;
ALTER SEQUENCE users_id_seq OWNED BY public.users.id;
ALTER SEQUENCE comments_id_seq OWNED BY public.comments.id;
