import Layout from "../components/Layout";
import FileUpload from "../components/FileUpload";

export default function UploadPage() {
  return (
    <Layout>
      <div className="max-w-5xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-extrabold text-slate-900 mb-2">Upload & Scan PDFs</h1>
          <p className="text-slate-500 font-medium">Upload your PDF documents for automated scanning and analysis</p>
        </div>
        
        <FileUpload />
      </div>
    </Layout>
  );
}