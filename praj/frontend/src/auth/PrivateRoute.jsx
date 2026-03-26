// import { Navigate } from "react-router-dom";
// import { useAuth } from "./AuthContext";
// import { hasRole } from "./rbac";

// const PrivateRoute = ({ children, roles }) => {
//   const { user } = useAuth();

//   if (!user) return <Navigate to="/login" />;

//   if (roles && !hasRole(user, roles)) {
//     return <Navigate to="/not-authorized" />;
//   }

//   return children;
// };

// export default PrivateRoute;


export default function PrivateRoute({ children }) {
  return children;
}
