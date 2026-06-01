# 🎁 PyPI Package Release Guide

**Version:** 1.0.0  
**Status:** ✅ Production Ready  
**Date:** June 1, 2026

---

## 📋 Pre-Release Checklist

### ✅ Code Quality
- [x] All tests pass
- [x] No breaking changes
- [x] Code follows PEP 8
- [x] Type hints added
- [x] Docstrings complete
- [x] Error handling robust

### ✅ Documentation
- [x] README.md optimized for PyPI
- [x] GLOBAL_MANUAL.md (27,900 words)
- [x] QUICKREF.md (quick reference)
- [x] COMMANDS.md (CLI reference)
- [x] LICENSE file (MIT)
- [x] CHANGELOG ready

### ✅ Packaging
- [x] pyproject.toml complete
- [x] All dependencies declared
- [x] Entry points configured
- [x] Optional dependencies defined
- [x] Metadata accurate
- [x] Keywords/classifiers set

### ✅ Version Management
- [x] Version 1.0.0 set in __init__.py
- [x] Version 1.0.0 set in pyproject.toml
- [x] Consistent across files

---

## 🚀 Release Steps

### Step 1: Build Distribution Files

```bash
# Install build tools
pip install build twine

# Build distribution
python -m build

# Output: dist/solarsystemcalculator-1.0.0-py3-none-any.whl
#         dist/solarsystemcalculator-1.0.0.tar.gz
```

### Step 2: Validate Distribution

```bash
# Check metadata
twine check dist/*

# Should output:
# Checking distribution dist/solarsystemcalculator-1.0.0-py3-none-any.whl: Passed
# Checking distribution dist/solarsystemcalculator-1.0.0.tar.gz: Passed
```

### Step 3: Test Installation (Local)

```bash
# Create test environment
python -m venv test_env
source test_env/bin/activate  # or test_env\Scripts\activate on Windows

# Install from local wheel
pip install dist/solarsystemcalculator-1.0.0-py3-none-any.whl

# Test imports
python -c "from solarsystemcalculator import distance; print(distance('earth', 'mars', unit='au'))"

# Test CLI
solarsystemcalculator earth mars

# Test GUI launching (visual test)
launch-viz
```

### Step 4: Upload to PyPI

```bash
# First time: Create account at https://pypi.org/account/register/
# Then: Store credentials in ~/.pypirc

# Upload to TestPyPI (recommended first)
twine upload --repository testpypi dist/*

# Then upload to Production PyPI
twine upload dist/*
```

### Step 5: Verify PyPI Release

```bash
# Install from PyPI
pip install solarsystemcalculator

# Test
python -c "from solarsystemcalculator import SolarSystemCalculator; print('✓ Installed successfully')"
```

---

## 📦 Package Contents

### Core Modules
```
solarsystemcalculator/
├── __init__.py              # Public API exports
├── __main__.py              # CLI entry point
├── calculator.py            # Core orbital mechanics
├── planets.py               # Body data & orbital elements
├── gui.py                   # Tkinter GUI
├── ml.py                    # ML models
├── utils.py                 # Utility functions
├── help.py                  # Help text
├── logging_utils.py         # Error handling
├── visualizer.py            # 3D visualization
└── train_gui.py             # Training GUI
```

### Documentation Files
```
├── README.md                # PyPI-ready description
├── GLOBAL_MANUAL.md         # 27,900-word reference
├── QUICKREF.md              # Quick reference
├── COMMANDS.md              # CLI commands
├── PROJECT_REVIEW.md        # Project assessment
├── IMPROVEMENTS.md          # Feature docs
├── LICENSE                  # MIT License
├── pyproject.toml           # Package config
└── .gitignore              # Git settings
```

### Entry Scripts
```
solarsystemcalculator          # Main CLI
solarsystemcalculator-help     # Help
solarsystemcalculator-gui      # GUI
solarsystemcalculator-viz      # Visualizer
launch-viz                     # Alt viz
launch-gui                     # Alt GUI
```

---

## 📊 Installation Variants

Users can install in different ways:

```bash
# Minimal (core only)
pip install solarsystemcalculator

# With visualization
pip install solarsystemcalculator[visualizer]

# With ML training
pip install solarsystemcalculator[ml]

# With ephemeris
pip install solarsystemcalculator[ephemeris]

# Everything
pip install solarsystemcalculator[ml,ephemeris,visualizer]

# Development
pip install solarsystemcalculator[dev]
```

---

## 🔧 Build & Upload Tools

### Required Tools
```bash
pip install build twine
```

### Build Distribution
```bash
# Build wheel and source distribution
python -m build

# Creates:
# - dist/solarsystemcalculator-1.0.0-py3-none-any.whl (binary)
# - dist/solarsystemcalculator-1.0.0.tar.gz (source)
```

### Validate Before Upload
```bash
# Check for issues
twine check dist/*

# View what will be uploaded
twine check dist/* --strict
```

### Upload to PyPI
```bash
# Requires PyPI credentials (stored in ~/.pypirc or environment)

# Test PyPI (recommended first)
twine upload --repository testpypi dist/*

# Production PyPI
twine upload dist/*

# Specify credentials (if not in .pypirc)
twine upload --username __token__ --password pypi-AgEIcHlwaS5vcmc... dist/*
```

---

## 🔐 PyPI Setup

### Create .pypirc File

**Linux/Mac:** `~/.pypirc`
**Windows:** `%APPDATA%\pypi\.pypirc`

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-AgEIcHlwaS5vcmc... (your PyPI token)

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-AgEIcHlwaS5vcmc... (your TestPyPI token)
```

### Generate Token
1. Go to https://pypi.org/account/login/
2. Navigate to Account Settings → API tokens
3. Create New Token → Scope: Entire account
4. Copy and paste into .pypirc

---

## 🧪 Testing After Release

### Test Installation from PyPI

```bash
# Fresh environment
python -m venv test_final
source test_final/bin/activate

# Install from PyPI
pip install solarsystemcalculator[all]

# Test core functionality
python << 'EOF'
from solarsystemcalculator import distance, SolarSystemCalculator
from datetime import datetime, timezone

# Test distance
dist = distance("earth", "mars", unit="au")
print(f"✓ Distance: {dist:.6f} AU")

# Test calculator
calc = SolarSystemCalculator()
state = calc.state("mars", datetime.now(timezone.utc))
print(f"✓ Position: {state.position_au}")

# Test CLI
import subprocess
result = subprocess.run(["solarsystemcalculator", "earth", "mars", "--unit", "au"], 
                       capture_output=True, text=True)
print(f"✓ CLI works: {result.stdout.strip()}")

print("\n✅ All tests passed!")
EOF
```

---

## 📈 Version Management

### Versioning Scheme
- Format: `MAJOR.MINOR.PATCH`
- Example: `1.0.0`

### Update Version For Next Release
```python
# solarsystemcalculator/__init__.py
__version__ = "1.1.0"  # Update here

# pyproject.toml
version = "1.1.0"  # Update here too
```

### Create Release Notes
```markdown
# Version 1.1.0 (YYYY-MM-DD)

## New Features
- Feature 1
- Feature 2

## Bug Fixes
- Fix 1
- Fix 2

## Breaking Changes
- None

## Upgrade Instructions
pip install --upgrade solarsystemcalculator
```

---

## 🐛 Common Issues & Solutions

### Issue: "twine check" fails
**Solution:** Ensure README.md is valid Markdown and classifiers are valid

### Issue: Import fails after pip install
**Solution:** Check __init__.py exports and package structure

### Issue: CLI commands not available
**Solution:** Verify entry_points in pyproject.toml

### Issue: Optional dependencies not installing
**Solution:** Use `pip install package[extra]` format

### Issue: Version mismatch
**Solution:** Update both __init__.py and pyproject.toml

---

## 📝 Changelog

### Version 1.0.0 (June 1, 2026)

**Initial Release** ✨

#### Features
- ✨ Real-time 3D visualization (pygame + OpenGL)
- 🤖 Machine learning correction models
- 📊 Professional desktop GUI (tkinter)
- 🎯 Accurate orbital mechanics (Keplerian + JPL ephemeris)
- 🔧 CLI with comprehensive help
- 🐍 Clean Python API

#### Documentation
- 📚 27,900-word comprehensive manual
- 📖 Quick reference guide
- 🎓 Complete API documentation
- 🎁 Professional packaging for pip

#### Quality
- ✅ Production ready
- ✅ Comprehensive error handling
- ✅ Type hints throughout
- ✅ Fully tested
- ✅ MIT licensed

---

## 🎯 What Users Get

When they install: `pip install solarsystemcalculator`

✅ **Core Package**
- SolarSystemCalculator class
- Orbital mechanics
- Distance calculations
- CLI interface

✅ **Optional: [visualizer]**
- 3D interactive visualization
- Real-time rendering
- Orbital prediction

✅ **Optional: [ml]**
- Machine learning models
- Training utilities
- Correction models

✅ **Optional: [ephemeris]**
- JPL ephemeris integration
- High-precision mode
- Skyfield backend

✅ **CLI Commands**
- `solarsystemcalculator` - Main CLI
- `solarsystemcalculator-gui` - Desktop GUI
- `solarsystemcalculator-viz` - 3D viewer
- `launch-viz` - Quick launch
- `launch-gui` - GUI launch

---

## 🚀 Distribution Channels

### PyPI (Primary)
- **URL:** https://pypi.org/project/solarsystemcalculator/
- **Install:** `pip install solarsystemcalculator`
- **Status:** Production ready

### GitHub Releases
- **URL:** https://github.com/yourusername/solarsystemcalculator/releases
- **Format:** Source code + wheel + changelog

### Source Distribution
- **File:** solarsystemcalculator-1.0.0.tar.gz
- **Contains:** All source code and documentation

### Wheel Distribution
- **File:** solarsystemcalculator-1.0.0-py3-none-any.whl
- **Benefit:** Faster installation, pre-built

---

## 📞 Support After Release

### User Support Channels
1. **GitHub Issues** - Bug reports and feature requests
2. **Discussions** - Q&A and community support
3. **Documentation** - GLOBAL_MANUAL.md covers everything
4. **Examples** - See package for usage examples

### Maintenance
- Monitor for issues
- Update dependencies
- Release patches for bugs
- Plan major versions

---

## ✨ Success Metrics

After release, monitor:
- PyPI downloads
- GitHub stars
- GitHub issues/PRs
- User feedback

---

## 🎉 You're Ready to Release!

All packaging is complete and professional. Follow the steps above to:

1. ✅ Build distribution files
2. ✅ Test locally
3. ✅ Upload to TestPyPI (optional but recommended)
4. ✅ Upload to PyPI
5. ✅ Verify installation

**Good luck with your release! 🚀**

---

Generated: June 1, 2026  
Status: ✅ Ready for Production Release
