// TrafficMind AI - Analytics & Comparative Benchmarking Charts (Chart.js)

document.addEventListener('DOMContentLoaded', () => {
    loadAnalyticsData();

    const laneFilter = document.getElementById('analytics-lane-filter');
    if (laneFilter) {
        laneFilter.addEventListener('change', () => loadAnalyticsData());
    }
});

let hourlyChartInstance = null;
let laneDistChartInstance = null;
let comparisonChartInstance = null;

function loadAnalyticsData() {
    const lane = document.getElementById('analytics-lane-filter')?.value || 'ALL';

    fetch(`/api/analytics/summary?lane=${lane}`)
        .then(res => res.json())
        .then(data => {
            renderHourlyChart(data.hourly);
            renderLaneDistributionChart(data.distribution);
            renderComparisonChart(data.comparison);
            renderMetricsSummary(data.comparison);
        })
        .catch(err => console.error('Error loading analytics:', err));
}

function renderHourlyChart(hourlyData) {
    const ctx = document.getElementById('hourlyTrafficChart')?.getContext('2d');
    if (!ctx) return;

    const labels = hourlyData.map(d => d.hour_slot);
    const vehicles = hourlyData.map(d => Math.round(d.avg_vehicles));
    const queues = hourlyData.map(d => Math.round(d.avg_queue));

    if (hourlyChartInstance) hourlyChartInstance.destroy();

    hourlyChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Hourly Vehicle Volume (vph)',
                    data: vehicles,
                    borderColor: '#06b6d4',
                    backgroundColor: 'rgba(6, 182, 212, 0.15)',
                    fill: true,
                    tension: 0.35,
                    borderWidth: 2
                },
                {
                    label: 'Average Queue Length (veh)',
                    data: queues,
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245, 158, 11, 0.1)',
                    fill: false,
                    tension: 0.35,
                    borderWidth: 2,
                    borderDash: [5, 5]
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: '#94a3b8' } }
            },
            scales: {
                x: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,0.05)' } },
                y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,0.05)' } }
            }
        }
    });
}

function renderLaneDistributionChart(distData) {
    const ctx = document.getElementById('laneDistributionChart')?.getContext('2d');
    if (!ctx) return;

    const labels = distData.map(d => d.lane);
    const volumes = distData.map(d => d.total_volume);

    if (laneDistChartInstance) laneDistChartInstance.destroy();

    laneDistChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: volumes,
                backgroundColor: ['#06b6d4', '#10b981', '#f59e0b', '#8b5cf6'],
                borderColor: '#111827',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { color: '#94a3b8' } }
            }
        }
    });
}

function renderComparisonChart(compData) {
    const ctx = document.getElementById('comparisonChart')?.getContext('2d');
    if (!ctx) return;

    if (comparisonChartInstance) comparisonChartInstance.destroy();

    const ad = compData.adaptive;
    const fix = compData.conventional_fixed;

    comparisonChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Avg Waiting Time (sec)', 'Avg Queue Length (veh)', 'Signal Efficiency (%)'],
            datasets: [
                {
                    label: 'TrafficMind AI (Adaptive Predictive)',
                    data: [ad.avg_wait_sec, ad.avg_queue, ad.signal_efficiency_pct],
                    backgroundColor: '#10b981',
                    borderRadius: 6
                },
                {
                    label: 'Conventional Fixed-Time Signal',
                    data: [fix.avg_wait_sec, fix.avg_queue, fix.signal_efficiency_pct],
                    backgroundColor: '#ef4444',
                    borderRadius: 6
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: '#94a3b8' } }
            },
            scales: {
                x: { ticks: { color: '#64748b' }, grid: { display: false } },
                y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,0.05)' } }
            }
        }
    });
}

function renderMetricsSummary(compData) {
    const waitRed = document.getElementById('comp-wait-reduction');
    const queueRed = document.getElementById('comp-queue-reduction');
    const tputGain = document.getElementById('comp-throughput-gain');

    if (waitRed) waitRed.textContent = `-${compData.improvements.wait_time_reduction_pct}%`;
    if (queueRed) queueRed.textContent = `-${compData.improvements.queue_reduction_pct}%`;
    if (tputGain) tputGain.textContent = `+${compData.improvements.throughput_gain_pct}%`;
}
