const express = require("express");
const path = require("path");
const fs = require("fs");
const multer = require("multer");
const workflow = require("../controllers/workflowController");

const router = express.Router();

const uploadDir = workflow.getUploadDirectory();
fs.mkdirSync(uploadDir, { recursive: true });

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, uploadDir),
  filename: (_req, file, cb) => {
    const ts = Date.now();
    const ext = path.extname(file.originalname);
    const base = path.basename(file.originalname, ext)
      .replace(/\s+/g, "_")
      .replace(/[^a-zA-Z0-9._-]/g, "");
    cb(null, `${base}_${ts}${ext}`);
  },
});

const upload = multer({ storage });

router.post("/upload", upload.array("files", 10), workflow.uploadFiles);
router.post("/scan", workflow.scanLatestUpload);

router.get("/drawings", workflow.getDrawings);
router.get("/crs/lookup", workflow.lookupCrs);
router.get("/crs/export", workflow.exportLookup);

router.get("/crs/drawing/:drawingNo/metadata", workflow.getDrawingMetadata);
router.get("/crs/drawing/:drawingNo/comments", workflow.getDrawingComments);
router.patch("/crs/drawing/:drawingNo/comments/:commentId", workflow.updateDrawingComment);
router.get("/crs/drawing/:drawingNo/export/:format", workflow.exportDrawing);

router.get("/engineers", workflow.getEngineers);

module.exports = router;
