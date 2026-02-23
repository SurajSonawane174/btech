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
    <div className="bg-white w-full rounded-2xl shadow-xl p-10 space-y-8 border border-slate-100">
      <div className="text-center">
        <h2 className="text-3xl font-extrabold text-slate-900 mb-2">
          Upload Documents
        </h2>
        <p className="text-slate-500">Drag and drop your PDFs below to begin the comment extraction process.</p>
      </div>

      <div 
        className={`border-2 border-dashed rounded-2xl p-10 text-center transition-all duration-300 cursor-pointer ${
          dragOver 
            ? 'border-indigo-500 bg-indigo-50' 
            : 'border-slate-300 hover:border-indigo-400 hover:bg-slate-50'
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
        <div className="text-6xl mb-4 text-slate-300">📄</div>
        <p className="text-lg text-slate-700 font-bold mb-1">
          Drop your PDFs here
        </p>
        <p className="text-sm text-slate-400 font-medium">
          or click to browse your files
        </p>
      </div>

      {files.length > 0 && (
        <div className="bg-slate-50 rounded-xl p-4 border border-slate-100 space-y-3">
          <h3 className="text-sm font-bold text-slate-500 uppercase tracking-wider">Queue ({files.length})</h3>
          {files.map((file, index) => (
            <div key={index} className="flex items-center justify-between bg-white p-3 rounded-lg shadow-sm border border-slate-100">
              <span className="text-sm font-medium text-slate-700 truncate mr-4">{file.name}</span>
              <button 
                onClick={() => removeFile(index)}
                className="text-slate-400 hover:text-rose-500 font-bold text-xl transition-colors"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-4 border-t border-slate-100">
        <button
          onClick={uploadFiles}
          disabled={loading || !files.length}
          className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-4 rounded-xl transition-all shadow-md hover:shadow-indigo-500/30 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Upload
        </button>
        <button
          onClick={scanFiles}
          disabled={loading}
          className="bg-emerald-500 hover:bg-emerald-600 text-white font-bold py-3 px-4 rounded-xl transition-all shadow-md hover:shadow-emerald-500/30 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Scan
        </button>
        <button
          onClick={exportExcel}
          disabled={loading}
          className="bg-slate-800 hover:bg-slate-900 text-white font-bold py-3 px-4 rounded-xl transition-all shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Excel
        </button>
        <button
          onClick={exportJSON}
          disabled={loading}
          className="bg-slate-200 hover:bg-slate-300 text-slate-800 font-bold py-3 px-4 rounded-xl transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
        >
          JSON
        </button>
      </div>

      {loading && (
        <div className="text-center text-slate-500 font-medium flex items-center justify-center space-x-3 mt-4">
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-indigo-600"></div>
          <span>Processing your documents...</span>
        </div>
      )}
    </div>
  );
}