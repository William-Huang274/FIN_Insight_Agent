import React from "react";
import { createRoot } from "react-dom/client";

import { BrowserRouter } from "react-router";
import { OperationsConsole } from "./operations/OperationsConsole";
import { ResearchSession } from "./app/ResearchSession";
const EvidencePackWorkspace = React.lazy(() => import("./app/ResearchWorkspace")
  .then(module => ({ default: module.ResearchWorkspace })));


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
    {entry === "/operations" ? (
      <OperationsConsole />
    ) : window.location.pathname === "/workspace/evidence-packs" ? (
      <React.Suspense fallback={<p role="status">正在读取历史证据工作台…</p>}><EvidencePackWorkspace /></React.Suspense>
    ) : (
      <BrowserRouter><ResearchSession /></BrowserRouter>
    )}
  </React.StrictMode>,
);
