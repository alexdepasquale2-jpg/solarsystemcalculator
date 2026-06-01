import numpy as np
from dataclasses import dataclass
from typing import Tuple

@dataclass
class OrbitalElements:
    """Planetary orbital elements with time-varying coefficients."""
    name: str
    
    # Base orbital elements.
    a0: float
    e0: float
    I0: float
    L0: float
    omega_bar0: float
    Omega0: float

    # Time derivatives per Julian century.
    a_dot: float = 0.0
    e_dot: float = 0.0
    I_dot: float = 0.0
    L_dot: float = 0.0
    omega_bar_dot: float = 0.0
    Omega_dot: float = 0.0
    b: float = 0.0
    c: float = 0.0
    s: float = 0.0
    f: float = 0.0
    
    def get_elements(self, T: float) -> Tuple[float, ...]:
        """
        Calculate elements at time T (Julian centuries from J2000).
        Returns: (a, e, I, L, omega_bar, Omega) in (AU, dimensionless, degrees, degrees, degrees, degrees).
        """
        a = self.a0 + self.a_dot * T
        e = self.e0 + self.e_dot * T
        I = self.I0 + self.I_dot * T
        L = self.L0 + self.L_dot * T
        omega_bar = self.omega_bar0 + self.omega_bar_dot * T
        Omega = self.Omega0 + self.Omega_dot * T
        
        return a, e, I, L, omega_bar, Omega

    def mean_anomaly_degrees(self, T: float) -> float:
        """Calculate mean anomaly in degrees with optional outer-planet correction terms."""
        _, _, _, L, omega_bar, _ = self.get_elements(T)
        return (
            L
            - omega_bar
            + self.b * T**2
            + self.c * np.cos(np.deg2rad(self.f * T))
            + self.s * np.sin(np.deg2rad(self.f * T))
        )


@dataclass(frozen=True)
class BodyProperties:
    """Physical body properties for simulation and game designers."""
    name: str
    body_type: str
    category: str
    mass_kg: float
    radius_km: float
    rotation_period_hours: float
    axial_tilt_deg: float
    albedo: float
    moon_count: int = 0
    has_rings: bool = False
    atmosphere: str = ""
    description: str = ""


# J2000 Orbital Elements (from NASA JPL)
# Valid for the time range 1800-2050 (higher precision than VSOP87 for this range)
PLANETARY_ELEMENTS = {
    'mercury': OrbitalElements(
        name='Mercury',
        a0=0.38709927, a_dot=0.00000037,
        e0=0.20563593, e_dot=0.00001906,
        I0=7.00497902, I_dot=-0.00594749,
        L0=252.25032350, L_dot=149472.67411175,
        omega_bar0=77.45779628, omega_bar_dot=0.16047689,
        Omega0=48.33076593, Omega_dot=-0.12534081
    ),
    
    'venus': OrbitalElements(
        name='Venus',
        a0=0.72333566, a_dot=0.00000390,
        e0=0.00677672, e_dot=-0.00004107,
        I0=3.39467605, I_dot=-0.00078890,
        L0=181.97909950, L_dot=58517.81538729,
        omega_bar0=131.60246718, omega_bar_dot=0.00268329,
        Omega0=76.67984255, Omega_dot=-0.27769418
    ),
    
    'earth': OrbitalElements(
        name='Earth',
        a0=1.00000261, a_dot=0.00000562,
        e0=0.01671123, e_dot=-0.00004392,
        I0=-0.00001531, I_dot=-0.01294668,
        L0=100.46457166, L_dot=35999.37244981,
        omega_bar0=102.93768193, omega_bar_dot=0.32327364,
        Omega0=0.0, Omega_dot=0.0
    ),
    
    'mars': OrbitalElements(
        name='Mars',
        a0=1.52371034, a_dot=0.00001847,
        e0=0.09339410, e_dot=0.00007882,
        I0=1.84969142, I_dot=-0.00813131,
        L0=-4.55343205, L_dot=19140.30268499,
        omega_bar0=-23.94362959, omega_bar_dot=0.44441088,
        Omega0=49.55953891, Omega_dot=-0.29257343
    ),
    
    'jupiter': OrbitalElements(
        name='Jupiter',
        a0=5.20288700, a_dot=-0.00011607,
        e0=0.04838624, e_dot=-0.00013253,
        I0=1.30439695, I_dot=-0.00183714,
        L0=34.39644051, L_dot=3034.74612775,
        omega_bar0=14.72847983, omega_bar_dot=0.21252668,
        Omega0=100.47390909, Omega_dot=0.20469106
    ),
    
    'saturn': OrbitalElements(
        name='Saturn',
        a0=9.53667594, a_dot=-0.00125060,
        e0=0.05386179, e_dot=-0.00050991,
        I0=2.48599187, I_dot=0.00193609,
        L0=49.95424423, L_dot=1222.49362201,
        omega_bar0=92.59887831, omega_bar_dot=-0.41897216,
        Omega0=113.66242448, Omega_dot=-0.28867794
    ),
    
    'uranus': OrbitalElements(
        name='Uranus',
        a0=19.18916464, a_dot=-0.00196176,
        e0=0.04725744, e_dot=-0.00004397,
        I0=0.77263783, I_dot=-0.00242939,
        L0=313.23810451, L_dot=428.48202785,
        omega_bar0=170.95427630, omega_bar_dot=0.40805281,
        Omega0=74.01692503, Omega_dot=0.04240589
    ),
    
    'neptune': OrbitalElements(
        name='Neptune',
        a0=30.06992276, a_dot=0.00026291,
        e0=0.00859048, e_dot=0.00005105,
        I0=1.77004347, I_dot=0.00035372,
        L0=-55.12002969, L_dot=218.45945325,
        omega_bar0=44.96476227, omega_bar_dot=-0.32241464,
        Omega0=131.78422574, Omega_dot=-0.00508664
    )
}

BODY_PROPERTIES = {
    'sun': BodyProperties(
        name='Sun',
        body_type='star',
        category='G-type main-sequence',
        mass_kg=1.98847e30,
        radius_km=695700.0,
        rotation_period_hours=609.12,
        axial_tilt_deg=7.25,
        albedo=0.0,
        moon_count=0,
        has_rings=False,
        atmosphere='plasma',
        description='The central star of the solar system.',
    ),
    'mercury': BodyProperties(
        name='Mercury',
        body_type='planet',
        category='terrestrial',
        mass_kg=3.3011e23,
        radius_km=2439.7,
        rotation_period_hours=1407.6,
        axial_tilt_deg=0.034,
        albedo=0.068,
        moon_count=0,
        has_rings=False,
        atmosphere='none',
        description='A small rocky planet with a heavily cratered surface.',
    ),
    'venus': BodyProperties(
        name='Venus',
        body_type='planet',
        category='terrestrial',
        mass_kg=4.8675e24,
        radius_km=6051.8,
        rotation_period_hours=-5832.5,
        axial_tilt_deg=177.36,
        albedo=0.75,
        moon_count=0,
        has_rings=False,
        atmosphere='carbon dioxide',
        description='A dense CO2 atmosphere with strong greenhouse heating.',
    ),
    'earth': BodyProperties(
        name='Earth',
        body_type='planet',
        category='terrestrial',
        mass_kg=5.97237e24,
        radius_km=6371.0,
        rotation_period_hours=23.9345,
        axial_tilt_deg=23.43928,
        albedo=0.306,
        moon_count=1,
        has_rings=False,
        atmosphere='nitrogen-oxygen',
        description='The home planet with liquid water and a breathable atmosphere.',
    ),
    'mars': BodyProperties(
        name='Mars',
        body_type='planet',
        category='terrestrial',
        mass_kg=6.4171e23,
        radius_km=3389.5,
        rotation_period_hours=24.6229,
        axial_tilt_deg=25.19,
        albedo=0.25,
        moon_count=2,
        has_rings=False,
        atmosphere='carbon dioxide',
        description='A cold desert world with thin atmosphere and polar ice caps.',
    ),
    'jupiter': BodyProperties(
        name='Jupiter',
        body_type='planet',
        category='gas giant',
        mass_kg=1.8982e27,
        radius_km=69911.0,
        rotation_period_hours=9.925,
        axial_tilt_deg=3.13,
        albedo=0.52,
        moon_count=95,
        has_rings=True,
        atmosphere='hydrogen-helium',
        description='The largest planet, a gas giant with a strong magnetic field.',
    ),
    'saturn': BodyProperties(
        name='Saturn',
        body_type='planet',
        category='gas giant',
        mass_kg=5.6834e26,
        radius_km=58232.0,
        rotation_period_hours=10.656,
        axial_tilt_deg=26.73,
        albedo=0.47,
        moon_count=83,
        has_rings=True,
        atmosphere='hydrogen-helium',
        description='Known for its extensive ring system and many moons.',
    ),
    'uranus': BodyProperties(
        name='Uranus',
        body_type='planet',
        category='ice giant',
        mass_kg=8.6810e25,
        radius_km=25362.0,
        rotation_period_hours=-17.24,
        axial_tilt_deg=97.77,
        albedo=0.51,
        moon_count=27,
        has_rings=True,
        atmosphere='hydrogen-helium-methane',
        description='An ice giant with an extreme axial tilt and faint rings.',
    ),
    'neptune': BodyProperties(
        name='Neptune',
        body_type='planet',
        category='ice giant',
        mass_kg=1.02413e26,
        radius_km=24622.0,
        rotation_period_hours=16.11,
        axial_tilt_deg=28.32,
        albedo=0.41,
        moon_count=14,
        has_rings=True,
        atmosphere='hydrogen-helium-methane',
        description='A distant ice giant with powerful winds and storms.',
    ),
}

# Aliases
PLANET_ALIASES = {
    'sun': None,  # Special case
    'sol': None,
    'mercury': 'mercury', 'merc': 'mercury',
    'venus': 'venus', 'ven': 'venus',
    'earth': 'earth', 'terra': 'earth', 'gaia': 'earth',
    'mars': 'mars', 'ares': 'mars',
    'jupiter': 'jupiter', 'jove': 'jupiter',
    'saturn': 'saturn',
    'uranus': 'uranus',
    'neptune': 'neptune'
}


def get_planet(name: str) -> OrbitalElements:
    """Get orbital elements by planet name (case-insensitive)."""
    key = name.lower().strip()
    canonical = PLANET_ALIASES.get(key, key)
    
    if canonical is None:
        return None  # Sun has no orbital elements
    
    if canonical not in PLANETARY_ELEMENTS:
        raise ValueError(f"Unknown planet: {name}. Available: {list(PLANETARY_ELEMENTS.keys())}")
    
    return PLANETARY_ELEMENTS[canonical]


def get_body_properties(name: str) -> BodyProperties:
    """Get physical and simulation-ready properties for a solar system body."""
    key = name.lower().strip()
    canonical = PLANET_ALIASES.get(key, key)
    if canonical is None:
        canonical = 'sun'

    if canonical not in BODY_PROPERTIES:
        raise ValueError(f"Unknown body: {name}. Available: {list(BODY_PROPERTIES.keys())}")

    return BODY_PROPERTIES[canonical]
