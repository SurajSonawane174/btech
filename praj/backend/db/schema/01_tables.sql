CREATE TABLE documents (
    id BIGSERIAL PRIMARY KEY,

    praj_document_number VARCHAR(100) NOT NULL,
    praj_revision_number VARCHAR(50),
    customer_document_number VARCHAR(100),
    customer_revision VARCHAR(50),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,

    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,

    role VARCHAR(50) NOT NULL DEFAULT 'reviewer',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE comments (
  id BIGSERIAL NOT NULL,

  document_id BIGINT NOT NULL,

  comment_id VARCHAR(100) NOT NULL,
  page_sheet VARCHAR(50),

  actual_extracted_comment TEXT NOT NULL,
  snapshot_file VARCHAR(255),

  name_of_person_commented VARCHAR(150),
  comment_datetime TIMESTAMP,

  comment_color VARCHAR(50),

  is_client_comment BOOLEAN NOT NULL DEFAULT FALSE,
  comment_category VARCHAR(100),
  is_handwritten BOOLEAN NOT NULL DEFAULT FALSE,

  extraction_confidence_percent NUMERIC(5, 2),

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT comments_pkey PRIMARY KEY (id),

  CONSTRAINT comments_document_id_fkey
    FOREIGN KEY (document_id)
    REFERENCES documents (id)
    ON DELETE CASCADE
);

