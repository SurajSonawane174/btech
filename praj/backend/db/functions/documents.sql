CREATE OR REPLACE FUNCTION get_or_create_document(
    p_praj_project_number      VARCHAR,
    p_praj_document_number     VARCHAR,
    p_praj_revision_number     VARCHAR,
    p_supplier_name            VARCHAR,
    p_supplier_po_number       VARCHAR,
    p_customer_document_number VARCHAR,
    p_customer_revision        VARCHAR
)
RETURNS BIGINT AS $$
DECLARE
    doc_id BIGINT;
BEGIN
    -- Try to find existing document
    SELECT id INTO doc_id
    FROM documents
    WHERE praj_project_number  = p_praj_project_number
      AND praj_document_number = p_praj_document_number
      AND praj_revision_number = p_praj_revision_number
      AND supplier_name        = p_supplier_name
      AND supplier_po_number   = p_supplier_po_number
    LIMIT 1;

    IF doc_id IS NOT NULL THEN
        RETURN doc_id;
    END IF;

    -- Insert new document
    INSERT INTO documents (
        praj_project_number,
        praj_document_number,
        praj_revision_number,
        supplier_name,
        supplier_po_number,
        customer_document_number,
        customer_revision
    )
    VALUES (
        p_praj_project_number,
        p_praj_document_number,
        p_praj_revision_number,
        p_supplier_name,
        p_supplier_po_number,
        NULLIF(p_customer_document_number, 'NA'),
        NULLIF(p_customer_revision, 'NA')
    )
    RETURNING id INTO doc_id;

    RETURN doc_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_all_documents()
RETURNS SETOF documents AS $$
BEGIN
    RETURN QUERY
    SELECT *
    FROM documents
    ORDER BY id;
END;
$$ LANGUAGE plpgsql;