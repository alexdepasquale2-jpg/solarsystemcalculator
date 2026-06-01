#!/usr/bin/env python
"""
Professional Training GUI for Solar System Calculator.

Provides an easy-to-use interface for:
1. Generating observations from ephemeris
2. Training ML correction models
3. Viewing and managing results
"""

import csv
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog, scrolledtext
except ImportError:
    raise ImportError("tkinter is required. Install with: pip install tk")

from solarsystemcalculator import SolarSystemCalculator


# Available bodies
BODIES = ["mercury", "venus", "earth", "mars", "jupiter", "saturn", "uranus", "neptune"]
MODELS = ["gaussian_process", "ridge", "mlp"]


class TrainingGUI:
    """Professional GUI for training data generation and model training."""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Solar System Calculator - Training Suite")
        self.root.geometry("1000x700")
        self.root.resizable(True, True)
        
        # Configure style
        self._setup_styles()
        
        # Create notebook (tabs)
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create tabs
        self.gen_frame = ttk.Frame(self.notebook)
        self.train_frame = ttk.Frame(self.notebook)
        self.results_frame = ttk.Frame(self.notebook)
        self.settings_frame = ttk.Frame(self.notebook)
        
        self.notebook.add(self.gen_frame, text="📊 Generate Data")
        self.notebook.add(self.train_frame, text="🤖 Train Model")
        self.notebook.add(self.results_frame, text="📈 Results")
        self.notebook.add(self.settings_frame, text="⚙️ Settings")
        
        self._setup_generate_tab()
        self._setup_train_tab()
        self._setup_results_tab()
        self._setup_settings_tab()
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=2)
        
        # Thread for long-running operations
        self.worker_thread: Optional[threading.Thread] = None
        self.is_running = False
    
    def _setup_styles(self) -> None:
        """Configure ttk styles."""
        style = ttk.Style()
        style.theme_use('clam')
    
    def _setup_generate_tab(self) -> None:
        """Setup data generation tab."""
        frame = self.gen_frame
        
        # Title
        title = ttk.Label(frame, text="Generate Training Data from Ephemeris", 
                         font=("Arial", 12, "bold"))
        title.pack(pady=10)
        
        # Settings frame
        settings = ttk.LabelFrame(frame, text="Generation Settings")
        settings.pack(fill=tk.X, padx=10, pady=5)
        
        # Bodies selection
        ttk.Label(settings, text="Bodies:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.gen_bodies = tk.StringVar(value="mars earth")
        bodies_frame = ttk.Frame(settings)
        bodies_frame.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)
        
        for body in BODIES:
            var = tk.BooleanVar(value=body in ["mars", "earth"])
            cb = ttk.Checkbutton(bodies_frame, text=body.capitalize(), variable=var,
                               command=lambda b=body, v=var: self._update_bodies())
            cb.pack(side=tk.LEFT)
            setattr(self, f"body_{body}", var)
        
        # Count
        ttk.Label(settings, text="Number of Observations:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.gen_count = ttk.Spinbox(settings, from_=10, to=1000, increment=10, width=10)
        self.gen_count.set(128)
        self.gen_count.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Date range
        ttk.Label(settings, text="Start Date (UTC):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.gen_start = ttk.Entry(settings, width=30)
        self.gen_start.insert(0, "2000-01-01T00:00:00Z")
        self.gen_start.grid(row=2, column=1, sticky=tk.EW, padx=5, pady=5)
        
        ttk.Label(settings, text="End Date (UTC):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.gen_end = ttk.Entry(settings, width=30)
        self.gen_end.insert(0, "2050-01-01T00:00:00Z")
        self.gen_end.grid(row=3, column=1, sticky=tk.EW, padx=5, pady=5)
        
        # Output file
        ttk.Label(settings, text="Output File:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.gen_output = ttk.Entry(settings, width=30)
        self.gen_output.insert(0, "observations.csv")
        self.gen_output.grid(row=4, column=1, sticky=tk.EW, padx=5, pady=5)
        
        # Seed
        ttk.Label(settings, text="Random Seed:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        self.gen_seed = ttk.Spinbox(settings, from_=0, to=999999, width=10)
        self.gen_seed.set(42)
        self.gen_seed.grid(row=5, column=1, sticky=tk.W, padx=5, pady=5)
        
        settings.columnconfigure(1, weight=1)
        
        # Preview area
        preview_frame = ttk.LabelFrame(frame, text="Preview")
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.gen_preview = scrolledtext.ScrolledText(preview_frame, height=10, width=80)
        self.gen_preview.pack(fill=tk.BOTH, expand=True)
        
        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Preview Data", 
                  command=self._preview_observations).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Generate & Save", 
                  command=self._generate_observations).pack(side=tk.LEFT, padx=5)
    
    def _setup_train_tab(self) -> None:
        """Setup model training tab."""
        frame = self.train_frame
        
        # Title
        title = ttk.Label(frame, text="Train Correction Model", 
                         font=("Arial", 12, "bold"))
        title.pack(pady=10)
        
        # Settings frame
        settings = ttk.LabelFrame(frame, text="Training Settings")
        settings.pack(fill=tk.X, padx=10, pady=5)
        
        # Input file
        ttk.Label(settings, text="Observations File:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        input_frame = ttk.Frame(settings)
        input_frame.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)
        self.train_input = ttk.Entry(input_frame, width=30)
        self.train_input.insert(0, "observations.csv")
        self.train_input.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(input_frame, text="Browse...", 
                  command=lambda: self._browse_file("input")).pack(side=tk.LEFT, padx=5)
        
        # Model selection
        ttk.Label(settings, text="Algorithm:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.train_model = ttk.Combobox(settings, values=MODELS, state="readonly", width=20)
        self.train_model.set("gaussian_process")
        self.train_model.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Test fraction
        ttk.Label(settings, text="Test Fraction:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.train_test_frac = ttk.Spinbox(settings, from_=0.05, to=0.5, increment=0.05, width=10, format="%.2f")
        self.train_test_frac.set(0.2)
        self.train_test_frac.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        # CV splits
        ttk.Label(settings, text="CV Splits:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.train_cv = ttk.Spinbox(settings, from_=2, to=10, width=10)
        self.train_cv.set(5)
        self.train_cv.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Output file
        ttk.Label(settings, text="Output Model:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        output_frame = ttk.Frame(settings)
        output_frame.grid(row=4, column=1, sticky=tk.EW, padx=5, pady=5)
        self.train_output = ttk.Entry(output_frame, width=30)
        self.train_output.insert(0, "models/orbit_residual_model.joblib")
        self.train_output.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(output_frame, text="Browse...", 
                  command=lambda: self._browse_file("output")).pack(side=tk.LEFT, padx=5)
        
        settings.columnconfigure(1, weight=1)
        
        # Progress area
        progress_frame = ttk.LabelFrame(frame, text="Training Progress")
        progress_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.train_progress = scrolledtext.ScrolledText(progress_frame, height=12, width=80)
        self.train_progress.pack(fill=tk.BOTH, expand=True)
        
        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=10)
        
        self.train_button = ttk.Button(button_frame, text="Start Training", 
                                      command=self._start_training)
        self.train_button.pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear Log", 
                  command=lambda: self.train_progress.delete("1.0", tk.END)).pack(side=tk.LEFT, padx=5)
    
    def _setup_results_tab(self) -> None:
        """Setup results viewing tab."""
        frame = self.results_frame
        
        # Title
        title = ttk.Label(frame, text="Training Results", 
                         font=("Arial", 12, "bold"))
        title.pack(pady=10)
        
        # Results display
        results_frame = ttk.LabelFrame(frame, text="Results Summary")
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.results_display = scrolledtext.ScrolledText(results_frame, height=20, width=80)
        self.results_display.pack(fill=tk.BOTH, expand=True)
        
        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Load Results", 
                  command=self._load_results).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear", 
                  command=lambda: self.results_display.delete("1.0", tk.END)).pack(side=tk.LEFT, padx=5)
    
    def _setup_settings_tab(self) -> None:
        """Setup settings tab."""
        frame = self.settings_frame
        
        # Title
        title = ttk.Label(frame, text="Application Settings", 
                         font=("Arial", 12, "bold"))
        title.pack(pady=10)
        
        # Info
        info_text = """
📋 Solar System Calculator Training Suite v1.0

This application helps you:
1. Generate training observations from JPL ephemeris
2. Train machine learning correction models
3. View and manage training results

🔧 Keyboard Shortcuts:
• Ctrl+Q: Quit
• Tab: Switch between tabs

📚 Documentation:
See GLOBAL_MANUAL.md for complete reference
See QUICKREF.md for quick command reference

⚙️ Configuration Files:
• generate_observations.py - Data generation script
• self_improve.py - Training script
• pyproject.toml - Package configuration

🚀 Command Line Alternatives:

Generate observations:
  python generate_observations.py --bodies mars earth --count 128

Train model:
  python self_improve.py observations.csv --model gaussian_process

Clean data:
  python clean_data.py --all

🌍 3D Visualization:
  launch-viz

📊 Desktop GUI:
  solarsystemcalculator-gui
        """
        
        text_widget = scrolledtext.ScrolledText(frame, height=25, width=80, state=tk.DISABLED)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        text_widget.config(state=tk.NORMAL)
        text_widget.insert("1.0", info_text)
        text_widget.config(state=tk.DISABLED)
    
    def _update_bodies(self) -> None:
        """Update bodies selection display."""
        selected = [body.upper() for body in BODIES if getattr(self, f"body_{body}").get()]
        self.gen_bodies.set(", ".join(selected))
    
    def _browse_file(self, mode: str) -> None:
        """Browse for file."""
        if mode == "input":
            file = filedialog.askopenfilename(
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if file:
                self.train_input.delete(0, tk.END)
                self.train_input.insert(0, file)
        elif mode == "output":
            file = filedialog.asksaveasfilename(
                defaultextension=".joblib",
                filetypes=[("Model files", "*.joblib"), ("All files", "*.*")]
            )
            if file:
                self.train_output.delete(0, tk.END)
                self.train_output.insert(0, file)
    
    def _update_status(self, message: str) -> None:
        """Update status bar."""
        self.status_var.set(message)
        self.root.update()
    
    def _preview_observations(self) -> None:
        """Preview generated observations."""
        try:
            # Get parameters
            bodies = [b for b in BODIES if getattr(self, f"body_{b}").get()]
            count = int(self.gen_count.get())
            
            if not bodies:
                messagebox.showwarning("Warning", "Please select at least one body")
                return
            
            self._update_status(f"Previewing {count} observations for {len(bodies)} body/ies...")
            
            # Import here to check dependencies
            try:
                from generate_observations import parse_datetime, random_datetimes, generate_rows
                import random
            except ImportError:
                messagebox.showerror("Error", "Could not import generate_observations module")
                return
            
            # Parse dates
            start = parse_datetime(self.gen_start.get())
            end = parse_datetime(self.gen_end.get())
            
            # Generate dates
            rng = random.Random(int(self.gen_seed.get()))
            dates = sorted(random_datetimes(start, end, count, rng))
            
            # Generate sample rows
            calc = SolarSystemCalculator(precision="high")
            rows = generate_rows(calc, bodies, dates[:min(len(dates), 5)])  # Show first 5
            
            # Display preview
            self.gen_preview.delete("1.0", tk.END)
            self.gen_preview.insert("1.0", "Preview (first 5 rows):\n\n")
            self.gen_preview.insert(tk.END, "body,datetime,x_au,y_au,z_au\n")
            for row in rows:
                line = f"{row['body']},{row['datetime']},{row['x_au']},{row['y_au']},{row['z_au']}\n"
                self.gen_preview.insert(tk.END, line)
            
            self.gen_preview.insert(tk.END, f"\n... {count - 5} more rows not shown\n")
            self._update_status(f"Preview ready ({count} total observations)")
            
        except Exception as e:
            messagebox.showerror("Error", f"Preview failed: {e}")
            self._update_status("Preview failed")
    
    def _generate_observations(self) -> None:
        """Generate and save observations."""
        if self.is_running:
            messagebox.showwarning("Warning", "Operation already in progress")
            return
        
        self.is_running = True
        self._update_status("Generating observations...")
        
        def run():
            try:
                # Import here
                from generate_observations import (
                    parse_datetime, random_datetimes, generate_rows, write_rows
                )
                import random
                
                # Get parameters
                bodies = [b for b in BODIES if getattr(self, f"body_{b}").get()]
                count = int(self.gen_count.get())
                output = self.gen_output.get()
                
                if not bodies:
                    raise ValueError("Please select at least one body")
                
                # Parse dates
                start = parse_datetime(self.gen_start.get())
                end = parse_datetime(self.gen_end.get())
                
                # Generate
                rng = random.Random(int(self.gen_seed.get()))
                dates = sorted(random_datetimes(start, end, count, rng))
                calc = SolarSystemCalculator(precision="high")
                rows = generate_rows(calc, bodies, dates)
                
                # Write
                written = write_rows(Path(output), rows)
                
                msg = f"✓ Generated {count} observations\n✓ Written {written} new rows\n✓ Saved to {output}"
                messagebox.showinfo("Success", msg)
                self._update_status(f"Generated {written} observations")
                
            except Exception as e:
                messagebox.showerror("Error", f"Generation failed: {e}")
                self._update_status("Generation failed")
            finally:
                self.is_running = False
        
        self.worker_thread = threading.Thread(target=run, daemon=True)
        self.worker_thread.start()
    
    def _start_training(self) -> None:
        """Start model training."""
        if self.is_running:
            messagebox.showwarning("Warning", "Operation already in progress")
            return
        
        self.is_running = True
        self.train_button.config(state=tk.DISABLED)
        self._update_status("Training in progress...")
        self.train_progress.delete("1.0", tk.END)
        
        def run():
            try:
                from self_improve import (
                    read_observations, group_by_body, train_body, rms
                )
                import joblib
                
                csv_path = Path(self.train_input.get())
                output_path = Path(self.train_output.get())
                
                if not csv_path.exists():
                    raise FileNotFoundError(f"Observations file not found: {csv_path}")
                
                self._log_train(f"Loading observations from {csv_path}...\n")
                observations = read_observations(csv_path)
                grouped = group_by_body(observations)
                
                calc = SolarSystemCalculator(precision="high")
                results = {}
                
                for body, rows in grouped.items():
                    self._log_train(f"\nTraining {body}...\n")
                    
                    result = train_body(
                        calc=calc,
                        body=body,
                        observations=rows,
                        model_name=self.train_model.get(),
                        test_fraction=float(self.train_test_frac.get()),
                        cv_splits=int(self.train_cv.get()),
                        random_state=42,
                    )
                    results[body] = result
                    
                    self._log_train(f"  rows: {result['rows']} train={result['train_rows']} test={result['test_rows']}\n")
                    self._log_train(f"  best params: {result['best_params']}\n")
                    self._log_train(f"  baseline RMS:  {result['baseline_rms_au']:.12e} AU\n")
                    self._log_train(f"  corrected RMS: {result['corrected_rms_au']:.12e} AU\n")
                    self._log_train(f"  improvement:   {100 * result['improvement_fraction']:.3f}%\n")
                
                # Save
                payload = {
                    "kind": "solarsystemcalculator.residual_correction",
                    "model_name": self.train_model.get(),
                    "feature_version": 1,
                    "bodies": results,
                }
                output_path.parent.mkdir(parents=True, exist_ok=True)
                joblib.dump(payload, output_path)
                
                self._log_train(f"\n✓ Saved: {output_path}\n")
                messagebox.showinfo("Success", f"Training complete!\nModel saved to {output_path}")
                
            except Exception as e:
                self._log_train(f"\n✗ Error: {e}\n")
                messagebox.showerror("Error", f"Training failed: {e}")
            finally:
                self.is_running = False
                self.train_button.config(state=tk.NORMAL)
                self._update_status("Ready")
        
        self.worker_thread = threading.Thread(target=run, daemon=True)
        self.worker_thread.start()
    
    def _log_train(self, text: str) -> None:
        """Add text to training log."""
        self.train_progress.insert(tk.END, text)
        self.train_progress.see(tk.END)
        self.root.update()
    
    def _load_results(self) -> None:
        """Load and display results."""
        try:
            from self_improve import read_observations, group_by_body
            
            csv_path = Path(self.train_input.get())
            if not csv_path.exists():
                raise FileNotFoundError(f"Observations file not found: {csv_path}")
            
            observations = read_observations(csv_path)
            grouped = group_by_body(observations)
            
            text = "📊 Dataset Summary\n\n"
            for body, rows in grouped.items():
                text += f"{body.upper()}: {len(rows)} observations\n"
            
            self.results_display.config(state=tk.NORMAL)
            self.results_display.delete("1.0", tk.END)
            self.results_display.insert("1.0", text)
            self.results_display.config(state=tk.NORMAL)
            
            messagebox.showinfo("Results", text)
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not load results: {e}")


def launch_training_gui() -> None:
    """Launch the training GUI."""
    root = tk.Tk()
    app = TrainingGUI(root)
    
    # Bind Ctrl+Q to quit
    root.bind("<Control-q>", lambda e: root.quit())
    
    root.mainloop()


if __name__ == "__main__":
    launch_training_gui()
