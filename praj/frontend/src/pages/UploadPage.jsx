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

// Mock comments shown after processing completes
const MOCK_COMMENTS = [
  { id: "C-001", page: 4,  status: "Open"        },
  { id: "C-002", page: 5,  status: "Open"        },
  { id: "C-003", page: 6,  status: "Open"        },
  { id: "C-004", page: 7,  status: "In Progress" },
  { id: "C-005", page: 8,  status: "Open"        },
];

export default function UploadPage() {
  const [loading, setLoading]           = useState(false);
  const [currentStep, setCurrentStep]   = useState(-1);   // -1 = idle
  const [completedSteps, setCompleted]  = useState([]);
  const [done, setDone]                 = useState(false);

  // Called by FileUpload — drives the step animation
  async function runSteps() {
    setDone(false);
    setCompleted([]);
    setLoading(true);

    for (let i = 0; i < STEPS.length; i++) {
      setCurrentStep(i);
      // Each step takes ~1.2s so the demo is visible
      await new Promise(res => setTimeout(res, 1200));
      setCompleted(prev => [...prev, i]);
    }

    setCurrentStep(-1);
    setLoading(false);
    setDone(true);
  }

  function resetStatus() {
    setCurrentStep(-1);
    setCompleted([]);
    setDone(false);
  }

  const getStepState = (i) => {
    if (completedSteps.includes(i)) return 'done';
    if (currentStep === i)          return 'active';
    return 'idle';
  };

  return (
    <Layout>
      <div className="max-w-7xl mx-auto space-y-6">
        
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Process New Drawing</h1>
          <p className="text-sm text-slate-500">Upload a PDF drawing for OCR comment extraction and CRS generation</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* Left Column */}
          <FileUpload loading={loading} setLoading={setLoading} onProcess={runSteps} onReset={resetStatus} />

          {/* Right Column */}
          <div className="space-y-6">

            {/* Status Panel */}
            <div className="bg-gradient-to-br from-white to-slate-50 rounded-xl border border-slate-200 shadow-sm p-5">
              <div className="flex items-center justify-between mb-6">
                <h3 className="font-bold text-slate-800 flex items-center gap-2">
                  <span className="text-xl">⚙️</span> Processing Status
                </h3>
                <span className={`text-xs px-2.5 py-1 rounded-full font-bold transition-all ${
                  done    ? 'bg-emerald-100 text-emerald-700' :
                  loading ? 'bg-amber-100 text-amber-700'     :
                  'bg-indigo-100 text-indigo-700'
                }`}>
                  {done ? '✓ Complete' : loading ? 'Processing...' : 'Ready'}
                </span>
              </div>

              <div className="space-y-3">
                {STEPS.map((step, i) => {
                  const state = getStepState(i);
                  return (
                    <div key={i} className={`flex flex-col p-3 rounded-lg border shadow-sm transition-all duration-500 ${
                      state === 'done'   ? 'bg-emerald-50 border-emerald-100 opacity-100' :
                      state === 'active' ? 'bg-indigo-50 border-indigo-200 opacity-100'   :
                      'bg-white border-slate-100 opacity-50'
                    }`}>
                      <div className="flex items-center gap-3 mb-1">
                        {state === 'done' ? (
                          <Check size={16} className="text-emerald-500 flex-shrink-0" />
                        ) : state === 'active' ? (
                          <Loader2 size={16} className="text-indigo-500 animate-spin flex-shrink-0" />
                        ) : (
                          <step.icon size={16} className="text-slate-300 flex-shrink-0" />
                        )}
                        <h4 className={`font-bold text-sm ${
                          state === 'done'   ? 'text-emerald-700' :
                          state === 'active' ? 'text-indigo-700'  :
                          'text-slate-400'
                        }`}>
                          {step.title}
                        </h4>
                        {state === 'active' && (
                          <span className="ml-auto text-[10px] font-bold text-indigo-400 animate-pulse">Running...</span>
                        )}
                        {state === 'done' && (
                          <span className="ml-auto text-[10px] font-bold text-emerald-500">Done</span>
                        )}
                      </div>
                      <p className={`text-xs pl-7 ${
                        state === 'done'   ? 'text-emerald-500' :
                        state === 'active' ? 'text-indigo-400'  :
                        'text-slate-400'
                      }`}>
                        {step.sub}
                      </p>
                    </div>
                  );
                })}
              </div>

              {/* Overall progress bar */}
              {(loading || done) && (
                <div className="mt-5">
                  <div className="flex justify-between text-[10px] font-bold text-slate-400 mb-1">
                    <span>Progress</span>
                    <span>{Math.round((completedSteps.length / STEPS.length) * 100)}%</span>
                  </div>
                  <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-indigo-500 rounded-full transition-all duration-500"
                      style={{ width: `${(completedSteps.length / STEPS.length) * 100}%` }}
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Extracted Comments */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="bg-slate-50 p-4 border-b border-slate-100 flex items-center justify-between">
                <div className="flex items-center gap-2 font-bold text-slate-700">
                  <MessageSquare size={16} className="text-purple-500" /> Extracted Comments
                </div>
                <span className="bg-indigo-100 text-indigo-700 text-[10px] px-2 py-0.5 rounded-full font-bold">
                  {done ? `${MOCK_COMMENTS.length} found` : '0 found'}
                </span>
              </div>
              <div className="p-4 flex gap-4 text-xs font-bold text-slate-400 uppercase tracking-wide border-b border-slate-100">
                <span className="flex-1">Comment ID</span>
                <span className="flex-1">Page</span>
                <span className="flex-1 text-right">Status</span>
              </div>

              {done ? (
                <div className="divide-y divide-slate-50">
                  {MOCK_COMMENTS.map((c, i) => (
                    <div key={i} className="px-4 py-2.5 flex items-center text-sm">
                      <span className="flex-1 font-bold text-indigo-600">{c.id}</span>
                      <span className="flex-1 text-slate-500">Page {c.page}</span>
                      <span className="flex-1 text-right">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                          c.status === 'Open'        ? 'bg-red-50 text-red-600 border-red-100' :
                          c.status === 'In Progress' ? 'bg-amber-50 text-amber-600 border-amber-100' :
                          'bg-emerald-50 text-emerald-600 border-emerald-100'
                        }`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${
                            c.status === 'Open' ? 'bg-red-500' :
                            c.status === 'In Progress' ? 'bg-amber-500' : 'bg-emerald-500'
                          }`} />
                          {c.status}
                        </span>
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-12 text-center text-sm text-slate-400 font-medium">
                  {loading ? 'Extracting comments...' : 'No comments extracted yet — process a drawing to begin'}
                </div>
              )}
            </div>

          </div>
        </div>
      </div>
    </Layout>
  );
}