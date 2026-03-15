/**
 * MessMate Dashboard Graphics Initialization (dashboard.js)
 * ---------------------------------------------------------
 * This file initializes and renders the Chart.js visualizations found on
 * the Admin Dashboard. It parses JSON payload data injected by the Flask backend
 * (window.MESSMATE_DATA) and renders the 7-day/30-day Trend Line Chart and
 * the Today's Per-Item Scores Bar Chart. It also handles the toggle logic
 * for switching between views.
 */

/**
 * MessMate Dashboard Charts Initialization
 * Expected data structure injected in window.MESSMATE_DATA by Jinja2 template.
 */

document.addEventListener("DOMContentLoaded", function () {
  
  const data = window.MESSMATE_DATA;
  
  // ---------------------------------------------------------
  // 1. Initialize Trend Chart (Line Chart)
  // ---------------------------------------------------------
  const trendCanvas = document.getElementById("trendChart");
  let trendChartInstance = null;
  const trendData = data.trendData || [];

  function renderTrendChart(days) {
    if (!trendCanvas) return;
    
    const titleEl = document.getElementById("trendChartTitle");
    if (titleEl) {
      titleEl.innerText = days === 7 ? "7-Day Overall Trend" : "30-Day Overall Trend";
    }

    // Slice the data for the requested number of days
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
      trendChartInstance.data.labels = labels;
      trendChartInstance.data.datasets[0].data = avgScores;
      trendChartInstance.update();
    } else {
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
                  return `Score: ${context.parsed.y.toFixed(1)}`;
                }
              }
            }
          }
        }
      });
    }
  }

  // Initial Render (7 Days)
  renderTrendChart(7);

  // Toggle Event Listeners
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
      // Use 30 or however many elements there are
      renderTrendChart(30); 
    });
  }

  // ---------------------------------------------------------
  // 2. Initialize Per-Item Scores Chart (Horizontal Bar Chart)
  // ---------------------------------------------------------
  const itemCanvas = document.getElementById("itemChart");
  
  if (itemCanvas) {
    const itemCtx = itemCanvas.getContext("2d");
    
    // Parse item_data: dict of {item_name: avg_score}
    const itemDataRaw = data.itemData || {};
    
    // Item mapping to display names (in requested order from prompt)
    const itemLabels = [
      "Rice_Curry", "Rice_Rasam", "Chapati", "Chapati_Gravy",
      "Poriyal", "Sweet", "Salad", "Curd", "Papad", "Pickle"
    ];
    
    const displayNames = {
      "Rice_Curry": "Rice + Curry",
      "Rice_Rasam": "Rice + Rasam",
      "Chapati": "Chapati",
      "Chapati_Gravy": "Chapati + Gravy",
      "Poriyal": "Poriyal",
      "Sweet": "Sweet/Fruits",
      "Salad": "Salad",
      "Curd": "Curd",
      "Papad": "Papad",
      "Pickle": "Pickle/Thogayal"
    };
    
    let chartLabels = [];
    let chartScores = [];
    let bgColors = [];
    
    // We only show items that have data (score > 0)
    itemLabels.forEach(key => {
      const score = itemDataRaw[key] || 0;
      if (score > 0) {
        chartLabels.push(displayNames[key]);
        chartScores.push(score);
        
        // Color coding dynamically based on score
        if (score < 2.5) {
          bgColors.push("#EF5350"); // Red
        } else if (score <= 3.5) {
          bgColors.push("#FFB300"); // Amber
        } else {
          bgColors.push("#66BB6A"); // Green
        }
      }
    });
    
    // Empty state handling
    if (chartLabels.length === 0) {
      chartLabels = ["No Data Yet"];
      chartScores = [0];
      bgColors = ["#e0e0e0"];
    }
    
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
        indexAxis: 'y', // Makes it a horizontal bar chart
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            beginAtZero: true,
            min: 0,
            max: 5,
            ticks: {
              stepSize: 1
            }
          }
        },
        plugins: {
          legend: {
            display: false
          },
          tooltip: {
            callbacks: {
              label: function(context) {
                return `Score: ${context.parsed.x.toFixed(1)}`;
              }
            }
          }
        }
      }
    });
  }

});
