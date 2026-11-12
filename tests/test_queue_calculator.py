import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from traffic.queue_calculator import QueueCalculator

class TestQueueCalculator(unittest.TestCase):
    def setUp(self):
        self.qc = QueueCalculator(avg_vehicle_space_meters=6.5)

    def test_spatial_queue(self):
        length_10 = self.qc.compute_spatial_queue(10)
        self.assertEqual(length_10, 65.0)

    def test_level_of_service(self):
        self.assertIn('LOS A', self.qc.determine_level_of_service(8))
        self.assertIn('LOS C', self.qc.determine_level_of_service(25))
        self.assertIn('LOS F', self.qc.determine_level_of_service(85))

    def test_arrival_rate_calculation(self):
        rate = self.qc.calculate_arrival_rate('NORTH', 24)
        self.assertGreater(rate, 0.0)

if __name__ == '__main__':
    unittest.main()
