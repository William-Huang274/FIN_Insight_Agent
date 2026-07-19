import { ReactNode, useCallback, useEffect, useState } from "react";

import {
  AnalystTopbar,
  CaseContextDrawer,
  CaseRouteKind,
  CompactCaseTabs,
  GlobalProductNav,
  TaskQueueRail,
} from "./AnalystWorkspaceChrome";
import { ActivityTrace } from "../features/activity-trace/ActivityTrace";
import { CaseOverview } from "../features/case-overview/CaseOverview";
import { DecisionSurface } from "../features/decision-surface/DecisionSurface";
import { DeliverableReview } from "../features/deliverable-review/DeliverableReview";
import { EvidenceWorkbench } from "../features/evidence-workbench/EvidenceWorkbench";
import { HumanBaseline } from "../features/human-baseline/HumanBaseline";
import { NumericWorkbench } from "../features/numeric-workbench/NumericWorkbench";
import { NewCase, TaskCenter } from "../features/task-center/TaskCenter";
import { WorkpaperReview } from "../features/workpaper-review/WorkpaperReview";
import { WorkbenchLocaleProvider } from "../i18n/WorkbenchLocale";
import { isWorkbenchNextPath, WorkbenchNext } from "./WorkbenchNext";
import "./p02-shell.css";

type AppShellProps = {
  legacyApp: ReactNode;
};

type Route =
  | { kind: "tasks" }
  | { kind: "newCase" }
  | { kind: "caseOverview"; caseId: string }
  | { kind: "decisionSurface"; caseId: string }
  | { kind: "evidence"; caseId: string }
  | { kind: "numbers"; caseId: string }
  | { kind: "workpaper"; caseId: string }
  | { kind: "deliverable"; caseId: string }
  | { kind: "activity"; caseId: string }
  | { kind: "humanBaseline"; caseId: string }
  | { kind: "legacy" };

export function AppShell({ legacyApp }: AppShellProps) {
  return (
    <WorkbenchLocaleProvider>
      <LocalizedAppShell legacyApp={legacyApp} />
    </WorkbenchLocaleProvider>
  );
}

function LocalizedAppShell({ legacyApp }: AppShellProps) {
  const [route, navigate] = useBrowserRoute();
  const online = useOnlineStatus();
  const activeCaseId = caseIdForRoute(route);
  const [recentCaseId, setRecentCaseId] = useState<string | null>(null);

  if (isWorkbenchNextPath(window.location.pathname)) return <WorkbenchNext online={online} />;
  if (route.kind === "legacy") return <>{legacyApp}</>;

  const rememberCase = (caseId: string) => {
    setRecentCaseId(caseId);
  };
  const openCase = (caseId: string) => {
    rememberCase(caseId);
    navigate({ kind: "caseOverview", caseId });
  };
  const navigateCaseTab = (kind: CaseRouteKind) => {
    const caseId = activeCaseId ?? recentCaseId;
    if (caseId) {
      rememberCase(caseId);
      navigate({ kind, caseId });
    }
  };

  return (
    <div className="p02-app-shell">
      <AnalystTopbar online={online} onTasks={() => navigate({ kind: "tasks" })} onOpenCase={openCase} />
      <div className={`analyst-workspace-shell ${activeCaseId ? "has-case" : ""}`}>
        <GlobalProductNav
          active={route.kind === "tasks" ? "tasks" : route.kind === "newCase" ? "newCase" : "case"}
          activeCaseKind={activeCaseId ? route.kind as CaseRouteKind : null}
          caseAvailable={Boolean(activeCaseId ?? recentCaseId)}
          onTasks={() => navigate({ kind: "tasks" })}
          onNewCase={() => navigate({ kind: "newCase" })}
          onNavigateCase={navigateCaseTab}
          onLegacy={() => navigate({ kind: "legacy" })}
        />
        {activeCaseId ? <TaskQueueRail activeCaseId={activeCaseId} onOpenCase={openCase} /> : null}
        <section className="analyst-main-workspace">
          {activeCaseId ? <CompactCaseTabs activeKind={route.kind as CaseRouteKind} onNavigate={navigateCaseTab} /> : null}
          <main className="p02-content analyst-page-content">
        {route.kind === "tasks" ? (
          <TaskCenter
            online={online}
            onNewCase={() => navigate({ kind: "newCase" })}
            onOpenCase={openCase}
          />
        ) : null}
        {route.kind === "newCase" ? (
          <NewCase
            online={online}
            onBack={() => navigate({ kind: "tasks" })}
            onCreated={(caseId) => navigate({ kind: "caseOverview", caseId })}
          />
        ) : null}
        {route.kind === "caseOverview" ? (
          <CaseOverview
            caseId={route.caseId}
            online={online}
            onBack={() => navigate({ kind: "tasks" })}
            onOpenDecisionSurface={() => navigate({ kind: "decisionSurface", caseId: route.caseId })}
            onOpenEvidence={() => navigate({ kind: "evidence", caseId: route.caseId })}
            onOpenActivity={() => navigate({ kind: "activity", caseId: route.caseId })}
          />
        ) : null}
        {route.kind === "decisionSurface" ? (
          <DecisionSurface
            caseId={route.caseId}
            online={online}
            onBack={() => navigate({ kind: "caseOverview", caseId: route.caseId })}
          />
        ) : null}
        {route.kind === "activity" ? (
          <ActivityTrace
            caseId={route.caseId}
            online={online}
            onBack={() => navigate({ kind: "caseOverview", caseId: route.caseId })}
            onExitCase={() => navigate({ kind: "tasks" })}
            onOpenDecisionSurface={() => navigate({ kind: "decisionSurface", caseId: route.caseId })}
            onOpenEvidence={() => navigate({ kind: "evidence", caseId: route.caseId })}
          />
        ) : null}
        {route.kind === "evidence" ? (
          <EvidenceWorkbench
            caseId={route.caseId}
            online={online}
            onBack={() => navigate({ kind: "caseOverview", caseId: route.caseId })}
            onOpenActivity={() => navigate({ kind: "activity", caseId: route.caseId })}
            onOpenNumeric={() => navigate({ kind: "numbers", caseId: route.caseId })}
          />
        ) : null}
        {route.kind === "numbers" ? (
          <NumericWorkbench
            caseId={route.caseId}
            online={online}
            onOpenEvidence={() => navigate({ kind: "evidence", caseId: route.caseId })}
            onOpenWorkpaper={() => navigate({ kind: "workpaper", caseId: route.caseId })}
          />
        ) : null}
        {route.kind === "workpaper" ? (
          <WorkpaperReview
            caseId={route.caseId}
            online={online}
            onOpenEvidence={() => navigate({ kind: "evidence", caseId: route.caseId })}
            onOpenNumeric={() => navigate({ kind: "numbers", caseId: route.caseId })}
          />
        ) : null}
        {route.kind === "deliverable" ? (
          <DeliverableReview
            caseId={route.caseId}
            online={online}
            onOpenWorkpaper={() => navigate({ kind: "workpaper", caseId: route.caseId })}
          />
        ) : null}
        {route.kind === "humanBaseline" ? (
          <HumanBaseline
            caseId={route.caseId}
            online={online}
            onOpenEvidence={() => navigate({ kind: "evidence", caseId: route.caseId })}
            onOpenNumeric={() => navigate({ kind: "numbers", caseId: route.caseId })}
            onOpenWorkpaper={() => navigate({ kind: "workpaper", caseId: route.caseId })}
            onOpenDeliverable={() => navigate({ kind: "deliverable", caseId: route.caseId })}
          />
        ) : null}
          </main>
        </section>
        {activeCaseId ? <CaseContextDrawer caseId={activeCaseId} /> : null}
      </div>
    </div>
  );
}

function useBrowserRoute(): [Route, (route: Route) => void] {
  const routeForPath = useCallback(() => decodeRoute(window.location.pathname), []);
  const [route, setRoute] = useState<Route>(routeForPath);

  useEffect(() => {
    const onPopState = () => setRoute(routeForPath());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [routeForPath]);

  const navigate = useCallback((next: Route) => {
    window.history.pushState({}, "", pathForRoute(next));
    setRoute(next);
  }, []);
  return [route, navigate];
}

function useOnlineStatus(): boolean {
  const [online, setOnline] = useState(() => navigator.onLine);
  useEffect(() => {
    const connect = () => setOnline(true);
    const disconnect = () => setOnline(false);
    window.addEventListener("online", connect);
    window.addEventListener("offline", disconnect);
    return () => {
      window.removeEventListener("online", connect);
      window.removeEventListener("offline", disconnect);
    };
  }, []);
  return online;
}

function decodeRoute(pathname: string): Route {
  if (pathname === "/legacy") return { kind: "legacy" };
  if (pathname === "/cases/new") return { kind: "newCase" };
  const activityMatch = /^\/cases\/([^/]+)\/activity\/?$/.exec(pathname);
  if (activityMatch) return { kind: "activity", caseId: decodeURIComponent(activityMatch[1]) };
  const evidenceMatch = /^\/cases\/([^/]+)\/evidence\/?$/.exec(pathname);
  if (evidenceMatch) return { kind: "evidence", caseId: decodeURIComponent(evidenceMatch[1]) };
  const numbersMatch = /^\/cases\/([^/]+)\/numbers\/?$/.exec(pathname);
  if (numbersMatch) return { kind: "numbers", caseId: decodeURIComponent(numbersMatch[1]) };
  const workpaperMatch = /^\/cases\/([^/]+)\/workpaper\/?$/.exec(pathname);
  if (workpaperMatch) return { kind: "workpaper", caseId: decodeURIComponent(workpaperMatch[1]) };
  const deliverableMatch = /^\/cases\/([^/]+)\/deliverable\/?$/.exec(pathname);
  if (deliverableMatch) return { kind: "deliverable", caseId: decodeURIComponent(deliverableMatch[1]) };
  const baselineMatch = /^\/cases\/([^/]+)\/baseline\/?$/.exec(pathname);
  if (baselineMatch) return { kind: "humanBaseline", caseId: decodeURIComponent(baselineMatch[1]) };
  const decisionSurfaceMatch = /^\/cases\/([^/]+)\/decision-surface\/?$/.exec(pathname);
  if (decisionSurfaceMatch) return { kind: "decisionSurface", caseId: decodeURIComponent(decisionSurfaceMatch[1]) };
  const caseMatch = /^\/cases\/([^/]+)(?:\/overview)?\/?$/.exec(pathname);
  if (caseMatch) return { kind: "caseOverview", caseId: decodeURIComponent(caseMatch[1]) };
  return { kind: "tasks" };
}

function pathForRoute(route: Route): string {
  if (route.kind === "newCase") return "/cases/new";
  if (route.kind === "caseOverview") return `/cases/${encodeURIComponent(route.caseId)}/overview`;
  if (route.kind === "decisionSurface") return `/cases/${encodeURIComponent(route.caseId)}/decision-surface`;
  if (route.kind === "activity") return `/cases/${encodeURIComponent(route.caseId)}/activity`;
  if (route.kind === "evidence") return `/cases/${encodeURIComponent(route.caseId)}/evidence`;
  if (route.kind === "numbers") return `/cases/${encodeURIComponent(route.caseId)}/numbers`;
  if (route.kind === "workpaper") return `/cases/${encodeURIComponent(route.caseId)}/workpaper`;
  if (route.kind === "deliverable") return `/cases/${encodeURIComponent(route.caseId)}/deliverable`;
  if (route.kind === "humanBaseline") return `/cases/${encodeURIComponent(route.caseId)}/baseline`;
  if (route.kind === "legacy") return "/legacy";
  return "/tasks";
}

function caseIdForRoute(route: Route): string | null {
  return "caseId" in route ? route.caseId : null;
}
