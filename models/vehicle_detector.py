import cv2
import numpy as np
from config import Config

# COCO vehicle class mapping
COCO_VEHICLE_MAP = {
    1: 'bicycle',
    2: 'car',
    3: 'motorcycle',
    5: 'bus',
    7: 'truck'
}

CLASS_COLORS = {
    'car': (0, 165, 255),         # Orange (as in reference image)
    'motorcycle': (0, 215, 255),  # Yellow
    'bus': (255, 120, 0),         # Blue
    'truck': (200, 50, 255),      # Purple
    'bicycle': (80, 220, 100),    # Green
    'ambulance': (0, 0, 255)      # Bright Red
}

class VehicleDetector:
    def __init__(self, model_path=None, conf_thresh=0.35):
        self.model_path = model_path or Config.YOLO_MODEL_PATH
        self.conf_thresh = conf_thresh
        self.yolo_model = None
        self.is_loaded = False
        self._init_yolo()

    def _init_yolo(self):
        try:
            from ultralytics import YOLO
            import os
            if os.path.exists(self.model_path):
                self.yolo_model = YOLO(self.model_path)
            else:
                self.yolo_model = YOLO('yolov8n.pt')
            self.is_loaded = True
            print(f"[VehicleDetector] YOLOv8 engine initialized from {self.model_path}")
        except Exception as e:
            print(f"[VehicleDetector] YOLOv8 initialization notice: {e}")
            self.yolo_model = None
            self.is_loaded = False

    def process_frame(self, frame, lane_name='NORTH', signal_state='RED', remaining_timer='--', sim_vehicles=None):
        """
        Runs object detection, bounding-box drawing, queue calculations, and HUD overlays.
        Returns:
            annotated_frame, stats_dict
        """
        h, w = frame.shape[:2]
        stop_line_y = 330
        queue_start_y = 140

        detections = []
        has_ambulance = False
        ambulance_conf = 0.0

        # 1. If sim_vehicles provided from simulation engine, use high-precision ground truth
        if sim_vehicles is not None and len(sim_vehicles) > 0:
            for v in sim_vehicles:
                x1 = int(v.x - v.width // 2)
                x2 = int(v.x + v.width // 2)
                y1 = int(v.y - v.length)
                y2 = int(v.y)
                
                # Check bounds
                if y2 <= 0 or y1 >= h:
                    continue
                    
                x1 = max(0, x1)
                x2 = min(w - 1, x2)
                y1 = max(0, y1)
                y2 = min(h - 1, y2)

                is_amb = getattr(v, 'is_ambulance', False) or (v.type == 'ambulance')
                if is_amb:
                    has_ambulance = True
                    ambulance_conf = 0.98

                detections.append({
                    'id': v.id,
                    'class': 'ambulance' if is_amb else v.type,
                    'conf': getattr(v, 'conf', 0.88),
                    'bbox': (x1, y1, x2, y2),
                    'speed': v.speed,
                    'is_ambulance': is_amb,
                    'y': v.y
                })
        else:
            # 2. Run real YOLOv8 inference on camera/video input
            if self.is_loaded and self.yolo_model is not None:
                results = self.yolo_model.predict(
                    source=frame,
                    conf=self.conf_thresh,
                    classes=[1, 2, 3, 5, 7],
                    verbose=False
                )
                for r in results:
                    for i, box in enumerate(r.boxes):
                        cls_id = int(box.cls[0].item())
                        conf = float(box.conf[0].item())
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        cname = COCO_VEHICLE_MAP.get(cls_id, 'car')
                        detections.append({
                            'id': i + 1,
                            'class': cname,
                            'conf': round(conf, 2),
                            'bbox': (x1, y1, x2, y2),
                            'speed': 3.0,
                            'is_ambulance': False,
                            'y': y2
                        })

        annotated = frame.copy()
        queue_count = 0
        class_breakdown = {'car': 0, 'motorcycle': 0, 'bus': 0, 'truck': 0, 'bicycle': 0, 'ambulance': 0}

        # 3. Draw Bounding Boxes and Labels on Detected Vehicles
        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            cname = det['class']
            conf = det['conf']
            is_amb = det['is_ambulance']

            class_breakdown[cname] = class_breakdown.get(cname, 0) + 1

            # Queue condition: vehicle is in approach corridor behind stop line and slow/stopped
            in_queue_zone = (queue_start_y <= det['y'] <= (stop_line_y + 15))
            is_queued = in_queue_zone and (signal_state in ('RED', 'YELLOW') or det['speed'] < 1.5)

            if is_queued:
                queue_count += 1

            if is_amb:
                box_color = (0, 0, 255) # Bold Red for Ambulance
                label = f"AMBULANCE {conf:.2f} [PRIORITY]"
                border_thick = 3
            else:
                box_color = CLASS_COLORS.get(cname, (0, 165, 255))
                # Format: "Car 0.89", "Motorcycle 0.45" exactly as in reference image!
                label = f"{cname.capitalize()} {conf:.2f}"
                border_thick = 2

            # Bounding rectangle
            cv2.rectangle(annotated, (x1, y1), (x2, y2), box_color, border_thick)

            # Text label above box
            font = cv2.FONT_HERSHEY_SIMPLEX
            f_scale = 0.45
            (tw, th), baseline = cv2.getTextSize(label, font, f_scale, 1)
            
            # Semi-transparent text background
            cv2.rectangle(annotated, (x1, max(0, y1 - th - 6)), (x1 + tw + 6, max(th + 6, y1)), (15, 20, 25), -1)
            cv2.putText(annotated, label, (x1 + 3, max(th, y1 - 3)), font, f_scale, box_color, 1, cv2.LINE_AA)

        total_vehicles = len(detections)
        # Vehicle density index
        density_index = total_vehicles

        # 4. Draw HUD Overlay at Bottom (Exact match to reference image!)
        # Format: "Density: 18 | Ambulance: No | Time: --"
        amb_text = "YES [APPROACHING]" if has_ambulance else "No"
        time_text = f"{remaining_timer}s" if remaining_timer not in ('--', None) else "--"
        hud_text = f"Density: {density_index} | Ambulance: {amb_text} | Time: {time_text}"

        hud_bar_h = 32
        cv2.rectangle(annotated, (0, h - hud_bar_h), (w, h), (10, 14, 18), -1)
        cv2.line(annotated, (0, h - hud_bar_h), (w, h - hud_bar_h), (60, 70, 80), 1)
        
        text_color = (0, 0, 255) if has_ambulance else (240, 240, 240)
        cv2.putText(annotated, hud_text, (20, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.58, text_color, 2, cv2.LINE_AA)

        # Lane Label Top Center (e.g. "Lane 1 - North")
        cv2.putText(annotated, f"Approach: {lane_name}", (200, 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

        density_pct = min(100.0, round((total_vehicles / 22.0) * 100.0, 1))

        stats = {
            'lane': lane_name,
            'vehicle_count': total_vehicles,
            'queue_length': queue_count,
            'density_pct': density_pct,
            'density_index': density_index,
            'ambulance_detected': has_ambulance,
            'ambulance_conf': ambulance_conf,
            'class_breakdown': class_breakdown,
            'active_tracks': detections
        }

        return annotated, stats
