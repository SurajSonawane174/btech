require("dotenv").config({
  path: require("path").resolve(__dirname, "../.env"),
});

const pool = require("./pool");

async function testCommentInsert() {
  try {
    console.log("Testing comment insertion...\n");

    const result = await pool.query(
      `SELECT insert_comment_from_json(
        $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19
      ) AS comment_id`,
      [
        "PRJ001", // p_praj_project_number
        "PRJ001-DWG001", // p_praj_document_number
        "RevA", // p_praj_revision_number
        "Supplier ABC", // p_supplier_name
        "PO-12345", // p_supplier_po_number
        "NA", // p_customer_document_number
        "NA", // p_customer_revision
        "1", // p_page_sheet
        "PRJ001-DWG001-001-013-001", // p_comment_id
        "Increase bolt diameter to 12mm", // p_actual_extracted_comment
        "output/sample.png", // p_snapshot_file
        "Unknown", // p_name_of_person_commented
        "NA", // p_date_of_comment
        "NA", // p_time_of_comment
        "Unknown", // p_comment_color
        "Y", // p_is_client_comment
        "technical", // p_comment_category
        "N", // p_is_handwritten
        100, // p_extraction_confidence_percent
      ],
    );

    const newCommentId = result.rows[0].comment_id;
    console.log("Inserted Comment ID:", newCommentId);

    // 🔎 Fetch all comments for this document
    const fetchResult = await pool.query(
      `
      SELECT c.*, 
             d.praj_project_number,
             d.praj_document_number, 
             d.praj_revision_number,
             d.supplier_name,
             d.supplier_po_number
      FROM comments c
      JOIN documents d ON c.document_id = d.id
      WHERE d.praj_project_number  = $1
        AND d.praj_document_number = $2
        AND d.praj_revision_number = $3
        AND d.supplier_name        = $4
        AND d.supplier_po_number   = $5
      `,
      [
        "PRJ001", // praj_project_number
        "PRJ001-DWG001", // praj_document_number
        "RevA", // praj_revision_number
        "Supplier ABC", // supplier_name
        "PO-12345", // supplier_po_number
      ],
    );

    console.log("\nComments for PRJ001 / PRJ001-DWG001 / RevA:");
    console.table(fetchResult.rows);
  } catch (err) {
    console.error("Error:", err);
  } finally {
    await pool.end();
  }
}

testCommentInsert();
