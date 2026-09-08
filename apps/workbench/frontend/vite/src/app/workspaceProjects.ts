import { useState } from "react";

export type ProjectIndex = { projects: { id: string; name: string }[]; assignments: Record<string, string>; pinned: string[] };
const key = "finsight.project-index.v1";
const empty: ProjectIndex = { projects: [], assignments: {}, pinned: [] };
export function useWorkspaceProjects() {
  const [index, setIndex] = useState<ProjectIndex>(() => {
    try { const value = JSON.parse(localStorage.getItem(key) || "null"); return value && Array.isArray(value.projects) && value.assignments && Array.isArray(value.pinned) ? value : empty; } catch { return empty; }
  });
  const [error, setError] = useState("");
  const update = (next: ProjectIndex) => {
    try { localStorage.setItem(key, JSON.stringify(next)); setIndex(next); setError(""); } catch { setError("浏览器无法保存项目整理，请检查本地存储空间或权限。"); }
  };
  return { index, error, update };
}
