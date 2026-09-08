import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendPort = Number(process.env.FINSIGHT_E2E_BACKEND_PORT || "8765");
if (!Number.isInteger(backendPort) || backendPort < 1024 || backendPort > 65535) {
  throw new Error("FINSIGHT_E2E_BACKEND_PORT must be an integer from 1024 to 65535");
}

export default defineConfig({
  root: "vite",
  plugins: [react()],
  build: {
    outDir: "../dist",
    emptyOutDir: true,
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": `http://127.0.0.1:${backendPort}`,
    },
  },
});
