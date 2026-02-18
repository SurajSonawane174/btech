import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Navbar() {
  const { user, logout } = useAuth();

  return (
    <nav className="bg-blue-600 text-white px-6 py-4 flex justify-between items-center shadow-lg">
      <div className="flex gap-6">
        <Link 
          to="/dashboard" 
          className="hover:text-blue-200 transition duration-300 font-semibold text-lg"
        >
          Dashboard
        </Link>
        {user?.role === "admin" && (
          <Link 
            to="/upload" 
            className="hover:text-blue-200 transition duration-300 font-semibold text-lg"
          >
            Upload
          </Link>
        )}
      </div>

      <div>
        {user && (
          <div className="flex items-center gap-4">
            <span className="text-sm font-medium">
              Welcome, {user.name || user.email}
            </span>
            <button
              onClick={logout}
              className="bg-red-600 hover:bg-red-700 px-4 py-2 rounded-lg font-semibold transition duration-300 shadow-md hover:shadow-lg"
            >
              Logout
            </button>
          </div>
        )}
      </div>
    </nav>
  );
}
