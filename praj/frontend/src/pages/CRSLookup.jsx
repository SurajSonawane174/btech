import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import { Search, Download, FileSearch, ArrowLeft } from 'lucide-react';

const BASE_URL = 'http://localhost:8080';

export default function CRSLookup() {
  const navigate = useNavigate();
  const [drawingNo, setDrawingNo] = useState('');
  const [supplier, setSupplier]   = useState('');
  const [po, setPo]               = useState('');
  const [status, setStatus]       = useState('All');
  const [results, setResults]     = useState([]);
  const [total, setTotal]         = useState(0);
  const [loading, setLoading]     = useState(false);

  useEffect(() => { fetchResults('All'); }, []);

  async function fetchResults(sts, dNo = drawingNo, sup = supplier, poVal = po) {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (dNo)  params.append('drawingNo', dNo);
      if (sup)  params.append('supplier', sup);
      if (poVal) params.append('po', poVal);
      // Only show drawings that have been released/staged for CRS
      params.append('crs_staged', 'true');
      if (sts && sts !== 'All') params.append('status', sts);

      const res = await fetch(`${BASE_URL}/api/crs/lookup?${params}`, {
        credentials: 'include'
      });
      const data = await res.json();
      setResults(data.results || []);
      setTotal(data.total || 0);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  function handleStatusChange(value) { setStatus(value); fetchResults(value); }
  function handleSearch() { fetchResults(status); }

  async function handleExport() {
    try {
      const params = new URLSearchParams({ drawingNo, supplier, po, status });
      const res = await fetch(`${BASE_URL}/api/crs/export?${params}`, { credentials: 'include' });
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'crs-results.xlsx';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export failed:', err);
    }
  }

  function goToReview(id) { navigate(`/crs-review/${id}`); }

  return (
    <Layout>
      <div className="max-w-7xl mx-auto space-y-6">

        {/* ── Header ── */}
        <div className="flex justify-between items-end">
          <div>
            <button
              onClick={() => navigate('/comments')}
              className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-2 transition-colors"
            >
              <ArrowLeft size={13} /> Back to Comment Extraction
            </button>
            <h1 className="text-2xl font-bold text-slate-800">CRS Lookup</h1>
            <p className="text-sm text-slate-500 mt-0.5">Released drawings — search, filter and open for full CRS review</p>
          </div>
          <button
            onClick={handleExport}
            className="bg-white border border-slate-200 hover:bg-slate-50 text-indigo-600 px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-all shadow-sm"
          >
            <Download size={16} className="text-rose-500" /> Export Results
          </button>
        </div>

        {/* ── Filter Bar ── */}
        <div className="bg-gradient-to-br from-white to-slate-50 p-5 rounded-xl border border-slate-200 shadow-sm flex gap-4 items-end">
          <div className="flex-1">
            <label className="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">Drawing No</label>
            <input type="text" placeholder="e.g. U-001" value={drawingNo} onChange={e => setDrawingNo(e.target.value)}
              className="w-full px-4 py-2.5 bg-white border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all" />
          </div>
          <div className="flex-1">
            <label className="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">Supplier Name</label>
            <input type="text" placeholder="Supplier name" value={supplier} onChange={e => setSupplier(e.target.value)}
              className="w-full px-4 py-2.5 bg-white border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all" />
          </div>
          <div className="flex-1">
            <label className="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">Supplier PO</label>
            <input type="text" placeholder="PO-7788" value={po} onChange={e => setPo(e.target.value)}
              className="w-full px-4 py-2.5 bg-white border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all" />
          </div>
          <div className="flex-1">
            <label className="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">Status</label>
            <select value={status} onChange={e => handleStatusChange(e.target.value)}
              className="w-full px-4 py-2.5 bg-white border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all appearance-none">
              <option>All</option>
              <option>Open</option>
              <option>In Progress</option>
              <option>Closed</option>
            </select>
          </div>
          <button onClick={handleSearch} disabled={loading}
            className="bg-indigo-500 hover:bg-indigo-600 text-white px-6 py-2.5 rounded-lg text-sm font-semibold flex items-center gap-2 transition-all shadow-md shadow-indigo-200 disabled:opacity-60">
            <Search size={16} /> {loading ? 'Searching...' : 'Search'}
          </button>
        </div>

        {/* ── Table ── */}
        <div className="bg-gradient-to-br from-slate-50 to-indigo-50/20 rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-slate-200/60 flex items-center gap-3 bg-white/60 backdrop-blur-sm">
            <FileSearch size={18} className="text-teal-500" />
            <h3 className="font-bold text-slate-800">CRS Results</h3>
            <span className="bg-indigo-100 text-indigo-700 text-[10px] px-2.5 py-0.5 rounded-full font-bold">{total} records</span>
            <span className="ml-auto text-[11px] text-slate-400 italic">Click "Open CRS" to review and resolve comments</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="text-xs text-slate-400 border-b border-slate-200/60 uppercase tracking-wider bg-white/30">
                  <th className="p-4 font-bold">Drawing No</th>
                  <th className="p-4 font-bold">Supplier</th>
                  <th className="p-4 font-bold">Supplier PO</th>
                  <th className="p-4 font-bold text-center">Total Comments</th>
                  <th className="p-4 font-bold text-center">Open Comments</th>
                  <th className="p-4 font-bold text-center">Closed Comments</th>
                  <th className="p-4 font-bold">Status</th>
                  <th className="p-4 font-bold">Action</th>
                </tr>
              </thead>
              <tbody className="text-sm bg-white/60">
                {loading ? (
                  <tr><td colSpan={8} className="p-8 text-center text-slate-400 text-sm">Loading...</td></tr>
                ) : results.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="p-12 text-center">
                      <div className="flex flex-col items-center gap-3">
                        <div className="w-12 h-12 bg-indigo-50 rounded-full flex items-center justify-center">
                          <FileSearch size={22} className="text-indigo-300" />
                        </div>
                        <p className="text-slate-500 font-medium text-sm">No released drawings yet</p>
                        <button onClick={() => navigate('/comments')} className="text-indigo-500 text-xs font-bold hover:underline">
                          ← Go to Comment Extraction to release drawings
                        </button>
                      </div>
                    </td>
                  </tr>
                ) : results.map((row, i) => (
                  <tr key={i} className="border-b border-slate-100 hover:bg-white transition-colors">
                    <td className="p-4 font-bold text-indigo-600">{row.id}</td>
                    <td className="p-4 text-slate-600">{row.sup}</td>
                    <td className="p-4 text-slate-600">{row.po}</td>
                    <td className="p-4 text-slate-800 font-medium text-center">{row.tot}</td>
                    <td className="p-4 text-red-500 font-bold text-center">{row.opn}</td>
                    <td className="p-4 text-emerald-500 font-bold text-center">{row.cls}</td>
                    <td className="p-4">
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold border cursor-pointer hover:opacity-80 transition-opacity ${
                        row.status === 'Open'        ? 'bg-red-50 text-red-600 border-red-100' :
                        row.status === 'In Progress' ? 'bg-amber-50 text-amber-600 border-amber-100' :
                        'bg-emerald-50 text-emerald-600 border-emerald-100'
                      }`}
                        onClick={() => goToReview(row.id)}
                      >
                        <span className={`w-1.5 h-1.5 rounded-full ${
                          row.status === 'Open' ? 'bg-red-500' :
                          row.status === 'In Progress' ? 'bg-amber-500' : 'bg-emerald-500'
                        }`}></span>
                        {row.status}
                      </span>
                    </td>
                    <td className="p-4">
                      <button
                        onClick={() => goToReview(row.id)}
                        className="bg-indigo-500 hover:bg-indigo-600 text-white px-4 py-1.5 rounded-md text-xs font-semibold shadow-sm transition-colors"
                      >
                        Open CRS
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="p-4 border-t border-slate-200/60 bg-white/40 flex justify-between items-center text-sm text-slate-500">
            <span>Showing {results.length} of {total}</span>
            <div className="flex gap-1">
              <button className="w-8 h-8 flex items-center justify-center rounded-md bg-indigo-500 text-white font-bold shadow-sm">1</button>
              <button className="w-8 h-8 flex items-center justify-center rounded-md bg-white border border-slate-200 hover:bg-slate-50 font-medium text-slate-600">2</button>
            </div>
          </div>
        </div>

      </div>
    </Layout>
  );
}