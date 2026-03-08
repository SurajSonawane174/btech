import React from 'react';
import Layout from '../components/Layout'; // Adjust path if necessary
import { AlertTriangle, ChevronRight, Folder, MessageCircle, Hourglass, ShieldAlert, FileText } from 'lucide-react';

export default function Dashboard() {
  return (
    <Layout>
      <div className="p-8 max-w-7xl mx-auto space-y-6">
        
        {/* Alert Banner */}
        <div className="bg-red-50 border border-red-100 rounded-lg p-3 flex items-center justify-between text-red-700">
          <div className="flex items-center gap-2 text-sm">
            <AlertTriangle size={18} className="text-red-500" />
            <span className="font-semibold text-red-600">3 overdue</span> CRS items — target dates have passed and need immediate resolution.
          </div>
          <button className="text-sm font-medium text-red-600 hover:text-red-800 flex items-center gap-1">
            View Overdue <ChevronRight size={16} />
          </button>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-4 gap-4">
          {[
            { title: "TOTAL DRAWINGS", count: "125", trend: "+ 12 vs last month", icon: Folder, color: "text-indigo-600", bg: "bg-indigo-50", line: "bg-indigo-500" },
            { title: "COMMENTS EXTRACTED", count: "6,540", trend: "+ 340 this week", icon: MessageCircle, color: "text-emerald-600", bg: "bg-emerald-50", line: "bg-emerald-500" },
            { title: "PENDING REVIEWS", count: "18", trend: "+ 5 since yesterday", icon: Hourglass, color: "text-amber-600", bg: "bg-amber-50", line: "bg-amber-500" },
            { title: "OVERDUE ITEMS", count: "3", trend: "+ 1 since last week", icon: ShieldAlert, color: "text-red-600", bg: "bg-red-50", line: "bg-red-500", trendColor: "text-red-500" }
          ].map((stat, i) => (
            <div key={i} className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm relative overflow-hidden">
              <div className={`absolute top-0 left-0 w-full h-1 ${stat.line}`}></div>
              <div className="flex justify-between items-start mb-4">
                <p className="text-[11px] font-bold text-slate-500 tracking-wider">{stat.title}</p>
                <div className={`p-2 rounded-lg ${stat.bg} ${stat.color}`}><stat.icon size={16} /></div>
              </div>
              <h3 className="text-3xl font-bold text-slate-800 mb-1">{stat.count}</h3>
              <p className={`text-xs ${stat.trendColor || 'text-emerald-500'} flex items-center gap-1 font-medium`}>↑ {stat.trend}</p>
            </div>
          ))}
        </div>

        {/* Main Content Grid (Table + Charts) */}
        <div className="grid grid-cols-3 gap-6 ">
          
          {/* Left Column (Table) */}
          <div className="col-span-2 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="p-5 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <FileText size={18} className="text-slate-400" />
                <h3 className="font-semibold text-slate-800">Recent Drawings</h3>
                <span className="bg-indigo-50 text-indigo-600 text-[10px] px-2 py-0.5 rounded-full font-semibold">7 shown</span>
              </div>
              <button className="text-xs text-indigo-600 font-medium hover:text-indigo-800">View All →</button>
            </div>
            
            {/* Tabs */}
            <div className="px-5 border-b border-slate-100 flex gap-6 text-sm">
              <button className="py-3 text-indigo-600 border-b-2 border-indigo-600 font-medium">All</button>
              <button className="py-3 text-slate-500 hover:text-slate-800">Open</button>
              <button className="py-3 text-slate-500 hover:text-slate-800">In Progress</button>
              <button className="py-3 text-slate-500 hover:text-slate-800">Closed</button>
            </div>

            {/* Table */}
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 text-xs text-slate-500 border-b border-slate-100">
                  <th className="p-4 font-medium">DRAWING NO</th>
                  <th className="p-4 font-medium">SUPPLIER</th>
                  <th className="p-4 font-medium">PO</th>
                  <th className="p-4 font-medium">COMMENTS</th>
                  <th className="p-4 font-medium">STATUS</th>
                </tr>
              </thead>
              <tbody className="text-sm">
                {[
                  { id: "chait-001", sup: "ABC Engineering", po: "PO-7788", com: "250", status: "Open" },
                  { id: "U-002", sup: "ABC Engineering", po: "PO-7788", com: "150", status: "In Progress" },
                  { id: "U-003", sup: "ABC Engineering", po: "PO-7788", com: "300", status: "Open" },
                  { id: "U-004", sup: "ABC Engineering", po: "PO-7788", com: "200", status: "Closed" },
                  { id: "ENGR-007", sup: "Delta Systems", po: "PO-5521", com: "88", status: "Open" },
                  { id: "ENGR-008", sup: "Delta Systems", po: "PO-5521", com: "42", status: "Closed" },
                ].map((row, i) => (
                  <tr key={i} className="border-b border-slate-50 hover:bg-slate-50">
                    <td className="p-4 text-indigo-600 font-medium">{row.id}</td>
                    <td className="p-4 text-slate-600">{row.sup}</td>
                    <td className="p-4 text-slate-600">{row.po}</td>
                    <td className="p-4 text-slate-800 font-medium">{row.com}</td>
                    <td className="p-4">
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium border ${
                        row.status === 'Open' ? 'bg-red-50 text-red-600 border-red-100' :
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
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Right Column (Charts) */}
          <div className="space-y-6">
            {/* CRS Status Chart Mockup */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
              <h3 className="font-semibold text-slate-800 flex items-center gap-2 mb-6">
                <span className="w-3 h-3 rounded-full bg-amber-700"></span> CRS Status
              </h3>
              <div className="flex items-center justify-center gap-6">
                <div className="relative w-32 h-32 rounded-full border-[12px] border-emerald-500 border-l-red-500 border-b-amber-500 flex items-center justify-center">
                   <div className="text-center">
                     <span className="block text-xl font-bold text-slate-800">6,540</span>
                     <span className="block text-[10px] text-slate-400">Total</span>
                   </div>
                </div>
                <div className="space-y-3 text-xs">
                  <div className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-emerald-500"></span><span className="text-slate-600">Closed</span><span className="font-semibold text-slate-800 ml-auto">3,597</span></div>
                  <div className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-amber-500"></span><span className="text-slate-600">In Progress</span><span className="font-semibold text-slate-800 ml-auto">1,635</span></div>
                  <div className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-red-500"></span><span className="text-slate-600">Open</span><span className="font-semibold text-slate-800 ml-auto">1,308</span></div>
                </div>
              </div>
            </div>

            {/* By Category Chart Mockup */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
              <h3 className="font-semibold text-slate-800 flex items-center gap-2 mb-4">
                <span className="w-3 h-3 rounded bg-amber-200 rotate-45"></span> By Category
              </h3>
              <div className="space-y-4">
                {[
                  { label: "Safety", value: "1,842", width: "w-[90%]", color: "bg-red-500" },
                  { label: "Design", value: "1,651", width: "w-[80%]", color: "bg-blue-500" },
                  { label: "Specs", value: "1,270", width: "w-[60%]", color: "bg-purple-500" },
                  { label: "Maintenance", value: "1,074", width: "w-[50%]", color: "bg-emerald-500" },
                  { label: "Labeling", value: "718", width: "w-[30%]", color: "bg-amber-500" },
                ].map((item, i) => (
                  <div key={i} className="flex items-center text-xs">
                    <span className="w-24 text-slate-600">{item.label}</span>
                    <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden mr-3">
                      <div className={`h-full ${item.width} ${item.color} rounded-full`}></div>
                    </div>
                    <span className="text-slate-400 w-10 text-right">{item.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Engineer Workload */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
          <div className="flex items-center gap-2 mb-6 border-b border-slate-100 pb-4">
            <span className="text-xl">👷</span>
            <h3 className="font-semibold text-slate-800">Engineer Workload</h3>
            <span className="bg-indigo-50 text-indigo-600 text-[10px] px-2 py-0.5 rounded-full font-semibold ml-2">5 engineers</span>
          </div>
          
          <div className="grid grid-cols-5 gap-6 divide-x divide-slate-100">
            {[
              { name: "ENGINEER A", count: 42, width: "w-[90%]" },
              { name: "ENGINEER B", count: 31, width: "w-[75%]" },
              { name: "ENGINEER C", count: 27, width: "w-[60%]" },
              { name: "ENGINEER D", count: 18, width: "w-[40%]" },
              { name: "ENGINEER E", count: 12, width: "w-[25%]" },
            ].map((eng, i) => (
              <div key={i} className={i !== 0 ? "pl-6" : ""}>
                <p className="text-[10px] font-bold text-slate-400 tracking-wider mb-2">{eng.name}</p>
                <p className="text-2xl font-bold text-slate-800 mb-3">{eng.count}</p>
                <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden mb-2">
                  <div className={`h-full bg-indigo-500 ${eng.width} rounded-full`}></div>
                </div>
                <p className="text-[10px] text-slate-400">tasks assigned</p>
              </div>
            ))}
          </div>
        </div>

      </div>
    </Layout>
  );
}