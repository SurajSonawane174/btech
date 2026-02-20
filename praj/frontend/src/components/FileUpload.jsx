import { useState, useRef } from "react";
import api from "../api/axios";

export default function FileUpload() {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);

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

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setDragOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const droppedFiles = Array.from(e.dataTransfer.files).filter(file => file.type === 'application/pdf');
    setFiles(droppedFiles);
  };

  const handleFileSelect = (e) => {
    const selectedFiles = Array.from(e.target.files);
    setFiles(selectedFiles);
  };

  const removeFile = (index) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4 py-8">
      <div className="bg-white w-full max-w-2xl rounded-lg shadow-lg p-8 space-y-6 border border-gray-200">

        <h2 className="text-3xl font-bold text-center text-gray-800 mb-8">
          PDF Document Scanner
        </h2>

        {/* File Input with Drag and Drop */}
        <div 
          className={`border-2 border-dashed rounded-lg p-8 text-center transition-all duration-300 cursor-pointer ${
            dragOver 
              ? 'border-blue-500 bg-blue-50' 
              : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'
          }`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept="application/pdf"
            onChange={handleFileSelect}
            className="hidden"
          />
          <div className="text-5xl mb-4 text-gray-400">📄</div>
          <p className="text-lg text-gray-700 font-medium mb-2">
            Drag & drop PDF files here or click to browse
          </p>
          <p className="text-sm text-gray-500">
            Only PDF files are supported
          </p>
        </div>

        {/* File List */}
        {files.length > 0 && (
          <div className="space-y-2">
            <h3 className="text-lg font-semibold text-gray-700">Selected Files:</h3>
            {files.map((file, index) => (
              <div key={index} className="flex items-center justify-between bg-gray-50 p-3 rounded-lg border">
                <span className="text-sm text-gray-600">{file.name}</span>
                <button 
                  onClick={() => removeFile(index)}
                  className="text-red-500 hover:text-red-700 font-bold text-lg"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Buttons */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <button
            onClick={uploadFiles}
            disabled={loading || !files.length}
            className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-4 rounded-lg transition duration-300 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Upload
          </button>

          <button
            onClick={scanFiles}
            disabled={loading}
            className="bg-green-600 hover:bg-green-700 text-white font-semibold py-3 px-4 rounded-lg transition duration-300 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Scan
          </button>

          <button
            onClick={exportExcel}
            disabled={loading}
            className="bg-purple-600 hover:bg-purple-700 text-white font-semibold py-3 px-4 rounded-lg transition duration-300 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Excel
          </button>

          <button
            onClick={exportJSON}
            disabled={loading}
            className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 px-4 rounded-lg transition duration-300 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
          >
            JSON
          </button>
        </div>

        {loading && (
          <div className="text-center text-gray-500 flex items-center justify-center space-x-2">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500"></div>
            <span>Processing...</span>
          </div>
        )}

      </div>
    </div>
  );
}
