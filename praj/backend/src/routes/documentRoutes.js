const express = require("express");
const router = express.Router();
const documentController = require("../controllers/documentController");
const { isLoggedIn } = require("../middleware/auth");

// router.use(isLoggedIn); // Protect all document routes



// 1. STATIC ROUTES (Must go first!)

// Get all documents across the entire system
router.get("/", documentController.getAllDocuments);

// Get filtered lists
router.get("/released", documentController.getAllReleasedDocuments);
router.get("/unreleased", documentController.getAllUnreleasedDocuments);

// Create a new document (or get it if it already exists)
router.post("/", documentController.createOrGetDocument);

// 2. DYNAMIC ROUTES (Using :id as praj_document_number)

// Get a single document by its document number (e.g., DWG099)
router.get("/:id", documentController.getDocumentById);

// Update document metadata
router.put("/:id", documentController.updateDocument);

// Delete a document (and cascade delete its comments)
router.delete("/:id", documentController.deleteDocument);

// 3. ACTION ROUTES 

// Change a document's status to released
router.put("/:id/release", documentController.releaseDocument);

module.exports = router;