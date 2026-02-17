const bcrypt = require('bcrypt');
const User = require('../models/userModel'); 
const passport = require('passport');

// 1. REGISTER USER
module.exports.register = async (req, res, next) => {
    try {
        const { email, password, fullName } = req.body;

        // Validation
        if (!email || !password || !fullName) {
            return res.status(400).json({ message: 'All fields are required' });
        }
        const existingUser = await User.findOne({ where: { email: email } });
        if (existingUser) {
            return res.status(400).json({ message: 'User already exists' });
        }

        const newUser = await User.create({
            email,
            password,
            fullName
        });

        req.login(newUser, err => {
            if (err) return next(err);
            
            const userResponse = newUser.toJSON();
            delete userResponse.password;

            res.status(201).json({ message: 'Welcome!', user: userResponse });
        });
    
    } catch (err) {
        console.error(err);
        res.status(500).json({ message: 'Server error' });
    }
};

// 2. LOGIN USER
module.exports.login = (req, res) => {
    res.json({ message: 'Welcome back!', user: req.user });
};

// 3. LOGOUT USER
module.exports.logout = (req, res, next) => {
    req.logout((err) => {
        if (err) return next(err);
        res.json({ message: 'Goodbye!' });
    });
};

// 4. GET PROFILE
module.exports.getProfile = async (req, res) => {
    try {
        const user = await User.findByPk(req.user.id, {
            attributes: ['id', 'email', 'fullName', 'monthlyBudget', 'currency']
        });

        if (!user) {
            return res.status(404).json({ message: 'User not found' });
        }

        res.json(user);
    } catch (err) {
        console.error(err);
        res.status(500).json({ message: 'Could not fetch profile' });
    }
};

// 5. UPDATE PROFILE
module.exports.updateProfile = async (req, res) => {
    try {
        const { fullName, monthlyBudget, currency } = req.body;

        const [updatedRows] = await User.update(
            { 

            },
            { 
                where: { id: req.user.id } 
            }
        );

        if (updatedRows === 0) {
            return res.status(400).json({ message: 'No changes made or user not found' });
        }

        res.json({ message: 'Profile updated successfully' });

    } catch (err) {
        console.error(err);
        res.status(500).json({ message: 'Could not update profile' });
    }
};