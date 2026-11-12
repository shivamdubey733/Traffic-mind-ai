import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from traffic.signal_controller import AdaptiveSignalController
from traffic.emergency_manager import EmergencyManager
from database.db_manager import DBManager

class TestSignalController(unittest.TestCase):
    def setUp(self):
        self.db = DBManager()
        self.em = EmergencyManager(self.db)
        self.controller = AdaptiveSignalController(self.db, self.em)

    def test_priority_score_calculation(self):
        # Higher queue should result in significantly higher priority score
        score_high = self.controller.calculate_priority_score('NORTH', queue_len=25, pred_queue=20, arrival_rate=15.0, wait_sec=30)
        score_low = self.controller.calculate_priority_score('SOUTH', queue_len=3, pred_queue=4, arrival_rate=5.0, wait_sec=5)
        self.assertGreater(score_high, score_low)

    def test_optimal_green_bounds(self):
        # Green time should be clamped between min_green and max_green
        min_g = self.controller.compute_optimal_green(queue_len=1, pred_queue=1, arrival_rate=2.0)
        max_g = self.controller.compute_optimal_green(queue_len=90, pred_queue=80, arrival_rate=50.0)
        
        self.assertGreaterEqual(min_g, self.controller.min_green)
        self.assertLessEqual(max_g, self.controller.max_green)

    def test_emergency_override_transition(self):
        # Trigger emergency on EAST
        self.em.trigger_emergency('EAST')
        self.assertTrue(self.em.is_emergency_active())
        self.assertEqual(self.em.get_emergency_lane(), 'EAST')

        # Run update tick
        state = self.controller.update({}, {})
        self.assertIn(state['active_state'], ['YELLOW', 'ALL_RED', 'GREEN'])

if __name__ == '__main__':
    unittest.main()
