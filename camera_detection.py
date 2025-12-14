"""
AADES - Autonomous Avoidance and Detection System
Real-time camera object detection and tracking
"""

import cv2
import numpy as np
from collections import deque

# --- CONFIGURATION ---
# Color Settings (Adjust for your red object/lighting)
LOWER_RED1 = np.array([0, 120, 70])
UPPER_RED1 = np.array([10, 255, 255])
LOWER_RED2 = np.array([170, 120, 70])
UPPER_RED2 = np.array([180, 255, 255])

# Tracking Physics
BUFFER_SIZE = 32         # Length of the red trail
PREDICTION_FRAMES = 15   # Length of the yellow prediction arrow
COLLISION_ZONE = 80      # Radius of the "Satellite Body" (Center screen)
GROWTH_THRESHOLD = 0.5   # Sensitivity for "Approaching" (Z-axis)
MOVEMENT_THRESHOLD = 2   # Sensitivity for Left/Right movement

def calculate_dynamics(pos_history, radius_history):
    """Calculates velocity in X, Y, and Z axes."""
    if len(pos_history) < 10 or len(radius_history) < 10:
        return (0, 0), 0
    
    # 1. X/Y Velocity (Smoothing over 9 frames)
    dx_total, dy_total = 0, 0
    for i in range(1, 10):
        pt_now = pos_history[i-1]
        pt_prev = pos_history[i]
        dx_total += (pt_now[0] - pt_prev[0])
        dy_total += (pt_now[1] - pt_prev[1])
    
    dx = int(dx_total / 9)
    dy = int(dy_total / 9)

    # 2. Z Velocity (Optical Expansion/Growth)
    r_now = np.mean(list(radius_history)[:5])
    r_old = np.mean(list(radius_history)[-5:])
    growth_rate = r_now - r_old 
    
    return (dx, dy), growth_rate

def get_direction_label(dx, dy):
    """Translates vector math into directions."""
    h_dir = ""
    v_dir = ""
    
    if dx > MOVEMENT_THRESHOLD: h_dir = "RIGHT"
    elif dx < -MOVEMENT_THRESHOLD: h_dir = "LEFT"
    
    if dy > MOVEMENT_THRESHOLD: v_dir = "DOWN"
    elif dy < -MOVEMENT_THRESHOLD: v_dir = "UP"
    
    if h_dir == "" and v_dir == "": return "STATIONARY"
    return f"{h_dir} {v_dir}".strip()

def main():
    cap = cv2.VideoCapture(0)
    
    # Deques act as the "Black Box Recorder" memory
    pos_pts = deque(maxlen=BUFFER_SIZE)
    rad_pts = deque(maxlen=BUFFER_SIZE)

    print("🛰️ AADES SYSTEM READY.")

    while True:
        ret, frame = cap.read()
        if not ret: break
        
        frame = cv2.flip(frame, 1) # Mirror view
        h, w, _ = frame.shape
        center_x, center_y = w // 2, h // 2
        
        # --- 1. COMPUTER VISION (The Sensor) ---
        blurred = cv2.GaussianBlur(frame, (11, 11), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, LOWER_RED1, UPPER_RED1) + cv2.inRange(hsv, LOWER_RED2, UPPER_RED2)
        mask = cv2.erode(mask, None, iterations=2)
        mask = cv2.dilate(mask, None, iterations=2)
        contours, _ = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Default HUD State
        status_msg = "SCANNING SECTOR..."
        status_color = (0, 255, 0) # Green
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
                
                # --- 2. DYNAMICS ANALYSIS (The Brain) ---
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

                # --- 3. DECISION MAKING ---
                if is_intercept and is_approaching:
                    status_color = (0, 0, 255) # Red
                    status_msg = "⚠️ COLLISION COURSE"
                    
                    # Smart Evasion Calculation
                    dodge_x = "RIGHT" if dx < 0 else "LEFT"
                    dodge_y = "DOWN" if dy < 0 else "UP"
                    
                    cv2.putText(frame, f"ACTION: THRUST {dodge_x} & {dodge_y}", (50, h - 80), 
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
                    
                    # Draw Collision Warning Line
                    cv2.line(frame, (int(x), int(y)), (center_x, center_y), (0, 0, 255), 3)

                elif is_intercept and not is_approaching:
                    status_color = (255, 100, 0) # Blue-ish
                    status_msg = "TRAJECTORY INTERSECT (SAFE - RECEDING)"
                else:
                    status_color = (0, 255, 255) # Yellow
                    status_msg = "TRACKING TARGET"

                # Update Vector Text
                vector_text = f"V: {direction_label} | Z: {z_label}"
                
                # Draw Object & Prediction
                cv2.circle(frame, (int(x), int(y)), int(radius), status_color, 2)
                if abs(dx) > 1 or abs(dy) > 1:
                    cv2.arrowedLine(frame, (int(x), int(y)), (int(x+dx*20), int(y+dy*20)), (0, 255, 255), 2)

        # --- 4. VISUALIZATION (The HUD) ---
        
        # DRAW TRAJECTORY TRAIL (Restored Feature)
        # We loop through the 'pos_pts' memory buffer
        for i in range(1, len(pos_pts)):
            if pos_pts[i - 1] is None or pos_pts[i] is None: continue
            
            # Dynamic thickness: Newer points are thicker
            thickness = int(np.sqrt(BUFFER_SIZE / float(i + 1)) * 2.5)
            
            # Draw the line (Red Trail)
            cv2.line(frame, pos_pts[i - 1], pos_pts[i], (0, 0, 255), thickness)

        # Dashboard Elements
        cv2.rectangle(frame, (0, 0), (w, 100), (0, 0, 0), -1) # Top Bar
        cv2.putText(frame, "AADES AUTONOMOUS SENSOR", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
        cv2.putText(frame, status_msg, (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.9, status_color, 2)
        cv2.putText(frame, vector_text, (20, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        # Satellite Body (Crosshair)
        cv2.line(frame, (center_x - 20, center_y), (center_x + 20, center_y), (100, 100, 100), 1)
        cv2.line(frame, (center_x, center_y - 20), (center_x, center_y + 20), (100, 100, 100), 1)
        cv2.circle(frame, (center_x, center_y), COLLISION_ZONE, (50, 50, 50), 1)

        cv2.imshow("AADES Final System", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
