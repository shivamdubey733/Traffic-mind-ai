# TrafficMind AI Trained Models Directory

This directory stores the AI/ML weights and serialized prediction models:

1. `yolov8n.pt`: Official Ultralytics YOLOv8 nano model for real-time multi-class vehicle detection (Car, Motorcycle, Bus, Truck, Bicycle).
2. `traffic_predictor.joblib`: Multi-horizon Random Forest Regressor trained on historical traffic database records to forecast +5m, +10m, and +15m vehicular demand and queue lengths.
3. `ambulance_yolov8.pt` (Optional): Custom-trained YOLOv8 weights specifically detecting emergency vehicles. If absent, the system operates with its built-in heuristic flashing-beacon detector and the Ideathon manual simulation override.
