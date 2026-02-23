import { useState } from "react";
import Sidebar from "./Sidebar";
import Navbar from "./Navbar";

export default function Layout({ children }) {
  // State to manage whether the sidebar is visible
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  const toggleSidebar = () => {
    setIsSidebarOpen(!isSidebarOpen);
  };

  return (
    <div className="flex min-h-screen bg-slate-50 overflow-hidden">
      {/* Sidebar handles its own open/closed styling based on the prop */}
      <Sidebar isOpen={isSidebarOpen} />
      
      {/* Main content area that takes up the rest of the space */}
      <div className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden">
        <Navbar toggleSidebar={toggleSidebar} />
        
        <main className="flex-1 p-8 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}