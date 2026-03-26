import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import api from '../api/axios';
import { Search, Folder } from 'lucide-react';

export default function Comments() {
  const navigate = useNavigate();
  const [drawingNo, setDrawingNo] = useState('');
  const [supplier, setSupplier] = useState('');
  const [status, setStatus] = useState('All');
  const [drawings, setDrawings] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  // Expected API response: { drawings: [{ id, doc, sup, po, tot, opn, cls, status }], total: number }

  useEffect(() => {
    fetchDrawings('All');
  }, []);

  async function fetchDrawings(sts, dNo = drawingNo, sup = supplier) {
    setLoading(true);
    try {
      const params = new URLSearchParams({ drawingNo: dNo, supplier: sup, status: sts });
      const res = await api.get(`/api/drawings?${params.toString()}`);
      const data = res.data;
      setDrawings(data.drawings);
      setTotal(data.total);
      console.log(res.data);
      
    } catch (err) {
      console.error('Failed to fetch drawings:', err);
    } finally {
      setLoading(false);
    }
  }

  function handleStatusChange(value) {
    setStatus(value);
    fetchDrawings(value);
  }

  function handleSearch() {
    fetchDrawings(status);
  }

  function goToReview(id) {
    navigate(`/crs-review/${id}`);
  }

  return (
    <Layout>
      <div className="max-w-7xl mx-auto space-y-6">

        {/* Page Header */}
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Drawing List</h1>
          <p className="text-sm text-slate-500">All submitted engineering drawings and their processing status</p>
        </div>

        {/* Search & Filter Bar */}
        <div className="bg-gradient-to-br from-white to-slate-50 p-5 rounded-xl border border-slate-200 shadow-sm flex gap-4 items-end">
          <div className="flex-1">
            <label className="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">Drawing No</label>
            <input
              type="text"
              placeholder="e.g. praj-001"
              value={drawingNo}
              onChange={e => setDrawingNo(e.target.value)}
              className="w-full px-4 py-2.5 bg-white border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all"
            />
          </div>
          <div className="flex-1">
            <label className="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">Supplier</label>
            <input
              type="text"
              placeholder="Supplier name"
              value={supplier}
              onChange={e => setSupplier(e.target.value)}
              className="w-full px-4 py-2.5 bg-white border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all"
            />
          </div>
          <div className="flex-1">
            <label className="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">Status</label>
            <select
              value={status}
              onChange={e => handleStatusChange(e.target.value)}
              className="w-full px-4 py-2.5 bg-white border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all appearance-none"
            >
              <option>All</option>
              <option>Open</option>
              <option>In Progress</option>
              <option>Closed</option>
            </select>
          </div>
          <button
            onClick={handleSearch}
            disabled={loading}
            className="bg-indigo-500 hover:bg-indigo-600 text-white px-6 py-2.5 rounded-lg text-sm font-semibold flex items-center gap-2 transition-all shadow-md shadow-indigo-200 disabled:opacity-60"
          >
            <Search size={16} /> {loading ? 'Searching...' : 'Search'}
          </button>
        </div>

        {/* Table Container */}
        <div className="bg-gradient-to-br from-slate-50 to-indigo-50/30 rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-slate-200/60 flex items-center gap-3 bg-white/50 backdrop-blur-sm">
            <Folder size={18} className="text-amber-500" />
            <h3 className="font-bold text-slate-800">All Drawings</h3>
            <span className="bg-indigo-100 text-indigo-700 text-[10px] px-2.5 py-0.5 rounded-full font-bold">{total} total</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="text-xs text-slate-400 border-b border-slate-200/60 uppercase tracking-wider bg-white/30">
                  <th className="p-4 font-bold">Drawing No</th>
                  <th className="p-4 font-bold">Customer Doc No</th>
                  <th className="p-4 font-bold">Supplier</th>
                  <th className="p-4 font-bold">PO</th>
                  <th className="p-4 font-bold text-center">Total Comments</th>
                  <th className="p-4 font-bold text-center">Open</th>
                  <th className="p-4 font-bold text-center">Closed</th>
                  <th className="p-4 font-bold">Status</th>
                  <th className="p-4 font-bold">Actions</th>
                </tr>
              </thead>
              <tbody className="text-sm bg-white/60">
                {loading ? (
                  <tr><td colSpan={9} className="p-8 text-center text-slate-400 text-sm">Loading...</td></tr>
                ) : drawings.length === 0 ? (
                  <tr><td colSpan={9} className="p-8 text-center text-slate-400 text-sm">No drawings match your filters.</td></tr>
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
                      <span
                        onClick={() => goToReview(row.id)}
                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold border cursor-pointer hover:opacity-80 transition-opacity ${
                          row.status === 'Open' ? 'bg-red-50 text-red-600 border-red-100' :
                          row.status === 'In Progress' ? 'bg-amber-50 text-amber-600 border-amber-100' :
                          'bg-emerald-50 text-emerald-600 border-emerald-100'
                        }`}
                      >
                        <span className={`w-1.5 h-1.5 rounded-full ${row.status === 'Open' ? 'bg-red-500' : row.status === 'In Progress' ? 'bg-amber-500' : 'bg-emerald-500'}`}></span>
                        {row.status}
                      </span>
                    </td>
                    <td className="p-4">
                      <button
                        onClick={() => goToReview(row.id)}
                        className="bg-indigo-500 hover:bg-indigo-600 text-white px-4 py-1.5 rounded-md text-xs font-semibold shadow-sm transition-colors"
                      >
                        Review
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="p-4 border-t border-slate-200/60 bg-white/40 flex justify-between items-center text-sm text-slate-500">
            <span>Showing {drawings.length} of {total} drawings</span>
            <div className="flex gap-1">
              <button className="w-8 h-8 flex items-center justify-center rounded-md bg-indigo-500 text-white font-bold shadow-sm">1</button>
              <button className="w-8 h-8 flex items-center justify-center rounded-md bg-white border border-slate-200 hover:bg-slate-50 font-medium text-slate-600">2</button>
              <button className="w-8 h-8 flex items-center justify-center rounded-md bg-white border border-slate-200 hover:bg-slate-50 font-medium text-slate-600">3</button>
            </div>
          </div>
        </div>

      </div>
    </Layout>
  );
}
