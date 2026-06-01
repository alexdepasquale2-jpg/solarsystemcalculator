from datetime import datetime, timezone

from solarsystemcalculator import SolarSystemCalculator, format_distance

calc = SolarSystemCalculator(precision='max')

planets_interested = ['earth', 'mars']

mars_dist = calc.distance('earth', 'mars', unit='km')
print(f"Earth to Mars right now: {format_distance(mars_dist)}")

june_solstice = datetime(2024, 6, 20, 20, 51, 0, tzinfo=timezone.utc)
au_dist = calc.distance('earth', 'sun', dt=june_solstice, unit='au')
print(f"Earth-Sun distance at June solstice: {au_dist:.6f} AU")

# Law-of-cosines check for the same date and the actual Sun-centered angle:
# d = sqrt(r1^2 + r2^2 - 2*r1*r2*cos(theta))
earth_sun_distance = calc.heliocentric_distance('earth', dt=june_solstice, unit='au')
mars_sun_distance = calc.heliocentric_distance('mars', dt=june_solstice, unit='au')
theta = calc.angle_between('earth', 'mars', dt=june_solstice, degrees=True)
calculated_distance = calc.distance_from_radii_and_angle(
    earth_sun_distance,
    mars_sun_distance,
    theta,
    degrees=True,
)

print(f"Earth-Sun radius: {earth_sun_distance:.6f} AU")
print(f"Mars-Sun radius: {mars_sun_distance:.6f} AU")
print(f"Actual Sun-centered Earth-Mars angle: {theta:.6f} degrees")
print(f"Law-of-cosines Earth-Mars distance: {calculated_distance:.12f} AU")

vector_distance = calc.distance('earth', 'mars', dt=june_solstice, unit='au')
difference = abs(vector_distance - calculated_distance)
print(f"3D vector Earth-Mars distance: {vector_distance:.12f} AU")
print(f"Difference between equivalent formulas: {difference:.12e} AU")
