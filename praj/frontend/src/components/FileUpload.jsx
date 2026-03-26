import React, { useState, useRef } from 'react';
import api from '../api/axios';
import { UploadCloud, FileText, Settings, X, Loader2 } from 'lucide-react';

const DEFAULT_META = {
  docNumber: '',
  revision: '',
  customerDocNo: '',
  customerRevision: '',
  supplierName: '',
  supplierPo: '',
  pageSheet: '1',
  drawingType: 'P&ID',
};

export default function FileUpload({ loading, setLoading, onProcess, onReset, onComplete }) {
  const [files, setFiles]     = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const [meta, setMeta]       = useState(DEFAULT_META); // FIX: controlled state
  const fileInputRef          = useRef(null);

  const handleDragOver  = (e) => { e.preventDefault(); setDragOver(true); };
  const handleDragLeave = (e) => { e.preventDefault(); setDragOver(false); };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = Array.from(e.dataTransfer.files).filter(
      f => f.type === 'application/pdf' || f.type.startsWith('image/')
    );
    setFiles(prev => [...prev, ...dropped]);
  };

  const handleFileSelect = (e) => {
    setFiles(prev => [...prev, ...Array.from(e.target.files)]);
  };

  const removeFile = (index) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
    onReset?.();
  };

  const updateMeta = (key, value) => setMeta(prev => ({ ...prev, [key]: value }));

  const handleProcessDrawing = async () => {
    if (!files.length) return alert("Please select a file first.");

    try {
      setLoading(true);

      // Step 1: Upload the file
      const formData = new FormData();
      for (let file of files) formData.append("files", file);
      await api.post("/api/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      // Step 2: Kick off the visual animation in parent (non-blocking)
      onProcess?.();

      // Step 3: Trigger the AI scan
      const scanResponse = await api.post("/api/scan");

      // Step 4: Pass results up
      onComplete?.(scanResponse.data);

    } catch (err) {
      console.error("Processing failed:", err);
      const msg = err.response?.data?.message || "Processing failed. Check server logs.";
      alert(msg);
      setLoading(false);
    }
  };

  const metaFields = [
    { label: "DOC NUMBER",        key: "docNumber",        placeholder: "e.g. chait-001" },
    { label: "REVISION",          key: "revision",         placeholder: "e.g. A" },
    { label: "CUSTOMER DOC NO",   key: "customerDocNo",    placeholder: "CUST-001" },
    { label: "CUSTOMER REVISION", key: "customerRevision", placeholder: "1" },
    { label: "SUPPLIER NAME",     key: "supplierName",     placeholder: "ABC Engineering" },
    { label: "SUPPLIER PO",       key: "supplierPo",       placeholder: "PO-7788" },
    { label: "PAGE / SHEET",      key: "pageSheet",        placeholder: "1" },
  ];

  return (
    <div className="col-span-2 space-y-6">

      {/* Upload Box */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="bg-slate-50 p-4 border-b border-slate-100 flex items-center gap-2 font-bold text-slate-700">
          <UploadCloud size={18} className="text-indigo-500" /> Upload Drawing
        </div>
        <div className="p-6">
          <div
            className={`border-2 border-dashed rounded-xl p-10 text-center flex flex-col items-center justify-center transition-all cursor-pointer min-h-[200px] ${
              dragOver
                ? 'border-indigo-500 bg-indigo-50'
                : 'border-indigo-200 bg-gradient-to-br from-indigo-50/50 to-purple-50/30 hover:bg-indigo-50/80'
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
              accept=".pdf,.png,.jpg,.jpeg"
              onChange={handleFileSelect}
              className="hidden"
            />
            {files.length > 0 ? (
              <div className="w-full text-left space-y-3">
                <h3 className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-2">
                  Selected Files ({files.length})
                </h3>
                {files.map((file, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between bg-white p-3 rounded-lg shadow-sm border border-slate-100"
                    onClick={e => e.stopPropagation()}
                  >
                    <span className="text-sm font-medium text-slate-700 truncate mr-4">{file.name}</span>
                    <button
                      onClick={e => { e.stopPropagation(); removeFile(index); }}
                      className="text-slate-400 hover:text-rose-500 transition-colors"
                    >
                      <X size={18} />
                    </button>
                  </div>
                ))}
                <p className="text-xs text-center text-slate-400 mt-4 font-medium">
                  Click or drag more files to add
                </p>
              </div>
            ) : (
              <>
                <FileText size={40} className="text-indigo-300 mb-4" />
                <h3 className="text-lg font-bold text-slate-700 mb-1">Drop your PDF here</h3>
                <p className="text-sm text-slate-500">or click to browse — PDF, PNG, JPG supported</p>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Metadata Form — now controlled */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="bg-slate-50 p-4 border-b border-slate-100 flex items-center gap-2 font-bold text-slate-700">
          <FileText size={18} className="text-emerald-500" /> Drawing Metadata
        </div>
        <div className="p-6 grid grid-cols-2 gap-5">
          {metaFields.map((field) => (
            <div key={field.key}>
              <label className="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">
                {field.label}
              </label>
              <input
                type="text"
                value={meta[field.key]}
                onChange={e => updateMeta(field.key, e.target.value)}
                placeholder={field.placeholder}
                className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-700 focus:ring-2 focus:ring-indigo-500 outline-none transition-all"
              />
            </div>
          ))}
          <div>
            <label className="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">
              DRAWING TYPE
            </label>
            <select
              value={meta.drawingType}
              onChange={e => updateMeta('drawingType', e.target.value)}
              className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-700 focus:ring-2 focus:ring-indigo-500 outline-none appearance-none transition-all"
            >
              <option>P&ID</option>
              <option>Isometric</option>
              <option>Structural</option>
            </select>
          </div>
        </div>
      </div>

      {/* Action Button */}
      <button
        onClick={handleProcessDrawing}
        disabled={loading || !files.length}
        className="w-full bg-gradient-to-r from-indigo-500 to-indigo-600 hover:from-indigo-600 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold py-4 rounded-xl shadow-lg shadow-indigo-200 flex justify-center items-center gap-2 transition-all"
      >
        {loading ? (
          <><Loader2 size={20} className="animate-spin" /> Processing Documents...</>
        ) : (
          <><Settings size={20} /> Process Drawing</>
        )}
      </button>
    </div>
  );
}