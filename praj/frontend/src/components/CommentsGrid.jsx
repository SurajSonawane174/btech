import React, { useState, useEffect } from 'react';
import { 
  ArrowLeft, Save, Send, Loader2, FileText, 
  FileSpreadsheet, Image as ImageIcon, Calendar, Search, Filter 
} from 'lucide-react';

const BASE_URL = 'http://localhost:8080';

export default function CommentsGrid({ drawingId, onBack }) {
  const [allTableData, setAllTableData]         = useState([]);
  const [tableData, setTableData]               = useState([]);
  const [searchTerm, setSearchTerm]             = useState('');
  const [filterStatus, setFilterStatus]         = useState('All');
  const [rowEdits, setRowEdits]                 = useState({});
  const [metadata, setMetadata]                 = useState(null);
  const [engineers, setEngineers]               = useState([]);
  const [commentsLoading, setCommentsLoading]   = useState(false);
  const [isReleasing, setIsReleasing]           = useState(false);

  useEffect(() => {
    if (!drawingId) return;
    setCommentsLoading(true);

    // 1. Fetch Comments
    fetch(`${BASE_URL}/api/comments/document/${drawingId}`, { mode: 'cors' })
      .then(res => {
        if (!res.ok) throw new Error("Failed to fetch comments");
        return res.json();
      })
      .then(data => {
        const commentsArray = Array.isArray(data) ? data : (data.comments || []);
        const mappedComments = commentsArray.map((item, index) => ({
          sr: index + 1,
          doc: item.document_id || drawingId,
          rev: "-",
          cDoc: "-",
          cRev: "-",
          page: item.page_sheet,
          cId: item.comment_id || `C-${index+1}`,
          comment: item.actual_extracted_comment || "-",
          snapshotUrl: item.snapshot_file,
          person: item.name_of_person_commented || "Unknown",
          date: (item.comment_datetime || item.created_at) 
                  ? new Date(item.comment_datetime || item.created_at).toLocaleDateString() 
                  : "-",
          color: item.comment_color || "Black",
          client: item.is_client_comment ? "Yes" : "No",
          cat: item.comment_category || "General",
          hw: item.is_handwritten ? "Yes" : "No",
          conf: item.extraction_confidence_percent ? `${item.extraction_confidence_percent}%` : "100%",
          assignee: item.assignee || "",
          target: item.target || "",
          crs: item.crs_ref || "-",
          res: item.resolution || "",
          status: item.status || "Open",
          ev: item.evidence || ""
        }));
        
        setAllTableData(mappedComments);
      })
      .catch(err => console.error("Error fetching comments:", err))
      .finally(() => setCommentsLoading(false));

    // 2. Fetch Metadata
    fetch(`${BASE_URL}/api/crs/drawing/${drawingId}/metadata`, { mode: 'cors' })
      .then(res => res.ok ? res.json() : null)
      .then(data => { if (data) setMetadata(data); })
      .catch(err => console.error("Error fetching metadata:", err));

    // 3. Fetch Engineers
    fetch(`${BASE_URL}/api/engineers`, { mode: 'cors' })
      .then(res => res.ok ? res.json() : [])
      .then(data => setEngineers(data))
      .catch(err => console.error("Error fetching engineers:", err));
      
  }, [drawingId]);

  // Handle Filtering
  useEffect(() => {
    let filtered = allTableData;

    if (searchTerm.trim() !== '') {
      const lowerSearch = searchTerm.toLowerCase();
      filtered = filtered.filter(row => 
        row.comment.toLowerCase().includes(lowerSearch) || 
        row.person.toLowerCase().includes(lowerSearch) ||
        row.cId.toLowerCase().includes(lowerSearch) ||
        row.cat.toLowerCase().includes(lowerSearch)
      );
    }

    if (filterStatus !== 'All') {
      filtered = filtered.filter(row => row.status === filterStatus);
    }

    setTableData(filtered);
  }, [searchTerm, filterStatus, allTableData]);

  function setField(rowId, field, value) {
    setRowEdits(prev => ({ ...prev, [rowId]: { ...prev[rowId], [field]: value } }));
  }

  async function handleSave(row) {
    const edits = rowEdits[row.cId] || {};
    
    const payload = {
      commentId: row.cId,
      assignee:   edits.assignee   ?? row.assignee,
      target:     edits.target     ?? row.target,
      resolution: edits.resolution ?? row.res,
      status:     edits.status     ?? row.status,
      evidence:   edits.evidence   ?? row.ev,
    };
    
    try {
      const res = await fetch(`${BASE_URL}/api/crs/drawing/${drawingId}/comments/${row.cId}`, {
        method: 'PATCH',
        mode: 'cors',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) throw new Error("Failed to save");

      setAllTableData(prev => prev.map(r => r.cId === row.cId ? { ...r, ...payload, res: payload.resolution, ev: payload.evidence } : r));
      setRowEdits(prev => { const n = { ...prev }; delete n[row.cId]; return n; });
    } catch (err) {
      console.error('Save failed:', err);
      alert("Failed to save changes.");
    }
  }

  async function handleDownload(format) {
    try {
      const res = await fetch(`${BASE_URL}/api/crs/drawing/${drawingId}/export/${format}`, { mode: 'cors' });
      if (!res.ok) throw new Error("Download failed");

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Document-${drawingId}-crs.${format === 'excel' ? 'xlsx' : 'pdf'}`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download failed:', err);
      alert(`Failed to download ${format.toUpperCase()}.`);
    }
  }

  async function handleRelease() {
    setIsReleasing(true);
    try {
      const res = await fetch(`${BASE_URL}/api/documents/${drawingId}/release-crs`, {
        method: 'POST', mode: 'cors',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!res.ok) throw new Error(`Release failed: ${res.status}`);
      
      onBack(); 
    } catch (err) {
      console.error('Release failed:', err);
      alert('Failed to release drawing to CRS.');
    } finally {
      setIsReleasing(false);
    }
  }

  const getCategoryColor = (cat) => {
    switch (cat?.toLowerCase()) {
      case 'safety':      return 'text-red-600 bg-red-50 border-red-100';
      case 'design':      return 'text-blue-600 bg-blue-50 border-blue-100';
      case 'maintenance': return 'text-emerald-600 bg-emerald-50 border-emerald-100';
      case 'labeling':    return 'text-amber-600 bg-amber-50 border-amber-100';
      case 'specs':       return 'text-teal-600 bg-teal-50 border-teal-100';
      case 'technical':   return 'text-indigo-600 bg-indigo-50 border-indigo-100';
      default:            return 'text-slate-600 bg-slate-50 border-slate-100';
    }
  };

  return (
    <div className="space-y-6 w-full animate-in fade-in zoom-in-95 duration-200">
      
      {/* ── Header Area ── */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <button
            onClick={onBack}
            className="mb-3 text-indigo-600 hover:text-indigo-800 text-sm font-medium flex items-center gap-1 transition-colors"
          >
            <ArrowLeft size={16} /> Back to Drawings List
          </button>
          {/* <h1 className="text-2xl font-bold text-slate-800">CRS Review — {drawingId || metadata?.docNo}</h1> */}
          {/* <p className="text-sm text-slate-500 mt-1">Inline comment resolution — assign, update status, add evidence</p> */}
        </div>
        
        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={() => handleDownload('excel')}
            className="bg-white border border-slate-200 hover:bg-slate-50 text-indigo-600 px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-all shadow-sm"
          >
            <FileSpreadsheet size={16} className="text-emerald-500" /> Download Excel
          </button>
          <button
            onClick={() => handleDownload('pdf')}
            className="bg-indigo-50 hover:bg-indigo-100 text-indigo-700 px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-all shadow-sm"
          >
            <FileText size={16} /> Download PDF
          </button>
          <button
            onClick={handleRelease}
            disabled={isReleasing}
            className="bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 text-white px-5 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-colors shadow-sm"
          >
            {isReleasing ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />} 
            {isReleasing ? 'Releasing...' : 'Release to CRS'}
          </button>
        </div>
      </div>

      {/* ── Metadata Banner ── */}
      {metadata && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {[
            { label: 'DOC NO',        val: metadata.docNo       },
            { label: 'REVISION',      val: metadata.revision    },
            { label: 'CUST DOC NO',   val: metadata.custDocNo   },
            { label: 'CUST REVISION', val: metadata.custRevision},
            { label: 'SUPPLIER',      val: metadata.supplier    },
            { label: 'PO',            val: metadata.po          },
          ].map((item, i) => (
            <div key={i}>
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">{item.label}</p>
              <p className="font-bold text-slate-800 text-sm truncate" title={item.val}>{item.val}</p>
            </div>
          ))}
        </div>
      )}

      {/* ── Resolution Grid Table Container ── */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col w-full">
        
        {/* Table Controls (Search & Filter) */}
        <div className="p-4 border-b border-slate-100 flex flex-wrap items-center justify-between bg-slate-50/50 gap-4">
          <div className="flex items-center gap-3">
            <FileText size={18} className="text-rose-400" />
            <h3 className="font-bold text-slate-800">Resolution Grid</h3>
            <span className="bg-indigo-100 text-indigo-700 text-[10px] px-2.5 py-0.5 rounded-full font-bold">{tableData.length} comments</span>
          </div>
          
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search comments..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-8 pr-4 py-1.5 border border-slate-200 rounded-md text-sm outline-none focus:ring-2 focus:ring-indigo-500 transition-shadow w-64"
              />
            </div>
            <div className="relative">
              <Filter size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="pl-8 pr-4 py-1.5 border border-slate-200 rounded-md text-sm outline-none focus:ring-2 focus:ring-indigo-500 appearance-none bg-white cursor-pointer"
              >
                <option value="All">All Statuses</option>
                <option value="Open">Open</option>
                <option value="In Progress">In Progress</option>
                <option value="Closed">Closed</option>
              </select>
            </div>
          </div>
        </div>

        {/* The Big Table (Horizontal Scroll enabled) */}
        <div className="overflow-x-auto w-full">
          <table className="w-full text-left border-collapse min-w-[1800px]">
            <thead>
              <tr className="text-[11px] text-slate-400 border-b border-slate-200/60 uppercase tracking-wider bg-white">
                <th className="p-4 font-bold">Sr.</th>
                <th className="p-4 font-bold">Doc No</th>
                <th className="p-4 font-bold">Rev</th>
                <th className="p-4 font-bold">Cust Doc</th>
                <th className="p-4 font-bold">Cust Rev</th>
                <th className="p-4 font-bold">Page</th>
                <th className="p-4 font-bold">Comment ID</th>
                <th className="p-4 font-bold min-w-[200px]">Comment</th>
                <th className="p-4 font-bold text-center">Snapshot</th>
                <th className="p-4 font-bold">Person</th>
                <th className="p-4 font-bold min-w-[100px]">Date</th>
                <th className="p-4 font-bold">Color</th>
                <th className="p-4 font-bold">Client?</th>
                <th className="p-4 font-bold">Category</th>
                <th className="p-4 font-bold text-center">HW?</th>
                <th className="p-4 font-bold">Conf %</th>
                <th className="p-4 font-bold min-w-[140px]">Assigned To</th>
                <th className="p-4 font-bold min-w-[140px]">Target Date</th>
                <th className="p-4 font-bold">CRS Ref</th>
                <th className="p-4 font-bold min-w-[160px]">Resolution</th>
                <th className="p-4 font-bold min-w-[120px]">Status</th>
                <th className="p-4 font-bold min-w-[160px]">Evidence</th>
                <th className="p-4 font-bold text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="text-sm text-slate-600">
              {commentsLoading ? (
                 <tr><td colSpan={23} className="p-8 text-center text-slate-400">Loading comments...</td></tr>
              ) : tableData.length === 0 ? (
                <tr><td colSpan={23} className="p-8 text-center text-slate-400 text-sm">No comments match your filter.</td></tr>
              ) : tableData.map((row) => {
                const edits = rowEdits[row.cId] || {};
                const hasEdits = Object.keys(edits).length > 0;

                return (
                  <tr key={row.cId} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                    <td className="p-4 text-slate-500">{row.sr}</td>
                    <td className="p-4 font-bold text-red-500">{row.doc}</td>
                    <td className="p-4">{row.rev}</td>
                    <td className="p-4 font-bold text-red-500">{row.cDoc}</td>
                    <td className="p-4">{row.cRev}</td>
                    <td className="p-4">{row.page}</td>
                    <td className="p-4 font-bold text-indigo-600">{row.cId}</td>
                    <td className="p-4 font-medium text-slate-800 truncate max-w-[200px]" title={row.comment}>{row.comment}</td>
                    <td className="p-4 text-center">
                      {row.snapshotUrl
                        ? <a href={row.snapshotUrl} target="_blank" rel="noopener noreferrer"><ImageIcon size={18} className="text-emerald-500 hover:text-emerald-700 mx-auto transition-colors" /></a>
                        : <ImageIcon size={18} className="text-slate-300 mx-auto" />
                      }
                    </td>
                    <td className="p-4">{row.person}</td>
                    <td className="p-4 text-emerald-600 font-medium">{row.date}</td>
                    <td className="p-4 font-medium" style={{ color: row.color?.toLowerCase() }}>{row.color}</td>
                    <td className="p-4 font-bold text-emerald-600">{row.client}</td>
                    <td className="p-4">
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold border ${getCategoryColor(row.cat)}`}>
                        <span className="w-1.5 h-1.5 rounded-full bg-current opacity-70"></span>
                        {row.cat}
                      </span>
                    </td>
                    <td className="p-4 text-center font-medium">{row.hw}</td>
                    <td className="p-4 font-bold text-emerald-600">{row.conf}</td>

                    {/* Editable fields */}
                    <td className="p-4">
                      <select
                        value={edits.assignee ?? row.assignee}
                        onChange={e => setField(row.cId, 'assignee', e.target.value)}
                        className="w-full bg-slate-50 border border-slate-200 text-slate-700 text-xs rounded-md px-2 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none"
                      >
                        <option value="">Select...</option>
                        {engineers.map(eng => <option key={eng.id} value={eng.name}>{eng.name}</option>)}
                      </select>
                    </td>
                    <td className="p-4 relative">
                      <input
                        type="date"
                        value={edits.target ?? row.target}
                        onChange={e => setField(row.cId, 'target', e.target.value)}
                        className="w-full bg-slate-50 border border-slate-200 text-slate-700 text-xs rounded-md pl-2 pr-7 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none"
                      />
                      <Calendar size={12} className="absolute right-6 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                    </td>
                    <td className="p-4 font-bold text-indigo-600">{row.crs}</td>
                    <td className="p-4">
                      <input
                        type="text"
                        placeholder="Resolution..."
                        value={edits.resolution ?? row.res}
                        onChange={e => setField(row.cId, 'resolution', e.target.value)}
                        className="w-full bg-slate-50 border border-slate-200 text-slate-700 text-xs rounded-md px-2 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none"
                      />
                    </td>
                    <td className="p-4">
                      <select
                        value={edits.status ?? row.status}
                        onChange={e => setField(row.cId, 'status', e.target.value)}
                        className="w-full bg-slate-50 border border-slate-200 text-slate-700 text-xs rounded-md px-2 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none"
                      >
                        <option>Open</option>
                        <option>In Progress</option>
                        <option>Closed</option>
                      </select>
                    </td>
                    <td className="p-4">
                      <input
                        type="text"
                        placeholder="Evidence link..."
                        value={edits.evidence ?? row.ev}
                        onChange={e => setField(row.cId, 'evidence', e.target.value)}
                        className="w-full bg-slate-50 border border-slate-200 text-slate-700 text-xs rounded-md px-2 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none"
                      />
                    </td>
                    <td className="p-4 text-center">
                      <button
                        onClick={() => handleSave(row)}
                        disabled={!hasEdits}
                        className={`px-3 py-1.5 rounded text-xs font-bold transition-colors shadow-sm flex items-center justify-center gap-1 w-full ${
                          hasEdits 
                          ? 'bg-indigo-500 hover:bg-indigo-600 text-white' 
                          : 'bg-slate-100 text-slate-400 cursor-not-allowed'
                        }`}
                      >
                        <Save size={14} /> Save
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Footer Pagination Stats */}
        <div className="p-4 border-t border-slate-200/60 flex justify-between items-center text-sm text-slate-500 bg-white">
          <span>Showing {tableData.length} of {allTableData.length} total comments</span>
          <div className="flex gap-1">
            <button className="w-8 h-8 flex items-center justify-center rounded-md bg-indigo-500 text-white font-bold shadow-sm">1</button>
            <button className="w-8 h-8 flex items-center justify-center rounded-md bg-white border border-slate-200 hover:bg-slate-50 font-medium text-slate-600">2</button>
          </div>
        </div>
      </div>
    </div>
  );
}