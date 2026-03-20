    const pool = require('../../db/db');

    // CREATE Comment 
    module.exports.createComment = async (req, res) => {
        try {
            const {
                praj_doc_number, praj_revision_number, customer_document_number, customer_revision,
                page_sheet, comment_id, actual_extracted_comment, snapshot_file,
                name_of_person_commented, date_of_comment, time_of_comment, comment_color,
                is_client_comment, comment_category, is_handwritten, extraction_confidence_percent
            } = req.body;

            // Convert actual booleans to 'Y'/'N' for your SQL function if necessary
            const clientCommentStr = is_client_comment ? 'Y' : 'N';
            const handwrittenStr = is_handwritten ? 'Y' : 'N';

            const result = await pool.query(
                `SELECT insert_comment_from_json(
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16
                ) AS new_comment_id`,
                [
                    praj_doc_number, praj_revision_number, customer_document_number || 'NA', customer_revision || 'NA',
                    page_sheet, comment_id, actual_extracted_comment, snapshot_file,
                    name_of_person_commented, date_of_comment || 'NA', time_of_comment || 'NA', comment_color,
                    clientCommentStr, comment_category, handwrittenStr, extraction_confidence_percent
                ]
            );

            res.status(201).json({ 
                message: 'Comment inserted successfully', 
                comment_id: result.rows[0].new_comment_id 
            });
        } catch (err) {
            console.error(err);
            res.status(500).json({ message: 'Server error creating comment' });
        }
    };

    // READ All Comments for a specific Document
    module.exports.getCommentsByDocument = async (req, res) => {
        try {
            const { documentId } = req.params;
            const result = await pool.query('SELECT * FROM comments WHERE document_id = $1 ORDER BY created_at DESC', [documentId]);
            res.json(result.rows);
        } catch (err) {
            console.error(err);
            res.status(500).json({ message: 'Server error fetching comments' });
        }
    };

    // READ Single Comment by ID
    module.exports.getCommentById = async (req, res) => {
        try {
            const { id } = req.params;
            const result = await pool.query('SELECT * FROM comments WHERE id = $1', [id]);
            
            if (result.rows.length === 0) return res.status(404).json({ message: 'Comment not found' });
            
            res.json(result.rows[0]);
        } catch (err) {
            console.error(err);
            res.status(500).json({ message: 'Server error fetching comment' });
        }
    };

    // UPDATE Comment
    module.exports.updateComment = async (req, res) => {
        try {
            const { id } = req.params;
            const { actual_extracted_comment, comment_category, comment_color, is_handwritten, is_client_comment } = req.body;

            const result = await pool.query(
                `UPDATE comments 
                SET actual_extracted_comment = $1, comment_category = $2, comment_color = $3, 
                    is_handwritten = $4, is_client_comment = $5
                WHERE id = $6 RETURNING *`,
                [actual_extracted_comment, comment_category, comment_color, is_handwritten, is_client_comment, id]
            );

            if (result.rows.length === 0) return res.status(404).json({ message: 'Comment not found' });

            res.json({ message: 'Comment updated', comment: result.rows[0] });
        } catch (err) {
            console.error(err);
            res.status(500).json({ message: 'Server error updating comment' });
        }
    };

    // DELETE Comment
    module.exports.deleteComment = async (req, res) => {
        try {
            const { id } = req.params;
            const result = await pool.query('DELETE FROM comments WHERE id = $1 RETURNING id', [id]);

            if (result.rows.length === 0) return res.status(404).json({ message: 'Comment not found' });

            res.json({ message: 'Comment deleted successfully' });
        } catch (err) {
            console.error(err);
            res.status(500).json({ message: 'Server error deleting comment' });
        }
    };