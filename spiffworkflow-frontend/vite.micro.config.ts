// vite.config.ts for a Vite + React project
import { defineConfig } from 'vite';
import react from "@vitejs/plugin-react";
import vitePluginSingleSpa from "vite-plugin-single-spa";
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    vitePluginSingleSpa({
      serverPort: 4101,
      spaEntryPoints: "src/spa.tsx",
    }),
  ],
  build: {
    rollupOptions: {
      output: {
        format: 'amd', // Use AMD module format
      }
    }
  },
  // To load assets from the micro frontend, we need to configure the base path
  // currently configured to the http-server path of local
  experimental: {
    renderBuiltUrl(filename, { hostId, hostType, type }) {
      if (type === 'public') {
        return 'http://172.31.80.1:8080/' + filename;
      } else if (path.extname(hostId) !== '.js') {
        return 'http://172.31.80.1:8080/' + filename;
      } else {
        return 'http://172.31.80.1:8080/' + filename;
      }
    }
  }
});