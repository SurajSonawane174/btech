const pool = require('../../db/db');

// CREATE / GET Document (Using your custom function)
module.exports.createOrGetDocument = async (req, res) => {
    try {
        const {
            praj_doc_number,
            praj_revision_number,
            customer_document_number,
            customer_revision
        } = req.body;

        const result = await pool.query(
            'SELECT get_or_create_document($1, $2, $3, $4) AS doc_id',
            [praj_doc_number, praj_revision_number, customer_document_number || 'NA', customer_revision || 'NA']
        );

        res.status(201).json({ 
            message: 'Document processed successfully', 
            doc_id: result.rows[0].doc_id 
        });
    } catch (err) {
        console.error(err);
        res.status(500).json({ message: 'Server error creating document' });
    }
};

// READ All Documents
module.exports.getAllDocuments = async (req, res) => {
    try {
        const result = await pool.query('SELECT * FROM documents ORDER BY created_at DESC');
        res.json(result.rows);
    } catch (err) {
        console.error(err);
        res.status(500).json({ message: 'Server error fetching documents' });
    }
};

// READ Single Document by ID
module.exports.getDocumentById = async (req, res) => {
    try {
        const { id } = req.params;
        const result = await pool.query('SELECT * FROM documents WHERE id = $1', [id]);
        
        if (result.rows.length === 0) return res.status(404).json({ message: 'Document not found' });
        
        res.json(result.rows[0]);
    } catch (err) {
        console.error(err);
        res.status(500).json({ message: 'Server error fetching document' });
    }
};

// UPDATE Document
module.exports.updateDocument = async (req, res) => {
    try {
        const { id } = req.params;
        const { praj_document_number, praj_revision_number, customer_document_number, customer_revision } = req.body;

        const result = await pool.query(
            `UPDATE documents 
             SET praj_document_number = $1, praj_revision_number = $2, customer_document_number = $3, customer_revision = $4 
             WHERE id = $5 RETURNING *`,
            [praj_document_number, praj_revision_number, customer_document_number, customer_revision, id]
        );

        if (result.rows.length === 0) return res.status(404).json({ message: 'Document not found' });

        res.json({ message: 'Document updated', document: result.rows[0] });
    } catch (err) {
        console.error(err);
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
        console.error(err);
        res.status(500).json({ message: 'Server error deleting document' });
    }
};