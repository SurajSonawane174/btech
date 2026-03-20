import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import { 
  Check, Bell, AlertCircle, FileCheck, UserPlus, 
  FileWarning, Settings, Clock, ArrowRight 
} from 'lucide-react';

export default function Notifications() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('all');

  const [notifications, setNotifications] = useState([
    { 
      id: 1, type: 'critical', icon: AlertCircle, color: 'text-rose-600', bg: 'bg-rose-50 border-rose-100', 
      title: 'SLA Breach: Overdue Review', 
      text: 'CRS-004 (U-004) assigned to Engineer D has missed its target resolution date of 01-Feb-2023. Immediate escalation required.', 
      time: '2h ago', unread: true, action: 'Escalate Item',
      actionRoute: '/crs-review/U-004'
    },
    { 
      id: 2, type: 'assignment', icon: UserPlus, color: 'text-indigo-600', bg: 'bg-indigo-50 border-indigo-100', 
      title: 'New Task Assignment', 
      text: 'You have been assigned to resolve Comment C-012 on drawing U-005 by the System Administrator.', 
      time: '4h ago', unread: true, action: 'View Assignment',
      actionRoute: '/crs-review/U-005'
    },
    { 
      id: 3, type: 'success', icon: FileCheck, color: 'text-emerald-600', bg: 'bg-emerald-50 border-emerald-100', 
      title: 'OCR Processing Complete', 
      text: 'Drawing U-005 has been successfully parsed. 180 comments extracted with an average confidence score of 91%.', 
      time: '6h ago', unread: true, action: 'Review Extraction',
      actionRoute: '/crs-review/U-005'
    },
    { 
      id: 4, type: 'warning', icon: FileWarning, color: 'text-amber-600', bg: 'bg-amber-50 border-amber-100', 
      title: 'Low Confidence Warning', 
      text: '12 comments in drawing ENGR-007 scored below the 70% confidence threshold. Manual verification is strongly recommended.', 
      time: 'Yesterday', unread: true, action: 'Verify Now',
      actionRoute: '/crs-review/ENGR-007'
    },
    { 
      id: 5, type: 'success', icon: Check, color: 'text-emerald-600', bg: 'bg-emerald-50 border-emerald-100', 
      title: 'CRS Item Resolved', 
      text: 'Engineer C has successfully closed CRS-003 (Add valve — chait-001) and attached the necessary photographic evidence.', 
      time: 'Yesterday', unread: false, action: 'View Evidence',
      actionRoute: '/get-crs'
    },
    { 
      id: 6, type: 'system', icon: FileCheck, color: 'text-slate-600', bg: 'bg-slate-100 border-slate-200', 
      title: 'Drawing Closed', 
      text: 'Drawing U-004 has achieved 100% resolution. All 200 comments are closed. The final PDF export is now available.', 
      time: '3 days ago', unread: false, action: 'Download PDF',
      actionRoute: '/reports'
    },
    { 
      id: 7, type: 'system', icon: Settings, color: 'text-slate-600', bg: 'bg-slate-100 border-slate-200', 
      title: 'System Update', 
      text: 'The OCR engine has been updated to v3.2. This includes improved detection for cursive handwritten annotations.', 
      time: 'Last week', unread: false, action: null,
      actionRoute: null
    },
  ]);

  function handleMarkAllRead() {
    setNotifications(prev => prev.map(n => ({ ...n, unread: false })));
  }

  function handleAction(note) {
    // Mark as read when action is clicked
    setNotifications(prev => prev.map(n => n.id === note.id ? { ...n, unread: false } : n));
    if (note.actionRoute) navigate(note.actionRoute);
  }

  const unreadCount = notifications.filter(n => n.unread).length;

  const filteredNotifications = notifications.filter(note => {
    if (activeTab === 'unread') return note.unread;
    if (activeTab === 'action') return !!note.action;
    return true;
  });

  return (
    <Layout>
      <div className="max-w-5xl mx-auto space-y-6">
        
        {/* Page Header */}
        <div className="flex justify-between items-end">
          <div>
            <h1 className="text-2xl font-extrabold text-slate-800 tracking-tight">Notifications</h1>
            <p className="text-xs text-slate-500 font-medium mt-1">Manage your alerts, assignments, and system updates</p>
          </div>
          <button
            onClick={handleMarkAllRead}
            className="bg-white border border-slate-200 hover:bg-slate-50 hover:border-indigo-200 text-indigo-600 px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-2 transition-all shadow-[0_2px_10px_rgba(0,0,0,0.04)]"
          >
            <Check size={14} /> Mark all as read
          </button>
        </div>

        {/* Main Content Area */}
        <div className="bg-white rounded-2xl border border-slate-100 shadow-[0_8px_30px_rgb(0,0,0,0.04)] overflow-hidden">
          
          {/* Header & Tabs */}
          <div className="border-b border-slate-100">
            <div className="p-5 flex items-center justify-between bg-slate-50/50">
              <div className="flex items-center gap-3">
                <div className="p-1.5 bg-indigo-50 rounded-lg border border-indigo-100 text-indigo-600">
                  <Bell size={16} />
                </div>
                <h3 className="font-bold text-base text-slate-800">Inbox</h3>
                {unreadCount > 0 && (
                  <span className="bg-indigo-600 text-white text-[10px] px-2 py-0.5 rounded-full font-bold ml-1 shadow-sm">
                    {unreadCount} New
                  </span>
                )}
              </div>
            </div>
            
            <div className="px-5 flex gap-6 text-xs bg-white">
              <button 
                onClick={() => setActiveTab('all')}
                className={`py-3 font-bold transition-colors ${activeTab === 'all' ? 'text-indigo-600 border-b-2 border-indigo-600' : 'text-slate-500 hover:text-slate-800'}`}
              >
                All Notifications
              </button>
              <button 
                onClick={() => setActiveTab('unread')}
                className={`py-3 font-bold transition-colors ${activeTab === 'unread' ? 'text-indigo-600 border-b-2 border-indigo-600' : 'text-slate-500 hover:text-slate-800'}`}
              >
                Unread Only
              </button>
              <button 
                onClick={() => setActiveTab('action')}
                className={`py-3 font-bold transition-colors ${activeTab === 'action' ? 'text-indigo-600 border-b-2 border-indigo-600' : 'text-slate-500 hover:text-slate-800'}`}
              >
                Requires Action
              </button>
            </div>
          </div>

          {/* Notifications List */}
          <div className="divide-y divide-slate-100">
            {filteredNotifications.length === 0 ? (
              <div className="p-10 text-center text-slate-400 text-sm">No notifications here.</div>
            ) : filteredNotifications.map((note) => (
              <div 
                key={note.id} 
                className={`p-5 flex gap-4 transition-all duration-200 group relative ${
                  note.unread ? 'bg-indigo-50/20 hover:bg-indigo-50/40' : 'bg-white hover:bg-slate-50/80'
                }`}
              >
                {/* Unread Indicator Line */}
                {note.unread && (
                  <div className="absolute left-0 top-0 bottom-0 w-1 bg-indigo-500 rounded-r-full"></div>
                )}

                {/* Icon Container */}
                <div className="flex-shrink-0">
                  <div className={`p-2.5 rounded-xl border shadow-sm ${note.bg} ${note.color}`}>
                    <note.icon size={16} />
                  </div>
                </div>

                {/* Content Area */}
                <div className="flex-1 min-w-0">
                  <div className="flex justify-between items-start mb-1">
                    <h4 className={`text-sm font-extrabold truncate pr-4 ${note.unread ? 'text-slate-900' : 'text-slate-700'}`}>
                      {note.title}
                    </h4>
                    <div className="flex items-center gap-1 text-[11px] font-bold text-slate-400 whitespace-nowrap flex-shrink-0">
                      <Clock size={12} /> {note.time}
                    </div>
                  </div>
                  
                  <p className={`text-xs leading-relaxed mb-3 ${note.unread ? 'text-slate-600 font-medium' : 'text-slate-500'}`}>
                    {note.text}
                  </p>

                  {/* Contextual Action Button */}
                  {note.action && (
                    <button
                      onClick={() => handleAction(note)}
                      className="inline-flex items-center gap-1.5 text-xs font-bold text-indigo-600 hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100 px-2.5 py-1.5 rounded-md transition-colors border border-indigo-100"
                    >
                      {note.action} <ArrowRight size={12} />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Footer */}
          <div className="p-3 border-t border-slate-100 bg-slate-50/50 text-center">
            <button className="text-xs font-bold text-slate-500 hover:text-indigo-600 transition-colors">
              Load Older Notifications ↓
            </button>
          </div>

        </div>
      </div>
    </Layout>
  );
}