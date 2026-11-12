import cv2
import threading
import time
import os
import numpy as np
from config import Config

class CameraStream:
    """Independent background worker for a single camera/lane feed."""
    def __init__(self, lane, vehicle_detector, ambulance_detector, simulator=None, video_source=None):
        self.lane = lane
        self.detector = vehicle_detector
        self.amb_detector = ambulance_detector
        self.simulator = simulator
        self.source = video_source  # None = simulator, int = webcam, str = file path
        
        self.cap = None
        self.latest_frame = None
        self.latest_jpeg = None
        self.latest_stats = {
            'lane': lane,
            'vehicle_count': 0,
            'queue_length': 0,
            'density_pct': 0.0,
            'density_index': 0,
            'class_breakdown': {},
            'ambulance_detected': False,
            'fps': 0.0
        }
        self.is_running = True
        self.lock = threading.Lock()
        self._init_capture()

    def _init_capture(self):
        if self.source is not None:
            try:
                self.cap = cv2.VideoCapture(self.source)
                if not self.cap.isOpened():
                    print(f"[Camera {self.lane}] Could not open source {self.source}. Falling back to simulator.")
                    self.cap = None
            except Exception as e:
                print(f"[Camera {self.lane}] Error opening video source: {e}")
                self.cap = None

    def set_source(self, new_source):
        with self.lock:
            if self.cap:
                self.cap.release()
            self.source = new_source
            self._init_capture()

    def process_step(self, signal_info):
        """Processes one video frame or simulation frame and updates stats."""
        raw_frame = None
        sim_vehicles = None

        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                # Loop video file
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
            if ret:
                raw_frame = cv2.resize(frame, (640, 480))

        if raw_frame is None and self.simulator:
            # Render frame from the 4-way intersection simulation engine
            raw_frame = self.simulator.render_lane_frame(self.lane, signal_info)
            sim_vehicles = self.simulator.get_lane_vehicles(self.lane)

        if raw_frame is None:
            raw_frame = 40 * np.ones((480, 640, 3), dtype=np.uint8)
            cv2.putText(raw_frame, f"CAM {self.lane} - NO SIGNAL", (180, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        # 1. Run Ambulance Detector check
        is_amb_manual, amb_conf, amb_mode, _ = self.amb_detector.detect_in_frame(raw_frame, self.lane)

        # 2. Run Vehicle Detection & Tracking
        sig_color = signal_info.get('color', 'RED')
        timer_val = signal_info.get('timer', '--')
        annotated, stats = self.detector.process_frame(
            raw_frame,
            lane_name=self.lane,
            signal_state=sig_color,
            remaining_timer=timer_val,
            sim_vehicles=sim_vehicles
        )

        # Combine ambulance triggers
        if is_amb_manual or stats.get('ambulance_detected'):
            stats['ambulance_detected'] = True
            stats['ambulance_conf'] = max(amb_conf, stats.get('ambulance_conf', 0.98))

        # Encode to JPEG for fast web streaming
        ret, jpeg = cv2.imencode('.jpg', annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if ret:
            with self.lock:
                self.latest_frame = annotated
                self.latest_jpeg = jpeg.tobytes()
                self.latest_stats = stats

        return stats

    def get_jpeg(self):
        with self.lock:
            return self.latest_jpeg

    def get_stats(self):
        with self.lock:
            return dict(self.latest_stats)

    def release(self):
        self.is_running = False
        if self.cap:
            self.cap.release()


class CameraManager:
    """Manages all 4 lane video feeds independently."""
    def __init__(self, vehicle_detector, ambulance_detector, simulator):
        self.lanes = Config.LANES
        self.streams = {}
        for lane in self.lanes:
            self.streams[lane] = CameraStream(
                lane=lane,
                vehicle_detector=vehicle_detector,
                ambulance_detector=ambulance_detector,
                simulator=simulator
            )

    def set_camera_source(self, lane, source):
        if lane in self.streams:
            self.streams[lane].set_source(source)

    def update_all(self, signal_states):
        """Ticks all cameras and aggregates fresh live statistics."""
        aggregated = {}
        for lane, stream in self.streams.items():
            sig_info = signal_states.get('lanes', {}).get(lane, {})
            stats = stream.process_step(sig_info)
            aggregated[lane] = stats
        return aggregated

    def get_frame(self, lane):
        if lane in self.streams:
            return self.streams[lane].get_jpeg()
        return None

    def get_all_stats(self):
        return {lane: self.streams[lane].get_stats() for lane in self.lanes}
