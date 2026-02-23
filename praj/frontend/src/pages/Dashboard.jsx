import React from "react";
import { Link } from "react-router-dom";
import Layout from "../components/Layout";
import { 
  MessageSquare, 
  Files, 
  ArrowUpRight, 
  Plus, 
  Download, 
  BarChart3, 
  FileText, 
  ChevronRight 
} from "lucide-react";

export default function Dashboard() {
  return (
    <Layout active="dashboard">
      <div className="max-w-7xl mx-auto animate-fade-in-up w-full">
        
        {/* Header Section */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-10">
          <div>
            <h1 className="text-3xl font-black text-gray-800 tracking-tight mb-1">
              Hello, Analyst! 👋
            </h1>
            <p className="text-gray-500 font-medium text-sm">
              Here is your document extraction overview.
            </p>
          </div>
          
          <div className="flex flex-wrap items-center gap-4 w-full md:w-auto">
            {/* Secondary Button */}
            <Link 
              to="/create-crs" 
              className="flex-1 md:flex-none flex items-center justify-center gap-2 bg-white border-2 border-gray-200 text-gray-700 hover:border-indigo-300 hover:bg-indigo-50 px-6 py-3 rounded-xl font-bold transition-all shadow-sm"
            >
              <Download className="w-5 h-5" />
              Get CRS
            </Link>
            
            {/* Primary Gradient Button */}
            <Link 
              to="/upload" 
              className="flex-1 md:flex-none flex items-center justify-center gap-2 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white px-6 py-3 rounded-xl font-bold transition-all shadow-lg transform hover:-translate-y-0.5"
            >
              <Plus className="w-5 h-5" />
              Upload Document
            </Link>
          </div>
        </div>

        {/* Top Stat Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          
          {/* Total Extracted Card */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 flex flex-col justify-between hover:shadow-md transition-shadow group">
            <div className="flex justify-between items-start mb-4">
              <div className="flex items-center gap-3">
                <div className="bg-indigo-50 text-indigo-600 p-2.5 rounded-xl group-hover:bg-indigo-100 transition-colors">
                  <MessageSquare className="w-5 h-5" />
                </div>
                <h3 className="text-gray-500 font-bold text-xs uppercase tracking-wider">Total Extracted</h3>
              </div>
              <div className="bg-emerald-50 text-emerald-600 p-1.5 rounded-lg">
                <ArrowUpRight className="w-4 h-4 font-bold" />
              </div>
            </div>
            <div>
              <h2 className="text-4xl font-black text-gray-800 mb-1 tracking-tight">4,250</h2>
              <p className="text-indigo-600 text-sm font-bold flex items-center gap-1">
                Comments Extracted
              </p>
            </div>
          </div>

          {/* Documents Card */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 flex flex-col justify-between hover:shadow-md transition-shadow group">
            <div className="flex justify-between items-start mb-4">
              <div className="flex items-center gap-3">
                <div className="bg-purple-50 text-purple-600 p-2.5 rounded-xl group-hover:bg-purple-100 transition-colors">
                  <Files className="w-5 h-5" />
                </div>
                <h3 className="text-gray-500 font-bold text-xs uppercase tracking-wider">Documents</h3>
              </div>
              <div className="bg-emerald-50 text-emerald-600 p-1.5 rounded-lg">
                <ArrowUpRight className="w-4 h-4 font-bold" />
              </div>
            </div>
            <div>
              <h2 className="text-4xl font-black text-gray-800 mb-1 tracking-tight">124</h2>
              <p className="text-purple-600 text-sm font-bold flex items-center gap-1">
                Successfully Scanned
              </p>
            </div>
          </div>
        </div>

        {/* Bottom Grid: Analytics & Recent */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Analytics Card */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 col-span-1 flex flex-col hover:shadow-md transition-shadow">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-lg font-bold text-gray-800 flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-indigo-500" />
                Analytics
              </h3>
              <span className="bg-gray-100 text-gray-600 text-xs font-bold px-3 py-1.5 rounded-full">30 Days</span>
            </div>
            
            <div className="flex-1 flex flex-col items-center justify-center py-6">
              <div className="text-center">
                <p className="text-gray-400 text-xs font-bold uppercase tracking-wider mb-2">Total Queries</p>
                <h4 className="text-4xl font-black text-gray-800 tracking-tight">16.8k</h4>
              </div>
            </div>
            
            <div className="mt-auto pt-6 border-t border-gray-100">
              <div className="flex justify-between text-sm mb-2">
                <span className="text-gray-500 font-medium">API Limit</span>
                <span className="font-bold text-gray-700">50K</span>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-2.5 overflow-hidden">
                <div className="bg-gradient-to-r from-indigo-500 to-purple-500 h-full rounded-full transition-all duration-1000" style={{ width: '33%' }}></div>
              </div>
            </div>
          </div>

          {/* Recent Comments Card */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 col-span-1 lg:col-span-2 hover:shadow-md transition-shadow">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-lg font-bold text-gray-800 flex items-center gap-2">
                <FileText className="w-5 h-5 text-indigo-500" />
                Recent Comments
              </h3>
              <Link to="/comments" className="text-indigo-600 font-bold text-sm hover:text-indigo-800 transition-colors flex items-center gap-1 group">
                See All <ChevronRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </Link>
            </div>

            <div className="space-y-4">
              {/* Comment Item 1 */}
              <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center p-4 rounded-xl border border-gray-100 bg-gray-50/50 hover:bg-white hover:border-indigo-100 transition-colors gap-4">
                <div className="flex items-center gap-4">
                  <div className="bg-white border border-gray-200 shadow-sm rounded-xl p-2 text-center min-w-[56px]">
                    <span className="text-[10px] text-gray-500 block uppercase font-bold tracking-wider">Dec</span>
                    <span className="text-lg font-black text-indigo-600 block leading-none mt-0.5">20</span>
                  </div>
                  <div>
                    <h4 className="font-bold text-gray-800 text-sm sm:text-base">"Needs review by legal team"</h4>
                    <p className="text-xs sm:text-sm text-gray-500 font-medium mt-0.5">j.smith@company.com • Q4_Report.pdf</p>
                  </div>
                </div>
                <span className="self-start sm:self-auto text-emerald-600 font-bold bg-emerald-100/50 border border-emerald-200 px-3 py-1 rounded-full text-xs whitespace-nowrap">
                  Extracted
                </span>
              </div>
              
              {/* Comment Item 2 */}
              <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center p-4 rounded-xl border border-gray-100 bg-gray-50/50 hover:bg-white hover:border-indigo-100 transition-colors gap-4">
                <div className="flex items-center gap-4">
                  <div className="bg-white border border-gray-200 shadow-sm rounded-xl p-2 text-center min-w-[56px]">
                    <span className="text-[10px] text-gray-500 block uppercase font-bold tracking-wider">Dec</span>
                    <span className="text-lg font-black text-indigo-600 block leading-none mt-0.5">19</span>
                  </div>
                  <div>
                    <h4 className="font-bold text-gray-800 text-sm sm:text-base">"Update the figures on page 12"</h4>
                    <p className="text-xs sm:text-sm text-gray-500 font-medium mt-0.5">admin • Audit_Draft_v2.pdf</p>
                  </div>
                </div>
                <span className="self-start sm:self-auto text-emerald-600 font-bold bg-emerald-100/50 border border-emerald-200 px-3 py-1 rounded-full text-xs whitespace-nowrap">
                  Extracted
                </span>
              </div>
            </div>

          </div>
        </div>
      </div>
    </Layout>
  );
}