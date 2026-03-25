module.exports.isLoggedIn = (req, res, next) => {
    if (req.isAuthenticated()) return next();

    req.session.returnTo = req.originalUrl;
    return res.status(401).json({
        success: false,
        message: "Authentication required"
    });
};