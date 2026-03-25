const express = require("express");
const router = express.Router();
const documentController = require("../controllers/documentController");
const { isLoggedIn } = require("../middleware/auth");

router.use(isLoggedIn); // Protect all document routes

router.post("/", documentController.createOrGetDocument);
router.get("/", documentController.getAllDocuments);
router.get("/:id", documentController.getDocumentById);
router.put("/:id", documentController.updateDocument);
router.delete("/:id", documentController.deleteDocument);

module.exports = router;