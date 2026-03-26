import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8080",
  withCredentials: true, // This is all you need — sends the session cookie
});

// REMOVED the interceptor that added Bearer token
// Your backend uses Passport sessions, not JWT. The withCredentials above
// sends the session cookie automatically on every request.

export default api;
