import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// The live Rust API (cross-origin in production; proxied in dev to keep cookies first-party).
const API_TARGET = "https://e1tyj5meuc.execute-api.us-east-1.amazonaws.com";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  // Relative asset URLs so the built app works from the /admin/ subfolder on S3/CloudFront.
  base: "./",
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  build: {
    // Emit the built SPA into the deployed static site as /admin.
    outDir: fileURLToPath(new URL("../admin", import.meta.url)),
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    port: 5174,
    // In dev, proxy /api to the live backend and rewrite the auth cookie to localhost
    // so login works first-party without cross-site cookie restrictions.
    proxy: {
      "/api": {
        target: API_TARGET,
        changeOrigin: true,
        secure: true,
        cookieDomainRewrite: "localhost",
        // Strip Secure so the http://localhost dev server can store the cookie.
        cookiePathRewrite: "/",
        configure: (proxy) => {
          proxy.on("proxyRes", (proxyRes) => {
            const sc = proxyRes.headers["set-cookie"];
            if (Array.isArray(sc)) {
              proxyRes.headers["set-cookie"] = sc.map((c) =>
                c.replace(/;\s*Secure/gi, "").replace(/;\s*SameSite=None/gi, "; SameSite=Lax")
              );
            }
          });
        },
      },
    },
  },
});
