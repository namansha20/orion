"""
ORION-EYE Web Server
Flask backend for debris avoidance dashboard
"""

from flask import Flask, render_template, jsonify, request, Response
from flask_cors import CORS
from orion_eye import OrionEyeSystem
import json
import cv2
import numpy as np
from collections import deque
from threading import Lock
from camera_utils import (
    calculate_dynamics, get_direction_label,
    LOWER_RED1, UPPER_RED1, LOWER_RED2, UPPER_RED2,
    BUFFER_SIZE, PREDICTION_FRAMES, COLLISION_ZONE, GROWTH_THRESHOLD
)

app = Flask(__name__)
CORS(app)

# Initialize ORION-EYE system
orion = OrionEyeSystem()

# Global camera instance with thread safety
camera = None
camera_active = False
camera_lock = Lock()


@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')


def convert_numpy(obj):
    """Convert numpy types to Python native types for JSON serialization"""
    import numpy as np
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    elif isinstance(obj, dict):
        return {key: convert_numpy(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy(item) for item in obj]
    else:
        return obj


@app.route('/api/simulate', methods=['POST'])
def simulate():
    """Run simulation with specified scenario"""
    data = request.json
    scenario = data.get('scenario', 'safe')
    
    try:
        result = orion.run_simulation(scenario)
        # Convert numpy arrays to native types for JSON serialization
        result_clean = convert_numpy(result)
        return jsonify(result_clean)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/scenarios')
def get_scenarios():
    """Get available demo scenarios"""
    scenarios = [
        {
            'id': 'safe',
            'name': 'Demo 1: Safe Passage',
            'description': 'Nominal scenario with distant objects, no collision risk',
            'expected_outcome': 'SAFE_PASSAGE'
        },
        {
            'id': 'crash',
            'name': 'Demo 2: Collision Course',
            'description': 'Critical scenario with object on direct collision course',
            'expected_outcome': 'AVOIDANCE_REQUIRED'
        },
        {
            'id': 'multi',
            'name': 'Demo 3: Multiple Objects',
            'description': 'Complex scenario with multiple objects requiring prioritization',
            'expected_outcome': 'COMPLEX_AVOIDANCE'
        }
    ]
    return jsonify(scenarios)


@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'operational', 'system': 'ORION-EYE'})


def generate_camera_frames():
    """Generate video frames with debris detection overlay"""
    global camera, camera_active
    
    # Initialize camera with error checking
    with camera_lock:
        camera = cv2.VideoCapture(0)
        if not camera.isOpened():
            camera = None
            camera_active = False
            return
        camera_active = True
    
    # Tracking memory buffers
    pos_pts = deque(maxlen=BUFFER_SIZE)
    rad_pts = deque(maxlen=BUFFER_SIZE)
    
    while camera_active:
        success, frame = camera.read()
        if not success:
            break
        
        frame = cv2.flip(frame, 1)  # Mirror view
        h, w, _ = frame.shape
        center_x, center_y = w // 2, h // 2
        
        # Computer Vision - Object Detection
        blurred = cv2.GaussianBlur(frame, (11, 11), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, LOWER_RED1, UPPER_RED1) + cv2.inRange(hsv, LOWER_RED2, UPPER_RED2)
        mask = cv2.erode(mask, None, iterations=2)
        mask = cv2.dilate(mask, None, iterations=2)
        contours, _ = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Default HUD State
        status_msg = "SCANNING SECTOR..."
        status_color = (0, 255, 0)  # Green
        vector_text = "NO TARGET"
        
        if len(contours) > 0:
            c = max(contours, key=cv2.contourArea)
            ((x, y), radius) = cv2.minEnclosingCircle(c)
            M = cv2.moments(c)
            
            if M["m00"] > 0 and radius > 10:
                center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))
                
                # Update Memory
                pos_pts.appendleft(center)
                rad_pts.appendleft(radius)
                
                # Dynamics Analysis
                (dx, dy), growth_rate = calculate_dynamics(pos_pts, rad_pts)
                direction_label = get_direction_label(dx, dy)
                
                # Z-Axis Logic
                z_label = "STABLE"
                if growth_rate > GROWTH_THRESHOLD: z_label = "APPROACHING"
                elif growth_rate < -GROWTH_THRESHOLD: z_label = "RECEDING"

                # Prediction Logic
                pred_x = int(x + (dx * PREDICTION_FRAMES))
                pred_y = int(y + (dy * PREDICTION_FRAMES))
                dist_future = np.linalg.norm(np.array((pred_x, pred_y)) - np.array((center_x, center_y)))
                
                is_intercept = dist_future < COLLISION_ZONE
                is_approaching = growth_rate > GROWTH_THRESHOLD

                # Decision Making
                if is_intercept and is_approaching:
                    status_color = (0, 0, 255)  # Red
                    status_msg = "⚠️ COLLISION COURSE"
                    
                    # Smart Evasion Calculation
                    dodge_x = "RIGHT" if dx < 0 else "LEFT"
                    dodge_y = "DOWN" if dy < 0 else "UP"
                    
                    cv2.putText(frame, f"ACTION: THRUST {dodge_x} & {dodge_y}", (50, h - 80), 
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
                    
                    # Draw Collision Warning Line
                    cv2.line(frame, (int(x), int(y)), (center_x, center_y), (0, 0, 255), 3)

                elif is_intercept and not is_approaching:
                    status_color = (255, 100, 0)  # Orange-ish
                    status_msg = "TRAJECTORY INTERSECT (SAFE - RECEDING)"
                else:
                    status_color = (0, 255, 255)  # Yellow
                    status_msg = "TRACKING TARGET"

                # Update Vector Text
                vector_text = f"V: {direction_label} | Z: {z_label}"
                
                # Draw Object & Prediction
                cv2.circle(frame, (int(x), int(y)), int(radius), status_color, 2)
                if abs(dx) > 1 or abs(dy) > 1:
                    cv2.arrowedLine(frame, (int(x), int(y)), (int(x+dx*20), int(y+dy*20)), (0, 255, 255), 2)

        # Draw Trajectory Trail
        for i in range(1, len(pos_pts)):
            if pos_pts[i - 1] is None or pos_pts[i] is None: continue
            thickness = int(np.sqrt(BUFFER_SIZE / float(i + 1)) * 2.5)
            cv2.line(frame, pos_pts[i - 1], pos_pts[i], (0, 0, 255), thickness)

        # Dashboard Elements
        cv2.rectangle(frame, (0, 0), (w, 100), (0, 0, 0), -1)  # Top Bar
        cv2.putText(frame, "AADES LIVE CAMERA DETECTION", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
        cv2.putText(frame, status_msg, (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.9, status_color, 2)
        cv2.putText(frame, vector_text, (20, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        # Satellite Body (Crosshair)
        cv2.line(frame, (center_x - 20, center_y), (center_x + 20, center_y), (100, 100, 100), 1)
        cv2.line(frame, (center_x, center_y - 20), (center_x, center_y + 20), (100, 100, 100), 1)
        cv2.circle(frame, (center_x, center_y), COLLISION_ZONE, (50, 50, 50), 1)
        
        # Encode frame to JPEG
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    
    # Clean up
    with camera_lock:
        if camera is not None:
            camera.release()


@app.route('/api/camera/start')
def start_camera():
    """Start camera detection"""
    global camera_active
    with camera_lock:
        if camera_active:
            return jsonify({'status': 'camera_already_running'})
        camera_active = True
    return jsonify({'status': 'camera_started'})


@app.route('/api/camera/stop')
def stop_camera():
    """Stop camera detection"""
    global camera_active, camera
    with camera_lock:
        camera_active = False
        if camera is not None:
            camera.release()
            camera = None
    return jsonify({'status': 'camera_stopped'})


@app.route('/api/camera/feed')
def camera_feed():
    """Video streaming route for camera feed"""
    return Response(generate_camera_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == '__main__':
    import os
    
    print("="*60)
    print("ORION-EYE System Starting")
    print("Simulated Onboard AI for Debris Avoidance")
    print("="*60)
    print("\nAccess dashboard at: http://localhost:5000")
    print("\nAvailable scenarios:")
    print("  1. Safe Passage - Nominal operations")
    print("  2. Collision Course - Critical avoidance")
    print("  3. Multiple Objects - Complex scenario")
    print("\n" + "="*60)
    
    # Use debug mode only in development (not in production)
    # Check FLASK_DEBUG for Flask 2.0+ compatibility
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)
