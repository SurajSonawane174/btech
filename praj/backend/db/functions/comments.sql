-- =========================================
-- COMMENT FUNCTIONS
-- =========================================

CREATE OR REPLACE FUNCTION insert_comment_from_json(
    p_praj_project_number          VARCHAR,
    p_praj_document_number         VARCHAR,
    p_praj_revision_number         VARCHAR,
    p_supplier_name                VARCHAR,
    p_supplier_po_number           VARCHAR,
    p_customer_document_number     VARCHAR,
    p_customer_revision            VARCHAR,
    p_page_sheet                   VARCHAR,
    p_comment_id                   VARCHAR,
    p_actual_extracted_comment     TEXT,
    p_snapshot_file                VARCHAR,
    p_name_of_person_commented     VARCHAR,
    p_date_of_comment              VARCHAR,
    p_time_of_comment              VARCHAR,
    p_comment_color                VARCHAR,
    p_is_client_comment            VARCHAR,
    p_comment_category             VARCHAR,
    p_is_handwritten               VARCHAR,
    p_extraction_confidence_percent NUMERIC
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
        extraction_confidence_percent
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
        p_extraction_confidence_percent
    )
    RETURNING id INTO new_comment_id;

    RETURN new_comment_id;
END;
$$ LANGUAGE plpgsql;

--

CREATE OR REPLACE FUNCTION get_comment_by_id(
    p_comment_id BIGINT
)
RETURNS SETOF comments AS $$
BEGIN
    RETURN QUERY
    SELECT *
    FROM comments
    WHERE id = p_comment_id;
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
    p_comment_id               BIGINT,
    p_actual_extracted_comment TEXT,
    p_comment_color            VARCHAR,
    p_comment_category         VARCHAR,
    p_is_client_comment        BOOLEAN,
    p_is_handwritten           BOOLEAN
)
RETURNS VOID AS $$
BEGIN
    UPDATE comments
    SET
        actual_extracted_comment = p_actual_extracted_comment,
        comment_color            = p_comment_color,
        comment_category         = p_comment_category,
        is_client_comment        = p_is_client_comment,
        is_handwritten           = p_is_handwritten
    WHERE id = p_comment_id;
END;
$$ LANGUAGE plpgsql;

--

CREATE OR REPLACE FUNCTION delete_comment(
    p_comment_id BIGINT
)
RETURNS VOID AS $$
BEGIN
    DELETE FROM comments
    WHERE id = p_comment_id;
END;
$$ LANGUAGE plpgsql;