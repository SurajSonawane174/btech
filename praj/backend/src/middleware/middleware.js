module.exports.isLoggedIn = (req, res, next) => {
    if (!req.isAuthenticated()) {
        req.session.returnTo = req.originalUrl;
        return res.status(401).json({ 
            error: 'You must be signed in first!' 
        });
    }
    next();
};