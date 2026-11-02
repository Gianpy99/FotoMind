import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Production: the built files are served by the FastAPI container from "/" (same origin).
// Development: proxy API calls to the local backend (npm run dev:web + fotomind-api).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
    },
  },
});
