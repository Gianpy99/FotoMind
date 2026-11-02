import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createClient } from "@fotomind/api-client";
import { AppShell } from "@fotomind/ui";
import "@fotomind/ui/styles.css";

// Local API by default. Pointing the desktop shell at the Pi through the portal needs the
// auth/CORS spike described in docs/adr/0003-desktop-and-web-clients.md.
const apiUrl = import.meta.env.VITE_FOTOMIND_API_URL ?? "http://127.0.0.1:8000";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppShell client={createClient(apiUrl)} surface="desktop" />
  </StrictMode>,
);
