-- =========================================
-- DOCUMENT FUNCTIONS
-- =========================================

CREATE OR REPLACE FUNCTION get_or_create_document(
    p_praj_doc_number VARCHAR,
    p_praj_revision_number VARCHAR,
    p_customer_document_number VARCHAR,
    p_customer_revision VARCHAR
)
RETURNS BIGINT AS $$
DECLARE
    doc_id BIGINT;
BEGIN
    SELECT id INTO doc_id
    FROM documents
    WHERE praj_doc_number = p_praj_doc_number
      AND praj_revision_number = p_praj_revision_number
    LIMIT 1;

    IF doc_id IS NOT NULL THEN
        RETURN doc_id;
    END IF;

    INSERT INTO documents (
        praj_doc_number,
        praj_revision_number,
        customer_document_number,
        customer_revision
    )
    VALUES (
        p_praj_doc_number,
        p_praj_revision_number,
        NULLIF(p_customer_document_number, 'NA'),
        NULLIF(p_customer_revision, 'NA')
    )
    RETURNING id INTO doc_id;

    RETURN doc_id;
END;
$$ LANGUAGE plpgsql;
