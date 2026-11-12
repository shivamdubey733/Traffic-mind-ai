import os
import csv
import io
import cv2
import numpy as np

def generate_csv_report(data_rows, fieldnames):
    """Generates an in-memory CSV string ready for download."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in data_rows:
        writer.writerow(row)
    return output.getvalue()

def create_sample_traffic_video(output_path, num_frames=120, has_ambulance=False):
    """Creates a sample MP4 video file for demonstration."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, 15.0, (640, 480))
    
    for i in range(num_frames):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[:] = (40, 42, 46)
        
        # Road markings
        cv2.line(frame, (80, 0), (80, 480), (200, 200, 200), 2)
        cv2.line(frame, (560, 0), (560, 480), (200, 200, 200), 2)
        cv2.line(frame, (320, 0), (320, 480), (220, 220, 220), 2)
        cv2.line(frame, (80, 360), (560, 360), (0, 220, 255), 4)
        
        # Moving cars
        y1 = (i * 4) % 480
        y2 = ((i * 3) + 120) % 480
        y3 = ((i * 2) + 240) % 480
        
        cv2.rectangle(frame, (180, y1), (220, y1 + 50), (200, 100, 20), -1)
        cv2.rectangle(frame, (400, y2), (440, y2 + 50), (40, 180, 220), -1)
        cv2.rectangle(frame, (180, y3), (230, y3 + 70), (20, 100, 200), -1)
        
        if has_ambulance:
            y_amb = (i * 6) % 480
            cv2.rectangle(frame, (390, y_amb), (450, y_amb + 70), (240, 240, 240), -1)
            # Red crosses & beacon
            beacon_col = (0, 0, 255) if (i % 4 < 2) else (255, 0, 0)
            cv2.circle(frame, (420, y_amb + 35), 8, beacon_col, -1)
            cv2.putText(frame, "AMBULANCE", (385, y_amb - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 2)
            
        out.write(frame)
        
    out.release()
    print(f"[Helpers] Sample video created: {output_path}")
