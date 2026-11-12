import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: {
    port: 5173,
    // The API runs as a separate process in development.
    proxy: { "/api": process.env.API_URL ?? "http://127.0.0.1:8000" },
  },
  test: { environment: "node" },
});
