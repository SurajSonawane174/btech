import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import api from "../api/axios";
import { useAuth } from "../auth/AuthContext";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      // ✅ REAL BACKEND CALL:
      const res = await fetch("http://localhost:8080/api/users/login", {
  method: "POST",
  credentials: "include",
  headers: {
    "Content-Type": "application/json",
  },
  body: JSON.stringify({ email, password }),
});

const data = await res.json();

if (data.user) {
  login(data.user);
}
      
      navigate("/dashboard");
    } catch (err) {
      const errorMsg = err.response?.data?.message || "Invalid credentials";
      setError(errorMsg);
      alert(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 relative overflow-hidden px-4">
      
      {/* Background Glowing Blobs */}
      <div className="absolute top-1/4 -left-10 w-96 h-96 bg-indigo-600 rounded-full mix-blend-screen filter blur-[128px] opacity-40"></div>
      <div className="absolute bottom-1/4 -right-10 w-96 h-96 bg-purple-600 rounded-full mix-blend-screen filter blur-[128px] opacity-40"></div>

      {/* Glassmorphism Card */}
      <div className="w-full max-w-md relative z-10 backdrop-blur-xl bg-white/10 border border-white/20 rounded-[2rem] p-8 sm:p-10 shadow-[0_8px_32px_0_rgba(0,0,0,0.3)]">
        
        <div className="text-center mb-8 mt-2">
          <h2 className="text-3xl font-extrabold text-white mb-2 tracking-tight">Welcome Back</h2>
          <p className="text-slate-300 font-medium">Sign in to your account</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-slate-200 font-bold mb-2 text-sm tracking-wide">Email Address</label>
            <input
              type="email"
              placeholder="name@company.com"
              className="w-full bg-white/5 border border-white/10 text-white placeholder-slate-400 p-3.5 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/80 focus:bg-white/10 transition-all shadow-inner"
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="block text-slate-200 font-bold mb-2 text-sm tracking-wide">Password</label>
            <input
              type="password"
              placeholder="••••••••"
              className="w-full bg-white/5 border border-white/10 text-white placeholder-slate-400 p-3.5 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/80 focus:bg-white/10 transition-all shadow-inner"
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          <button 
            type="submit"
            disabled={loading}
            className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-3.5 rounded-xl transition-all shadow-[0_0_20px_rgba(79,70,229,0.4)] hover:shadow-[0_0_25px_rgba(79,70,229,0.6)] disabled:opacity-70 disabled:cursor-not-allowed mt-4 border border-indigo-400/50"
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

        <p className="text-slate-300 text-center font-medium mt-8 text-sm">
          Don't have an account?{" "}
          <Link to="/register" className="text-indigo-400 font-bold hover:text-indigo-300 transition duration-200 drop-shadow-sm">
            Sign Up
          </Link>
        </p>
      </div>
    </div>
  );
}