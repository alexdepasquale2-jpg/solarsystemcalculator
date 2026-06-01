import numpy as np
from dataclasses import dataclass
from datetime import datetime, timezone
from scipy.optimize import newton
from typing import Dict, Optional, Tuple

from .planets import BodyProperties, get_body_properties, get_planet


@dataclass(frozen=True)
class OrbitState:
    """A heliocentric state and derived orbital attributes for one body."""

    body: str
    datetime_utc: datetime
    julian_date: float
    position_au: Tuple[float, float, float]
    velocity_au_per_day: Tuple[float, float, float]
    orbital_plane_position_au: Tuple[float, float, float]
    radius_au: float
    speed_au_per_day: float
    semi_major_axis_au: float
    eccentricity: float
    inclination_deg: float
    longitude_deg: float
    longitude_of_perihelion_deg: float
    longitude_of_ascending_node_deg: float
    argument_of_perihelion_deg: float
    mean_anomaly_deg: float
    eccentric_anomaly_deg: float
    true_anomaly_deg: float
    orbital_period_days: float
    perihelion_distance_au: float
    aphelion_distance_au: float
    days_since_perihelion: float
    days_to_perihelion: float
    mass_kg: float = 0.0
    radius_km: float = 0.0
    rotation_period_hours: float = 0.0
    axial_tilt_deg: float = 0.0
    albedo: float = 0.0
    moon_count: int = 0
    has_rings: bool = False
    body_type: str = ""
    category: str = ""
    atmosphere: str = ""
    surface_gravity_m_s2: float = 0.0
    escape_velocity_km_per_s: float = 0.0
    mean_density_g_cm3: float = 0.0
    specific_orbital_energy_km2_per_s2: float = 0.0
    semi_minor_axis_au: float = 0.0
    angular_momentum_vector_au2_per_day: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    angular_momentum_magnitude_au2_per_day: float = 0.0
    orbit_normal_vector_au2_per_day: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    eccentricity_vector: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    hill_sphere_radius_au: float = 0.0
    solar_irradiance_w_m2: float = 0.0
    insolation_relative_to_earth: float = 0.0


class SolarSystemCalculator:
    """
    High-precision calculator for solar system distances and positions.
    Uses Keplerian orbital mechanics with J2000 elements.
    """
    
    AU_TO_KM = 149597870.700      # IAU 2015
    AU_TO_M = 149597870700.0
    AU_TO_MILES = 92955807.273
    OBLIQUITY_J2000_DEG = 23.43928
    GAUSSIAN_GRAVITATIONAL_CONSTANT = 0.01720209895
    SUN_MASS_KG = 1.98847e30
    GRAVITATIONAL_CONSTANT = 6.67430e-11
    SOLAR_CONSTANT_W_M2 = 1361.0
    SECONDS_PER_DAY = 86400.0
    
    def __init__(self, precision: str = 'high', ephemeris: Optional[str] = None):
        """
        Initialize calculator.
        
        Parameters:
            precision: 'high' (float64) or 'max' (float128 if available)
            ephemeris: optional Skyfield ephemeris name or file path for higher-accuracy
                heliocentric positions and velocities.
        """
        self.dtype = np.float128 if precision == 'max' and hasattr(np, 'float128') else np.float64
        self.ephemeris = ephemeris
        self._skyfield_ephemeris = None
        self._skyfield_timescale = None
        
    def _julian_date(self, dt: datetime) -> float:
        """Convert datetime to Julian Date with high precision."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
        
        y, m, d = self.dtype(dt.year), self.dtype(dt.month), self.dtype(dt.day)
        
        # Fractional day with microsecond precision
        frac = (self.dtype(dt.hour) / 24 + 
                self.dtype(dt.minute) / 1440 + 
                self.dtype(dt.second) / 86400 + 
                self.dtype(dt.microsecond) / 86400e6)
        
        if m <= 2:
            y -= 1
            m += 12
        
        A = np.floor(y / 100)
        B = 2 - A + np.floor(A / 4)
        
        jd = np.floor(365.25 * (y + 4716)) + np.floor(30.6001 * (m + 1)) + d + frac + B - 1524.5
        return self.dtype(jd)
    
    def _time_centuries_since_j2000(self, dt: datetime) -> float:
        """Return Julian centuries from J2000.0."""
        jd = self._julian_date(dt)
        return (jd - self.dtype(2451545.0)) / self.dtype(36525.0)

    def _solve_kepler(self, M: float, e: float) -> float:
        """
        Solve Kepler's equation M = E - e*sin(E) using Newton-Raphson.
        
        Parameters:
            M: Mean anomaly (radians)
            e: Eccentricity
        
        Returns:
            E: Eccentric anomaly (radians)
        """
        M = self.dtype((M + np.pi) % (2 * np.pi) - np.pi)
        e = self.dtype(e)
        initial = M + e * np.sin(M)

        def equation(E):
            return E - e * np.sin(E) - M

        def derivative(E):
            return 1 - e * np.cos(E)

        return self.dtype(newton(equation, initial, fprime=derivative, tol=1e-14, maxiter=50))

    def _unit_factor(self, unit: str) -> float:
        conversions = {
            'au': 1.0,
            'km': self.AU_TO_KM,
            'm': self.AU_TO_M,
            'miles': self.AU_TO_MILES,
            'light_seconds': self.AU_TO_KM / 299792.458,
        }

        if unit not in conversions:
            raise ValueError(f"Unknown unit: {unit}. Use: {list(conversions.keys())}")

        return conversions[unit]

    def _load_ephemeris(self):
        if self._skyfield_ephemeris is not None:
            return

        try:
            from skyfield.api import load as _skyfield_load
        except ImportError as exc:
            raise ImportError(
                "Ephemeris mode requires the optional Skyfield dependency. "
                "Install with `pip install .[ephemeris]`."
            ) from exc

        self._skyfield_timescale = _skyfield_load.timescale()
        self._skyfield_ephemeris = _skyfield_load(self.ephemeris or "de421.bsp")

    def get_body_properties(self, body: str) -> BodyProperties:
        """Return physical and game-friendly body metadata."""
        return get_body_properties(body)

    def _ephemeris_target(self, body: str) -> str:
        if body.lower().strip() in {"sun", "sol"}:
            return "sun"

        planet = get_planet(body)
        if planet is None:
            raise ValueError(f"Unknown body: {body}")

        mapping = {
            'mercury': 'mercury',
            'venus': 'venus',
            'earth': 'earth',
            'mars': 'mars',
            'jupiter': 'jupiter barycenter',
            'saturn': 'saturn barycenter',
            'uranus': 'uranus barycenter',
            'neptune': 'neptune barycenter',
        }

        canonical_name = planet.name.lower()
        if canonical_name not in mapping:
            raise ValueError(f"Ephemeris mode does not support: {body}")
        return mapping[canonical_name]

    def _icrf_to_ecliptic(self, vector: np.ndarray) -> np.ndarray:
        epsilon = np.deg2rad(self.dtype(self.OBLIQUITY_J2000_DEG))
        x, y, z = vector
        return np.array(
            [
                x,
                np.cos(epsilon) * y + np.sin(epsilon) * z,
                -np.sin(epsilon) * y + np.cos(epsilon) * z,
            ],
            dtype=self.dtype,
        )

    def _ephemeris_heliocentric_position(self, planet_name: str, dt: Optional[datetime]) -> np.ndarray:
        if dt is None:
            dt = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)

        self._load_ephemeris()
        t = self._skyfield_timescale.utc(dt)
        target = self._ephemeris_target(planet_name)

        pos = np.asarray(self._skyfield_ephemeris[target].at(t).position.au, dtype=self.dtype)
        sun_pos = np.asarray(self._skyfield_ephemeris['sun'].at(t).position.au, dtype=self.dtype)
        return self._icrf_to_ecliptic(pos - sun_pos)

    def _ephemeris_heliocentric_velocity(self, planet_name: str, dt: Optional[datetime]) -> np.ndarray:
        if dt is None:
            dt = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)

        self._load_ephemeris()
        t = self._skyfield_timescale.utc(dt)
        target = self._ephemeris_target(planet_name)

        vel = np.asarray(self._skyfield_ephemeris[target].at(t).velocity.au_per_d, dtype=self.dtype)
        sun_vel = np.asarray(self._skyfield_ephemeris['sun'].at(t).velocity.au_per_d, dtype=self.dtype)
        return self._icrf_to_ecliptic(vel - sun_vel)

    def _state_from_ephemeris(self, planet_name: str, dt: datetime) -> OrbitState:
        planet = get_planet(planet_name)
        if planet is None:
            zero = (0.0, 0.0, 0.0)
            return OrbitState(
                body='sun',
                datetime_utc=dt,
                julian_date=float(self._julian_date(dt)),
                position_au=zero,
                velocity_au_per_day=zero,
                orbital_plane_position_au=zero,
                radius_au=0.0,
                speed_au_per_day=0.0,
                semi_major_axis_au=0.0,
                eccentricity=0.0,
                inclination_deg=0.0,
                longitude_deg=0.0,
                longitude_of_perihelion_deg=0.0,
                longitude_of_ascending_node_deg=0.0,
                argument_of_perihelion_deg=0.0,
                mean_anomaly_deg=0.0,
                eccentric_anomaly_deg=0.0,
                true_anomaly_deg=0.0,
                orbital_period_days=0.0,
                perihelion_distance_au=0.0,
                aphelion_distance_au=0.0,
                days_since_perihelion=0.0,
                days_to_perihelion=0.0,
            )

        position = self._ephemeris_heliocentric_position(planet_name, dt)
        velocity = self._ephemeris_heliocentric_velocity(planet_name, dt)
        return self._state_from_vectors(planet.name, dt, position, velocity)

    def _state_from_vectors(
        self,
        body: str,
        dt: datetime,
        position: np.ndarray,
        velocity: np.ndarray,
    ) -> OrbitState:
        position = np.asarray(position, dtype=self.dtype)
        velocity = np.asarray(velocity, dtype=self.dtype)
        body_props = get_body_properties(body)

        radius = np.linalg.norm(position)
        speed = np.linalg.norm(velocity)
        mu = self.dtype(self.GAUSSIAN_GRAVITATIONAL_CONSTANT**2)

        h = np.cross(position, velocity)
        h_norm = np.linalg.norm(h)
        n = np.cross(np.array([0.0, 0.0, 1.0], dtype=self.dtype), h)
        n_norm = np.linalg.norm(n)

        e_vec = (np.cross(velocity, h) / mu) - (position / radius)
        eccentricity = np.linalg.norm(e_vec)

        energy = self.dtype(0.5) * speed**2 - mu / radius
        semi_major_axis = -mu / (self.dtype(2.0) * energy)

        inclination = np.arccos(h[2] / h_norm) if h_norm > 0 else self.dtype(0.0)
        longitude_of_ascending_node = (
            np.arctan2(n[1], n[0]) if n_norm > 0 else self.dtype(0.0)
        )
        if longitude_of_ascending_node < 0:
            longitude_of_ascending_node += 2 * np.pi

        if eccentricity > 1e-12 and n_norm > 0:
            arg_perihelion = np.arccos(
                np.clip(np.dot(n, e_vec) / (n_norm * eccentricity), -1.0, 1.0)
            )
            if e_vec[2] < 0:
                arg_perihelion = 2 * np.pi - arg_perihelion
        else:
            arg_perihelion = self.dtype(0.0)

        if eccentricity > 1e-12:
            true_anomaly = np.arccos(
                np.clip(np.dot(e_vec, position) / (eccentricity * radius), -1.0, 1.0)
            )
            if np.dot(position, velocity) < 0:
                true_anomaly = 2 * np.pi - true_anomaly
            eccentric_anomaly = 2 * np.arctan2(
                np.sqrt(self.dtype(1.0) - eccentricity) * np.sin(true_anomaly / 2),
                np.sqrt(self.dtype(1.0) + eccentricity) * np.cos(true_anomaly / 2),
            )
        else:
            true_anomaly = self.dtype(0.0)
            eccentric_anomaly = self.dtype(0.0)

        if eccentric_anomaly < 0:
            eccentric_anomaly += 2 * np.pi

        mean_anomaly = eccentric_anomaly - eccentricity * np.sin(eccentric_anomaly)
        if mean_anomaly < 0:
            mean_anomaly += 2 * np.pi

        mean_motion = self.dtype(np.nan)
        orbital_period = self.dtype(np.nan)
        days_since_perihelion = self.dtype(np.nan)
        days_to_perihelion = self.dtype(np.nan)
        if semi_major_axis > 0:
            mean_motion = np.sqrt(mu / semi_major_axis**3)
            orbital_period = 2 * np.pi / mean_motion
            days_since_perihelion = mean_anomaly / mean_motion
            days_to_perihelion = (orbital_period - days_since_perihelion) % orbital_period

        orbital_plane_x = semi_major_axis * (np.cos(eccentric_anomaly) - eccentricity)
        orbital_plane_y = (
            semi_major_axis
            * np.sqrt(self.dtype(1.0) - eccentricity**2)
            * np.sin(eccentric_anomaly)
            if eccentricity < 1
            else self.dtype(0.0)
        )

        longitude = np.arctan2(position[1], position[0])
        if longitude < 0:
            longitude += 2 * np.pi

        longitude_of_perihelion = (longitude_of_ascending_node + arg_perihelion) % (2 * np.pi)

        radius_km = radius * self.AU_TO_KM
        velocity_km_s = speed * self.AU_TO_KM / self.SECONDS_PER_DAY
        surface_gravity = self.dtype(0.0)
        escape_velocity = self.dtype(0.0)
        mean_density = self.dtype(0.0)
        if body_props.radius_km > 0 and body_props.mass_kg > 0:
            radius_m = self.dtype(body_props.radius_km) * self.dtype(1000.0)
            surface_gravity = (self.dtype(self.GRAVITATIONAL_CONSTANT) * self.dtype(body_props.mass_kg)) / (radius_m**2)
            escape_velocity = np.sqrt(2 * self.dtype(self.GRAVITATIONAL_CONSTANT) * self.dtype(body_props.mass_kg) / radius_m) / self.dtype(1000.0)
            mean_density = (
                self.dtype(body_props.mass_kg)
                / (self.dtype(4.0) / self.dtype(3.0) * np.pi * radius_m**3)
                / self.dtype(1000.0)
            )

        semi_minor_axis = self.dtype(0.0)
        if semi_major_axis > 0 and eccentricity < 1:
            semi_minor_axis = semi_major_axis * np.sqrt(self.dtype(1.0) - eccentricity**2)

        hill_sphere_radius = self.dtype(0.0)
        if semi_major_axis > 0 and body_props.mass_kg > 0:
            hill_sphere_radius = semi_major_axis * np.cbrt(
                self.dtype(body_props.mass_kg) / (self.dtype(3.0) * self.dtype(self.SUN_MASS_KG))
            )

        solar_irradiance = self.dtype(0.0)
        insolation_ratio = self.dtype(0.0)
        if radius > 0:
            solar_irradiance = self.dtype(self.SOLAR_CONSTANT_W_M2) / (radius**2)
            insolation_ratio = solar_irradiance / self.dtype(self.SOLAR_CONSTANT_W_M2)

        orbit_normal = h / h_norm if h_norm > 0 else np.array([0.0, 0.0, 0.0], dtype=self.dtype)
        mu_km3_s2 = self.dtype(self.SUN_MASS_KG) * self.dtype(self.GRAVITATIONAL_CONSTANT) / self.dtype(1e9)

        return OrbitState(
            body=body,
            datetime_utc=dt,
            julian_date=float(self._julian_date(dt)),
            position_au=tuple(float(v) for v in position),
            velocity_au_per_day=tuple(float(v) for v in velocity),
            orbital_plane_position_au=(
                float(orbital_plane_x),
                float(orbital_plane_y),
                0.0,
            ),
            radius_au=float(radius),
            speed_au_per_day=float(speed),
            semi_major_axis_au=float(semi_major_axis),
            eccentricity=float(eccentricity),
            inclination_deg=float(np.rad2deg(inclination)),
            longitude_deg=float(np.rad2deg(longitude)),
            longitude_of_perihelion_deg=float(np.rad2deg(longitude_of_perihelion)),
            longitude_of_ascending_node_deg=float(np.rad2deg(longitude_of_ascending_node)),
            argument_of_perihelion_deg=float(np.rad2deg(arg_perihelion)),
            mean_anomaly_deg=float(np.rad2deg(mean_anomaly)),
            eccentric_anomaly_deg=float(np.rad2deg(eccentric_anomaly)),
            true_anomaly_deg=float(np.rad2deg(true_anomaly)),
            orbital_period_days=float(orbital_period),
            perihelion_distance_au=float(semi_major_axis * (1 - eccentricity)),
            aphelion_distance_au=float(semi_major_axis * (1 + eccentricity)),
            days_since_perihelion=float(days_since_perihelion),
            days_to_perihelion=float(days_to_perihelion),
            mass_kg=float(body_props.mass_kg),
            radius_km=float(body_props.radius_km),
            rotation_period_hours=float(body_props.rotation_period_hours),
            axial_tilt_deg=float(body_props.axial_tilt_deg),
            albedo=float(body_props.albedo),
            moon_count=int(body_props.moon_count),
            has_rings=bool(body_props.has_rings),
            body_type=body_props.body_type,
            category=body_props.category,
            atmosphere=body_props.atmosphere,
            surface_gravity_m_s2=float(surface_gravity),
            escape_velocity_km_per_s=float(escape_velocity),
            mean_density_g_cm3=float(mean_density),
            specific_orbital_energy_km2_per_s2=float(
                0.5 * velocity_km_s**2 - mu_km3_s2 / (radius * self.AU_TO_KM)
            ),
            semi_minor_axis_au=float(semi_minor_axis),
            angular_momentum_vector_au2_per_day=tuple(float(v) for v in h),
            angular_momentum_magnitude_au2_per_day=float(h_norm),
            orbit_normal_vector_au2_per_day=tuple(float(v) for v in orbit_normal),
            eccentricity_vector=tuple(float(v) for v in e_vec),
            hill_sphere_radius_au=float(hill_sphere_radius),
            solar_irradiance_w_m2=float(solar_irradiance),
            insolation_relative_to_earth=float(insolation_ratio),
        )

    def _elements_at(self, body: str, dt: datetime) -> Dict[str, float]:
        planet = get_planet(body)
        if planet is None:
            raise ValueError("The Sun does not have heliocentric orbital elements.")

        T = self._time_centuries_since_j2000(dt)
        a, e, I_deg, L_deg, omega_bar_deg, Omega_deg = planet.get_elements(T)
        M_deg = planet.mean_anomaly_degrees(T)
        M = np.deg2rad(self.dtype(M_deg))
        E = self._solve_kepler(M, e)
        true_anomaly = 2 * np.arctan2(
            np.sqrt(1 + e) * np.sin(E / 2),
            np.sqrt(1 - e) * np.cos(E / 2),
        )

        return {
            "T": T,
            "a": self.dtype(a),
            "e": self.dtype(e),
            "I": np.deg2rad(self.dtype(I_deg)),
            "L": np.deg2rad(self.dtype(L_deg)),
            "omega_bar": np.deg2rad(self.dtype(omega_bar_deg)),
            "Omega": np.deg2rad(self.dtype(Omega_deg)),
            "M": self.dtype(M),
            "E": self.dtype(E),
            "nu": self.dtype(true_anomaly),
            "I_deg": self.dtype(I_deg),
            "L_deg": self.dtype(L_deg),
            "omega_bar_deg": self.dtype(omega_bar_deg),
            "Omega_deg": self.dtype(Omega_deg),
            "M_deg": self.dtype(np.rad2deg((M + 2 * np.pi) % (2 * np.pi))),
        }

    def _rotate_orbital_to_ecliptic(
        self,
        x_prime: float,
        y_prime: float,
        omega: float,
        Omega: float,
        I: float,
    ) -> np.ndarray:
        cos_O, sin_O = np.cos(Omega), np.sin(Omega)
        cos_w, sin_w = np.cos(omega), np.sin(omega)
        cos_I, sin_I = np.cos(I), np.sin(I)

        x = (cos_O * cos_w - sin_O * sin_w * cos_I) * x_prime + \
            (-cos_O * sin_w - sin_O * cos_w * cos_I) * y_prime

        y = (sin_O * cos_w + cos_O * sin_w * cos_I) * x_prime + \
            (-sin_O * sin_w + cos_O * cos_w * cos_I) * y_prime

        z = (sin_w * sin_I) * x_prime + \
            (cos_w * sin_I) * y_prime

        return np.array([x, y, z], dtype=self.dtype)
    
    def get_heliocentric_position(self, planet_name: str, dt: Optional[datetime] = None) -> np.ndarray:
        """
        Calculate heliocentric ecliptic coordinates (x, y, z) in AU.
        
        Parameters:
            planet_name: Name of the planet
            dt: datetime (UTC). Defaults to now.
        
        Returns:
            numpy array [x, y, z] in AU
        """
        if self.ephemeris is not None:
            return self._ephemeris_heliocentric_position(planet_name, dt)

        if dt is None:
            dt = datetime.now(timezone.utc)
        
        # Special case: Sun is at origin
        planet = get_planet(planet_name)
        if planet is None:
            return np.array([0.0, 0.0, 0.0], dtype=self.dtype)
        
        elements = self._elements_at(planet_name, dt)
        a = elements["a"]
        e = elements["e"]
        E = elements["E"]
        omega = elements["omega_bar"] - elements["Omega"]

        x_prime = a * (np.cos(E) - e)
        y_prime = a * np.sqrt(1 - e**2) * np.sin(E)

        return self._rotate_orbital_to_ecliptic(
            x_prime,
            y_prime,
            omega,
            elements["Omega"],
            elements["I"],
        )

    def state(self, planet_name: str, dt: Optional[datetime] = None) -> OrbitState:
        """
        Calculate heliocentric position, velocity, and derived orbital attributes.

        Position is in J2000 ecliptic AU. Velocity is AU/day.
        """
        if dt is None:
            dt = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)

        planet = get_planet(planet_name)
        if planet is None:
            zero = (0.0, 0.0, 0.0)
            return OrbitState(
                body="sun",
                datetime_utc=dt,
                julian_date=float(self._julian_date(dt)),
                position_au=zero,
                velocity_au_per_day=zero,
                orbital_plane_position_au=zero,
                radius_au=0.0,
                speed_au_per_day=0.0,
                semi_major_axis_au=0.0,
                eccentricity=0.0,
                inclination_deg=0.0,
                longitude_deg=0.0,
                longitude_of_perihelion_deg=0.0,
                longitude_of_ascending_node_deg=0.0,
                argument_of_perihelion_deg=0.0,
                mean_anomaly_deg=0.0,
                eccentric_anomaly_deg=0.0,
                true_anomaly_deg=0.0,
                orbital_period_days=0.0,
                perihelion_distance_au=0.0,
                aphelion_distance_au=0.0,
                days_since_perihelion=0.0,
                days_to_perihelion=0.0,
            )

        if self.ephemeris is not None:
            return self._state_from_ephemeris(planet_name, dt)

        elements = self._elements_at(planet_name, dt)
        a = elements["a"]
        e = elements["e"]
        E = elements["E"]
        I = elements["I"]
        Omega = elements["Omega"]
        omega = elements["omega_bar"] - Omega

        x_prime = a * (np.cos(E) - e)
        y_prime = a * np.sqrt(1 - e**2) * np.sin(E)
        position = self._rotate_orbital_to_ecliptic(x_prime, y_prime, omega, Omega, I)
        mu = self.dtype(self.GAUSSIAN_GRAVITATIONAL_CONSTANT**2)
        mean_motion = np.sqrt(mu / a**3)
        velocity = self._rotate_orbital_to_ecliptic(
            -a * np.sin(E) * (mean_motion / (1 - e * np.cos(E))),
            a * np.sqrt(1 - e**2) * np.cos(E) * (mean_motion / (1 - e * np.cos(E))),
            omega,
            Omega,
            I,
        )

        return self._state_from_vectors(planet.name, dt, position, velocity)

    def position(self, body: str, dt: Optional[datetime] = None, unit: str = 'au') -> Tuple[float, float, float]:
        """Return heliocentric J2000 ecliptic position as an (x, y, z) tuple."""
        factor = self._unit_factor(unit)
        return tuple(float(v * factor) for v in self.get_heliocentric_position(body, dt))

    def velocity(self, body: str, dt: Optional[datetime] = None, unit: str = 'au_per_day') -> Tuple[float, float, float]:
        """Return heliocentric J2000 ecliptic velocity as an (vx, vy, vz) tuple."""
        state = self.state(body, dt)
        if unit == 'au_per_day':
            factor = 1.0
        elif unit == 'km_per_second':
            factor = self.AU_TO_KM / 86400.0
        else:
            raise ValueError("Unknown velocity unit. Use: ['au_per_day', 'km_per_second']")
        return tuple(float(v * factor) for v in state.velocity_au_per_day)

    def get_equatorial_position(self, planet_name: str, dt: Optional[datetime] = None) -> np.ndarray:
        """Calculate heliocentric equatorial J2000 coordinates (x, y, z) in AU."""
        ecliptic = self.get_heliocentric_position(planet_name, dt)
        epsilon = np.deg2rad(self.dtype(self.OBLIQUITY_J2000_DEG))
        x, y, z = ecliptic
        return np.array(
            [
                x,
                np.cos(epsilon) * y - np.sin(epsilon) * z,
                np.sin(epsilon) * y + np.cos(epsilon) * z,
            ],
            dtype=self.dtype,
        )

    def heliocentric_distance(self, body: str, dt: Optional[datetime] = None, unit: str = 'au') -> float:
        """Calculate a body's distance from the Sun."""
        return self.distance('sun', body, dt=dt, unit=unit)

    def angle_between(self, body1: str, body2: str, dt: Optional[datetime] = None, degrees: bool = True) -> float:
        """Calculate the Sun-centered 3D angle between two bodies."""
        pos1 = self.get_heliocentric_position(body1, dt)
        pos2 = self.get_heliocentric_position(body2, dt)
        norm1 = np.linalg.norm(pos1)
        norm2 = np.linalg.norm(pos2)

        if norm1 == 0 or norm2 == 0:
            raise ValueError("Cannot calculate a heliocentric angle involving the Sun.")

        cos_theta = np.dot(pos1, pos2) / (norm1 * norm2)
        theta = np.arccos(np.clip(cos_theta, -1.0, 1.0))
        return float(np.rad2deg(theta) if degrees else theta)

    def distance_from_radii_and_angle(
        self,
        radius1: float,
        radius2: float,
        angle: float,
        degrees: bool = True,
    ) -> float:
        """Distance from two heliocentric radii and their included angle."""
        theta = np.deg2rad(angle) if degrees else angle
        return float(np.sqrt(radius1**2 + radius2**2 - 2 * radius1 * radius2 * np.cos(theta)))
    
    def distance(self, body1: str, body2: str, dt: Optional[datetime] = None, unit: str = 'km') -> float:
        """
        Calculate distance between any two solar system bodies.
        
        Parameters:
            body1: Name of first body (planet or 'sun')
            body2: Name of second body (planet or 'sun')
            dt: datetime (UTC). Defaults to now.
            unit: 'km', 'au', 'm', 'miles', 'light_seconds'
        
        Returns:
            Distance in specified unit
        """
        pos1 = self.get_heliocentric_position(body1, dt)
        pos2 = self.get_heliocentric_position(body2, dt)
        
        dist_au = np.sqrt(np.sum((pos2 - pos1) ** 2))
        return float(dist_au * self._unit_factor(unit))
    
    def get_all_distances(self, reference: str, dt: Optional[datetime] = None, unit: str = 'km') -> dict:
        """
        Get distances from reference body to all other planets.
        
        Parameters:
            reference: Reference body name
            dt: datetime
            unit: output unit
        
        Returns:
            Dictionary of {planet_name: distance}
        """
        bodies = ['sun', 'mercury', 'venus', 'earth', 'mars', 
                  'jupiter', 'saturn', 'uranus', 'neptune']
        
        results = {}
        for body in bodies:
            if body != reference.lower():
                results[body] = self.distance(reference, body, dt, unit)
        
        return results


# Convenience function for quick calculations
def distance(body1: str, body2: str, dt=None, unit='km', precision='high'):
    """
    Quick calculation of distance between two solar system bodies.
    
    Example:
        distance('earth', 'mars')  # Current Earth-Mars distance in km
        distance('earth', 'jupiter', datetime(2024, 6, 1))  # Specific date
    """
    calc = SolarSystemCalculator(precision=precision)
    return calc.distance(body1, body2, dt, unit)
