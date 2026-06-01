#!/usr/bin/env python3
"""
Quick launcher for the pygame 3D solar system visualizer.
"""

import sys
from solarsystemcalculator.visualizer import launch_visualizer


def main():
    """Launch the visualizer with default or custom bodies."""
    # Default: inner planets + Jupiter and Saturn for scale
    bodies = ['sun', 'mercury', 'venus', 'earth', 'mars', 'jupiter', 'saturn']
    
    try:
        launch_visualizer(bodies=bodies, width=1400, height=900)
    except ImportError as e:
        print(f"Error: Required package not installed: {e}")
        print("Please install pygame and PyOpenGL:")
        print("  pip install .[visualizer]")
        sys.exit(1)


if __name__ == "__main__":
    main()
