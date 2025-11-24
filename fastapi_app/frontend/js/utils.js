export function getHeaders() {
  const token = localStorage.getItem("token");
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export function checkAdmin() {
  const role = localStorage.getItem("role");
  if (role !== "admin") location.href = "../dashboard.html";
}
