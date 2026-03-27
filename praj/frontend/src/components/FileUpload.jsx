import React, { useState, useRef, useMemo } from 'react';
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

export default function FileUpload({
  loading = false,
  setLoading = () => {},
  onProcess,
  onReset,
  onComplete
}) {
  const [files, setFiles] = useState([]);
  const [comments, setComments] = useState([]);
  const [search, setSearch] = useState("");
  const [filterType, setFilterType] = useState("all");

  const [dragOver, setDragOver] = useState(false);
  const [meta, setMeta] = useState(DEFAULT_META);
  const fileInputRef = useRef(null);

  const handleDragOver = (e) => { e.preventDefault(); setDragOver(true); };
  const handleDragLeave = (e) => { e.preventDefault(); setDragOver(false); };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = Array.from(e.dataTransfer.files);
    setFiles(prev => [...prev, ...dropped]);
  };

  const handleFileSelect = (e) => {
    setFiles(prev => [...prev, ...Array.from(e.target.files)]);
  };

  const removeFile = (index) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
    onReset?.();
  };

  const updateMeta = (key, value) => {
    setMeta(prev => ({ ...prev, [key]: value }));
  };

  // 🔥 FILTER + SEARCH
  const filteredComments = useMemo(() => {
    return comments.filter(c => {
      const matchesSearch =
        c.actual_extracted_comment?.toLowerCase().includes(search.toLowerCase());

      const matchesFilter =
        filterType === "all" || c.comment_category === filterType;

      return matchesSearch && matchesFilter;
    });
  }, [comments, search, filterType]);

  // 🔥 PROCESS
  const handleProcessDrawing = async () => {
    if (!files.length) {
      alert("Please select a file first.");
      return;
    }

    try {
      setLoading(true);
      onProcess?.();

      const formData = new FormData();
      files.forEach(file => formData.append("files", file));
      formData.append("metadata", JSON.stringify(meta));

      const response = await fetch("http://localhost:8080/api/drawings/process-drawing", {
        method: "POST",
        body: formData
      });

      const result = await response.json();

      const extracted = result?.extractedComments || [];

      setComments(extracted); // 🔥 store

      onComplete?.(extracted);

    } catch (err) {
      console.error(err);
      alert("Processing failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">

      {/* Upload */}
      <div className="bg-white p-6 rounded-xl border">
        <div
          className="border-2 border-dashed p-8 text-center cursor-pointer"
          onClick={() => fileInputRef.current.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={handleFileSelect}
          />

          {files.length === 0 ? (
            <p>Upload PDF</p>
          ) : (
            files.map((f, i) => (
              <div key={i} className="flex justify-between">
                <span>{f.name}</span>
                <X onClick={() => removeFile(i)} />
              </div>
            ))
          )}
        </div>
      </div>

      {/* Button */}
      <button
        onClick={handleProcessDrawing}
        disabled={loading}
        className="bg-indigo-600 text-white px-4 py-2 rounded"
      >
        {loading ? "Processing..." : "Process Drawing"}
      </button>

      {/* 🔍 SEARCH + FILTER */}
      {comments.length > 0 && (
        <div className="bg-white p-4 rounded-xl border space-y-3">

          <div className="flex gap-3">
            <input
              type="text"
              placeholder="Search comments..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="border px-3 py-2 rounded w-full"
            />

            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="border px-3 py-2 rounded"
            >
              <option value="all">All</option>
              <option value="technical">Technical</option>
              <option value="aesthetic">Aesthetic</option>
              <option value="repeated">Repeated</option>
            </select>
          </div>

          {/* 📊 TABLE */}
          <div className="overflow-auto max-h-[400px]">
            <table className="w-full border text-sm">
              <thead className="bg-slate-100 sticky top-0">
                <tr>
                  <th className="p-2 border">#</th>
                  <th className="p-2 border">Comment</th>
                  <th className="p-2 border">Page</th>
                  <th className="p-2 border">Type</th>
                  <th className="p-2 border">By</th>
                  <th className="p-2 border">Snapshot</th>
                </tr>
              </thead>

              <tbody>
                {filteredComments.map((c, i) => (
                  <tr key={i} className="hover:bg-slate-50">
                    <td className="p-2 border">{i + 1}</td>

                    <td className="p-2 border">
                      {c.actual_extracted_comment}
                    </td>

                    <td className="p-2 border">{c.page_sheet}</td>

                    <td className="p-2 border capitalize">
                      {c.comment_category}
                    </td>

                    <td className="p-2 border">
                      {c.name_of_person_commented}
                    </td>

                    {/* 🖼 IMAGE */}
                    <td className="p-2 border">
                      {c.snapshot_file ? (
                        <img
                          src={`http://localhost:8080/${c.snapshot_file}`}
                          alt="snapshot"
                          className="w-20 h-20 object-cover rounded cursor-pointer"
                          onClick={() =>
                            window.open(`http://localhost:8080/${c.snapshot_file}`)
                          }
                        />
                      ) : (
                        "N/A"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}