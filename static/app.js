// Backtrader Web
const els = {};

function init() {
  // Get elements
  els.list = document.getElementById("strategy-list");
  els.sidebar = document.getElementById("sidebar");
  els.toggleSidebar = document.getElementById("toggleSidebar");
  els.symbol = document.getElementById("symbol");
  els.cash = document.getElementById("cash");
  els.startDate = document.getElementById("startDate");
  els.endDate = document.getElementById("endDate");
  els.runBtn = document.getElementById("runBtn");
  els.exportBtn = document.getElementById("exportBtn");
  els.status = document.getElementById("status");
  els.metrics = document.getElementById("metrics");
  els.canvas = document.getElementById("chart");
  els.klineContainer = document.getElementById("kline-container");
  els.contextMenu = document.getElementById("strategy-context-menu");
  els.contextRunBacktest = document.getElementById("btnBacktest");
  els.contextEditSource = document.getElementById("btnEdit");
  els.contextViewSource = document.getElementById("btnView");
  els.contextDownloadStrategy = document.getElementById("btnDownload");
  els.contextDeleteStrategy = document.getElementById("btnDelete");
  els.sourceModal = document.getElementById("source-modal");
  els.sourceModalMask = document.getElementById("source-modal-mask");
  els.sourceModalClose = document.getElementById("source-modal-close");
  els.sourceTitle = document.getElementById("source-modal-title");
  els.sourceCode = document.getElementById("source-code-view");
  els.sourceEditor = document.getElementById("source-editor");
  els.sourceModalSave = document.getElementById("source-modal-save");
  els.editorLoading = document.getElementById("editor-loading");
  els.strategyUpload = document.getElementById("strategyUpload");
  els.symbolAutocomplete = document.getElementById("symbolAutocomplete");
  els.klineMetrics = document.getElementById("kline-metrics");
  els.equityMetrics = document.getElementById("equity-metrics");
  els.editorHighlight = document.getElementById("editor-highlight");

  console.log("Elements loaded");
  console.log("btnEdit:", document.getElementById("btnEdit"));
  console.log("btnView:", document.getElementById("btnView"));
  console.log("hljs:", typeof hljs);
  console.log("hljs.highlight:", typeof (hljs && hljs.highlight));

  // Set default dates
  var end = new Date();
  var start = new Date(end.getTime());
  start.setFullYear(end.getFullYear() - 10);
  els.startDate.value = formatDate(start);
  els.endDate.value = formatDate(end);

  // Setup events
  setupEvents();

  // Load strategies
  loadStrategies();
}

function formatDate(d) {
  var pad = function(n) { return String(n).padStart(2, "0"); };
  return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
}

function hideContextMenu() {
  if (els.contextMenu) els.contextMenu.classList.add("hidden");
}

function showContextMenu(x, y, strategyId) {
  contextStrategyId = strategyId;
  var menu = els.contextMenu;
  
  // 先显示菜单获取正确尺寸
  menu.classList.remove("hidden");
  
  var rect = menu.getBoundingClientRect();
  var left = Math.min(x, window.innerWidth - rect.width - 8);
  var top = Math.min(y, window.innerHeight - rect.height - 8);
  
  // 延迟设置位置确保可见
  setTimeout(function() {
    menu.style.left = Math.max(10, left) + "px";
    menu.style.top = Math.max(10, top) + "px";
  }, 10);
}

var contextStrategyId = null;
var selectedStrategyId = null;

function loadStrategies() {
  fetch("/api/strategies")
    .then(function(res) { return res.json(); })
    .then(function(data) {
      els.list.innerHTML = "";
      var items = data.items || [];
      for (var i = 0; i < items.length; i++) {
        var item = items[i];
        var div = document.createElement("div");
        div.className = "strategy-item";
        div.dataset.id = item.id;
        div.innerHTML = "<div class='strategy-name'>" + item.name + "</div><div class='strategy-id'>" + item.id + "</div>";
        
        // Click to select - store current item
        div.addEventListener("click", (function(itemId) {
          return function() {
            console.log("Click on:", itemId);
            setActive(itemId);
          };
        })(item.id));
        
        // Right click to show menu
        div.addEventListener("contextmenu", (function(itemId) {
          return function(evt) {
            evt.preventDefault();
            setActive(itemId);
            showContextMenu(evt.clientX, evt.clientY, itemId);
          };
        })(item.id));
        
        els.list.appendChild(div);
      }
      if (items.length > 0) {
        setActive(items[0].id);
      }
    });
}

function setActive(id) {
  // Remove active from all
  var nodes = els.list.querySelectorAll(".strategy-item");
  for (var i = 0; i < nodes.length; i++) {
    nodes[i].classList.remove("active");
  }
  // Add active to selected
  var node = els.list.querySelector('[data-id="' + id + '"]');
  if (node) {
    node.classList.add("active");
  }
  selectedStrategyId = id;
  console.log("Selected:", id);
}

function setupEvents() {
  // Toggle sidebar
  if (els.toggleSidebar) {
    els.toggleSidebar.addEventListener("click", function() {
      els.sidebar.classList.toggle("collapsed");
      els.toggleSidebar.textContent = els.sidebar.classList.contains("collapsed") ? "▶" : "◀";
    });
  }

  // Symbol autocomplete
  var acTimer = null;
  var acItems = [];
  var acIndex = -1;
  
  function hideAc() {
    if (els.symbolAutocomplete) els.symbolAutocomplete.classList.remove("show");
    acItems = [];
    acIndex = -1;
  }
  
  function renderAc(items) {
    if (!els.symbolAutocomplete) return;
    if (!items || items.length === 0) {
      hideAc();
      return;
    }
    els.symbolAutocomplete.innerHTML = items.map(function(item, i) {
      return '<div class="autocomplete-item' + (i === acIndex ? ' active' : '') + '" data-index="' + i + '">' + item.symbol + ' - ' + item.name + '</div>';
    }).join("");
    els.symbolAutocomplete.querySelectorAll(".autocomplete-item").forEach(function(el) {
      el.addEventListener("click", function() {
        var idx = parseInt(el.dataset.index, 10);
        if (acItems[idx]) {
          els.symbol.value = acItems[idx].symbol;
          hideAc();
        }
      });
    });
    els.symbolAutocomplete.classList.add("show");
  }
  
  function searchStocks(query, callback) {
    fetch("/api/stocks?q=" + encodeURIComponent(query))
      .then(function(res) { return res.json(); })
      .then(function(data) {
        var items = Array.isArray(data) ? data : (data.items || []);
        callback(items);
      })
      .catch(function() { callback([]); });
  }
  
  if (els.symbol) {
    els.symbol.addEventListener("input", function() {
      var query = els.symbol.value.trim().toUpperCase();
      if (!query) { hideAc(); return; }
      if (acTimer) clearTimeout(acTimer);
      acTimer = setTimeout(function() {
        searchStocks(query, function(items) {
          acItems = items.slice(0, 10);
          acIndex = -1;
          if (acItems.length > 0) renderAc(acItems);
          else hideAc();
        });
      }, 200);
    });
    els.symbol.addEventListener("keydown", function(e) {
      if (!els.symbolAutocomplete || !els.symbolAutocomplete.classList.contains("show")) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (acIndex < acItems.length - 1) { acIndex++; renderAc(acItems); }
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (acIndex > 0) { acIndex--; renderAc(acItems); }
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (acIndex >= 0 && acItems[acIndex]) {
          els.symbol.value = acItems[acIndex].symbol;
          hideAc();
          runBacktest();
        } else if (acItems.length > 0 && els.symbol.value.trim()) {
          runBacktest();
        }
      } else if (e.key === "Escape") {
        hideAc();
      }
    });
    document.addEventListener("click", function(e) {
      if (!els.symbol.contains(e.target) && !els.symbolAutocomplete.contains(e.target)) {
        hideAc();
      }
    });
  }

  els.runBtn.addEventListener("click", runBacktest);

  // Right click menu buttons - onclick instead of addEventListener
  if (els.contextRunBacktest) {
    els.contextRunBacktest.onclick = function() {
      hideContextMenu();
      runBacktest();
    };
  }

  if (els.contextEditSource) {
    els.contextEditSource.onclick = function() {
      hideContextMenu();
      openEditor();
    };
  }

  if (els.contextViewSource) {
    els.contextViewSource.onclick = function() {
      hideContextMenu();
      openViewOnly();
    };
  }

  if (els.contextDownloadStrategy) {
    els.contextDownloadStrategy.onclick = function() {
      if (!contextStrategyId) return;
      hideContextMenu();
      fetch("/api/strategies/source/" + encodeURIComponent(contextStrategyId))
        .then(function(res) { return res.json(); })
        .then(function(data) {
          var blob = new Blob([data.source || ""], {type: "text/plain;charset=utf-8"});
          var url = URL.createObjectURL(blob);
          var a = document.createElement("a");
          a.href = url;
          a.download = contextStrategyId + ".py";
          a.click();
          URL.revokeObjectURL(url);
        });
    };
  }

  if (els.contextDeleteStrategy) {
    els.contextDeleteStrategy.onclick = function() {
      if (!contextStrategyId) return;
      if (!confirm("Delete " + contextStrategyId + "?")) return;
      fetch("/api/strategies/" + encodeURIComponent(contextStrategyId), { method: "DELETE" })
        .then(function() {
          loadStrategies();
          hideContextMenu();
        });
    };
  }

  // Close modal
  if (els.sourceModalClose) {
    els.sourceModalClose.onclick = function() {
      els.sourceModal.classList.add("hidden");
    };
  }

  if (els.sourceModalMask) {
    els.sourceModalMask.onclick = function() {
      els.sourceModal.classList.add("hidden");
    };
  }

  // Save button
  if (els.sourceModalSave) {
    els.sourceModalSave.onclick = function() {
      saveAndRun();
    };
  }

  // Upload
  if (els.strategyUpload) {
    els.strategyUpload.addEventListener("change", function(evt) {
      var file = evt.target.files[0];
      if (!file) return;
      var formData = new FormData();
      formData.append("file", file);
      els.status.textContent = "Uploading...";
      fetch("/api/strategies/upload", { method: "POST", body: formData })
        .then(function(res) { return res.json(); })
        .then(function(data) {
          els.status.textContent = "Uploaded: " + file.name;
          loadStrategies();
          selectedStrategyId = data.id;
        })
        .catch(function(e) {
          els.status.textContent = e.message || e;
        });
      evt.target.value = "";
    });
  }

  // Close on click outside
  document.addEventListener("click", function(evt) {
    if (els.contextMenu && !els.contextMenu.contains(evt.target)) {
      hideContextMenu();
    }
  });

  // Escape
  document.addEventListener("keydown", function(evt) {
    if (evt.key === "Escape") {
      hideContextMenu();
      els.sourceModal.classList.add("hidden");
    }
  });
  
  // Editor sync highlight
  if (els.sourceEditor) {
    els.sourceEditor.addEventListener("input", function() {
      syncEditorHighlight(els.sourceEditor.value);
    });
    els.sourceEditor.addEventListener("scroll", function() {
      if (els.editorHighlight) {
        els.editorHighlight.scrollTop = els.sourceEditor.scrollTop;
        els.editorHighlight.scrollLeft = els.sourceEditor.scrollLeft;
      }
    });
  }
}

function openEditor() {
  if (!contextStrategyId) return;
  var strategyId = contextStrategyId;
  els.sourceTitle.textContent = "Edit - " + strategyId;
  els.sourceModal.classList.remove("hidden");
  els.sourceEditor.style.display = "block";
  els.editorHighlight.style.display = "block";
  els.sourceCode.style.display = "none";
  if (els.sourceModalSave) els.sourceModalSave.style.display = "inline-block";
  els.sourceEditor.value = "Loading...";
  els.sourceEditor.disabled = true;
  els.editorLoading.classList.remove("hidden");

  fetch("/api/strategies/source/" + encodeURIComponent(strategyId))
    .then(function(res) { return res.json(); })
    .then(function(data) {
      els.editorLoading.classList.add("hidden");
      els.sourceEditor.disabled = false;
      var source = data.source || "";
      els.sourceEditor.value = source;
      syncEditorHighlight(source);
    });
}

function openViewOnly() {
  if (!contextStrategyId) return;
  var strategyId = contextStrategyId;
  els.sourceTitle.textContent = "Source - " + strategyId;
  els.sourceModal.classList.remove("hidden");
  els.sourceEditor.style.display = "none";
  els.editorHighlight.style.display = "none";
  els.sourceCode.style.display = "block";
  if (els.sourceModalSave) els.sourceModalSave.style.display = "none";
  els.sourceCode.textContent = "Loading...";

  fetch("/api/strategies/source/" + encodeURIComponent(strategyId))
    .then(function(res) { return res.json(); })
    .then(function(data) {
      if (hljs && hljs.highlight) {
        var result = hljs.highlight(data.source || "", {language: "python"});
        els.sourceCode.innerHTML = result.value;
      } else {
        els.sourceCode.textContent = data.source || "";
      }
    });
}

function syncEditorHighlight(source) {
  if (hljs && els.editorHighlight) {
    var result = hljs.highlight(source || "", {language: "python"});
    els.editorHighlight.innerHTML = result.value;
  }
}

function saveAndRun() {
  if (!contextStrategyId) return;
  var newSource = els.sourceEditor.value;
  els.editorLoading.classList.remove("hidden");
  els.sourceEditor.disabled = true;
  els.status.textContent = "Saving...";

  fetch("/api/strategies/" + encodeURIComponent(contextStrategyId), {
    method: "PUT",
    body: newSource,
  })
    .then(function(res) { return res.json(); })
    .then(function() {
      els.sourceModal.classList.add("hidden");
      els.status.textContent = "Saved! Running backtest...";
      runBacktest();
    })
    .catch(function(e) {
      els.editorLoading.classList.add("hidden");
      els.sourceEditor.disabled = false;
      els.status.textContent = e.message || e;
    });
}

var lastResult = null;

function runBacktest() {
  if (!selectedStrategyId) {
    els.status.textContent = "Select a strategy first";
    return;
  }

  var symbol = els.symbol.value.trim().toUpperCase();
  var cash = Number(els.cash.value);
  var startDate = els.startDate.value;
  var endDate = els.endDate.value;

  if (!symbol) { els.status.textContent = "Enter stock code"; return; }
  if (!cash || cash <= 0) { els.status.textContent = "Invalid cash"; return; }
  if (!startDate || !endDate) { els.status.textContent = "Select dates"; return; }

  els.status.textContent = "Running backtest...";
  els.runBtn.disabled = true;

  fetch("/api/backtest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      strategy_id: selectedStrategyId,
      symbol: symbol,
      cash: cash,
      start_date: startDate,
      end_date: endDate,
      commission: 0.001,
    }),
  })
    .then(function(res) { return res.json(); })
    .then(function(data) {
      if (data.detail) {
        els.status.textContent = data.detail;
        return;
      }
      lastResult = data;
      renderResults(data);
      els.status.textContent = "Done";
    })
    .catch(function(e) {
      els.status.textContent = e.message || e;
    })
    .finally(function() {
      els.runBtn.disabled = false;
    });
}

function renderResults(data) {
  if (!data || !data.ohlcv || data.ohlcv.length === 0) {
    els.klineContainer.innerHTML = "<div style='padding:10px;color:#aaa'>No K-line data</div>";
    return;
  }

  // Render metrics
  var m = data.metrics;
  var fmtPct = function(x) { return Number.isFinite(Number(x)) ? Number(x).toFixed(2) + "%" : "-"; };
  var fmtRatio = function(x) { return Number.isFinite(Number(x)) ? Number(x).toFixed(3) : "-"; };
  var fmtMoney = function(x) { return Number.isFinite(x) ? x.toLocaleString(undefined, {maximumFractionDigits:2}) : "-"; };
  
  if (m) {
    els.metrics.textContent = 
      "策略:" + m.strategy + " | " +
      "期初:" + fmtMoney(m.start_cash) + " | " +
      "期末:" + fmtMoney(m.end_value) + " | " +
      "收益:" + fmtMoney(m.pnl) + "(" + fmtPct(m.return_pct) + ") | " +
      "年化:" + fmtPct(m.annual_return_pct) + " | " +
      "夏普:" + fmtRatio(m.sharpe) + " | " +
      "索提诺:" + fmtRatio(m.sortino) + " | " +
      "最大回撤:" + fmtPct(m.max_drawdown_pct) + " | " +
      "胜率:" + fmtPct(m.win_rate_pct) + " | " +
      "盈亏比:" + fmtRatio(m.avg_win_loss_ratio) + " | " +
      "卡尔马:" + fmtRatio(m.calmar) + " | " +
      "买/卖:" + m.buy_count + "/" + m.sell_count;
    
    if (els.klineMetrics) {
      els.klineMetrics.textContent = 
        "收益:" + fmtMoney(m.pnl) + " " + fmtPct(m.return_pct) + 
        " 夏普:" + fmtRatio(m.sharpe) + 
        " 胜率:" + fmtPct(m.win_rate_pct);
    }
    
    if (els.equityMetrics) {
      els.equityMetrics.textContent = 
        "期初:" + fmtMoney(m.start_cash) + 
        " 期末:" + fmtMoney(m.end_value) + 
        " 年化:" + fmtPct(m.annual_return_pct) + 
        " 最大回撤:" + fmtPct(m.max_drawdown_pct);
    }
  }

  // Render K-line using Lightweight Charts
  if (typeof LightweightCharts !== "undefined") {
    var container = els.klineContainer;
    container.innerHTML = "";
    
    var width = container.clientWidth || 800;
    var height = container.clientHeight || 420;
    
    var chart = LightweightCharts.createChart(container, {
      width: width,
      height: height,
      layout: { background: { type: "solid", color: "transparent" }, textColor: "#aab3d6" },
      grid: { vertLines: { color: "rgba(255,255,255,0.05)" }, horzLines: { color: "rgba(255,255,255,0.05)" } },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.1)" },
      timeScale: { borderColor: "rgba(255,255,255,0.1)", timeVisible: true },
    });
    
    var resizeTimer = null;
    var currentWidth = width;
    var currentHeight = height;
    var ro = new ResizeObserver(function() {
      if (resizeTimer) clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function() {
        var targetWidth = container.clientWidth;
        var targetHeight = container.clientHeight;
        var startTime = performance.now();
        var duration = 250;
        function animate(time) {
          var elapsed = time - startTime;
          var progress = Math.min(elapsed / duration, 1);
          var eased = 1 - Math.pow(1 - progress, 3);
          currentWidth = width + (targetWidth - width) * eased;
          currentHeight = height + (targetHeight - height) * eased;
          chart.resize(Math.floor(currentWidth), Math.floor(currentHeight));
          if (progress < 1) requestAnimationFrame(animate);
        }
        requestAnimationFrame(animate);
      }, 100);
    });
    ro.observe(container);
    
    var candleSeries = chart.addCandlestickSeries({
      upColor: "#3ddc97",
      downColor: "#ff4d4f",
      borderUpColor: "#3ddc97",
      borderDownColor: "#ff4d4f",
      wickUpColor: "#3ddc97",
      wickDownColor: "#ff4d4f",
    });
    
    var candleData = data.ohlcv.map(function(d) {
      return {
        time: Math.floor(new Date(d.time).getTime() / 1000),
        open: Number(d.open),
        high: Number(d.high),
        low: Number(d.low),
        close: Number(d.close),
      };
    });
    
    candleSeries.setData(candleData);
    
    // Calculate and add MA lines
    var closePrices = candleData.map(function(d) { return d.close; });
    var times = candleData.map(function(d) { return d.time; });
    var ma5 = calculateMA(closePrices, 5, times);
    var ma10 = calculateMA(closePrices, 10, times);
    var ma20 = calculateMA(closePrices, 20, times);
    
    var ma5Series = chart.addLineSeries({ color: "#ff9500", lineWidth: 1, priceLineColor: "#ff9500" });
    ma5Series.setData(ma5);
    
    var ma10Series = chart.addLineSeries({ color: "#5ac8fa", lineWidth: 1, priceLineColor: "#5ac8fa" });
    ma10Series.setData(ma10);
    
    var ma20Series = chart.addLineSeries({ color: "#af52de", lineWidth: 1, priceLineColor: "#af52de" });
    ma20Series.setData(ma20);
    
    // Add buy/sell markers
    var buyMarkers = (data.buys || []).map(function(m) {
      return {
        time: Math.floor(new Date(m.date).getTime() / 1000),
        position: "belowBar",
        color: "#3ddc97",
        shape: "arrowUp",
        text: "B",
      };
    });
    
    var sellMarkers = (data.sells || []).map(function(m) {
      return {
        time: Math.floor(new Date(m.date).getTime() / 1000),
        position: "aboveBar",
        color: "#ff4d4f",
        shape: "arrowDown",
        text: "S",
      };
    });
    
    candleSeries.setMarkers(buyMarkers.concat(sellMarkers));
    chart.timeScale().fitContent();
  } else {
    els.klineContainer.innerHTML = "<div style='padding:10px;color:#aaa'>K-line chart library not loaded</div>";
  }
  
  // Render equity curve
  if (data.equity && data.equity.length > 0) {
    renderEquityCurve(data.equity);
  }
}

function calculateMA(prices, period, times) {
  var result = [];
  for (var i = 0; i < prices.length; i++) {
    if (i < period - 1) {
      result.push({ time: times[i], value: NaN });
    } else {
      var sum = 0;
      for (var j = 0; j < period; j++) {
        sum += prices[i - j];
      }
      result.push({ time: times[i], value: sum / period });
    }
  }
  return result;
}

function renderEquityCurve(equity) {
  var canvas = els.canvas;
  var rect = canvas.getBoundingClientRect();
  var dpr = window.devicePixelRatio || 1;
  var w = Math.floor(rect.width * dpr);
  var h = Math.floor(rect.height * dpr);
  
  if (canvas.width !== w || canvas.height !== h) {
    canvas.width = w;
    canvas.height = h;
  }
  
  var ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, w, h);
  
  var values = equity.map(function(p) { return Number(p.value); });
  var dates = equity.map(function(p) { return p.date; });
  
  var minV = Math.min.apply(null, values);
  var maxV = Math.max.apply(null, values);
  
  if (maxV === minV) { maxV += 1; minV -= 1; }
  
  var padLeft = Math.floor(rect.width * 0.03);
  var padRight = 20;
  var padTop = 20;
  var padBottom = 30;
  var left = padLeft;
  var right = w - padRight;
  var top = padTop;
  var bottom = h - padBottom;
  
  var n = values.length;
  var xAt = function(i) { return left + (i / (n - 1)) * (right - left); };
  var yAt = function(v) { return top + ((maxV - v) / (maxV - minV)) * (bottom - top); };
  
  // Draw Y-axis labels (money)
  ctx.fillStyle = "rgba(170,179,214,0.9)";
  ctx.font = "12px sans-serif";
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  
  var fmtMoney = function(x) { return x >= 1000000 ? (x/1000000).toFixed(1) + "M" : x >= 1000 ? (x/1000).toFixed(0) + "K" : x.toFixed(0); };
  
  for (var i = 0; i <= 4; i++) {
    var t = i / 4;
    var v = maxV - t * (maxV - minV);
    var y = yAt(v);
    ctx.fillText(fmtMoney(v), left - 10, y);
  }
  
  // Draw X-axis labels (dates)
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  for (var i = 0; i <= 4; i++) {
    var idx = Math.floor(i * (n - 1) / 4);
    var x = xAt(idx);
    var dateStr = dates[idx] || "";
    ctx.fillText(dateStr.substring(5), x, bottom + 8);
  }
  
  // Draw the equity line
  ctx.strokeStyle = "rgba(79,124,255,0.95)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(xAt(0), yAt(values[0]));
  for (var i = 1; i < n; i++) {
    ctx.lineTo(xAt(i), yAt(values[i]));
  }
  ctx.stroke();
}

// Start
init();