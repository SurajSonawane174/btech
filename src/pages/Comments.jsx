import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import { Search, Folder } from 'lucide-react';

const ALL_DRAWINGS = [
  { id: "praj-001", doc: "CUST-001", sup: "ABC Engineering", po: "PO-7788", tot: 250, opn: 100, cls: 150, status: "Open" },
  { id: "U-002", doc: "CUST-002", sup: "ABC Engineering", po: "PO-7788", tot: 150, opn: 50, cls: 100, status: "In Progress" },
  { id: "U-003", doc: "CUST-003", sup: "ABC Engineering", po: "PO-7788", tot: 300, opn: 150, cls: 150, status: "Open" },
  { id: "U-004", doc: "CUST-004", sup: "ABC Engineering", po: "PO-7788", tot: 200, opn: 0, cls: 200, status: "Closed" },
  { id: "U-005", doc: "CUST-005", sup: "ABC Engineering", po: "PO-7788", tot: 180, opn: 80, cls: 100, status: "In Progress" },
  { id: "ENGR-007", doc: "CUST-006", sup: "Delta Systems", po: "PO-5521", tot: 88, opn: 55, cls: 33, status: "Open" },
  { id: "ENGR-008", doc: "CUST-007", sup: "Delta Systems", po: "PO-5521", tot: 42, opn: 0, cls: 42, status: "Closed" },
];

export default function Comments() {
  const navigate = useNavigate();
  const [drawingNo, setDrawingNo] = useState('');
  const [supplier, setSupplier] = useState('');
  const [status, setStatus] = useState('All');
  const [filtered, setFiltered] = useState(ALL_DRAWINGS);

  function applyFilters(dNo, sup, sts) {
    const result = ALL_DRAWINGS.filter(row => {
      const matchDrawing = dNo === '' || row.id.toLowerCase().includes(dNo.toLowerCase());
      const matchSupplier = sup === '' || row.sup.toLowerCase().includes(sup.toLowerCase());
      const matchStatus = sts === 'All' || row.status === sts;
      return matchDrawing && matchSupplier && matchStatus;
    });
    setFiltered(result);
  }

  function handleStatusChange(value) {
    setStatus(value);
    applyFilters(drawingNo, supplier, value);
  }

  function handleSearch() {
    applyFilters(drawingNo, supplier, status);
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
            className="bg-indigo-500 hover:bg-indigo-600 text-white px-6 py-2.5 rounded-lg text-sm font-semibold flex items-center gap-2 transition-all shadow-md shadow-indigo-200"
          >
            <Search size={16} /> Search
          </button>
        </div>

        {/* Table Container */}
        <div className="bg-gradient-to-br from-slate-50 to-indigo-50/30 rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-slate-200/60 flex items-center gap-3 bg-white/50 backdrop-blur-sm">
            <Folder size={18} className="text-amber-500" />
            <h3 className="font-bold text-slate-800">All Drawings</h3>
            <span className="bg-indigo-100 text-indigo-700 text-[10px] px-2.5 py-0.5 rounded-full font-bold">{filtered.length} total</span>
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
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="p-8 text-center text-slate-400 text-sm">No drawings match your filters.</td>
                  </tr>
                ) : filtered.map((row, i) => (
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
            <span>Showing {filtered.length} of {ALL_DRAWINGS.length} drawings</span>
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