import time
import math

class QueueCalculator:
    """
    Computes rigorous queue dynamics, spatial queue length in meters,
    cumulative vehicle waiting time, arrival rates, and Level of Service (LOS).
    """
    def __init__(self, avg_vehicle_space_meters=6.5):
        self.avg_vehicle_space = avg_vehicle_space_meters # Vehicle length + safety buffer
        self.lane_arrival_history = {} # lane -> list of timestamps
        self.lane_waiting_trackers = {} # lane -> {vehicle_id: start_wait_timestamp}

    def compute_spatial_queue(self, vehicle_queue_count):
        """Returns physical estimated queue length in meters."""
        return round(vehicle_queue_count * self.avg_vehicle_space, 1)

    def update_waiting_times(self, lane, active_tracks, signal_state):
        """
        Updates and tracks how long queued vehicles have been delayed.
        Returns average waiting time in seconds.
        """
        now = time.time()
        if lane not in self.lane_waiting_trackers:
            self.lane_waiting_trackers[lane] = {}

        tracker = self.lane_waiting_trackers[lane]
        current_tracked_ids = set()

        for track in active_tracks:
            vid = track['id']
            current_tracked_ids.add(vid)
            # If vehicle is stopped or signal is RED
            if track.get('stationary', 0) > 1 or signal_state == 'RED':
                if vid not in tracker:
                    tracker[vid] = now
            else:
                # Vehicle is moving through green, remove
                tracker.pop(vid, None)

        # Clean up departed vehicles
        for old_id in list(tracker.keys()):
            if old_id not in current_tracked_ids:
                tracker.pop(old_id, None)

        if not tracker:
            return 0.0

        total_wait = sum(now - start_t for start_t in tracker.values())
        return round(total_wait / float(len(tracker)), 1)

    def calculate_arrival_rate(self, lane, current_count):
        """
        Estimates vehicle arrival rate (vehicles/minute) using exponential moving average.
        """
        now = time.time()
        if lane not in self.lane_arrival_history:
            self.lane_arrival_history[lane] = []

        history = self.lane_arrival_history[lane]
        history.append((now, current_count))
        # Keep recent 2 minutes
        cutoff = now - 120
        self.lane_arrival_history[lane] = [item for item in history if item[0] >= cutoff]

        if len(self.lane_arrival_history[lane]) < 2:
            return round(current_count * 0.8, 1)

        first_t, first_c = self.lane_arrival_history[lane][0]
        elapsed_min = max(0.1, (now - first_t) / 60.0)
        # Approximate incoming arrivals
        rate = round(current_count / elapsed_min, 1)
        return max(1.0, min(rate, 60.0))

    def determine_level_of_service(self, avg_delay_sec):
        """
        Highway Capacity Manual (HCM) Level of Service (LOS) criteria:
        LOS A: <= 10s (Free Flow)
        LOS B: 10 - 20s (Stable)
        LOS C: 20 - 35s (Acceptable)
        LOS D: 35 - 55s (Approaching Capacity)
        LOS E: 55 - 80s (Unstable / Capacity)
        LOS F: > 80s (Severe Congestion Breakdown)
        """
        if avg_delay_sec <= 10:
            return 'LOS A (Free Flow)'
        elif avg_delay_sec <= 20:
            return 'LOS B (Stable)'
        elif avg_delay_sec <= 35:
            return 'LOS C (Acceptable)'
        elif avg_delay_sec <= 55:
            return 'LOS D (High Delay)'
        elif avg_delay_sec <= 80:
            return 'LOS E (At Capacity)'
        else:
            return 'LOS F (Forced Flow / Breakdown)'
