export function backendOrigin() {
  return (process.env.FIND_YOU_API_ORIGIN || "http://127.0.0.1:8000").replace(/\/+$/, "");
}
