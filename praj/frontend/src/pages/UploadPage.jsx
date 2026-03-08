import React, { useState } from 'react';
import Layout from '../components/Layout';
import FileUpload from '../components/FileUpload';
import { 
  UploadCloud, Search, Settings, Image as ImageIcon, 
  CheckSquare, MessageSquare 
} from 'lucide-react';

export default function UploadPage() {
  // We manage the loading state here so both columns can react to it
  const [loading, setLoading] = useState(false);

  return (
    <Layout>
      <div className="max-w-7xl mx-auto space-y-6">
        
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Process New Drawing</h1>
          <p className="text-sm text-slate-500">Upload a PDF drawing for OCR comment extraction and CRS generation</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* Left Column Component */}
          <FileUpload loading={loading} setLoading={setLoading} />

          {/* Right Column (Status & Extraction) */}
          <div className="space-y-6">
            
            {/* Status Panel */}
            <div className="bg-gradient-to-br from-white to-slate-50 rounded-xl border border-slate-200 shadow-sm p-5">
              <div className="flex items-center justify-between mb-6">
                <h3 className="font-bold text-slate-800 flex items-center gap-2">
                  <span className="text-xl">⚙️</span> Processing Status
                </h3>
                <span className={`text-xs px-2.5 py-1 rounded-full font-bold ${loading ? 'bg-amber-100 text-amber-700' : 'bg-indigo-100 text-indigo-700'}`}>
                  {loading ? 'Processing...' : 'Ready'}
                </span>
              </div>
              
              <div className="space-y-4">
                {[
                  { icon: UploadCloud, title: "File Upload", sub: "Uploading drawing to server", color: "text-slate-300" },
                  { icon: Search, title: "OCR Processing", sub: "Extracting text and annotations", color: "text-slate-300" },
                  { icon: Settings, title: "Comment Parsing", sub: "AI categorisation & confidence scoring", color: "text-slate-300" },
                  { icon: ImageIcon, title: "Snapshot Extraction", sub: "Cropping per-comment image regions", color: "text-slate-300" },
                  { icon: CheckSquare, title: "CRS Generation", sub: "Creating comment resolution sheets", color: "text-slate-300" }
                ].map((step, i) => (
                  <div key={i} className={`flex flex-col p-3 rounded-lg border shadow-sm transition-all ${loading ? 'bg-indigo-50/50 border-indigo-100 opacity-100 animate-pulse' : 'bg-white border-slate-100 opacity-60'}`}>
                    <div className="flex items-center gap-3 mb-1">
                      <step.icon size={16} className={loading ? 'text-indigo-400' : step.color} />
                      <h4 className={`font-bold text-sm ${loading ? 'text-indigo-700' : 'text-slate-500'}`}>{step.title}</h4>
                      <span className="ml-auto text-slate-300">—</span>
                    </div>
                    <p className={`text-xs pl-7 ${loading ? 'text-indigo-500' : 'text-slate-400'}`}>{step.sub}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Extracted Comments */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
               <div className="bg-slate-50 p-4 border-b border-slate-100 flex items-center justify-between">
                <div className="flex items-center gap-2 font-bold text-slate-700">
                  <MessageSquare size={16} className="text-purple-500" /> Extracted Comments
                </div>
                <span className="bg-indigo-100 text-indigo-700 text-[10px] px-2 py-0.5 rounded-full font-bold">0 found</span>
              </div>
              <div className="p-4 flex gap-4 text-xs font-bold text-slate-400 uppercase tracking-wide border-b border-slate-100">
                <span className="flex-1">Comment ID</span>
                <span className="flex-1">Page</span>
                <span className="flex-1 text-right">Status</span>
              </div>
              <div className="p-12 text-center text-sm text-slate-400 font-medium">
                No comments extracted yet — process a drawing to begin
              </div>
            </div>

          </div>
        </div>
      </div>
    </Layout>
  );
}