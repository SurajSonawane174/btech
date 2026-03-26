import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import {
  Check, Bell, AlertCircle, FileCheck, UserPlus,
  FileWarning, Settings, Clock, ArrowRight
} from 'lucide-react';

// Map icon name strings from API to Lucide components
const ICON_MAP = { AlertCircle, FileCheck, UserPlus, FileWarning, Check, Settings };

export default function Notifications() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('all');
  const [notifications, setNotifications] = useState([]);

  // Expected API response: array of {
  //   id, type, icon (string key of ICON_MAP), color, bg,
  //   title, text, time, unread, action (string|null), actionRoute (string|null)
  // }

  useEffect(() => {
    fetch('/api/notifications')
      .then(r => r.json())
      .then(setNotifications)
      .catch(console.error);
  }, []);

  async function handleMarkAllRead() {
    try {
      await fetch('/api/notifications/mark-all-read', { method: 'POST' });
      setNotifications(prev => prev.map(n => ({ ...n, unread: false })));
    } catch (err) {
      console.error('Mark all read failed:', err);
    }
  }

  function handleAction(note) {
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
            ) : filteredNotifications.map((note) => {
              const IconComponent = ICON_MAP[note.icon] || Bell;
              return (
                <div
                  key={note.id}
                  className={`p-5 flex gap-4 transition-all duration-200 group relative ${
                    note.unread ? 'bg-indigo-50/20 hover:bg-indigo-50/40' : 'bg-white hover:bg-slate-50/80'
                  }`}
                >
                  {note.unread && (
                    <div className="absolute left-0 top-0 bottom-0 w-1 bg-indigo-500 rounded-r-full"></div>
                  )}

                  <div className="flex-shrink-0">
                    <div className={`p-2.5 rounded-xl border shadow-sm ${note.bg} ${note.color}`}>
                      <IconComponent size={16} />
                    </div>
                  </div>

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
              );
            })}
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