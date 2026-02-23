require("dotenv").config({
  path: require("path").resolve(__dirname, "../.env"),
});

const pool = require("./pool");

async function testCommentInsert() {
  try {
    console.log("Testing comment insertion...\n");

    const result = await pool.query(
      `SELECT insert_comment_from_json(
		  $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16
		) AS comment_id`,
      [
        "PRJ001",
        "RevA",
        "NA",
        "NA",
        "1",
        "PRJ001-DWG001-001-013-001",
        "Increase bolt diameter to 12mm",
        "output/sample.png",
        "Unknown",
        "NA",
        "NA",
        "Unknown",
        "Y",
        "technical",
        "N",
        100,
      ],
    );

    const newCommentId = result.rows[0].comment_id;
    console.log("Inserted Comment ID:", newCommentId);

    // 🔎 Fetch all comments for this document
    const fetchResult = await pool.query(
      `
		SELECT c.*, d.praj_doc_number, d.praj_revision_number
		FROM comments c
		JOIN documents d ON c.document_id = d.id
		WHERE d.praj_doc_number = $1
		  AND d.praj_revision_number = $2
		`,
      ["PRJ001", "RevA"],
    );

    console.log("\nComments for PRJ001 RevA:");
    console.table(fetchResult.rows);
  } catch (err) {
    console.error("Error:", err);
  } finally {
    await pool.end();
  }
}

testCommentInsert();
