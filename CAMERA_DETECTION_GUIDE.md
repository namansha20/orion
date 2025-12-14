# 📹 AADES Camera Detection Quick Reference

## Overview
AADES (Autonomous Avoidance and Detection System) is a real-time camera-based object detection and tracking system that detects red objects, tracks their motion in 3D space, and predicts collision trajectories.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the system
python camera_detection.py

# Press 'q' to quit
```

## System Features

### 1. Object Detection
- **Method**: HSV color space filtering for red objects
- **Noise Reduction**: Gaussian blur + morphological operations (erosion/dilation)
- **Minimum Size**: 10 pixels radius
- **Color Ranges**: 
  - Red Range 1: H(0-10), S(120-255), V(70-255)
  - Red Range 2: H(170-180), S(120-255), V(70-255)

### 2. Motion Tracking
- **X/Y Velocity**: 9-frame smoothing for stable velocity calculation
- **Z-axis Motion**: Optical expansion detection (object size change)
- **Trajectory Trail**: 32-frame buffer with dynamic thickness visualization

### 3. Collision Prediction
- **Prediction Window**: 15 frames ahead
- **Collision Zone**: 80-pixel radius from screen center
- **Alert States**:
  - 🟢 **SCANNING SECTOR** - No objects detected
  - 🟡 **TRACKING TARGET** - Object detected, no collision risk
  - 🟠 **TRAJECTORY INTERSECT** - Path crosses zone but object receding
  - 🔴 **COLLISION COURSE** - Imminent collision with evasion recommendations

### 4. HUD Display
- **Top Dashboard**: Status bar with system name, alert message, velocity vector
- **Center Overlay**: Crosshair and collision zone circle
- **Trajectory Trail**: Red path showing object history
- **Velocity Arrow**: Cyan arrow showing predicted direction
- **Evasion Guide**: Smart thrust recommendations during collision alerts

## Configuration

Edit `camera_detection.py` to customize:

```python
# Color detection (HSV ranges for different lighting)
LOWER_RED1 = np.array([0, 120, 70])
UPPER_RED1 = np.array([10, 255, 255])
LOWER_RED2 = np.array([170, 120, 70])
UPPER_RED2 = np.array([180, 255, 255])

# Tracking parameters
BUFFER_SIZE = 32         # Trail length (frames)
PREDICTION_FRAMES = 15   # Prediction distance
COLLISION_ZONE = 80      # Detection radius (pixels)
GROWTH_THRESHOLD = 0.5   # Z-axis sensitivity
MOVEMENT_THRESHOLD = 2   # X/Y sensitivity
```

## Motion States

### Horizontal Motion
- **LEFT**: dx < -2
- **RIGHT**: dx > 2
- **STATIONARY**: -2 ≤ dx ≤ 2

### Vertical Motion
- **UP**: dy < -2
- **DOWN**: dy > 2
- **STATIONARY**: -2 ≤ dy ≤ 2

### Z-axis Motion (Depth)
- **APPROACHING**: growth_rate > 0.5 (object getting larger)
- **RECEDING**: growth_rate < -0.5 (object getting smaller)
- **STABLE**: -0.5 ≤ growth_rate ≤ 0.5

## Collision Detection Logic

```
IF predicted_position inside COLLISION_ZONE:
    IF object is APPROACHING:
        → 🔴 COLLISION COURSE
        → Display evasion recommendations
        → Draw warning line to object
    ELSE:
        → 🟠 TRAJECTORY INTERSECT (SAFE)
ELSE:
    → 🟡 TRACKING TARGET
```

## Evasion Recommendations

When collision detected, system calculates smart evasion:
- **Dodge Horizontal**: Opposite to object's X velocity
- **Dodge Vertical**: Opposite to object's Y velocity
- **Example**: If object moving LEFT + DOWN → Recommend "THRUST RIGHT & UP"

## Tips for Best Results

### Lighting
- Use good ambient lighting
- Avoid backlighting or harsh shadows
- Fluorescent or LED lighting works best

### Camera Setup
- Position camera at eye level
- Ensure clear background (not cluttered)
- Maintain 1-3 meter distance for optimal detection

### Object Selection
- Use solid red objects (balls, toys, markers)
- Smooth surfaces reflect better than textured
- Size: 5-20cm diameter works best
- Avoid transparent or shiny red objects

### Color Calibration
If detection is poor, adjust HSV ranges:
1. Capture frame and check object's HSV values
2. Adjust `LOWER_RED1/2` and `UPPER_RED1/2` accordingly
3. Lower S (saturation) for pale red objects
4. Lower V (value) for dark environments

## Troubleshooting

### No Object Detected
- Check lighting conditions
- Verify object is actually red in HSV space
- Adjust color ranges
- Ensure object is larger than 10 pixels radius

### False Detections
- Increase saturation threshold (S value in LOWER_RED)
- Use erosion/dilation iterations (already at 2)
- Check for other red objects in frame

### Jittery Motion
- Ensure stable camera mounting
- Check MOVEMENT_THRESHOLD (increase for more stability)
- Verify frame rate is consistent

### Incorrect Z-axis Detection
- Adjust GROWTH_THRESHOLD (default 0.5)
- Move object more dramatically
- Ensure object stays circular (not tilted)

## Technical Details

### Algorithm Flow
```
1. Capture frame from camera
2. Mirror frame (flip horizontal)
3. Apply Gaussian blur (11x11 kernel)
4. Convert BGR → HSV color space
5. Create binary mask (red color ranges)
6. Morphological operations (erode → dilate)
7. Find contours, select largest
8. Calculate centroid and radius
9. Update position and radius buffers
10. Calculate velocity and growth rate
11. Predict future position
12. Determine collision risk
13. Generate evasion recommendations
14. Render HUD and display
```

### Performance
- **FPS**: 30+ on modern hardware
- **Latency**: ~33ms per frame
- **CPU Usage**: 10-20% single core
- **Memory**: ~50MB

## Integration with Orion

The camera detection system complements the existing Orion space debris simulation:
- **Orion-Eye**: Simulated space debris tracking
- **AADES**: Real-world camera-based object detection

Both systems share similar concepts:
- Object detection and tracking
- Trajectory prediction
- Collision avoidance
- Autonomous decision-making

## Requirements

```
opencv-python==4.8.1.78
numpy>=1.26.2,<2.0.0
```

## License
Part of the Orion project - educational and demonstration purposes.

## Support
For issues or questions, refer to the main README.md or open an issue on GitHub.

---

**Built for real-time object detection and collision avoidance**

*"Real Cameras, Real Detection, Real Time"*
