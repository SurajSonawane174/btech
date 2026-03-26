const fs = require("fs");
const path = require("path");
const { execFile } = require("child_process");
const { promisify } = require("util");
const pool = require("../../db/db");

const execFileAsync = promisify(execFile);

// In-memory review fields used by CRS review grid (demo-friendly, no schema change required).
const reviewState = new Map();

function toYN(value, truthy = "Y", falsy = "N") {
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["y", "yes", "true", "1"].includes(normalized)) return truthy;
  }
  if (value === true || value === 1) return truthy;
  return falsy;
}

function normalizeStatus(value) {
  if (!value) return "Open";
  const s = String(value).trim();
  if (s === "Closed") return "Closed";
  if (s === "In Progress") return "In Progress";
  return "Open";
}

function getReviewFor(commentId) {
  return reviewState.get(String(commentId)) || {};
}

function buildDrawingStatus(total, open, closed) {
  if (total === 0) return "Open";
  if (closed === total) return "Closed";
  if (open === total) return "Open";
  return "In Progress";
}

function getAiEnginePaths() {
  const rootDir = path.resolve(__dirname, "../../../");
  const aiEngineDir = path.join(rootDir, "ai-engine");
  const uploadDir = path.join(aiEngineDir, "test_pdfs");
  const outputDir = path.join(aiEngineDir, "output");
  return { rootDir, aiEngineDir, uploadDir, outputDir };
}

module.exports.uploadFiles = async (req, res) => {
  try {
    if (!req.files || req.files.length === 0) {
      return res.status(400).json({ message: "No file uploaded" });
    }

    const pdf = req.files.find((f) => f.mimetype === "application/pdf") || req.files[0];

    req.session.latestUpload = {
      absolutePath: pdf.path,
      fileName: pdf.filename,
      originalName: pdf.originalname,
      uploadedAt: new Date().toISOString(),
    };

    return res.json({
      message: "File uploaded",
      file: {
        name: pdf.originalname,
        storedAs: pdf.filename,
      },
    });
  } catch (error) {
    console.error("Upload failed:", error);
    return res.status(500).json({ message: "Upload failed", error: error.message });
  }
};

module.exports.scanLatestUpload = async (req, res) => {
  try {
    const upload = req.session.latestUpload;
    if (!upload || !upload.absolutePath) {
      return res.status(400).json({ message: "No uploaded file found. Upload a PDF first." });
    }

    const { aiEngineDir } = getAiEnginePaths();
    const pythonCmd = process.env.PYTHON_BIN || "python";

    await execFileAsync(
      pythonCmd,
      ["doc_process.py", "--input", upload.absolutePath],
      {
        cwd: aiEngineDir,
        env: process.env,
        maxBuffer: 1024 * 1024 * 10,
      }
    );

    const stem = path.parse(upload.fileName).name;
    const commentsPath = path.join(aiEngineDir, "output", stem, "comments.json");

    if (!fs.existsSync(commentsPath)) {
      return res.status(500).json({ message: "Extraction completed but comments.json was not found." });
    }

    const extracted = JSON.parse(fs.readFileSync(commentsPath, "utf-8"));
    if (!Array.isArray(extracted) || extracted.length === 0) {
      return res.json({
        message: "Scan complete. No comments found in this PDF.",
        drawingNo: stem,
        documentId: null,
        comments: [],
      });
    }

    const first = extracted[0];
    const prajDoc = first.praj_document_number || stem;
    const prajRev = first.praj_revision_number || "R0";
    const custDoc = first.customer_document_number || "NA";
    const custRev = first.customer_revision || "NA";

    const docResult = await pool.query(
      "SELECT get_or_create_document($1, $2, $3, $4) AS doc_id",
      [prajDoc, prajRev, custDoc, custRev]
    );

    const documentId = docResult.rows[0].doc_id;

    await pool.query("DELETE FROM comments WHERE document_id = $1", [documentId]);

    for (const item of extracted) {
      await pool.query(
        `SELECT insert_comment_from_json(
          $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16
        ) AS comment_id`,
        [
          item.praj_document_number || prajDoc,
          item.praj_revision_number || prajRev,
          item.customer_document_number || custDoc,
          item.customer_revision || custRev,
          String(item.page_sheet || ""),
          item.comment_id,
          item.actual_extracted_comment || "",
          item.snapshot_file || "",
          item.name_of_person_commented || "Unknown",
          item.date_of_comment || "NA",
          item.time_of_comment || "NA",
          item.comment_color || "Unknown",
          toYN(item.is_client_comment),
          item.comment_category || "technical",
          toYN(item.is_handwritten),
          Number(item.extraction_confidence_percent || 0),
        ]
      );
    }

    const insertedComments = await pool.query(
      "SELECT id, comment_id, page_sheet, actual_extracted_comment, comment_color FROM comments WHERE document_id = $1 ORDER BY id",
      [documentId]
    );

    return res.json({
      message: "Scan complete",
      drawingNo: prajDoc,
      documentId,
      comments: insertedComments.rows,
    });
  } catch (error) {
    console.error("Scan failed:", error);
    return res.status(500).json({ message: "Scan failed", error: error.message });
  }
};

module.exports.getDrawings = async (req, res) => {
  try {
    const drawingNo = (req.query.drawingNo || "").toLowerCase();
    const supplier = (req.query.supplier || "").toLowerCase();
    const statusFilter = req.query.status || "All";

    const query = `
      SELECT d.*, c.id AS comment_pk, c.comment_id
      FROM documents d
      LEFT JOIN comments c ON c.document_id = d.id
      ORDER BY d.id DESC, c.id ASC
    `;

    const { rows } = await pool.query(query);

    const grouped = new Map();
    for (const row of rows) {
      const docId = row.id;
      if (!grouped.has(docId)) {
        grouped.set(docId, {
          docId,
          id: row.praj_doc_number || row.praj_document_number || `DOC-${docId}`,
          doc: row.customer_document_number || "NA",
          sup: "Unknown",
          po: "NA",
          comments: [],
        });
      }
      if (row.comment_pk) grouped.get(docId).comments.push(row.comment_id);
    }

    let drawings = Array.from(grouped.values()).map((d) => {
      let closed = 0;
      for (const cid of d.comments) {
        const state = getReviewFor(cid);
        if (normalizeStatus(state.status) === "Closed") closed += 1;
      }
      const total = d.comments.length;
      const open = total - closed;
      const status = buildDrawingStatus(total, open, closed);

      return {
        id: d.id,
        doc: d.doc,
        sup: d.sup,
        po: d.po,
        tot: total,
        opn: open,
        cls: closed,
        status,
      };
    });

    drawings = drawings.filter((d) => {
      const byDrawing = !drawingNo || d.id.toLowerCase().includes(drawingNo);
      const bySupplier = !supplier || d.sup.toLowerCase().includes(supplier);
      const byStatus = statusFilter === "All" || d.status === statusFilter;
      return byDrawing && bySupplier && byStatus;
    });

    return res.json({ drawings, total: drawings.length });
  } catch (error) {
    console.error("Failed to fetch drawings:", error);
    return res.status(500).json({ message: "Failed to fetch drawings", error: error.message });
  }
};

module.exports.lookupCrs = async (req, res) => {
  try {
    const drawingNo = (req.query.drawingNo || "").toLowerCase();
    const supplier = (req.query.supplier || "").toLowerCase();
    const po = (req.query.po || "").toLowerCase();
    const statusFilter = req.query.status || "All";

    const drawingsResponse = await new Promise((resolve, reject) => {
      const fakeReq = { query: { drawingNo: "", supplier: "", status: "All" } };
      const fakeRes = {
        json: (payload) => resolve(payload),
        status: () => ({ json: (payload) => reject(new Error(payload.message || "Lookup failed")) }),
      };
      module.exports.getDrawings(fakeReq, fakeRes);
    });

    let results = drawingsResponse.drawings.map((d) => ({
      id: d.id,
      sup: d.sup,
      po: d.po,
      tot: d.tot,
      opn: d.opn,
      cls: d.cls,
      status: d.status,
    }));

    results = results.filter((r) => {
      const byDrawing = !drawingNo || r.id.toLowerCase().includes(drawingNo);
      const bySupplier = !supplier || r.sup.toLowerCase().includes(supplier);
      const byPo = !po || r.po.toLowerCase().includes(po);
      const byStatus = statusFilter === "All" || r.status === statusFilter;
      return byDrawing && bySupplier && byPo && byStatus;
    });

    return res.json({ results, total: results.length });
  } catch (error) {
    console.error("CRS lookup failed:", error);
    return res.status(500).json({ message: "CRS lookup failed", error: error.message });
  }
};

module.exports.getDrawingMetadata = async (req, res) => {
  try {
    const { drawingNo } = req.params;
    const { rows } = await pool.query("SELECT * FROM documents ORDER BY id DESC");

    const found = rows.find((d) => {
      const code = d.praj_doc_number || d.praj_document_number || "";
      return code === drawingNo;
    });

    if (!found) {
      return res.status(404).json({ message: "Drawing not found" });
    }

    const d = found;
    return res.json({
      docNo: d.praj_doc_number || d.praj_document_number || drawingNo,
      revision: d.praj_revision_number || "NA",
      custDocNo: d.customer_document_number || "NA",
      custRevision: d.customer_revision || "NA",
      supplier: "Unknown",
      po: "NA",
    });
  } catch (error) {
    console.error("Failed to fetch metadata:", error);
    return res.status(500).json({ message: "Failed to fetch metadata", error: error.message });
  }
};

module.exports.getDrawingComments = async (req, res) => {
  try {
    const { drawingNo } = req.params;

    const docResult = await pool.query("SELECT * FROM documents ORDER BY id DESC");
    const doc = docResult.rows.find((d) => {
      const code = d.praj_doc_number || d.praj_document_number || "";
      return code === drawingNo;
    });

    if (!doc) {
      return res.json([]);
    }

    const commentsResult = await pool.query(
      "SELECT * FROM comments WHERE document_id = $1 ORDER BY id",
      [doc.id]
    );

    const rows = commentsResult.rows.map((c, index) => {
      const extra = getReviewFor(c.comment_id);
      const snapshotUrl = c.snapshot_file
        ? `${process.env.API_BASE_URL || "http://localhost:8080"}/${String(c.snapshot_file).replace(/\\/g, "/")}`
        : "";

      return {
        sr: index + 1,
        doc: doc.praj_doc_number || doc.praj_document_number || drawingNo,
        rev: doc.praj_revision_number || "NA",
        cDoc: doc.customer_document_number || "NA",
        cRev: doc.customer_revision || "NA",
        page: c.page_sheet || "",
        cId: c.comment_id,
        comment: c.actual_extracted_comment,
        snapshotUrl,
        person: c.name_of_person_commented || "Unknown",
        date: c.comment_datetime ? new Date(c.comment_datetime).toISOString().slice(0, 10) : "NA",
        color: c.comment_color || "Unknown",
        client: c.is_client_comment ? "Y" : "N",
        cat: c.comment_category || "technical",
        hw: c.is_handwritten ? "Y" : "N",
        conf: c.extraction_confidence_percent ? Number(c.extraction_confidence_percent).toFixed(0) : "0",
        assignee: extra.assignee || "Unassigned",
        target: extra.target || "",
        crs: `${drawingNo}-${index + 1}`,
        res: extra.resolution || "",
        status: normalizeStatus(extra.status),
        ev: extra.evidence || "",
      };
    });

    return res.json(rows);
  } catch (error) {
    console.error("Failed to fetch drawing comments:", error);
    return res.status(500).json({ message: "Failed to fetch drawing comments", error: error.message });
  }
};

module.exports.updateDrawingComment = async (req, res) => {
  try {
    const { commentId } = req.params;
    const { assignee, target, resolution, status, evidence } = req.body;

    reviewState.set(String(commentId), {
      assignee: assignee || "Unassigned",
      target: target || "",
      resolution: resolution || "",
      status: normalizeStatus(status),
      evidence: evidence || "",
    });

    return res.json({ message: "Comment review data updated" });
  } catch (error) {
    console.error("Failed to update review comment:", error);
    return res.status(500).json({ message: "Failed to update review comment", error: error.message });
  }
};

function toCsv(rows, headers) {
  const head = headers.join(",");
  const body = rows
    .map((row) =>
      headers
        .map((h) => {
          const value = row[h] === undefined || row[h] === null ? "" : String(row[h]);
          return `"${value.replace(/"/g, '""')}"`;
        })
        .join(",")
    )
    .join("\n");
  return `${head}\n${body}`;
}

module.exports.exportLookup = async (req, res) => {
  try {
    const lookupPayload = await new Promise((resolve, reject) => {
      const fakeRes = {
        json: (payload) => resolve(payload),
        status: () => ({ json: (payload) => reject(new Error(payload.message || "Export failed")) }),
      };
      module.exports.lookupCrs(req, fakeRes);
    });

    const csv = toCsv(lookupPayload.results, ["id", "sup", "po", "tot", "opn", "cls", "status"]);
    res.setHeader("Content-Type", "text/csv");
    res.setHeader("Content-Disposition", "attachment; filename=crs-results.csv");
    return res.send(csv);
  } catch (error) {
    console.error("Export failed:", error);
    return res.status(500).json({ message: "Export failed", error: error.message });
  }
};

module.exports.exportDrawing = async (req, res) => {
  try {
    const { drawingNo, format } = req.params;

    const fakeReq = { params: { drawingNo } };
    const comments = await new Promise((resolve, reject) => {
      const fakeRes = {
        json: (payload) => resolve(payload),
        status: () => ({ json: (payload) => reject(new Error(payload.message || "Export failed")) }),
      };
      module.exports.getDrawingComments(fakeReq, fakeRes);
    });

    const csv = toCsv(comments, [
      "sr", "doc", "rev", "cDoc", "cRev", "page", "cId", "comment", "person", "date", "color", "client", "cat", "hw", "conf", "assignee", "target", "crs", "res", "status", "ev",
    ]);

    const ext = format === "pdf" ? "pdf" : "csv";
    res.setHeader("Content-Type", "text/csv");
    res.setHeader("Content-Disposition", `attachment; filename=${drawingNo}-crs.${ext}`);
    return res.send(csv);
  } catch (error) {
    console.error("Drawing export failed:", error);
    return res.status(500).json({ message: "Drawing export failed", error: error.message });
  }
};

module.exports.getEngineers = async (_req, res) => {
  return res.json([
    { id: 1, name: "Unassigned" },
    { id: 2, name: "Process Engineer" },
    { id: 3, name: "Mechanical Reviewer" },
    { id: 4, name: "Electrical Reviewer" },
  ]);
};

module.exports.getUploadDirectory = () => {
  return getAiEnginePaths().uploadDir;
};

module.exports.getOutputDirectory = () => {
  return getAiEnginePaths().outputDir;
};
