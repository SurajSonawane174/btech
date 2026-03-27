import { exec } from "child_process";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

//  FIX __dirname for ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export const drawingController = (req, res) => {
  try {
    console.log(" CONTROLLER HIT");

    const files = req.files;

    if (!files || files.length === 0) {
      console.log(" No file uploaded");
      return res.status(400).json({ message: "No file uploaded" });
    }

    const file = files[0];
    const filePath = path.resolve(file.path);
    const fileName = path.parse(file.filename).name;

    console.log(" File received:", file.originalname);
    console.log(" Saved at:", filePath);

    //  Resolve AI eFngine path correctly
    const baseDir = path.resolve(__dirname, "../../../ai-engine");

    const pythonPath = path.join(baseDir, ".venv/bin/python");
    const scriptPath = path.join(baseDir, "doc_process.py");

    //  FINAL COMMAND
    const command = `"${pythonPath}" "${scriptPath}" --input "${filePath}"`;

    console.log("🚀 Running command:", command);

    exec(command, { cwd: baseDir }, (error, stdout, stderr) => {

      //  Python error
      if (error) {
        console.error(" Python Error:", error.message);
        console.error("STDERR:", stderr);
        return res.status(500).json({ message: "Python execution failed" });
      }

      console.log("Python script executed successfully");

      if (stdout) {
        console.log("📤 Python Output:", stdout);
      }

      try {
        // Output path (relative to backend root)
        const outputPath = path.resolve(
  __dirname,
  `../../../ai-engine/output/${fileName}/comments.json`
);

        console.log("📁 Looking for JSON at:", outputPath);

        if (!fs.existsSync(outputPath)) {
          console.error(" JSON file not found!");
          return res.status(500).json({ message: "Output JSON not found" });
        }

        const rawData = fs.readFileSync(outputPath, "utf-8");
        const data = JSON.parse(rawData);

        console.log(`📊 Total comments extracted: ${data.length}`);

        return res.json({
          success: true,
          count: data.length,
          extractedComments: data
        });

      } catch (err) {
        console.error("JSON Read Error:", err);
        return res.status(500).json({ message: "Failed to read output JSON" });
      }
    });

  } catch (err) {
    console.error(" Controller Error:", err);
    res.status(500).json({ message: "Server error" });
  }
};