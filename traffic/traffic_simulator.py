import cv2
import numpy as np
import time
import random
import threading
from config import Config

VEHICLE_CONFIGS = {
    'car': {'length': 42, 'width': 22, 'colors': [(220, 180, 50), (200, 200, 200), (50, 50, 200), (40, 160, 220), (30, 30, 30), (180, 50, 50)], 'speed': 4.5, 'prob': 0.65},
    'motorcycle': {'length': 24, 'width': 12, 'colors': [(30, 210, 240), (240, 120, 30), (50, 220, 100)], 'speed': 5.2, 'prob': 0.18},
    'bus': {'length': 75, 'width': 26, 'colors': [(20, 130, 240), (40, 180, 80), (240, 80, 20)], 'speed': 3.5, 'prob': 0.08},
    'truck': {'length': 65, 'width': 26, 'colors': [(160, 50, 200), (140, 140, 140), (60, 100, 180)], 'speed': 3.8, 'prob': 0.06},
    'bicycle': {'length': 20, 'width': 8, 'colors': [(100, 220, 100)], 'speed': 2.8, 'prob': 0.03}
}

LANE_OFFSETS = [140, 220, 300] # 3 driving tracks per approach

class SimVehicle:
    def __init__(self, vid, vtype, lane, track_idx=0, y_pos=0.0, speed=4.0, is_ambulance=False):
        self.id = vid
        self.type = vtype
        self.lane = lane
        self.track_idx = track_idx
        self.x = LANE_OFFSETS[track_idx]
        self.y = y_pos
        self.speed = speed
        self.is_ambulance = is_ambulance
        
        if is_ambulance:
            self.type = 'ambulance'
            self.length = 52
            self.width = 24
            self.color = (250, 250, 250) # Pure white
            self.max_speed = 6.5
            self.conf = round(random.uniform(0.95, 0.99), 2)
        else:
            cfg = VEHICLE_CONFIGS.get(vtype, VEHICLE_CONFIGS['car'])
            self.length = cfg['length']
            self.width = cfg['width']
            self.color = random.choice(cfg['colors'])
            self.max_speed = cfg['speed']
            self.conf = round(random.uniform(0.82, 0.96), 2)

        self.stopped_frames = 0
        self.flash_timer = 0

class TrafficSimulator:
    """
    High-density multi-lane 4-way intersection simulation engine.
    Renders realistic roadway with vehicles, queues, and ambulances.
    """
    def __init__(self):
        self.lanes = Config.LANES
        self.is_running = True
        self.is_paused = False
        self.traffic_multiplier = 1.0
        self.mode = 'NORMAL'
        self.vehicles = {lane: [] for lane in self.lanes}
        self.next_vid = 101
        self.lock = threading.Lock()
        
        self.stop_line_y = 330
        self.frame_h = 480
        self.frame_w = 640

        # Target densities matching real intersections (North heaviest, South lightest)
        self.target_densities = {
            'NORTH': 18,
            'EAST': 13,
            'SOUTH': 6,
            'WEST': 16
        }

        # Initialize realistic vehicle volume for all lanes
        for lane, count in self.target_densities.items():
            self._seed_lane_vehicles(lane, count)

    def _seed_lane_vehicles(self, lane, count):
        per_track = max(1, count // 3)
        extra = count % 3
        for track in range(3):
            track_count = per_track + (1 if track < extra else 0)
            spacing = 380.0 / max(1, track_count)
            for i in range(track_count):
                y = 40.0 + (i * spacing) + random.uniform(-5, 5)
                self._spawn_vehicle(lane, track_idx=track, y_pos=min(440.0, y))

    def _spawn_vehicle(self, lane, track_idx=None, y_pos=15.0, is_ambulance=False):
        if track_idx is None:
            track_idx = random.randint(0, 2)
            
        if is_ambulance:
            vtype = 'ambulance'
        else:
            r = random.random()
            cum = 0.0
            vtype = 'car'
            for vt, cfg in VEHICLE_CONFIGS.items():
                cum += cfg['prob']
                if r <= cum:
                    vtype = vt
                    break

        v = SimVehicle(self.next_vid, vtype, lane, track_idx=track_idx, y_pos=y_pos, is_ambulance=is_ambulance)
        self.next_vid += 1
        self.vehicles[lane].append(v)
        return v

    def trigger_ambulance(self, lane='NORTH'):
        with self.lock:
            # Check if ambulance already exists in this lane
            for v in self.vehicles[lane]:
                if v.is_ambulance:
                    v.y = 40.0 # reset to approach top
                    return v.id

            # Clear center track at approach top and spawn ambulance
            track = 1 # Center express lane
            amb = self._spawn_vehicle(lane, track_idx=track, y_pos=35.0, is_ambulance=True)
            print(f"[Simulator] Injected Emergency Ambulance on lane {lane} (ID: #{amb.id})")
            return amb.id

    def set_multiplier(self, factor):
        self.traffic_multiplier = max(0.4, min(factor, 3.0))

    def set_peak_hour(self):
        self.mode = 'PEAK_HOUR'
        self.traffic_multiplier = 1.8
        with self.lock:
            for lane in self.lanes:
                needed = int(self.target_densities[lane] * 1.4) - len(self.vehicles[lane])
                for _ in range(max(0, needed)):
                    self._spawn_vehicle(lane, y_pos=random.uniform(40, 310))

    def set_normal_traffic(self):
        self.mode = 'NORMAL'
        self.traffic_multiplier = 1.0

    def reset(self):
        with self.lock:
            self.vehicles = {lane: [] for lane in self.lanes}
            self.next_vid = 101
            for lane, count in self.target_densities.items():
                self._seed_lane_vehicles(lane, count)

    def step(self, signal_states):
        """Advances vehicle dynamics, deceleration behind stop line, and acceleration through green."""
        if self.is_paused:
            return

        with self.lock:
            for lane in self.lanes:
                sig_info = signal_states.get(lane, {})
                sig_color = sig_info.get('color', 'RED')
                v_list = self.vehicles[lane]

                target = int(self.target_densities.get(lane, 12) * self.traffic_multiplier)

                # Replenish vehicles if below target density
                if len(v_list) < target:
                    # Check if entry is clear
                    tracks_busy_at_top = {v.track_idx for v in v_list if v.y < 60}
                    free_tracks = [t for t in range(3) if t not in tracks_busy_at_top]
                    if free_tracks and random.random() < 0.25:
                        self._spawn_vehicle(lane, track_idx=random.choice(free_tracks), y_pos=15.0)

                # Process vehicles per track from front to back
                for track in range(3):
                    track_vehicles = [v for v in v_list if v.track_idx == track]
                    track_vehicles.sort(key=lambda x: x.y, reverse=True) # closest to stop line first

                    for i, v in enumerate(track_vehicles):
                        lead_y = track_vehicles[i - 1].y if i > 0 else 9999.0
                        lead_len = track_vehicles[i - 1].length if i > 0 else 0
                        lead_gap = lead_y - v.y - lead_len

                        dist_to_stop = self.stop_line_y - v.y
                        should_stop = False

                        # Red or Yellow light stop logic
                        if sig_color in ('RED', 'YELLOW'):
                            if 0 < dist_to_stop <= 45:
                                should_stop = True

                        # Follow leader distance
                        if lead_gap < 16:
                            should_stop = True

                        if should_stop:
                            v.speed = max(0.0, v.speed - 0.8)
                            v.stopped_frames += 1
                        else:
                            v.speed = min(v.max_speed, v.speed + 0.5)
                            v.stopped_frames = 0

                        v.y += v.speed
                        v.flash_timer = (v.flash_timer + 1) % 8

                # Remove vehicles that crossed through and exited bottom of frame
                self.vehicles[lane] = [v for v in v_list if v.y < (self.frame_h + 30)]

    def get_lane_vehicles(self, lane):
        with self.lock:
            return list(self.vehicles.get(lane, []))

    def render_lane_frame(self, lane, signal_info):
        """
        Renders complete, realistic highway/intersection camera scene:
        3 driving lanes, asphalt, road arrows, realistic vehicle bodies,
        brake lights, flashing ambulance beacons, and side traffic light housing.
        """
        frame = np.zeros((self.frame_h, self.frame_w, 3), dtype=np.uint8)
        
        # 1. Asphalt Roadway
        frame[:] = (38, 42, 46)

        # Curbs and sidewalks
        cv2.rectangle(frame, (0, 0), (80, self.frame_h), (50, 54, 60), -1)
        cv2.rectangle(frame, (380, 0), (self.frame_w, self.frame_h), (50, 54, 60), -1)
        # Curb edge lines
        cv2.line(frame, (80, 0), (80, self.frame_h), (180, 180, 190), 2)
        cv2.line(frame, (380, 0), (380, self.frame_h), (180, 180, 190), 2)

        # Lane dividers (Dashed white lines for 3 lanes)
        for div_x in [180, 260]:
            y = 0
            while y < self.frame_h:
                cv2.line(frame, (div_x, y), (div_x, y + 25), (220, 220, 220), 2)
                y += 45

        # Stop Line (Bold Yellow/White)
        cv2.line(frame, (80, self.stop_line_y), (380, self.stop_line_y), (0, 220, 255), 4)
        cv2.putText(frame, "STOP LINE", (88, self.stop_line_y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 220, 255), 1)

        # Crosswalk stripes
        for cx in range(90, 370, 30):
            cv2.rectangle(frame, (cx, self.stop_line_y + 8), (cx + 18, self.stop_line_y + 35), (200, 200, 200), -1)

        # Queue waiting zone outline
        overlay = frame.copy()
        sig_color = signal_info.get('color', 'RED')
        q_color = (0, 0, 180) if sig_color == 'RED' else (0, 160, 0)
        cv2.rectangle(overlay, (85, 140), (375, self.stop_line_y), q_color, -1)
        cv2.addWeighted(overlay, 0.10, frame, 0.90, 0, frame)

        # 2. Render Vehicles
        with self.lock:
            v_list = list(self.vehicles.get(lane, []))

        for v in v_list:
            x1 = int(v.x - v.width // 2)
            x2 = int(v.x + v.width // 2)
            y1 = int(v.y - v.length)
            y2 = int(v.y)

            # Wheels / Tires
            cv2.rectangle(frame, (x1 - 2, y1 + 6), (x1, y1 + 14), (10, 10, 10), -1)
            cv2.rectangle(frame, (x2, y1 + 6), (x2 + 2, y1 + 14), (10, 10, 10), -1)
            cv2.rectangle(frame, (x1 - 2, y2 - 14), (x1, y2 - 6), (10, 10, 10), -1)
            cv2.rectangle(frame, (x2, y2 - 14), (x2 + 2, y2 - 6), (10, 10, 10), -1)

            # Vehicle Body
            cv2.rectangle(frame, (x1, y1), (x2, y2), v.color, -1)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (240, 240, 240), 1)

            # Windshield & Rear glass
            ws_y1 = y1 + int(v.length * 0.20)
            ws_y2 = y1 + int(v.length * 0.38)
            cv2.rectangle(frame, (x1 + 3, ws_y1), (x2 - 3, ws_y2), (30, 40, 50), -1)
            
            rg_y1 = y2 - int(v.length * 0.28)
            rg_y2 = y2 - int(v.length * 0.15)
            cv2.rectangle(frame, (x1 + 3, rg_y1), (x2 - 3, rg_y2), (30, 40, 50), -1)

            # Tail lights (Bright glowing RED if stopping/queued)
            tail_color = (0, 0, 255) if v.speed < 1.0 else (0, 100, 200)
            cv2.circle(frame, (x1 + 4, y2 - 2), 3, tail_color, -1)
            cv2.circle(frame, (x2 - 4, y2 - 2), 3, tail_color, -1)

            # Headlights
            cv2.circle(frame, (x1 + 4, y1 + 2), 2, (0, 255, 255), -1)
            cv2.circle(frame, (x2 - 4, y1 + 2), 2, (0, 255, 255), -1)

            # AMBULANCE SPECIAL GRAPHICS
            if v.is_ambulance:
                # Red emergency cross on roof
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                cv2.rectangle(frame, (cx - 2, cy - 8), (cx + 2, cy + 8), (0, 0, 240), -1)
                cv2.rectangle(frame, (cx - 8, cy - 2), (cx + 8, cy + 2), (0, 0, 240), -1)

                # High-Intensity Strobe Beacon (Alternating Blue and Red flashing lights)
                b1_col = (255, 50, 50) if (v.flash_timer < 4) else (50, 50, 255)
                b2_col = (50, 50, 255) if (v.flash_timer < 4) else (255, 50, 50)
                cv2.circle(frame, (x1 + 6, cy - 6), 5, b1_col, -1)
                cv2.circle(frame, (x2 - 6, cy - 6), 5, b2_col, -1)
                # Outer glow halo
                cv2.circle(frame, (x1 + 6, cy - 6), 9, b1_col, 1)
                cv2.circle(frame, (x2 - 6, cy - 6), 9, b2_col, 1)

        # 3. Render Physical Traffic Light Housing (Left side of camera feed, like reference image)
        self._render_side_traffic_light(frame, sig_color)

        return frame

    def _render_side_traffic_light(self, frame, sig_color):
        """Renders the physical vertical traffic signal post on the left curb."""
        lx = 20
        ly = 60
        lw = 44
        lh = 130

        # Metal casing
        cv2.rectangle(frame, (lx, ly), (lx + lw, ly + lh), (20, 22, 26), -1)
        cv2.rectangle(frame, (lx, ly), (lx + lw, ly + lh), (100, 110, 120), 2)

        # 1. Red Light
        r_on = (sig_color == 'RED')
        r_col = (0, 0, 255) if r_on else (15, 15, 45)
        cv2.circle(frame, (lx + lw // 2, ly + 25), 14, r_col, -1)
        if r_on:
            cv2.circle(frame, (lx + lw // 2, ly + 25), 18, (0, 0, 255), 2) # glow halo

        # 2. Yellow Light
        y_on = (sig_color == 'YELLOW')
        y_col = (0, 220, 255) if y_on else (20, 45, 50)
        cv2.circle(frame, (lx + lw // 2, ly + 65), 14, y_col, -1)
        if y_on:
            cv2.circle(frame, (lx + lw // 2, ly + 65), 18, (0, 220, 255), 2)

        # 3. Green Light
        g_on = (sig_color == 'GREEN')
        g_col = (0, 255, 0) if g_on else (15, 45, 15)
        cv2.circle(frame, (lx + lw // 2, ly + 105), 14, g_col, -1)
        if g_on:
            cv2.circle(frame, (lx + lw // 2, ly + 105), 18, (0, 255, 0), 2)
