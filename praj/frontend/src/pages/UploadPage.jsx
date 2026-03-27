import React, { useState } from 'react';
import Layout from '../components/Layout';
import FileUpload from '../components/FileUpload';
import { 
  UploadCloud, Search, Settings, Image as ImageIcon, 
  CheckSquare, MessageSquare, Check, Loader2
} from 'lucide-react';

const STEPS = [
  { icon: UploadCloud,  title: "File Upload",          sub: "Uploading drawing to server"                  },
  { icon: Search,       title: "OCR Processing",        sub: "Extracting text and annotations"              },
  { icon: Settings,     title: "Comment Parsing",       sub: "AI categorisation & confidence scoring"       },
  { icon: ImageIcon,    title: "Snapshot Extraction",   sub: "Cropping per-comment image regions"           },
  { icon: CheckSquare,  title: "CRS Generation",        sub: "Creating comment resolution sheets"           },
];

export default function UploadPage() {
  const [loading, setLoading]           = useState(false);
  const [currentStep, setCurrentStep]   = useState(-1);
  const [completedSteps, setCompleted]  = useState([]);
  const [done, setDone]                 = useState(false);
  const [extractedComments, setExtractedComments] = useState([]);

  async function runSteps() {
    setDone(false);
    setCompleted([]);
    for (let i = 0; i < STEPS.length; i++) {
      setCurrentStep(i);
      await new Promise(res => setTimeout(res, i < 2 ? 600 : 1400));
      setCompleted(prev => [...prev, i]);
    }
    setCurrentStep(-1);
    setDone(true);
  }

  function resetStatus() {
    setCurrentStep(-1);
    setCompleted([]);
    setDone(false);
    setExtractedComments([]);
  }

  function handleProcessComplete(payload) {
    // payload is the extracted array from FileUpload
    setExtractedComments(payload || []);
  }

  const getStepState = (i) => {
    if (completedSteps.includes(i)) return 'done';
    if (currentStep === i)          return 'active';
    return 'idle';
  };

  return (
    <Layout>
      <div className="max-w-7xl mx-auto px-4 pb-12 space-y-8">
        
        {/* HEADER SECTION */}
        <div className="border-b border-slate-200 pb-6">
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Process New Drawing</h1>
          <p className="text-slate-500 mt-1">Upload a PDF drawing for OCR comment extraction and CRS generation</p>
        </div>

        {/* MAIN GRID - Uses 12-column grid for precise control */}
        <div className="grid grid-cols-12 gap-8 items-start">
          
          {/* LEFT COLUMN: UPLOAD & MAIN TABLE (Takes 8/12 of space) */}
          <div className="col-span-12 lg:col-span-8 space-y-6 min-w-0">
            <FileUpload
              loading={loading}
              setLoading={setLoading}
              onProcess={runSteps}
              onReset={resetStatus}
              onComplete={handleProcessDrawingComplete => handleProcessComplete(handleProcessDrawingComplete)}
            />
          </div>

          {/* RIGHT COLUMN: SIDEBAR (Takes 4/12 of space) */}
          <div className="col-span-12 lg:col-span-4 space-y-6 sticky top-6">

            {/* STATUS PANEL */}
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 overflow-hidden">
              <div className="flex items-center justify-between mb-6">
                <h3 className="font-bold text-slate-800 flex items-center gap-2">
                  <Settings size={18} className="text-indigo-500" /> Status
                </h3>
                <span className={`text-[10px] uppercase tracking-widest px-2.5 py-1 rounded-md font-black ${
                  done    ? 'bg-emerald-100 text-emerald-700' :
                  loading ? 'bg-amber-100 text-amber-700 animate-pulse' :
                  'bg-slate-100 text-slate-500'
                }`}>
                  {done ? 'Complete' : loading ? 'In Progress' : 'Idle'}
                </span>
              </div>

              <div className="space-y-3">
                {STEPS.map((step, i) => {
                  const state = getStepState(i);
                  return (
                    <div key={i} className={`group flex flex-col p-3 rounded-xl border transition-all duration-300 ${
                      state === 'done'   ? 'bg-emerald-50/50 border-emerald-100' :
                      state === 'active' ? 'bg-indigo-50 border-indigo-200 ring-2 ring-indigo-500/10' :
                      'bg-slate-50 border-transparent opacity-60'
                    }`}>
                      <div className="flex items-center gap-3">
                        <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 ${
                          state === 'done' ? 'bg-emerald-500 text-white' :
                          state === 'active' ? 'bg-indigo-600 text-white' : 'bg-slate-200 text-slate-400'
                        }`}>
                          {state === 'done' ? <Check size={14} /> : <step.icon size={12} />}
                        </div>
                        <div className="min-w-0 flex-1">
                          <h4 className={`text-xs font-bold truncate ${
                            state === 'done' ? 'text-emerald-700' : 
                            state === 'active' ? 'text-indigo-900' : 'text-slate-500'
                          }`}>
                            {step.title}
                          </h4>
                        </div>
                        {state === 'active' && <Loader2 size={14} className="text-indigo-500 animate-spin" />}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Progress Bar */}
              {(loading || done) && (
                <div className="mt-6 pt-6 border-t border-slate-100">
                  <div className="flex justify-between text-[10px] font-black text-slate-400 mb-2 uppercase tracking-tighter">
                    <span>Overall Completion</span>
                    <span>{Math.round((completedSteps.length / STEPS.length) * 100)}%</span>
                  </div>
                  <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ease-out ${
                        done ? 'bg-emerald-500' : 'bg-indigo-600'
                      }`}
                      style={{ width: `${(completedSteps.length / STEPS.length) * 100}%` }}
                    />
                  </div>
                </div>
              )}
            </div>

            {/* EXTRACTED COMMENTS SUMMARY */}
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col max-h-[400px]">
              <div className="p-4 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between">
                <div className="flex items-center gap-2 font-bold text-slate-700 text-sm">
                  <MessageSquare size={16} className="text-indigo-500" /> Recent
                </div>
                {done && (
                  <span className="bg-indigo-600 text-white text-[10px] px-2 py-0.5 rounded font-bold">
                    {extractedComments.length} Total
                  </span>
                )}
              </div>
              
              <div className="overflow-y-auto custom-scrollbar">
                {done ? (
                  <div className="divide-y divide-slate-50">
                    {extractedComments.map((c, i) => (
                      <div key={i} className="p-3 flex items-center justify-between hover:bg-slate-50 transition-colors">
                        <div className="flex flex-col min-w-0">
                          <span className="text-[11px] font-bold text-slate-900 truncate">
                            {c.comment_id || `ID-${i+1}`}
                          </span>
                          <span className="text-[10px] text-slate-400">Page {c.page_sheet || 'N/A'}</span>
                        </div>
                        <span className="text-[9px] font-black uppercase px-2 py-0.5 rounded bg-red-50 text-red-600 border border-red-100">
                          Open
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-10 text-center space-y-2">
                    <div className="w-10 h-10 bg-slate-50 rounded-full flex items-center justify-center mx-auto">
                       <MessageSquare size={18} className="text-slate-200" />
                    </div>
                    <p className="text-[11px] text-slate-400 font-medium px-4">
                      {loading ? 'AI is scanning drawing regions...' : 'No comments extracted yet'}
                    </p>
                  </div>
                )}
              </div>
            </div>

          </div>
        </div>
      </div>
      <style jsx>{`
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #e2e8f0; border-radius: 10px; }
      `}</style>
    </Layout>
  );
}