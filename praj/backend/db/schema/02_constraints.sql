-- Step 1: Add columns as nullable
ALTER TABLE documents
ADD COLUMN praj_project_number VARCHAR(100),
ADD COLUMN supplier_name       VARCHAR(150),
ADD COLUMN supplier_po_number  VARCHAR(100);

-- Step 2: Backfill existing rows
UPDATE documents
SET praj_project_number = 'UNKNOWN',
    supplier_name       = 'UNKNOWN',
    supplier_po_number  = 'UNKNOWN'
WHERE praj_project_number IS NULL;

-- Step 3: Apply NOT NULL constraints
ALTER TABLE documents
ALTER COLUMN praj_project_number SET NOT NULL,
ALTER COLUMN supplier_name       SET NOT NULL,
ALTER COLUMN supplier_po_number  SET NOT NULL;

-- Step 4: ONLY NOW add the unique constraint
ALTER TABLE documents
ADD CONSTRAINT unique_doc_revision
UNIQUE (praj_project_number, praj_document_number, praj_revision_number, supplier_name, supplier_po_number);