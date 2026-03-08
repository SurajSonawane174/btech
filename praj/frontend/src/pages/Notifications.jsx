import React from 'react';
import Layout from '../components/Layout';
import { Check, Bell } from 'lucide-react';

export default function Notifications() {
  const notifications = [
    { type: 'overdue', dot: 'bg-red-500', title: 'Overdue', text: 'CRS-004 (U-004 · Engineer D) passed target date 01-Feb-2023. Immediate action required.', time: '2h ago', unread: true },
    { type: 'assignment', dot: 'bg-indigo-500', title: 'New Assignment', text: 'C-012 from drawing U-005 has been assigned to Engineer B by Admin.', time: '4h ago', unread: true },
    { type: 'processed', dot: 'bg-emerald-500', title: 'Drawing Processed', text: 'U-005 OCR complete — 180 comments extracted with avg confidence 91%.', time: '6h ago', unread: true },
    { type: 'low_conf', dot: 'bg-amber-500', title: 'Low Confidence', text: '12 comments in drawing ENGR-007 scored below 70% — manual review recommended.', time: '1d ago', unread: true },
    { type: 'closed', dot: 'bg-indigo-400', title: 'CRS Closed', text: 'Engineer C resolved CRS-003 (Add valve — chait-001) and added evidence link.', time: '2d ago', unread: true },
    { type: 'system', dot: 'bg-slate-200', title: 'System', text: 'Drawing U-004 fully closed — all 200 comments resolved. Export available.', time: '3d ago', unread: false },
    { type: 'system', dot: 'bg-slate-200', title: 'System', text: 'OCR engine updated to v3.2 — improved handwritten text detection.', time: '5d ago', unread: false },
  ];

  return (
    <Layout>
      <div className="max-w-6xl mx-auto space-y-6">
        
        {/* Header */}
        <div className="flex justify-between items-end">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">Notifications</h1>
            <p className="text-sm text-slate-500">5 unread alerts — system, assignments and overdue items</p>
          </div>
          <button className="bg-white border border-slate-200 hover:bg-slate-50 text-indigo-600 px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-all shadow-sm">
            <Check size={16} /> Mark all read
          </button>
        </div>

        {/* Notifications Card */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="bg-slate-50 p-5 border-b border-slate-100 flex items-center gap-3">
            <Bell size={18} className="text-amber-500 fill-amber-500" />
            <h3 className="font-bold text-slate-800">All Notifications</h3>
            <span className="bg-indigo-100 text-indigo-700 text-[10px] px-2.5 py-0.5 rounded-full font-bold">5 unread</span>
          </div>

          <div className="divide-y divide-slate-100">
            {notifications.map((note, i) => (
              <div key={i} className={`p-5 flex items-start gap-4 hover:bg-slate-50 transition-colors ${note.unread ? 'bg-white' : 'bg-slate-50/50'}`}>
                <div className={`w-2.5 h-2.5 rounded-full mt-1.5 flex-shrink-0 ${note.dot}`}></div>
                <div className="flex-1">
                  <p className="text-sm">
                    <span className={`font-bold ${note.unread ? 'text-slate-800' : 'text-slate-400'}`}>{note.title}: </span>
                    <span className={note.unread ? 'text-slate-600' : 'text-slate-400'}>{note.text}</span>
                  </p>
                </div>
                <span className="text-xs font-medium text-slate-400 whitespace-nowrap">{note.time}</span>
              </div>
            ))}
          </div>
        </div>

      </div>
    </Layout>
  );
}