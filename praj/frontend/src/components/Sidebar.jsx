import { useAuth } from '../auth/AuthContext';
import React, { useState, useRef, useEffect } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { 
  FileText, LayoutDashboard, MessageSquare, SearchCode, 
  CheckSquare, BarChart2, BellRing, Settings, MoreHorizontal,
  LogOut
} from 'lucide-react';



export default function Sidebar({ isOpen }) {
  const [showMenu, setShowMenu] = useState(false);
  const menuRef = useRef(null);
  const navigate = useNavigate();
  
  const { user, logout } = useAuth();

  // Build initials and display name from the real user object
  const initials = user?.name
    ? user.name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
    : (user?.email?.[0] ?? '?').toUpperCase();

  const displayName = user?.name || user?.email || 'User';
  const displayId   = user?.email || user?.id || '';

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setShowMenu(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  function handleLogout() {
  logout(); // use AuthContext logout — clears localStorage + user state
  navigate('/login');
 }

  const navItemStyles = ({ isActive }) => 
    `flex items-center justify-between px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-300 group ${
      isActive 
        ? 'bg-gradient-to-r from-blue-600 to-blue-500 text-white shadow-[0_0_15px_rgba(37,99,235,0.4)] font-medium border border-blue-400/30'
        : 'hover:bg-blue-800/40 text-blue-200 hover:text-white hover:shadow-[inset_0_0_12px_rgba(59,130,246,0.2)]'
    }`;

  return (
    <aside
      className={`bg-gradient-to-b from-slate-950 via-blue-950 to-slate-950 border-r border-blue-900/50 shadow-[4px_0_24px_rgba(30,58,138,0.5)] text-blue-100 flex flex-col h-screen flex-shrink-0 transition-all duration-300 overflow-hidden z-20 ${
        isOpen ? 'w-64' : 'w-0'
      }`}
    >
      <div className="w-64 flex flex-col h-full">
        {/* Logo Area */}
        <div className="p-6 flex items-center gap-3 border-b border-blue-900/50 bg-white/[0.02]">
          <div className="w-8 h-8 bg-gradient-to-br from-cyan-400 to-blue-600 rounded-lg flex items-center justify-center text-white font-bold shadow-[0_0_15px_rgba(6,182,212,0.4)]">
            <FileText size={18} />
          </div>
          <div>
            <h1 className="text-white font-extrabold text-lg tracking-wide drop-shadow-[0_0_8px_rgba(255,255,255,0.3)]">Praj</h1>
            <p className="text-[10px] text-cyan-400 font-medium tracking-widest uppercase">Workspace</p>
          </div>
        </div>

        {/* Navigation Links */}
        <div className="flex-1 overflow-y-auto py-6 px-4 space-y-8 scrollbar-hide">
          
          {/* MAIN SECTION */}
          <div>
            <p className="text-[10px] font-bold text-cyan-500/80 tracking-widest uppercase mb-3 px-3">Main</p>
            <ul className="space-y-1.5">
              <li>
                <NavLink to="/dashboard" className={navItemStyles}>
                  <div className="flex items-center gap-3"><LayoutDashboard size={18} className="group-hover:text-cyan-300 transition-colors" /> <span className="text-sm">Dashboard</span></div>
                </NavLink>
              </li>
              <li>
                <NavLink to="/comments" className={navItemStyles}>
                  <div className="flex items-center gap-3"><MessageSquare size={18} className="group-hover:text-cyan-300 transition-colors" /> <span className="text-sm">Comment Collector</span></div>
                  <span className="bg-cyan-500/20 border border-cyan-500/30 text-[10px] px-2 py-0.5 rounded-full text-cyan-300 font-semibold shadow-[0_0_8px_rgba(6,182,212,0.2)]">125</span>
                </NavLink>
              </li>
              <li>
                <NavLink to="/upload" className={navItemStyles}>
                  <div className="flex items-center gap-3"><FileText size={18} className="group-hover:text-cyan-300 transition-colors" /> <span className="text-sm">Process Drawing</span></div>
                </NavLink>
              </li>
            </ul>
          </div>

          {/* REVIEW SECTION */}
          <div>
            <p className="text-[10px] font-bold text-cyan-500/80 tracking-widest uppercase mb-3 px-3">Review</p>
            <ul className="space-y-1.5">
              <li>
                <NavLink to="/get-crs" className={navItemStyles}>
                  <div className="flex items-center gap-3"><SearchCode size={18} className="group-hover:text-cyan-300 transition-colors" /> <span className="text-sm">CRS Lookup</span></div>
                </NavLink>
              </li>
              <li>
                <NavLink to="/review" className={navItemStyles}>
                  <div className="flex items-center gap-3"><CheckSquare size={18} className="group-hover:text-cyan-300 transition-colors" /> <span className="text-sm">CRS Review</span></div>
                  <span className="bg-rose-500/20 border border-rose-500/30 text-[10px] px-2 py-0.5 rounded-full text-yellow-500 font-bold shadow-[0_0_8px_rgba(244,63,94,0.3)]">13</span>
                </NavLink>
              </li>
            </ul>
          </div>

          {/* OUTPUT SECTION */}
          <div>
            <p className="text-[10px] font-bold text-cyan-500/80 tracking-widest uppercase mb-3 px-3">Output</p>
            <ul className="space-y-1.5">
              <li>
                <NavLink to="/reports" className={navItemStyles}>
                  <div className="flex items-center gap-3"><BarChart2 size={18} className="group-hover:text-cyan-300 transition-colors" /> <span className="text-sm">Reports</span></div>
                </NavLink>
              </li>
            </ul>
          </div>

          {/* SYSTEM SECTION */}
          <div>
            <p className="text-[10px] font-bold text-cyan-500/80 tracking-widest uppercase mb-3 px-3">System</p>
            <ul className="space-y-1.5">
              <li>
                <NavLink to="/notifications" className={navItemStyles}>
                  <div className="flex items-center gap-3"><BellRing size={18} className="group-hover:text-cyan-300 transition-colors" /> <span className="text-sm">Notifications</span></div>
                  <span className="bg-amber-500/20 border border-amber-500/30 text-[10px] px-2 py-0.5 rounded-full text-amber-300 font-bold shadow-[0_0_8px_rgba(245,158,11,0.2)]">5</span>
                </NavLink>
              </li>
              <li>
                <NavLink to="/settings" className={navItemStyles}>
                  <div className="flex items-center gap-3"><Settings size={18} className="group-hover:text-cyan-300 transition-colors" /> <span className="text-sm">Settings</span></div>
                </NavLink>
              </li>
            </ul>
          </div>
        </div>

        {/* User Profile */}
        <div className="relative p-4 border-t border-blue-900/50" ref={menuRef}>

          {/* Logout Popup Menu */}
          {showMenu && (
            <div className="absolute bottom-full left-4 right-4 mb-2 bg-slate-900 border border-blue-800/60 rounded-xl shadow-[0_0_20px_rgba(30,58,138,0.5)] overflow-hidden">
              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-3 px-4 py-3 text-sm text-rose-400 hover:bg-rose-500/10 hover:text-rose-300 transition-colors"
              >
                <LogOut size={15} /> Logout
              </button>
            </div>
          )}

          <div className="flex items-center gap-3 bg-white/[0.01] hover:bg-blue-900/30 rounded-xl px-1 py-1 transition-colors group cursor-pointer">
            {/* Avatar + Name — clicks to Settings */}
            <div
              onClick={() => navigate('/settings')}
              className="flex items-center gap-3 flex-1 min-w-0"
            >
              <div className="w-9 h-9 rounded-full bg-gradient-to-r from-blue-600 to-indigo-600 flex items-center justify-center text-white text-xs font-bold shadow-[0_0_10px_rgba(37,99,235,0.3)] border border-blue-400/20 flex-shrink-0">{initials}</div>
              <div className="min-w-0">
                <p className="text-sm font-medium text-blue-50 group-hover:text-white transition-colors truncate">{displayName}</p>
                <p className="text-xs text-blue-300/70 truncate">{displayId}</p>
              </div>
            </div>

            {/* 3 dots — toggles logout menu */}
            <button
              onClick={(e) => { e.stopPropagation(); setShowMenu(v => !v); }}
              className="p-1 rounded-lg hover:bg-blue-800/50 transition-colors flex-shrink-0"
            >
              <MoreHorizontal size={18} className="text-blue-400/50 group-hover:text-cyan-400 transition-colors" />
            </button>
          </div>
        </div>

      </div>
    </aside>
  );
}