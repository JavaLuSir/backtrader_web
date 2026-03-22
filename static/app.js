const els = {
  list: document.getElementById("strategy-list"),
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
};

let selectedStrategyId = null;
let lastResult = null;

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
  const parts = [
    `策略: ${metrics.strategy}`,
    `期初: ${formatMoney(metrics.start_cash)}`,
    `期末: ${formatMoney(metrics.end_value)}`,
    `收益: ${formatMoney(metrics.pnl)} (${metrics.return_pct.toFixed(2)}%)`,
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
  const metrics = (result && result.metrics) || {};
  const symbol = metrics.symbol || "";
  const strategy = metrics.strategy || "";
  const start = metrics.start_date || "";
  const end = metrics.end_date || "";

  const trades = [...((result && result.buys) || []), ...((result && result.sells) || [])];
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
    div.addEventListener("click", () => selectStrategy(item.id));
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

let klineChart = null;
let candleSeries = null;
let volumeSeries = null;

function renderKlineChart(result) {
  const container = els.klineContainer;
  
  if (!result || !result.ohlcv || result.ohlcv.length === 0) {
    container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--muted);">暂无K线数据</div>';
    return;
  }

  container.innerHTML = '';

  klineChart = LightweightCharts.createChart(container, {
    layout: {
      background: { type: 'solid', color: 'transparent' },
      textColor: '#aab3d6',
    },
    grid: {
      vertLines: { color: 'rgba(255,255,255,0.05)' },
      horzLines: { color: 'rgba(255,255,255,0.05)' },
    },
    crosshair: {
      mode: LightweightCharts.CrosshairMode.Normal,
    },
    rightPriceScale: {
      borderColor: 'rgba(255,255,255,0.1)',
    },
    timeScale: {
      borderColor: 'rgba(255,255,255,0.1)',
      timeVisible: true,
    },
    handleScroll: { vertTouchDrag: false },
  });

  candleSeries = klineChart.addCandlestickSeries({
    upColor: '#3ddc97',
    downColor: '#ff4d4f',
    borderUpColor: '#3ddc97',
    borderDownColor: '#ff4d4f',
    wickUpColor: '#3ddc97',
    wickDownColor: '#ff4d4f',
  });

  volumeSeries = klineChart.addHistogramSeries({
    color: '#26a69a',
    priceFormat: { type: 'volume' },
    priceScaleId: '',
  });
  volumeSeries.priceScale().applyOptions({
    scaleMargins: { top: 0.8, bottom: 0 },
  });

  const ohlcvData = result.ohlcv.map(d => ({
    time: d.time,
    open: d.open,
    high: d.high,
    low: d.low,
    close: d.close,
  }));

  const volumeData = result.ohlcv.map(d => ({
    time: d.time,
    value: d.volume,
    color: d.close >= d.open ? 'rgba(61,220,151,0.4)' : 'rgba(255,77,79,0.4)',
  }));

  candleSeries.setData(ohlcvData);
  volumeSeries.setData(volumeData);

  const buys = result.buys || [];
  const sells = result.sells || [];

  const buyMarkers = buys.map(m => ({
    time: m.date,
    position: 'belowBar',
    color: '#3ddc97',
    shape: 'arrowUp',
    text: 'B',
  }));

  const sellMarkers = sells.map(m => ({
    time: m.date,
    position: 'aboveBar',
    color: '#ff4d4f',
    shape: 'arrowDown',
    text: 'S',
  }));

  candleSeries.setMarkers([...buyMarkers, ...sellMarkers]);

  const resizeObserver = new ResizeObserver(() => {
    if (klineChart) {
      klineChart.applyOptions({
        width: container.clientWidth,
        height: container.clientHeight,
      });
    }
  });
  resizeObserver.observe(container);

  klineChart.timeScale().fitContent();
}

function renderEquityChart(result) {
  const canvas = els.canvas;
  const changed = resizeCanvasToDisplaySize(canvas);
  if (!changed && !result) return;

  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;

  ctx.clearRect(0, 0, w, h);

  ctx.save();
  ctx.scale(1, 1);
  ctx.font = `${Math.max(12, Math.floor(w / 100))}px ui-sans-serif, system-ui`;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";

  if (!result || !result.equity || result.equity.length < 2) {
    drawText(ctx, "暂无回测结果", w / 2, h / 2, "rgba(170,179,214,0.9)", "center");
    ctx.restore();
    return;
  }

  const pad = Math.floor(Math.min(w, h) * 0.09);
  const left = pad;
  const right = w - pad;
  const top = pad;
  const bottom = h - pad;

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
  const gridLines = 6;
  for (let i = 0; i <= gridLines; i++) {
    const y = top + (i / gridLines) * (bottom - top);
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
    ctx.fillText(formatMoney(v), left - 10, y);
  }

  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  const xTicks = 6;
  for (let i = 0; i < xTicks; i++) {
    const idx = Math.floor((i / (xTicks - 1)) * (n - 1));
    const x = xAt(idx);
    ctx.fillText(dates[idx], x, bottom + 10);
  }

  ctx.strokeStyle = "rgba(79,124,255,0.95)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(xAt(0), yAt(values[0]));
  for (let i = 1; i < n; i++) ctx.lineTo(xAt(i), yAt(values[i]));
  ctx.stroke();

  const dateToIndex = new Map();
  for (let i = 0; i < dates.length; i++) dateToIndex.set(dates[i], i);

  const buys = result.buys || [];
  const sells = result.sells || [];

  for (const m of buys) {
    const i = dateToIndex.get(m.date);
    if (i == null) continue;
    drawTriangle(ctx, xAt(i), yAt(values[i]), 7, "rgba(61,220,151,0.95)", "up");
  }
  for (const m of sells) {
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

function setup() {
  setDefaultDates();
  renderChart(null);
  loadStrategies().catch((e) => setStatus(String(e?.message || e)));

  els.runBtn.addEventListener("click", runBacktest);
  els.exportBtn.addEventListener("click", exportTradesCsv);
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

setup();

