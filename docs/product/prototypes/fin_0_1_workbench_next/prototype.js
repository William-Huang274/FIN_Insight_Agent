const routes = new Set(["tasks", "case-ready", "case-running", "evidence", "workpaper", "review", "report", "inspect"]);

const tasks = [
  ["P36", "AI 基础设施利润捕获", "高", "研究中", "7 / 12", 58, "31", "3", "核验封装产能"],
  ["NVDA", "FY2026Q2 数据中心增长与利润捕获", "高", "待复核", "9 / 10", 90, "46", "2", "复核反证"],
  ["TSMC", "先进封装扩产、利润率与资本回报", "中", "研究中", "6 / 8", 75, "27", "4", "补充法说会"],
  ["MU", "HBM 供给、定价与客户集中度", "高", "有阻断", "4 / 9", 44, "18", "5", "寻找价格证据"],
  ["ASML", "EUV 订单兑现与半导体设备周期", "中", "可交付", "8 / 8", 100, "39", "1", "生成底稿"],
  ["MSFT", "AI Capex 消化与云业务增量回报", "常规", "研究中", "5 / 9", 56, "23", "3", "校验 Azure 指标"]
];

const nav = (active = "tasks") => `
  <aside class="global-nav">
    <div class="nav-label">分析师工作区</div>
    <a class="nav-item ${active === "tasks" ? "active" : ""}" href="#tasks"><span class="nav-icon">☷</span>研究任务</a>
    <a class="nav-item ${active === "workpaper" ? "active" : ""}" href="#workpaper"><span class="nav-icon">▤</span>工作底稿</a>
    <a class="nav-item ${active === "evidence" ? "active" : ""}" href="#evidence"><span class="nav-icon">▣</span>证据库</a>
    <a class="nav-item ${active === "review" ? "active" : ""}" href="#review"><span class="nav-icon">✓</span>待我复核</a>
    <div class="nav-spacer"></div>
    <div class="nav-label">研究资产</div>
    <a class="nav-item" href="#report"><span class="nav-icon">◇</span>内部报告</a>
    <a class="nav-item" href="#inspect"><span class="nav-icon">⌁</span>运行检查</a>
    <div class="nav-meta">Internal Alpha<br/>中文 · P36 Research</div>
  </aside>`;

const topbar = () => `
  <header class="topbar">
    <a href="#tasks" class="brand"><span class="brand-mark">F</span><span>FinSight Workbench</span></a>
    <label class="global-search"><span>⌕</span><input aria-label="全局搜索" placeholder="搜索公司、研究任务、指标或证据"/><span>Ctrl K</span></label>
    <div class="top-actions"><span class="env">INTERNAL ALPHA</span><span>中文</span><span>数据源 3 / 3</span><span class="avatar">RA</span></div>
  </header>`;

const frame = (content, active) => `<div class="app-frame">${topbar()}${nav(active)}<main class="main">${content}</main></div>`;

function taskCenter() {
  const rows = tasks.map((t, i) => `
    <tr class="${i === 0 ? "selected" : ""}" data-route="${i === 0 ? "case-running" : "case-ready"}">
      <td><div class="task-title"><span class="ticker">${t[0]}</span><span>${t[1]}</span></div><div class="task-sub">负责人：R. Chen · 更新于 ${i === 0 ? "18 分钟前" : `${i + 1} 小时前`}</div></td>
      <td><span class="status-pill ${t[2] === "高" ? "red" : t[2] === "中" ? "amber" : "blue"}">${t[2]}</span></td>
      <td><span class="status-pill ${t[3] === "待复核" ? "amber" : t[3] === "有阻断" ? "red" : t[3] === "可交付" ? "green" : "blue"}">${t[3]}</span></td>
      <td><div class="metric-strong">${t[4]} cells</div><div class="progress"><span style="width:${t[5]}%"></span></div></td>
      <td><div class="metric-strong">${t[6]}</div><div class="metric-sub">候选证据</div></td>
      <td><div class="metric-strong" style="color:${Number(t[7]) > 3 ? "var(--red)" : "var(--amber)"}">${t[7]}</div><div class="metric-sub">开放缺口</div></td>
      <td><strong>${t[8]}</strong><div class="metric-sub">今天</div></td>
    </tr>`).join("");
  return frame(`
    <section class="page">
      <div class="page-head"><div><p class="eyebrow">RESEARCH TASK CENTER</p><h1>研究任务</h1><p>从进度、证据质量和关键缺口判断下一项工作，而不是浏览后台对象。</p></div><div class="head-actions"><button class="button secondary">刷新</button><button class="button primary" data-route="case-ready">+ 发起研究</button></div></div>
      <div class="task-layout">
        <section class="resume-band"><div><p class="eyebrow" style="color:var(--green)">继续当前研究</p><h2>P36 · AI 基础设施利润捕获</h2><p>Evidence Agent 正在核验先进封装产能；7 / 12 cells 已形成初步判断，3 个缺口需要关注。</p></div><div class="button-row"><span class="status-pill blue"><span class="dot"></span>运行中 · 18:42</span><button class="button success" data-route="case-running">继续研究 →</button></div></section>
        <section class="panel">
          <div class="tab-row"><button class="active">我的任务 <small>8</small></button><button>待复核 <small>3</small></button><button>存在阻断 <small>2</small></button><button>最近完成</button></div>
          <div class="toolbar"><input class="field search" placeholder="搜索任务或公司"/><button class="button small">状态：全部</button><button class="button small">优先级</button><button class="button small">排序：下一步截止</button><span style="margin-left:auto;color:var(--muted);font-size:11px">8 个任务</span></div>
          <table class="task-table"><colgroup><col style="width:39%"><col style="width:8%"><col style="width:10%"><col style="width:13%"><col style="width:8%"><col style="width:8%"><col style="width:14%"></colgroup><thead><tr><th>研究问题</th><th>优先级</th><th>阶段</th><th>研究进度</th><th>证据</th><th>缺口</th><th>下一步</th></tr></thead><tbody>${rows}</tbody></table>
        </section>
        <aside class="panel">
          <div class="panel-head"><h2>研究概览</h2><span class="status-pill blue">进行中</span></div>
          <div class="brief-body"><p class="eyebrow">P36 · AI INFRASTRUCTURE</p><h2 class="brief-title">评估需求能否转化为可持续收入与利润</h2><p class="brief-thesis"><strong>当前判断：</strong>需求真实性较强，但利润捕获集中于加速器与稀缺存储；先进封装和 OEM 单位经济性仍需补证。</p>
            <div class="metric-grid"><div><span>研究完成度</span><div class="metric-strong">58%</div></div><div><span>证据候选</span><div class="metric-strong">31</div></div><div><span>开放缺口</span><div class="metric-strong" style="color:var(--red)">3</div></div></div>
            <div class="brief-section"><h3>活跃研究单元</h3>${["需求真实性与持续性","加速器收入与利润捕获","服务器 OEM 订单与毛利","先进封装产能瓶颈","HBM 供给与定价","Capex 消化与周期反证"].map((x,i)=>`<div class="cell-line"><span>0${i+1}</span><span>${x}</span><span class="status-pill ${i<2?"green":i===3?"red":"blue"}">${i<2?"已证实":i===3?"阻断":"研究中"}</span></div>`).join("")}</div>
            <div class="brief-section"><h3>关键缺口</h3><div class="event-evidence"><strong>先进封装组合与产能兑现</strong><br/><span style="color:var(--muted)">当前证据只支持“较扩产”，不足以支持超额收益归属。</span></div></div>
            <button class="button primary" style="width:100%;margin-top:14px" data-route="case-running">打开研究工作台 →</button>
          </div>
        </aside>
      </div>
    </section>`, "tasks");
}

const caseCommand = (stage, activeMode = "research") => `
  <div class="case-command">
    <div class="case-title"><a class="back-link" href="#tasks">‹</a><div><h1>P36 | AI 基础设施利润捕获 | 2026Q2</h1><p>负责人 R. Chen · ${stage}</p></div></div>
    <div class="segmented"><a class="${activeMode === "research" ? "active" : ""}" href="#case-running">研究</a><a class="${activeMode === "review" ? "active" : ""}" href="#review">复核</a><a class="${activeMode === "inspect" ? "active" : ""}" href="#inspect">检查</a></div>
    <div class="head-actions"><button class="profile-summary" data-open-profile><span class="status-pill green">PRO</span><span><strong>Research Pro · P36 Graph</strong><span>3 sources · 6 skills · Lead + 6 agents</span></span></button>${stage.includes("运行中") ? '<button class="button secondary" data-toast="研究已暂停在当前 checkpoint">暂停</button><button class="button danger" data-toast="停止需要填写原因；原有 artifact 将被保留">停止</button>' : ""}</div>
  </div>`;

const event = (num, type, title, copy, cls = "done", extra = "") => `<article class="thread-event ${cls}"><span class="event-icon">${num}</span><div class="event-meta"><span>${type}</span><span>${cls === "active" ? "正在进行" : "已完成"}</span></div><div class="event-title">${title}</div><p class="event-copy">${copy}</p>${extra}</article>`;

function caseReady() {
  return frame(`<section class="case-page">${caseCommand("运行前 · 待接受计划")}
    <div class="case-body"><aside class="run-thread"><div class="thread-head"><h2>Research Run</h2><span class="status-pill gray">READY</span></div><div class="thread-scroll">
      ${event("1","CASE","已接收研究目标","评估 P36 AI 基础设施需求如何跨价值链转化为收入与利润，并明确证据、瓶颈与反证。")}
      ${event("2","PLANNER","形成三阶段计划","先验证需求与利润桥，再扩展供应链机制，最后组织反证、情景与可改变结论的条件。")}
      ${event("3","PREFLIGHT","数据与权限检查通过","Official filings、Internal RAG 与 P36 Graph 可用；外部写入和真实 Case mutation 均禁用。")}
      ${event("4","HUMAN HANDOFF","等待你接受研究计划","开始后会形成新的 run candidate；你仍可调整研究范围与 Run Profile。","active",'<div class="event-actions"><button class="button primary small" data-route="case-running">接受并开始</button><button class="button small" data-toast="范围编辑将在下一版原型展开">调整范围</button></div>')}
    </div></aside>
    <section class="artifact-canvas"><div class="canvas-scroll"><div class="canvas-head"><div><p class="eyebrow">ACCEPTED PLAN CANDIDATE</p><h2>AI 基础设施利润捕获研究计划</h2><p>目标是形成可供 senior 判断的证据化底稿，而不是生成一次性答案。</p></div><div class="button-row"><button class="button" data-open-profile>Run Profile</button><button class="button primary" data-route="case-running">开始研究 →</button></div></div>
      <section class="canvas-section"><div class="plan-summary"><div><span>研究单元</span><strong>12 cells</strong></div><div><span>高优先级</span><strong>6</strong></div><div><span>预计时长</span><strong>35–45 min</strong></div><div><span>成本上限</span><strong>US$12</strong></div></div></section>
      <section class="canvas-section"><div class="section-head"><div><p class="eyebrow">RESEARCH SEQUENCE</p><h3>三阶段纵向研究</h3></div><span class="status-pill green">数据源 3 / 3 已连接</span></div>
        <div class="phase"><div class="phase-num">01</div><div><h4>先确认需求与利润桥</h4><p>验证数据中心部署、客户 capex 与订单信号能否转化为 accelerator、server OEM 与 HBM 收入，并核验利润归属。</p><div class="cell-chips"><span class="cell-chip">需求真实性</span><span class="cell-chip">Accelerator</span><span class="cell-chip">Server OEM</span><span class="cell-chip">HBM</span></div></div><div class="phase-side"><strong>5 cells</strong>Official + Numeric<br/>Lead checkpoint</div></div>
        <div class="phase"><div class="phase-num">02</div><div><h4>扩展供应链机制</h4><p>分析 foundry、advanced packaging 与 semicap 的产能、租金与资本开支 read-through，识别瓶颈和价值迁移。</p><div class="cell-chips"><span class="cell-chip">Foundry</span><span class="cell-chip">Advanced Packaging</span><span class="cell-chip">Semicap</span></div></div><div class="phase-side"><strong>4 cells</strong>Graph expansion<br/>Numeric bridge</div></div>
        <div class="phase"><div class="phase-num">03</div><div><h4>建立反证与决策边界</h4><p>检查 capex digestion、出口限制、price-in、供给释放与周期下行；形成情景和 What Would Change。</p><div class="cell-chips"><span class="cell-chip">Cross-chain counterevidence</span><span class="cell-chip">Scenario</span><span class="cell-chip">What Would Change</span></div></div><div class="phase-side"><strong>3 cells</strong>Senior-ready<br/>No-source writer</div></div>
      </section>
      <section class="canvas-section"><div class="section-head"><div><p class="eyebrow">SUCCESS CONTRACT</p><h3>本次完成的判断标准</h3></div></div><div class="source-row"><div><div class="source-title">判断不是“AI 很强”</div><div class="source-snippet">必须说明收入与利润在哪一段价值链被捕获，以及哪些条件会打破结论。</div></div><div><div class="source-title">证据不是链接集合</div><div class="source-snippet">关键数字、反证、时间边界和来源适用范围必须与判断绑定。</div></div></div></section>
    </div></section></div></section>`, "tasks");
}

function caseRunning() {
  return frame(`<section class="case-page">${caseCommand("运行中 · 7 / 12 cells")}
    <div class="case-body"><aside class="run-thread"><div class="thread-head"><h2>Research Run</h2><span class="status-pill blue"><span class="dot"></span>RUNNING · 18:42</span></div><div class="thread-scroll">
      ${event("1","LEAD","研究计划已接受","12 个 cells 已按需求、利润桥、供应链机制和反证分配给 specialist agents。")}
      ${event("2","EVIDENCE","需求真实性已有一手证据","从发行人披露确认数据中心与 AI 工厂部署增长；证据适用于需求方向，不足以单独证明持续性。", "done",'<div class="event-evidence"><strong>Q1 Fiscal 2027 Summary</strong><br/>Official issuer · 2026-05-20 · 接受为需求方向证据</div>')}
      ${event("3","NUMERIC","利润率复算一致","收入 US$130.5B、毛利 US$97.9B、营业利润 US$81.5B；复算毛利率 74.99%，营业利润率 62.42%。")}
      ${event("4","COUNTEREVIDENCE","建立持续性反证","提前采购、供给错配和强需求下的双重下单可能令订单信号高估可持续终端需求。")}
      ${event("5","DOMAIN","正在核验先进封装产能兑现","Graph 已扩展到 foundry、CoWoS 设备、封装测试和主要客户；当前需要 official capacity 证据。","active",'<div class="event-evidence"><strong>当前工具</strong><br/>P36 Graph → Official Filing Index → Numeric Parser</div><div class="event-actions"><button class="button small" data-route="evidence">查看相关证据</button><button class="button small" data-toast="方向修正会写入 run event 并交给 Lead 判断">提出方向修正</button></div>')}
      ${event("6","NEXT","后续计划","完成先进封装后核验 HBM 定价与客户集中度，再进入 Lead synthesis 和 Writer no-source。", "")}
    </div></aside>
    <section class="artifact-canvas"><div class="canvas-scroll"><div class="canvas-head"><div><p class="eyebrow">LIVE WORKPAPER · 7 / 12 CELLS</p><h2>需求正在转化，但利润捕获高度集中</h2><p>以下内容只由已验证的证据和数字形成；未成熟判断保留为缺口。</p></div><div class="button-row"><button class="button" data-route="evidence">证据矩阵</button><button class="button" data-route="workpaper">打开底稿</button></div></div>
      <section class="canvas-section judgment-hero"><div class="judgment-copy"><p class="eyebrow" style="color:var(--green)">当前研究判断</p><h3>需求转化已经出现，但持续性和跨链分配仍有明确边界</h3><p>公司披露的数据中心增长与大规模客户部署支持需求正在转化；accelerator 与 HBM 保持较强议价，但 server OEM、先进封装和周期后段的利润捕获仍需补证。</p><div class="live-bar"><span class="pulse"></span>Domain Agent 正在核验先进封装产能与租金归属</div></div><div class="hero-metrics"><div><span>收入</span><strong>US$130.5B</strong></div><div><span>毛利率</span><strong>74.99%</strong></div><div><span>证据</span><strong>31</strong></div><div><span>开放缺口</span><strong style="color:var(--red)">3</strong></div></div></section>
      <section class="canvas-section"><div class="section-head"><div><p class="eyebrow">ACCEPTED FINDINGS</p><h3>已进入底稿的研究单元</h3></div><span class="status-pill blue">实时更新</span></div>
        <div class="work-block"><h4>01 · 需求真实性与持续性</h4><p>数据中心与 AI 工厂部署支持需求方向，但订单持续性仍需要后续周期与供给错配证据确认。</p><div class="source-row"><div><div class="source-label">一手披露</div><div class="source-title">Q1 Fiscal 2027 Summary</div><div class="source-snippet">AI factories across industries and countries...</div></div><div><div class="source-label">反证</div><div class="source-title">提前采购与重复下单</div><div class="source-snippet">强需求环境可能令订单信号领先终端消化。</div></div></div></div>
        <div class="work-block"><h4>02 · Accelerator 收入与利润捕获</h4><p>高毛利与营业利润支持主要利润池仍集中于 accelerator 平台，但需剥离产品组合和供给稀缺对当前利润率的临时贡献。</p></div>
        <div class="work-block"><h4>03 · Server OEM 单位经济性</h4><p>订单履行存在非线性，收入转化可见但毛利和现金转换证据不足，暂不提升为高置信判断。</p></div>
      </section>
    </div></section></div></section>`, "tasks");
}

function pageHead(eyebrow, title, copy, actions = "") { return `<div class="page-head"><div><p class="eyebrow">${eyebrow}</p><h1>${title}</h1><p>${copy}</p></div><div class="head-actions">${actions}</div></div>`; }

function evidencePage() {
  const rows = [
    ["需求真实性","部署与数据中心增长是否代表可持续终端需求？","A-","3","1","已接受","核验持续性"],
    ["Accelerator 利润捕获","收入增长是否形成可持续平台利润？","A","5","2","已接受","拆分组合效应"],
    ["Server OEM 订单","订单是否能转化为收入、毛利与现金？","B","2","1","需补证","寻找现金桥"],
    ["先进封装产能","扩产是否形成持续瓶颈与超额租金？","B-","2","2","阻断","补 official capacity"],
    ["HBM 定价与集中度","供给约束是否维持定价与利润？","B+","4","2","研究中","核验客户集中"],
    ["Capex 与周期反证","资本开支是否可能提前消化未来需求？","B","3","3","研究中","形成下行情景"]
  ];
  const trs = rows.map((r,i)=>`<tr class="${i===0?"selected":""}"><td><div class="claim">${r[0]}</div><div class="claim-sub">${r[1]}</div></td><td><span class="grade">${r[2]}</span></td><td>${r[3]} 条</td><td>${r[4]} 条</td><td><span class="status-pill ${r[5]==="阻断"?"red":r[5]==="需补证"?"amber":r[5]==="已接受"?"green":"blue"}">${r[5]}</span></td><td><strong>${r[6]}</strong></td></tr>`).join("");
  return frame(`<section class="page">${pageHead("EVIDENCE DECISION MATRIX","P36 证据矩阵","按判断组织证据、数字和反证；选择一行查看 inclusion decision 与适用边界。",'<button class="button" data-route="case-running">返回 Research Run</button><button class="button primary" data-route="workpaper">打开底稿 →</button>')}
    <div class="matrix-layout"><section class="panel matrix-panel"><div class="panel-head"><h2>研究判断与证据状态</h2><div class="segmented"><button class="active">全部 12</button><button>缺口 3</button><button>冲突 2</button></div></div><table class="matrix-table"><colgroup><col style="width:35%"><col style="width:8%"><col style="width:10%"><col style="width:11%"><col style="width:14%"><col style="width:22%"></colgroup><thead><tr><th>判断问题</th><th>质量</th><th>证据</th><th>反证</th><th>状态</th><th>下一步</th></tr></thead><tbody>${trs}</tbody></table></section>
    <aside class="inspector sticky"><div class="panel-head"><h2>来源与适用边界</h2><button class="icon-button" title="关闭检查器">×</button></div><div class="inspector-body"><p class="eyebrow">OFFICIAL ISSUER · ACCEPTED</p><h3>Q1 Fiscal 2027 Summary</h3><p>2026-05-20 · Company filing structured-object index</p><div class="quote">“data centers and AI factories across industries and countries.”</div><ul class="meta-list"><li><span>支持</span><strong>需求方向与部署广度</strong></li><li><span>不支持</span><strong>订单持续性与利润归属</strong></li><li><span>Freshness</span><strong>当前财季</strong></li><li><span>Inclusion</span><strong>作为一手方向证据</strong></li></ul><div class="button-row" style="margin-top:14px"><button class="button small success" data-toast="证据已保持为 accepted；变更会形成新判断版本">接受</button><button class="button small" data-toast="该来源已标记为需要降级">降级</button><button class="button small danger" data-toast="排除原因必须记录">排除</button></div></div></aside></div></section>`, "evidence");
}

const paperBody = () => `<article class="paper"><p class="eyebrow">WORKPAPER · DRAFT V4</p><h1>P36 AI 基础设施需求与利润捕获</h1><p class="paper-lede">当前证据支持 AI 基础设施需求已从预期进入部署和收入转化阶段，但利润池集中于具备平台控制力和供给稀缺性的环节。持续性判断仍取决于终端消化、先进封装兑现与客户集中度。</p>
  <h2>核心判断</h2><h3>1. 需求真实性已增强，持续性仍需周期验证</h3><p>发行人披露的数据中心与 AI 工厂部署提供了直接需求信号<span class="cite">1</span>。但强需求环境中的提前采购、重复下单和供给错配意味着订单不能直接等同于可持续终端消化<span class="cite">2</span>。</p>
  <h3>2. 利润首先由 accelerator 平台捕获</h3><p>最新财务事实显示收入、毛利和营业利润均处于高位，复算利润率与披露一致。当前盈利结构支持平台环节拥有最强利润捕获，但必须持续拆分产品组合和供给稀缺的临时贡献。</p>
  <table class="number-table"><thead><tr><th>指标</th><th>报告值</th><th>复算</th><th>状态</th></tr></thead><tbody><tr><td>收入</td><td>US$130.497B</td><td>US$130.497B</td><td>一致</td></tr><tr><td>毛利率</td><td>74.99%</td><td>74.99%</td><td>一致</td></tr><tr><td>营业利润率</td><td>62.42%</td><td>62.42%</td><td>一致</td></tr></tbody></table>
  <h3>3. 跨链利润并不均匀</h3><p>HBM 和先进封装受益于供给稀缺，但现有证据尚不足以证明所有扩产环节都能维持超额租金。Server OEM 的收入转化可见，单位经济性和现金桥仍是开放缺口。</p>
  <h2>反证与边界</h2><p>主要反证包括 capex digestion、出口限制、price-in、供给释放和客户集中。若供给在需求放缓前集中释放，利润可能从稀缺环节回流至客户。</p>
  <h2>What Would Change</h2><div class="wwc"><strong>下调判断：</strong>连续两个季度终端消化弱于订单、先进封装利用率下降、HBM 定价显著松动，或 accelerator 毛利率在组合稳定时持续下行。<br/><br/><strong>上调判断：</strong>客户部署转化为可复现的业务收入，且供应链扩产仍未消除关键稀缺。</div></article>`;

function workpaperPage() {
  return frame(`<section class="page">${pageHead("STRUCTURED WORKPAPER","研究底稿","形成判断的可编辑工作空间；证据 lineage 通过引用进入 Inspector，不在正文全量展开。",'<button class="button" data-route="evidence">证据矩阵</button><button class="button" data-toast="编辑会生成 Workpaper v5，不覆盖当前版本">编辑底稿</button><button class="button primary" data-route="review">提交 Senior Review →</button>')}
    <div class="workpaper-layout"><section>${paperBody()}</section><aside class="inspector sticky"><div class="panel-head"><h2>研究上下文</h2><div class="segmented"><button class="active">引用</button><button>数字</button><button>评论</button></div></div><div class="inspector-body"><p class="eyebrow">SELECTED CITATION · 1</p><h3>Q1 Fiscal 2027 Summary</h3><div class="quote">data centers and AI factories across industries and countries...</div><p>该来源支持需求方向与部署广度，不单独支持订单持续性或跨链利润归属。</p><ul class="meta-list"><li><span>来源等级</span><strong>一手披露</strong></li><li><span>证据状态</span><strong>Accepted</strong></li><li><span>反证绑定</span><strong>2 条</strong></li></ul><div class="brief-section"><h3>Open gaps</h3><div class="event-evidence"><strong>先进封装产能兑现</strong><br/>缺少利用率与租金归属的直接证据。</div><div class="event-evidence"><strong>Server OEM 现金桥</strong><br/>收入转化尚未连接至现金和库存。</div></div></div></aside></div></section>`, "workpaper");
}

function reviewPage() {
  const cards = [
    ["需求持续性边界","需求已从预期进入部署，但订单不能直接等同于可持续终端消化。","一手披露支持部署广度；提前采购与供给错配构成反证。"],
    ["Accelerator 利润捕获","平台环节仍是当前最强利润池，但组合与稀缺贡献需要继续拆分。","三项 exact numbers 已复算一致；利润率边界已保留。"],
    ["先进封装超额租金","扩产受益明确，但现有证据不足以证明超额租金可持续。","缺少利用率、租金归属和供给释放后的价格证据。"]
  ].map((c,i)=>`<article class="review-card"><div class="review-card-head"><span class="review-num">0${i+1}</span><div><h3>${c[0]}</h3><p>${c[1]}</p></div><span class="status-pill ${i===2?"amber":"blue"}">${i===2?"需要判断":"待复核"}</span></div><div class="review-context"><div><h4>证据与数字</h4><p>${c[2]}</p></div><div><h4>反证与边界</h4><p>${i===0?"强需求下重复下单可能使订单领先消化。":i===1?"供给正常化和产品组合变化可能压低利润率。":"供给释放可能令利润转移回客户。"}</p></div></div><div class="review-actions"><button class="button small success" data-review-action="接受">接受</button><button class="button small" data-review-action="编辑后接受">编辑后接受</button><button class="button small" data-review-action="降级">降级</button><button class="button small danger" data-review-action="退回修复">退回修复</button><button class="button small" data-review-action="保持未决">保持未决</button></div></article>`).join("");
  return frame(`<section class="page">${pageHead("EXACT HUMAN SENIOR REVIEW","P36 Senior Review","在原判断、证据、数字和反证上下文中作出 exact outcome，不再填写脱离内容的空白问卷。",'<button class="button" data-route="workpaper">打开底稿</button><button class="button primary" data-route="report">完成复核 →</button>')}
    <div class="review-layout"><div class="review-banner"><div><strong>待审对象：Workpaper v4</strong><br/><span style="color:var(--muted)">3 个关键判断需要 senior outcome；其余 7 个判断沿用已记录的 evidence maturity。</span></div><span class="status-pill amber">AWAITING HUMAN</span></div>
    <section>${cards}</section><aside class="inspector sticky"><div class="panel-head"><h2>复核记录</h2><span class="status-pill blue">0 / 3</span></div><div class="inspector-body"><p class="eyebrow">SENIOR R2</p><h3>本轮需要回答什么</h3><p>不是判断研究是否“完美”，而是判断当前底稿是否足以支持内部使用，以及哪些主张必须降级或退回修复。</p><textarea class="comment-box" placeholder="记录整体意见或发布边界"></textarea><div class="brief-section"><h3>提交后将形成</h3><ul class="meta-list"><li><span>Artifact</span><strong>Workpaper v4</strong></li><li><span>Outcome</span><strong>逐判断记录</strong></li><li><span>Repair</span><strong>仅对退回项</strong></li><li><span>Publish</span><strong>仍为 Internal</strong></li></ul></div><button class="button primary" style="width:100%;margin-top:14px" data-route="report">提交 exact review</button></div></aside></div></section>`, "review");
}

function reportPage() {
  return frame(`<section class="page">${pageHead("DECISION-READY INTERNAL REPORT","P36 AI 基础设施利润捕获","Senior Review 已完成；本报告可供内部研究使用，不构成生产发布或投资建议。",'<button class="button" data-route="workpaper">查看底稿</button><button class="button" data-route="inspect">检查运行记录</button><button class="button primary" data-toast="FIN 0.1 当前只生成内部 artifact">导出内部报告</button>')}
    <div class="report-layout"><section><div class="report-hero"><p class="eyebrow">EXECUTIVE VIEW · CONFIDENCE 72%</p><h1>需求已转化，利润仍集中在平台与稀缺供给</h1><p>AI 基础设施需求已从预期进入部署和收入转化阶段，但价值链并非普遍受益。Accelerator 平台和 HBM 目前具备更清晰的利润捕获；Server OEM 与先进封装仍需证明单位经济性和超额租金持续性。</p><div class="report-kpis"><div><span>收入</span><strong>US$130.5B</strong></div><div><span>毛利率</span><strong>74.99%</strong></div><div><span>Senior outcome</span><strong>8 / 10</strong></div><div><span>开放边界</span><strong style="color:var(--amber)">2</strong></div></div></div>
      <section class="canvas-section"><div class="section-head"><div><p class="eyebrow">WHO CAPTURES VALUE</p><h3>跨链价值捕获地图</h3></div><button class="text-button" data-route="evidence">打开全部证据 →</button></div><div class="chain-map">${[["Accelerator","平台控制力最强，利润池集中","高"],["HBM","供给稀缺支持定价，集中度是边界","中高"],["Foundry","规模与工艺受益，资本强度约束回报","中"],["Packaging","扩产明确，超额租金持续性待证","中低"],["Server OEM","收入可见，毛利与现金桥较弱","低"]].map(x=>`<div class="chain-node"><span class="status-pill ${x[2]==="高"?"green":x[2]==="低"?"red":"amber"}">${x[2]}</span><h4>${x[0]}</h4><p>${x[1]}</p><div class="chain-score">${x[2]}</div></div>`).join("")}</div></section>
      <section class="canvas-section"><div class="section-head"><div><p class="eyebrow">SCENARIOS</p><h3>未来 12 个月判断边界</h3></div></div><table class="scenario-table"><thead><tr><th>情景</th><th>关键条件</th><th>利润捕获</th><th>需要观察</th></tr></thead><tbody><tr><td><strong>上行</strong></td><td>部署持续、供给仍紧、客户收入兑现</td><td>平台与 HBM 维持高位</td><td>利用率、客户 monetization</td></tr><tr><td><strong>基准</strong></td><td>需求增长但供给逐步释放</td><td>利润保持集中但边际回落</td><td>毛利率与库存</td></tr><tr><td><strong>下行</strong></td><td>capex digestion、重复下单、价格松动</td><td>稀缺租金快速回吐</td><td>订单取消、利用率、定价</td></tr></tbody></table></section>
      <section class="canvas-section"><div class="section-head"><div><p class="eyebrow">WHAT WOULD CHANGE</p><h3>改变当前判断的条件</h3></div></div><div class="wwc">连续两个季度终端消化弱于订单、先进封装利用率下降、HBM 定价显著松动，或 accelerator 毛利率在组合稳定时持续下行，将触发判断下调与 Case repair。</div></section>
    </section><aside class="inspector sticky"><div class="panel-head"><h2>报告索引</h2><span class="status-pill green">INTERNAL</span></div><div class="inspector-body"><ul class="meta-list"><li><span>关键判断</span><strong>10</strong></li><li><span>Accepted</span><strong>8</strong></li><li><span>Unresolved</span><strong>2</strong></li><li><span>证据引用</span><strong>31</strong></li><li><span>Exact numbers</span><strong>3</strong></li></ul><div class="brief-section"><h3>Senior Review</h3><div class="event-evidence"><strong>接受并保留边界</strong><br/>需求与利润集中判断可供内部使用；先进封装与 Server OEM 不提升为高置信主张。</div></div><div class="brief-section"><h3>主要来源</h3><div class="cell-line"><span>01</span><span>Official filings</span><span>12</span></div><div class="cell-line"><span>02</span><span>Internal RAG</span><span>11</span></div><div class="cell-line"><span>03</span><span>P36 Graph</span><span>8</span></div></div></div></aside></div></section>`, "tasks");
}

function inspectPage() {
  return frame(`<section class="page">${pageHead("STRUCTURED RUN INSPECTOR","运行检查","这里承接版本、调用、成本、错误与 lineage；产品研究界面不再展示这些字段。",'<button class="button" data-route="case-running">返回研究模式</button><button class="button" data-route="report">查看报告</button>')}
    <div class="inspect-layout"><section><div class="inspect-graph"><div class="section-head"><div><p class="eyebrow">AGENT ORCHESTRATION</p><h3>Run execution map</h3></div><span class="status-pill green">7 / 12 cells</span></div>
      <div class="agent-lane"><div class="agent-name">Lead</div><div class="agent-node done">Plan accepted<br/>12 cells</div><div class="agent-node done">Checkpoint A<br/>scope retained</div><div class="agent-node active">Synthesis<br/>waiting 2 agents</div><div class="agent-node">Writer<br/>not started</div></div>
      <div class="agent-lane"><div class="agent-name">Evidence</div><div class="agent-node done">Official retrieval<br/>12 docs</div><div class="agent-node done">Inclusion<br/>31 candidates</div><div class="agent-node done">Counterevidence<br/>11 items</div><div class="agent-node">Complete</div></div>
      <div class="agent-lane"><div class="agent-name">Numeric</div><div class="agent-node done">Parse facts<br/>3 metrics</div><div class="agent-node done">Recalculate<br/>matched</div><div class="agent-node">Standby</div><div class="agent-node">Complete</div></div>
      <div class="agent-lane"><div class="agent-name">Domain</div><div class="agent-node done">Accelerator</div><div class="agent-node warn">Server OEM<br/>gap</div><div class="agent-node active">Packaging<br/>retrieving</div><div class="agent-node">HBM</div></div>
    </div>
    <section class="panel" style="margin-top:14px"><div class="panel-head"><h2>Package 与版本身份</h2><span class="status-pill blue">只读</span></div><table class="debug-table"><tbody><tr><td>case_id</td><td>case_80fb19038ebf44f5ef7ad5b5</td></tr><tr><td>run_candidate</td><td>run_p36_20260719_184205_c04</td></tr><tr><td>package_digest</td><td>sha256:91c4e6c25b9d...1eb7</td></tr><tr><td>workpaper_version</td><td>wp_p36_v4 · digest verified</td></tr><tr><td>authority</td><td>internal_fixture_shadow_only</td></tr><tr><td>external_writes</td><td>0</td></tr></tbody></table></section></section>
    <aside class="inspector sticky"><div class="panel-head"><h2>调用与预算</h2><span class="status-pill blue">18:42</span></div><div class="inspector-body"><div class="metric-grid"><div><span>工具调用</span><div class="metric-strong">27</div></div><div><span>失败</span><div class="metric-strong">1</div></div><div><span>成本</span><div class="metric-strong">US$4.12</div></div></div><div class="brief-section"><h3>最近调用</h3><ul class="call-list"><li><span>18:42:10</span><strong>P36 Graph expand(packaging)</strong><span class="status-pill blue">RUN</span></li><li><span>18:41:52</span><strong>Official Filing Index query</strong><span class="status-pill green">200</span></li><li><span>18:40:31</span><strong>Numeric Parser margin bridge</strong><span class="status-pill green">PASS</span></li><li><span>18:39:44</span><strong>Internal RAG capacity</strong><span class="status-pill red">0 hits</span></li></ul></div><div class="brief-section"><h3>边界</h3><ul class="meta-list"><li><span>网络策略</span><strong>allowlisted</strong></li><li><span>业务写入</span><strong>0</strong></li><li><span>Secret persistence</span><strong>disabled</strong></li><li><span>Production readiness</span><strong>not admitted</strong></li></ul></div></div></aside></div></section>`, "tasks");
}

const renderers = { tasks: taskCenter, "case-ready": caseReady, "case-running": caseRunning, evidence: evidencePage, workpaper: workpaperPage, review: reviewPage, report: reportPage, inspect: inspectPage };

function currentRoute() { const route = location.hash.replace(/^#/, "") || "tasks"; return routes.has(route) ? route : "tasks"; }
function navigate(route) { location.hash = route; }
function showToast(message) { const toast = document.getElementById("toast"); toast.textContent = message; toast.classList.add("show"); clearTimeout(showToast.timer); showToast.timer = setTimeout(() => toast.classList.remove("show"), 2400); }

function bind() {
  document.querySelectorAll("[data-route]").forEach(el => el.addEventListener("click", () => navigate(el.dataset.route)));
  document.querySelectorAll("[data-open-profile]").forEach(el => el.addEventListener("click", () => document.getElementById("profile-dialog").showModal()));
  document.querySelectorAll("[data-close-profile]").forEach(el => el.addEventListener("click", () => document.getElementById("profile-dialog").close()));
  document.querySelectorAll("[data-toast]").forEach(el => el.addEventListener("click", () => showToast(el.dataset.toast)));
  document.querySelectorAll("[data-review-action]").forEach(el => el.addEventListener("click", () => { el.closest(".review-actions").querySelectorAll("button").forEach(b => b.classList.remove("primary", "success", "danger")); el.classList.add(el.dataset.reviewAction === "接受" ? "success" : el.dataset.reviewAction === "退回修复" ? "danger" : "primary"); showToast(`已记录：${el.dataset.reviewAction}`); }));
}

function render() { document.getElementById("app").innerHTML = renderers[currentRoute()](); bind(); window.scrollTo(0, 0); }
window.addEventListener("hashchange", render);
render();
