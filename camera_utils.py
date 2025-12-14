"""
Shared utilities for camera-based debris detection
"""

import numpy as np

# --- CONFIGURATION ---
# Color Settings (Adjust for your red object/lighting)
LOWER_RED1 = np.array([0, 120, 70])
UPPER_RED1 = np.array([10, 255, 255])
LOWER_RED2 = np.array([170, 120, 70])
UPPER_RED2 = np.array([180, 255, 255])

# Tracking Physics
BUFFER_SIZE = 32         # Length of the red trail
PREDICTION_FRAMES = 15   # Length of the cyan prediction arrow
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
    # For deque, index 0 is most recent, so [:5] are newest, [-5:] are oldest
    r_now = np.mean(list(radius_history)[:5])  # Most recent 5 frames
    r_old = np.mean(list(radius_history)[-5:])  # Oldest 5 frames
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
