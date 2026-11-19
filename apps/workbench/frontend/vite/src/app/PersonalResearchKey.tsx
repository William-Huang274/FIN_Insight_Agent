import { useState } from "react";
import type { ResearchConfiguration } from "../api/reportSessions";

export function PersonalResearchKey({ configuration, onChange }: {
  configuration: ResearchConfiguration;
  onChange: (configured: boolean) => void;
}) {
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!configuration.personal_keys_enabled) {
    return configuration.personal_key_required ? <p role="alert">请联系管理员启用个人模型密钥存储后启动研究。</p> : null;
  }

  async function update(remove: boolean) {
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/v1/personal-research-key", {
        method: remove ? "DELETE" : "PUT",
        credentials: "same-origin", redirect: "error", cache: "no-store",
        headers: { "X-Workbench-Request": "1", "Content-Type": "text/plain" },
        body: remove ? undefined : key,
      });
      if (!response.ok) throw Error("无法更新个人模型密钥。请检查登录状态和密钥格式。");
      onChange(!remove);
    } catch {
      setError("无法更新个人模型密钥。请检查登录状态和密钥格式。");
    } finally {
      setKey("");
      setBusy(false);
    }
  }

  return <fieldset className="fs-execution-picker" disabled={busy}><legend>个人模型密钥</legend>
    <p>推荐使用自己的 DeepSeek 官方 API Key。模型费用计入该密钥的账户。</p>
    <label>DeepSeek API Key <input type="password" autoComplete="off" spellCheck={false} value={key}
      maxLength={512} onChange={event => setKey(event.target.value)} /></label>
    <button type="button" disabled={!key} onClick={() => update(false)}>保存密钥</button>
    {configuration.personal_key_configured && <><span role="status">已配置个人密钥</span>
      <button type="button" onClick={() => update(true)}>移除密钥</button></>}
    {error && <p role="alert">{error}</p>}
  </fieldset>;
}
