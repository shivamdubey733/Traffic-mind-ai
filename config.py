import os
from pathlib import Path

# Base Directory
BASE_DIR = Path(__file__).resolve().parent

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'trafficmind-ai-secret-key-2025-ideathon')
    
    # Database
    DATABASE_PATH = os.path.join(BASE_DIR, 'database', 'trafficmind.db')
    SCHEMA_PATH = os.path.join(BASE_DIR, 'database', 'schema.sql')
    
    # Model Weights
    YOLO_MODEL_PATH = os.path.join(BASE_DIR, 'trained_models', 'yolov8n.pt')
    AMBULANCE_MODEL_PATH = os.path.join(BASE_DIR, 'trained_models', 'ambulance_yolov8.pt')
    PREDICTOR_MODEL_PATH = os.path.join(BASE_DIR, 'trained_models', 'traffic_predictor.joblib')
    
    # Lane Definitions (Four-way intersection)
    LANES = ['NORTH', 'EAST', 'SOUTH', 'WEST']
    
    # Default Signal Timing (seconds)
    DEFAULT_MIN_GREEN = 10
    DEFAULT_MAX_GREEN = 60
    DEFAULT_YELLOW = 4
    DEFAULT_ALL_RED = 2
    DEFAULT_PEDESTRIAN_TIME = 15
    
    # Priority Scoring Weights
    WEIGHT_QUEUE = 0.40
    WEIGHT_PREDICTED = 0.30
    WEIGHT_WAITING = 0.20
    WEIGHT_ARRIVAL_RATE = 0.10
    
    # Video & Stream Settings
    VIDEO_DIR = os.path.join(BASE_DIR, 'data', 'videos')
    SAMPLE_DATA_CSV = os.path.join(BASE_DIR, 'data', 'sample_data.csv')
    
    # Computer Vision Settings
    CONFIDENCE_THRESHOLD = 0.45
    IOU_THRESHOLD = 0.50
    VEHICLE_CLASSES = ['car', 'motorcycle', 'bus', 'truck', 'bicycle']
    
    # Simulation Settings
    SIMULATION_FPS = 15
    SIMULATION_UPDATE_INTERVAL = 1.0  # seconds
