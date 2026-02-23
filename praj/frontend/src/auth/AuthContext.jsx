import { createContext, useContext, useState } from "react";
import { jwtDecode } from "jwt-decode";

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    const token = localStorage.getItem("token");
    if (!token) return null;
    
    try {
      // Try to decode a real token
      return jwtDecode(token);
    } catch (error) {
      // If it fails (e.g., our mock token), log a warning and return a mock user
      console.warn("Invalid token found, using mock user for bypass.");
      return { role: "admin", name: "Test User" }; 
    }
  });

  const login = (token) => {
    localStorage.setItem("token", token);
    try {
      setUser(jwtDecode(token));
    } catch (error) {
      // Set a mock user so your dashboard has some data to work with
      setUser({ role: "admin", name: "Test User" });
    }
  };

  const logout = () => {
    localStorage.removeItem("token");
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);