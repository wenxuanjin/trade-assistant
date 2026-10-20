const configured = import.meta.env.VITE_API_BASE_URL?.trim()

/** Python Agent 地址。可用 VITE_API_BASE_URL 覆盖。 */
export const API_BASE_URL = (configured || "http://127.0.0.1:8000").replace(/\/$/, "")
