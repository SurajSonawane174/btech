import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Sidebar({ isOpen }) {
  const { logout } = useAuth();
  const location = useLocation();

  const isActive = (path) => location.pathname === path;

  return (
    <aside 
      className={`bg-[#0F172A] flex flex-col shadow-xl transition-all duration-300 ease-in-out z-20 whitespace-nowrap overflow-hidden
        ${isOpen ? 'w-64' : 'w-0'}
      `}
    >
      <div className="p-6 flex items-center gap-3 h-20 border-b border-slate-800/50">
        <div className="bg-indigo-600 p-2 rounded-lg shrink-0">
          <span className="text-white text-xl">📄</span>
        </div>
        <h2 className="text-white text-2xl font-bold tracking-wide">DocScanner</h2>
      </div>

      <nav className="flex-1 px-4 mt-6 space-y-2">
        <Link 
          to="/dashboard" 
          className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
            isActive('/dashboard') 
              ? 'bg-indigo-600 text-white shadow-md' 
              : 'text-slate-400 hover:text-white hover:bg-slate-800'
          }`}
        >
          <span className="shrink-0">📊</span>
          <span className="font-medium">Dashboard</span>
        </Link>
        
        <Link 
          to="/upload" 
          className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
            isActive('/upload') 
              ? 'bg-indigo-600 text-white shadow-md' 
              : 'text-slate-400 hover:text-white hover:bg-slate-800'
          }`}
        >
          <span className="shrink-0">📤</span>
          <span className="font-medium">Upload PDF</span>
        </Link>
        
        <Link 
          to="/comments" 
          className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
            isActive('/comments') 
              ? 'bg-indigo-600 text-white shadow-md' 
              : 'text-slate-400 hover:text-white hover:bg-slate-800'
          }`}
        >
          <span className="shrink-0">💬</span>
          <span className="font-medium">Read Comments</span>
        </Link>
      </nav>

      <div className="p-4 mb-4 border-t border-slate-800 mx-4">
        <button
          onClick={logout}
          className="bg-red-500/10 text-red-400 hover:bg-red-500/20 px-4 py-2 rounded-lg font-medium transition duration-300 w-full text-left flex items-center gap-3"
        >
          <span className="shrink-0">🚪</span>
          <span>Logout</span>
        </button>
      </div>
    </aside>
  );
}