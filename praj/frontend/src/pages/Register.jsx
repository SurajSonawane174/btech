import React from 'react';
import { UserPlus, User, Mail, Lock, Shield } from 'lucide-react';

const Register = () => {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="w-full max-w-md animate-fade-in-up">
        
        <div className="relative group">
          {/* Glowing Background Effect */}
          <div className="absolute -inset-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 rounded-2xl blur opacity-25 group-hover:opacity-50 transition duration-1000"></div>
          
          <div className="relative bg-white/80 backdrop-blur-xl rounded-2xl p-8 shadow-2xl border border-white/50">
            
            <div className="text-center mb-8">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-indigo-100 text-indigo-600 mb-4 shadow-sm">
                <UserPlus className="w-6 h-6" />
              </div>
              <h2 className="text-2xl font-black text-gray-800 tracking-tight">Create Account</h2>
              <p className="text-gray-500 text-sm mt-1">Join BudgetBuddy today</p>
            </div>

            <form action="/register" method="POST" className="space-y-5">
              
              {/* Full Name Field */}
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-1.5 ml-1">
                  Full Name
                </label>
                <div className="relative group">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 group-focus-within:text-indigo-500 transition-colors" />
                  <input 
                    type="text" 
                    name="fullName" 
                    placeholder="John Doe" 
                    required 
                    className="w-full pl-10 pr-4 py-3 bg-gray-50/50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all outline-none" 
                  />
                </div>
              </div>

              {/* Email Address Field */}
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-1.5 ml-1">
                  Email Address
                </label>
                <div className="relative group">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 group-focus-within:text-indigo-500 transition-colors" />
                  <input 
                    type="email" 
                    name="email" 
                    placeholder="you@example.com" 
                    required 
                    className="w-full pl-10 pr-4 py-3 bg-gray-50/50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all outline-none" 
                  />
                </div>
              </div>

              {/* Role Field (New) */}
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-1.5 ml-1">
                  Account Role
                </label>
                <div className="relative group">
                  <Shield className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 group-focus-within:text-indigo-500 transition-colors" />
                  <select 
                    name="role" 
                    required 
                    className="w-full pl-10 pr-4 py-3 bg-gray-50/50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all outline-none appearance-none"
                  >
                    <option value="" disabled selected>Select a role...</option>
                    <option value="user">Regular User</option>
                    <option value="admin">Administrator</option>
                  </select>
                </div>
              </div>

              {/* Password Field */}
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-1.5 ml-1">
                  Password
                </label>
                <div className="relative group">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 group-focus-within:text-indigo-500 transition-colors" />
                  <input 
                    type="password" 
                    name="password" 
                    placeholder="••••••••" 
                    required 
                    className="w-full pl-10 pr-4 py-3 bg-gray-50/50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all outline-none" 
                  />
                </div>
              </div>

              <button 
                type="submit" 
                className="w-full py-3.5 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-bold rounded-xl shadow-lg transform transition hover:-translate-y-0.5"
              >
                Sign Up
              </button>

            </form>

            <div className="mt-6 text-center text-sm text-gray-500">
              Already have an account?{' '}
              <a href="/login" className="font-bold text-indigo-600 hover:text-indigo-800 hover:underline">
                Log in
              </a>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
};

export default Register;