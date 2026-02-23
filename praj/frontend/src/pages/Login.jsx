import React from 'react';
import { LogIn, Mail, Lock } from 'lucide-react';

const Login = () => {
  return (
    <div className="min-h-[80vh] flex items-center justify-center">
      <div className="w-full max-w-md animate-fade-in-up">
        
        <div className="relative group">
          {/* Glowing Background Effect */}
          <div className="absolute -inset-1 bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 rounded-2xl blur opacity-25 group-hover:opacity-50 transition duration-1000"></div>
          
          <div className="relative bg-white/80 backdrop-blur-xl rounded-2xl p-8 shadow-2xl border border-white/50">
            
            <div className="text-center mb-8">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-emerald-100 text-emerald-600 mb-4 shadow-sm">
                <LogIn className="w-6 h-6" />
              </div>
              <h2 className="text-2xl font-black text-gray-800 tracking-tight">Welcome Back</h2>
              {/* <p className="text-gray-500 text-sm mt-1">Manage your finances with ease</p> */}
            </div>

            <form action="/login" method="POST" className="space-y-5">
              
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-1.5 ml-1">
                  Email Address
                </label>
                <div className="relative group">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 group-focus-within:text-emerald-500 transition-colors" />
                  <input 
                    type="email" 
                    name="email" 
                    placeholder="you@example.com" 
                    required 
                    className="w-full pl-10 pr-4 py-3 bg-gray-50/50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:bg-white transition-all outline-none" 
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between items-center mb-1.5 ml-1">
                    <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider">
                      Password
                    </label>
                    <a href="/forgot-password" className="text-xs text-emerald-600 hover:underline">
                      Forgot?
                    </a>
                </div>
                <div className="relative group">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 group-focus-within:text-emerald-500 transition-colors" />
                  <input 
                    type="password" 
                    name="password" 
                    placeholder="••••••••" 
                    required 
                    className="w-full pl-10 pr-4 py-3 bg-gray-50/50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:bg-white transition-all outline-none" 
                  />
                </div>
              </div>

              <button 
                type="submit" 
                className="w-full py-3.5 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 text-white font-bold rounded-xl shadow-lg transform transition hover:-translate-y-0.5"
              >
                Log In
              </button>

            </form>

            <div className="mt-6 text-center text-sm text-gray-500">
              New here?{' '}
              <a href="/register" className="font-bold text-emerald-600 hover:text-emerald-800 hover:underline">
                Create an account
              </a>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;