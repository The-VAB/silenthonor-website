import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ApiError } from "@/lib/api";
import { ToastProvider } from "@/components/toast";
import App from "@/App";
import "@/styles/tokens.css";
import "@/styles/app.css";
import "@/styles/components.css";
import "@/styles/builder.css";
import "@/styles/assistant.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Don't hammer the API on auth failures; surface them instead.
      retry: (count, err) => !(err instanceof ApiError && (err.status === 401 || err.status === 403)) && count < 2,
      refetchOnWindowFocus: false,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <App />
      </ToastProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
