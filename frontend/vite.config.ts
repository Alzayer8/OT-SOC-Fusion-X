import react from "@vitejs/plugin-react";
import { configDefaults, defineConfig } from "vitest/config";

export default defineConfig({
  cacheDir: process.env.VITE_CACHE_DIR ?? "node_modules/.vite",
  plugins: [react()],
  server: {
    allowedHosts: ["frontend", "localhost", "127.0.0.1"],
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_PROXY_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: false,
      },
      "/health": {
        target: process.env.VITE_PROXY_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: false,
      },
    },
  },
  preview: {
    host: "127.0.0.1",
    port: 4173,
  },
  test: {
    environment: "jsdom",
    exclude: [...configDefaults.exclude, "tests/**"],
    setupFiles: ["./src/test/setup.ts"],
    coverage: {
      reporter: ["text", "html"],
    },
  },
});
