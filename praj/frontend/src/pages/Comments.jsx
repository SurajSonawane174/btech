import Layout from "../components/Layout";

export default function Comments() {
  // A bit of dummy data to show off the layout. 
  // You will eventually replace this with real data from your Python backend!
  const allComments = [
    {
      id: 1,
      date: "20 Dec",
      text: "Needs review by legal team",
      author: "j.smith@company.com",
      document: "Q4_Report.pdf",
      status: "Extracted",
      statusColor: "text-emerald-500 bg-emerald-50"
    },
    {
      id: 2,
      date: "19 Dec",
      text: "Update the figures on page 12",
      author: "admin",
      document: "Audit_Draft_v2.pdf",
      status: "Extracted",
      statusColor: "text-emerald-500 bg-emerald-50"
    },
    {
      id: 3,
      date: "18 Dec",
      text: "Missing signature here",
      author: "h.potter@company.com",
      document: "Contract.pdf",
      status: "Processing",
      statusColor: "text-amber-500 bg-amber-50"
    },
    {
      id: 4,
      date: "15 Dec",
      text: "Clarify the terms in section 4.2",
      author: "l.croft@company.com",
      document: "Vendor_Agreement.pdf",
      status: "Extracted",
      statusColor: "text-emerald-500 bg-emerald-50"
    },
    {
      id: 5,
      date: "14 Dec",
      text: "Is this the final revision?",
      author: "b.wayne@company.com",
      document: "Project_Proposal.pdf",
      status: "Failed",
      statusColor: "text-rose-500 bg-rose-50"
    }
  ];

  return (
    <Layout>
      <div className="max-w-6xl mx-auto">
        <div className="flex justify-between items-end mb-8">
          <div>
            <h1 className="text-3xl font-extrabold text-slate-900 mb-2">All Comments</h1>
            <p className="text-slate-500 font-medium">View and manage every comment extracted from your scanned documents.</p>
          </div>
          
          {/* A handy little filter or export button for the future */}
          <button className="bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 px-5 py-2.5 rounded-xl font-semibold transition-all shadow-sm flex items-center gap-2">
            <span>⬇️</span> Export List
          </button>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
          <div className="p-6 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
            <h3 className="font-bold text-slate-700">Comment Log</h3>
            <span className="bg-indigo-100 text-indigo-700 text-xs font-bold px-3 py-1 rounded-full">
              {allComments.length} Total
            </span>
          </div>

          <div className="p-6 space-y-4">
            {allComments.map((comment) => (
              <div key={comment.id} className="flex flex-col sm:flex-row sm:justify-between sm:items-center p-4 rounded-xl border border-slate-100 hover:border-indigo-100 hover:bg-slate-50 transition-colors gap-4">
                
                <div className="flex items-start gap-4">
                  <div className="bg-white border border-slate-200 rounded-xl p-3 text-center min-w-[60px] shadow-sm shrink-0">
                    <span className="text-xs text-slate-400 block uppercase font-bold">{comment.date.split(' ')[1]}</span>
                    <span className="text-xl font-bold text-slate-800 block">{comment.date.split(' ')[0]}</span>
                  </div>
                  
                  <div>
                    <h4 className="font-bold text-slate-800 text-lg mb-1">"{comment.text}"</h4>
                    <div className="flex items-center gap-2 text-sm text-slate-500">
                      <span className="font-medium text-slate-700">{comment.author}</span>
                      <span>•</span>
                      <span className="flex items-center gap-1">
                        📄 {comment.document}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-end sm:justify-start gap-4 shrink-0">
                  <span className={`font-bold px-4 py-1.5 rounded-full text-sm ${comment.statusColor}`}>
                    {comment.status}
                  </span>
                  <button className="text-slate-400 hover:text-indigo-600 transition-colors p-2">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7"></path>
                    </svg>
                  </button>
                </div>

              </div>
            ))}
          </div>
        </div>
      </div>
    </Layout>
  );
}