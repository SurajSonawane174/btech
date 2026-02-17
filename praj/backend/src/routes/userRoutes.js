const express = require("express");
const router = express.Router();
const passport = require("passport");
const user = require("../controllers/userController");

// Register route
router.route("/register")
    .post(user.register);   // POST /api/users/register

// Login route
router.route("/login")
    .post(passport.authenticate("local", {
        failureMessage: true,
    }), user.login);  

// Logout route
router.route("/logout")
    .get(user.logout);  

// Protected profile route
router.route("/profile")
    .get((req, res) => {
        if (!req.isAuthenticated()) {
            return res.status(401).json({ error: "You must be signed in first!" });
        }
        res.json({ user: req.user });
    });

module.exports = router;