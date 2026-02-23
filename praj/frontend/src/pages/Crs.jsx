import React, { useState } from 'react';
import { FileSpreadsheet, UploadCloud, CheckSquare, Download, Settings, File } from 'lucide-react';

const CreateCRS = () => {
  const [file, setFile] = useState(null);
  const [selectedFields, setSelectedFields] = useState({
    commentId: true,
    reviewerName: true,
    documentSection: true,
    commentText: true,
    severity: false,
    resolutionStatus: true,
    developerResponse: true,
    targetDate: false,
  });

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
    }
  };

  const handleFieldToggle = (field) => {
    setSelectedFields((prev) => ({
      ...prev,
      [field]: !prev[field],
    }));
  };

  const handleDownload = (e) => {
    e.preventDefault();
    // In a real app, you would use a library like 'xlsx' or send this data to your Node backend
    // to generate and return the formatted Excel file.
    alert(`Generating CRS Excel sheet...\nTemplate: ${file ? file.name : 'Default Template'}`);
  };

  // Helper for rendering checkboxes beautifully
  const CheckboxOption = ({ id, label, description }) => (
    <label 
      htmlFor={id} 
      className={`flex items-start gap-3 p-4 rounded-xl border-2 cursor-pointer transition-all duration-200 ${
        selectedFields[id] 
          ? 'border-indigo-500 bg-indigo-50/50' 
          : 'border-gray-100 hover:border-indigo-200 bg-white'
      }`}
    >
      <div className="flex-shrink-0 mt-0.5">
        <input
          type="checkbox"
          id={id}
          className="w-5 h-5 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 transition-colors"
          checked={selectedFields[id]}
          onChange={() => handleFieldToggle(id)}
        />
      </div>
      <div>
        <p className={`text-sm font-bold ${selectedFields[id] ? 'text-indigo-900' : 'text-gray-700'}`}>
          {label}
        </p>
        <p className="text-xs text-gray-500 mt-1">{description}</p>
      </div>
    </label>
  );

  return (
    <div className="max-w-5xl mx-auto animate-fade-in-up">
      
      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-black text-gray-800 tracking-tight flex items-center gap-3">
          <div className="p-2 bg-indigo-100 text-indigo-600 rounded-lg shadow-sm">
            <FileSpreadsheet className="w-6 h-6" />
          </div>
          Create Comment Resolution Sheet
        </h1>
        <p className="text-gray-500 text-sm mt-2 ml-1">
          Upload your template and select the data fields to generate a formatted CRS.
        </p>
      </div>

      <form onSubmit={handleDownload} className="space-y-6">
        
        {/* Step 1: Upload Template */}
        <div className="bg-white rounded-2xl p-6 md:p-8 shadow-sm border border-gray-200">
          <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2 mb-4">
            <UploadCloud className="w-5 h-5 text-indigo-500" />
            1. Upload Base Template (Optional)
          </h2>
          
          <div className="relative group">
            <label className={`flex flex-col items-center justify-center w-full h-40 border-2 border-dashed rounded-xl cursor-pointer transition-all duration-300 ${
              file ? 'border-emerald-400 bg-emerald-50/50' : 'border-gray-300 bg-gray-50 hover:bg-indigo-50 hover:border-indigo-400'
            }`}>
              <div className="flex flex-col items-center justify-center pt-5 pb-6">
                {file ? (
                  <>
                    <File className="w-10 h-10 text-emerald-500 mb-3" />
                    <p className="mb-2 text-sm font-bold text-emerald-700">{file.name}</p>
                    <p className="text-xs text-emerald-600/80">{(file.size / 1024).toFixed(2)} KB</p>
                  </>
                ) : (
                  <>
                    <UploadCloud className="w-10 h-10 text-gray-400 mb-3 group-hover:text-indigo-500 transition-colors" />
                    <p className="mb-2 text-sm text-gray-500">
                      <span className="font-bold text-indigo-600">Click to upload</span> or drag and drop
                    </p>
                    <p className="text-xs text-gray-400">.xlsx, .xls, or .csv formats</p>
                  </>
                )}
              </div>
              <input type="file" className="hidden" accept=".xlsx, .xls, .csv" onChange={handleFileChange} />
            </label>
          </div>
        </div>

        {/* Step 2: Select Fields */}
        <div className="bg-white rounded-2xl p-6 md:p-8 shadow-sm border border-gray-200">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
              <CheckSquare className="w-5 h-5 text-indigo-500" />
              2. Select Columns to Include
            </h2>
            <button 
              type="button"
              className="text-xs font-bold text-indigo-600 hover:text-indigo-800 transition-colors flex items-center gap-1"
              onClick={() => setSelectedFields(Object.keys(selectedFields).reduce((acc, key) => ({...acc, [key]: true}), {}))}
            >
              <Settings className="w-3 h-3" /> Select All
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <CheckboxOption 
              id="commentId" 
              label="Comment ID" 
              description="Unique identifier for tracking." 
            />
            <CheckboxOption 
              id="reviewerName" 
              label="Reviewer Name" 
              description="Name of the person leaving the comment." 
            />
            <CheckboxOption 
              id="documentSection" 
              label="Document Section" 
              description="Page, line, or module referenced." 
            />
            <CheckboxOption 
              id="commentText" 
              label="Comment Text" 
              description="The actual review feedback." 
            />
            <CheckboxOption 
              id="severity" 
              label="Severity/Priority" 
              description="High, Medium, or Low impact." 
            />
            <CheckboxOption 
              id="developerResponse" 
              label="Developer Response" 
              description="Action taken to address the comment." 
            />
            <CheckboxOption 
              id="resolutionStatus" 
              label="Resolution Status" 
              description="Open, In Progress, or Closed." 
            />
            <CheckboxOption 
              id="targetDate" 
              label="Target Fix Date" 
              description="Deadline for the resolution." 
            />
          </div>
        </div>

        {/* Action Button */}
        <div className="flex justify-end">
          <button 
            type="submit" 
            className="w-full md:w-auto px-8 py-3.5 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-bold rounded-xl shadow-lg transform transition hover:-translate-y-0.5 flex items-center justify-center gap-2"
          >
            <Download className="w-5 h-5" />
            Generate & Download CRS
          </button>
        </div>

      </form>
    </div>
  );
};

export default CreateCRS;