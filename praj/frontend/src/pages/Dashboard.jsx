import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import { AlertTriangle, ChevronRight, Folder, MessageCircle, Hourglass, ShieldAlert, FileText, Loader2, TrendingUp } from 'lucide-react';
import { 
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, BarChart, Bar
} from 'recharts';

const TABS = ['All', 'Open', 'In Progress', 'Closed'];
// const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8080';
    const BASE_URL = 'http://localhost:8080';

// Chart Colors
const COLORS = {
  closed: '#10b981',     // Emerald
  inProgress: '#f59e0b', // Amber
  open: '#ef4444',       // Red
  primary: '#6366f1',    // Indigo
  secondary: '#818cf8'   // Light Indigo
};

export default function Dashboard() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('All');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Data States
  const [stats, setStats] = useState(null);
  const [drawings, setDrawings] = useState([]);
  const [crsStatus, setCrsStatus] = useState(null);
  const [categories, setCategories] = useState([]);
  const [engineers, setEngineers] = useState([]);
  const [trends, setTrends] = useState([]); // NEW: Time-series data

  useEffect(() => {
    const fetchAPI = async (endpoint) => {
      const res = await fetch(`${BASE_URL}${endpoint}`);
      if (!res.ok) throw new Error(`Failed to fetch ${endpoint}`);
      return res.json();
    };

    const loadDashboardData = async () => {
      setIsLoading(true);
      try {
        const results = await Promise.allSettled([
          fetchAPI('/api/documents'),
          fetchAPI('/api/dashboard/stats'),
          fetchAPI('/api/dashboard/crs-status'),
          fetchAPI('/api/dashboard/categories'),
          fetchAPI('/api/dashboard/engineer-workload'),
          fetchAPI('/api/dashboard/trends') // New endpoint for the line chart
        ]);

        if (results[0].status === 'fulfilled') {
          setDrawings(results[0].value.map(doc => ({
            id: doc.praj_document_number || '-', sup: doc.supplier_name || 'Unknown', 
            po: doc.supplier_po_number || '-', com: doc.comments || '-', 
            status: doc.status || 'Open', dbId: doc.id
          })));
        }

        if (results[1].status === 'fulfilled') setStats(results[1].value);
        if (results[2].status === 'fulfilled') setCrsStatus(results[2].value);
        if (results[3].status === 'fulfilled') setCategories(results[3].value);
        if (results[4].status === 'fulfilled') setEngineers(results[4].value);
        
        // Handle Trends or use fallback mock data if API isn't ready yet
        if (results[5].status === 'fulfilled') {
          setTrends(results[5].value);
        } else {
          setTrends([
            { date: 'Mon', extracted: 120, resolved: 80 },
            { date: 'Tue', extracted: 180, resolved: 110 },
            { date: 'Wed', extracted: 250, resolved: 160 },
            { date: 'Thu', extracted: 210, resolved: 190 },
            { date: 'Fri', extracted: 290, resolved: 240 },
            { date: 'Sat', extracted: 140, resolved: 120 },
            { date: 'Sun', extracted: 90, resolved: 150 },
          ]);
        }
      } catch (err) {
        setError("Failed to load dashboard data.");
      } finally {
        setIsLoading(false);
      }
    };
    loadDashboardData();
  }, []);

  const filteredDrawings = activeTab === 'All' ? drawings : drawings.filter(d => d.status === activeTab);

  const pieData = crsStatus ? [
    { name: 'Closed', value: crsStatus.closed, color: COLORS.closed },
    { name: 'In Progress', value: crsStatus.inProgress, color: COLORS.inProgress },
    { name: 'Open', value: crsStatus.open, color: COLORS.open }
  ] : [];

  if (isLoading) return (
    <Layout><div className="flex flex-col items-center justify-center h-[80vh] text-slate-500"><Loader2 className="w-8 h-8 animate-spin mb-4 text-indigo-600" /><p>Loading analytics...</p></div></Layout>
  );

  return (
    <Layout>
      <div className="p-8 max-w-[1400px] mx-auto space-y-6 bg-slate-50 min-h-screen">
        
        {/* Header & Alerts */}
        <div className="flex justify-between items-end mb-2">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">Overview Dashboard</h1>
            <p className="text-sm text-slate-500">Real-time comment extraction and CRS performance.</p>
          </div>
        </div>

        {error && <div className="bg-red-50 text-red-600 p-4 rounded-lg">{error}</div>}
        
        {stats?.overdueItems > 0 && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-center justify-between shadow-sm">
            <div className="flex items-center gap-3">
              <ShieldAlert className="text-red-500" size={24} />
              <div>
                <h4 className="font-bold text-red-800 text-sm">Action Required</h4>
                <p className="text-sm text-red-600"><span className="font-bold">{stats.overdueItems}</span> CRS items are overdue.</p>
              </div>
            </div>
            <button onClick={() => navigate('/notifications')} className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg transition-colors">
              Review Overdue
            </button>
          </div>
        )}

        {/* Top KPIs */}
        <div className="grid grid-cols-4 gap-6">
          {[
            { title: "TOTAL DRAWINGS", val: stats?.totalDrawings, icon: Folder, color: "text-indigo-600", bg: "bg-white", border: "border-indigo-100" },
            { title: "COMMENTS EXTRACTED", val: stats?.commentsExtracted, icon: MessageCircle, color: "text-emerald-600", bg: "bg-white", border: "border-emerald-100" },
            { title: "PENDING REVIEWS", val: stats?.pendingReviews, icon: Hourglass, color: "text-amber-600", bg: "bg-white", border: "border-amber-100" },
            { title: "OVERDUE ITEMS", val: stats?.overdueItems, icon: AlertTriangle, color: "text-red-600", bg: "bg-white", border: "border-red-100" }
          ].map((stat, i) => (
            <div key={i} className={`bg-white p-6 rounded-2xl border ${stat.border} shadow-sm flex items-center gap-4`}>
              <div className={`p-4 rounded-xl ${stat.color} bg-slate-50 border border-slate-100`}><stat.icon size={24} /></div>
              <div>
                <p className="text-[11px] font-bold text-slate-500 tracking-wider mb-1">{stat.title}</p>
                <h3 className="text-3xl font-extrabold text-slate-800">{stat.val || 0}</h3>
              </div>
            </div>
          ))}
        </div>

        {/* Middle Section: Trends & Donut */}
        <div className="grid grid-cols-3 gap-6">
          {/* Trend Chart (Spans 2 columns) */}
          <div className="col-span-2 bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <div className="flex items-center gap-2 mb-6">
              <TrendingUp className="text-indigo-500" size={20} />
              <h3 className="font-bold text-slate-800">Extraction vs Resolution Trend</h3>
            </div>
            <div className="h-[280px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trends} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorExtracted" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={COLORS.primary} stopOpacity={0.3}/>
                      <stop offset="95%" stopColor={COLORS.primary} stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="colorResolved" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={COLORS.closed} stopOpacity={0.3}/>
                      <stop offset="95%" stopColor={COLORS.closed} stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                  <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#64748b' }} dy={10} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#64748b' }} />
                  <RechartsTooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                  <Legend verticalAlign="top" height={36} iconType="circle" />
                  <Area type="monotone" dataKey="extracted" name="Comments Extracted" stroke={COLORS.primary} strokeWidth={3} fillOpacity={1} fill="url(#colorExtracted)" />
                  <Area type="monotone" dataKey="resolved" name="Comments Resolved" stroke={COLORS.closed} strokeWidth={3} fillOpacity={1} fill="url(#colorResolved)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Real Donut Chart */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 flex flex-col">
            <h3 className="font-bold text-slate-800 mb-2">Overall CRS Status</h3>
            <p className="text-xs text-slate-500 mb-4">Current state of all extracted comments.</p>
            <div className="flex-1 min-h-[250px] relative">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={pieData} innerRadius={70} outerRadius={100} paddingAngle={5} dataKey="value" stroke="none">
                    {pieData.map((entry, index) => <Cell key={`cell-${index}`} fill={entry.color} />)}
                  </Pie>
                  <RechartsTooltip formatter={(value) => [`${value} Comments`, 'Count']} contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                </PieChart>
              </ResponsiveContainer>
              {/* Center Text inside Donut */}
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-3xl font-extrabold text-slate-800">{crsStatus?.total || 0}</span>
                <span className="text-xs text-slate-400 font-medium">Total</span>
              </div>
            </div>
            
            {/* Custom Legend */}
            <div className="grid grid-cols-3 gap-2 mt-4 text-center border-t border-slate-100 pt-4">
              <div>
                <p className="text-[10px] text-slate-400 uppercase font-bold mb-1">Closed</p>
                <p className="text-lg font-bold text-emerald-600">{crsStatus?.closed || 0}</p>
              </div>
              <div className="border-x border-slate-100">
                <p className="text-[10px] text-slate-400 uppercase font-bold mb-1">In Prog</p>
                <p className="text-lg font-bold text-amber-600">{crsStatus?.inProgress || 0}</p>
              </div>
              <div>
                <p className="text-[10px] text-slate-400 uppercase font-bold mb-1">Open</p>
                <p className="text-lg font-bold text-red-600">{crsStatus?.open || 0}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Section: Workload & Table */}
        <div className="grid grid-cols-3 gap-6">
          
          {/* Engineer Bar Chart */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <h3 className="font-bold text-slate-800 mb-6">Workload by Engineer</h3>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={engineers} layout="vertical" margin={{ top: 0, right: 20, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke="#f1f5f9" />
                  <XAxis type="number" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#94a3b8' }} />
                  <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#475569', fontWeight: 500 }} width={80} />
                  <RechartsTooltip cursor={{ fill: '#f8fafc' }} contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                  <Bar dataKey="count" name="Assigned Tasks" fill={COLORS.primary} radius={[0, 4, 4, 0]} barSize={24} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Recent Drawings Table */}
          <div className="col-span-2 bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col h-[400px]">
            <div className="p-5 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
              <h3 className="font-bold text-slate-800 flex items-center gap-2"><FileText size={18} className="text-indigo-500"/> Recent Document Processing</h3>
              <button onClick={() => navigate('/comments')} className="text-sm text-indigo-600 font-bold hover:text-indigo-800">View Master List →</button>
            </div>

            <div className="flex gap-1 p-2 bg-white border-b border-slate-100">
              {TABS.map(tab => (
                <button key={tab} onClick={() => setActiveTab(tab)} className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all ${activeTab === tab ? 'bg-indigo-50 text-indigo-700' : 'text-slate-500 hover:bg-slate-50'}`}>
                  {tab}
                </button>
              ))}
            </div>

            <div className="overflow-auto flex-1">
              <table className="w-full text-left border-collapse">
                <thead className="sticky top-0 bg-white shadow-sm z-10">
                  <tr className="text-xs text-slate-400 font-bold uppercase tracking-wider">
                    <th className="p-4">Drawing No</th>
                    <th className="p-4">Supplier</th>
                    <th className="p-4 text-center">Comments</th>
                    <th className="p-4 text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="text-sm">
                  {filteredDrawings.map((row, i) => (
                    <tr key={i} className="border-b border-slate-50 hover:bg-slate-50 cursor-pointer" onClick={() => navigate(`/crs-review/${row.dbId}`)}>
                      <td className="p-4 font-bold text-slate-700">{row.id}</td>
                      <td className="p-4 text-slate-500">
                        <div className="font-medium text-slate-800">{row.sup}</div>
                        <div className="text-[11px]">PO: {row.po}</div>
                      </td>
                      <td className="p-4 text-center font-bold text-indigo-600">{row.com}</td>
                      <td className="p-4 text-right">
                        <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold ${
                          row.status === 'Open' ? 'bg-red-50 text-red-700' :
                          row.status === 'In Progress' ? 'bg-amber-50 text-amber-700' : 'bg-emerald-50 text-emerald-700'
                        }`}>
                          {row.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

        </div>
      </div>
    </Layout>
  );
}