const express = require("express");
const router = express.Router();
const documentController = require("../controllers/documentController");
const { isLoggedIn } = require("../middleware/auth");

// router.use(isLoggedIn); // Protect all document routes


// CREATE / GET Document
// POST /api/documents
router.post('/', documentController.createOrGetDocument);

// READ All Documents
// GET /api/documents
router.get('/', documentController.getAllDocuments);

// READ Single Document by ID
// GET /api/documents/:id
router.get('/:id', documentController.getDocumentById);

// UPDATE Document
// PUT /api/documents/:id
router.put('/:id', documentController.updateDocument);

// DELETE Document
// DELETE /api/documents/:id
router.delete('/:id', documentController.deleteDocument);

module.exports = router;