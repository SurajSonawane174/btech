import Navbar from "../components/Navbar";

export default function Dashboard() {
  return (
    <>
      <Navbar />
      <div className="min-h-screen bg-gray-50">
        <div className="container mx-auto px-6 py-8">
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-800 mb-2">Dashboard</h1>
            <p className="text-gray-600">Welcome to the PDF Document Scanner System</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
              <div className="flex items-center mb-4">
                <div className="bg-blue-100 p-3 rounded-lg">
                  <span className="text-2xl">📄</span>
                </div>
                <div className="ml-4">
                  <h3 className="text-lg font-semibold text-gray-800">Documents</h3>
                  <p className="text-gray-600">Manage your PDF files</p>
                </div>
              </div>
              <div className="text-2xl font-bold text-blue-600">0</div>
              <p className="text-sm text-gray-500">Total documents uploaded</p>
            </div>

            <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
              <div className="flex items-center mb-4">
                <div className="bg-green-100 p-3 rounded-lg">
                  <span className="text-2xl">🔍</span>
                </div>
                <div className="ml-4">
                  <h3 className="text-lg font-semibold text-gray-800">Scans</h3>
                  <p className="text-gray-600">Completed document scans</p>
                </div>
              </div>
              <div className="text-2xl font-bold text-green-600">0</div>
              <p className="text-sm text-gray-500">Scans performed</p>
            </div>

            <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
              <div className="flex items-center mb-4">
                <div className="bg-purple-100 p-3 rounded-lg">
                  <span className="text-2xl">📊</span>
                </div>
                <div className="ml-4">
                  <h3 className="text-lg font-semibold text-gray-800">Reports</h3>
                  <p className="text-gray-600">Generated reports</p>
                </div>
              </div>
              <div className="text-2xl font-bold text-purple-600">0</div>
              <p className="text-sm text-gray-500">Reports exported</p>
            </div>
          </div>

          <div className="mt-8 bg-white rounded-lg shadow-md p-6 border border-gray-200">
            <h2 className="text-xl font-semibold text-gray-800 mb-4">Recent Activity</h2>
            <div className="text-center text-gray-500 py-8">
              <span className="text-4xl mb-4 block">📋</span>
              <p>No recent activity</p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
