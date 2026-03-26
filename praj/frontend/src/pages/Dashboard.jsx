import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import { AlertTriangle, ChevronRight, Folder, MessageCircle, Hourglass, ShieldAlert, FileText } from 'lucide-react';

const TABS = ['All', 'Open', 'In Progress', 'Closed'];

export default function Dashboard() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('All');

  const [stats, setStats] = useState(null);
  const [drawings, setDrawings] = useState([]);
  const [crsStatus, setCrsStatus] = useState(null);
  const [categories, setCategories] = useState([]);
  const [engineers, setEngineers] = useState([]);

  useEffect(() => {
    fetch('http://localhost:8080/api/comments/PRJ001-DWG001-001-053-005')
  .then(async (res) => {
    console.log("STATUS:", res.status);

    if (!res.ok) {
      const text = await res.text();
      throw new Error(text);
    }

    return res.json();
  })
  .then(data => {
    console.log("DATA:", data);
    setDrawings(data);
  })
  .catch(err => console.error("FETCH ERROR:", err));
    // fetch('/api/dashboard/recent-drawings').then(r => r.json()).then(setDrawings).catch(console.error);
    // fetch('/api/dashboard/crs-status').then(r => r.json()).then(setCrsStatus).catch(console.error);
    // fetch('/api/dashboard/categories').then(r => r.json()).then(setCategories).catch(console.error);
    // fetch('/api/dashboard/engineer-workload').then(r => r.json()).then(setEngineers).catch(console.error);
  }, []);

  const filteredDrawings = activeTab === 'All'
    ? drawings
    : drawings.filter(d => d.status === activeTab);

  // stats cards config — values come from API
  // Expected stats shape: { totalDrawings, totalDrawingsTrend, commentsExtracted, commentsExtractedTrend,
  //                         pendingReviews, pendingReviewsTrend, overdueItems, overdueItemsTrend }
  const statCards = stats ? [
    { title: "TOTAL DRAWINGS",     count: stats.totalDrawings,     trend: stats.totalDrawingsTrend,     icon: Folder,      color: "text-indigo-600", bg: "bg-indigo-50", line: "bg-indigo-500" },
    { title: "COMMENTS EXTRACTED", count: stats.commentsExtracted, trend: stats.commentsExtractedTrend, icon: MessageCircle, color: "text-emerald-600", bg: "bg-emerald-50", line: "bg-emerald-500" },
    { title: "PENDING REVIEWS",    count: stats.pendingReviews,    trend: stats.pendingReviewsTrend,    icon: Hourglass,   color: "text-amber-600",  bg: "bg-amber-50",  line: "bg-amber-500" },
    { title: "OVERDUE ITEMS",      count: stats.overdueItems,      trend: stats.overdueItemsTrend,      icon: ShieldAlert, color: "text-red-600",    bg: "bg-red-50",    line: "bg-red-500", trendColor: "text-red-500" },
  ] : [];

  // Expected drawings item shape: { id, sup, po, com, status }
  // Expected crsStatus shape: { total, closed, inProgress, open }
  // Expected categories item shape: { label, value, width (e.g. "w-[90%]"), color (e.g. "bg-red-500") }
  // Expected engineers item shape: { name, count, width (e.g. "w-[90%]") }

  const maxEngCount = engineers.length ? Math.max(...engineers.map(e => e.count)) : 1;

return (
  <div>
        {JSON.stringify(drawings)}
  </div>
);
  return (
    <Layout>
      <div className="p-8 max-w-7xl mx-auto space-y-6">

        {/* Alert Banner */}
        {stats?.overdueItems > 0 && (
          <div className="bg-red-50 border border-red-100 rounded-lg p-3 flex items-center justify-between text-red-700">
            <div className="flex items-center gap-2 text-sm">
              <AlertTriangle size={18} className="text-red-500" />
              <span className="font-semibold text-red-600">{stats.overdueItems} overdue</span> CRS items — target dates have passed and need immediate resolution.
            </div>
            <button onClick={() => navigate('/notifications')} className="text-sm font-medium text-red-600 hover:text-red-800 flex items-center gap-1">
              View Overdue <ChevronRight size={16} />
            </button>
          </div>
        )}

        {/* Stats Grid */}
        <div className="grid grid-cols-4 gap-4">
          {statCards.map((stat, i) => (
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
        <div className="grid grid-cols-3 gap-6">

          {/* Left Column (Table) */}
          <div className="col-span-2 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="p-5 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <FileText size={18} className="text-slate-400" />
                <h3 className="font-semibold text-slate-800">Recent Drawings</h3>
                <span className="bg-indigo-50 text-indigo-600 text-[10px] px-2 py-0.5 rounded-full font-semibold">{filteredDrawings.length} shown</span>
              </div>
              <button onClick={() => navigate('/comments')} className="text-xs text-indigo-600 font-medium hover:text-indigo-800">
                View All →
              </button>
            </div>

            {/* Tabs */}
            <div className="px-5 border-b border-slate-100 flex gap-6 text-sm">
              {TABS.map(tab => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`py-3 transition-colors ${activeTab === tab ? 'text-indigo-600 border-b-2 border-indigo-600 font-medium' : 'text-slate-500 hover:text-slate-800'}`}
                >
                  {tab}
                </button>
              ))}
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
                {filteredDrawings.length === 0 ? (
                  <tr><td colSpan={5} className="p-6 text-center text-slate-400 text-xs">No drawings found for this status.</td></tr>
                ) : filteredDrawings.map((row, i) => (
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
                        <span className={`w-1.5 h-1.5 rounded-full ${row.status === 'Open' ? 'bg-red-500' : row.status === 'In Progress' ? 'bg-amber-500' : 'bg-emerald-500'}`}></span>
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
            {/* CRS Status */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
              <h3 className="font-semibold text-slate-800 flex items-center gap-2 mb-6">
                <span className="w-3 h-3 rounded-full bg-amber-700"></span> CRS Status
              </h3>
              {crsStatus && (
                <div className="flex items-center justify-center gap-6">
                  <div className="relative w-32 h-32 rounded-full border-[12px] border-emerald-500 border-l-red-500 border-b-amber-500 flex items-center justify-center">
                    <div className="text-center">
                      <span className="block text-xl font-bold text-slate-800">{crsStatus.total?.toLocaleString()}</span>
                      <span className="block text-[10px] text-slate-400">Total</span>
                    </div>
                  </div>
                  <div className="space-y-3 text-xs">
                    <div className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-emerald-500"></span><span className="text-slate-600">Closed</span><span className="font-semibold text-slate-800 ml-auto">{crsStatus.closed?.toLocaleString()}</span></div>
                    <div className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-amber-500"></span><span className="text-slate-600">In Progress</span><span className="font-semibold text-slate-800 ml-auto">{crsStatus.inProgress?.toLocaleString()}</span></div>
                    <div className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-red-500"></span><span className="text-slate-600">Open</span><span className="font-semibold text-slate-800 ml-auto">{crsStatus.open?.toLocaleString()}</span></div>
                  </div>
                </div>
              )}
            </div>

            {/* By Category */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
              <h3 className="font-semibold text-slate-800 flex items-center gap-2 mb-4">
                <span className="w-3 h-3 rounded bg-amber-200 rotate-45"></span> By Category
              </h3>
              <div className="space-y-4">
                {categories.map((item, i) => (
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
            <span className="bg-indigo-50 text-indigo-600 text-[10px] px-2 py-0.5 rounded-full font-semibold ml-2">{engineers.length} engineers</span>
          </div>

          <div className="grid gap-6 divide-x divide-slate-100" style={{ gridTemplateColumns: `repeat(${engineers.length || 1}, minmax(0, 1fr))` }}>
            {engineers.map((eng, i) => (
              <div key={i} className={i !== 0 ? "pl-6" : ""}>
                <p className="text-[10px] font-bold text-slate-400 tracking-wider mb-2">{eng.name}</p>
                <p className="text-2xl font-bold text-slate-800 mb-3">{eng.count}</p>
                <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden mb-2">
                  <div className={`h-full bg-indigo-500 rounded-full`} style={{ width: `${Math.round((eng.count / maxEngCount) * 100)}%` }}></div>
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