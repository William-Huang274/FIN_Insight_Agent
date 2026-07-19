import { AlertTriangle, LoaderCircle, RefreshCcw, ShieldAlert, WifiOff } from "lucide-react";
import { useWorkbenchLocale } from "../i18n/WorkbenchLocale";

export type RemoteStatusKind = "loading" | "empty" | "error" | "permission" | "stale" | "conflict" | "reconnecting";

type RemoteStatusProps = {
  kind: RemoteStatusKind;
  message?: string;
  onRetry?: () => void;
};

export function RemoteStatus({ kind, message, onRetry }: RemoteStatusProps) {
  const { copy } = useWorkbenchLocale();
  const statusCopy: Record<RemoteStatusKind, string> = {
    loading: copy("正在加载研究数据。", "Loading research data."),
    empty: copy("当前工作区还没有研究任务。", "No research cases are available for this workspace."),
    error: copy("研究数据暂时无法加载。", "Research data could not be loaded."),
    permission: copy("当前工作区无权访问这项研究。", "This workspace does not grant access to the requested research case."),
    stale: copy("这项研究已有更新版本，请重新打开最新版本。", "This research case has a newer version. Reopen the latest version."),
    conflict: copy("刷新期间研究内容发生了变化，请重新载入。", "The research case changed while this view was refreshing."),
    reconnecting: copy("连接暂时中断，恢复后将自动刷新。", "Connection is unavailable. The view will refresh after reconnection."),
  };
  const Icon = iconFor(kind);
  return (
    <section className={`p02-remote-status p02-remote-status--${kind}`} aria-live="polite">
      <Icon aria-hidden="true" size={18} className={kind === "loading" ? "p02-spin" : undefined} />
      <div>
        <p>{message ?? statusCopy[kind]}</p>
      </div>
      {onRetry ? (
        <button type="button" className="p02-icon-button" title={copy("重试", "Retry")} aria-label={copy("重试", "Retry")} onClick={onRetry}>
          <RefreshCcw size={16} aria-hidden="true" />
        </button>
      ) : null}
    </section>
  );
}

function iconFor(kind: RemoteStatusKind) {
  if (kind === "loading") return LoaderCircle;
  if (kind === "permission") return ShieldAlert;
  if (kind === "reconnecting") return WifiOff;
  return AlertTriangle;
}
