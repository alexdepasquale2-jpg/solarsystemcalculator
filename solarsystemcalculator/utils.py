from datetime import datetime, timedelta
from typing import List

def find_conjunction(body1: str, body2: str, start: datetime, end: datetime, 
                     calculator, step_days=1):
    """
    Find minimum distance (conjunction) between two bodies in a date range.
    
    Parameters:
        body1, body2: Planet names
        start, end: datetime range
        calculator: SolarSystemCalculator instance
        step_days: Initial search step size
    
    Returns:
        (datetime of closest approach, minimum distance in AU)
    """
    current = start
    min_dist = float('inf')
    min_time = start
    
    # Coarse search
    while current <= end:
        pos1 = calculator.get_heliocentric_position(body1, current)
        pos2 = calculator.get_heliocentric_position(body2, current)
        dist = ((pos2[0] - pos1[0])**2 + (pos2[1] - pos1[1])**2 + (pos2[2] - pos1[2])**2)**0.5
        
        if dist < min_dist:
            min_dist = dist
            min_time = current
        
        current += timedelta(days=step_days)
    
    return min_time, min_dist


def format_distance(km: float) -> str:
    """Format large distance in human-readable form."""
    if km >= 1e9:
        return f"{km/1e9:.3f} billion km"
    elif km >= 1e6:
        return f"{km/1e6:.3f} million km"
    else:
        return f"{km:,.0f} km"