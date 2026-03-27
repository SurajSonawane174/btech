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

    -- Insert new document (is_released defaults to FALSE)
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

--

DROP FUNCTION IF EXISTS get_all_documents();

CREATE FUNCTION get_all_documents()
RETURNS TABLE (
    id                       BIGINT,
    praj_project_number      VARCHAR,
    praj_document_number     VARCHAR,
    praj_revision_number     VARCHAR,
    supplier_name            VARCHAR,
    supplier_po_number       VARCHAR,
    customer_document_number VARCHAR,
    customer_revision        VARCHAR,
    is_released              BOOLEAN,
    created_at               TIMESTAMP,
    total_comments           BIGINT
)
AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.praj_project_number,
        d.praj_document_number,
        d.praj_revision_number,
        d.supplier_name,
        d.supplier_po_number,
        d.customer_document_number,
        d.customer_revision,
        d.is_released,
        d.created_at,
        COUNT(c.id) AS total_comments
    FROM documents d
    LEFT JOIN comments c ON c.document_id = d.id
    GROUP BY d.id
    ORDER BY d.id;
END;
$$ LANGUAGE plpgsql;

--

CREATE OR REPLACE FUNCTION get_document_by_praj_document_number(
    p_praj_document_number VARCHAR
)
RETURNS documents AS $$
DECLARE
    doc documents;
BEGIN
    SELECT * INTO doc
    FROM documents
    WHERE praj_document_number = p_praj_document_number;

    RETURN doc;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION get_unreleased_documents()
RETURNS TABLE (
    id                       BIGINT,
    praj_project_number      VARCHAR,
    praj_document_number     VARCHAR,
    praj_revision_number     VARCHAR,
    supplier_name            VARCHAR,
    supplier_po_number       VARCHAR,
    customer_document_number VARCHAR,
    customer_revision        VARCHAR,
    is_released              BOOLEAN,
    created_at               TIMESTAMP,
    total_comments           BIGINT
)
AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.praj_project_number,
        d.praj_document_number,
        d.praj_revision_number,
        d.supplier_name,
        d.supplier_po_number,
        d.customer_document_number,
        d.customer_revision,
        d.is_released,
        d.created_at,
        COUNT(c.id) AS total_comments
    FROM documents d
    LEFT JOIN comments c ON c.document_id = d.id
    WHERE d.is_released = FALSE
    GROUP BY d.id
    ORDER BY d.id;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION get_released_documents()
RETURNS TABLE (
    id                       BIGINT,
    praj_project_number      VARCHAR,
    praj_document_number     VARCHAR,
    praj_revision_number     VARCHAR,
    supplier_name            VARCHAR,
    supplier_po_number       VARCHAR,
    customer_document_number VARCHAR,
    customer_revision        VARCHAR,
    is_released              BOOLEAN,
    created_at               TIMESTAMP,
    total_comments           BIGINT
)
AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.praj_project_number,
        d.praj_document_number,
        d.praj_revision_number,
        d.supplier_name,
        d.supplier_po_number,
        d.customer_document_number,
        d.customer_revision,
        d.is_released,
        d.created_at,
        COUNT(c.id) AS total_comments
    FROM documents d
    LEFT JOIN comments c ON c.document_id = d.id
    WHERE d.is_released = TRUE
    GROUP BY d.id
    ORDER BY d.id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION delete_document(
    p_praj_document_number VARCHAR
)
RETURNS VOID AS $$
BEGIN
    DELETE FROM documents
    WHERE praj_document_number = p_praj_document_number;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION release_document(
    p_praj_document_number VARCHAR
)
RETURNS VOID AS $$
BEGIN
    UPDATE documents
    SET is_released = TRUE
    WHERE praj_document_number = p_praj_document_number;
END;
$$ LANGUAGE plpgsql;
