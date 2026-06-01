"""
Real-time 3D pygame visualizer for the solar system with artistic indicators.

Features:
- Accurate body positions and relative scales
- Real-time orbital extrapolation (paths drawn outward)
- Artistic visual indicators (rings, trails, highlights)
- Live time playback control
- Interactive navigation (pan, zoom, rotate)

Note: Requires pygame and PyOpenGL. Install with:
    pip install .[visualizer]
"""

import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Optional
import math
import numpy as np

try:
    import pygame
    from pygame.locals import *
    HAS_PYGAME = True
except ImportError:
    HAS_PYGAME = False

try:
    from OpenGL.GL import *
    from OpenGL.GLU import *
    HAS_OPENGL = True
except ImportError:
    HAS_OPENGL = False

from .calculator import SolarSystemCalculator, OrbitState
from .logging_utils import get_logger


logger = get_logger()


class SolarSystemVisualizer:
    """
    OpenGL/Pygame 3D visualizer for orbital mechanics.
    Shows accurate positions with artistic enhancements.
    """

    # Visual scale factors (logarithmic to make small planets visible)
    BODY_SIZE_SCALE = {
        'sun': 15.0,
        'mercury': 2.0,
        'venus': 4.0,
        'earth': 4.2,
        'mars': 2.5,
        'jupiter': 10.0,
        'saturn': 9.0,
        'uranus': 5.0,
        'neptune': 5.0,
    }

    # Artistic colors (RGB, normalized to 0-1)
    BODY_COLORS = {
        'sun': (1.0, 0.95, 0.3),
        'mercury': (0.7, 0.7, 0.7),
        'venus': (0.95, 0.85, 0.5),
        'earth': (0.2, 0.6, 0.95),
        'mars': (0.95, 0.4, 0.2),
        'jupiter': (0.85, 0.7, 0.5),
        'saturn': (0.9, 0.8, 0.6),
        'uranus': (0.4, 0.8, 0.95),
        'neptune': (0.2, 0.4, 0.95),
    }

    ORBIT_COLOR = (0.4, 0.5, 0.6, 0.3)
    TRAIL_COLOR = (0.8, 0.8, 0.9, 0.2)
    TEXT_COLOR = (0.95, 0.95, 0.95)

    def __init__(self, width: int = 1400, height: int = 900, target_bodies: Optional[List[str]] = None):
        """
        Initialize the visualizer.

        Parameters:
            width: Window width in pixels
            height: Window height in pixels
            target_bodies: List of bodies to display. Default: inner planets + jupiter
        """
        if not HAS_PYGAME or not HAS_OPENGL:
            raise ImportError(
                "Visualizer requires pygame and PyOpenGL. "
                "Install with: pip install .[visualizer]"
            )
        
        self.width = width
        self.height = height
        self.target_bodies = target_bodies or ['sun', 'mercury', 'venus', 'earth', 'mars', 'jupiter', 'saturn']
        
        self.calc = SolarSystemCalculator(precision='high')
        self.current_time = datetime.now(timezone.utc)
        self.paused = False
        
        # Trail tracking (position history for artistic effect)
        self.trails: Dict[str, List[Tuple[float, float, float]]] = {body: [] for body in self.target_bodies}
        self.max_trail_length = 200
        
        # Cached state data
        self.body_states: Dict[str, OrbitState] = {}
        self.extrapolated_positions: Dict[str, List[Tuple[float, float, float]]] = {}
        
        # Visualization state
        self.camera_distance = 3.0
        self.camera_angle_x = 0.3
        self.camera_angle_y = 0.0
        self.camera_focus = (0.0, 0.0, 0.0)
        self.show_orbits = True
        self.show_trails = True
        self.show_labels = True
        self.show_info = True
        self.time_scale = 1.0  # Multiplier for simulation speed
        self.selected_body: Optional[str] = None
        
        # Font for labels (will be set after pygame init)
        self.font_large = None
        self.font_small = None
        self.overlay_margin = 16
        
        self._initialized = False
        
        logger.debug(f"SolarSystemVisualizer initialized for {len(self.target_bodies)} bodies")

    def initialize(self) -> None:
        """Initialize pygame and OpenGL."""
        pygame.init()
        pygame.font.init()
        self.font_large = pygame.font.SysFont("Segoe UI", 18, bold=True)
        self.font_small = pygame.font.SysFont("Segoe UI", 14)
        self.display = (self.width, self.height)
        pygame.display.set_mode(self.display, DOUBLEBUF | OPENGL)
        pygame.display.set_caption("Solar System Calculator - 3D Orbital Visualizer")
        
        # Setup OpenGL
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_POINT_SMOOTH)
        glHint(GL_POINT_SMOOTH_HINT, GL_NICEST)
        
        # Lighting
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        
        light_pos = (1.0, 1.0, 1.0, 0.0)
        glLight(GL_LIGHT0, GL_POSITION, light_pos)
        glLight(GL_LIGHT0, GL_AMBIENT, (0.2, 0.2, 0.2, 1.0))
        glLight(GL_LIGHT0, GL_DIFFUSE, (0.9, 0.9, 0.9, 1.0))
        
        self.clock = pygame.time.Clock()
        self._initialized = True
        self._update_camera()
        logger.debug("OpenGL initialization complete")

    def _update_camera(self) -> None:
        """Update camera projection and view."""
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, (self.width / self.height), 0.1, 500.0)
        
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        
        # Position camera relative to the selected focus point
        cam_x = self.camera_distance * math.sin(self.camera_angle_y) * math.cos(self.camera_angle_x)
        cam_y = self.camera_distance * math.sin(self.camera_angle_x)
        cam_z = self.camera_distance * math.cos(self.camera_angle_y) * math.cos(self.camera_angle_x)
        focus_x, focus_y, focus_z = self.camera_focus
        gluLookAt(cam_x + focus_x, cam_y + focus_y, cam_z + focus_z, focus_x, focus_y, focus_z, 0, 1, 0)

    def _draw_sphere(self, radius: float, color: Tuple[float, float, float], 
                     position: Tuple[float, float, float] = (0, 0, 0),
                     segments: int = 20) -> None:
        """Draw a sphere at position with given color."""
        glPushMatrix()
        glTranslatef(*position)
        glColor3f(*color)
        
        # Use GLU sphere for simplicity
        quad = gluNewQuadric()
        gluSphere(quad, radius, segments, segments)
        
        glPopMatrix()

    def _draw_orbit_line(self, body: str, extrapolate_days: int = 180) -> None:
        """Draw the orbital path for a body (extrapolated into future)."""
        if body not in self.extrapolated_positions or not self.extrapolated_positions[body]:
            return
        
        positions = self.extrapolated_positions[body]
        
        glDisable(GL_LIGHTING)
        glColor4f(*self.ORBIT_COLOR)
        glLineWidth(1.0)
        
        glBegin(GL_LINE_STRIP)
        for x, y, z in positions:
            glVertex3f(x, z, y)  # Swap to match coordinate system
        glEnd()
        
        glEnable(GL_LIGHTING)

    def _draw_trail(self, body: str) -> None:
        """Draw the trail for a body."""
        if body not in self.trails or not self.trails[body]:
            return
        
        positions = self.trails[body]
        
        glDisable(GL_LIGHTING)
        glColor4f(*self.TRAIL_COLOR)
        glLineWidth(0.5)
        
        glBegin(GL_LINE_STRIP)
        for x, y, z in positions:
            glVertex3f(x, z, y)
        glEnd()
        
        glEnable(GL_LIGHTING)

    def _extrapolate_orbit(self, body: str, days_ahead: int = 180, step: int = 5) -> List[Tuple[float, float, float]]:
        """Extrapolate orbital position into the future."""
        positions = []
        current_date = self.current_time
        
        for day_offset in range(0, days_ahead, step):
            try:
                future_date = current_date + timedelta(days=day_offset)
                state = self.calc.state(body, future_date)
                x, y, z = state.position_au
                positions.append((x, y, z))
            except Exception as e:
                logger.debug(f"Extrapolation stopped for {body} at day {day_offset}: {e}")
                break
        
        return positions

    def _project_to_screen(self, x: float, y: float, z: float) -> Optional[Tuple[int, int]]:
        """Project a 3D world point to 2D screen coordinates."""
        try:
            modelview = glGetDoublev(GL_MODELVIEW_MATRIX)
            projection = glGetDoublev(GL_PROJECTION_MATRIX)
            viewport = glGetIntegerv(GL_VIEWPORT)
            win_x, win_y, _ = gluProject(x, z, y, modelview, projection, viewport)
            screen_x = int(win_x)
            screen_y = int(self.height - win_y)
            if 0 <= screen_x < self.width and 0 <= screen_y < self.height:
                return screen_x, screen_y
        except Exception:
            pass
        return None

    def _draw_screen_text(self, text: str, x: int, y: int, color=(255, 255, 255)) -> None:
        if self.font_small is None:
            return
        surface = self.font_small.render(text, True, color)
        display = pygame.display.get_surface()
        if display is not None:
            display.blit(surface, (x, y))

    def _draw_labels(self) -> None:
        if not self.show_labels:
            return
        for body, state in self.body_states.items():
            if body == 'sun':
                continue
            screen_pos = self._project_to_screen(*state.position_au)
            if screen_pos is None:
                continue
            x, y = screen_pos
            label = body.capitalize()
            self._draw_screen_text(label, x + 8, y - 12)

    def _draw_overlay(self) -> None:
        if not self.show_info:
            return
        y = self.overlay_margin
        self._draw_screen_text(f"UTC: {self.current_time.isoformat(timespec='seconds')}", self.overlay_margin, y)
        y += 22
        self._draw_screen_text(f"Speed: {self.time_scale:.2f} days/frame", self.overlay_margin, y)
        y += 18
        self._draw_screen_text(f"Paused: {'yes' if self.paused else 'no'}", self.overlay_margin, y)
        y += 18
        self._draw_screen_text(f"Orbits: {'on' if self.show_orbits else 'off'} | Trails: {'on' if self.show_trails else 'off'}", self.overlay_margin, y)
        y += 18
        self._draw_screen_text(f"Labels: {'on' if self.show_labels else 'off'} | Info: {'on' if self.show_info else 'off'}", self.overlay_margin, y)
        y += 24
        if self.selected_body and self.selected_body in self.body_states:
            state = self.body_states[self.selected_body]
            self._draw_screen_text(f"Selected: {self.selected_body.capitalize()}", self.overlay_margin, y)
            y += 18
            self._draw_screen_text(f"Distance: {np.linalg.norm(state.position_au):.4f} AU", self.overlay_margin, y)
            y += 18
            self._draw_screen_text(f"Semi-major axis: {state.semi_major_axis_au:.4f} AU", self.overlay_margin, y)
            y += 18
            self._draw_screen_text(f"Eccentricity: {state.eccentricity:.4f}", self.overlay_margin, y)
            y += 18
            self._draw_screen_text(f"Inclination: {state.inclination_deg:.3f}°", self.overlay_margin, y)
            y += 18
            self._draw_screen_text(f"True anomaly: {state.true_anomaly_deg:.3f}°", self.overlay_margin, y)

    def _update_state(self) -> None:
        """Update body positions and orbital extrapolations."""
        # Fetch current positions
        for body in self.target_bodies:
            try:
                state = self.calc.state(body, self.current_time)
                self.body_states[body] = state
                
                # Update trail
                x, y, z = state.position_au
                self.trails[body].append((x, y, z))
                if len(self.trails[body]) > self.max_trail_length:
                    self.trails[body].pop(0)
                
                # Extrapolate future orbit
                self.extrapolated_positions[body] = self._extrapolate_orbit(body, days_ahead=365)
                
            except Exception as e:
                logger.warning(f"Error updating {body}: {e}")

        if self.selected_body and self.selected_body in self.body_states:
            self.camera_focus = self.body_states[self.selected_body].position_au
        else:
            self.camera_focus = (0.0, 0.0, 0.0)

    def _handle_input(self) -> bool:
        """Handle keyboard and mouse input. Returns False if quit requested."""
        for event in pygame.event.get():
            if event.type == QUIT:
                return False
            
            if event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    return False
                elif event.key == K_SPACE:
                    self.paused = not self.paused
                    logger.debug(f"Simulation {'paused' if self.paused else 'resumed'}")
                elif event.key == K_o:
                    self.show_orbits = not self.show_orbits
                elif event.key == K_t:
                    self.show_trails = not self.show_trails
                elif event.key == K_l:
                    self.show_labels = not self.show_labels
                elif event.key == K_i:
                    self.show_info = not self.show_info
                elif event.key == K_UP:
                    self.time_scale *= 1.5
                    logger.debug(f"Time scale: {self.time_scale:.2f}x")
                elif event.key == K_DOWN:
                    self.time_scale = max(0.01, self.time_scale / 1.5)
                    logger.debug(f"Time scale: {self.time_scale:.2f}x")
                elif event.key == K_EQUALS or event.key == K_PLUS:
                    self.time_scale *= 1.5
                    logger.debug(f"Time scale: {self.time_scale:.2f}x")
                elif event.key == K_MINUS or event.key == K_UNDERSCORE:
                    self.time_scale = max(0.01, self.time_scale / 1.5)
                    logger.debug(f"Time scale: {self.time_scale:.2f}x")
                elif event.key == K_r:
                    self.current_time = datetime.now(timezone.utc)
                    self.trails = {body: [] for body in self.target_bodies}
                    self.time_scale = 1.0
                    logger.info("Simulation reset to current time")
                elif event.key == K_1:
                    self.selected_body = None
                elif event.key == K_2:
                    self.selected_body = 'earth'
                elif event.key == K_3:
                    self.selected_body = 'mars'
                elif event.key == K_4:
                    self.selected_body = 'jupiter'
                elif event.key == K_5:
                    self.selected_body = 'saturn'
                
            elif event.type == MOUSEMOTION:
                # Smooth camera rotation with mouse
                if pygame.mouse.get_pressed()[0]:
                    rel = pygame.mouse.get_rel()
                    self.camera_angle_y += rel[0] * 0.005
                    self.camera_angle_x += rel[1] * 0.005
                    self.camera_angle_x = np.clip(self.camera_angle_x, -math.pi/2, math.pi/2)
                
            elif event.type == MOUSEBUTTONDOWN:
                if event.button == 4:  # Scroll up
                    self.camera_distance *= 0.9
                elif event.button == 5:  # Scroll down
                    self.camera_distance *= 1.1
                self.camera_distance = np.clip(self.camera_distance, 0.5, 50.0)
        
        return True

    def render(self) -> None:
        """Render one frame of the visualization."""
        if not self._initialized:
            return
        
        # Clear
        glClearColor(0.01, 0.01, 0.02, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        # Update camera
        self._update_camera()
        
        # Draw sun (reference point)
        if 'sun' in self.body_states:
            sun_color = self.BODY_COLORS['sun']
            self._draw_sphere(self.BODY_SIZE_SCALE['sun'] * 0.05, sun_color, (0, 0, 0), segments=30)
        
        # Draw each body
        for body in self.target_bodies:
            if body not in self.body_states or body == 'sun':
                continue
            
            state = self.body_states[body]
            x, y, z = state.position_au
            color = self.BODY_COLORS.get(body, (0.8, 0.8, 0.8))
            size = self.BODY_SIZE_SCALE.get(body, 2.0)
            
            # Highlight selected body
            if body == self.selected_body:
                size *= 1.5
            
            # Draw orbit line
            if self.show_orbits:
                self._draw_orbit_line(body, extrapolate_days=365)
            
            # Draw trail
            if self.show_trails:
                self._draw_trail(body)
            
            # Draw body
            self._draw_sphere(size * 0.01, color, (x, z, y), segments=20)

        self._draw_labels()
        self._draw_overlay()
        pygame.display.flip()

    def run(self) -> None:
        """Main visualization loop."""
        try:
            self.initialize()
            running = True
            
            print("\n" + "=" * 60)
            print("SOLAR SYSTEM VISUALIZER CONTROLS")
            print("=" * 60)
            print("MOUSE:        Drag to rotate | Scroll to zoom")
            print("SPACE:        Pause/Resume")
            print("↑/↓:          Speed up/slow down time")
            print("O:            Toggle orbit lines")
            print("T:            Toggle trails")
            print("L:            Toggle labels")
            print("I:            Toggle info panel")
            print("R:            Reset to current time")
            print("1/2/3:        Focus on sun/earth/mars")
            print("4/5:          Focus on jupiter/saturn")
            print("+/-:          Speed up/slow down time")
            print("ESC:          Exit")
            print("=" * 60 + "\n")
            
            frame_count = 0
            while running:
                running = self._handle_input()
                
                if not self.paused:
                    # Advance time
                    self.current_time += timedelta(days=self.time_scale)
                    self._update_state()
                
                self.render()
                self.clock.tick(60)  # 60 FPS
                frame_count += 1
            
            logger.info(f"Visualizer closed after {frame_count} frames")
        
        except Exception as e:
            logger.error(f"Visualizer error: {e}", exc_info=True)
            raise
        
        finally:
            if HAS_PYGAME:
                pygame.quit()


def launch_visualizer(bodies: Optional[List[str]] = None, width: int = 1400, height: int = 900) -> None:
    """
    Launch the pygame 3D solar system visualizer.
    
    Parameters:
        bodies: List of bodies to display. Default: inner planets + jupiter
        width: Window width
        height: Window height
    
    Raises:
        ImportError: If pygame or PyOpenGL are not installed
    """
    try:
        viz = SolarSystemVisualizer(width=width, height=height, target_bodies=bodies)
        viz.run()
    except ImportError as e:
        print(f"\nError: {e}", file=sys.stderr)
        print("Install required packages with:", file=sys.stderr)
        print("  pip install .[visualizer]", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    launch_visualizer()
