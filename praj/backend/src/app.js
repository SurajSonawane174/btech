require("dotenv").config();
const express = require("express");
const session = require("express-session");
const passport = require("passport");
const LocalStrategy = require("passport-local").Strategy;
const bcrypt = require("bcrypt");
const cors = require("cors");
const path = require("path");
const pool = require("../db/db");
const userRoutes = require("./routes/userRoutes");
const documentRoutes = require("./routes/documentRoutes");
const commentRoutes = require("./routes/commentRoutes");
const workflowRoutes = require("./routes/workflowRoutes");
const { isLoggedIn } = require("./middleware/auth");

const app = express();
const port = 8080;

pool.connect()
  .then(() => console.log("Database Connected"))
  .catch(err => console.error("DB Error:", err));

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

app.use(cors({
  origin: "http://localhost:5173",
  credentials: true,
}));

app.use(session({
  secret: process.env.SESSION_SECRET || "thisshouldbeabettersecret",
  resave: false,
  saveUninitialized: false,
  cookie: {
    httpOnly: true,
    maxAge: 1000 * 60 * 60 * 24 * 7,
    sameSite: "lax",
  },
}));

app.use(passport.initialize());
app.use(passport.session());

passport.use(new LocalStrategy(
  { usernameField: "email", passwordField: "password" },
  async (email, password, done) => {
    try {
      const result = await pool.query("SELECT * FROM get_user_by_email($1)", [email]);
      if (result.rows.length === 0) return done(null, false, { message: "Incorrect email" });
      const user = result.rows[0];
      const valid = await bcrypt.compare(password, user.password_hash);
      if (!valid) return done(null, false, { message: "Incorrect password" });
      return done(null, user);
    } catch (err) {
      return done(err);
    }
  }
));

passport.serializeUser((user, done) => done(null, user.id));
passport.deserializeUser(async (id, done) => {
  try {
    const result = await pool.query("SELECT * FROM get_user_by_id($1)", [id]);
    if (result.rows.length === 0) return done(null, false);
    done(null, result.rows[0]);
  } catch (err) {
    done(err);
  }
});

// =========================================
// DASHBOARD ROUTES (built from real DB data)
// =========================================
app.get("/api/dashboard/stats", isLoggedIn, async (req, res) => {
  try {
    const docsResult = await pool.query("SELECT COUNT(*) FROM documents");
    const commentsResult = await pool.query("SELECT COUNT(*) FROM comments");
    const totalDrawings = parseInt(docsResult.rows[0].count);
    const commentsExtracted = parseInt(commentsResult.rows[0].count);

    res.json({
      totalDrawings,
      totalDrawingsTrend: "All time",
      commentsExtracted,
      commentsExtractedTrend: "All time",
      pendingReviews: totalDrawings, // all docs are pending until closed
      pendingReviewsTrend: "Needs action",
      overdueItems: 0,
      overdueItemsTrend: "None overdue",
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ message: "Failed to fetch stats" });
  }
});

app.get("/api/dashboard/recent-drawings", isLoggedIn, async (req, res) => {
  try {
    const result = await pool.query(`
      SELECT d.id AS doc_id, d.praj_doc_number, d.praj_document_number,
             COUNT(c.id) AS comment_count
      FROM documents d
      LEFT JOIN comments c ON c.document_id = d.id
      GROUP BY d.id
      ORDER BY d.id DESC
      LIMIT 10
    `);

    const drawings = result.rows.map(row => ({
      id: row.praj_doc_number || row.praj_document_number || `DOC-${row.doc_id}`,
      sup: "Unknown",
      po: "NA",
      com: parseInt(row.comment_count),
      status: "Open",
    }));

    res.json(drawings);
  } catch (err) {
    console.error(err);
    res.status(500).json({ message: "Failed to fetch recent drawings" });
  }
});

app.get("/api/dashboard/crs-status", isLoggedIn, async (req, res) => {
  try {
    const result = await pool.query("SELECT COUNT(*) FROM comments");
    const total = parseInt(result.rows[0].count);
    res.json({ total, closed: 0, inProgress: 0, open: total });
  } catch (err) {
    console.error(err);
    res.status(500).json({ message: "Failed to fetch CRS status" });
  }
});

app.get("/api/dashboard/categories", isLoggedIn, async (req, res) => {
  try {
    const result = await pool.query(`
      SELECT comment_category, COUNT(*) as cnt
      FROM comments
      GROUP BY comment_category
    `);
    const total = result.rows.reduce((s, r) => s + parseInt(r.cnt), 0) || 1;
    const colors = ["bg-red-500", "bg-amber-500", "bg-blue-500", "bg-emerald-500"];
    const categories = result.rows.map((row, i) => {
      const pct = Math.round((parseInt(row.cnt) / total) * 100);
      return {
        label: row.comment_category || "Unknown",
        value: parseInt(row.cnt),
        width: `w-[${pct}%]`,
        color: colors[i % colors.length],
      };
    });
    res.json(categories);
  } catch (err) {
    console.error(err);
    res.status(500).json({ message: "Failed to fetch categories" });
  }
});

app.get("/api/dashboard/engineer-workload", isLoggedIn, async (req, res) => {
  // Static for now — extend when you add engineer assignment to DB
  res.json([
    { name: "Unassigned", count: 0 },
  ]);
});

// =========================================
// ROUTES
// =========================================
app.use("/api/users", userRoutes);
app.use("/api/documents", documentRoutes);
app.use("/api/comments", commentRoutes);
app.use("/api", workflowRoutes); // FIX: only mount once, at /api

app.use("/output", express.static(path.resolve(__dirname, "../../ai-engine/output")));

app.listen(port, () => {
  console.log(`Server running on port ${port}`);
});