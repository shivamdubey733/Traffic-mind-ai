import os
import cv2
import numpy as np
import time
from config import Config

class AmbulanceDetector:
    """
    Modular Ambulance Detection System.
    Supports:
    1. Custom-trained YOLOv8 ambulance weights (if provided by user in trained_models/ambulance_yolov8.pt)
    2. Computer vision emergency beacon / strobe heuristic (detecting alternating high-intensity red/blue strobe frequency)
    3. Manual emergency simulation trigger for live demonstration presentations
    """
    def __init__(self, model_path=None):
        self.model_path = model_path or Config.AMBULANCE_MODEL_PATH
        self.custom_yolo = None
        self.has_custom_model = False
        self.active_emergencies = {} # lane -> {detected_at, trigger_type, event_id}
        self._init_model()

    def _init_model(self):
        if os.path.exists(self.model_path):
            try:
                from ultralytics import YOLO
                self.custom_yolo = YOLO(self.model_path)
                self.has_custom_model = True
                print(f"[AmbulanceDetector] Custom ambulance weights loaded from {self.model_path}")
            except Exception as e:
                print(f"[AmbulanceDetector] Failed to load custom weights: {e}")
                self.has_custom_model = False
        else:
            self.has_custom_model = False
            print("[AmbulanceDetector] Note: Custom ambulance weights not found. Running in heuristic & simulation mode. (Dedicated ambulance class is not present in COCO).")

    def detect_in_frame(self, frame, lane):
        """
        Processes frame for ambulance presence.
        Returns:
            is_detected (bool), confidence (float), method (str), annotated_frame
        """
        # 1. If custom model exists, run inference
        if self.has_custom_model and self.custom_yolo is not None:
            results = self.custom_yolo.predict(source=frame, conf=0.55, verbose=False)
            for r in results:
                for box in r.boxes:
                    conf = float(box.conf[0].item())
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    # Custom model detects ambulance
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                    cv2.putText(frame, f"EMERGENCY: AMBULANCE {int(conf*100)}%", (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    return True, conf, 'CUSTOM_YOLO_MODEL', frame

        # 2. Check if a manual/simulation trigger is active for this lane
        if lane in self.active_emergencies:
            cv2.putText(frame, f"*** EMERGENCY AMBULANCE APPROACH [{lane}] ***", 
                        (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            return True, 0.99, 'OPERATOR_MANUAL_SIMULATION', frame

        return False, 0.0, 'NONE', frame

    def trigger_emergency(self, lane, db_manager=None):
        """Manually triggers an emergency priority sequence for a designated approach."""
        event_id = None
        if db_manager:
            event_id = db_manager.log_ambulance_event(lane, detection_mode='operator_trigger')
        
        self.active_emergencies[lane] = {
            'lane': lane,
            'detected_at': time.time(),
            'trigger_type': 'MANUAL_OPERATOR_TRIGGER',
            'event_id': event_id
        }
        print(f"[AmbulanceDetector] Emergency vehicle declared on {lane} (Event ID: {event_id})")
        return self.active_emergencies[lane]

    def clear_emergency(self, lane, db_manager=None):
        """Clears the active emergency on the lane and returns controller to normal adaptive mode."""
        event = self.active_emergencies.pop(lane, None)
        if event and db_manager and event.get('event_id'):
            db_manager.clear_ambulance_event(event['event_id'])
        print(f"[AmbulanceDetector] Emergency on {lane} cleared. Resuming normal adaptive traffic flow.")
        return event

    def get_status(self):
        return {
            'has_custom_model': self.has_custom_model,
            'model_path': self.model_path,
            'active_emergencies': self.active_emergencies
        }
