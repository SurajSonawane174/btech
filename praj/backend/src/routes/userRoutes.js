const express = require("express");
const router = express.Router();
const passport = require("passport");
const user = require("../controllers/userController");
const {isLoggedIn}  = require("../middleware/auth")

// Register
router.post("/register", user.register);

// Login
router.post(
    "/login",
    passport.authenticate("local", {
        failureMessage: true,
    }),
    user.login
);

// Logout (protected)
router.get("/logout", isLoggedIn, user.logout);

// Profile (protected)
router.get("/profile", isLoggedIn, user.getProfile);


module.exports = router;