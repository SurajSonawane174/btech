const pool = require('../../db/db');

// CREATE / GET Document 
module.exports.createOrGetDocument = async (req, res) => {
    try {
        const {
            praj_project_number,
            praj_document_number,
            praj_revision_number,
            supplier_name,
            supplier_po_number,
            customer_document_number,
            customer_revision
        } = req.body;

        // Note: The SQL function takes exactly 7 arguments now.
        const result = await pool.query(
            'SELECT get_or_create_document($1, $2, $3, $4, $5, $6, $7) AS doc_id',
            [
                praj_project_number, 
                praj_document_number, 
                praj_revision_number, 
                supplier_name, 
                supplier_po_number, 
                customer_document_number || 'NA', 
                customer_revision || 'NA'
            ]
        );

        res.status(201).json({ 
            message: 'Document processed successfully', 
            doc_id: result.rows[0].doc_id 
        });
    } catch (err) {
        console.error('Error creating/getting document:', err);
        res.status(500).json({ message: 'Server error creating document' });
    }
};

// READ All Documents
module.exports.getAllDocuments = async (req, res) => {
    try {
        const result = await pool.query('SELECT * FROM get_all_documents()');
        res.json(result.rows);
    } catch (err) {
        console.error('Error fetching all documents:', err);
        res.status(500).json({ message: 'Server error fetching documents' });
    }
};

// READ All Released Documents
module.exports.getAllReleasedDocuments = async (req, res) => {
    try {
        const result = await pool.query('SELECT * FROM get_released_documents()');
        res.json(result.rows);
    } catch (err) {
        console.error('Error fetching released documents:', err);
        res.status(500).json({ message: 'Server error fetching released documents' });
    }
};

// READ All Unreleased Documents
module.exports.getAllUnreleasedDocuments = async (req, res) => {
    try {
        const result = await pool.query('SELECT * FROM get_unreleased_documents()');
        res.json(result.rows);
    } catch (err) {
        console.error('Error fetching unreleased documents:', err);
        res.status(500).json({ message: 'Server error fetching unreleased documents' });
    }
};

// READ Single Document by praj_document_number
module.exports.getDocumentById = async (req, res) => {
    try {
        // req.params.id is acting as the praj_document_number (e.g., "DWG099")
        const { id: praj_document_number } = req.params; 
        
        const result = await pool.query('SELECT * FROM get_document_by_praj_document_number($1)', [praj_document_number]);
        
        // If the custom function returns a row with null fields, it means it wasn't found
        if (!result.rows[0] || !result.rows[0].praj_document_number) {
            return res.status(404).json({ message: 'Document not found' });
        }
        
        res.json(result.rows[0]);
    } catch (err) {
        console.error('Error fetching document by document number:', err);
        res.status(500).json({ message: 'Server error fetching document' });
    }
};

// UPDATE Document Status to Released
module.exports.releaseDocument = async (req, res) => {
    try {
        const { id: praj_document_number } = req.params;
        
        // The SQL function returns VOID, so we just execute it
        await pool.query('SELECT release_document($1)', [praj_document_number]);

        res.json({ message: `Document ${praj_document_number} released successfully` });
    } catch (err) {
        console.error('Error releasing document:', err);
        res.status(500).json({ message: 'Server error releasing document' });
    }
};

// DELETE Document
module.exports.deleteDocument = async (req, res) => {
    try {
        const { id: praj_document_number } = req.params;
        
        // The SQL function returns VOID
        await pool.query('SELECT delete_document($1)', [praj_document_number]);

        res.json({ message: `Document ${praj_document_number} and associated comments deleted successfully` });
    } catch (err) {
        console.error('Error deleting document:', err);
        res.status(500).json({ message: 'Server error deleting document' });
    }
};

// UPDATE Document Metadata 
// Note: You didn't provide a custom SQL function for this specific action. 
// If you still need to update supplier names, etc., keep this standard SQL query.
module.exports.updateDocument = async (req, res) => {
    try {
        // Here, we'll assume you are using the praj_document_number to update it based on the new pattern
        const { id: praj_document_number } = req.params;
        const { 
            praj_project_number,
            praj_revision_number, 
            supplier_name,
            supplier_po_number,
            customer_document_number, 
            customer_revision 
        } = req.body;

        const result = await pool.query(
            `UPDATE documents 
             SET praj_project_number = $1, 
                 praj_revision_number = $2, 
                 supplier_name = $3,
                 supplier_po_number = $4,
                 customer_document_number = $5, 
                 customer_revision = $6 
             WHERE praj_document_number = $7 RETURNING *`,
            [
                praj_project_number, 
                praj_revision_number, 
                supplier_name, 
                supplier_po_number, 
                customer_document_number, 
                customer_revision, 
                praj_document_number
            ]
        );

        if (result.rows.length === 0) return res.status(404).json({ message: 'Document not found' });

        res.json({ message: 'Document updated', document: result.rows[0] });
    } catch (err) {
        if (err.code === '23505') { 
            return res.status(409).json({ message: 'A document with these details already exists.' });
        }
        console.error('Error updating document:', err);
        res.status(500).json({ message: 'Server error updating document' });
    }
};