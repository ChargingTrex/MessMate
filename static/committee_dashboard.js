/**
 * MessMate Committee Dashboard Charts (committee_dashboard.js)
 * -------------------------------------------------------------
 * Separate from dashboard.js on purpose: that file is asserted against by
 * tests/dashboard_tests.robot, and keeping the committee charts out of it
 * means the student dashboard suite cannot break from committee work.
 *
 * Charts:
 *   1. Today by dimension (horizontal bar, colour-coded by score)
 *   2. Committee trend (line, 7/30-day toggle, overall + per-dimension)
 *
 * The same red/amber/green thresholds as dashboard.js: <2.5 / <=3.5 / >3.5.
 */

document.addEventListener("DOMContentLoaded", function () {

  const data = window.COMMITTEE_DATA || {};
  const dimensions = data.dimensions || [];
  const dimensionData = data.dimensionData || {};
  const trendData = data.trendData || [];

  function scoreColor(score) {
    if (score < 2.5) return "#EF5350";   // Red
    if (score <= 3.5) return "#FFB300";  // Amber
    return "#66BB6A";                    // Green
  }

  // ---------------------------------------------------------
  // 1. Today by dimension
  // ---------------------------------------------------------
  const dimCanvas = document.getElementById("dimensionChart");
  if (dimCanvas) {
    const labels = [];
    const scores = [];
    const colors = [];
    const counts = [];

    dimensions.forEach(dim => {
      const entry = dimensionData[dim] || { avg: 0, count: 0 };
      if (entry.avg > 0) {
        labels.push(dim);
        scores.push(entry.avg);
        colors.push(scoreColor(entry.avg));
        counts.push(entry.count);
      }
    });

    if (labels.length === 0) {
      const wrapper = dimCanvas.parentElement;
      if (wrapper) {
        wrapper.innerHTML = '<div class="empty-state">No committee reviews today yet.</div>';
      }
    } else {
      new Chart(dimCanvas.getContext("2d"), {
        type: "bar",
        data: {
          labels: labels,
          datasets: [{
            label: "Average Score",
            data: scores,
            backgroundColor: colors,
            borderWidth: 0,
            borderRadius: 4
          }]
        },
        options: {
          indexAxis: "y",
          responsive: true,
          maintainAspectRatio: false,
          scales: { x: { beginAtZero: true, min: 0, max: 5, ticks: { stepSize: 1 } } },
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: function (context) {
                  return [
                    " Avg Score: " + context.parsed.x.toFixed(1),
                    " Rated by: " + counts[context.dataIndex] + " member(s)"
                  ];
                }
              }
            }
          }
        }
      });
    }
  }

  // ---------------------------------------------------------
  // 2. Committee trend — 7 / 30 day toggle
  // ---------------------------------------------------------
  const trendCanvas = document.getElementById("committeeTrendChart");
  let trendChart = null;

  // Distinct hues per dimension; overall stays the MessMate blue
  const dimensionColors = {
    Taste: "#8E24AA", Quality: "#00897B", Variety: "#F4511E",
    Hygiene: "#3949AB", Menu: "#7CB342"
  };

  function renderTrend(days) {
    if (!trendCanvas) return;

    const title = document.getElementById("committeeTrendTitle");
    if (title) {
      title.innerText = days === 7 ? "7-Day Committee Trend" : "30-Day Committee Trend";
    }

    // Keep a reference to the slice — the tooltip indexes into THIS array,
    // not the full trendData, or the counts misalign on the 7-day view
    const sliced = trendData.slice(-days);
    const labels = sliced.length ? sliced.map(r => r.Date) : ["No Data"];

    const datasets = [{
      label: "Overall",
      data: sliced.length ? sliced.map(r => r.Avg_Overall) : [0],
      borderColor: "#2E75B6",
      backgroundColor: "rgba(46, 117, 182, 0.1)",
      borderWidth: 3,
      tension: 0.4,
      fill: true,
      pointBackgroundColor: "#1F4E79",
      pointRadius: 4
    }];

    // Per-dimension lines start hidden so the overall trend reads clearly;
    // clicking a legend entry brings one in
    dimensions.forEach(dim => {
      datasets.push({
        label: dim,
        data: sliced.map(r => r[dim] || 0),
        borderColor: dimensionColors[dim] || "#888",
        borderWidth: 2,
        tension: 0.4,
        fill: false,
        pointRadius: 3,
        hidden: true
      });
    });

    const tooltipLabel = function (context) {
      const point = sliced[context.dataIndex];
      const value = context.parsed.y.toFixed(1);
      if (context.datasetIndex === 0 && point) {
        return [" Overall: " + value, " Reviews: " + (point.Response_Count || 0)];
      }
      return " " + context.dataset.label + ": " + value;
    };

    if (trendChart) {
      trendChart.data.labels = labels;
      trendChart.data.datasets.forEach((ds, i) => { ds.data = datasets[i].data; });
      trendChart.options.plugins.tooltip.callbacks.label = tooltipLabel;
      trendChart.update();
      return;
    }

    trendChart = new Chart(trendCanvas.getContext("2d"), {
      type: "line",
      data: { labels: labels, datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { y: { beginAtZero: true, min: 0, max: 5, ticks: { stepSize: 1 } } },
        plugins: {
          legend: { display: true, position: "bottom" },
          tooltip: { callbacks: { label: tooltipLabel } }
        }
      }
    });
  }

  renderTrend(7);

  const btn7 = document.getElementById("btnCommittee7");
  const btn30 = document.getElementById("btnCommittee30");
  if (btn7 && btn30) {
    btn7.addEventListener("click", () => {
      btn7.classList.add("active"); btn30.classList.remove("active");
      renderTrend(7);
    });
    btn30.addEventListener("click", () => {
      btn30.classList.add("active"); btn7.classList.remove("active");
      renderTrend(30);
    });
  }
});
