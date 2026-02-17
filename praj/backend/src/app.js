const express = require("express");
const path = require("path");
const session = require("express-session");
const passport = require("passport");
const LocalStrategy = require("passport-local").Strategy;

const User = require("./models/userModel");
const userRoutes = require("./routes/userRoutes");

const app = express();
const port = 8080;
const { connectDB, sequelize } = require("./config/db");
connectDB();


// Config
app.set("views", path.join(__dirname, "views"));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static("public"));
app.use(express.json()); 


// Session setup
const sessionConfig = {
  secret: "thisshouldbeabettersecret",
  resave: false,
  saveUninitialized: false,
  cookie: {
    httpOnly: true,
    expires: Date.now() + 1000 * 60 * 60 * 24 * 7, // 1 week
    maxAge: 1000 * 60 * 60 * 24 * 7,
  },
};
app.use(session(sessionConfig));

// Passport setup
app.use(passport.initialize());
app.use(passport.session());


passport.use(
  new LocalStrategy(
    {
      usernameField: "email",
      passwordField: "password",
    },
    async (email, password, done) => {
      try {
        console.log("Login attempt:");
        console.log("Email:", email);
        console.log("Password received:", password);

        const user = await User.findOne({ where: { email } });

        if (!user) {
          console.log("User not found");
          return done(null, false, { message: "Incorrect email." });
        }

        const isValid = await user.validatePassword(password);

        if (!isValid) {
          console.log("Password mismatch");
          return done(null, false, { message: "Incorrect password." });
        }

        console.log("✅ Login successful");
        return done(null, user);

      } catch (error) {
        console.error("Login error:", error);
        return done(error);
      }
    }
  )
);


passport.serializeUser((user, done) => done(null, user.id));
passport.deserializeUser(async (id, done) => {
  try {
    const user = await User.findByPk(id);
    done(null, user);
  } catch (err) {
    done(err);
  }
});

// Middleware
app.use((req, res, next) => {
  res.locals.currentUser = req.user;
  res.locals.returnTo = req.session.returnTo;
  next();
});

// Routes
app.use("/", userRoutes);

app.listen(port, () => {
  console.log(`Server listening on port ${port}`);
});