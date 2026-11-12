import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
import datetime
from models.traffic_predictor import TrafficPredictor
from database.db_manager import DBManager

class TestTrafficPredictor(unittest.TestCase):
    def setUp(self):
        self.db = DBManager()
        self.predictor = TrafficPredictor()
        if not self.predictor.is_trained:
            self.predictor.train_from_db(self.db)

    def test_model_training(self):
        self.assertTrue(self.predictor.is_trained)
        self.assertIn(5, self.predictor.models)
        self.assertIn(10, self.predictor.models)
        self.assertIn(15, self.predictor.models)

    def test_prediction_output_structure(self):
        preds = self.predictor.predict('NORTH', current_count=35, current_queue=14, current_density=50.0)
        self.assertIn('5m', preds)
        self.assertIn('10m', preds)
        self.assertIn('15m', preds)
        self.assertIn('predicted_demand', preds['5m'])
        self.assertIn('predicted_queue', preds['5m'])
        self.assertIn('congestion_level', preds['5m'])

    def test_all_lanes_prediction(self):
        all_preds = self.predictor.predict_all_lanes()
        for lane in ['NORTH', 'EAST', 'SOUTH', 'WEST']:
            self.assertIn(lane, all_preds)
            self.assertIn('5m', all_preds[lane])

if __name__ == '__main__':
    unittest.main()
