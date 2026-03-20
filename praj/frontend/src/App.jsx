import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import PrivateRoute from "./auth/PrivateRoute";

// --- PAGES ---
import Register from "./pages/Register";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import UploadPage from "./pages/UploadPage";
import NotAuthorized from "./pages/NotAuthorized";
import Comments from "./pages/Comments";
import GetCrs from "./pages/CRSLookup";
import Reports from "./pages/Reports"; 
import Notifications from "./pages/Notifications";
import CRSReview from "./pages/CRSReview";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Default Route */}
          <Route path="/" element={<Navigate to="/login" />} />

          {/* Public Routes */}
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
              <PrivateRoute roles={["admin", "user"]}>
                <UploadPage />
              </PrivateRoute>
            }
          />

          <Route
            path="/comments"
            element={
              <PrivateRoute roles={["admin"]}>
                <Comments />
              </PrivateRoute>
            }
          />
          <Route path="/crs-review/:drawingNo" element={<PrivateRoute roles={["admin", "user"]}><CRSReview /></PrivateRoute>} />
          <Route
            path="/get-crs"
            element={
              <PrivateRoute roles={["admin", "user"]}>
                <GetCrs />
              </PrivateRoute>
            }
          />
          
          <Route 
            path="/notifications" 
            element={
              <PrivateRoute roles={["admin", "user"]}>
                <Notifications />
              </PrivateRoute>
            } 
          />
          
          <Route 
            path="/review" 
            element={
              <PrivateRoute roles={["admin", "user"]}>
                <CRSReview />
              </PrivateRoute>
            } 
          />

          <Route
            path="/reports"
            element={
              <PrivateRoute roles={["admin", "user"]}>
                <Reports />
              </PrivateRoute>
            }
          />

          <Route
            path="/settings"
            element={
              <PrivateRoute roles={["admin", "user"]}>
                <Settings />
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