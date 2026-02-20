const passport = require('passport');
const pool = require('../../db/db');
const bcrypt = require('bcrypt');


module.exports.register = async (req, res) => {
    try {
        const { username, email, password, role } = req.body;

        const existing = await pool.query(
            'SELECT * FROM get_user_by_email($1)',
            [email]
        );

        if (existing.rows.length > 0) {
            return res.status(400).json({ message: 'User exists' });
        }

        const hashedPassword = await bcrypt.hash(password, 10);

        await pool.query(
            'SELECT create_user($1, $2, $3, $4)',
            [username, email, hashedPassword, role]
        );

        res.status(201).json({ message: 'User registered' });

    } catch (err) {
        res.status(500).json({ message: 'Server error' });
    }
};


// LOGIN 
module.exports.login = (req, res, next) => {
    passport.authenticate('local', (err, user, info) => {
        if (err) return next(err);

        if (!user) {
            return res.status(400).json({ message: info.message });
        }

        req.login(user, (err) => {
            if (err) return next(err);

            return res.json({
                message: 'Login successful',
                user
            });
        });
    })(req, res, next);
};


// LOGOUT
module.exports.logout = (req, res, next) => {
    req.logout(function (err) {
        if (err) return next(err);

        req.session.destroy(() => {
            res.clearCookie('connect.sid');
            res.json({ message: 'Logged out successfully' });
        });
    });
};


// GET PROFILE 
module.exports.getProfile = (req, res) => {
    if (!req.isAuthenticated()) {
        return res.status(401).json({ message: 'Unauthorized' });
    }

    res.json(req.user);
};