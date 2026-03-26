import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import Layout from '../components/Layout';
import api from '../api/axios';
import { FileText, Download, FileSpreadsheet, Image as ImageIcon, Calendar } from 'lucide-react';

export default function CRSReview() {
  const { drawingNo } = useParams();

  const [metadata, setMetadata] = useState(null);
  const [tableData, setTableData] = useState([]);
  const [engineers, setEngineers] = useState([]);
  // Track per-row unsaved edits: { [index]: { assignee, target, resolution, status, evidence } }
  const [rowEdits, setRowEdits] = useState({});

  // Expected metadata shape: { docNo, revision, custDocNo, custRevision, supplier, po }
  // Expected tableData item shape: { sr, doc, rev, cDoc, cRev, page, cId, comment, snapshotUrl,
  //   person, date, color, client, cat, hw, conf, assignee, target, crs, res, status, ev }
  // Expected engineers: [{ id, name }]

  useEffect(() => {
    const id = drawingNo || 'PRAJ-001';
    api.get(`/api/crs/drawing/${id}/metadata`).then(r => setMetadata(r.data)).catch(console.error);
    api.get(`/api/crs/drawing/${id}/comments`).then(r => setTableData(r.data)).catch(console.error);
    api.get('/api/engineers').then(r => setEngineers(r.data)).catch(console.error);
  }, [drawingNo]);

  function setField(rowIndex, field, value) {
    setRowEdits(prev => ({ ...prev, [rowIndex]: { ...prev[rowIndex], [field]: value } }));
  }

  async function handleSave(rowIndex) {
    const row = tableData[rowIndex];
    const edits = rowEdits[rowIndex] || {};
    const payload = {
      commentId: row.cId,
      assignee:   edits.assignee   ?? row.assignee,
      target:     edits.target     ?? row.target,
      resolution: edits.resolution ?? row.res,
      status:     edits.status     ?? row.status,
      evidence:   edits.evidence   ?? row.ev,
    };
    try {
      await api.patch(`/api/crs/drawing/${drawingNo}/comments/${row.cId}`, payload);
      setTableData(prev => prev.map((r, i) => i === rowIndex ? { ...r, ...payload, res: payload.resolution, ev: payload.evidence } : r));
      setRowEdits(prev => { const n = { ...prev }; delete n[rowIndex]; return n; });
    } catch (err) {
      console.error('Save failed:', err);
    }
  }

  async function handleDownload(format) {
    try {
      const res = await api.get(`/api/crs/drawing/${drawingNo}/export/${format}`, { responseType: 'blob' });
      const blob = res.data;
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${drawingNo}-crs.${format === 'excel' ? 'xlsx' : 'pdf'}`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download failed:', err);
    }
  }

  const getCategoryColor = (cat) => {
    switch (cat) {
      case 'Safety':      return 'text-red-600 bg-red-50 border-red-100';
      case 'Design':      return 'text-blue-600 bg-blue-50 border-blue-100';
      case 'Maintenance': return 'text-emerald-600 bg-emerald-50 border-emerald-100';
      case 'Labeling':    return 'text-amber-600 bg-amber-50 border-amber-100';
      case 'Specs':       return 'text-teal-600 bg-teal-50 border-teal-100';
      default:            return 'text-slate-600 bg-slate-50 border-slate-100';
    }
  };

  return (
    <Layout>
      <div className="max-w-full 2xl:max-w-7xl mx-auto space-y-6">

        {/* Header */}
        <div className="flex justify-between items-end">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">CRS Review — {drawingNo || metadata?.docNo}</h1>
            <p className="text-sm text-slate-500">Inline comment resolution — assign, update status, add evidence</p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => handleDownload('excel')}
              className="bg-white border border-slate-200 hover:bg-slate-50 text-indigo-600 px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-all shadow-sm"
            >
              <FileSpreadsheet size={16} className="text-emerald-500" /> Download Excel
            </button>
            <button
              onClick={() => handleDownload('pdf')}
              className="bg-indigo-500 hover:bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-all shadow-sm"
            >
              <FileText size={16} /> Download PDF
            </button>
          </div>
        </div>

        {/* Metadata Banner */}
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
                <p className="font-bold text-slate-800 text-sm">{item.val}</p>
              </div>
            ))}
          </div>
        )}

        {/* Resolution Grid Table Container */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
          <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
            <div className="flex items-center gap-3">
              <FileText size={18} className="text-rose-400" />
              <h3 className="font-bold text-slate-800">Resolution Grid</h3>
              <span className="bg-indigo-100 text-indigo-700 text-[10px] px-2.5 py-0.5 rounded-full font-bold">{tableData.length} comments</span>
            </div>
            <Link to="/get-crs" className="text-sm text-indigo-600 hover:text-indigo-800 transition-colors">
              ← Back to Lookup
            </Link>
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
                  <tr><td colSpan={23} className="p-8 text-center text-slate-400 text-sm">Loading comments...</td></tr>
                ) : tableData.map((row, i) => {
                  const edits = rowEdits[i] || {};
                  return (
                    <tr key={i} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
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
                          onChange={e => setField(i, 'assignee', e.target.value)}
                          className="w-full bg-slate-50 border border-slate-200 text-slate-700 text-xs rounded-md px-2 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none"
                        >
                          {engineers.map(eng => <option key={eng.id} value={eng.name}>{eng.name}</option>)}
                        </select>
                      </td>
                      <td className="p-4 relative">
                        <input
                          type="text"
                          value={edits.target ?? row.target}
                          onChange={e => setField(i, 'target', e.target.value)}
                          className="w-[110px] bg-slate-50 border border-slate-200 text-slate-700 text-xs rounded-md pl-2 pr-7 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none"
                        />
                        <Calendar size={12} className="absolute right-6 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                      </td>
                      <td className="p-4 font-bold text-indigo-600">{row.crs}</td>
                      <td className="p-4">
                        <input
                          type="text"
                          value={edits.resolution ?? row.res}
                          onChange={e => setField(i, 'resolution', e.target.value)}
                          className="w-full bg-slate-50 border border-slate-200 text-slate-700 text-xs rounded-md px-2 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none"
                        />
                      </td>
                      <td className="p-4">
                        <select
                          value={edits.status ?? row.status}
                          onChange={e => setField(i, 'status', e.target.value)}
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
                          value={edits.evidence ?? row.ev}
                          onChange={e => setField(i, 'evidence', e.target.value)}
                          className="w-full bg-slate-50 border border-slate-200 text-slate-700 text-xs rounded-md px-2 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none"
                        />
                      </td>
                      <td className="p-4 text-center">
                        <button
                          onClick={() => handleSave(i)}
                          className="bg-indigo-500 hover:bg-indigo-600 text-white px-3 py-1.5 rounded text-xs font-bold transition-colors shadow-sm"
                        >
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
            <span>Showing {tableData.length} comments</span>
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