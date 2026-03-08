import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  FileText, LayoutDashboard, MessageSquare, SearchCode, 
  CheckSquare, BarChart2, BellRing, Settings, MoreHorizontal 
} from 'lucide-react';

export default function Sidebar({ isOpen }) {
  // Handles the active/inactive styling
  const navItemStyles = ({ isActive }) => 
    `flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition-colors ${
      isActive 
        ? 'bg-indigo-600 text-white' 
        : 'hover:bg-slate-800 text-slate-300'
    }`;

  return (
    <aside 
      className={`bg-slate-900 text-slate-300 flex flex-col h-screen flex-shrink-0 transition-all duration-300 overflow-hidden z-20 ${
        isOpen ? 'w-64' : 'w-0'
      }`}
    >
      <div className="w-64 flex flex-col h-full">
        {/* Logo Area */}
        <div className="p-6 flex items-center gap-3 border-b border-slate-800">
          <div className="w-8 h-8 bg-indigo-500 rounded flex items-center justify-center text-white font-bold">
            <FileText size={18} />
          </div>
          <div>
            <h1 className="text-white font-extrabold text-sm">Praj</h1>
            {/* <p className="text-[10px] text-slate-400 tracking-wider">COMMENT COLLECTOR</p> */}
          </div>
        </div>

        {/* Navigation Links */}
        <div className="flex-1 overflow-y-auto py-4 px-3 space-y-6 scrollbar-hide">
          
          {/* MAIN SECTION */}
          <div>
            <p className="text-xs font-semibold text-slate-500 mb-2 px-3">MAIN</p>
            <ul className="space-y-1">
              <li>
                <NavLink to="/dashboard" className={navItemStyles}>
                  <div className="flex items-center gap-3"><LayoutDashboard size={18} /> <span className="text-sm">Dashboard</span></div>
                </NavLink>
              </li>
              <li>
                <NavLink to="/comments" className={navItemStyles}>
                  <div className="flex items-center gap-3"><MessageSquare size={18} /> <span className="text-sm">Comment Collector</span></div>
                  <span className="bg-indigo-500/30 text-[10px] px-2 py-0.5 rounded-full text-indigo-100">125</span>
                </NavLink>
              </li>
              <li>
                <NavLink to="/upload" className={navItemStyles}>
                  <div className="flex items-center gap-3"><FileText size={18} /> <span className="text-sm">Process Drawing</span></div>
                </NavLink>
              </li>
            </ul>
          </div>

          {/* REVIEW SECTION */}
          <div>
            <p className="text-xs font-semibold text-slate-500 mb-2 px-3">REVIEW</p>
            <ul className="space-y-1">
              <li>
                <NavLink to="/get-crs" className={navItemStyles}>
                  <div className="flex items-center gap-3"><SearchCode size={18} /> <span className="text-sm">CRS Lookup</span></div>
                </NavLink>
              </li>
              <li>
                {/* WIRED UP THE CRS REVIEW LINK */}
                <NavLink to="/review" className={navItemStyles}>
                  <div className="flex items-center gap-3"><CheckSquare size={18} /> <span className="text-sm">CRS Review</span></div>
                  <span className="text-[10px] text-red-400 font-bold">18</span>
                </NavLink>
              </li>
            </ul>
          </div>

          {/* OUTPUT SECTION */}
          <div>
            <p className="text-xs font-semibold text-slate-500 mb-2 px-3">OUTPUT</p>
            <ul className="space-y-1">
              <li>
                <NavLink to="/reports" className={navItemStyles}>
                  <div className="flex items-center gap-3"><BarChart2 size={18} /> <span className="text-sm">Reports</span></div>
                </NavLink>
              </li>
            </ul>
          </div>

          {/* SYSTEM SECTION */}
          <div>
            <p className="text-xs font-semibold text-slate-500 mb-2 px-3">SYSTEM</p>
            <ul className="space-y-1">
              <li>
                {/* UPGRADED TO NAVLINK FOR NOTIFICATIONS */}
                <NavLink to="/notifications" className={navItemStyles}>
                  <div className="flex items-center gap-3"><BellRing size={18} /> <span className="text-sm">Notifications</span></div>
                  <span className="bg-amber-500 text-[10px] px-2 py-0.5 rounded-full text-slate-900 font-bold">5</span>
                </NavLink>
              </li>
              <li>
                <div className="flex items-center gap-3 px-3 py-2 hover:bg-slate-800 rounded-lg cursor-pointer text-slate-300 transition-colors">
                  <Settings size={18} /> <span className="text-sm">Settings</span>
                </div>
              </li>
            </ul>
          </div>
        </div>

        {/* User Profile */}
        <div className="p-4 border-t border-slate-800 flex items-center gap-3 hover:bg-slate-800 cursor-pointer transition-colors">
          <div className="w-8 h-8 rounded-full bg-indigo-500 flex items-center justify-center text-white text-xs font-bold">NA</div>
          <div className="flex-1">
            <p className="text-sm font-medium text-white">N. Admin</p>
            <p className="text-xs text-slate-500">ecc-admin</p>
          </div>
          <MoreHorizontal size={16} className="text-slate-400" />
        </div>
      </div>
    </aside>
  );
}