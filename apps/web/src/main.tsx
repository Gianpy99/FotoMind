import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createClient } from "@fotomind/api-client";
import { AppShell } from "@fotomind/ui";
import "@fotomind/ui/styles.css";

// Same origin as the API (served by FastAPI behind the Family Portal).
const client = createClient("");

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppShell client={client} surface="web" />
  </StrictMode>,
);
