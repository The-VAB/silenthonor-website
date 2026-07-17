/*
 * Shared dashboard widget helpers - reused across dashboard.html, admin.html,
 * and counselor-*.html so the same trend badge / ApexCharts theme isn't
 * hand-rolled on every page. Extracted from dashboard.html (PR #5).
 *
 * Requires: ApexCharts loaded via <script src="https://cdn.jsdelivr.net/npm/apexcharts"></script>
 * before this file, and css/dashboard-widgets.css linked for the accompanying classes.
 */

/**
 * Sets a stat-trend badge (arrow + magnitude) on an element produced by the
 * .stat-trend markup pattern. Never invents a value - pass a real number
 * (or null/undefined to leave the badge hidden) sourced from the backend.
 * @param {string} elId - id of the .stat-trend element
 * @param {number|null|undefined} delta - signed change value (e.g. +12, -5)
 * @param {string} [suffix] - text appended after the magnitude, e.g. "(30d)"
 */
function setStatTrend(elId, delta, suffix) {
  var el = document.getElementById(elId);
  if (!el || typeof delta !== "number" || delta === 0) return;
  var isUp = delta > 0;
  el.className = "stat-trend " + (isUp ? "up" : "down");
  var arrow = isUp
    ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M12 19V5M5 12l7-7 7 7"/></svg>'
    : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M12 5v14M5 12l7 7 7-7"/></svg>';
  el.innerHTML = arrow + Math.abs(delta) + (suffix ? " " + suffix : "");
  el.style.display = "inline-flex";
}

/**
 * Standard dark-navy ApexCharts theme options for area/line series, matching
 * the Credit Score Trend chart pattern from dashboard.html. Pass series/
 * colors/categories built from real API data - this function does not
 * fabricate data, only supplies consistent chart chrome.
 * @param {{series: Array, colors: Array, categories: Array, height?: number}} cfg
 */
function buildDashboardAreaChartOptions(cfg) {
  return {
    chart: {
      type: "area",
      height: cfg.height || 260,
      toolbar: { show: false },
      fontFamily: "'Barlow', sans-serif",
      background: "transparent"
    },
    series: cfg.series,
    colors: cfg.colors,
    theme: { mode: "dark" },
    stroke: { curve: "smooth", width: 2 },
    fill: {
      type: "gradient",
      gradient: { shadeIntensity: 1, type: "vertical", opacityFrom: 0.35, opacityTo: 0 }
    },
    dataLabels: { enabled: false },
    grid: {
      borderColor: "rgba(148, 163, 184, 0.15)",
      strokeDashArray: 3,
      yaxis: { lines: { show: true } },
      xaxis: { lines: { show: false } }
    },
    xaxis: {
      categories: cfg.categories,
      labels: { style: { colors: "#94a3b8", fontSize: "11px" } },
      axisBorder: { color: "rgba(148, 163, 184, 0.2)" },
      axisTicks: { color: "rgba(148, 163, 184, 0.2)" }
    },
    yaxis: {
      labels: { style: { colors: "#94a3b8", fontSize: "11px" } }
    },
    legend: { show: false },
    tooltip: { theme: "dark" }
  };
}

/**
 * Renders a chart-legend-item list (dot + label) matching .chart-legend markup,
 * for use alongside buildDashboardAreaChartOptions when legend: {show:false}.
 * @param {Array<{name: string, color: string}>} items
 */
function renderChartLegend(items) {
  return items.map(function (item) {
    return '<span class="chart-legend-item"><span class="chart-legend-dot" style="background:' + item.color + '"></span>' + item.name + '</span>';
  }).join("");
}

/**
 * Renders an ApexCharts area/line chart into elId only if at least one series
 * has real data, otherwise leaves the pre-existing empty-state markup visible.
 * Mirrors the "honest empty state, never fabricate" pattern from dashboard.html.
 * @param {{chartElId: string, emptyElId: string, wrapElId: string, legendElId?: string, series: Array, colors: Array, categories: Array}} cfg
 */
function renderDashboardTrendChart(cfg) {
  var hasData = cfg.series.some(function (s) {
    return s.data && s.data.some(function (v) { return v != null; });
  });
  if (!hasData) return false;

  var emptyEl = document.getElementById(cfg.emptyElId);
  var wrapEl = document.getElementById(cfg.wrapElId);
  if (emptyEl) emptyEl.style.display = "none";
  if (wrapEl) wrapEl.style.display = "block";
  if (cfg.legendElId) {
    var legendEl = document.getElementById(cfg.legendElId);
    if (legendEl) {
      legendEl.innerHTML = renderChartLegend(cfg.series.map(function (s, i) {
        return { name: s.name, color: cfg.colors[i] };
      }));
    }
  }

  var chartEl = document.getElementById(cfg.chartElId);
  if (window.ApexCharts && chartEl) {
    var chart = new ApexCharts(chartEl, buildDashboardAreaChartOptions({
      series: cfg.series,
      colors: cfg.colors,
      categories: cfg.categories
    }));
    chart.render();
    return true;
  }
  return false;
}
