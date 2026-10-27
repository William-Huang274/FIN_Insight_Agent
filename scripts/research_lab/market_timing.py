"""Independent public-data experiment. No FIN runtime, provider API, or broker."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import html
import io
import json
from pathlib import Path
import platform
import re
import sys
import time
import traceback
import urllib.request
import zipfile

import numpy as np


def digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def month_number(month: str) -> int:
    return int(month[:4]) * 12 + int(month[4:]) - 1


def parse_french(blob: bytes) -> tuple[np.ndarray, np.ndarray]:
    """Read only monthly rows, excluding annual footer. Reject ambiguous input."""
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        if len(names) != 1:
            raise ValueError("Expected exactly one CSV in source archive")
        text = archive.read(names[0]).decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    headers = []
    for i, row in enumerate(rows):
        if [s.strip() for s in row] != ["", "Mkt-RF", "SMB", "HML", "RF"]:
            continue
        following = next((r for r in rows[i + 1:] if r and any(s.strip() for s in r)), [])
        if following and re.fullmatch(r"\d{6}", following[0].strip()):
            headers.append(i)
    if len(headers) != 1:
        raise ValueError("Missing/ambiguous monthly factor header")
    dates, values = [], []
    for row in rows[headers[0] + 1:]:
        if not row or not re.fullmatch(r"\d{6}", row[0].strip()):
            if dates:
                break
            continue
        if len(row) != 5:
            raise ValueError("Unexpected monthly row width")
        date = row[0].strip()
        if not 1 <= int(date[4:]) <= 12:
            raise ValueError("Invalid calendar month")
        data = np.array([float(x) for x in row[1:]])
        if not np.isfinite(data).all() or np.isin(data, [-99.99, -999]).any():
            raise ValueError("Missing/nonfinite source return")
        dates.append(date)
        values.append(data / 100.0)
    if not dates or any(month_number(b) - month_number(a) != 1 for a, b in zip(dates, dates[1:])):
        raise ValueError("Monthly dates must be unique and contiguous")
    return np.array(dates), np.array(values)


def feature_matrix(dates: np.ndarray, data: np.ndarray, lag: int = 2):
    if lag < 2:
        raise ValueError("This experiment requires a full intervening month")
    out_dates, ends, features, targets, rf = [], [], [], [], []
    for i in range(11 + lag, len(dates)):
        j = i - lag
        history = data[j - 11:j + 1, 0]
        features.append([history[-1], np.prod(1 + history[-3:]) - 1,
                         np.prod(1 + history) - 1, np.std(history, ddof=1)])
        out_dates.append(dates[i]); ends.append(dates[j])
        targets.append(data[i, 0]); rf.append(data[i, 3])
    return np.array(out_dates), np.array(ends), np.array(features), np.array(targets), np.array(rf)


def fit_ridge(x: np.ndarray, y: np.ndarray, alpha: float):
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale = np.where(scale > 1e-12, scale, 1.0)
    z = (x - mean) / scale
    intercept = float(y.mean())
    coef = np.linalg.solve(z.T @ z + alpha * np.eye(x.shape[1]), z.T @ (y - intercept))
    return {"mean": mean.tolist(), "scale": scale.tolist(), "coef": coef.tolist(), "intercept": intercept}


def predict(model: dict, x: np.ndarray):
    return (x - np.array(model["mean"])) / np.array(model["scale"]) @ np.array(model["coef"]) + model["intercept"]


def simulate(weights: np.ndarray, excess: np.ndarray, rf: np.ndarray, cost_bps: float):
    if not (len(weights) == len(excess) == len(rf)):
        raise ValueError("Portfolio series lengths differ")
    if not np.isfinite(np.r_[weights, excess, rf]).all() or np.any((weights < 0) | (weights > 1)):
        raise ValueError("Nonfinite or unsupported position")
    returns, turnover = [], []
    drifted = 0.0
    for w, ex, cash in zip(weights, excess, rf):
        trade = abs(w - drifted)
        fee = trade * cost_bps / 10000
        gross = cash + w * ex
        if fee >= 1 or gross <= -1:
            raise ValueError("Insolvent simulation")
        returns.append((1 - fee) * (1 + gross) - 1)
        turnover.append(trade)
        drifted = w * (1 + cash + ex) / (1 + gross)
    return np.array(returns), np.array(turnover)


def metrics(returns: np.ndarray, rf: np.ndarray, turnover: np.ndarray, weights: np.ndarray):
    excess = returns - rf
    nav = np.r_[1.0, np.cumprod(1 + returns)]
    std = float(np.std(excess, ddof=1))
    return {"months": len(returns), "annualized_return": float(nav[-1] ** (12 / len(returns)) - 1),
            "annualized_volatility": float(np.std(returns, ddof=1) * np.sqrt(12)),
            "excess_sharpe": float(np.mean(excess) / std * np.sqrt(12)) if std > 1e-12 else None,
            "max_drawdown": float(np.min(nav / np.maximum.accumulate(nav) - 1)),
            "annualized_turnover": float(np.mean(turnover) * 12), "mean_market_weight": float(np.mean(weights))}


def block_interval(difference: np.ndarray):
    rng = np.random.default_rng(17)
    n, block = len(difference), 12
    samples = []
    for _ in range(1000):
        starts = rng.integers(0, n - block + 1, size=(n + block - 1) // block)
        draw = np.concatenate([difference[s:s + block] for s in starts])[:n]
        samples.append(float(draw.mean() * 12))
    return np.quantile(samples, [0.025, 0.975]).tolist()


def render_report(run: Path, results: dict, dates: np.ndarray, series: dict, spec: dict):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    mask = (dates >= spec["test_start"]) & (dates <= spec["test_end"])
    for name, returns in series.items():
        nav = np.r_[1.0, np.cumprod(1 + returns[mask])]
        axes[0].plot(nav, label=name)
        axes[1].plot(nav / np.maximum.accumulate(nav) - 1)
    axes[0].set(ylabel="Wealth (test start = 1)", title="Frozen test / 10 bps one-way / research-market proxy")
    axes[1].set(ylabel="Drawdown", xlabel="Months since 2010-01")
    axes[0].legend(ncol=3); fig.tight_layout(); fig.savefig(run / "test_chart.svg"); plt.close(fig)
    tables = []
    for period in ["validation", "test", "201001-201912", "202001-202512"]:
        rows = []
        for name, vals in results["portfolio"][str(spec["primary_cost_bps"])][period].items():
            sharpe = "—" if vals["excess_sharpe"] is None else f'{vals["excess_sharpe"]:.3f}'
            rows.append(f'<tr><td>{name}</td><td>{vals["annualized_return"]:.2%}</td><td>{vals["annualized_volatility"]:.2%}</td><td>{sharpe}</td><td>{vals["max_drawdown"]:.2%}</td><td>{vals["annualized_turnover"]:.2f}</td><td>{vals["mean_market_weight"]:.1%}</td></tr>')
        tables.append(f'<h2>{period}</h2><table><tr><th>Strategy</th><th>CAGR</th><th>Vol.</th><th>Excess Sharpe</th><th>Max DD</th><th>Turnover/year</th><th>Exposure</th></tr>{"".join(rows)}</table>')
    content = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>公开数据量化实验 | Research lab</title><style>body{{font:16px/1.65 system-ui,sans-serif;background:#f4f6f8;color:#182b3b;max-width:1080px;margin:35px auto;padding:20px}}h1{{font-size:30px}}.note{{background:#fff3dc;border-left:4px solid #b77b17;padding:18px}}table{{width:100%;border-collapse:collapse;background:white}}td,th{{padding:9px;text-align:right;border-bottom:1px solid #dde4ea}}td:first-child,th:first-child{{text-align:left}}img{{width:100%;background:white}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:white;padding:16px}}a{{color:#0969a2}}</style>
<h1>公开数据 → 简单模型 → 历史实验</h1><p>独立原型 · 固定训练与测试 · 无付费模型调用</p>
<div class="note">这是一份研究市场代理序列的模拟，不是可实盘交易的策略。数据是当前修订版本，未验证历史发布时点；测试收益不能视为可执行收益。以下同时保留失败结果与基准，不按收益选择赢家。</div>
<p>1960–1999训练；2000–2009验证；2010–2025测试。Ridge α=10，4项滞后特征，训练一次。特征末月与目标收益月之间留出一个完整月。未调参、未在验证后重训。</p>
<img src="test_chart.svg" alt="测试期净值和回撤，10基点成本">
{"".join(tables)}<h2>预测与不确定性</h2><pre>{html.escape(json.dumps(results['prediction'],indent=2))}</pre>
<p>Bootstrap 区间针对相对被动市场的算术年化收益差；不代表因果关系，不修正选题偏差。</p>
<h2>可复核文件</h2><p><a href="metrics.json">完整指标与成本情景</a> · <a href="predictions.csv">逐月预测、仓位、成本后收益</a> · <a href="model.json">模型参数</a> · <a href="frozen_spec.json">实验规格</a> · <a href="provenance.json">数据与代码版本</a> · <a href="execution.json">执行记录</a></p>
<details><summary>实验假设和限制</summary><pre>{html.escape(json.dumps(spec,indent=2,ensure_ascii=False))}</pre></details></html>'''
    (run / "index.html").write_text(content, encoding="utf-8")


def execute(run: Path, spec: dict, blob: bytes):
    dates, values = parse_french(blob)
    dates, ends, x, y, rf = feature_matrix(dates, values, spec["feature_end_lag_months"])
    train = (dates >= spec["train_start"]) & (dates <= spec["train_end"])
    oos = (dates >= spec["validation_start"]) & (dates <= spec["test_end"])
    for start, end in [(spec["train_start"], spec["train_end"]), (spec["validation_start"], spec["test_end"])]:
        if start not in dates or end not in dates:
            raise ValueError("Source does not cover frozen split")
    if not spec["train_end"] < spec["validation_start"] <= spec["validation_end"] < spec["test_start"] <= spec["test_end"]:
        raise ValueError("Invalid chronological split")
    model = fit_ridge(x[train], y[train], spec["ridge_alpha"])
    write_json(run / "model.json", model)
    dates, ends, x, y, rf = dates[oos], ends[oos], x[oos], y[oos], rf[oos]
    predictions = predict(model, x)
    strategies = {"ridge": (predictions > 0).astype(float), "market": np.ones(len(y)),
                  "cash": np.zeros(len(y)), "static_half": np.full(len(y), 0.5),
                  "momentum_12m": (x[:, 2] > 0).astype(float)}
    periods = {"validation": [spec["validation_start"], spec["validation_end"]],
               "test": [spec["test_start"], spec["test_end"]]}
    periods.update({f"{a}-{b}": [a, b] for a, b in spec["subperiods"]})
    result = {"train_rows": int(train.sum()), "portfolio": {}, "prediction": {}}
    primary_series = {}; primary_turnover = {}
    for cost in spec["one_way_cost_bps"]:
        result["portfolio"][str(cost)] = {k: {} for k in periods}
        for name, weights in strategies.items():
            ret, turnover = simulate(weights, y, rf, cost)
            for period, (a, b) in periods.items():
                mask = (dates >= a) & (dates <= b)
                result["portfolio"][str(cost)][period][name] = metrics(ret[mask], rf[mask], turnover[mask], weights[mask])
            if cost == spec["primary_cost_bps"]:
                primary_series[name] = ret; primary_turnover[name] = turnover
    for period in ["validation", "test"]:
        a, b = periods[period]; mask = (dates >= a) & (dates <= b)
        mse = float(np.mean((predictions[mask] - y[mask]) ** 2))
        base = float(np.mean((model["intercept"] - y[mask]) ** 2))
        result["prediction"][period] = {"ridge_mse": mse, "train_mean_mse": base,
            "r2_vs_train_mean": 1 - mse / base, "direction_accuracy": float(np.mean((predictions[mask] > 0) == (y[mask] > 0))),
            "always_positive_accuracy": float(np.mean(y[mask] > 0)),
            "ridge_minus_market_annual_mean_ci95": block_interval((primary_series["ridge"] - primary_series["market"])[mask])}
    write_json(run / "metrics.json", result)
    with (run / "predictions.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["target_month", "feature_last_month", "prediction", "market_excess", "rf"] + [f"{n}_{s}" for n in strategies for s in ["weight", "net_return", "turnover"]])
        for i in range(len(dates)):
            writer.writerow([dates[i], ends[i], predictions[i], y[i], rf[i]] + [v for n in strategies for v in [strategies[n][i], primary_series[n][i], primary_turnover[n][i]]])
    render_report(run, result, dates, primary_series, spec)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--data-zip", type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    if args.output_root.resolve().is_relative_to(repo):
        parser.error("Keep generated data/run history outside the repository")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    run = args.output_root / stamp; run.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    spec_blob = Path(__file__).with_name("experiment.json").read_bytes()
    spec = json.loads(spec_blob)
    (run / "frozen_spec.json").write_bytes(spec_blob)
    provenance = {"started_utc": stamp, "spec_sha256": digest(spec_blob),
                  "code_sha256": digest(Path(__file__).read_bytes()), "python": platform.python_version(),
                  "numpy": np.__version__, "platform": platform.platform(), "provider_calls": 0}
    write_json(run / "provenance.json", provenance)
    try:
        if args.data_zip:
            blob = args.data_zip.read_bytes()
            provenance["data_origin"] = "explicit cached file"
        else:
            with urllib.request.urlopen(spec["data_url"], timeout=60) as response:
                blob = response.read(10_000_001)
                if len(blob) > 10_000_000:
                    raise ValueError("Unexpected download size")
                provenance["http"] = {"url": response.url, "status": response.status,
                                      "last_modified": response.headers.get("Last-Modified")}
        (run / "raw.zip").write_bytes(blob)
        provenance["data_sha256"] = digest(blob)
        write_json(run / "provenance.json", provenance)
        result = execute(run, spec, blob)
        write_json(run / "execution.json", {"status": "complete", "elapsed_seconds": time.perf_counter() - started,
            "fits": 1, "hyperparameter_searches": 0, "provider_calls": 0,
            "test_exposure": "evaluated frozen retrospective holdout once; no tuning on results"})
        print(json.dumps({"run": str(run), "test": result["portfolio"]["10"]["test"], "prediction": result["prediction"]["test"]}, indent=2))
    except Exception:
        write_json(run / "execution.json", {"status": "failed", "elapsed_seconds": time.perf_counter() - started,
                                            "traceback": traceback.format_exc(), "provider_calls": 0})
        raise


if __name__ == "__main__":
    main()
