import time
import math
from config import Config

class AdaptiveSignalController:
    """
    TrafficMind AI Dynamic Adaptive Signal Controller.
    Implements multi-factor priority scoring, proactive predictive allocation,
    yellow transitions, all-red clearance, anti-starvation aging, and emergency preemption.
    """
    def __init__(self, db_manager=None, emergency_manager=None):
        self.db_manager = db_manager
        self.emergency_manager = emergency_manager

        self.lanes = Config.LANES
        self.current_lane = 'NORTH'
        self.current_state = 'GREEN' # GREEN, YELLOW, ALL_RED
        self.state_start_time = time.time()
        self.allocated_duration = 25 # Initial default green seconds
        
        # Timing parameters
        self.min_green = Config.DEFAULT_MIN_GREEN
        self.max_green = Config.DEFAULT_MAX_GREEN
        self.yellow_time = Config.DEFAULT_YELLOW
        self.all_red_time = Config.DEFAULT_ALL_RED
        self.pedestrian_phase = Config.DEFAULT_PEDESTRIAN_TIME

        # Weights
        self.w_queue = Config.WEIGHT_QUEUE
        self.w_predicted = Config.WEIGHT_PREDICTED
        self.w_wait = Config.WEIGHT_WAITING
        self.w_arrival = Config.WEIGHT_ARRIVAL_RATE

        # Per-lane tracking
        self.red_start_times = {lane: time.time() for lane in self.lanes if lane != self.current_lane}
        self.lane_scores = {lane: 0.0 for lane in self.lanes}
        self.last_green_durations = {lane: 20 for lane in self.lanes}
        self.next_scheduled_lane = 'EAST'
        self.control_mode = 'ADAPTIVE_PREDICTIVE' # or 'FIXED_TIME'

        # Fixed time parameters (for comparative benchmarking)
        self.fixed_green_duration = 30

    def set_timing_parameters(self, min_g=None, max_g=None, yellow=None, all_red=None):
        if min_g is not None: self.min_green = int(min_g)
        if max_g is not None: self.max_green = int(max_g)
        if yellow is not None: self.yellow_time = int(yellow)
        if all_red is not None: self.all_red_time = int(all_red)

    def calculate_priority_score(self, lane, queue_len, pred_queue, arrival_rate, wait_sec):
        """
        Priority formula balancing live queues, predictive surges, and anti-starvation aging.
        """
        # Anti-starvation waiting bonus: adds 0.5 points per second waited
        starvation_bonus = wait_sec * 0.45
        
        score = (
            self.w_queue * (queue_len * 2.5) +
            self.w_predicted * (pred_queue * 2.0) +
            self.w_arrival * (arrival_rate * 1.2) +
            self.w_wait * starvation_bonus
        )
        return round(score, 2)

    def compute_optimal_green(self, queue_len, pred_queue, arrival_rate):
        """
        Calculates exact green light duration tailored to discharge the current queue
        plus the predicted arriving vehicles during the phase.
        Saturation flow rate: ~1 vehicle per 2.2 seconds.
        """
        if self.control_mode == 'FIXED_TIME':
            return self.fixed_green_duration

        total_demand = queue_len + (pred_queue * 0.6)
        discharge_time = total_demand * 2.2 # seconds needed to clear
        startup_lost_time = 3.0 # Driver reaction time at green onset
        
        calculated = discharge_time + startup_lost_time
        clamped = max(self.min_green, min(int(round(calculated)), self.max_green))
        return clamped

    def update(self, live_stats, predictions):
        """
        Periodic state-machine tick. Evaluates current countdown and transitions phases safely.
        live_stats: dict of lane -> {vehicle_count, queue_length, density_pct, arrival_rate, wait_time}
        predictions: dict of lane -> {'5m': {predicted_demand, predicted_queue}, ...}
        """
        now = time.time()
        elapsed = now - self.state_start_time
        remaining = max(0, int(round(self.allocated_duration - elapsed)))

        # 1. Check for Emergency Preemption
        if self.emergency_manager and self.emergency_manager.is_emergency_active():
            em_lane = self.emergency_manager.get_emergency_lane()
            
            # If current lane is already the emergency lane and in GREEN, hold it
            if self.current_lane == em_lane and self.current_state == 'GREEN':
                self.allocated_duration = max(self.allocated_duration, 45)
                self.emergency_manager.activate_priority_green()
            # If emergency lane is NOT currently green, we MUST transition safely via yellow -> all_red
            elif self.current_state == 'GREEN':
                # Curtail green immediately to begin safety clearance
                if elapsed >= 3.0: # Ensure minimum 3s before yellow to prevent abrupt stop
                    self._transition_to_yellow(em_lane, reason='emergency_preemption')
                    remaining = self.yellow_time
            elif self.current_state == 'ALL_RED' and elapsed >= self.all_red_time:
                # Transition directly to emergency lane
                self._transition_to_green(em_lane, green_duration=40, is_emergency=True)
                self.emergency_manager.activate_priority_green()
                remaining = 40
            return self.get_signal_states(remaining)

        # 2. Update priority scores for all lanes
        for lane in self.lanes:
            stats = live_stats.get(lane, {})
            preds = predictions.get(lane, {}).get('5m', {})
            
            q_len = stats.get('queue_length', 5)
            p_queue = preds.get('predicted_queue', 6)
            arr_rate = stats.get('arrival_rate', 10.0)
            
            if lane == self.current_lane and self.current_state == 'GREEN':
                wait_sec = 0
            else:
                wait_sec = now - self.red_start_times.get(lane, now)

            score = self.calculate_priority_score(lane, q_len, p_queue, arr_rate, wait_sec)
            self.lane_scores[lane] = score

        # 3. State Machine Transitions
        if elapsed >= self.allocated_duration:
            if self.current_state == 'GREEN':
                # Pick next lane with highest score among other waiting lanes
                candidates = [l for l in self.lanes if l != self.current_lane]
                if self.control_mode == 'FIXED_TIME':
                    # Round robin in fixed time mode
                    curr_idx = self.lanes.index(self.current_lane)
                    next_lane = self.lanes[(curr_idx + 1) % len(self.lanes)]
                else:
                    # Adaptive priority selection
                    next_lane = max(candidates, key=lambda l: self.lane_scores[l])

                self.next_scheduled_lane = next_lane
                self._transition_to_yellow(next_lane)
                remaining = self.yellow_time

            elif self.current_state == 'YELLOW':
                self._transition_to_all_red()
                remaining = self.all_red_time

            elif self.current_state == 'ALL_RED':
                # Activate scheduled next lane
                stats = live_stats.get(self.next_scheduled_lane, {})
                preds = predictions.get(self.next_scheduled_lane, {}).get('5m', {})
                q_len = stats.get('queue_length', 8)
                p_queue = preds.get('predicted_queue', 8)
                arr_rate = stats.get('arrival_rate', 12.0)

                optimal_green = self.compute_optimal_green(q_len, p_queue, arr_rate)
                self._transition_to_green(self.next_scheduled_lane, optimal_green)
                remaining = optimal_green

        return self.get_signal_states(remaining)

    def _transition_to_yellow(self, next_lane, reason='adaptive_cycle'):
        self.current_state = 'YELLOW'
        self.state_start_time = time.time()
        self.allocated_duration = self.yellow_time
        self.next_scheduled_lane = next_lane
        if self.db_manager:
            self.db_manager.log_signal_history(self.current_lane, 'YELLOW', self.yellow_time, reason=reason)

    def _transition_to_all_red(self):
        self.current_state = 'ALL_RED'
        self.state_start_time = time.time()
        self.allocated_duration = self.all_red_time
        # Now old green lane begins accumulating red waiting time
        self.red_start_times[self.current_lane] = time.time()
        if self.db_manager:
            self.db_manager.log_signal_history('ALL', 'ALL_RED', self.all_red_time, reason='intersection_clearance')

    def _transition_to_green(self, next_lane, green_duration, is_emergency=False):
        self.current_lane = next_lane
        self.current_state = 'GREEN'
        self.state_start_time = time.time()
        self.allocated_duration = green_duration
        self.last_green_durations[next_lane] = green_duration
        self.red_start_times.pop(next_lane, None)

        if self.db_manager:
            reason = 'emergency_override' if is_emergency else 'adaptive_allocation'
            self.db_manager.log_signal_history(next_lane, 'GREEN', green_duration, reason=reason, is_emergency=1 if is_emergency else 0)

    def get_signal_states(self, remaining_time=None):
        """Returns visual signal indicators and timers for all 4 lanes."""
        if remaining_time is None:
            elapsed = time.time() - self.state_start_time
            remaining_time = max(0, int(round(self.allocated_duration - elapsed)))

        states = {}
        for lane in self.lanes:
            if self.current_state == 'ALL_RED':
                color = 'RED'
            elif lane == self.current_lane:
                color = self.current_state # GREEN or YELLOW
            else:
                color = 'RED'

            states[lane] = {
                'color': color,
                'is_active': (lane == self.current_lane),
                'timer': remaining_time if (lane == self.current_lane or self.current_state == 'ALL_RED') else '--',
                'priority_score': self.lane_scores.get(lane, 0.0),
                'allocated_green': self.last_green_durations.get(lane, 20)
            }

        return {
            'active_lane': self.current_lane,
            'active_state': self.current_state,
            'remaining_seconds': remaining_time,
            'next_lane': self.next_scheduled_lane,
            'control_mode': self.control_mode,
            'lanes': states
        }
