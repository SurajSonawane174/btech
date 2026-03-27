import { exec } from "child_process";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import pool from "../../db/db.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Helper function to format dates correctly for PostgreSQL
const formatDateTimeForDB = (dateStr, timeStr) => {
  if (!dateStr || dateStr === "NA") return null;
  
  // Convert "18/02/2026" to "2026-02-18"
  if (dateStr.includes("/")) {
    const [day, month, year] = dateStr.split("/");
    const formattedDate = `${year}-${month}-${day}`;
    
    if (timeStr && timeStr !== "NA") {
      return `${formattedDate} ${timeStr}`;
    }
    return formattedDate;
  }
  return dateStr; 
};

export const drawingController = (req, res) => {
  try {
    console.log("🔥 CONTROLLER HIT");

    const files = req.files;

    if (!files || files.length === 0) {
      console.log(" No file uploaded");
      return res.status(400).json({ message: "No file uploaded" });
    }

    const file = files[0];
    const filePath = path.resolve(file.path);
    const fileName = path.parse(file.originalname).name;

    const nameParts = fileName.split("_");
    const req_project_number = nameParts[0] || "UNKNOWN_PRJ"; 

    const baseDir = path.resolve(__dirname, "../../../ai-engine");
    const pythonPath = path.join(baseDir, ".venv/bin/python");
    const scriptPath = path.join(baseDir, "doc_process.py");

    const command = `"${pythonPath}" "${scriptPath}" --input "${filePath}"`;

    exec(command, { cwd: baseDir }, async (error, stdout, stderr) => {

      if (error) {
        console.error(" Python Error:", error.message);
        return res.status(500).json({ message: "Python execution failed" });
      }

      try {
        const outputPath = path.resolve(
          __dirname,
          `../../../ai-engine/output/${fileName}/comments.json`
        );

        if (!fs.existsSync(outputPath)) {
          console.error(" JSON file not found!");
          return res.status(500).json({ message: "Output JSON not found" });
        }

        const rawData = fs.readFileSync(outputPath, "utf-8");
        const data = JSON.parse(rawData);

        console.log(`📊 Total comments extracted: ${data.length}`);

        const insertQuery = `
          SELECT insert_comment_from_json(
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
            $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22
          ) AS new_comment_id
        `;

        const insertedCommentsDisplay = []; 

        // Insert into database sequentially
        for (const comment of data) {
          
          const projectNum = comment.praj_document_number || req_project_number;
          const revisionNum = comment.praj_revision_number || "NA";
          const customerDocNum = comment.customer_document_number || "NA";
          const customerRev = comment.customer_revision || "NA";
          
          const formattedDateTime = formatDateTimeForDB(comment.date_of_comment, comment.time_of_comment);

          const values = [
            projectNum,                                 
            nameParts[2] || "UNKNOWN_DWG",              
            revisionNum,                                
            req.body.supplier_name || "NA",             
            req.body.supplier_po_number || "NA",        
            customerDocNum,                             
            customerRev,                                
            String(comment.page_sheet || "1"),          
            comment.comment_id,                         
            comment.actual_extracted_comment || "NA",   
            comment.snapshot_file || "NA",              
            comment.name_of_person_commented || "NA",   
            formattedDateTime,                          
            null,                                       
            comment.comment_color || "NA",              
            comment.is_client_comment || "N",           
            comment.comment_category || "technical",    
            comment.is_handwritten || "N",              
            comment.extraction_confidence_percent || 100, 
            req.body.assigned_to || null,               
            req.body.target_closure_date || null,       
            req.body.status || "Open"                   
          ];
          
          await pool.query(insertQuery, values);
          
          insertedCommentsDisplay.push({
            Comment_ID: comment.comment_id,
            Author: comment.name_of_person_commented,
            Text: comment.actual_extracted_comment.substring(0, 30) + "..." 
          });
        }
        
        console.log("\n✅ --- SUCCESSFULLY SAVED COMMENTS TO DATABASE --- ✅");
        console.table(insertedCommentsDisplay);
        console.log("----------------------------------------------------\n");

        // ✅ FIX: Returning the full 'data' array so your frontend receives all the comments
        return res.json({
          success: true,
          count: data.length,
          message: "Comments extracted and saved to database successfully",
          extractedComments: data  // <-- This restores the functionality you asked for!
        });

      } catch (err) {
        console.error("Data Processing/DB Error:", err);
        return res.status(500).json({ message: "Failed to read JSON or save to DB", error: err.message });
      }
    });

  } catch (err) {
    console.error(" Controller Error:", err);
    res.status(500).json({ message: "Server error" });
  }
};