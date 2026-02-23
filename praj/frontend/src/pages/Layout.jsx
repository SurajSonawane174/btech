import React, { useState } from "react";
import {
  Wallet,
  LayoutDashboard,
  List,
  PlusCircle,
  FileCheck2,
} from "lucide-react";
import { Link, Outlet } from "react-router-dom";

const Layout = ({
  children,
  currentUser = null,
  summary = { monthlyExpense: 0 },
  success,
  error,
  active = "dashboard",
}) => {
  // Set to true by default so it shows up on desktop right away
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  // --- LOGIC: Calculate Sidebar Data ---
  const budgetLimit = 500000;
  let currentSpend = 0;

  if (summary && summary.monthlyExpense) {
    currentSpend = summary.monthlyExpense;
  }

  const percentUsed = Math.min(
    Math.round((currentSpend / budgetLimit) * 100),
    100,
  );
  const remaining = Math.max(budgetLimit - currentSpend, 0);

  let progressBarColor = "bg-indigo-500";
  if (percentUsed > 90) progressBarColor = "bg-rose-500";
  else if (percentUsed > 75) progressBarColor = "bg-amber-500";

  return (
    <div className="flex min-h-screen relative  bg-gray-50">
      {/* --- SIDEBAR --- */}
      <aside
        id="sidebar"
        className={`fixed inset-y-0 left-0 z-50 w-64 bg-[#0f172a] text-white transition-transform duration-300 ease-in-out transform flex flex-col border-r border-gray-800 ${
          isSidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="h-16 flex items-center px-6 border-b border-gray-800">
          <div className="flex items-center gap-3 font-bold text-xl tracking-wide">
            <div className="bg-indigo-600 p-1.5 rounded-lg shadow-lg shadow-indigo-500/30">
              <Wallet className="w-5 h-5 text-white" />
            </div>
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">
              PRAJ
            </span>
          </div>
        </div>

        <nav className="flex-1 px-4 py-6 space-y-2">
          <Link
            to="/dashboard"
            className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group ${
              active === "dashboard"
                ? "bg-indigo-600 text-white shadow-lg shadow-indigo-900/50"
                : "text-gray-400 hover:bg-white/5 hover:text-white"
            }`}
          >
            <LayoutDashboard className="w-5 h-5 group-hover:scale-110 transition-transform" />
            <span className="font-medium">Dashboard</span>
          </Link>

          <Link
            to="/projects"
            className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group ${
              active === "transactions"
                ? "bg-indigo-600 text-white shadow-lg shadow-indigo-900/50"
                : "text-gray-400 hover:bg-white/5 hover:text-white"
            }`}
          >
            <List className="w-5 h-5 group-hover:scale-110 transition-transform" />
            <span className="font-medium">Project</span>
          </Link>

          <Link
            to="/project/commentextract/upload"
            className="flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group text-gray-400 hover:bg-white/5 hover:text-white"
          >
            <PlusCircle className="w-5 h-5 group-hover:scale-110 transition-transform" />
            <span className="font-medium">Scan</span>
          </Link>

          <Link
            to="/project/crs    "
            className="flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group text-gray-400 hover:bg-white/5 hover:text-white"
          >
            <FileCheck2 className="w-5 h-5 group-hover:scale-110 transition-transform" />
            <span className="font-medium">Comment Resolution</span>
          </Link>
        </nav>

        <div className="p-4 border-t border-gray-800">
          <div className="bg-white/5 rounded-xl p-4 border border-white/5">
            {/* <div className="flex justify-between items-end mb-2">
                  <p className="text-xs text-gray-400 font-medium uppercase tracking-wider">Monthly Limit</p>
                  <p className="text-xs font-bold text-gray-300">₹{budgetLimit.toLocaleString('en-IN', { notation: "compact" })}</p>
              </div>

              <div className="w-full bg-gray-700 h-2 rounded-full mb-2 overflow-hidden">
                  <div className={`${progressBarColor} h-full rounded-full transition-all duration-1000 ease-out`} style={{ width: `${percentUsed}%` }}></div>
              </div> */}

            <div className="flex justify-between text-xs font-medium">
              <span
                className={
                  percentUsed > 90 ? "text-rose-400" : "text-indigo-300"
                }
              >
                {percentUsed}% Used
              </span>
              {/* <span className="text-gray-400">₹{remaining.toLocaleString('en-IN', { notation: "compact" })} left</span> */}
            </div>
          </div>
        </div>
      </aside>

      {/* --- MAIN CONTENT AREA --- */}
      {/* Adjusted the margin here so it collapses when the sidebar is closed */}
      <div
        className={`flex-1 flex flex-col transition-all duration-300 ${isSidebarOpen ? "md:ml-64" : "ml-0"}`}
      >
        {/* --- HEADER --- */}
        <header className="sticky top-0 z-30 h-16 bg-white/90 backdrop-blur-md border-b border-gray-200 shadow-sm flex items-center justify-between px-6 transition-all duration-300">
          <div className="flex items-center gap-4">
            <button
              id="sidebarToggle"
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              // Removed md:hidden here so it shows on all screen sizes
              className="p-2 text-gray-600 hover:text-indigo-600 hover:bg-gray-100/50 rounded-lg transition-colors"
              aria-label="Toggle Sidebar"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <line x1="4" x2="20" y1="12" y2="12" />
                <line x1="4" x2="20" y1="6" y2="6" />
                <line x1="4" x2="20" y1="18" y2="18" />
              </svg>
            </button>

            <div className="relative hidden sm:block group">
              <svg
                className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 group-focus-within:text-indigo-500 transition-colors"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="11" cy="11" r="8" />
                <path d="m21 21-4.3-4.3" />
              </svg>
              <input
                type="search"
                id="search-input"
                placeholder="Search transactions..."
                className="pl-10 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-full text-sm w-64 focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all placeholder-gray-400 text-gray-700 outline-none"
              />
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="relative group h-full flex items-center">
              <button
                onClick={() => setIsProfileOpen(!isProfileOpen)}
                className="flex items-center gap-3 focus:outline-none py-2"
              >
                <div className="text-right hidden sm:block">
                  <p className="text-sm font-semibold text-gray-700">
                    {currentUser?.profile?.fullName || "Guest User"}
                  </p>
                  <p className="text-xs text-gray-500">Admin</p>
                </div>

                <div className="h-9 w-9 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-full flex items-center justify-center text-white font-bold shadow-md ring-2 ring-transparent group-hover:ring-indigo-200 transition-all">
                  {currentUser?.profile?.fullName
                    ? currentUser.profile.fullName.charAt(0).toUpperCase()
                    : "G"}
                </div>
              </button>

              <div
                className={`absolute right-0 top-full pt-2 w-48 transition-all duration-200 transform origin-top-right z-50 ${isProfileOpen ? "opacity-100 visible" : "opacity-0 invisible group-hover:opacity-100 group-hover:visible"}`}
              >
                <div className="bg-white/95 backdrop-blur-xl rounded-xl shadow-2xl border border-gray-100 overflow-hidden ring-1 ring-black ring-opacity-5">
                  {currentUser ? (
                    <div className="py-1">
                      <div className="px-4 py-3 border-b border-gray-100 sm:hidden">
                        <p className="text-sm font-medium text-gray-900">
                          {currentUser.profile.fullName}
                        </p>
                        <p className="text-xs text-gray-500 truncate">
                          {currentUser.email}
                        </p>
                      </div>

                      <Link
                        to="/profile/update"
                        className="flex items-center gap-2 px-4 py-2.5 text-sm text-gray-700 hover:bg-indigo-50 hover:text-indigo-600 transition-colors"
                      >
                        <svg
                          className="w-4 h-4"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                          ></path>
                        </svg>
                        Profile
                      </Link>

                      <Link
                        to="/logout"
                        className="flex items-center gap-2 px-4 py-2.5 text-sm text-rose-600 hover:bg-rose-50 transition-colors"
                      >
                        <svg
                          className="w-4 h-4"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                          ></path>
                        </svg>
                        Logout
                      </Link>
                    </div>
                  ) : (
                    <div className="py-1">
                      <Link
                        to="/login"
                        className="block px-4 py-2.5 text-sm text-gray-700 hover:bg-indigo-50 hover:text-indigo-600"
                      >
                        Log In
                      </Link>
                      <Link
                        to="/register"
                        className="block px-4 py-2.5 text-sm text-gray-700 hover:bg-indigo-50 hover:text-indigo-600"
                      >
                        Sign Up
                      </Link>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </header>

        {/* --- PAGE CONTENT --- */}
        <main className="flex justify-center items-center p-6 overflow-y-auto flex-col">
          <div className="w-full max-w-7xl">
            {success && (
              <div
                className="bg-green-100 border-l-4 border-green-500 text-green-700 p-4 mb-4 rounded shadow-sm"
                role="alert"
              >
                <p className="font-bold">Success</p>
                <p>{success}</p>
              </div>
            )}

            {error && (
              <div
                className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 mb-4 rounded shadow-sm"
                role="alert"
              >
                <p className="font-bold">Error</p>
                <p>{error}</p>
              </div>
            )}

            {/* Renders children props OR React Router's Outlet depending on how you use it */}
            {children || <Outlet />}
          </div>
        </main>

        {/* --- FOOTER --- */}
        <footer className="footer mt-auto">
          <div className="footer-inner text-center py-4 text-sm text-gray-500">
            <small>Made with ♥ — Praj</small>
          </div>
        </footer>
      </div>
    </div>
  );
};

export default Layout;
