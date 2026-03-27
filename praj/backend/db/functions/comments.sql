-- =========================================
-- COMMENT FUNCTIONS
-- =========================================

CREATE OR REPLACE FUNCTION insert_comment_from_json(
    p_praj_project_number           VARCHAR,
    p_praj_document_number          VARCHAR,
    p_praj_revision_number          VARCHAR,
    p_supplier_name                 VARCHAR,
    p_supplier_po_number            VARCHAR,
    p_customer_document_number      VARCHAR,
    p_customer_revision             VARCHAR,
    p_page_sheet                    VARCHAR,
    p_comment_id                    VARCHAR,
    p_actual_extracted_comment      TEXT,
    p_snapshot_file                 VARCHAR,
    p_name_of_person_commented      VARCHAR,
    p_date_of_comment               VARCHAR,
    p_time_of_comment               VARCHAR,
    p_comment_color                 VARCHAR,
    p_is_client_comment             VARCHAR,
    p_comment_category              VARCHAR,
    p_is_handwritten                VARCHAR,
    p_extraction_confidence_percent NUMERIC,
    p_assigned_to                   BIGINT  DEFAULT NULL,
    p_target_closure_date           DATE    DEFAULT NULL,
    p_status                        VARCHAR DEFAULT 'open'
)
RETURNS BIGINT AS $$
DECLARE
    doc_id           BIGINT;
    new_comment_id   BIGINT;
    final_timestamp  TIMESTAMP;
BEGIN

    -- 1️⃣ Get or create document
    doc_id := get_or_create_document(
        p_praj_project_number,
        p_praj_document_number,
        p_praj_revision_number,
        p_supplier_name,
        p_supplier_po_number,
        p_customer_document_number,
        p_customer_revision
    );

    -- 2️⃣ Combine date & time (if available)
    IF p_date_of_comment <> 'NA' AND p_time_of_comment <> 'NA' THEN
        final_timestamp := (p_date_of_comment || ' ' || p_time_of_comment)::timestamp;
    ELSE
        final_timestamp := NULL;
    END IF;

    -- 3️⃣ Insert comment
    INSERT INTO comments (
        document_id,
        comment_id,
        page_sheet,
        actual_extracted_comment,
        snapshot_file,
        name_of_person_commented,
        comment_datetime,
        comment_color,
        is_client_comment,
        comment_category,
        is_handwritten,
        extraction_confidence_percent,
        assigned_to,
        target_closure_date,
        status
    )
    VALUES (
        doc_id,
        p_comment_id,
        p_page_sheet,
        p_actual_extracted_comment,
        p_snapshot_file,
        p_name_of_person_commented,
        final_timestamp,
        p_comment_color,
        (p_is_client_comment = 'Y'),
        p_comment_category,
        (p_is_handwritten = 'Y'),
        p_extraction_confidence_percent,
        p_assigned_to,
        p_target_closure_date,
        p_status
    )
    RETURNING id INTO new_comment_id;

    RETURN new_comment_id;
END;
$$ LANGUAGE plpgsql;

--

CREATE OR REPLACE FUNCTION get_comment_by_id(
    p_comment_id VARCHAR
)
RETURNS SETOF comments AS $$
BEGIN
    RETURN QUERY
    SELECT *
    FROM comments
    WHERE comment_id = p_comment_id;
END;
$$ LANGUAGE plpgsql;

--

CREATE OR REPLACE FUNCTION get_comments_by_document(
    p_document_id BIGINT
)
RETURNS SETOF comments AS $$
BEGIN
    RETURN QUERY
    SELECT *
    FROM comments
    WHERE document_id = p_document_id
    ORDER BY id;
END;
$$ LANGUAGE plpgsql;

--

CREATE OR REPLACE FUNCTION update_comment(
    p_comment_id               VARCHAR,
    p_actual_extracted_comment TEXT,
    p_comment_color            VARCHAR,
    p_comment_category         VARCHAR,
    p_is_client_comment        BOOLEAN,
    p_is_handwritten           BOOLEAN,
    p_assigned_to              BIGINT  DEFAULT NULL,
    p_target_closure_date      DATE    DEFAULT NULL,
    p_status                   VARCHAR DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
    UPDATE comments
    SET
        actual_extracted_comment = p_actual_extracted_comment,
        comment_color            = p_comment_color,
        comment_category         = p_comment_category,
        is_client_comment        = p_is_client_comment,
        is_handwritten           = p_is_handwritten,
        assigned_to              = p_assigned_to,
        target_closure_date      = p_target_closure_date,
        status                   = COALESCE(p_status, status)
    WHERE comment_id = p_comment_id;
END;
$$ LANGUAGE plpgsql;

--

CREATE OR REPLACE FUNCTION delete_comment(
    p_comment_id VARCHAR
)
RETURNS VOID AS $$
BEGIN
    DELETE FROM comments
    WHERE comment_id = p_comment_id;
END;
$$ LANGUAGE plpgsql;

--

CREATE OR REPLACE FUNCTION get_comments_by_praj_document_number(
    p_praj_document_number VARCHAR
)
RETURNS TABLE (
    id                            BIGINT,
    document_id                   BIGINT,
    comment_id                    VARCHAR,
    page_sheet                    VARCHAR,
    actual_extracted_comment      TEXT,
    snapshot_file                 VARCHAR,
    name_of_person_commented      VARCHAR,
    comment_datetime              TIMESTAMP,
    comment_color                 VARCHAR,
    is_client_comment             BOOLEAN,
    comment_category              VARCHAR,
    is_handwritten                BOOLEAN,
    extraction_confidence_percent NUMERIC,
    assigned_to                   BIGINT,
    target_closure_date           DATE,
    status                        VARCHAR,
    created_at                    TIMESTAMP,
    praj_project_number           VARCHAR,
    praj_document_number          VARCHAR,
    praj_revision_number          VARCHAR,
    supplier_name                 VARCHAR,
    supplier_po_number            VARCHAR,
    customer_document_number      VARCHAR,
    customer_revision             VARCHAR
)
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.document_id,
        c.comment_id,
        c.page_sheet,
        c.actual_extracted_comment,
        c.snapshot_file,
        c.name_of_person_commented,
        c.comment_datetime,
        c.comment_color,
        c.is_client_comment,
        c.comment_category,
        c.is_handwritten,
        c.extraction_confidence_percent,
        c.assigned_to,
        c.target_closure_date,
        c.status,
        c.created_at,
        d.praj_project_number,
        d.praj_document_number,
        d.praj_revision_number,
        d.supplier_name,
        d.supplier_po_number,
        d.customer_document_number,
        d.customer_revision
    FROM comments c
    JOIN documents d ON c.document_id = d.id
    WHERE d.praj_document_number = p_praj_document_number
    ORDER BY c.id;
END;
$$ LANGUAGE plpgsql;