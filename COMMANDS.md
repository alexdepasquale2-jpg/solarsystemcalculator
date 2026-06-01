# Command Reference

## Install

```powershell
pip install .
pip install .[ml]
pip install .[ephemeris]
pip install .[ml,ephemeris]
```

## List Commands

```powershell
python -m solarsystemcalculator commands
python -m solarsystemcalculator.help
solarsystemcalculator-help
```

## Distance Calculation

```powershell
python -m solarsystemcalculator earth mars
python -m solarsystemcalculator earth mars --unit au
python -m solarsystemcalculator earth mars --date 2024-06-20T20:51:00Z --unit km
python -m solarsystemcalculator earth mars --ephemeris de421.bsp --unit au
```

## Desktop GUI

```powershell
python -m solarsystemcalculator.gui
solarsystemcalculator-gui
```

## Generate Accurate Random Observations

Generates heliocentric J2000 ecliptic positions in AU using Skyfield and a JPL
ephemeris file.

```powershell
python generate_observations.py --bodies mars earth --count 128 --seed 42
python generate_observations.py --bodies mercury venus earth mars jupiter --count 256 --start 1900-01-01T00:00:00Z --end 2050-01-01T00:00:00Z
python generate_observations.py --output observations.csv --ephemeris de421.bsp
```

CSV columns:

```csv
body,datetime,x_au,y_au,z_au
mars,2024-06-20T20:51:00Z,1.3916575758,0.0868106900,-0.0323126230
```

## Train Residual Correction Model

```powershell
python self_improve.py observations.csv --model gaussian_process --output models/orbit_residual_model.joblib
python self_improve.py observations.csv --model ridge --cv-splits 5
python self_improve.py observations.csv --model mlp --test-fraction 0.2
```

Models:

- `gaussian_process`: best default for small scientific datasets and smooth interpolation.
- `ridge`: fast, stable linear residual baseline.
- `mlp`: neural network trained from scratch; useful when you have more observations.

## Script Help

```powershell
python generate_observations.py --help
python self_improve.py --help
python -m solarsystemcalculator --help
```
