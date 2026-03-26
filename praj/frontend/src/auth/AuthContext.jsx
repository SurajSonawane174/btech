import { createContext, useContext, useState } from "react";
import { jwtDecode } from "jwt-decode";

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    const token = localStorage.getItem("token");
    const storedUser = localStorage.getItem("user");
    
    if (storedUser) {
      try {
        return JSON.parse(storedUser);
      } catch (error) {
        return null;
      }
    }
    
    if (!token) return null;
    
    try {
      return jwtDecode(token);
    } catch (error) {
      return null;
    }
  });

  const login = (data) => {
    // Handle both token and user object data
    if (typeof data === 'string') {
      // It's a token
      localStorage.setItem("token", data);
      try {
        setUser(jwtDecode(data));
      } catch (error) {
        setUser({ role: "admin", name: "User" });
      }
    } else if (typeof data === 'object') {
      // It's user data from session
      localStorage.setItem("user", JSON.stringify(data));
      localStorage.setItem("token", data.id); // Store user id as token placeholder
      setUser(data);
    }
  };

  const logout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);