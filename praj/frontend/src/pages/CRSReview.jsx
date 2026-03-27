import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import { FileText, Download, FileSpreadsheet, Image as ImageIcon, Calendar, Search, Filter, ArrowLeft, CheckCircle } from 'lucide-react';

const BASE_URL = 'http://localhost:8080';

export default function CRSReview() {
  const navigate = useNavigate();

  const [metadata, setMetadata]       = useState(null);
  const [allTableData, setAllTableData] = useState([]);
  const [tableData, setTableData]     = useState([]);
  const [engineers, setEngineers]     = useState([]);
  const [rowEdits, setRowEdits]       = useState({});
  const [searchTerm, setSearchTerm]   = useState('');
  const [filterStatus, setFilterStatus] = useState('All');

  // Grab BOTH possible param names
  const { drawingNo, id: routeId } = useParams();
  const actualDocId = drawingNo || routeId; 

  useEffect(() => {
    if (!actualDocId) return;

    // 1. Fetch Comments
    fetch(`${BASE_URL}/api/comments/document/${actualDocId}`, { mode: 'cors' })
      .then(res => { 
        if (!res.ok) throw new Error(`Comments fetch failed: ${res.status}`); 
        return res.json(); 
      })
      .then(data => {
        const commentsArray = Array.isArray(data) ? data : (data.comments || data.data || []);
        const mapped = commentsArray.map((item, index) => {
          
          // Format the target date properly for the HTML <input type="date">
          let formattedTarget = '';
          if (item.target_closure_date) {
            formattedTarget = new Date(item.target_closure_date).toISOString().split('T')[0];
          }

          return {
            sr:    index + 1,
            doc:   item.document_id || actualDocId,
            rev:   '-',
            cDoc:  '-',
            cRev:  '-',
            page:  item.page_sheet,
            cId:   item.comment_id || `C-${index + 1}`,
            comment: item.actual_extracted_comment || '-',
            snapshotUrl: item.snapshot_file && item.snapshot_file !== 'NA' 
              ? `${BASE_URL}/${item.snapshot_file}` 
              : null,
            person: item.name_of_person_commented || 'Unknown',
            date: (item.comment_datetime || item.created_at)
              ? new Date(item.comment_datetime || item.created_at).toLocaleDateString()
              : '-',
            color:    item.comment_color || 'Black',
            client:   item.is_client_comment ? 'Yes' : 'No',
            cat:      item.comment_category || 'General',
            hw:       item.is_handwritten ? 'Yes' : 'No',
            conf:     item.extraction_confidence_percent ? `${item.extraction_confidence_percent}%` : '100%',
            
            // ✅ FIX: Use correct database column names for initial load
            assignee: item.assigned_to || '',
            target:   formattedTarget,
            crs:      item.crs_ref || '-',
            res:      item.resolution || '',
            status:   item.status || 'Open',
            ev:       item.evidence || '',
          };
        });
        setAllTableData(mapped);
      })
      .catch(err => console.error('Error fetching comments:', err));

    // 2. Fetch Metadata
    fetch(`${BASE_URL}/api/documents/${actualDocId}`, { mode: 'cors' })
      .then(res => res.ok ? res.json() : null)
      .then(data => { 
        if (data) {
          setMetadata({
            docNo: data.praj_document_number,
            revision: data.praj_revision_number,
            custDocNo: data.customer_document_number,
            custRevision: data.customer_revision,
            supplier: data.supplier_name,
            po: data.supplier_po_number,
            is_released: data.is_released 
          });
        }
      })
      .catch(err => console.error('Error fetching metadata:', err));

    // 3. Fetch Engineers
    fetch(`${BASE_URL}/api/engineers`, { mode: 'cors' })
      .then(res => res.ok ? res.json() : [])
      .then(data => {
        let engArray = Array.isArray(data) ? data : (data.engineers || data.data || []);
        if (engArray.length === 0) {
          engArray = [
            { id: 1, name: "Yash R. (Lead)" },
            { id: 2, name: "Suraj P. (Mech)" },
            { id: 3, name: "Amit K. (Elec)" },
            { id: 4, name: "Priya S. (Civil)" }
          ];
        }
        setEngineers(engArray);
      })
      .catch(err => console.error('Error fetching engineers:', err));
  }, [actualDocId]);

  // Filtering
  useEffect(() => {
    let filtered = allTableData;
    if (searchTerm.trim()) {
      const lower = searchTerm.toLowerCase();
      filtered = filtered.filter(r =>
        r.comment.toLowerCase().includes(lower) ||
        r.person.toLowerCase().includes(lower) ||
        r.cId.toLowerCase().includes(lower) ||
        r.cat.toLowerCase().includes(lower)
      );
    }
    if (filterStatus !== 'All') filtered = filtered.filter(r => r.status === filterStatus);
    setTableData(filtered);
  }, [searchTerm, filterStatus, allTableData]);

  // ✅ FIX: Bulletproof state updater so React always registers the dropdown changes
  function setField(rowId, field, value) {
    setRowEdits(prev => ({
      ...prev,
      [rowId]: {
        ...(prev[rowId] || {}),
        [field]: value
      }
    }));
  }

  async function handleRelease() {
    const confirmRelease = window.confirm("Are you sure you want to release this document?");
    if (!confirmRelease) return;

    try {
      const res = await fetch(`${BASE_URL}/api/documents/${actualDocId}/release`, {
        method: 'PUT',
        mode: 'cors'
      });
      
      if (!res.ok) throw new Error('Failed to release document');
      
      setMetadata(prev => ({ ...prev, is_released: true }));
      alert("Document released successfully!");
    } catch (err) {
      console.error('Release failed:', err);
      alert('Failed to release document. Check console for details.');
    }
  }

  async function handleSave(row) {
    const edits = rowEdits[row.cId] || {};
    const payload = {
      commentId:  row.cId,
      assignee:   edits.assignee   ?? row.assignee,
      target:     edits.target     ?? row.target,
      resolution: edits.resolution ?? row.res,
      status:     edits.status     ?? row.status,
      evidence:   edits.evidence   ?? row.ev,
    };
    try {
      const res = await fetch(`${BASE_URL}/api/crs/drawing/${actualDocId}/comments/${row.cId}`, {
        method: 'PATCH', mode: 'cors',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      
      // Optmistic UI Update
      setAllTableData(prev => prev.map(r => r.cId === row.cId
        ? { ...r, ...payload, res: payload.resolution, ev: payload.evidence }
        : r
      ));
      setRowEdits(prev => { const n = { ...prev }; delete n[row.cId]; return n; });
      alert("Changes saved locally!");
    } catch (err) {
      console.error('Save failed:', err);
      alert('Failed to save changes. Check console for details.');
    }
  }

  async function handleDownload(format) {
    try {
      const res = await fetch(`${BASE_URL}/api/crs/drawing/${actualDocId}/export/${format}`, { mode: 'cors' });
      if (!res.ok) throw new Error('Download failed');
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Document-${actualDocId}-crs.${format === 'excel' ? 'xlsx' : 'pdf'}`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download failed:', err);
      alert(`Failed to download ${format.toUpperCase()}.`);
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
    <Layout>
      <div className="max-w-full 2xl:max-w-7xl mx-auto space-y-6">

        {/* ── Header ── */}
        <div className="flex justify-between items-end">
          <div>
            <button
              onClick={() => navigate('/crs-lookup')}
              className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-2 transition-colors"
            >
              <ArrowLeft size={13} /> Back to CRS Lookup
            </button>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-slate-800">CRS Review — {actualDocId || metadata?.docNo}</h1>
              {metadata?.is_released && (
                <span className="bg-emerald-100 text-emerald-700 text-xs px-2.5 py-1 rounded-md font-bold uppercase tracking-wide border border-emerald-200">
                  Released
                </span>
              )}
            </div>
            <p className="text-sm text-slate-500 mt-0.5">Inline comment resolution — assign, update status, add evidence</p>
          </div>
          
          <div className="flex gap-3">
            {metadata && !metadata.is_released && (
              <button 
                onClick={handleRelease}
                className="bg-white border border-slate-200 hover:bg-emerald-50 hover:border-emerald-200 text-emerald-600 px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-all shadow-sm"
              >
                <CheckCircle size={16} /> Release Document
              </button>
            )}

            <button onClick={() => handleDownload('excel')}
              className="bg-white border border-slate-200 hover:bg-slate-50 text-indigo-600 px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-all shadow-sm">
              <FileSpreadsheet size={16} className="text-emerald-500" /> Download Excel
            </button>
            <button onClick={() => handleDownload('pdf')}
              className="bg-indigo-500 hover:bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-all shadow-sm">
              <FileText size={16} /> Download PDF
            </button>
          </div>
        </div>

        {/* ── Metadata Banner ── */}
        {metadata && (
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 grid grid-cols-6 gap-4">
            {[
              { label: 'DOC NO',        val: metadata.docNo        },
              { label: 'REVISION',      val: metadata.revision     },
              { label: 'CUST DOC NO',   val: metadata.custDocNo    },
              { label: 'CUST REVISION', val: metadata.custRevision },
              { label: 'SUPPLIER',      val: metadata.supplier     },
              { label: 'PO',            val: metadata.po           },
            ].map((item, i) => (
              <div key={i}>
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">{item.label}</p>
                <p className="font-bold text-slate-800 text-sm">{item.val || '-'}</p>
              </div>
            ))}
          </div>
        )}

        {/* ── Resolution Grid ── */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">

          <div className="p-4 border-b border-slate-100 flex flex-wrap items-center justify-between bg-slate-50/50 gap-4">
            <div className="flex items-center gap-3">
              <FileText size={18} className="text-rose-400" />
              <h3 className="font-bold text-slate-800">Resolution Grid</h3>
              <span className="bg-indigo-100 text-indigo-700 text-[10px] px-2.5 py-0.5 rounded-full font-bold">{tableData.length} comments</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input type="text" placeholder="Search comments..." value={searchTerm} onChange={e => setSearchTerm(e.target.value)}
                  className="pl-8 pr-4 py-1.5 border border-slate-200 rounded-md text-sm outline-none focus:ring-2 focus:ring-indigo-500 transition-shadow w-64" />
              </div>
              <div className="relative">
                <Filter size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
                  className="pl-8 pr-4 py-1.5 border border-slate-200 rounded-md text-sm outline-none focus:ring-2 focus:ring-indigo-500 appearance-none bg-white cursor-pointer">
                  <option value="All">All Statuses</option>
                  <option value="Open">Open</option>
                  <option value="In Progress">In Progress</option>
                  <option value="Closed">Closed</option>
                </select>
              </div>
            </div>
          </div>

          <div className="overflow-x-auto">
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
                  <th className="p-4 font-bold min-w-[150px]">Comment</th>
                  <th className="p-4 font-bold">Snapshot</th>
                  <th className="p-4 font-bold">Person</th>
                  <th className="p-4 font-bold">Date</th>
                  <th className="p-4 font-bold">Color</th>
                  <th className="p-4 font-bold">Client?</th>
                  <th className="p-4 font-bold">Category</th>
                  <th className="p-4 font-bold">Handwritten?</th>
                  <th className="p-4 font-bold">Conf %</th>
                  <th className="p-4 font-bold">Assigned To</th>
                  <th className="p-4 font-bold">Target Date</th>
                  <th className="p-4 font-bold">CRS Ref</th>
                  <th className="p-4 font-bold min-w-[150px]">Resolution</th>
                  <th className="p-4 font-bold">Status</th>
                  <th className="p-4 font-bold min-w-[150px]">Evidence</th>
                  <th className="p-4 font-bold text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="text-sm text-slate-600">
                {tableData.length === 0 ? (
                  <tr><td colSpan={23} className="p-8 text-center text-slate-400 text-sm">No comments match your filter.</td></tr>
                ) : tableData.map((row) => {
                  const edits = rowEdits[row.cId] || {};
                  return (
                    <tr key={row.cId} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                      <td className="p-4 text-slate-500">{row.sr}</td>
                      <td className="p-4 font-bold text-red-500">{row.doc}</td>
                      <td className="p-4">{row.rev}</td>
                      <td className="p-4 font-bold text-red-500">{row.cDoc}</td>
                      <td className="p-4">{row.cRev}</td>
                      <td className="p-4">{row.page}</td>
                      <td className="p-4 font-bold text-indigo-600">{row.cId}</td>
                      <td className="p-4 font-medium text-slate-800">{row.comment}</td>
                      <td className="p-4 text-center">
                        {row.snapshotUrl
                          ? <a href={row.snapshotUrl} target="_blank" rel="noopener noreferrer"><ImageIcon size={18} className="text-emerald-500/80 mx-auto" /></a>
                          : <ImageIcon size={18} className="text-slate-300 mx-auto" />}
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

                      {/* ✅ FIX: Removed 'disabled' property entirely so you can assign freely */}
                      <td className="p-4">
                        <select 
                          value={edits.assignee ?? row.assignee} 
                          onChange={e => setField(row.cId, 'assignee', e.target.value)}
                          className="w-full bg-white border border-slate-300 text-slate-700 text-xs rounded-md px-2 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none">
                          <option value="">Select...</option>
                          {engineers.map(eng => <option key={eng.id} value={eng.name}>{eng.name}</option>)}
                        </select>
                      </td>
                      
                      {/* ✅ FIX: Removed 'disabled' property */}
                      <td className="p-4">
                        <input 
                          type="date" 
                          value={edits.target ?? row.target ?? ''} 
                          onChange={e => setField(row.cId, 'target', e.target.value)}
                          className="w-[120px] bg-white border border-slate-300 text-slate-700 text-xs rounded-md px-2 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none" />
                      </td>
                      <td className="p-4 font-bold text-indigo-600">{row.crs}</td>
                      
                      {/* ✅ FIX: Removed 'disabled' property */}
                      <td className="p-4">
                        <input 
                          type="text" 
                          value={edits.resolution ?? row.res} 
                          onChange={e => setField(row.cId, 'resolution', e.target.value)}
                          className="w-full bg-white border border-slate-300 text-slate-700 text-xs rounded-md px-2 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none" />
                      </td>
                      
                      {/* ✅ FIX: Removed 'disabled' property */}
                      <td className="p-4">
                        <select 
                          value={edits.status ?? row.status} 
                          onChange={e => setField(row.cId, 'status', e.target.value)}
                          className="w-full bg-white border border-slate-300 text-slate-700 text-xs rounded-md px-2 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none">
                          <option>Open</option>
                          <option>In Progress</option>
                          <option>Closed</option>
                        </select>
                      </td>
                      
                      {/* ✅ FIX: Removed 'disabled' property */}
                      <td className="p-4">
                        <input 
                          type="text" 
                          value={edits.evidence ?? row.ev} 
                          onChange={e => setField(row.cId, 'evidence', e.target.value)}
                          className="w-full bg-white border border-slate-300 text-slate-700 text-xs rounded-md px-2 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none" />
                      </td>
                      
                      {/* ✅ FIX: Removed 'disabled' property from Save button */}
                      <td className="p-4 text-center">
                        <button 
                          onClick={() => handleSave(row)}
                          className="bg-indigo-500 hover:bg-indigo-600 text-white px-3 py-1.5 rounded text-xs font-bold transition-colors shadow-sm">
                          Save
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="p-4 border-t border-slate-200/60 flex justify-between items-center text-sm text-slate-500 bg-white">
            <span>Showing {tableData.length} of {allTableData.length} total comments</span>
            <div className="flex gap-1">
              <button className="w-8 h-8 flex items-center justify-center rounded-md bg-indigo-500 text-white font-bold shadow-sm">1</button>
            </div>
          </div>
        </div>

      </div>
    </Layout>
  );
}