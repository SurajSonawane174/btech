require("dotenv").config();
const pool = require("./pool");

async function testDB() {
  try {
    console.log("From test:", process.env.DATABASE_URL);
    const result = await pool.query("SELECT NOW()");
    console.log("Connected:", result.rows[0]);
  } catch (err) {
    console.error("Error:", err);
  }
}

testDB();
