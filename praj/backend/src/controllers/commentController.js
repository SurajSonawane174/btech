const pool = require('../../db/db');

// CREATE Comment (already correct, kept as is)
module.exports.createComment = async (req, res) => {
  try {
    const {
      praj_project_number,
      praj_document_number,
      praj_revision_number,
      supplier_name,
      supplier_po_number,
      customer_document_number,
      customer_revision,
      page_sheet,
      comment_id,
      actual_extracted_comment,
      snapshot_file,
      name_of_person_commented,
      date_of_comment,
      time_of_comment,
      comment_color,
      is_client_comment,
      comment_category,
      is_handwritten,
      extraction_confidence_percent
    } = req.body;

    const clientCommentStr = is_client_comment ? "Y" : "N";
    const handwrittenStr = is_handwritten ? "Y" : "N";

    const result = await pool.query(
      `SELECT insert_comment_from_json(
        $1, $2, $3, $4, $5, $6, $7,
        $8, $9, $10, $11, $12, $13,
        $14, $15, $16, $17, $18, $19
      ) AS new_comment_id`,
      [
        praj_project_number,
        praj_document_number,
        praj_revision_number,
        supplier_name,
        supplier_po_number,
        customer_document_number || "NA",
        customer_revision || "NA",
        page_sheet,
        comment_id,
        actual_extracted_comment,
        snapshot_file,
        name_of_person_commented,
        date_of_comment || null,
        time_of_comment || null,
        comment_color,
        clientCommentStr,
        comment_category,
        handwrittenStr,
        extraction_confidence_percent
      ]
    );

    res.status(201).json({
      message: "Comment inserted successfully",
      comment_id: result.rows[0].new_comment_id
    });

  } catch (err) {
    console.error("Error creating comment:", err);
    res.status(500).json({
      message: "Server error creating comment",
      error: err.message
    });
  }
};


// GET Comments by Document (using function)
module.exports.getCommentsByDocument = async (req, res) => {
  try {
    const { documentId } = req.params;

    if (!documentId || isNaN(documentId)) {
      return res.status(400).json({ message: "Invalid documentId" });
    }

    const result = await pool.query(
      `SELECT * FROM get_comments_by_document($1::BIGINT)`,
      [documentId]
    );

    res.json(result.rows);

  } catch (err) {
    console.error("Error fetching comments:", err);
    res.status(500).json({ message: "Server error fetching comments" });
  }
};


// GET Single Comment (using function)
module.exports.getCommentById = async (req, res) => {
  try {
    const { id } = req.params;

    if (!id || isNaN(id)) {
      return res.status(400).json({ message: "Invalid comment id" });
    }

    const result = await pool.query(
      `SELECT * FROM get_comment_by_id($1::BIGINT)`,
      [id]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ message: "Comment not found" });
    }

    res.json(result.rows[0]);

  } catch (err) {
    console.error("Error fetching comment:", err);
    res.status(500).json({ message: "Server error fetching comment" });
  }
};


//  UPDATE Comment (using function)
module.exports.updateComment = async (req, res) => {
  try {
    const { id } = req.params;

    if (!id || isNaN(id)) {
      return res.status(400).json({ message: "Invalid comment id" });
    }

    const {
      actual_extracted_comment,
      comment_color,
      comment_category,
      is_client_comment,
      is_handwritten
    } = req.body;

    const clientCommentBool =
      is_client_comment === true || is_client_comment === "Y";

    const handwrittenBool =
      is_handwritten === true || is_handwritten === "Y";

    await pool.query(
      `SELECT update_comment($1, $2, $3, $4, $5, $6)`,
      [
        id,
        actual_extracted_comment,
        comment_color,
        comment_category,
        clientCommentBool,
        handwrittenBool
      ]
    );

    res.json({ message: "Comment updated successfully" });

  } catch (err) {
    console.error("Error updating comment:", err);
    res.status(500).json({ message: "Server error updating comment" });
  }
};


//  DELETE Comment (using function)
module.exports.deleteComment = async (req, res) => {
  try {
    const { id } = req.params;

    if (!id || isNaN(id)) {
      return res.status(400).json({ message: "Invalid comment id" });
    }

    await pool.query(
      `SELECT delete_comment($1::BIGINT)`,
      [id]
    );

    res.json({ message: "Comment deleted successfully" });

  } catch (err) {
    console.error("Error deleting comment:", err);
    res.status(500).json({ message: "Server error deleting comment" });
  }
};