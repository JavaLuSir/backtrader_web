const els = {
  list: document.getElementById("strategy-list"),
  sidebar: document.getElementById("sidebar"),
  toggleSidebar: document.getElementById("toggleSidebar"),
  symbol: document.getElementById("symbol"),
  cash: document.getElementById("cash"),
  startDate: document.getElementById("startDate"),
  endDate: document.getElementById("endDate"),
  runBtn: document.getElementById("runBtn"),
  exportBtn: document.getElementById("exportBtn"),
  status: document.getElementById("status"),
  metrics: document.getElementById("metrics"),
  canvas: document.getElementById("chart"),
  klineContainer: document.getElementById("kline-container"),
  klineLegend: document.getElementById("kline-legend"),
  ma5Color: document.getElementById("ma5Color"),
  ma10Color: document.getElementById("ma10Color"),
  ma20Color: document.getElementById("ma20Color"),
  contextMenu: document.getElementById("strategy-context-menu"),
  contextRunBacktest: document.getElementById("contextRunBacktest"),
  contextViewSource: document.getElementById("contextViewSource"),
  sourceModal: document.getElementById("source-modal"),
  sourceModalMask: document.getElementById("source-modal-mask"),
  sourceModalClose: document.getElementById("source-modal-close"),
  sourceTitle: document.getElementById("source-modal-title"),
  sourceCode: document.getElementById("source-code"),
};

let selectedStrategyId = null;
let contextStrategyId = null;
let lastResult = null;
let klineChart = null;
let candleSeries = null;
let volumeSeries = null;
let maSeries = {};

function getMaConfig() {
  return [
    { period: 5, color: els.ma5Color.value, label: "MA5" },
    { period: 10, color: els.ma10Color.value, label: "MA10" },
    { period: 20, color: els.ma20Color.value, label: "MA20" },
  ];
}

const sourceCache = new Map();

function isoDate(d) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function setDefaultDates() {
  const end = new Date();
  const start = new Date(end.getTime());
  start.setFullYear(end.getFullYear() - 10);
  els.startDate.value = isoDate(start);
  els.endDate.value = isoDate(end);
}

function setStatus(text) {
  els.status.textContent = text;
}

function formatMoney(x) {
  if (!Number.isFinite(x)) return "-";
  return x.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function renderMetrics(metrics) {
  if (!metrics) {
    els.metrics.textContent = "";
    return;
  }

  const fmtPct = (x) => (Number.isFinite(Number(x)) ? `${Number(x).toFixed(2)}%` : "-");
  const fmtRatio = (x) => (Number.isFinite(Number(x)) ? Number(x).toFixed(3) : "-");

  const parts = [
    `策略: ${metrics.strategy}`,
    `期初: ${formatMoney(metrics.start_cash)}`,
    `期末: ${formatMoney(metrics.end_value)}`,
    `收益: ${formatMoney(metrics.pnl)} (${fmtPct(metrics.return_pct)})`,
    `年化: ${fmtPct(metrics.annual_return_pct)}`,
    `夏普: ${fmtRatio(metrics.sharpe)}`,
    `索提诺: ${fmtRatio(metrics.sortino)}`,
    `最大回撤: ${fmtPct(metrics.max_drawdown_pct)}`,
    `胜率: ${fmtPct(metrics.win_rate_pct)}`,
    `盈亏比: ${fmtRatio(metrics.avg_win_loss_ratio)}`,
    `卡尔马: ${fmtRatio(metrics.calmar)}`,
    `买/卖: ${metrics.buy_count}/${metrics.sell_count}`,
  ];

  els.metrics.textContent = parts.join(" | ");
}

function escapeCsv(v) {
  if (v === null || v === undefined) return "";
  const s = String(v);
  if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

function fmtNum(x, digits = 2) {
  const n = Number(x);
  return Number.isFinite(n) ? n.toFixed(digits) : "";
}

function safeFilename(s) {
  return String(s || "export.csv")
    .replace(/[<>:"/\\|?*]+/g, "_")
    .replace(/\s+/g, "_");
}

function makeTradesCsv(result) {
  const metrics = result?.metrics || {};
  const symbol = metrics.symbol || "";
  const strategy = metrics.strategy || "";
  const start = metrics.start_date || "";
  const end = metrics.end_date || "";

  const trades = [...(result?.buys || []), ...(result?.sells || [])];
  trades.sort(
    (a, b) =>
      String(a.date || "").localeCompare(String(b.date || "")) ||
      String(a.action || "").localeCompare(String(b.action || ""))
  );

  const headers = [
    "symbol",
    "strategy",
    "start_date",
    "end_date",
    "date",
    "action",
    "price",
    "size",
    "cash",
    "value",
    "position_size",
  ];
  const lines = [headers.join(",")];

  for (const t of trades) {
    const row = [
      symbol,
      strategy,
      start,
      end,
      t.date || "",
      t.action || "",
      fmtNum(t.price, 4),
      fmtNum(t.size, 6),
      fmtNum(t.cash, 2),
      fmtNum(t.value, 2),
      fmtNum(t.position_size, 6),
    ].map(escapeCsv);
    lines.push(row.join(","));
  }

  return lines.join("\n");
}

function downloadTextFile(filename, text, mimeType) {
  const blob = new Blob([text], { type: mimeType || "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 500);
}

function exportTradesCsv() {
  if (!lastResult || !lastResult.metrics) {
    setStatus("暂无可导出的回测结果");
    return;
  }
  const m = lastResult.metrics;
  const filename = safeFilename(
    `${m.symbol || "SYMBOL"}_${m.strategy || "strategy"}_${m.start_date || ""}_${m.end_date || ""}_trades.csv`
  );
  const csv = makeTradesCsv(lastResult);
  downloadTextFile(filename, csv, "text/csv;charset=utf-8");
}

function clearListActive() {
  els.list.querySelectorAll(".strategy-item").forEach((n) => n.classList.remove("active"));
}

function selectStrategy(id) {
  selectedStrategyId = id;
  clearListActive();
  const node = els.list.querySelector(`[data-id="${CSS.escape(id)}"]`);
  if (node) node.classList.add("active");
}

function hideContextMenu() {
  els.contextMenu.classList.add("hidden");
  contextStrategyId = null;
}

function showContextMenu(x, y, strategyId) {
  contextStrategyId = strategyId;
  const menu = els.contextMenu;
  menu.classList.remove("hidden");

  const rect = menu.getBoundingClientRect();
  const left = Math.min(x, window.innerWidth - rect.width - 8);
  const top = Math.min(y, window.innerHeight - rect.height - 8);

  menu.style.left = `${Math.max(8, left)}px`;
  menu.style.top = `${Math.max(8, top)}px`;
}

function openSourceModal() {
  if (!contextStrategyId) return;

  const strategyId = contextStrategyId;
  hideContextMenu();

  els.sourceTitle.textContent = `策略源码 - ${strategyId}`;
  els.sourceCode.textContent = "加载中...";
  els.sourceModal.classList.remove("hidden");
  document.body.style.overflow = "hidden";

  const cached = sourceCache.get(strategyId);
  if (cached) {
    renderSourceCode(strategyId, cached);
    return;
  }

  fetch(`/api/strategies/source/${encodeURIComponent(strategyId)}`)
    .then(async (res) => {
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "获取源码失败");
      }
      return res.json();
    })
    .then((data) => {
      const source = String(data?.source || "");
      sourceCache.set(strategyId, source);
      renderSourceCode(strategyId, source);
    })
    .catch((err) => {
      els.sourceCode.textContent = `加载失败: ${err?.message || err}`;
    });
}

function renderSourceCode(strategyId, source) {
  els.sourceTitle.textContent = `策略源码 - ${strategyId}`;
  
  if (window.hljs && window.hljs.highlight) {
    const result = window.hljs.highlight(source, { language: "python" });
    els.sourceCode.innerHTML = result.value;
    els.sourceCode.className = "hljs language-python";
  } else {
    els.sourceCode.textContent = source;
    els.sourceCode.className = "language-python";
  }
}

function closeSourceModal() {
  els.sourceModal.classList.add("hidden");
  document.body.style.overflow = "";
}

async function loadStrategies() {
  const res = await fetch("/api/strategies");
  if (!res.ok) throw new Error("加载策略列表失败");
  const data = await res.json();
  els.list.innerHTML = "";

  const items = data.items || [];
  if (items.length === 0) {
    els.list.innerHTML = `<div class="status">未找到 strategies/*.py</div>`;
    return;
  }

  for (const item of items) {
    const div = document.createElement("div");
    div.className = "strategy-item";
    div.dataset.id = item.id;
    div.innerHTML = `
      <div class="strategy-name">${item.name}</div>
      <div class="strategy-id">${item.id}</div>
    `;

    div.addEventListener("click", () => {
      hideContextMenu();
      selectStrategy(item.id);
    });

    div.addEventListener("contextmenu", (evt) => {
      evt.preventDefault();
      selectStrategy(item.id);
      showContextMenu(evt.clientX, evt.clientY, item.id);
    });

    els.list.appendChild(div);
  }

  selectStrategy(items[0].id);
}

function resizeCanvasToDisplaySize(canvas) {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const width = Math.max(10, Math.floor(rect.width * dpr));
  const height = Math.max(10, Math.floor(rect.height * dpr));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
    return true;
  }
  return false;
}

function drawText(ctx, text, x, y, color, align = "left") {
  ctx.save();
  ctx.fillStyle = color;
  ctx.textAlign = align;
  ctx.fillText(text, x, y);
  ctx.restore();
}

function drawTriangle(ctx, x, y, size, color, direction) {
  ctx.save();
  ctx.fillStyle = color;
  ctx.beginPath();
  if (direction === "up") {
    ctx.moveTo(x, y - size);
    ctx.lineTo(x - size, y + size);
    ctx.lineTo(x + size, y + size);
  } else {
    ctx.moveTo(x, y + size);
    ctx.lineTo(x - size, y - size);
    ctx.lineTo(x + size, y - size);
  }
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

function renderKlineChart(result) {
  const container = els.klineContainer;
  if (!container) return;

  if (klineChart) {
    klineChart.remove();
    klineChart = null;
    candleSeries = null;
    volumeSeries = null;
  }

  container.innerHTML = "";

  if (typeof LightweightCharts === "undefined") {
    container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#ff4d4f;">K线图依赖加载失败</div>';
    return;
  }

  if (!result || !result.ohlcv || result.ohlcv.length === 0) {
    container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--muted);">暂无K线数据</div>';
    return;
  }

  const width = container.clientWidth || 800;
  const height = container.clientHeight || 420;

  klineChart = LightweightCharts.createChart(container, {
    width,
    height,
    layout: {
      background: { type: "solid", color: "transparent" },
      textColor: "#aab3d6",
    },
    grid: {
      vertLines: { color: "rgba(255,255,255,0.05)" },
      horzLines: { color: "rgba(255,255,255,0.05)" },
    },
    rightPriceScale: { borderColor: "rgba(255,255,255,0.1)" },
    timeScale: { borderColor: "rgba(255,255,255,0.1)", timeVisible: true },
    handleScroll: { vertTouchDrag: false },
  });

  candleSeries = klineChart.addCandlestickSeries({
    upColor: "#3ddc97",
    downColor: "#ff4d4f",
    borderUpColor: "#3ddc97",
    borderDownColor: "#ff4d4f",
    wickUpColor: "#3ddc97",
    wickDownColor: "#ff4d4f",
  });

  volumeSeries = klineChart.addHistogramSeries({
    color: "#26a69a",
    priceFormat: { type: "volume" },
    priceScaleId: "",
  });

  volumeSeries.priceScale().applyOptions({
    scaleMargins: { top: 0.8, bottom: 0 },
  });

  const candleData = result.ohlcv.map((d) => ({
    time: Math.floor(new Date(d.time).getTime() / 1000),
    open: Number(d.open),
    high: Number(d.high),
    low: Number(d.low),
    close: Number(d.close),
  }));

  const volumeData = result.ohlcv.map((d) => ({
    time: Math.floor(new Date(d.time).getTime() / 1000),
    value: Number(d.volume),
    color: Number(d.close) >= Number(d.open) ? "rgba(61,220,151,0.4)" : "rgba(255,77,79,0.4)",
  }));

  candleSeries.setData(candleData);
  volumeSeries.setData(volumeData);

  function calcSMA(data, period) {
    const result = [];
    for (let i = 0; i < data.length; i++) {
      if (i < period - 1) {
        result.push({ time: data[i].time, value: null });
      } else {
        let sum = 0;
        for (let j = 0; j < period; j++) {
          sum += data[i - j].close;
        }
        result.push({ time: data[i].time, value: sum / period });
      }
    }
    return result;
  }

  const currentMaConfig = getMaConfig();
  maSeries = {};
  currentMaConfig.forEach(cfg => {
    const series = klineChart.addLineSeries({ color: cfg.color, lineWidth: 1, priceLineVisible: false });
    series.setData(calcSMA(candleData, cfg.period));
    maSeries[cfg.label] = { series, color: cfg.color, period: cfg.period };
  });

  const lastCandle = candleData[candleData.length - 1];
  let legendHtml = `<span style="margin-right:12px"><span style="display:inline-block;width:10px;height:10px;background:#3ddc97;border-radius:2px;margin-right:4px"></span>OHLC</span>`;
  currentMaConfig.forEach(cfg => {
    const maVal = calcSMA(candleData, cfg.period);
    const val = maVal[maVal.length - 1]?.value?.toFixed(2) || "-";
    legendHtml += `<span style="margin-right:12px"><span style="display:inline-block;width:10px;height:2px;background:${cfg.color};margin-right:4px;vertical-align:middle"></span>${cfg.label}: ${val}</span>`;
  });
  els.klineLegend.innerHTML = legendHtml;

  const buyMarkers = (result.buys || []).map((m) => ({
    time: Math.floor(new Date(m.date).getTime() / 1000),
    position: "belowBar",
    color: "#3ddc97",
    shape: "arrowUp",
    text: "B",
  }));

  const sellMarkers = (result.sells || []).map((m) => ({
    time: Math.floor(new Date(m.date).getTime() / 1000),
    position: "aboveBar",
    color: "#ff4d4f",
    shape: "arrowDown",
    text: "S",
  }));

  candleSeries.setMarkers([...buyMarkers, ...sellMarkers]);
  klineChart.timeScale().fitContent();
}

function renderEquityChart(result) {
  const canvas = els.canvas;
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const w = Math.floor(rect.width * dpr);
  const h = Math.floor(rect.height * dpr);
  const containerW = rect.width;

  const extraW = 100;
  if (canvas.width !== w + extraW || canvas.height !== h) {
    canvas.width = w + extraW;
    canvas.height = h;
    canvas.style.width = (w + extraW) / dpr + "px";
  }

  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, w, h);

  ctx.save();
  ctx.scale(1, 1);
  ctx.font = `${Math.max(12, Math.floor(containerW / 100))}px ui-sans-serif, system-ui`;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";

  if (!result || !result.equity || result.equity.length < 2) {
    drawText(ctx, "暂无回测结果", w / 2, h / 2, "rgba(170,179,214,0.9)", "center");
    ctx.restore();
    return;
  }

  const padLeft = Math.max(85, Math.floor(containerW * 0.12));
  const padRight = 20;
  const padTop = Math.floor(Math.min(containerW, h) * 0.08);
  const padBottom = Math.floor(Math.min(containerW, h) * 0.12);
  const left = padLeft;
  const right = w - padRight;
  const top = padTop;
  const bottom = h - padBottom;

  const equity = result.equity;
  const dates = equity.map((p) => p.date);
  const values = equity.map((p) => Number(p.value));
  let minV = Math.min(...values);
  let maxV = Math.max(...values);

  if (!Number.isFinite(minV) || !Number.isFinite(maxV)) {
    drawText(ctx, "数据异常", w / 2, h / 2, "rgba(255,77,79,0.9)", "center");
    ctx.restore();
    return;
  }

  if (maxV === minV) {
    maxV += 1;
    minV -= 1;
  }

  const margin = (maxV - minV) * 0.08;
  maxV += margin;
  minV -= margin;

  const n = values.length;
  const xAt = (i) => left + (i / (n - 1)) * (right - left);
  const yAt = (v) => top + ((maxV - v) / (maxV - minV)) * (bottom - top);

  ctx.strokeStyle = "rgba(255,255,255,0.08)";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 6; i++) {
    const y = top + (i / 6) * (bottom - top);
    ctx.beginPath();
    ctx.moveTo(left, y);
    ctx.lineTo(right, y);
    ctx.stroke();
  }

  ctx.fillStyle = "rgba(170,179,214,0.9)";
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  for (let i = 0; i <= 3; i++) {
    const t = i / 3;
    const v = maxV - t * (maxV - minV);
    const y = yAt(v);
    ctx.fillText(formatMoney(v), left - 30, y);
  }

  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  for (let i = 0; i < 6; i++) {
    const idx = Math.floor((i / 5) * (n - 1));
    const x = xAt(idx);
    const dateStr = dates[idx];
    ctx.fillText(dateStr ? dateStr.substring(5) : '', x, bottom + 12);
  }

  ctx.strokeStyle = "rgba(79,124,255,0.95)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(xAt(0), yAt(values[0]));
  for (let i = 1; i < n; i++) {
    ctx.lineTo(xAt(i), yAt(values[i]));
  }
  ctx.stroke();

  const dateToIndex = new Map();
  for (let i = 0; i < dates.length; i++) {
    dateToIndex.set(dates[i], i);
  }

  for (const m of result.buys || []) {
    const i = dateToIndex.get(m.date);
    if (i == null) continue;
    drawTriangle(ctx, xAt(i), yAt(values[i]), 7, "rgba(61,220,151,0.95)", "up");
  }

  for (const m of result.sells || []) {
    const i = dateToIndex.get(m.date);
    if (i == null) continue;
    drawTriangle(ctx, xAt(i), yAt(values[i]), 7, "rgba(255,77,79,0.95)", "down");
  }

  ctx.restore();
}

function renderChart(result) {
  renderKlineChart(result);
  renderEquityChart(result);
}

async function runBacktest() {
  if (!selectedStrategyId) {
    setStatus("请先选择策略");
    return;
  }

  const symbol = els.symbol.value.trim().toUpperCase();
  const cash = Number(els.cash.value);
  const startDate = els.startDate.value;
  const endDate = els.endDate.value;

  if (!symbol) return setStatus("股票代码不能为空");
  if (!Number.isFinite(cash) || cash <= 0) return setStatus("资金金额必须 > 0");
  if (!startDate || !endDate) return setStatus("请选择开始/结束时间");
  if (startDate > endDate) return setStatus("开始时间不能晚于结束时间");

  setStatus("回测中...");
  els.runBtn.disabled = true;
  els.exportBtn.disabled = true;
  renderMetrics(null);

  try {
    const res = await fetch("/api/backtest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        strategy_id: selectedStrategyId,
        symbol,
        cash,
        start_date: startDate,
        end_date: endDate,
        commission: 0.001,
      }),
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setStatus(data.detail || "回测失败");
      return;
    }

    lastResult = data;
    renderMetrics(data.metrics);
    renderChart(data);
    els.exportBtn.disabled = false;
    setStatus("完成");
  } catch (e) {
    setStatus(String(e?.message || e));
  } finally {
    els.runBtn.disabled = false;
  }
}

function setupEvents() {
  els.runBtn.addEventListener("click", runBacktest);
  els.exportBtn.addEventListener("click", exportTradesCsv);

  // 侧边栏折叠/展开
  els.toggleSidebar.addEventListener("click", () => {
    els.sidebar.classList.toggle("collapsed");
    setTimeout(() => {
      if (klineChart) {
        klineChart.resize(els.klineContainer.clientWidth, els.klineContainer.clientHeight);
      }
      renderEquityChart(lastResult);
    }, 320);
  });

  els.contextRunBacktest.addEventListener("click", () => {
    hideContextMenu();
    runBacktest();
  });
  els.contextViewSource.addEventListener("click", openSourceModal);
  els.sourceModalClose.addEventListener("click", closeSourceModal);
  els.sourceModalMask.addEventListener("click", closeSourceModal);

  document.addEventListener("click", (evt) => {
    if (!els.contextMenu.contains(evt.target)) {
      hideContextMenu();
    }
  });

  document.addEventListener("keydown", (evt) => {
    if (evt.key === "Escape") {
      hideContextMenu();
      closeSourceModal();
    }
  });

  window.addEventListener("resize", () => {
    renderEquityChart(lastResult);
    if (klineChart) {
      klineChart.applyOptions({
        width: els.klineContainer.clientWidth,
        height: els.klineContainer.clientHeight,
      });
    }
  });
}

function setup() {
  setDefaultDates();
  renderChart(null);
  setupEvents();

  loadStrategies().catch((e) => {
    setStatus(String(e?.message || e));
  });
}

setup();