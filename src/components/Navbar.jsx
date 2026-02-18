import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Navbar() {
  const { user, logout } = useAuth();

  return (
    <nav className="bg-gray-800 text-white px-6 py-3 flex justify-between items-center">
      <div className="flex gap-4">
        <Link to="/dashboard" className="hover:text-gray-300">
          Dashboard
        </Link>
        {user?.role === "admin" && (
          <Link to="/upload" className="hover:text-gray-300">
            Upload
          </Link>
        )}
      </div>

      <div>
        {user && (
          <button
            onClick={logout}
            className="bg-red-600 px-3 py-1 rounded hover:bg-red-700"
          >
            Logout
          </button>
        )}
      </div>
    </nav>
  );
}
