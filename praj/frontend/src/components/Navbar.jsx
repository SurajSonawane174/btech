import React from 'react';
import { Search, Moon, Bell, Upload, Menu } from 'lucide-react';

export default function Navbar({ toggleSidebar }) {
  return (
    <header className="h-20 bg-white border-b border-slate-200 flex items-center justify-between px-8 flex-shrink-0">
      <div className="flex items-center gap-4">
        <button 
          onClick={toggleSidebar}
          className="p-2 text-slate-500 hover:bg-slate-100 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <Menu size={20} />
        </button>
        
        <div>
          <h2 className="text-xl font-bold text-slate-800">Dashboard</h2>
          {/* <p className="text-sm text-slate-500">Wed, 25 Feb 2026 — Welcome back, N. Admin</p> */}
        </div>
      </div>
      
      <div className="flex items-center gap-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
          <input 
            type="text" 
            placeholder="Search drawings, comments..." 
            className="pl-10 pr-4 py-2 bg-slate-100 border-transparent rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 w-64 transition-all"
          />
        </div>
        
        <button className="p-2 text-slate-500 hover:bg-slate-100 rounded-full transition-colors"><Moon size={20} /></button>
        <button className="p-2 text-slate-500 hover:bg-slate-100 rounded-full transition-colors relative">
          <Bell size={20} />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full border-2 border-white"></span>
        </button>
        
        {/* Replaced your old React Router Link with the new design's button */}
        <button className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors shadow-sm">
          <Upload size={16} /> Upload Drawing
        </button>
      </div>
    </header>
  );
}