import React from "react";
import { createRoot } from "react-dom/client";

import { BrowserRouter } from "react-router";
import { OperationsConsole } from "./operations/OperationsConsole";
import { ResearchSession } from "./app/ResearchSession";
import { IdentityBoundary } from './app/IdentityBoundary';
const ConversationWorkspace = React.lazy(() => import("./app/ConversationWorkspace"));
const AssetWorkspace = React.lazy(() => import("./app/AssetWorkspace"));
const ProjectWorkspace = React.lazy(() => import("./app/ProjectWorkspace"));
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

// Preserve old links while making the asset workspace the canonical data surface.
const oldView=new URLSearchParams(window.location.search).get('view');
if(['/workspace','/workspace/session'].includes(window.location.pathname)&&['library','financial-data'].includes(oldView||'')){
  window.history.replaceState({},'',`/workspace/assets?view=${oldView}`);
}
const entry = canonicalEntry(window.location.pathname);
if(window.location.pathname==='/workspace'&&!window.location.search){
  window.history.replaceState({},'','/workspace/projects');
}
createRoot(root).render(
  <React.StrictMode>
    <IdentityBoundary>
    {entry === "/operations" ? (
      <OperationsConsole />
    ) : window.location.pathname === "/workspace/evidence-packs" ? (
      <React.Suspense fallback={<p role="status">正在读取历史证据工作台…</p>}><EvidencePackWorkspace /></React.Suspense>
    ) : window.location.pathname === "/workspace/projects" ? (
      <BrowserRouter><React.Suspense fallback={<p role="status">正在打开项目…</p>}><ProjectWorkspace /></React.Suspense></BrowserRouter>
    ) : window.location.pathname === "/workspace/assets" ? (
      <BrowserRouter><React.Suspense fallback={<p role="status">正在打开资产工作区…</p>}><AssetWorkspace /></React.Suspense></BrowserRouter>
    ) : window.location.pathname === "/workspace/assistant" ? (
      <BrowserRouter><React.Suspense fallback={<p role="status">正在打开对话…</p>}><ConversationWorkspace /></React.Suspense></BrowserRouter>
    ) : (
      <BrowserRouter><ResearchSession /></BrowserRouter>
    )}
    </IdentityBoundary>
  </React.StrictMode>,
);
