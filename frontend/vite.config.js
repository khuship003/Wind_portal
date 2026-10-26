import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: proxy /api to the Flask backend. Prod: same-origin (nginx / Vercel rewrites).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": process.env.API_URL || "http://localhost:8000" },
  },
});
