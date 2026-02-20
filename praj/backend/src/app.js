require("dotenv").config();
const express = require("express");
const session = require("express-session");
const passport = require("passport");
const LocalStrategy = require("passport-local").Strategy;
const bcrypt = require("bcrypt");
const cors = require("cors"); 
const pool = require("../db/db");
const userRoutes = require("./routes/userRoutes");

const app = express();
const port = 8080;

/* =========================================
   DATABASE
========================================= */
pool.connect()
  .then(() => console.log("Database Connected"))
  .catch(err => console.error(" DB Error:", err));

/* =========================================
   MIDDLEWARE
========================================= */
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

/* =========================================
   CORS (IMPORTANT FOR REACT FRONTEND)
========================================= */
app.use(cors({
  origin: "http://localhost:3000", // React frontend
  credentials: true               // Allow cookies/session
}));

/* =========================================
   SESSION
========================================= */
app.use(session({
  secret: process.env.SESSION_SECRET || "thisshouldbeabettersecret",
  resave: false,
  saveUninitialized: false,
  cookie: {
    httpOnly: true,
    maxAge: 1000 * 60 * 60 * 24 * 7, // 1 week
    sameSite: "lax"                  // Important for localhost
  }
}));

/* =========================================
   PASSPORT CONFIG
========================================= */
app.use(passport.initialize());
app.use(passport.session());

passport.use(new LocalStrategy(
  {
    usernameField: "email",
    passwordField: "password"
  },
  async (email, password, done) => {
    try {
      const result = await pool.query(
        "SELECT * FROM get_user_by_email($1)",
        [email]
      );

      if (result.rows.length === 0)
        return done(null, false, { message: "Incorrect email" });

      const user = result.rows[0];

      const valid = await bcrypt.compare(password, user.password_hash);

      if (!valid)
        return done(null, false, { message: "Incorrect password" });

      return done(null, user);

    } catch (err) {
      return done(err);
    }
  }
));

passport.serializeUser((user, done) => {
  done(null, user.id);
});

passport.deserializeUser(async (id, done) => {
  try {
    const result = await pool.query(
      "SELECT * FROM get_user_by_id($1)",
      [id]
    );

    if (result.rows.length === 0)
      return done(null, false);

    done(null, result.rows[0]);
  } catch (err) {
    done(err);
  }
});

/* =========================================
   ROUTES
========================================= */
app.use("/api/users", userRoutes);

/* =========================================
   SERVER
========================================= */
app.listen(port, () => {
  console.log(`🚀 Server running on port ${port}`);
});