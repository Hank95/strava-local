/**
 * Chart.js Configuration Factory
 * Provides consistent, polished chart configurations for Strava Local
 */

const ChartConfig = {
  // Color palette matching CSS design system
  colors: {
    primary: '#FC4C02',
    primaryLight: 'rgba(252, 76, 2, 0.1)',

    // Activity types
    run: '#FC4C02',
    ride: '#2196F3',
    virtualride: '#2196F3',
    swim: '#00BCD4',
    walk: '#8BC34A',
    hike: '#4CAF50',
    workout: '#9C27B0',
    yoga: '#9C27B0',
    weighttraining: '#795548',
    golf: '#FFEB3B',
    other: '#607D8B',

    // Metrics
    ctl: '#2196F3',
    atl: '#FF9800',
    tsbPositive: '#4CAF50',
    tsbNegative: '#F44336',
    hr: '#E91E63',
    elevation: '#4CAF50',
    pace: '#FF9800',
    power: '#9C27B0',

    // Generic palette for multiple series
    palette: [
      '#FC4C02', '#2196F3', '#4CAF50', '#8BC34A', '#00BCD4',
      '#9C27B0', '#FF9800', '#F44336', '#795548', '#607D8B'
    ],

    // Neutral
    grid: 'rgba(0, 0, 0, 0.05)',
    gridDark: 'rgba(0, 0, 0, 0.1)',
    text: '#1a1a1a',
    textMuted: '#6c757d',
  },

  /**
   * Get color for an activity type
   */
  getActivityColor(type) {
    if (!type) return this.colors.other;
    const key = type.toLowerCase().replace(/\s+/g, '');
    return this.colors[key] || this.colors.other;
  },

  /**
   * Get color with alpha transparency
   */
  withAlpha(color, alpha) {
    // Handle hex colors
    if (color.startsWith('#')) {
      const r = parseInt(color.slice(1, 3), 16);
      const g = parseInt(color.slice(3, 5), 16);
      const b = parseInt(color.slice(5, 7), 16);
      return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }
    return color;
  },

  /**
   * Default chart options for consistent styling
   */
  defaults: {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      intersect: false,
      mode: 'index',
    },
    plugins: {
      legend: {
        display: true,
        position: 'top',
        align: 'end',
        labels: {
          usePointStyle: true,
          pointStyle: 'circle',
          padding: 16,
          font: {
            size: 12,
            weight: '500',
          },
          color: '#6c757d',
        },
      },
      tooltip: {
        backgroundColor: 'rgba(0, 0, 0, 0.85)',
        titleFont: { size: 13, weight: '600' },
        bodyFont: { size: 12 },
        padding: 12,
        cornerRadius: 8,
        displayColors: true,
        boxPadding: 4,
        usePointStyle: true,
      },
    },
    scales: {
      x: {
        grid: {
          display: false,
        },
        ticks: {
          font: { size: 11 },
          color: '#6c757d',
        },
      },
      y: {
        grid: {
          color: 'rgba(0, 0, 0, 0.05)',
          drawBorder: false,
        },
        ticks: {
          font: { size: 11 },
          color: '#6c757d',
        },
      },
    },
  },

  /**
   * Create a doughnut chart configuration
   */
  doughnut(labels, data, options = {}) {
    const colors = labels.map((label, i) =>
      this.getActivityColor(label) || this.colors.palette[i % this.colors.palette.length]
    );

    return {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{
          data,
          backgroundColor: colors,
          borderWidth: 0,
          hoverOffset: 8,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '65%',
        plugins: {
          legend: {
            position: 'right',
            labels: {
              usePointStyle: true,
              pointStyle: 'circle',
              padding: 12,
              font: { size: 11, weight: '500' },
              color: '#6c757d',
              generateLabels: (chart) => {
                const data = chart.data;
                if (data.labels.length && data.datasets.length) {
                  const total = data.datasets[0].data.reduce((a, b) => a + b, 0);
                  return data.labels.map((label, i) => {
                    const value = data.datasets[0].data[i];
                    const pct = total > 0 ? ((value / total) * 100).toFixed(0) : 0;
                    return {
                      text: `${label} (${pct}%)`,
                      fillStyle: data.datasets[0].backgroundColor[i],
                      hidden: false,
                      index: i,
                      pointStyle: 'circle',
                    };
                  });
                }
                return [];
              },
            },
          },
          tooltip: {
            ...this.defaults.plugins.tooltip,
            callbacks: {
              label: (ctx) => {
                const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                const percentage = total > 0 ? ((ctx.raw / total) * 100).toFixed(1) : 0;
                return `${ctx.label}: ${ctx.raw} (${percentage}%)`;
              },
            },
          },
        },
        ...options,
      },
    };
  },

  /**
   * Create a bar chart configuration
   */
  bar(labels, datasets, options = {}) {
    const processedDatasets = datasets.map((ds, i) => ({
      ...ds,
      backgroundColor: ds.backgroundColor || this.colors.palette[i],
      borderRadius: 4,
      borderSkipped: false,
      maxBarThickness: 40,
    }));

    return {
      type: 'bar',
      data: {
        labels,
        datasets: processedDatasets,
      },
      options: {
        ...this.defaults,
        plugins: {
          ...this.defaults.plugins,
          legend: {
            display: datasets.length > 1,
            ...this.defaults.plugins.legend,
          },
        },
        scales: {
          ...this.defaults.scales,
          y: {
            ...this.defaults.scales.y,
            beginAtZero: true,
          },
        },
        ...options,
      },
    };
  },

  /**
   * Create a line chart configuration
   */
  line(labels, datasets, options = {}) {
    const processedDatasets = datasets.map((ds) => ({
      tension: 0.4,
      pointRadius: 0,
      pointHoverRadius: 5,
      pointHoverBackgroundColor: ds.borderColor,
      borderWidth: 2,
      fill: false,
      ...ds,
    }));

    return {
      type: 'line',
      data: {
        labels,
        datasets: processedDatasets,
      },
      options: {
        ...this.defaults,
        interaction: {
          intersect: false,
          mode: 'index',
        },
        ...options,
      },
    };
  },

  /**
   * Create an area chart (filled line)
   */
  area(labels, data, color, options = {}) {
    return this.line(labels, [{
      data,
      borderColor: color,
      backgroundColor: this.withAlpha(color, 0.1),
      fill: true,
    }], {
      plugins: {
        ...this.defaults.plugins,
        legend: { display: false },
      },
      ...options,
    });
  },

  /**
   * Training load chart (CTL/ATL/TSB)
   */
  trainingLoad(labels, data, options = {}) {
    return this.line(labels, [
      {
        label: 'CTL (Fitness)',
        data: data.ctl,
        borderColor: this.colors.ctl,
        backgroundColor: this.withAlpha(this.colors.ctl, 0.1),
        fill: true,
      },
      {
        label: 'ATL (Fatigue)',
        data: data.atl,
        borderColor: this.colors.atl,
      },
      {
        label: 'TSB (Form)',
        data: data.tsb,
        borderColor: this.colors.tsbPositive,
        hidden: true,
        segment: {
          borderColor: (ctx) => {
            if (ctx.p1.parsed.y < 0) return this.colors.tsbNegative;
            return this.colors.tsbPositive;
          },
        },
      },
    ], {
      plugins: {
        ...this.defaults.plugins,
        tooltip: {
          ...this.defaults.plugins.tooltip,
          callbacks: {
            afterBody: (ctx) => {
              if (data.tss && ctx[0]) {
                const idx = ctx[0].dataIndex;
                return `Daily TSS: ${data.tss[idx] || 0}`;
              }
              return '';
            },
          },
        },
      },
      ...options,
    });
  },

  /**
   * Elevation profile chart
   */
  elevationProfile(labels, data, options = {}) {
    return {
      type: 'line',
      data: {
        labels,
        datasets: [{
          data,
          borderColor: this.colors.elevation,
          backgroundColor: this.withAlpha(this.colors.elevation, 0.15),
          fill: true,
          tension: 0.2,
          pointRadius: 0,
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            ...this.defaults.plugins.tooltip,
            callbacks: {
              title: (ctx) => `Distance: ${ctx[0].label}`,
              label: (ctx) => `Elevation: ${ctx.raw} m`,
            },
          },
        },
        scales: {
          x: {
            display: true,
            grid: { display: false },
            ticks: {
              maxTicksLimit: 6,
              color: '#6c757d',
              font: { size: 10 },
            },
          },
          y: {
            beginAtZero: false,
            grid: { color: 'rgba(0,0,0,0.05)' },
            ticks: {
              color: '#6c757d',
              font: { size: 10 },
            },
          },
        },
        ...options,
      },
    };
  },

  /**
   * Heart rate chart
   */
  heartRate(labels, data, options = {}) {
    return {
      type: 'line',
      data: {
        labels,
        datasets: [{
          data,
          borderColor: this.colors.hr,
          backgroundColor: this.withAlpha(this.colors.hr, 0.15),
          fill: true,
          tension: 0.2,
          pointRadius: 0,
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            ...this.defaults.plugins.tooltip,
            callbacks: {
              label: (ctx) => `HR: ${ctx.raw} bpm`,
            },
          },
        },
        scales: {
          x: {
            display: true,
            grid: { display: false },
            ticks: {
              maxTicksLimit: 6,
              color: '#6c757d',
              font: { size: 10 },
            },
          },
          y: {
            beginAtZero: false,
            grid: { color: 'rgba(0,0,0,0.05)' },
            ticks: {
              color: '#6c757d',
              font: { size: 10 },
            },
          },
        },
        ...options,
      },
    };
  },

  /**
   * HR Zone distribution (horizontal bar)
   */
  hrZones(data, options = {}) {
    const zoneColors = ['#64B5F6', '#81C784', '#FFD54F', '#FF8A65', '#E57373'];
    const zoneLabels = ['Z1 Recovery', 'Z2 Aerobic', 'Z3 Tempo', 'Z4 Threshold', 'Z5 VO2max'];

    return {
      type: 'bar',
      data: {
        labels: zoneLabels,
        datasets: [{
          data: [data.z1, data.z2, data.z3, data.z4, data.z5],
          backgroundColor: zoneColors,
          borderRadius: 4,
        }],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            ...this.defaults.plugins.tooltip,
            callbacks: {
              label: (ctx) => {
                const mins = Math.floor(ctx.raw / 60);
                const secs = Math.floor(ctx.raw % 60);
                return `${mins}:${secs.toString().padStart(2, '0')}`;
              },
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              callback: (value) => {
                const mins = Math.floor(value / 60);
                return `${mins}m`;
              },
            },
          },
          y: {
            grid: { display: false },
          },
        },
        ...options,
      },
    };
  },
};

// Export for use in templates
window.ChartConfig = ChartConfig;
