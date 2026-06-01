from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from tkinter import BooleanVar, StringVar, Tk, filedialog, messagebox
from tkinter import ttk
from typing import Optional

from . import SolarSystemCalculator, format_distance


BODIES = ["sun", "mercury", "venus", "earth", "mars", "jupiter", "saturn", "uranus", "neptune"]
DISTANCE_UNITS = ["km", "au", "miles", "m", "light_seconds"]
VELOCITY_UNITS = ["km_per_second", "au_per_day"]


class SolarSystemControlPanel(ttk.Frame):
    """Professional desktop control panel for calculator workflows."""

    def __init__(self, master: Tk):
        super().__init__(master, padding=14)
        self.master = master
        self.calc = SolarSystemCalculator()
        self.trainer_process: Optional[subprocess.Popen] = None

        now = datetime.now(timezone.utc).replace(microsecond=0)
        self.body1 = StringVar(value="earth")
        self.body2 = StringVar(value="mars")
        self.date_value = StringVar(value=now.isoformat().replace("+00:00", "Z"))
        self.distance_unit = StringVar(value="km")
        self.velocity_unit = StringVar(value="km_per_second")
        self.precision = StringVar(value="high")
        self.use_ephemeris = BooleanVar(value=Path("de421.bsp").exists())
        self.ephemeris_path = StringVar(value="de421.bsp" if Path("de421.bsp").exists() else "")
        self.status = StringVar(value="Ready")
        self.training_csv = StringVar(value="")
        self.training_output = StringVar(value="models/orbit_residual_model.joblib")
        self.training_model = StringVar(value="gaussian_process")

        self._build_style()
        self._build_layout()
        self.refresh()

    def _build_style(self) -> None:
        style = ttk.Style(self.master)
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 16))
        style.configure("Section.TLabelframe.Label", font=("Segoe UI Semibold", 10))
        style.configure("Metric.TLabel", font=("Consolas", 10))
        style.configure("Status.TLabel", foreground="#37506f")
        style.configure("Primary.TButton", font=("Segoe UI Semibold", 10))

    def _build_layout(self) -> None:
        self.master.title("Solar System Calculator Control Panel")
        self.master.minsize(1120, 720)
        self.grid(row=0, column=0, sticky="nsew")
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=0, minsize=330)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Solar System Calculator", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, textvariable=self.status, style="Status.TLabel").grid(row=0, column=1, sticky="e")

        left = ttk.Frame(self)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        left.columnconfigure(0, weight=1)

        controls = ttk.LabelFrame(left, text="Calculation Controls", style="Section.TLabelframe", padding=12)
        controls.grid(row=0, column=0, sticky="ew")
        controls.columnconfigure(1, weight=1)

        self._label(controls, "Body A", 0)
        ttk.Combobox(controls, textvariable=self.body1, values=BODIES, state="readonly").grid(row=0, column=1, sticky="ew", pady=3)
        self._label(controls, "Body B", 1)
        ttk.Combobox(controls, textvariable=self.body2, values=BODIES, state="readonly").grid(row=1, column=1, sticky="ew", pady=3)
        self._label(controls, "UTC Time", 2)
        ttk.Entry(controls, textvariable=self.date_value).grid(row=2, column=1, sticky="ew", pady=3)
        self._label(controls, "Distance Unit", 3)
        ttk.Combobox(controls, textvariable=self.distance_unit, values=DISTANCE_UNITS, state="readonly").grid(row=3, column=1, sticky="ew", pady=3)
        self._label(controls, "Velocity Unit", 4)
        ttk.Combobox(controls, textvariable=self.velocity_unit, values=VELOCITY_UNITS, state="readonly").grid(row=4, column=1, sticky="ew", pady=3)
        self._label(controls, "Precision", 5)
        ttk.Combobox(controls, textvariable=self.precision, values=["high", "max"], state="readonly").grid(row=5, column=1, sticky="ew", pady=3)
        ttk.Checkbutton(controls, text="Use JPL ephemeris file", variable=self.use_ephemeris).grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 3))
        ephemeris_row = ttk.Frame(controls)
        ephemeris_row.grid(row=7, column=0, columnspan=2, sticky="ew")
        ephemeris_row.columnconfigure(0, weight=1)
        ttk.Entry(ephemeris_row, textvariable=self.ephemeris_path).grid(row=0, column=0, sticky="ew")
        ttk.Button(ephemeris_row, text="Browse", command=self.browse_ephemeris).grid(row=0, column=1, padx=(6, 0))

        buttons = ttk.Frame(controls)
        buttons.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        buttons.columnconfigure((0, 1, 2), weight=1)
        ttk.Button(buttons, text="Now", command=self.use_now).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ttk.Button(buttons, text="Swap", command=self.swap_bodies).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(buttons, text="Compute", style="Primary.TButton", command=self.refresh).grid(row=0, column=2, sticky="ew", padx=(5, 0))

        trainer = ttk.LabelFrame(left, text="Self-Improvement Trainer", style="Section.TLabelframe", padding=12)
        trainer.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        trainer.columnconfigure(0, weight=1)
        ttk.Label(trainer, text="Observation CSV").grid(row=0, column=0, sticky="w")
        csv_row = ttk.Frame(trainer)
        csv_row.grid(row=1, column=0, sticky="ew", pady=(3, 8))
        csv_row.columnconfigure(0, weight=1)
        ttk.Entry(csv_row, textvariable=self.training_csv).grid(row=0, column=0, sticky="ew")
        ttk.Button(csv_row, text="Browse", command=self.browse_training_csv).grid(row=0, column=1, padx=(6, 0))
        ttk.Label(trainer, text="Output Model").grid(row=2, column=0, sticky="w")
        ttk.Entry(trainer, textvariable=self.training_output).grid(row=3, column=0, sticky="ew", pady=(3, 8))
        ttk.Label(trainer, text="Model").grid(row=4, column=0, sticky="w")
        ttk.Combobox(
            trainer,
            textvariable=self.training_model,
            values=["gaussian_process", "ridge", "mlp"],
            state="readonly",
        ).grid(row=5, column=0, sticky="ew", pady=(3, 10))
        ttk.Button(trainer, text="Train Residual Model", command=self.run_training).grid(row=6, column=0, sticky="ew")

        right = ttk.Notebook(self)
        right.grid(row=1, column=1, sticky="nsew")

        summary = ttk.Frame(right, padding=12)
        state_tab = ttk.Frame(right, padding=12)
        distances = ttk.Frame(right, padding=12)
        right.add(summary, text="Summary")
        right.add(state_tab, text="State Vector")
        right.add(distances, text="Distance Table")

        summary.columnconfigure(0, weight=1)
        summary.rowconfigure(1, weight=1)
        self.summary_text = self._text(summary)
        self.summary_text.grid(row=0, column=0, sticky="nsew")
        self.orbit_canvas = ttk.Frame(summary)
        self.orbit_canvas.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        self.canvas = None
        self._build_canvas(summary)

        state_tab.columnconfigure((0, 1), weight=1)
        self.state_a = self._text(state_tab)
        self.state_b = self._text(state_tab)
        self.state_a.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.state_b.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        distances.columnconfigure(0, weight=1)
        distances.rowconfigure(0, weight=1)
        columns = ("body", "distance")
        self.distance_tree = ttk.Treeview(distances, columns=columns, show="headings", height=18)
        self.distance_tree.heading("body", text="Body")
        self.distance_tree.heading("distance", text="Distance")
        self.distance_tree.column("body", width=180, anchor="w")
        self.distance_tree.column("distance", width=260, anchor="e")
        self.distance_tree.grid(row=0, column=0, sticky="nsew")

    def _build_canvas(self, parent: ttk.Frame) -> None:
        import tkinter as tk

        self.canvas = tk.Canvas(parent, height=260, background="#0f1720", highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

    def _label(self, parent: ttk.Frame, text: str, row: int) -> None:
        ttk.Label(parent, text=text).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)

    def _text(self, parent: ttk.Frame):
        import tkinter as tk

        widget = tk.Text(
            parent,
            height=14,
            wrap="none",
            borderwidth=1,
            relief="solid",
            font=("Consolas", 10),
            background="#fbfcfe",
        )
        widget.configure(state="disabled")
        return widget

    def parse_dt(self) -> datetime:
        value = self.date_value.get().strip()
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                "Invalid UTC datetime format. Use ISO-8601 like 2024-06-20T20:51:00Z."
            ) from exc
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def calculator(self) -> SolarSystemCalculator:
        ephemeris = None
        if self.use_ephemeris.get():
            path = self.ephemeris_path.get().strip()
            if not path:
                raise ValueError("Ephemeris mode is enabled but no file was selected.")
            if not Path(path).exists():
                raise FileNotFoundError(f"Ephemeris file not found: {path}")
            ephemeris = path
        return SolarSystemCalculator(precision=self.precision.get(), ephemeris=ephemeris)

    def use_now(self) -> None:
        self.date_value.set(datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"))
        self.refresh()

    def swap_bodies(self) -> None:
        first, second = self.body1.get(), self.body2.get()
        self.body1.set(second)
        self.body2.set(first)
        self.refresh()

    def browse_ephemeris(self) -> None:
        path = filedialog.askopenfilename(
            title="Select ephemeris file",
            filetypes=[("SPK ephemeris", "*.bsp"), ("All files", "*.*")],
        )
        if path:
            self.ephemeris_path.set(path)
            self.use_ephemeris.set(True)

    def browse_training_csv(self) -> None:
        path = filedialog.askopenfilename(
            title="Select observation CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if path:
            self.training_csv.set(path)

    def set_text(self, widget, text: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def refresh(self) -> None:
        try:
            dt = self.parse_dt()
            calc = self.calculator()
            body_a = self.body1.get()
            body_b = self.body2.get()
            unit = self.distance_unit.get()
            velocity_unit = self.velocity_unit.get()

            state_a = calc.state(body_a, dt)
            state_b = calc.state(body_b, dt)
            distance = calc.distance(body_a, body_b, dt=dt, unit=unit)
            angle_text = "n/a"
            if body_a != "sun" and body_b != "sun":
                angle_text = f"{calc.angle_between(body_a, body_b, dt=dt):.9f} deg"

            if unit == "km":
                distance_text = format_distance(distance)
            else:
                distance_text = f"{distance:.12g} {unit}"

            summary = [
                f"Time UTC:        {dt.isoformat()}",
                f"Mode:            {'JPL ephemeris' if calc.ephemeris else 'Keplerian formula'}",
                f"Body pair:       {body_a} -> {body_b}",
                f"Distance:        {distance_text}",
                f"Included angle:  {angle_text}",
                "",
                f"{body_a} radius:  {state_a.radius_au:.12f} AU",
                f"{body_b} radius:  {state_b.radius_au:.12f} AU",
                f"{body_a} speed:   {self._speed_line(calc, body_a, dt, velocity_unit)}",
                f"{body_b} speed:   {self._speed_line(calc, body_b, dt, velocity_unit)}",
            ]
            self.set_text(self.summary_text, "\n".join(summary))
            self.set_text(self.state_a, self._state_text(state_a, body_a))
            self.set_text(self.state_b, self._state_text(state_b, body_b))
            self._refresh_distances(calc, body_a, dt, unit)
            self._draw_orbit_view(calc, body_a, body_b, dt)
            self.status.set("Computed successfully")
        except Exception as exc:
            self.status.set("Calculation failed")
            messagebox.showerror("Calculation failed", str(exc))

    def _speed_line(self, calc: SolarSystemCalculator, body: str, dt: datetime, unit: str) -> str:
        velocity = calc.velocity(body, dt=dt, unit=unit)
        speed = sum(v * v for v in velocity) ** 0.5
        return f"{speed:.12g} {unit}"

    def _state_text(self, state, body: str) -> str:
        lines = [
            f"{body.upper()} STATE",
            f"Julian date:       {state.julian_date:.9f}",
            f"Position AU:       {self._tuple(state.position_au)}",
            f"Velocity AU/day:   {self._tuple(state.velocity_au_per_day)}",
            f"Orbit-plane AU:    {self._tuple(state.orbital_plane_position_au)}",
            "",
            f"Radius AU:         {state.radius_au:.12f}",
            f"Speed AU/day:      {state.speed_au_per_day:.12f}",
            f"Semi-major AU:     {state.semi_major_axis_au:.12f}",
            f"Eccentricity:      {state.eccentricity:.12f}",
            f"Inclination deg:   {state.inclination_deg:.9f}",
            "",
            f"Mean anomaly:      {state.mean_anomaly_deg:.9f} deg",
            f"Ecc anomaly:       {state.eccentric_anomaly_deg:.9f} deg",
            f"True anomaly:      {state.true_anomaly_deg:.9f} deg",
            f"Arg perihelion:    {state.argument_of_perihelion_deg:.9f} deg",
            "",
            f"Period days:       {state.orbital_period_days:.6f}",
            f"Perihelion AU:     {state.perihelion_distance_au:.12f}",
            f"Aphelion AU:       {state.aphelion_distance_au:.12f}",
            f"Days since peri:   {state.days_since_perihelion:.6f}",
            f"Days to peri:      {state.days_to_perihelion:.6f}",
        ]
        return "\n".join(lines)

    def _tuple(self, values) -> str:
        return "(" + ", ".join(f"{value:.12f}" for value in values) + ")"

    def _refresh_distances(self, calc: SolarSystemCalculator, reference: str, dt: datetime, unit: str) -> None:
        for item in self.distance_tree.get_children():
            self.distance_tree.delete(item)

        distances = []
        for body in BODIES:
            if body != reference:
                value = calc.distance(reference, body, dt=dt, unit=unit)
                text = format_distance(value) if unit == "km" else f"{value:.12g} {unit}"
                distances.append((body, value, text))

        for body, _value, text in sorted(distances, key=lambda row: row[1]):
            self.distance_tree.insert("", "end", values=(body, text))

    def _draw_orbit_view(self, calc: SolarSystemCalculator, body_a: str, body_b: str, dt: datetime) -> None:
        if self.canvas is None:
            return
        canvas = self.canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 720)
        height = max(canvas.winfo_height(), 260)
        cx, cy = width / 2, height / 2

        positions = {}
        max_radius = 1.0
        for body in BODIES:
            pos = calc.position(body, dt=dt, unit="au")
            positions[body] = pos
            max_radius = max(max_radius, abs(pos[0]), abs(pos[1]))

        scale = min(width, height) * 0.42 / max_radius
        canvas.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, fill="#f6c453", outline="")

        for body, pos in positions.items():
            if body == "sun":
                continue
            x = cx + pos[0] * scale
            y = cy - pos[1] * scale
            r = 5 if body in {body_a, body_b} else 3
            color = "#5cc8ff" if body == body_a else "#ff8f5c" if body == body_b else "#9aa8b8"
            canvas.create_oval(x - r, y - r, x + r, y + r, fill=color, outline="")
            canvas.create_text(x + 8, y - 8, text=body, fill="#d7dee8", anchor="w", font=("Segoe UI", 8))

    def run_training(self) -> None:
        csv_path = self.training_csv.get().strip()
        if not csv_path:
            messagebox.showwarning("Training CSV required", "Select an observation CSV before training.")
            return

        command = [
            sys.executable,
            "self_improve.py",
            csv_path,
            "--model",
            self.training_model.get(),
            "--output",
            self.training_output.get().strip() or "models/orbit_residual_model.joblib",
        ]
        try:
            self.trainer_process = subprocess.Popen(command, cwd=Path.cwd())
            self.status.set("Training started in background")
            messagebox.showinfo("Training started", "The residual trainer is running in the background.")
        except Exception as exc:
            messagebox.showerror("Training failed to start", str(exc))


def main() -> int:
    root = Tk()
    SolarSystemControlPanel(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
