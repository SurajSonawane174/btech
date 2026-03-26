import React, { useState, useRef } from 'react';
import api from '../api/axios';
import { UploadCloud, FileText, Settings, X, Loader2 } from 'lucide-react';

export default function FileUpload({ loading, setLoading, onProcess, onReset }) {
  const [files, setFiles]       = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef            = useRef(null);

  const handleDragOver  = (e) => { e.preventDefault(); setDragOver(true);  };
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

  const handleProcessDrawing = async () => {
    if (!files.length) return alert("Please select a file to process first.");

    try {
      // Kick off the step animation in the parent
      onProcess?.();

      const formData = new FormData();
      for (let file of files) formData.append("files", file);
      await api.post("/upload", formData);
      await api.post("/scan");

    } catch (err) {
      console.error(err);
      alert("Processing failed. Please check the network tab or server logs.");
      setLoading(false);
    }
  };

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

      {/* Metadata Form */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="bg-slate-50 p-4 border-b border-slate-100 flex items-center gap-2 font-bold text-slate-700">
          <FileText size={18} className="text-emerald-500" /> Drawing Metadata
        </div>
        <div className="p-6 grid grid-cols-2 gap-5">
          {[
            { label: "DOC NUMBER",       val: "chait-001"       },
            { label: "REVISION",         val: "A"               },
            { label: "CUSTOMER DOC NO",  val: "CUST-001"        },
            { label: "CUSTOMER REVISION",val: "1"               },
            { label: "SUPPLIER NAME",    val: "ABC Engineering" },
            { label: "SUPPLIER PO",      val: "PO-7788"         },
            { label: "PAGE / SHEET",     val: "1"               },
          ].map((field, i) => (
            <div key={i}>
              <label className="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">{field.label}</label>
              <input
                type="text"
                defaultValue={field.val}
                className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-700 focus:ring-2 focus:ring-indigo-500 outline-none transition-all"
              />
            </div>
          ))}
          <div>
            <label className="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">DRAWING TYPE</label>
            <select className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-700 focus:ring-2 focus:ring-indigo-500 outline-none appearance-none transition-all">
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