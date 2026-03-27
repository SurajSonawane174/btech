import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import FileUpload from '../components/FileUpload';
import CommentsGrid from '../components/CommentsGrid'; // Ensure this path is correct
import {
  Search, Folder, Upload, X, Settings, Image as ImageIcon,
  CheckSquare, Check, Loader2, MessageSquare, UploadCloud, Send, ArrowRightCircle
} from 'lucide-react';

const BASE_URL = 'http://localhost:8080';

const STEPS = [
  { icon: UploadCloud,  title: "File Upload"        },
  { icon: Search,       title: "OCR Processing"      },
  { icon: Settings,     title: "Comment Parsing"     },
  { icon: ImageIcon,    title: "Snapshot Extraction" },
  { icon: CheckSquare,  title: "CRS Generation"      },
];

export default function Comments() {
  const navigate = useNavigate();

  const [drawingNo, setDrawingNo]     = useState('');
  const [supplier, setSupplier]       = useState('');
  const [listStatus, setListStatus]   = useState('All');
  const [drawings, setDrawings]       = useState([]);
  const [total, setTotal]             = useState(0);
  const [listLoading, setListLoading] = useState(false);
  const [releasing, setReleasing]     = useState(null); 

  const [showUpload, setShowUpload]             = useState(false);
  const [loading, setLoading]                   = useState(false);
  const [currentStep, setCurrentStep]           = useState(-1);
  const [completedSteps, setCompleted]          = useState([]);
  const [done, setDone]                         = useState(false);
  const [extractedComments, setExtractedComments] = useState([]);
  const [uploadedDocId, setUploadedDocId]       = useState(null); 

  const [viewingDrawingId, setViewingDrawingId] = useState(null);

  useEffect(() => { fetchDrawings('All'); }, []);

  async function fetchDrawings(sts, dNo = drawingNo, sup = supplier) {
    setListLoading(true);
    try {
      const params = new URLSearchParams();
      if (dNo) params.append('drawingNo', dNo);
      if (sup) params.append('supplier', sup);
      if (sts && sts !== 'All') params.append('status', sts);
      params.append('crs_staged', 'false');

      const res = await fetch(`${BASE_URL}/api/documents?${params.toString()}`, {
        method: 'GET', mode: 'cors',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!res.ok) throw new Error(`Failed to fetch: ${res.status}`);

      const data = await res.json();
      let mapped = [];
      let totalCount = 0;

      if (Array.isArray(data)) {
        mapped = data.map(doc => ({
          id:  doc.praj_document_number    || doc.id,
          doc: doc.customer_document_number || '-',
          sup: doc.supplier_name            || '-',
          po:  doc.supplier_po_number       || '-',
          tot: doc.total_comments           || 0,
          opn: doc.open_comments            || 0,
          cls: doc.closed_comments          || 0,
          status: doc.status                || 'Open',
        }));
        totalCount = mapped.length;
      } else if (data && data.drawings) {
        mapped = data.drawings;
        totalCount = data.total || data.drawings.length;
      }

      setDrawings(mapped);
      setTotal(totalCount);
    } catch (err) {
      console.error('Failed to fetch drawings:', err);
    } finally {
      setListLoading(false);
    }
  }

  async function handleRelease(drawingId) {
    setReleasing(drawingId);
    try {
      const res = await fetch(`${BASE_URL}/api/documents/${drawingId}/release-crs`, {
        method: 'POST', mode: 'cors',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!res.ok) throw new Error(`Release failed: ${res.status}`);

      setDrawings(prev => prev.filter(d => d.id !== drawingId));
      setTotal(prev => prev - 1);
    } catch (err) {
      console.error('Release failed:', err);
      alert('Failed to release drawing to CRS. Please try again.');
    } finally {
      setReleasing(null);
    }
  }

  function handleListStatusChange(value) { setListStatus(value); fetchDrawings(value); }
  function handleListSearch() { fetchDrawings(listStatus); }

  async function runSteps() {
    setDone(false);
    setCompleted([]);
    for (let i = 0; i < STEPS.length; i++) {
      setCurrentStep(i);
      await new Promise(res => setTimeout(res, i < 2 ? 600 : 1400));
      setCompleted(prev => [...prev, i]);
    }
    setCurrentStep(-1);
    setDone(true);
  }

  function resetStatus() {
    setCurrentStep(-1);
    setCompleted([]);
    setDone(false);
    setExtractedComments([]);
    setUploadedDocId(null);
  }

  function handleProcessComplete(payload) {
    if (payload && payload.documentId) {
      setUploadedDocId(payload.documentId);
      setExtractedComments(payload.comments || []);
    } else if (Array.isArray(payload)) {
      setExtractedComments(payload);
    } else {
      setExtractedComments(payload || []);
    }
  }

  async function handleReleaseFromUpload() {
    if (uploadedDocId) {
      await handleRelease(uploadedDocId);
    }
    navigate('/review');
  }

  function openUpload() { resetStatus(); setShowUpload(true); }
  function closeUpload() {
    setShowUpload(false);
    if (done) fetchDrawings(listStatus);
  }

  const getStepState = (i) => {
    if (completedSteps.includes(i)) return 'done';
    if (currentStep === i)          return 'active';
    return 'idle';
  };

  return (
    <Layout>
      <div className="max-w-7xl mx-auto space-y-6">

        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">
              {viewingDrawingId ? `Comments for ${viewingDrawingId}` : 'Comment Extraction'}
            </h1>
            <p className="text-sm text-slate-500 mt-0.5">
              {viewingDrawingId 
                ? 'Review and update comment statuses' 
                : 'Drawings pending review — release to CRS when ready'}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {!viewingDrawingId && (
              <>
                <button
                  onClick={() => navigate('/get-crs')}
                  className="border border-indigo-200 text-indigo-600 hover:bg-indigo-50 px-4 py-2 rounded-md text-sm font-medium flex items-center gap-2 transition-colors"
                >
                  <ArrowRightCircle size={16} /> CRS Lookup
                </button>
                <button
                  onClick={openUpload}
                  className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-md text-sm font-medium flex items-center gap-2 transition-colors shadow-sm"
                >
                  <Upload size={16} /> Upload New
                </button>
              </>
            )}
          </div>
        </div>

        {showUpload && !viewingDrawingId && (
          <div className="rounded-2xl border border-slate-200 shadow-md bg-white overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Process New Drawing</h2>
                <p className="text-xs text-slate-500 mt-0.5">Upload a PDF drawing for OCR comment extraction and CRS generation</p>
              </div>
              <button onClick={closeUpload} className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-200 transition-colors text-slate-500">
                <X size={18} />
              </button>
            </div>

            <div className="p-6 grid grid-cols-12 gap-6 items-start">
              <div className="col-span-12 lg:col-span-8 min-w-0 space-y-4">
                <FileUpload
                  loading={loading}
                  setLoading={setLoading}
                  onProcess={runSteps}
                  onReset={resetStatus}
                  onComplete={handleProcessComplete}
                />

                {done && (
                  <div className="flex items-center justify-between bg-emerald-50 border border-emerald-200 rounded-xl px-5 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-emerald-500 flex items-center justify-center flex-shrink-0">
                        <Check size={16} className="text-white" />
                      </div>
                      <div>
                        <p className="text-sm font-bold text-emerald-800">Processing complete</p>
                        <p className="text-xs text-emerald-600 mt-0.5">
                          {extractedComments.length} comment{extractedComments.length !== 1 ? 's' : ''} extracted — release to begin CRS review
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={handleReleaseFromUpload}
                      className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 active:scale-95 text-white px-5 py-2.5 rounded-lg text-sm font-semibold shadow-md shadow-emerald-200 transition-all duration-150"
                    >
                      <Send size={15} /> Flag
                    </button>
                  </div>
                )}
              </div>

              <div className="col-span-12 lg:col-span-4 space-y-4">
                <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-bold text-slate-800 flex items-center gap-2 text-sm">
                      <Settings size={16} className="text-indigo-500" /> Status
                    </h3>
                    <span className={`text-[10px] uppercase tracking-widest px-2 py-0.5 rounded font-black ${
                      done    ? 'bg-emerald-100 text-emerald-700' :
                      loading ? 'bg-amber-100 text-amber-700 animate-pulse' :
                      'bg-slate-100 text-slate-500'
                    }`}>
                      {done ? 'Complete' : loading ? 'In Progress' : 'Idle'}
                    </span>
                  </div>

                  <div className="space-y-2">
                    {STEPS.map((step, i) => {
                      const state = getStepState(i);
                      return (
                        <div key={i} className={`flex items-center gap-3 p-2.5 rounded-lg border transition-all duration-300 ${
                          state === 'done'   ? 'bg-emerald-50/60 border-emerald-100' :
                          state === 'active' ? 'bg-indigo-50 border-indigo-200 ring-1 ring-indigo-400/20' :
                          'bg-slate-50 border-transparent opacity-50'
                        }`}>
                          <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ${
                            state === 'done'   ? 'bg-emerald-500 text-white' :
                            state === 'active' ? 'bg-indigo-600 text-white' :
                            'bg-slate-200 text-slate-400'
                          }`}>
                            {state === 'done' ? <Check size={11} /> : <step.icon size={10} />}
                          </div>
                          <span className={`text-xs font-bold flex-1 truncate ${
                            state === 'done'   ? 'text-emerald-700' :
                            state === 'active' ? 'text-indigo-900' : 'text-slate-500'
                          }`}>{step.title}</span>
                          {state === 'active' && <Loader2 size={12} className="text-indigo-500 animate-spin" />}
                        </div>
                      );
                    })}
                  </div>

                  {(loading || done) && (
                    <div className="mt-4 pt-4 border-t border-slate-100">
                      <div className="flex justify-between text-[10px] font-black text-slate-400 mb-1.5 uppercase">
                        <span>Completion</span>
                        <span>{Math.round((completedSteps.length / STEPS.length) * 100)}%</span>
                      </div>
                      <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-700 ease-out ${done ? 'bg-emerald-500' : 'bg-indigo-600'}`}
                          style={{ width: `${(completedSteps.length / STEPS.length) * 100}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>

                <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden max-h-64 flex flex-col">
                  <div className="p-3 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between">
                    <div className="flex items-center gap-2 font-bold text-slate-700 text-xs">
                      <MessageSquare size={14} className="text-indigo-500" /> Extracted
                    </div>
                    {done && (
                      <span className="bg-indigo-600 text-white text-[10px] px-2 py-0.5 rounded font-bold">
                        {extractedComments.length} Total
                      </span>
                    )}
                  </div>
                  <div className="overflow-y-auto">
                    {done ? (
                      <div className="divide-y divide-slate-50">
                        {extractedComments.map((c, i) => (
                          <div key={i} className="px-3 py-2 flex items-center justify-between hover:bg-slate-50">
                            <div className="flex flex-col min-w-0">
                              <span className="text-[11px] font-bold text-slate-900 truncate">{c.comment_id || `ID-${i + 1}`}</span>
                              <span className="text-[10px] text-slate-400">Page {c.page_sheet || 'N/A'}</span>
                            </div>
                            <span className="text-[9px] font-black uppercase px-1.5 py-0.5 rounded bg-red-50 text-red-600 border border-red-100">Open</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="p-8 text-center">
                        <MessageSquare size={20} className="text-slate-200 mx-auto mb-2" />
                        <p className="text-[11px] text-slate-400">{loading ? 'Scanning drawing…' : 'No comments yet'}</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {viewingDrawingId ? (
          <CommentsGrid 
            drawingId={viewingDrawingId} 
            onBack={() => setViewingDrawingId(null)} 
          />
        ) : (
          <>
            <div className="bg-gradient-to-br from-white to-slate-50 p-5 rounded-xl border border-slate-200 shadow-sm flex gap-4 items-end">
              <div className="flex-1">
                <label className="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">Drawing No</label>
                <input type="text" placeholder="e.g. praj-001" value={drawingNo} onChange={e => setDrawingNo(e.target.value)}
                  className="w-full px-4 py-2.5 bg-white border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all" />
              </div>
              <div className="flex-1">
                <label className="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">Supplier</label>
                <input type="text" placeholder="Supplier name" value={supplier} onChange={e => setSupplier(e.target.value)}
                  className="w-full px-4 py-2.5 bg-white border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all" />
              </div>
              <div className="flex-1">
                <label className="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">Status</label>
                <select value={listStatus} onChange={e => handleListStatusChange(e.target.value)}
                  className="w-full px-4 py-2.5 bg-white border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all appearance-none">
                  <option>All</option>
                  <option>Open</option>
                  <option>In Progress</option>
                  <option>Closed</option>
                </select>
              </div>
              <button onClick={handleListSearch} disabled={listLoading}
                className="bg-indigo-500 hover:bg-indigo-600 text-white px-6 py-2.5 rounded-lg text-sm font-semibold flex items-center gap-2 transition-all shadow-md shadow-indigo-200 disabled:opacity-60">
                <Search size={16} /> {listLoading ? 'Searching...' : 'Search'}
              </button>
            </div>

            <div className="bg-gradient-to-br from-slate-50 to-indigo-50/30 rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="p-5 border-b border-slate-200/60 flex items-center gap-3 bg-white/50 backdrop-blur-sm">
                <Folder size={18} className="text-amber-500" />
                <h3 className="font-bold text-slate-800">Pending CRS Release</h3>
                <span className="bg-indigo-100 text-indigo-700 text-[10px] px-2.5 py-0.5 rounded-full font-bold">{total} drawings</span>
                <span className="ml-auto text-[11px] text-slate-400 italic">Click "View" to open the detailed comments grid</span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="text-xs text-slate-400 border-b border-slate-200/60 uppercase tracking-wider bg-white/30">
                      <th className="p-4 font-bold">Drawing No</th>
                      <th className="p-4 font-bold">Customer Doc No</th>
                      <th className="p-4 font-bold">Supplier</th>
                      <th className="p-4 font-bold">PO</th>
                      <th className="p-4 font-bold text-center">Total</th>
                      <th className="p-4 font-bold text-center">Open</th>
                      <th className="p-4 font-bold text-center">Closed</th>
                      <th className="p-4 font-bold">Status</th>
                      <th className="p-4 font-bold text-center">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="text-sm bg-white/60">
                    {listLoading ? (
                      <tr><td colSpan={9} className="p-8 text-center text-slate-400 text-sm">Loading...</td></tr>
                    ) : drawings.length === 0 ? (
                      <tr>
                        <td colSpan={9} className="p-12 text-center">
                          <div className="flex flex-col items-center gap-3">
                            <div className="w-12 h-12 bg-emerald-50 rounded-full flex items-center justify-center">
                              <Check size={22} className="text-emerald-400" />
                            </div>
                            <p className="text-slate-500 font-medium text-sm">All drawings have been released to CRS</p>
                            <button onClick={() => navigate('/crs-lookup')} className="text-indigo-500 text-xs font-bold hover:underline">
                              Go to CRS Lookup →
                            </button>
                          </div>
                        </td>
                      </tr>
                    ) : drawings.map((row, i) => (
                      <tr key={i} className="border-b border-slate-100 hover:bg-white transition-colors">
                        <td className="p-4 font-bold text-indigo-600">{row.id}</td>
                        <td className="p-4 text-slate-600">{row.doc}</td>
                        <td className="p-4 text-slate-600">{row.sup}</td>
                        <td className="p-4 text-slate-600">{row.po}</td>
                        <td className="p-4 text-slate-800 font-medium text-center">{row.tot}</td>
                        <td className="p-4 text-red-500 font-bold text-center">{row.opn}</td>
                        <td className="p-4 text-emerald-500 font-bold text-center">{row.cls}</td>
                        <td className="p-4">
                          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold border ${
                            row.status === 'Open'        ? 'bg-red-50 text-red-600 border-red-100' :
                            row.status === 'In Progress' ? 'bg-amber-50 text-amber-600 border-amber-100' :
                            'bg-emerald-50 text-emerald-600 border-emerald-100'
                          }`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${
                              row.status === 'Open' ? 'bg-red-500' :
                              row.status === 'In Progress' ? 'bg-amber-500' : 'bg-emerald-500'
                            }`}></span>
                            {row.status}
                          </span>
                        </td>
                        <td className="p-4 text-center">
                          <button
                            onClick={() => setViewingDrawingId(row.id)}
                            className="inline-flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-1.5 rounded-md text-xs font-semibold shadow-sm transition-colors"
                          >
                            <Send size={12} /> View
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="p-4 border-t border-slate-200/60 bg-white/40 flex justify-between items-center text-sm text-slate-500">
                <span>Showing {drawings.length} of {total} drawings</span>
                <div className="flex gap-1">
                  <button className="w-8 h-8 flex items-center justify-center rounded-md bg-indigo-500 text-white font-bold shadow-sm">1</button>
                  <button className="w-8 h-8 flex items-center justify-center rounded-md bg-white border border-slate-200 hover:bg-slate-50 font-medium text-slate-600">2</button>
                  <button className="w-8 h-8 flex items-center justify-center rounded-md bg-white border border-slate-200 hover:bg-slate-50 font-medium text-slate-600">3</button>
                </div>
              </div>
            </div>
          </>
        )}

      </div>
    </Layout>
  );
}