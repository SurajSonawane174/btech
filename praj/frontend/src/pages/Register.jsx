import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import api from "../api/axios"; 

export default function Register() {
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    role: "user",
  });
  const [loading, setLoading] = useState(false);

  const navigate = useNavigate();

  const handleChange = (e) => {
    setForm({
      ...form,
      [e.target.name]: e.target.value,
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      // Rename 'name' to 'username' to match backend schema
      const { name, ...rest } = form;
      await api.post("/api/users/register", { username: name, ...rest });
      alert("Account created successfully");
      navigate("/login");
    } catch (err) {
      const errorMsg = err.response?.data?.message || "Registration failed";
      alert(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 relative overflow-hidden px-4 py-8">
      
      {/* Background Glowing Blobs */}
      <div className="absolute top-1/4 -right-10 w-96 h-96 bg-purple-600 rounded-full mix-blend-screen filter blur-[128px] opacity-40"></div>
      <div className="absolute bottom-1/4 -left-10 w-96 h-96 bg-indigo-600 rounded-full mix-blend-screen filter blur-[128px] opacity-40"></div>

      {/* Glassmorphism Card */}
      <div className="w-full max-w-md relative z-10 backdrop-blur-xl bg-white/10 border border-white/20 rounded-[2rem] p-8 sm:p-10 shadow-[0_8px_32px_0_rgba(0,0,0,0.3)]">

        <div className="text-center mb-8 mt-2">
          <h2 className="text-3xl font-extrabold text-white mb-2 tracking-tight">Create Account</h2>
          {/* <p className="text-slate-300 font-medium">Join us and start scanning</p> */}
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-slate-200 font-bold mb-2 text-sm tracking-wide">Full Name</label>
            <input
              name="name"
              placeholder="Jon Snow"
              className="w-full bg-white/5 border border-white/10 text-white placeholder-slate-400 p-3.5 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/80 focus:bg-white/10 transition-all shadow-inner"
              onChange={handleChange}
              required
            />
          </div>

          <div>
            <label className="block text-slate-200 font-bold mb-2 text-sm tracking-wide">Email Address</label>
            <input
              name="email"
              type="email"
              placeholder="name@company.com"
              className="w-full bg-white/5 border border-white/10 text-white placeholder-slate-400 p-3.5 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/80 focus:bg-white/10 transition-all shadow-inner"
              onChange={handleChange}
              required
            />
          </div>

          <div>
            <label className="block text-slate-200 font-bold mb-2 text-sm tracking-wide">Password</label>
            <input
              name="password"
              type="password"
              placeholder="Create a strong password"
              className="w-full bg-white/5 border border-white/10 text-white placeholder-slate-400 p-3.5 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/80 focus:bg-white/10 transition-all shadow-inner"
              onChange={handleChange}
              required
            />
          </div>

          <div>
            <label className="block text-slate-200 font-bold mb-2 text-sm tracking-wide">Role</label>
            <select
              name="role"
              className="w-full bg-white/5 border border-white/10 text-white p-3.5 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/80 focus:bg-white/10 transition-all shadow-inner appearance-none"
              onChange={handleChange}
            >
              {/* Native select options need a dark background so they are readable when opened */}
              <option value="user" className="bg-slate-800 text-white">User</option>
              <option value="admin" className="bg-slate-800 text-white">Admin</option>
            </select>
          </div>

          <button 
            type="submit"
            disabled={loading}
            className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-3.5 rounded-xl transition-all shadow-[0_0_20px_rgba(79,70,229,0.4)] hover:shadow-[0_0_25px_rgba(79,70,229,0.6)] disabled:opacity-70 disabled:cursor-not-allowed mt-4 border border-indigo-400/50"
          >
            {loading ? (
              <div className="flex items-center justify-center space-x-2">
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                <span>Creating Account...</span>
              </div>
            ) : (
              "Sign Up"
            )}
          </button>
        </form>

        <p className="text-slate-300 text-center font-medium mt-8 text-sm">
          Already have an account?{" "}
          <Link to="/login" className="text-indigo-400 font-bold hover:text-indigo-300 transition duration-200 drop-shadow-sm">
            Sign In
          </Link>
        </p>
      </div>
    </div>
  );
}