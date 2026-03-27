const pool = require('../../db/db');

// CREATE / GET Document (Using your updated custom function)
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

        // Ensure all required parameters are passed to the DB function
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

// READ All Documents (Using your custom function)
module.exports.getAllDocuments = async (req, res) => {
    try {
        // Utilizing the get_all_documents() function defined in your SQL
        const result = await pool.query('SELECT * FROM get_all_documents()');
        res.json(result.rows);
    } catch (err) {
        console.error('Error fetching all documents:', err);
        res.status(500).json({ message: 'Server error fetching documents' });
    }
};

// READ Single Document by ID
module.exports.getDocumentById = async (req, res) => {
    try {
        const { id } = req.params;
        const result = await pool.query('SELECT * FROM get_document_by_praj_document_number($1::VARCHAR)', [id]);
        
        if (result.rows.length === 0) return res.status(404).json({ message: 'Document not found' });
        
        res.json(result.rows[0]);
    } catch (err) {
        console.error('Error fetching document by ID:', err);
        res.status(500).json({ message: 'Server error fetching document' });
    }
};

// UPDATE Document
module.exports.updateDocument = async (req, res) => {
    try {
        const { id } = req.params;
        const { 
            praj_project_number,
            praj_document_number, 
            praj_revision_number, 
            supplier_name,
            supplier_po_number,
            customer_document_number, 
            customer_revision 
        } = req.body;

        const result = await pool.query(
            `UPDATE documents 
             SET praj_project_number = $1, 
                 praj_document_number = $2, 
                 praj_revision_number = $3, 
                 supplier_name = $4,
                 supplier_po_number = $5,
                 customer_document_number = $6, 
                 customer_revision = $7 
             WHERE id = $8 RETURNING *`,
            [
                praj_project_number, 
                praj_document_number, 
                praj_revision_number, 
                supplier_name, 
                supplier_po_number, 
                customer_document_number, 
                customer_revision, 
                id
            ]
        );

        if (result.rows.length === 0) return res.status(404).json({ message: 'Document not found' });

        res.json({ message: 'Document updated', document: result.rows[0] });
    } catch (err) {
        // If the update violates the unique constraint, handle it gracefully
        if (err.code === '23505') { 
            return res.status(409).json({ message: 'A document with this project, document number, revision, and supplier already exists.' });
        }
        console.error('Error updating document:', err);
        res.status(500).json({ message: 'Server error updating document' });
    }
};

// DELETE Document
module.exports.deleteDocument = async (req, res) => {
    try {
        const { id } = req.params;
        const result = await pool.query('DELETE FROM documents WHERE id = $1 RETURNING id', [id]);

        if (result.rows.length === 0) return res.status(404).json({ message: 'Document not found' });

        // Note: Comments will be auto-deleted due to ON DELETE CASCADE in your schema
        res.json({ message: 'Document and associated comments deleted successfully' });
    } catch (err) {
        console.error('Error deleting document:', err);
        res.status(500).json({ message: 'Server error deleting document' });
    }
};