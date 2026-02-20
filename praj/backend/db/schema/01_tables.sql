CREATE TABLE documents (
    id BIGSERIAL PRIMARY KEY,

    praj_doc_number VARCHAR(100) NOT NULL,
    praj_revision VARCHAR(50),
    customer_doc_number VARCHAR(100),
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
    id BIGSERIAL PRIMARY KEY,

    document_id BIGINT NOT NULL
        REFERENCES documents(id)
        ON DELETE CASCADE,

    comment_id_external VARCHAR(100) NOT NULL,
    page_sheet VARCHAR(50),

    actual_comment TEXT NOT NULL,
    snapshot_file VARCHAR(255),

    commenter_name VARCHAR(150),
    comment_datetime TIMESTAMP,

    comment_color VARCHAR(50),

    is_client_comment BOOLEAN NOT NULL DEFAULT FALSE,
    comment_category VARCHAR(100),
    is_handwritten BOOLEAN NOT NULL DEFAULT FALSE,

    extraction_confidence DECIMAL(5,2),

    assigned_to_user_id BIGINT
        REFERENCES users(id)
        ON DELETE SET NULL,

    target_closure_date DATE,
    crs_reference VARCHAR(100),

    resolution_summary TEXT,

    status VARCHAR(50) NOT NULL DEFAULT 'Open',

    evidence_link VARCHAR(255),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
