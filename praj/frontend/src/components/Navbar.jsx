import { useAuth } from "../auth/AuthContext";

export default function Navbar({ toggleSidebar }) {
  const { user } = useAuth();

  return (
    <header className="bg-white h-20 flex items-center justify-between px-6 shadow-sm border-b border-slate-200 z-10">
      <div className="flex items-center gap-6 flex-1">
        {/* Hamburger Toggle Button */}
        <button 
          onClick={toggleSidebar}
          className="text-slate-500 hover:text-indigo-600 transition-colors p-2 rounded-lg hover:bg-slate-50"
          aria-label="Toggle Sidebar"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        {/* Search Bar matching your image */}
        <div className="max-w-md w-full relative hidden md:block">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <span className="text-slate-400">🔍</span>
          </div>
          <input 
            type="text" 
            placeholder="Search documents or comments..." 
            className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all"
          />
        </div>
      </div>

      {/* User Profile Section */}
      <div className="flex items-center gap-4">
        <div className="text-right hidden sm:block">
          <p className="text-sm font-bold text-slate-700">{user?.name || user?.email || "Analyst"}</p>
          <p className="text-xs text-slate-500">System Admin</p>
        </div>
        <div className="h-10 w-10 rounded-full bg-indigo-600 text-white flex items-center justify-center font-bold shadow-md">
          {user?.name?.charAt(0).toUpperCase() || "A"}
        </div>
      </div>
    </header>
  );
}