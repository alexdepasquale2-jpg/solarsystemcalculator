# Solar System Calculator

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://img.shields.io/badge/version-1.0.0-brightgreen.svg)](https://pypi.org/project/solarsystemcalculator/)

Professional-grade Python package for calculating accurate heliocentric positions, velocities, and distances between solar system bodies. Features real-time 3D visualization, machine learning correction models, and optional JPL ephemeris integration.

## ✨ Features

- 🌍 **Accurate Orbital Mechanics** - Keplerian element propagation with optional JPL ephemeris backend
- 🎨 **Real-time 3D Visualization** - Interactive OpenGL/Pygame visualizer with 365-day orbital prediction
- 🤖 **Machine Learning Models** - Learn residual corrections from observations using Gaussian Process, Ridge, or Neural Network
- 📊 **Professional CLI & GUI** - Command-line interface and Tkinter desktop application
- ⚡ **High Performance** - Fast formula-based calculations or high-precision ephemeris mode
- 🔧 **Easy Integration** - Clean Python API for seamless integration into your projects

## 🚀 Quick Start

### Installation

```bash
pip install solarsystemcalculator
```

### With Optional Features

```bash
# 3D Visualization
pip install solarsystemcalculator[visualizer]

# Machine Learning Models
pip install solarsystemcalculator[ml]

# High-Precision Ephemeris
pip install solarsystemcalculator[ephemeris]

# Everything
pip install solarsystemcalculator[ml,ephemeris,visualizer]
```

### 3D Visualization

```bash
launch-viz
# Or
solarsystemcalculator-viz
```

**Controls:**
- **Drag Mouse** - Rotate view
- **Scroll** - Zoom in/out
- **SPACE** - Pause/Resume
- **↑/↓** - Speed up/slow down
- **O/T/L/I** - Toggle orbits/trails/labels/info
- **ESC** - Exit

### Python API

```python
from solarsystemcalculator import SolarSystemCalculator, distance
from datetime import datetime, timezone

# Quick distance calculation
dist = distance("earth", "mars", unit="km")
print(f"Earth-Mars: {dist:,.0f} km")

# Complete orbital state
calc = SolarSystemCalculator()
state = calc.state("mars", datetime.now(timezone.utc))
print(f"Position: {state.position_au} AU")
print(f"Velocity: {state.velocity_au_per_day} AU/day")
print(f"Orbital Period: {state.orbital_period_days:.2f} days")
```

### Command Line

```bash
# Basic distance calculation
solarsystemcalculator earth mars --unit au

# At specific date
solarsystemcalculator earth mars --date 2024-06-20T20:51:00Z

# High precision
solarsystemcalculator earth mars --ephemeris de421.bsp --precision max

# Desktop GUI
solarsystemcalculator-gui
```

## 📚 Documentation

- **[GLOBAL_MANUAL.md](GLOBAL_MANUAL.md)** - Complete reference (27,900 words)
- **[QUICKREF.md](QUICKREF.md)** - Quick reference guide
- **[README.md](#readme)** - This file

## 🤖 Machine Learning Features

### Generate Training Data

```bash
pip install solarsystemcalculator[ephemeris]
python -m solarsystemcalculator.generate_observations --bodies mars earth --count 128
```

### Train Correction Model

```bash
pip install solarsystemcalculator[ml]
python -m solarsystemcalculator.train_model observations.csv --model gaussian_process
```

### Use Trained Model

```python
import joblib
from solarsystemcalculator.ml import ObservationInterpolator

model_data = joblib.load("models/orbit_residual_model.joblib")
model = ObservationInterpolator(calc, model_data)
corrected_position = model.predict_position("mars", datetime.now(timezone.utc))
```

## 📊 Performance

| Operation | Time | Notes |
|-----------|------|-------|
| Single distance | <1 ms | Formula-based |
| Full state vector | 1-2 ms | 22+ orbital elements |
| 3D frame render | ~16 ms | 60 FPS target |
| ML prediction | <10 ms | Depends on model |

## 🔬 Scientific Accuracy

- **Formula Mode**: ~0.01-0.1 AU error (fast, default)
- **Ephemeris Mode**: ~0.0001 AU error (high-precision JPL data)
- **ML-Corrected**: 1-10% additional improvement with observations

## 💻 System Requirements

- Python 3.9+
- NumPy, SciPy (always required)
- Optional: Pygame, PyOpenGL (visualization)
- Optional: scikit-learn, joblib (ML models)
- Optional: Skyfield, JPLephem (ephemeris)

## 🎯 Use Cases

- **Mission Planning** - Trajectory analysis and conjunction/opposition finding
- **Education** - Teach orbital mechanics visually
- **Research** - High-precision astronomical calculations
- **Games** - Realistic solar system backgrounds
- **Simulations** - N-body simulation initial conditions

## 📦 Available Commands

```bash
solarsystemcalculator          # Main CLI
solarsystemcalculator-help     # Show help
solarsystemcalculator-gui      # Desktop GUI
solarsystemcalculator-viz      # 3D Visualization
launch-viz                     # Alternative viz launch
launch-gui                     # Alternative GUI launch
```

## 🐍 Python API

### Core Classes

```python
from solarsystemcalculator import (
    SolarSystemCalculator,      # Main calculator
    OrbitState,                 # State vector (position, velocity, orbital elements)
    BodyProperties,             # Body metadata
    OrbitalElements,            # Orbital element set
)
```

### Key Functions

```python
from solarsystemcalculator import (
    distance,                   # Quick distance calculation
    format_distance,            # Pretty-print distance
    find_conjunction,           # Find conjunction dates
    get_body_properties,        # Get body metadata
    validate_body_name,         # Validate body name
    get_logger,                 # Get logger for debugging
)
```

### Exception Handling

```python
from solarsystemcalculator import (
    InvalidBodyError,           # Invalid body name
    CalculationError,          # Calculation failed
    ValidationError,           # Input validation failed
)
```

## 📋 Available Bodies

```
Sun
Mercury, Venus, Earth, Mars
Jupiter, Saturn, Uranus, Neptune
Moon (via Earth), Earth-Moon barycenter (EMB)
```

## ⚠️ Limitations & Trade-offs

1. **Visualization** - Sizes/distances logarithmically scaled (not to scale for visibility)
2. **Performance** - Large point clouds may reduce FPS
3. **Accuracy** - Keplerian elements have inherent limitations (use ephemeris for precision)
4. **ML Models** - Require sufficient observations for training (50+ recommended)

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Follow PEP 8 style guide
4. Write tests for new features
5. Submit a pull request

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **JPL Ephemeris**: NASA Jet Propulsion Laboratory (de421.bsp)
- **Orbital Elements**: Published NASA/ESA planetary data
- **Libraries**: NumPy, SciPy, scikit-learn, Pygame, PyOpenGL

## 🔗 Links

- **PyPI**: https://pypi.org/project/solarsystemcalculator/
- **GitHub**: https://github.com/yourusername/solarsystemcalculator
- **Documentation**: See GLOBAL_MANUAL.md in source
- **Issues**: Report bugs on GitHub

## 📞 Support

For questions or issues:
1. Check [GLOBAL_MANUAL.md](GLOBAL_MANUAL.md) - comprehensive reference
2. Review [QUICKREF.md](QUICKREF.md) - quick answers
3. Open an issue on GitHub
4. Review examples in package

## 🚀 What's Next?

1. **Install**: `pip install solarsystemcalculator[all]`
2. **Explore**: `launch-viz`
3. **Learn**: Read GLOBAL_MANUAL.md
4. **Integrate**: Use Python API in your project
5. **Train**: `python -m solarsystemcalculator.train_model`

---

**Status**: ✅ Production Ready | **Version**: 1.0.0 | **License**: MIT

**Made with ❤️ for astronomy and orbital mechanics enthusiasts**
