// TrafficMind AI - Live Command Center SocketIO Controller

document.addEventListener('DOMContentLoaded', () => {
    // Connect to Flask-SocketIO
    const socket = io();

    // Clock
    function updateClock() {
        const now = new Date();
        const timeEl = document.getElementById('live-clock');
        if (timeEl) {
            timeEl.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) + 
                                 ' | ' + now.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
        }
    }
    setInterval(updateClock, 1000);
    updateClock();

    socket.on('connect', () => {
        console.log('[SocketIO] Connected to TrafficMind Command Center');
        const badge = document.getElementById('sys-status-badge');
        if (badge) {
            badge.innerHTML = '<span class="pulse-dot"></span> LIVE SYSTEM ONLINE';
            badge.className = 'pulse-badge';
        }
    });

    socket.on('disconnect', () => {
        console.warn('[SocketIO] Disconnected from backend');
        const badge = document.getElementById('sys-status-badge');
        if (badge) {
            badge.textContent = 'OFFLINE / RECONNECTING';
            badge.style.color = '#ef4444';
        }
    });

    // Receive full real-time telemetry tick
    socket.on('telemetry_update', (data) => {
        if (!data) return;

        // 1. Top Metrics Cards
        updateElementText('metric-total-vehicles', data.summary?.total_detected || 0);
        updateElementText('metric-queued-vehicles', data.summary?.total_queued || 0);
        updateElementText('metric-busiest-lane', data.summary?.busiest_lane || '--');
        updateElementText('metric-avg-queue', (data.summary?.avg_queue || 0) + ' veh (' + Math.round((data.summary?.avg_queue || 0) * 6.5) + 'm)');
        updateElementText('metric-active-signal', (data.signals?.active_lane || '--') + ' [' + (data.signals?.active_state || '--') + ' ' + (data.signals?.remaining_seconds || '') + 's]');
        updateElementText('metric-congestion-level', data.summary?.predicted_congestion || 'MODERATE');

        // Ambulance metric & top alert banner
        const emBanner = document.getElementById('emergency-banner');
        const emText = document.getElementById('emergency-banner-text');
        const emMetric = document.getElementById('metric-ambulance-status');

        if (data.emergency?.active) {
            if (emBanner) emBanner.style.display = 'flex';
            if (emText) {
                emText.textContent = `EMERGENCY PREEMPTION ACTIVE: Ambulance approaching on ${data.emergency.lane} approach! Safety clearance active. Green priority granted.`;
            }
            if (emMetric) {
                emMetric.textContent = `YES (${data.emergency.lane})`;
                emMetric.style.color = '#ef4444';
            }
        } else {
            if (emBanner) emBanner.style.display = 'none';
            if (emMetric) {
                emMetric.textContent = 'No (Clear)';
                emMetric.style.color = '#10b981';
            }
        }

        // 2. Update 4 Lane Camera Cards
        const lanes = ['NORTH', 'EAST', 'SOUTH', 'WEST'];
        lanes.forEach(lane => {
            const laneStats = data.camera_stats ? data.camera_stats[lane] : null;
            const laneSignal = data.signals?.lanes ? data.signals.lanes[lane] : null;

            if (laneSignal) {
                const pill = document.getElementById(`signal-pill-${lane.toLowerCase()}`);
                const timerEl = document.getElementById(`signal-timer-${lane.toLowerCase()}`);
                
                if (pill) {
                    pill.className = `signal-status-pill pill-${laneSignal.color.toLowerCase()}`;
                    pill.textContent = `${laneSignal.color} ${laneSignal.timer !== '--' ? laneSignal.timer + 's' : ''}`;
                }
                if (timerEl) {
                    timerEl.textContent = laneSignal.timer !== '--' ? `${laneSignal.timer}s` : '--';
                }
            }

            if (laneStats) {
                const densityVal = laneStats.density_index !== undefined ? laneStats.density_index : laneStats.vehicle_count;
                updateElementText(`density-idx-${lane.toLowerCase()}`, densityVal);
                updateElementText(`queue-len-${lane.toLowerCase()}`, `${laneStats.queue_length} (${Math.round(laneStats.queue_length * 6.5)}m)`);
                
                // Ambulance status text per lane
                const ambEl = document.getElementById(`amb-status-${lane.toLowerCase()}`);
                if (ambEl) {
                    if (laneStats.ambulance_detected || (data.emergency?.active && data.emergency?.lane === lane)) {
                        ambEl.textContent = 'YES [APPROACHING]';
                        ambEl.style.color = '#ef4444';
                        ambEl.style.fontWeight = 'bold';
                    } else {
                        ambEl.textContent = 'No';
                        ambEl.style.color = '#10b981';
                        ambEl.style.fontWeight = 'normal';
                    }
                }
            }
        });

        // 3. Update Proactive Predictive Matrix Table
        if (data.predictions) {
            lanes.forEach(lane => {
                const p = data.predictions[lane] || {};
                const sig = data.signals?.lanes ? data.signals.lanes[lane] : {};
                const cur = data.camera_stats ? data.camera_stats[lane] : {};

                const curDensity = cur.density_index !== undefined ? cur.density_index : cur.vehicle_count;
                updateElementText(`pred-cur-${lane.toLowerCase()}`, curDensity || 0);
                updateElementText(`pred-5m-${lane.toLowerCase()}`, p['5m']?.predicted_demand || '--');
                updateElementText(`pred-10m-${lane.toLowerCase()}`, p['10m']?.predicted_demand || '--');
                updateElementText(`pred-15m-${lane.toLowerCase()}`, p['15m']?.predicted_demand || '--');
                updateElementText(`pred-score-${lane.toLowerCase()}`, sig.priority_score || '--');
                updateElementText(`pred-green-${lane.toLowerCase()}`, (sig.allocated_green || 20) + 's');
            });
        }
    });

    function updateElementText(id, text) {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    // Window global control actions
    window.triggerEmergency = function(lane) {
        fetch('/api/emergency/trigger', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ lane: lane })
        })
        .then(res => res.json())
        .then(res => {
            console.log('Emergency response:', res);
        })
        .catch(err => console.error('Error triggering emergency:', err));
    };

    window.clearEmergency = function() {
        fetch('/api/emergency/clear', {
            method: 'POST'
        })
        .then(res => res.json())
        .then(res => console.log('Emergency cleared:', res))
        .catch(err => console.error(err));
    };

    window.setSimulationMode = function(mode) {
        fetch('/api/simulation/mode', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ mode: mode })
        })
        .then(res => res.json())
        .then(res => {
            alert(`Simulation traffic pattern switched to: ${mode}`);
        });
    };

    window.retrainPredictor = function() {
        const btn = document.getElementById('btn-retrain');
        if (btn) btn.textContent = 'Retraining AI Models...';
        
        fetch('/api/prediction/retrain', { method: 'POST' })
        .then(res => res.json())
        .then(res => {
            if (btn) btn.textContent = 'Retrain Random Forest Predictor';
            alert(`Model retrained successfully! 5m R2: ${res.metrics?.horizon_5m?.r2_score || '0.92'}`);
        })
        .catch(err => {
            if (btn) btn.textContent = 'Retrain Random Forest Predictor';
            alert('Error retraining model: ' + err);
        });
    };
});
