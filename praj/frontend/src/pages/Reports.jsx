import React from 'react';
import Layout from '../components/Layout';
import { Download, FileText, Settings, RefreshCw } from 'lucide-react';

export default function Reports() {
  const reports = [
    { 
      title: "CRS Summary Report", 
      desc: "Full comment resolution sheet with status breakdown by drawing and supplier", 
      icon: "📊", 
      bg: "from-indigo-50 to-blue-100/50" 
    },
    { 
      title: "Engineer Performance", 
      desc: "Task completion rates, overdue items and resolution times per engineer", 
      icon: "📈", 
      bg: "from-emerald-50 to-teal-100/50" 
    },
    { 
      title: "Supplier Activity", 
      desc: "Drawing submissions, comment volumes and open/closed ratios per supplier", 
      icon: "🏭", 
      bg: "from-amber-50 to-orange-100/50" 
    },
    { 
      title: "Overdue Items Report", 
      desc: "All CRS items past target date, grouped by engineer and severity", 
      icon: "🚨", 
      bg: "from-rose-50 to-red-100/50" 
    },
    { 
      title: "OCR Quality Report", 
      desc: "Confidence score distribution, handwritten detection accuracy per drawing", 
      icon: "🤖", 
      bg: "from-purple-50 to-fuchsia-100/50" 
    },
    { 
      title: "Monthly Summary", 
      desc: "Month-by-month breakdown of drawings processed, comments and closures", 
      icon: "📅", 
      bg: "from-sky-50 to-cyan-100/50" 
    }
  ];

  return (
    <Layout>
      <div className="max-w-7xl mx-auto space-y-8">
        
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Reports</h1>
          <p className="text-sm text-slate-500">Generate and export engineering comment reports in multiple formats</p>
        </div>

        {/* Reports Grid */}
        <div className="grid grid-cols-3 gap-6">
          {reports.map((report, i) => (
            <div key={i} className={`bg-gradient-to-br ${report.bg} rounded-xl border border-white shadow-sm p-6 flex flex-col justify-between transition-transform hover:-translate-y-1`}>
              <div>
                <div className="text-3xl mb-4">{report.icon}</div>
                <h3 className="font-bold text-slate-800 mb-2">{report.title}</h3>
                <p className="text-sm text-slate-600 leading-relaxed mb-6">{report.desc}</p>
              </div>
              <div className="flex gap-3">
                <button className="flex-1 bg-indigo-500 hover:bg-indigo-600 text-white py-2 rounded-lg text-sm font-semibold flex items-center justify-center gap-2 shadow-sm transition-colors">
                  <Download size={14} /> Excel
                </button>
                <button className="flex-1 bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 py-2 rounded-lg text-sm font-semibold flex items-center justify-center gap-2 shadow-sm transition-colors">
                  <FileText size={14} className="text-slate-400" /> PDF
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Custom Report Builder */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="bg-slate-50 p-4 border-b border-slate-100 flex items-center gap-2 font-bold text-slate-700">
            <Settings size={18} className="text-slate-400" /> Custom Report Builder
          </div>
          
          <div className="p-6">
            <div className="grid grid-cols-3 gap-6 mb-6">
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">Date From</label>
                <input type="date" className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none text-slate-600" />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">Date To</label>
                <input type="date" className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none text-slate-600" />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">Supplier</label>
                <select className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none appearance-none text-slate-600">
                  <option>All Suppliers</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">Status Filter</label>
                <select className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none appearance-none text-slate-600">
                  <option>All</option>
                  <option>Open</option>
                  <option>Closed</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">Category</label>
                <select className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none appearance-none text-slate-600">
                  <option>All Categories</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">Format</label>
                <select className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none appearance-none text-slate-600">
                  <option>Excel (Image Embedded)</option>
                  <option>PDF Report</option>
                </select>
              </div>
            </div>

            <div className="flex gap-3">
              <button className="bg-indigo-500 hover:bg-indigo-600 text-white px-6 py-2.5 rounded-lg text-sm font-semibold flex items-center gap-2 shadow-md shadow-indigo-200 transition-all">
                <span className="text-amber-300">⚡</span> Generate Report
              </button>
              <button className="bg-white hover:bg-slate-50 text-indigo-600 border border-slate-200 px-6 py-2.5 rounded-lg text-sm font-semibold flex items-center gap-2 transition-all shadow-sm">
                <RefreshCw size={14} /> Reset Filters
              </button>
            </div>
          </div>
        </div>

      </div>
    </Layout>
  );
}