import { Link } from "react-router-dom";
import Layout from "../components/Layout";

export default function Dashboard() {
  return (
    <Layout>
      <div className="flex justify-between items-center mb-10">
        <div>
          <h1 className="text-4xl font-extrabold text-slate-900 mb-1">Hello, Analyst!</h1>
          <p className="text-slate-500 font-medium">Here is your document extraction overview.</p>
        </div>
        <div className="flex gap-4">
          <button className="bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 px-6 py-3 rounded-xl font-semibold transition-all shadow-sm flex items-center gap-2">
            Get CRS
          </button>
          <Link to="/upload" className="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-3 rounded-xl font-semibold transition-all shadow-lg hover:shadow-indigo-500/30 flex items-center gap-2">
            <span>+</span> Upload Document
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6 flex flex-col justify-between">
          <div className="flex justify-between items-start">
            <div className="flex items-center gap-3">
              <div className="bg-indigo-100 text-indigo-600 p-2 rounded-lg">💬</div>
              <h3 className="text-slate-500 font-bold text-sm tracking-wide">TOTAL EXTRACTED</h3>
            </div>
            <span className="text-indigo-500 font-bold text-xl">↗</span>
          </div>
          <div className="mt-4">
            <h2 className="text-4xl font-bold text-slate-800 mb-1">4,250</h2>
            <p className="text-indigo-500 text-sm font-medium flex items-center gap-1">
              Comments Extracted
            </p>
          </div>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6 flex flex-col justify-between">
          <div className="flex justify-between items-start">
            <div className="flex items-center gap-3">
              <div className="bg-indigo-100 text-indigo-600 p-2 rounded-lg">📄</div>
              <h3 className="text-slate-500 font-bold text-sm tracking-wide">DOCUMENTS</h3>
            </div>
            <span className="text-indigo-500 font-bold text-xl">↗</span>
          </div>
          <div className="mt-4">
            <h2 className="text-4xl font-bold text-slate-800 mb-1">124</h2>
            <p className="text-indigo-500 text-sm font-medium flex items-center gap-1">
              Successfully Scanned
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6 col-span-1">
          <div className="flex justify-between items-center mb-10">
            <h3 className="text-lg font-bold text-slate-800">Analytics</h3>
            <span className="bg-slate-100 text-slate-600 text-xs font-bold px-3 py-1 rounded-full">30 Days</span>
          </div>
          <div className="h-40 flex items-center justify-center">
            <div className="text-center">
              <p className="text-slate-400 text-sm mb-2">TOTAL QUERIES</p>
              <h4 className="text-3xl font-extrabold text-slate-800">16.8k</h4>
            </div>
          </div>
          <div className="mt-6 pt-6 border-t border-slate-100">
            <div className="flex justify-between text-sm">
              <span className="text-slate-500">API Limit</span>
              <span className="font-bold text-slate-700">50K</span>
            </div>
            <div className="w-full bg-slate-100 rounded-full h-2 mt-2">
              <div className="bg-indigo-600 h-2 rounded-full" style={{ width: '33%' }}></div>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6 col-span-2">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-lg font-bold text-slate-800">Recent Comments</h3>
            <Link to="/comments" className="text-indigo-600 font-bold text-sm hover:text-indigo-800 transition-colors">
              See All →
            </Link>
          </div>

          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-4">
                <div className="bg-slate-50 border border-slate-100 rounded-xl p-3 text-center min-w-[50px]">
                  <span className="text-xs text-slate-400 block uppercase font-bold">Dec</span>
                  <span className="text-lg font-bold text-slate-800 block">20</span>
                </div>
                <div>
                  <h4 className="font-bold text-slate-800">"Needs review by legal team"</h4>
                  <p className="text-sm text-slate-500">j.smith@company.com • Q4_Report.pdf</p>
                </div>
              </div>
              <span className="text-emerald-500 font-bold bg-emerald-50 px-3 py-1 rounded-full text-sm">
                Extracted
              </span>
            </div>
            
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-4">
                <div className="bg-slate-50 border border-slate-100 rounded-xl p-3 text-center min-w-[50px]">
                  <span className="text-xs text-slate-400 block uppercase font-bold">Dec</span>
                  <span className="text-lg font-bold text-slate-800 block">19</span>
                </div>
                <div>
                  <h4 className="font-bold text-slate-800">"Update the figures on page 12"</h4>
                  <p className="text-sm text-slate-500">admin • Audit_Draft_v2.pdf</p>
                </div>
              </div>
              <span className="text-emerald-500 font-bold bg-emerald-50 px-3 py-1 rounded-full text-sm">
                Extracted
              </span>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}