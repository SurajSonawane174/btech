const express = require("express");
const multer = require("multer");
const path = require("path"); // ✅ ADD THIS
const { drawingController } = require("../controllers/drawingController");

const router = express.Router();

// ✅ multer storage with extension
const storage = multer.diskStorage({
  destination: function (req, file, cb) {
    cb(null, "uploads/");
  },
  filename: function (req, file, cb) {
    const ext = path.extname(file.originalname); // now works
    const uniqueName = Date.now() + ext;
    cb(null, uniqueName);
  }
});

const upload = multer({ storage });

router.post("/process-drawing", upload.array("files"), drawingController);

module.exports = router;