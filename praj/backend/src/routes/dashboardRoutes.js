const express = require('express');
const router = express.Router();
const dashboardController = require('../controllers/dashboardController');

router.get('/stats', dashboardController.getStats);
router.get('/crs-status', dashboardController.getCrsStatus);
router.get('/categories', dashboardController.getCategories);
router.get('/engineer-workload', dashboardController.getEngineerWorkload);
router.get('/trends', dashboardController.getTrends);

module.exports = router;