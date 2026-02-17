const { Sequelize } = require("sequelize");
require("dotenv").config();

const sequelize = new Sequelize(
  process.env.DB_NAME,
  process.env.DB_USER,
  process.env.DB_PASS,
  {
    host: process.env.DB_HOST,
    dialect: "mysql",
    logging: false,
  }
);

const connectDB = async () => {
  try {
    await sequelize.authenticate();
    console.log("✅ Connected to SQL database successfully.");
    await sequelize.sync({ alter: true });
  } catch (error) {
    console.error("❌ Unable to connect to the database:", error);
  }
};

module.exports = { sequelize, connectDB };