# Solar System Calculator - Quick Reference Cheat Sheet

## Installation

```bash
# Base installation
pip install .

# Add features
pip install .[visualizer]           # 3D visualization
pip install .[ml]                   # Machine learning models
pip install .[ephemeris]            # JPL high-precision ephemeris
pip install .[ml,ephemeris,visualizer]  # Everything
```

## 3D Visualization (NEW!)

### Launch Visualizer
```bash
launch-viz                          # Quick launch
solarsystemcalculator-viz          # Alternative
python launch_visualizer.py         # Direct script
```

### Visualizer Controls
| Key/Action | Effect |
|---|---|
| **Drag Mouse** | Rotate view |
| **Scroll Wheel** | Zoom in/out |
| **SPACE** | Pause/resume |
| **↑ / ↓** | Speed up/slow down time |
| **O** | Toggle orbits |
| **T** | Toggle trails |
| **L** | Toggle labels |
| **I** | Toggle info |
| **R** | Reset to now |
| **1/2/3** | Focus Sun/Earth/Mars |
| **ESC** | Exit |

### Programmatic Launch
```python
from solarsystemcalculator.visualizer import launch_visualizer

# Default bodies
launch_visualizer()

# Custom bodies and window size
launch_visualizer(
    bodies=['sun', 'earth', 'mars', 'jupiter'],
    width=1920,
    height=1080
)
```

---

## Command Line

### Basic Distance Calculation
```bash
# Earth to Mars in km (default)
python -m solarsystemcalculator earth mars

# With specific unit
python -m solarsystemcalculator earth mars --unit au
python -m solarsystemcalculator earth mars --unit miles

# At specific date
python -m solarsystemcalculator earth mars --date 2024-06-20T20:51:00Z

# High precision ephemeris
python -m solarsystemcalculator earth mars --ephemeris de421.bsp

# Debug mode
python -m solarsystemcalculator earth mars --verbose
```

### Available Units
- `km` (kilometers, default)
- `au` (astronomical units)
- `m` (meters)
- `miles` (miles)
- `light_seconds` (light travel time)

### Available Bodies
```
sun, mercury, venus, earth, mars, jupiter, saturn, uranus, neptune
```

### Help
```bash
python -m solarsystemcalculator --help
python -m solarsystemcalculator commands
solarsystemcalculator-help
```

---

## Python API

### Basic Usage
```python
from solarsystemcalculator import SolarSystemCalculator, distance, format_distance
from datetime import datetime, timezone

# Create calculator
calc = SolarSystemCalculator()

# Distance between bodies
d = calc.distance("earth", "mars", unit="km")
print(format_distance(d))  # Pretty print

# Alternative shortcut
d = distance("earth", "mars", unit="km")
```

### Full Orbital State
```python
from datetime import datetime, timezone

calc = SolarSystemCalculator()

# Get full state vector
state = calc.state("mars", datetime(2024, 6, 20, tzinfo=timezone.utc))

print(state.position_au)                    # (x, y, z) in AU
print(state.velocity_au_per_day)            # Velocity vector
print(state.radius_au)                      # Distance from Sun
print(state.true_anomaly_deg)               # True anomaly
print(state.orbital_period_days)            # Orbital period
print(state.solar_irradiance_w_m2)         # Solar irradiance received
print(state.hill_sphere_radius_au)         # Sphere of influence
```

### High Precision Mode
```python
# Float128 precision (if available)
calc = SolarSystemCalculator(precision='max')

# Use JPL ephemeris for accuracy
calc = SolarSystemCalculator(ephemeris="de421.bsp")

# Both
calc = SolarSystemCalculator(precision='max', ephemeris="de421.bsp")
```

### Error Handling
```python
from solarsystemcalculator import validate_body_name, InvalidBodyError, get_logger

logger = get_logger(verbose=True)

try:
    body = validate_body_name("earth")
    logger.debug(f"Valid body: {body}")
except InvalidBodyError as e:
    print(f"Error: {e}")
```

### Machine Learning Correction
```python
from solarsystemcalculator.ml import ObservationInterpolator

# Create model
model = ObservationInterpolator(calc)

# Fit with observations
model.fit("mars", observation_dates, observed_positions_au)

# Predict with correction
corrected_position = model.predict_position(dt)
```

---

## GUI

### Launch Desktop Control Panel
```bash
python -m solarsystemcalculator.gui
solarsystemcalculator-gui
```

**Features:**
- Body selection dropdown
- Date/time picker
- Unit selector
- Formula vs Ephemeris toggle
- Real-time distance display
- Orbital state viewer
- Distance table (all body pairs)
- Top-down orbit visualization
- Training model launcher

---

## Generate Observations

### Create Dataset from Ephemeris
```bash
pip install .[ephemeris]

# Generate observations
python generate_observations.py --bodies mars earth --count 128 --seed 42

# Custom date range
python generate_observations.py \
    --bodies mercury venus earth mars jupiter \
    --count 256 \
    --start 1900-01-01T00:00:00Z \
    --end 2050-01-01T00:00:00Z

# Output to file
python generate_observations.py --output my_observations.csv
```

---

## Train ML Models

### Self-Improvement Training
```bash
pip install .[ml]

# Gaussian Process (recommended for science)
python self_improve.py observations.csv --model gaussian_process

# Ridge regression (fast baseline)
python self_improve.py observations.csv --model ridge

# Neural network (deep learning)
python self_improve.py observations.csv --model mlp

# Save to specific location
python self_improve.py observations.csv \
    --model gaussian_process \
    --output models/mars_model.joblib
```

### CSV Format Required
```csv
body,datetime,x_au,y_au,z_au
mars,2024-06-20T20:51:00Z,1.3916575758,0.0868106900,-0.0323126230
earth,2024-06-20T20:51:00Z,0.9833098670,-0.1774865660,-0.0050099630
```

---

## Documentation

| File | Purpose |
|------|---------|
| `README.md` | Package overview and quick start |
| `COMMANDS.md` | CLI reference |
| `IMPROVEMENTS.md` | New features and improvements (9500+ words) |
| `PROJECT_REVIEW.md` | Comprehensive project assessment |

---

## Troubleshooting

### "No module named 'pygame'"
```bash
pip install .[visualizer]
```

### "No module named 'OpenGL'"
```bash
pip install PyOpenGL PyOpenGL_accelerate
```

### "No module named 'sklearn'"
```bash
pip install .[ml]
```

### Visualizer won't launch
```bash
# Check if requirements installed
python -c "import pygame; import OpenGL.GL; print('✓ OK')"

# Check with verbose
python -m solarsystemcalculator.visualizer --verbose
```

### Accuracy issues
```bash
# Use high-precision ephemeris
# Download: https://naif.jpl.nasa.gov/naif/data/generic_kernels/spk/planets/
# Save as: de421.bsp

python -m solarsystemcalculator earth mars \
    --ephemeris de421.bsp \
    --precision max
```

---

## Performance Tips

| Need | Solution |
|------|----------|
| **Speed** | Use formula-based (default) |
| **Accuracy** | Add `--ephemeris de421.bsp` |
| **Better GUI** | Launch `solarsystemcalculator-gui` |
| **Smooth viz** | Ensure 60 FPS (reduce bodies or camera distance) |
| **Better training** | Use more observations (128-256+) |

---

## Examples

### Mission Planning
```python
from solarsystemcalculator import SolarSystemCalculator
from datetime import datetime, timezone, timedelta

calc = SolarSystemCalculator()

# Find closest approach date
best_distance = float('inf')
best_date = None

for offset in range(365):
    dt = datetime(2024, 6, 20, tzinfo=timezone.utc) + timedelta(days=offset)
    distance = calc.distance("earth", "mars", dt=dt, unit="km")
    
    if distance < best_distance:
        best_distance = distance
        best_date = dt

print(f"Closest: {best_date.date()} at {best_distance:,.0f} km")
```

### Visualization Study
```python
from solarsystemcalculator.visualizer import launch_visualizer

# Study Mars opposition
launch_visualizer(
    bodies=['sun', 'earth', 'mars'],
    width=1600,
    height=1200
)

# Navigate to August 2026 (opposition season)
# Observe how Earth and Mars align
```

---

## Version & Status

- **Version:** 1.0.0+viz
- **Status:** Production Ready ✅
- **Last Updated:** June 1, 2026

---

See full documentation:
- [PROJECT_REVIEW.md](PROJECT_REVIEW.md) - Complete assessment
- [IMPROVEMENTS.md](IMPROVEMENTS.md) - Detailed improvements
- [README.md](README.md) - Package overview
- [COMMANDS.md](COMMANDS.md) - CLI reference
