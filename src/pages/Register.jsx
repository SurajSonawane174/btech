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
    <div className="min-h-screen flex items-center justify-center bg-white px-4">
      <div className="w-full max-w-md rounded-2xl p-8 border border-gray-100 shadow-lg bg-white/80 backdrop-blur-sm">
        <div className="text-center mb-6">
          <h2 className="text-3xl font-bold text-gray-800 mb-1">Create Account</h2>
          <p className="text-gray-600">Join us today</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-gray-700 font-medium mb-2">Full Name</label>
            <input
              name="name"
              placeholder="Enter your full name"
              className="w-full border border-gray-200 bg-white text-gray-800 placeholder-gray-400 p-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-200"
              onChange={handleChange}
              required
            />
          </div>

          <div>
            <label className="block text-gray-700 font-medium mb-2">Email</label>
            <input
              name="email"
              type="email"
              placeholder="Enter your email"
              className="w-full border border-gray-200 bg-white text-gray-800 placeholder-gray-400 p-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-200"
              onChange={handleChange}
              required
            />
          </div>

          <div>
            <label className="block text-gray-700 font-medium mb-2">Password</label>
            <input
              name="password"
              type="password"
              placeholder="Create a password"
              className="w-full border border-gray-200 bg-white text-gray-800 placeholder-gray-400 p-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-200"
              onChange={handleChange}
              required
            />
          </div>

          <div>
            <label className="block text-gray-700 font-medium mb-2">Role</label>
            <select
              name="role"
              className="w-full border border-gray-200 bg-white text-gray-800 p-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-200"
              onChange={handleChange}
            >
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
          </div>

          <button 
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-lg transition duration-200 shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
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

        <p className="text-gray-600 text-center mt-6">
          Already have an account?{" "}
          <Link to="/login" className="text-blue-600 font-semibold hover:text-blue-800 transition duration-200">
            Sign In
          </Link>
        </p>
      </div>
    </div>
  );
}
