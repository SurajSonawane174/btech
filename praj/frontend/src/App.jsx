import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

// Pages & Components
import Register from "./pages/Register";
import Login from "./pages/Login";
import Layout from "./pages/Layout";
import CreateCRS from "./pages/Crs";
import CommentExtractor from "./pages/CommentExtractor";
import Dashboard from "./pages/Dashboard"

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Wrap all routes inside Layout */}
        <Route path="/" element={<Layout />}>
          {/* Nested routes will render inside Layout */}
          {/* <Route index element={<Navigate to="/login" />} /> */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/project/crs" element={<CreateCRS />} />
          <Route path="/project/commentextract/upload" element={<CommentExtractor />} />
          <Route path="/dashboard" element={<Dashboard />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}