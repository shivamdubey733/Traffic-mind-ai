import os
import sys
import time
import threading
from functools import wraps

# Ensure app directory is in Python path regardless of execution location
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, Response, jsonify
)
from flask_socketio import SocketIO

from config import Config
from database.db_manager import DBManager
from models.vehicle_detector import VehicleDetector
from models.ambulance_detector import AmbulanceDetector
from models.traffic_predictor import TrafficPredictor
from traffic.queue_calculator import QueueCalculator
from traffic.emergency_manager import EmergencyManager
from traffic.signal_controller import AdaptiveSignalController
from traffic.traffic_simulator import TrafficSimulator
from utils.camera_manager import CameraManager
from utils.helpers import generate_csv_report, create_sample_traffic_video

# Flask App & SocketIO
app = Flask(__name__)
app.config.from_object(Config)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

@app.after_request
def add_no_cache_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# Core Engine Components
db_manager = DBManager()
vehicle_detector = VehicleDetector()
ambulance_detector = AmbulanceDetector()
emergency_manager = EmergencyManager(db_manager)
signal_controller = AdaptiveSignalController(db_manager, emergency_manager)
simulator = TrafficSimulator()
camera_manager = CameraManager(vehicle_detector, ambulance_detector, simulator)
queue_calc = QueueCalculator()
predictor = TrafficPredictor()

# Ensure ML predictor is trained on start
if not predictor.is_trained:
    print("[Startup] Initializing and training historical traffic prediction engine...")
    predictor.train_from_db(db_manager)

# Generate sample demo videos in data/videos/ if not present
sample_video_path = os.path.join(Config.VIDEO_DIR, 'sample_traffic.mp4')
sample_amb_video_path = os.path.join(Config.VIDEO_DIR, 'sample_ambulance.mp4')
if not os.path.exists(sample_video_path):
    create_sample_traffic_video(sample_video_path, num_frames=90, has_ambulance=False)
if not os.path.exists(sample_amb_video_path):
    create_sample_traffic_video(sample_amb_video_path, num_frames=90, has_ambulance=True)

# State cache for fast thread exchange
state_lock = threading.Lock()
latest_telemetry = {
    'summary': {
        'total_detected': 0,
        'total_queued': 0,
        'busiest_lane': 'NORTH',
        'avg_queue': 0.0,
        'predicted_congestion': 'LOW'
    },
    'signals': signal_controller.get_signal_states(),
    'emergency': emergency_manager.get_status(),
    'camera_stats': {},
    'predictions': {}
}

# Login Required Decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Background Real-time Orchestrator Thread
def background_traffic_engine():
    """
    Continuous background loop synchronizing:
    1. Simulation micro-dynamics
    2. Computer vision & camera feeds
    3. Adaptive signal control calculations
    4. Periodic ML predictions & database logging
    5. Real-time SocketIO telemetry streaming
    """
    last_pred_time = 0
    last_db_log_time = 0

    while True:
        try:
            start_tick = time.time()

            # 1. Get current signal states
            current_signals = signal_controller.get_signal_states()

            # 2. Advance vehicle simulation physics
            simulator.step(current_signals['lanes'])

            # 3. Process camera frames through YOLO / Vision
            cam_stats = camera_manager.update_all(current_signals)

            # 4. Check for vision-based ambulance triggers & auto-clearance
            for lane, stats in cam_stats.items():
                if stats.get('ambulance_detected') and not emergency_manager.is_emergency_active():
                    emergency_manager.trigger_emergency(lane, detection_mode='yolo_vision')

            if emergency_manager.is_emergency_active():
                em_lane = emergency_manager.get_emergency_lane()
                em_status = emergency_manager.get_status()
                has_amb = cam_stats.get(em_lane, {}).get('ambulance_detected', False)
                # Auto clear once the ambulance has traversed through the intersection (18s window)
                if not has_amb and em_status.get('elapsed_sec', 0) > 16.0:
                    emergency_manager.clear_emergency()

            # 5. Periodically refresh ML multi-horizon predictions (every 10s)
            now = time.time()
            if now - last_pred_time > 10.0 or not latest_telemetry['predictions']:
                predictions = predictor.predict_all_lanes(cam_stats)
                last_pred_time = now
            else:
                predictions = latest_telemetry['predictions']

            # 6. Update Adaptive Signal Controller
            updated_signals = signal_controller.update(cam_stats, predictions)

            # 7. Aggregate corridor metrics
            total_det = sum(s.get('vehicle_count', 0) for s in cam_stats.values())
            total_q = sum(s.get('queue_length', 0) for s in cam_stats.values())
            avg_q = round(total_q / max(1, len(cam_stats)), 1)
            
            busiest = max(cam_stats.keys(), key=lambda l: cam_stats[l].get('vehicle_count', 0)) if cam_stats else 'NORTH'

            # Determine macro congestion status
            if avg_q > 14 or total_det > 70:
                cong_level = 'SEVERE'
            elif avg_q > 9 or total_det > 45:
                cong_level = 'HIGH'
            elif avg_q > 4:
                cong_level = 'MODERATE'
            else:
                cong_level = 'LOW'

            summary = {
                'total_detected': total_det,
                'total_queued': total_q,
                'busiest_lane': busiest,
                'avg_queue': avg_q,
                'predicted_congestion': cong_level
            }

            # 8. Periodically log traffic snapshot to SQLite (every 15s)
            if now - last_db_log_time > 15.0:
                for lane, s in cam_stats.items():
                    db_manager.log_traffic_record(
                        lane=lane,
                        vehicle_count=s.get('vehicle_count', 0),
                        queue_length=s.get('queue_length', 0),
                        density_pct=s.get('density_pct', 0.0),
                        breakdown=s.get('class_breakdown', {})
                    )
                last_db_log_time = now

            # 9. Update telemetry cache & emit via SocketIO
            payload = {
                'summary': summary,
                'signals': updated_signals,
                'emergency': emergency_manager.get_status(),
                'camera_stats': cam_stats,
                'predictions': predictions
            }

            with state_lock:
                latest_telemetry.update(payload)

            socketio.emit('telemetry_update', payload)

            # Maintain ~15 FPS cycle rate
            elapsed = time.time() - start_tick
            sleep_time = max(0.02, 0.066 - elapsed)
            time.sleep(sleep_time)

        except Exception as e:
            print(f"[Orchestrator Error] {e}")
            time.sleep(0.5)

# Start background worker daemon
orchestrator_thread = threading.Thread(target=background_traffic_engine, daemon=True)
orchestrator_thread.start()

# --- WEB ROUTES ---

@app.route('/')
def index():
    return render_template('simple_dashboard.html')

@app.route('/dashboard')
def dashboard():
    return render_template('simple_dashboard.html')

@app.route('/advanced')
def advanced_dashboard():
    return render_template('dashboard.html')

@app.route('/analytics')
@login_required
def analytics():
    return render_template('analytics.html')

@app.route('/simulation')
@login_required
def simulation_view():
    return render_template('simulation.html')

@app.route('/settings')
@login_required
def settings_view():
    settings = db_manager.get_system_settings()
    amb_status = ambulance_detector.get_status()
    return render_template('settings.html', settings=settings, ambulance_status=amb_status)

@app.route('/save_settings', methods=['POST'])
@login_required
def save_settings_route():
    min_g = request.form.get('min_green')
    max_g = request.form.get('max_green')
    yellow = request.form.get('yellow_time')
    all_red = request.form.get('all_red_time')
    mode = request.form.get('control_mode')

    db_manager.save_setting('min_green', min_g)
    db_manager.save_setting('max_green', max_g)
    db_manager.save_setting('yellow_time', yellow)
    db_manager.save_setting('all_red_time', all_red)
    db_manager.save_setting('control_mode', mode)

    signal_controller.set_timing_parameters(min_g, max_g, yellow, all_red)
    signal_controller.control_mode = mode

    flash('System settings updated successfully.', 'success')
    return redirect(url_for('settings_view'))

# --- VIDEO STREAMING MJPEG ---

def gen_mjpeg_frames(lane):
    """Generator yielding boundary multipart JPEG frames for browser <img> tags."""
    while True:
        frame_bytes = camera_manager.get_frame(lane)
        if frame_bytes:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.06)

@app.route('/video_feed/<lane>')
def video_feed(lane):
    lane_upper = lane.upper()
    if lane_upper not in Config.LANES:
        return "Invalid Lane", 404
    return Response(gen_mjpeg_frames(lane_upper),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# --- REST APIS FOR DEMONSTRATION & CONTROLS ---

@app.route('/api/emergency/trigger', methods=['POST'])
@login_required
def api_trigger_emergency():
    data = request.get_json() or {}
    lane = data.get('lane', 'NORTH').upper()
    if lane not in Config.LANES:
        return jsonify({'error': 'Invalid lane'}), 400

    # Inject ambulance into the simulation lane & activate emergency preemption
    simulator.trigger_ambulance(lane)
    event = emergency_manager.trigger_emergency(lane, detection_mode='operator_trigger')
    return jsonify({'status': 'SUCCESS', 'message': f'Ambulance preemption engaged for {lane}', 'event': event})

@app.route('/api/emergency/clear', methods=['POST'])
@login_required
def api_clear_emergency():
    cleared = emergency_manager.clear_emergency()
    return jsonify({'status': 'SUCCESS', 'cleared': cleared})

@app.route('/api/simulation/start', methods=['POST'])
@login_required
def api_sim_start():
    simulator.is_paused = False
    return jsonify({'status': 'RUNNING'})

@app.route('/api/simulation/pause', methods=['POST'])
@login_required
def api_sim_pause():
    simulator.is_paused = True
    return jsonify({'status': 'PAUSED'})

@app.route('/api/simulation/reset', methods=['POST'])
@login_required
def api_sim_reset():
    simulator.reset()
    return jsonify({'status': 'RESET_COMPLETE'})

@app.route('/api/simulation/mode', methods=['POST'])
@login_required
def api_sim_mode():
    data = request.get_json() or {}
    mode = data.get('mode', 'NORMAL')
    if mode == 'PEAK_HOUR':
        simulator.set_peak_hour()
    else:
        simulator.set_normal_traffic()
    return jsonify({'status': 'SUCCESS', 'mode': simulator.mode})

@app.route('/api/simulation/multiplier', methods=['POST'])
@login_required
def api_sim_multiplier():
    data = request.get_json() or {}
    factor = float(data.get('factor', 1.0))
    simulator.set_multiplier(simulator.traffic_multiplier * factor)
    return jsonify({'status': 'SUCCESS', 'multiplier': round(simulator.traffic_multiplier, 2)})

@app.route('/api/prediction/retrain', methods=['POST'])
@login_required
def api_retrain_predictor():
    metrics = predictor.train_from_db(db_manager)
    return jsonify({'status': 'SUCCESS', 'metrics': metrics})

@app.route('/api/analytics/summary', methods=['GET'])
@login_required
def api_analytics_summary():
    lane = request.args.get('lane', 'ALL')
    hourly = db_manager.get_hourly_analytics(lane=lane)
    distribution = db_manager.get_lane_distribution(days=7)
    comparison = db_manager.get_performance_comparison()
    return jsonify({
        'hourly': hourly,
        'distribution': distribution,
        'comparison': comparison
    })

@app.route('/api/analytics/export_csv', methods=['GET'])
@login_required
def export_csv():
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp, lane, vehicle_count, queue_length, density_pct,
               cars, motorcycles, buses, trucks, bicycles, is_peak
        FROM traffic_records
        ORDER BY timestamp DESC
        LIMIT 1000
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    fields = ['timestamp', 'lane', 'vehicle_count', 'queue_length', 'density_pct',
              'cars', 'motorcycles', 'buses', 'trucks', 'bicycles', 'is_peak']
    csv_str = generate_csv_report(rows, fields)

    return Response(
        csv_str,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=trafficmind_traffic_records.csv"}
    )

if __name__ == '__main__':
    print("=" * 65)
    print("🚦  TRAFFICMIND AI – PREDICTIVE INTELLIGENT TRAFFIC MANAGEMENT  🚦")
    print("=" * 65)
    print("Command Center Dashboard: http://127.0.0.1:5000/dashboard")
    print("Default Login: admin / admin123")
    print("Ready for Live College Ideathon Demonstration.")
    print("=" * 65)
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
