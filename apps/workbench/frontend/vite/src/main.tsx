import React from "react";
import { createRoot } from "react-dom/client";

import { ResearchWorkspace } from "./app/ResearchWorkspace";
import { OperationsConsole } from "./operations/OperationsConsole";
import { ResearchSession } from "./app/ResearchSession";


function canonicalEntry(pathname: string): "/workspace" | "/operations" {
  if (pathname === "/operations" || pathname.startsWith("/operations/")) {
    return "/operations";
  }
  if (pathname === "/legacy" || pathname.startsWith("/legacy/")) {
    window.history.replaceState({}, "", "/operations");
    return "/operations";
  }
  if (
    pathname === "/"
    || pathname === "/current"
    || pathname.startsWith("/current/")
    || pathname === "/next"
    || pathname.startsWith("/next/")
    || pathname === "/tasks"
    || pathname === "/cases"
    || pathname.startsWith("/cases/")
  ) {
    window.history.replaceState({}, "", "/workspace");
  }
  return "/workspace";
}


const root = document.getElementById("root");
if (!root) throw new Error("workbench_root_missing");

const entry = canonicalEntry(window.location.pathname);
createRoot(root).render(
  <React.StrictMode>
    {window.location.pathname === "/workspace/session" ? <ResearchSession /> : entry === "/operations" ? (
      <OperationsConsole />
    ) : (
      <ResearchWorkspace />
    )}
  </React.StrictMode>,
);
