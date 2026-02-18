import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import PrivateRoute from "./auth/PrivateRoute";
import Register from "./pages/Register";

import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import UploadPage from "./pages/UploadPage";
import NotAuthorized from "./pages/NotAuthorized";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>

          {/* Default Route */}
          <Route path="/" element={<Navigate to="/login" />} />

          {/* Public Route */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />   
          {/* Protected Routes */}
          <Route
            path="/dashboard"
            element={
              <PrivateRoute roles={["admin", "user"]}>
                <Dashboard />
              </PrivateRoute>
            }
          />

          <Route
            path="/upload"
            element={
              <PrivateRoute roles={["admin"]}>
                <UploadPage />
              </PrivateRoute>
            }
          />

          {/* Unauthorized */}
          <Route path="/not-authorized" element={<NotAuthorized />} />

          {/* Catch All */}
          <Route path="*" element={<Navigate to="/login" />} />

        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
