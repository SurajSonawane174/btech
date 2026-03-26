require("dotenv").config({
  path: require("path").resolve(__dirname, "../.env"),
});

const pool = require("./pool");

async function testDB() {
  try {
    console.log("Testing DB connection...");

    // 1️⃣ Create user
    const createResult = await pool.query(
      "SELECT create_user($1, $2, $3, $4) AS user_id",
      [
        "model_test",
        "model_test@email.com",
        "hashed_password_123", // In real app use bcrypt
        "reviewer",
      ],
    );

    const newUserId = createResult.rows[0].user_id;
    console.log("User created with ID:", newUserId);

    // 2️⃣ Fetch user by ID
    const getResult = await pool.query("SELECT * FROM get_user_by_id($1)", [
      newUserId,
    ]);

    console.log("Fetched user:", getResult.rows[0]);
  } catch (err) {
    console.error("Error:", err);
  } finally {
    await pool.end(); // close connection
  }
}

// testDB();
module.exports = testDB;
