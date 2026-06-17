require("dotenv").config({
  path: require("path").resolve(__dirname, "../.env"),
});

const pool = require("./pool");

async function testGetCommentsByDocument() {
  try {
    console.log("Testing get_comments_by_document...\n");

    const documentId = 1; // 🔁 change this as needed

    const result = await pool.query(
      "SELECT * FROM get_comments_by_document($1::BIGINT)",
      [documentId],
    );

    if (result.rows.length === 0) {
      console.log("❌ No comments found for document ID:", documentId);
    } else {
      console.log(`✅ Found ${result.rows.length} comment(s):\n`);
      console.table(result.rows);
    }
  } catch (err) {
    console.error("Error:", err);
  } finally {
    await pool.end();
  }
}

testGetCommentsByDocument();
