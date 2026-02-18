import { useState } from "react";
import api from "../api/axios";

export default function FileUpload() {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);

  const uploadFiles = async () => {
    if (!files.length) return alert("Select files first");

    const formData = new FormData();
    for (let file of files) {
      formData.append("files", file);
    }

    try {
      setLoading(true);
      await api.post("/upload", formData);
      alert("Upload successful");
    } catch (err) {
      alert("Upload failed");
    } finally {
      setLoading(false);
    }
  };

  const scanFiles = async () => {
    try {
      setLoading(true);
      await api.post("/scan");
      alert("Scan completed");
    } catch (err) {
      alert("Scan failed");
    } finally {
      setLoading(false);
    }
  };

  const exportExcel = async () => {
    const res = await api.get("/export/excel", {
      responseType: "blob",
    });

    const url = window.URL.createObjectURL(new Blob([res.data]));
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", "output.xlsx");
    document.body.appendChild(link);
    link.click();
  };

  const exportJSON = async () => {
    const res = await api.get("/export/json");
    const blob = new Blob([JSON.stringify(res.data)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);

    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", "output.json");
    document.body.appendChild(link);
    link.click();
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-100 to-gray-200 px-4">
      <div className="bg-white w-full max-w-2xl rounded-xl shadow-xl p-8 space-y-6">

        <h2 className="text-2xl font-bold text-center text-gray-800">
          PDF Comment Scanner
        </h2>

        {/* File Input */}
        <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-blue-500 transition">
          <input
            type="file"
            multiple
            accept="application/pdf"
            onChange={(e) => setFiles(e.target.files)}
            className="hidden"
            id="fileUpload"
          />
          <label
            htmlFor="fileUpload"
            className="cursor-pointer text-gray-600 font-medium"
          >
            Click to select PDF files
          </label>

          {files.length > 0 && (
            <p className="mt-3 text-sm text-gray-500">
              {files.length} file(s) selected
            </p>
          )}
        </div>

        {/* Buttons */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">

          <button
            onClick={uploadFiles}
            className="bg-green-600 hover:bg-green-700 text-white font-semibold py-2 rounded-md transition duration-300 shadow-md hover:shadow-lg"
          >
            Upload
          </button>

          <button
            onClick={scanFiles}
            className="bg-yellow-500 hover:bg-yellow-600 text-white font-semibold py-2 rounded-md transition duration-300 shadow-md hover:shadow-lg"
          >
            Scan
          </button>

          <button
            onClick={exportExcel}
            className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 rounded-md transition duration-300 shadow-md hover:shadow-lg"
          >
            Excel
          </button>

          <button
            onClick={exportJSON}
            className="bg-purple-600 hover:bg-purple-700 text-white font-semibold py-2 rounded-md transition duration-300 shadow-md hover:shadow-lg"
          >
            JSON
          </button>

        </div>

        {loading && (
          <div className="text-center text-gray-500 animate-pulse">
            Processing...
          </div>
        )}

      </div>
    </div>
  );
}
