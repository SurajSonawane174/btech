const express = require("express");
const router = express.Router();
const commentController = require("../controllers/commentController");
const { isLoggedIn } = require("../middleware/auth");

// router.use(isLoggedIn); // Protect all comment routes

router.post("/new", commentController.createComment);
router.get("/document/:documentId", commentController.getCommentsByDocument);//to get all the comments for that doc number  
router.get("/:id", commentController.getCommentById);
router.put("/:id", commentController.updateComment);
router.delete("/:id", commentController.deleteComment);

module.exports = router;