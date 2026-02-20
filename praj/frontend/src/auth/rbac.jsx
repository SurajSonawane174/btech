export const hasRole = (user, allowedRoles) => {
  if (!user) return false;
  return allowedRoles.includes(user.role);
};