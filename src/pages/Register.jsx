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
      await api.post("/auth/register", form);
      alert("Account created successfully");
      navigate("/login");
    } catch (err) {
      alert("Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-indigo-600 px-4">
      <div className="bg-white/20 backdrop-blur-lg w-full max-w-md rounded-2xl shadow-2xl p-8 border border-white/30">
        <div className="text-center mb-8">
          <h2 className="text-3xl font-bold text-white mb-2">Create Account</h2>
          <p className="text-white/80">Join us today</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-white font-medium mb-2">Full Name</label>
            <input
              name="name"
              placeholder="Enter your full name"
              className="w-full border-0 bg-white/20 text-white placeholder-white/60 p-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-white/50 backdrop-blur-sm"
              onChange={handleChange}
              required
            />
          </div>

          <div>
            <label className="block text-white font-medium mb-2">Email</label>
            <input
              name="email"
              type="email"
              placeholder="Enter your email"
              className="w-full border-0 bg-white/20 text-white placeholder-white/60 p-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-white/50 backdrop-blur-sm"
              onChange={handleChange}
              required
            />
          </div>

          <div>
            <label className="block text-white font-medium mb-2">Password</label>
            <input
              name="password"
              type="password"
              placeholder="Create a password"
              className="w-full border-0 bg-white/20 text-white placeholder-white/60 p-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-white/50 backdrop-blur-sm"
              onChange={handleChange}
              required
            />
          </div>

          <div>
            <label className="block text-white font-medium mb-2">Role</label>
            <select
              name="role"
              className="w-full border-0 bg-white/20 text-white p-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-white/50 backdrop-blur-sm"
              onChange={handleChange}
            >
              <option value="user" className="text-gray-800">User</option>
              <option value="admin" className="text-gray-800">Admin</option>
            </select>
          </div>

          <button 
            type="submit"
            disabled={loading}
            className="w-full bg-white/30 hover:bg-white/40 text-white font-semibold py-3 rounded-lg transition duration-300 shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed backdrop-blur-sm"
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

        <p className="text-white/80 text-center mt-6">
          Already have an account?{" "}
          <Link to="/login" className="text-white font-semibold hover:text-yellow-300 transition duration-300">
            Sign In
          </Link>
        </p>
      </div>
    </div>
  );
}
