import React from 'react';
import Layout from '../components/Layout';
import { FileText, Download, FileSpreadsheet, Image as ImageIcon, Calendar } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function CRSReview() {
  const tableData = [
    { sr: 1, doc: "chait-001", rev: "A", cDoc: "CUST-001", cRev: "1", page: 4, cId: "C-001", comment: "Revise gas detector location", person: "John Doe", date: "2023-01-01", color: "Red", client: "Y", cat: "Safety", hw: "N", conf: "92", assignee: "Engineer A", target: "2023-02-01", crs: "CRS-001", res: "Location updated in rev", status: "Open", ev: "link/to/evidence" },
    { sr: 2, doc: "chait-001", rev: "A", cDoc: "CUST-001", cRev: "1", page: 5, cId: "C-002", comment: "Check pipe diameter", person: "Jane Smith", date: "2023-01-02", color: "Blue", client: "N", cat: "Design", hw: "Y", conf: "85", assignee: "Engineer B", target: "2023-02-02", crs: "CRS-002", res: "Diameter confirmed", status: "In Progress", ev: "link/to/evidence" },
    { sr: 3, doc: "chait-001", rev: "A", cDoc: "CUST-001", cRev: "1", page: 6, cId: "C-003", comment: "Add valve", person: "Alice", date: "2023-01-03", color: "Green", client: "Y", cat: "Maintenance", hw: "N", conf: "95", assignee: "Engineer C", target: "2023-02-03", crs: "CRS-003", res: "Valve added", status: "Closed", ev: "link/to/evidence" },
    { sr: 4, doc: "chait-001", rev: "A", cDoc: "CUST-001", cRev: "1", page: 7, cId: "C-004", comment: "Update label", person: "Bob", date: "2023-01-04", color: "Yellow", client: "N", cat: "Labeling", hw: "Y", conf: "88", assignee: "Engineer D", target: "2023-02-04", crs: "CRS-004", res: "Label updated", status: "Open", ev: "link/to/evidence" },
    { sr: 5, doc: "chait-001", rev: "A", cDoc: "CUST-001", cRev: "1", page: 8, cId: "C-005", comment: "Review specs", person: "Charlie", date: "2023-01-05", color: "Orange", client: "Y", cat: "Specs", hw: "N", conf: "90", assignee: "Engineer E", target: "2023-02-05", crs: "CRS-005", res: "Specs reviewed", status: "Closed", ev: "link/to/evidence" },
  ];

  const getCategoryColor = (cat) => {
    switch(cat) {
      case 'Safety': return 'text-red-600 bg-red-50 border-red-100';
      case 'Design': return 'text-blue-600 bg-blue-50 border-blue-100';
      case 'Maintenance': return 'text-emerald-600 bg-emerald-50 border-emerald-100';
      case 'Labeling': return 'text-amber-600 bg-amber-50 border-amber-100';
      case 'Specs': return 'text-teal-600 bg-teal-50 border-teal-100';
      default: return 'text-slate-600 bg-slate-50 border-slate-100';
    }
  };

  return (
    <Layout>
      <div className="max-w-full 2xl:max-w-7xl mx-auto space-y-6">
        
        {/* Header */}
        <div className="flex justify-between items-end">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">CRS Review — PRAJ-001</h1>
            <p className="text-sm text-slate-500">Inline comment resolution — assign, update status, add evidence</p>
          </div>
          <div className="flex gap-3">
            <button className="bg-white border border-slate-200 hover:bg-slate-50 text-indigo-600 px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-all shadow-sm">
              <FileSpreadsheet size={16} className="text-emerald-500" /> Download Excel
            </button>
            <button className="bg-indigo-500 hover:bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-all shadow-sm">
              <FileText size={16} /> Download PDF
            </button>
          </div>
        </div>

        {/* Metadata Banner */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 grid grid-cols-6 gap-4">
          {[
            { label: 'DOC NO', val: 'chait-001' },
            { label: 'REVISION', val: 'A' },
            { label: 'CUST DOC NO', val: 'CUST-001' },
            { label: 'CUST REVISION', val: '1' },
            { label: 'SUPPLIER', val: 'ABC Engineering' },
            { label: 'PO', val: 'PO-7788' }
          ].map((item, i) => (
            <div key={i}>
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">{item.label}</p>
              <p className="font-bold text-slate-800 text-sm">{item.val}</p>
            </div>
          ))}
        </div>

        {/* Resolution Grid Table Container */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
          <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
            <div className="flex items-center gap-3">
              <FileText size={18} className="text-rose-400" />
              <h3 className="font-bold text-slate-800">Resolution Grid</h3>
              <span className="bg-indigo-100 text-indigo-700 text-[10px] px-2.5 py-0.5 rounded-full font-bold">5 comments</span>
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
                {tableData.map((row, i) => (
                  <tr key={i} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                    <td className="p-4 text-slate-500">{row.sr}</td>
                    <td className="p-4 font-bold text-red-500">{row.doc}</td>
                    <td className="p-4">{row.rev}</td>
                    <td className="p-4 font-bold text-red-500">{row.cDoc}</td>
                    <td className="p-4">{row.cRev}</td>
                    <td className="p-4">{row.page}</td>
                    <td className="p-4 font-bold text-indigo-600">{row.cId}</td>
                    <td className="p-4 font-medium text-slate-800">{row.comment}</td>
                    <td className="p-4 text-center"><ImageIcon size={18} className="text-emerald-500/80 mx-auto" /></td>
                    <td className="p-4">{row.person}</td>
                    <td className="p-4 text-emerald-600 font-medium">{row.date}</td>
                    <td className="p-4 font-medium" style={{ color: row.color.toLowerCase() }}>{row.color}</td>
                    <td className="p-4 font-bold text-emerald-600">{row.client}</td>
                    <td className="p-4">
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold border ${getCategoryColor(row.cat)}`}>
                        <span className={`w-1.5 h-1.5 rounded-full bg-current opacity-70`}></span>
                        {row.cat}
                      </span>
                    </td>
                    <td className="p-4 text-center font-medium">{row.hw}</td>
                    <td className="p-4 font-bold text-emerald-600">{row.conf}</td>
                    
                    {/* Interactive Form Fields */}
                    <td className="p-4">
                      <select className="w-full bg-slate-50 border border-slate-200 text-slate-700 text-xs rounded-md px-2 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none">
                        <option>{row.assignee}</option>
                        <option>Engineer A</option>
                        <option>Engineer B</option>
                        <option>Engineer C</option>
                      </select>
                    </td>
                    <td className="p-4 relative">
                      <input type="text" defaultValue="02/01/2023" className="w-[110px] bg-slate-50 border border-slate-200 text-slate-700 text-xs rounded-md pl-2 pr-7 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none" />
                      <Calendar size={12} className="absolute right-6 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                    </td>
                    <td className="p-4 font-bold text-indigo-600">{row.crs}</td>
                    <td className="p-4">
                      <input type="text" defaultValue={row.res} className="w-full bg-slate-50 border border-slate-200 text-slate-700 text-xs rounded-md px-2 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none" />
                    </td>
                    <td className="p-4">
                      <select className="w-full bg-slate-50 border border-slate-200 text-slate-700 text-xs rounded-md px-2 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none">
                        <option>{row.status}</option>
                        <option>Open</option>
                        <option>In Progress</option>
                        <option>Closed</option>
                      </select>
                    </td>
                    <td className="p-4">
                      <input type="text" defaultValue={row.ev} className="w-full bg-slate-50 border border-slate-200 text-slate-700 text-xs rounded-md px-2 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none" />
                    </td>
                    <td className="p-4 text-center">
                      <button className="bg-indigo-500 hover:bg-indigo-600 text-white px-3 py-1.5 rounded text-xs font-bold transition-colors shadow-sm">Save</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="p-4 border-t border-slate-200/60 flex justify-between items-center text-sm text-slate-500 bg-white">
            <span>Showing 5 of 5 — Page 1 of 2</span>
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