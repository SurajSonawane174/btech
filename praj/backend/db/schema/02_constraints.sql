ALTER TABLE documents
ADD CONSTRAINT unique_doc_revision
UNIQUE (praj_doc_number, praj_revision_number);
