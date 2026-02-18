import Navbar from "../components/Navbar";
import FileUpload from "../components/FileUpload";

export default function UploadPage() {
  return (
    <>
      <Navbar />
      <div className="min-h-screen bg-gray-50">
        <div className="container mx-auto px-6 py-8">
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-800 mb-2">Upload & Scan PDFs</h1>
            <p className="text-gray-600">Upload your PDF documents for automated scanning and analysis</p>
          </div>
          <FileUpload />
        </div>
      </div>
    </>
  );
}
