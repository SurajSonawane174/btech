import React, { useState, useEffect } from 'react';
import { 
  UploadCloud, 
  FileText, 
  FolderDown, 
  Loader2, 
  CheckCircle, 
  Download, 
  FileSpreadsheet, 
  FileJson,
  File as FileIcon
} from 'lucide-react';

const CommentExtractor = () => {
  // States: 'idle' | 'uploading' | 'processing' | 'success' | 'error'
  const [status, setStatus] = useState('idle');
  const [fileInfo, setFileInfo] = useState(null);
  const [progress, setProgress] = useState(0);

  // Handle File or Folder Selection
  const handleSelection = (e, type) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      if (type === 'folder') {
        setFileInfo({ name: `${files.length} files selected (Folder)`, type: 'folder' });
      } else {
        setFileInfo({ name: files[0].name, type: 'file', size: files[0].size });
      }
      setStatus('idle');
      setProgress(0);
    }
  };

  // Simulate the Upload and Processing Flow
  const startExtraction = (e) => {
    e.preventDefault();
    if (!fileInfo) return;

    setStatus('uploading');
    setProgress(0);

    // Simulate Upload Phase
    const uploadInterval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          clearInterval(uploadInterval);
          startProcessing();
          return 100;
        }
        return prev + 10;
      });
    }, 200);
  };

  const startProcessing = () => {
    setStatus('processing');
    setProgress(0);

    // Simulate Processing Phase
    const processInterval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          clearInterval(processInterval);
          setStatus('success');
          return 100;
        }
        return prev + 5; // Processing is a bit slower
      });
    }, 300);
  };

  const resetUploader = () => {
    setFileInfo(null);
    setStatus('idle');
    setProgress(0);
  };

  return (
    <div className="max-w-4xl mx-auto animate-fade-in-up">
      
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-black text-gray-800 tracking-tight flex items-center gap-3">
          <div className="p-2 bg-indigo-100 text-indigo-600 rounded-lg shadow-sm">
            <UploadCloud className="w-6 h-6" />
          </div>
          Project Comment Extractor
        </h1>
        <p className="text-gray-500 text-sm mt-2 ml-1">
          Upload a PDF document or a complete project folder to automatically extract all comments and reviews.
        </p>
      </div>

      <div className="bg-white rounded-2xl p-6 md:p-8 shadow-sm border border-gray-200">
        
        {/* --- STATE: IDLE (Selection) --- */}
        {status === 'idle' && (
          <form onSubmit={startExtraction} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              
              {/* Option 1: Upload Single PDF */}
              <label className="relative flex flex-col items-center justify-center w-full h-48 border-2 border-dashed border-gray-300 rounded-xl bg-gray-50 hover:bg-indigo-50 hover:border-indigo-400 cursor-pointer transition-all duration-300 group">
                <div className="flex flex-col items-center justify-center pt-5 pb-6 text-center px-4">
                  <FileText className="w-10 h-10 text-gray-400 mb-3 group-hover:text-indigo-500 transition-colors" />
                  <p className="mb-1 text-sm font-bold text-gray-700 group-hover:text-indigo-700">Upload PDF File</p>
                  <p className="text-xs text-gray-500">Extract from a single document</p>
                </div>
                <input type="file" className="hidden" accept=".pdf" onChange={(e) => handleSelection(e, 'file')} />
              </label>

              {/* Option 2: Upload Project Folder */}
              <label className="relative flex flex-col items-center justify-center w-full h-48 border-2 border-dashed border-gray-300 rounded-xl bg-gray-50 hover:bg-purple-50 hover:border-purple-400 cursor-pointer transition-all duration-300 group">
                <div className="flex flex-col items-center justify-center pt-5 pb-6 text-center px-4">
                  <FolderDown className="w-10 h-10 text-gray-400 mb-3 group-hover:text-purple-500 transition-colors" />
                  <p className="mb-1 text-sm font-bold text-gray-700 group-hover:text-purple-700">Upload Project Folder</p>
                  <p className="text-xs text-gray-500">Extract from multiple files at once</p>
                </div>
                {/* webkitdirectory allows folder selection in modern browsers */}
                <input type="file" className="hidden" webkitdirectory="true" directory="true" onChange={(e) => handleSelection(e, 'folder')} />
              </label>
            </div>

            {/* Selected File Indicator */}
            {fileInfo && (
              <div className="flex items-center justify-between p-4 bg-emerald-50 border border-emerald-200 rounded-xl">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-emerald-100 rounded-lg text-emerald-600">
                    {fileInfo.type === 'folder' ? <FolderDown className="w-5 h-5" /> : <FileIcon className="w-5 h-5" />}
                  </div>
                  <div>
                    <p className="text-sm font-bold text-emerald-900">{fileInfo.name}</p>
                    <p className="text-xs text-emerald-600 font-medium">Ready to process</p>
                  </div>
                </div>
                <button 
                  type="submit" 
                  className="px-6 py-2.5 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-bold rounded-lg shadow-md transform transition hover:-translate-y-0.5"
                >
                  Upload & Extract
                </button>
              </div>
            )}
          </form>
        )}

        {/* --- STATE: UPLOADING OR PROCESSING --- */}
        {(status === 'uploading' || status === 'processing') && (
          <div className="flex flex-col items-center justify-center py-12 text-center animate-fade-in-up">
            <Loader2 className="w-12 h-12 text-indigo-600 animate-spin mb-4" />
            <h3 className="text-xl font-bold text-gray-800 mb-2">
              {status === 'uploading' ? 'Uploading Project...' : 'Extracting Comments...'}
            </h3>
            <p className="text-gray-500 text-sm max-w-sm mb-8">
              {status === 'uploading' 
                ? 'Securely transferring your files to our servers. Please do not close this window.' 
                : 'Our system is parsing the documents and compiling all review comments. This might take a moment.'}
            </p>

            {/* Progress Bar */}
            <div className="w-full max-w-md bg-gray-100 rounded-full h-3 mb-2 overflow-hidden shadow-inner">
              <div 
                className={`h-3 rounded-full transition-all duration-300 ease-out ${
                  status === 'uploading' ? 'bg-indigo-500' : 'bg-purple-500'
                }`}
                style={{ width: `${progress}%` }}
              ></div>
            </div>
            <p className="text-xs font-bold text-gray-500">{progress}%</p>
          </div>
        )}

        {/* --- STATE: SUCCESS (Download Options) --- */}
        {status === 'success' && (
          <div className="text-center animate-fade-in-up py-4">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-emerald-100 text-emerald-500 mb-4 shadow-sm">
              <CheckCircle className="w-8 h-8" />
            </div>
            <h3 className="text-2xl font-black text-gray-800 tracking-tight mb-2">Extraction Complete!</h3>
            <p className="text-gray-500 text-sm mb-8">
              We successfully processed <span className="font-bold text-gray-700">{fileInfo.name}</span>. Choose your preferred download format below.
            </p>

            {/* Download Buttons Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-2xl mx-auto mb-8">
              
              <button className="flex flex-col items-center justify-center p-6 border-2 border-gray-100 rounded-xl hover:border-red-300 hover:bg-red-50 transition-all group">
                <FileText className="w-8 h-8 text-red-500 mb-3 group-hover:scale-110 transition-transform" />
                <span className="font-bold text-gray-800">Download PDF</span>
                <span className="text-xs text-gray-500 mt-1">Formatted Report</span>
              </button>

              <button className="flex flex-col items-center justify-center p-6 border-2 border-gray-100 rounded-xl hover:border-emerald-300 hover:bg-emerald-50 transition-all group">
                <FileSpreadsheet className="w-8 h-8 text-emerald-500 mb-3 group-hover:scale-110 transition-transform" />
                <span className="font-bold text-gray-800">Download Excel</span>
                <span className="text-xs text-gray-500 mt-1">Standard CRS</span>
              </button>

              <button className="flex flex-col items-center justify-center p-6 border-2 border-gray-100 rounded-xl hover:border-amber-300 hover:bg-amber-50 transition-all group">
                <FileJson className="w-8 h-8 text-amber-500 mb-3 group-hover:scale-110 transition-transform" />
                <span className="font-bold text-gray-800">Download JSON</span>
                <span className="text-xs text-gray-500 mt-1">Raw Data</span>
              </button>

            </div>

            <button 
              onClick={resetUploader}
              className="text-sm font-bold text-indigo-600 hover:text-indigo-800 transition-colors hover:underline"
            >
              Extract another project
            </button>
          </div>
        )}

      </div>
    </div>
  );
};

export default CommentExtractor;