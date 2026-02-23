import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import api from "../api/axios";
import { useAuth } from "../auth/AuthContext";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("user"); // Added role state
  const [loading, setLoading] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();

  // const handleSubmit = async (e) => {
  //   e.preventDefault();
  //   setLoading(true);

  //   try {
  //     // Sending role along with email and password
  //     const res = await api.post("/auth/login", { email, password, role });
  //     login(res.data.token); 
  //     navigate("/dashboard");
  //   } catch (err) {
  //     alert("Invalid credentials");
  //   } finally {
  //     setLoading(false);
  //   }
  // };
  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      // ❌ COMMENT OUT THE REAL BACKEND CALL:
      // const res = await api.post("/auth/login", { email, password, role });
      
      // ✅ FAKE A SMALL DELAY (optional, just to see your new loading spinner)
      await new Promise((resolve) => setTimeout(resolve, 800));

      // ✅ MOCK A SUCCESSFUL LOGIN:
      // Pass a dummy token to your AuthContext so it thinks you are logged in
      login("temporary-mock-jwt-token-123"); 
      
      // Force the navigation to the dashboard
      navigate("/dashboard");

    } catch (err) {
      alert("Invalid credentials");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-100 via-white to-purple-100 px-4">
      <div className="w-full max-w-md rounded-3xl p-8 border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.08)] bg-white/40 backdrop-blur-md">
        <div className="text-center mb-6">
          <h2 className="text-3xl font-bold text-gray-800 mb-1">Welcome Back</h2>
          <p className="text-gray-600">Sign in to your account</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-gray-700 font-medium mb-2">Email</label>
            <input
              type="email"
              placeholder="Enter your email"
              className="w-full border border-white/50 bg-white/50 text-gray-800 placeholder-gray-500 p-3 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-300 focus:bg-white/80 transition-all"
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="block text-gray-700 font-medium mb-2">Password</label>
            <input
              type="password"
              placeholder="Enter your password"
              className="w-full border border-white/50 bg-white/50 text-gray-800 placeholder-gray-500 p-3 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-300 focus:bg-white/80 transition-all"
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          {/* Added Role Selection to Login */}
          <div>
            <label className="block text-gray-700 font-medium mb-2">Role</label>
            <select
              className="w-full border border-white/50 bg-white/50 text-gray-800 p-3 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-300 focus:bg-white/80 transition-all"
              onChange={(e) => setRole(e.target.value)}
              value={role}
            >
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
          </div>

          <button 
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600/90 hover:bg-blue-700 text-white font-semibold py-3 rounded-xl transition duration-200 shadow-lg backdrop-blur-sm disabled:opacity-50 disabled:cursor-not-allowed mt-2"
          >
            {loading ? (
              <div className="flex items-center justify-center space-x-2">
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                <span>Signing In...</span>
              </div>
            ) : (
              "Sign In"
            )}
          </button>
        </form>

        <p className="text-gray-600 text-center mt-6">
          Don't have an account?{" "}
          <Link to="/register" className="text-blue-700 font-semibold hover:text-blue-900 transition duration-200">
            Sign Up
          </Link>
        </p>
      </div>
    </div>
  );
}