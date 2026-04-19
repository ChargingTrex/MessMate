/**
 * MessMate Dashboard Charts Initialization (dashboard.js)
 * --------------------------------------------------------
 * Renders Chart.js visualizations on the Admin Dashboard.
 * Data is injected by the Flask backend via window.MESSMATE_DATA in the template.
 *
 * Charts:
 *   1. Overall Trend Line Chart (7-day / 30-day toggle)
 *   2. Today's Per-Item Scores Horizontal Bar Chart
 *
 * CRITICAL: The tooltip callback indexes into slicedData (not the full trendData array).
 * This prevents misaligned tooltips when viewing 7-day subset of 30-day data.
 */

document.addEventListener("DOMContentLoaded", function () {

  const data = window.MESSMATE_DATA;

  // ---------------------------------------------------------
  // 1. Trend Chart (Line Chart) — 7 Day / 30 Day Toggle
  // ---------------------------------------------------------
  const trendCanvas = document.getElementById("trendChart");
  let trendChartInstance = null;
  const trendData = data.trendData || [];

  function renderTrendChart(days) {
    if (!trendCanvas) return;

    // Update chart title based on toggle
    const titleEl = document.getElementById("trendChartTitle");
    if (titleEl) {
      titleEl.innerText = days === 7 ? "7-Day Overall Trend" : "30-Day Overall Trend";
    }

    // CRITICAL: Slice the data and keep a reference for the tooltip callback
    const slicedData = trendData.slice(-days);

    let labels = [];
    let avgScores = [];

    if (slicedData.length > 0) {
      labels = slicedData.map(row => row.Date);
      avgScores = slicedData.map(row => row.Avg_Overall);
    } else {
      labels = ["No Data"];
      avgScores = [0];
    }

    if (trendChartInstance) {
      // Update existing chart instead of recreating
      trendChartInstance.data.labels = labels;
      trendChartInstance.data.datasets[0].data = avgScores;

      // CRITICAL: Update the tooltip callback to use the NEW slicedData reference
      trendChartInstance.options.plugins.tooltip.callbacks.label = function(context) {
        const point = slicedData[context.dataIndex];
        if (!point) return "";
        const avg = context.parsed.y.toFixed(1);
        const count = point.Response_Count || 0;
        return [" Avg Score: " + avg, " Responses: " + count];
      };

      trendChartInstance.update();
    } else {
      // Create chart for the first time
      const trendCtx = trendCanvas.getContext("2d");
      trendChartInstance = new Chart(trendCtx, {
        type: "line",
        data: {
          labels: labels,
          datasets: [{
            label: "Overall Avg Score",
            data: avgScores,
            borderColor: "#2E75B6",
            backgroundColor: "rgba(46, 117, 182, 0.1)",
            borderWidth: 3,
            tension: 0.4,
            fill: true,
            pointBackgroundColor: "#1F4E79",
            pointRadius: 4,
            pointHoverRadius: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: {
              beginAtZero: true,
              min: 0,
              max: 5,
              ticks: { stepSize: 1 }
            }
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: function(context) {
                  // Use slicedData — NOT trendData — to prevent index misalignment
                  const point = slicedData[context.dataIndex];
                  if (!point) return "";
                  const avg = context.parsed.y.toFixed(1);
                  const count = point.Response_Count || 0;
                  return [" Avg Score: " + avg, " Responses: " + count];
                }
              }
            }
          }
        }
      });
    }
  }

  // Initial render — show 7 days
  renderTrendChart(7);

  // Toggle event listeners
  const btn7Days = document.getElementById("btn7Days");
  const btn30Days = document.getElementById("btn30Days");

  if (btn7Days && btn30Days) {
    btn7Days.addEventListener("click", () => {
      btn7Days.classList.add("active");
      btn30Days.classList.remove("active");
      renderTrendChart(7);
    });

    btn30Days.addEventListener("click", () => {
      btn30Days.classList.add("active");
      btn7Days.classList.remove("active");
      renderTrendChart(30);
    });
  }

  // ---------------------------------------------------------
  // 2. Per-Item Scores Chart (Horizontal Bar Chart)
  // ---------------------------------------------------------
  const itemCanvas = document.getElementById("itemChart");

  if (itemCanvas) {
    const itemCtx = itemCanvas.getContext("2d");
    const itemDataRaw = data.itemData || {};

    // Item keys in display order
    const itemKeys = [
      "Rice_Curry", "Rice_Rasam", "Chapati", "Chapati_Gravy",
      "Poriyal", "Sweet", "Salad", "Curd", "Papad", "Pickle"
    ];

    // Readable display names
    const displayNames = {
      "Rice_Curry": "Rice + Curry",
      "Rice_Rasam": "Rice + Rasam",
      "Chapati": "Chapati",
      "Chapati_Gravy": "Chapati + Gravy",
      "Poriyal": "Poriyal",
      "Sweet": "Sweet / Fruits",
      "Salad": "Salad",
      "Curd": "Curd",
      "Papad": "Papad",
      "Pickle": "Pickle / Thogayal"
    };

    let chartLabels = [];
    let chartScores = [];
    let bgColors = [];
    // Track which keys are plotted (for tooltip indexing)
    let plottedKeys = [];

    // Only show items with avg > 0 (skip unrated items)
    itemKeys.forEach(key => {
      const itemVal = itemDataRaw[key] || { avg: 0, count: 0 };
      const score = itemVal.avg || 0;
      if (score > 0) {
        chartLabels.push(displayNames[key]);
        chartScores.push(score);
        plottedKeys.push(key);

        // Color bars by score: <2.5=red, 2.5-3.5=amber, >3.5=green
        if (score < 2.5) {
          bgColors.push("#EF5350");  // Red
        } else if (score <= 3.5) {
          bgColors.push("#FFB300");  // Amber
        } else {
          bgColors.push("#66BB6A");  // Green
        }
      }
    });

    // Empty state handling
    if (chartLabels.length === 0) {
      // Show a centered message instead of an empty chart
      const wrapper = itemCanvas.parentElement;
      if (wrapper) {
        wrapper.innerHTML = '<div class="empty-state">No item ratings yet.</div>';
      }
    } else {
      new Chart(itemCtx, {
        type: "bar",
        data: {
          labels: chartLabels,
          datasets: [{
            label: "Average Score",
            data: chartScores,
            backgroundColor: bgColors,
            borderWidth: 0,
            borderRadius: 4
          }]
        },
        options: {
          indexAxis: "y",  // Horizontal bar chart
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: {
              beginAtZero: true,
              min: 0,
              max: 5,
              ticks: { stepSize: 1 }
            }
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: function(context) {
                  const key = plottedKeys[context.dataIndex];
                  const item = itemDataRaw[key];
                  const avg = item?.avg ? item.avg.toFixed(1) : "N/A";
                  const count = item?.count || 0;
                  return [" Avg Score: " + avg, " Rated by: " + count + " students"];
                }
              }
            }
          }
        }
      });
    }
  }

});
