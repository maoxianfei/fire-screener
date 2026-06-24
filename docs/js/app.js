(function () {
  "use strict";

  var SECTOR_CLASSES = {
    "白酒": "sector-白酒",
    "新能源": "sector-新能源",
    "医药": "sector-医药",
    "科技": "sector-科技",
    "金融": "sector-金融",
    "消费": "sector-消费",
    "通信": "sector-通信",
    "化工": "sector-化工",
    "能源": "sector-能源",
    "银行": "sector-银行",
    "食品": "sector-食品",
    "农业": "sector-农业",
    "半导体": "sector-半导体",
    "新材料": "sector-新材料",
    "机械": "sector-机械",
    "交运设备": "sector-交运设备",
    "环保": "sector-环保",
    "零售": "sector-零售",
    "汽车": "sector-汽车",
    "消费电子": "sector-消费电子",
    "传媒": "sector-传媒",
    "服装": "sector-服装",
    "家纺": "sector-家纺",
    "园区": "sector-园区",
    "物流": "sector-物流",
    "造纸": "sector-造纸",
    "军工": "sector-军工",
    "软件": "sector-软件",
    "贸易": "sector-贸易",
    "人力资源": "sector-人力资源",
    "电力": "sector-电力",
    "纺织": "sector-纺织",
    "建筑": "sector-建筑",
    "电子": "sector-电子",
    "家居": "sector-家居",
    "家电": "sector-家电"
  };

  var KNOWN_SECTORS = Object.keys(SECTOR_CLASSES);

  function $(id) {
    return document.getElementById(id);
  }

  function formatPrice(val) {
    if (val === null || val === undefined) return "-";
    return val.toFixed(2);
  }

  function renderStars(rating) {
    var r = Math.max(1, Math.min(5, rating || 0));
    var s = "";
    for (var i = 0; i < r; i++) s += "\u2605";
    for (var j = r; j < 5; j++) s += "\u2606";
    return s;
  }

  function getSectorClass(sector) {
    if (SECTOR_CLASSES[sector]) return SECTOR_CLASSES[sector];
    for (var i = 0; i < KNOWN_SECTORS.length; i++) {
      if (sector && sector.indexOf(KNOWN_SECTORS[i]) !== -1) {
        return SECTOR_CLASSES[KNOWN_SECTORS[i]];
      }
    }
    return "sector-default";
  }

  var _currentStocks = [];
  var _currentDateRange = "";

  function renderSectorStats(stocks) {
    var container = $("sector-stats");
    if (!container) return;
    if (!stocks || stocks.length === 0) {
      container.style.display = "none";
      return;
    }
    var counts = {};
    for (var i = 0; i < stocks.length; i++) {
      var sector = stocks[i].sector || "其他";
      counts[sector] = (counts[sector] || 0) + 1;
    }
    var sorted = Object.keys(counts).sort(function(a, b) { return counts[b] - counts[a]; });
    var maxCount = counts[sorted[0]];
    var html = "";
    for (var j = 0; j < sorted.length; j++) {
      var name = sorted[j];
      var count = counts[name];
      var barWidth = Math.round((count / maxCount) * 60);
      html += '<div class="sector-stat-item">' +
        '<span class="sector-stat-name">' + escHtml(name) + '</span>' +
        '<span class="sector-stat-count">' + count + '</span>' +
        '<span class="sector-stat-bar" style="width:' + barWidth + 'px"></span>' +
        '</div>';
    }
    container.innerHTML = html;
    container.style.display = "";
  }

  function renderTable(stocks) {
    _currentStocks = stocks || [];
    var tbody = $("watchlist-body");
    var emptyState = $("empty-state");
    tbody.innerHTML = "";

    if (!stocks || stocks.length === 0) {
      emptyState.style.display = "";
      return;
    }
    emptyState.style.display = "none";

    for (var i = 0; i < stocks.length; i++) {
      var s = stocks[i];
      var tr = document.createElement("tr");
      tr.setAttribute("data-code", s.code || "");
      tr.setAttribute("data-sector", s.sector || "");
      tr.setAttribute("data-rating", s.rating || 0);

      tr.innerHTML =
        '<td class="col-code">' + escHtml(s.code || "") + "</td>" +
        '<td class="col-name">' + escHtml(s.name || "") + "</td>" +
        '<td class="col-sector"><span class="sector-tag ' + getSectorClass(s.sector) + '">' + escHtml(s.sector || "") + "</span></td>" +
        '<td class="col-reason">火地晋水雷屯信号</td>' +
        '<td class="col-price">' + formatPrice(s.current_price) + "</td>" +
        '<td class="col-rating"><span class="stars">' + renderStars(s.rating) + "</span></td>";

      tbody.appendChild(tr);
    }
  }

  function updateDateRange(current) {
    _currentDateRange = (current.date_start || "") + "-" + (current.date_end || "");
    $("date-range").textContent = current.date_start + " - " + current.date_end;
    $("updated-at").textContent = current.updated_at || "-";
    // 显示筛选形态信息
    var patternEl = $("pattern-info");
    if (patternEl) {
      if (current.pattern && current.pattern_name) {
        patternEl.textContent = "形态: " + current.pattern + " (" + current.pattern_name + ")";
        patternEl.style.display = "";
      } else {
        patternEl.style.display = "none";
      }
    }
    // 更新股票数量
    var countEl = $("stocks-count");
    if (countEl && current.stocks) {
      countEl.textContent = current.stocks.length + " 只";
    }
  }

  function loadCurrent(data) {
    var current = data.current;
    if (!current) return;
    renderTable(current.stocks);
    renderSectorStats(current.stocks);
    updateDateRange(current);
  }

  function loadHistory(fileUrl) {
    $("watchlist-body").innerHTML = "";
    $("error-state").style.display = "none";
    $("empty-state").style.display = "none";

    fetch(fileUrl)
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (data) {
        renderTable(data.stocks);
        renderSectorStats(data.stocks);
        updateDateRange(data);
      })
      .catch(function () {
        $("error-state").style.display = "";
      });
  }

  function initSelector(data) {
    var selector = $("week-selector");
    selector.innerHTML = "";

    var current = data.current;
    var opt = document.createElement("option");
    opt.value = "current";
    opt.textContent = current.date_start + " - " + current.date_end + " (本周)";
    selector.appendChild(opt);

    var history = data.history || [];
    for (var i = 0; i < history.length; i++) {
      var h = history[i];
      var optH = document.createElement("option");
      optH.value = h.file;
      optH.textContent = h.date_start + " - " + h.date_end;
      selector.appendChild(optH);
    }

    selector.addEventListener("change", function () {
      var val = selector.value;
      if (val === "current") {
        loadCurrent(data);
      } else if (val) {
        loadHistory(val);
      }
    });
  }

  function exportCodes() {
    if (!_currentStocks.length) return;
    var codes = [];
    for (var i = 0; i < _currentStocks.length; i++) {
      if (_currentStocks[i].code) codes.push(_currentStocks[i].code);
    }
    var text = codes.join("\n");
    var blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = "关注股票_" + _currentDateRange.replace(/\./g, "") + ".txt";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function escHtml(str) {
    var div = document.createElement("div");
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  function init() {
    fetch("data/watchlists.json")
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (data) {
        initSelector(data);
        loadCurrent(data);
        $("export-btn").addEventListener("click", exportCodes);
      })
      .catch(function () {
        $("error-state").style.display = "";
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
