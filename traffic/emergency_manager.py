import time

class EmergencyManager:
    """
    Orchestrates Emergency Vehicle Preemption (EVP).
    Coordinates safety clearance intervals and prioritizes approaching emergency vehicles.
    """
    def __init__(self, db_manager=None):
        self.db_manager = db_manager
        self.active_emergency = None # {lane, event_id, stage, start_time}
        self.last_cleared_time = 0

    def trigger_emergency(self, lane, detection_mode='manual_simulation'):
        event_id = None
        if self.db_manager:
            event_id = self.db_manager.log_ambulance_event(lane, detection_mode)
            
        self.active_emergency = {
            'lane': lane,
            'event_id': event_id,
            'stage': 'SAFETY_CLEARING', # Requires safety yellow + all-red before green
            'detected_at': time.time(),
            'granted_at': None,
            'mode': detection_mode
        }
        return self.active_emergency

    def activate_priority_green(self):
        if self.active_emergency:
            self.active_emergency['stage'] = 'PRIORITY_ACTIVE'
            self.active_emergency['granted_at'] = time.time()

    def clear_emergency(self):
        if self.active_emergency:
            lane = self.active_emergency['lane']
            if self.db_manager and self.active_emergency.get('event_id'):
                self.db_manager.clear_ambulance_event(self.active_emergency['event_id'])
            self.last_cleared_time = time.time()
            cleared = self.active_emergency
            self.active_emergency = None
            return cleared
        return None

    def is_emergency_active(self):
        return self.active_emergency is not None

    def get_emergency_lane(self):
        return self.active_emergency['lane'] if self.active_emergency else None

    def get_status(self):
        if not self.active_emergency:
            return {'active': False, 'lane': None, 'stage': 'NORMAL'}
        return {
            'active': True,
            'lane': self.active_emergency['lane'],
            'stage': self.active_emergency['stage'],
            'elapsed_sec': round(time.time() - self.active_emergency['detected_at'], 1),
            'mode': self.active_emergency['mode']
        }
