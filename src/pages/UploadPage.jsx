import Navbar from "../components/Navbar";
import FileUpload from "../components/FileUpload";

export default function UploadPage() {
  return (
    <>
      <Navbar />
      <div className="p-8 bg-gray-100 min-h-screen">
        <h1 className="text-2xl font-bold mb-6">Upload & Scan PDFs</h1>
        <FileUpload />
      </div>
    </>
  );
}
