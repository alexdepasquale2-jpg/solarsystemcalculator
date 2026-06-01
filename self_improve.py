import argparse
import csv
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np

from solarsystemcalculator import SolarSystemCalculator


@dataclass(frozen=True)
class Observation:
    body: str
    dt: datetime
    position_au: Tuple[float, float, float]


BODY_SUFFIX_PATTERN = re.compile(
    r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)([A-Za-z][A-Za-z0-9_]*)?\s*$"
)


def parse_datetime(value: str) -> datetime:
    dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_z_au_and_body(z_value: str) -> tuple[float, str | None]:
    match = BODY_SUFFIX_PATTERN.match(z_value)
    if not match:
        raise ValueError(f"Invalid z_au value: {z_value!r}")
    numeric_part, suffix = match.groups()
    return float(numeric_part), suffix.lower() if suffix else None


def read_observations(path: Path, default_body: str = "") -> List[Observation]:
    observations = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"datetime", "x_au", "y_au", "z_au"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing required CSV columns: {sorted(missing)}")

        for row in reader:
            explicit_body = (row.get("body") or "").strip().lower()
            z_raw = row["z_au"].strip()
            z_value, body_suffix = _parse_z_au_and_body(z_raw)
            body = explicit_body or body_suffix or default_body.strip().lower()
            if not body:
                raise ValueError(
                    "Each row needs a body column, or pass --body. "
                    "If the CSV has a body suffix attached to z_au, it will be extracted automatically."
                )
            if explicit_body and body_suffix and explicit_body != body_suffix:
                raise ValueError(
                    f"Body mismatch in row: body={explicit_body!r} but z_au contains suffix {body_suffix!r}"
                )
            observations.append(
                Observation(
                    body=body,
                    dt=parse_datetime(row["datetime"]),
                    position_au=(
                        float(row["x_au"]),
                        float(row["y_au"]),
                        z_value,
                    ),
                )
            )

    observations.sort(key=lambda item: (item.body, item.dt))
    return observations


def group_by_body(observations: Iterable[Observation]) -> Dict[str, List[Observation]]:
    grouped: Dict[str, List[Observation]] = {}
    for observation in observations:
        grouped.setdefault(observation.body, []).append(observation)
    return grouped


def feature_row(calc: SolarSystemCalculator, body: str, dt: datetime, epoch_jd: float) -> np.ndarray:
    state = calc.state(body, dt)
    jd_delta = state.julian_date - epoch_jd
    return np.asarray(
        [
            jd_delta,
            np.sin(2 * np.pi * jd_delta / state.orbital_period_days),
            np.cos(2 * np.pi * jd_delta / state.orbital_period_days),
            state.position_au[0],
            state.position_au[1],
            state.position_au[2],
            state.velocity_au_per_day[0],
            state.velocity_au_per_day[1],
            state.velocity_au_per_day[2],
            state.radius_au,
            state.mean_anomaly_deg / 360.0,
            state.true_anomaly_deg / 360.0,
            state.days_to_perihelion / state.orbital_period_days,
        ],
        dtype=float,
    )


def build_training_matrices(
    calc: SolarSystemCalculator,
    body: str,
    observations: Sequence[Observation],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    epoch_jd = calc.state(body, observations[0].dt).julian_date
    x = np.asarray([feature_row(calc, body, item.dt, epoch_jd) for item in observations])
    observed = np.asarray([item.position_au for item in observations], dtype=float)
    baseline = np.asarray([calc.position(body, item.dt, unit="au") for item in observations])
    residual = observed - baseline
    return x, residual, baseline, epoch_jd


def split_train_test(x: np.ndarray, y: np.ndarray, test_fraction: float):
    if not 0.0 < test_fraction < 0.8:
        raise ValueError("--test-fraction must be between 0 and 0.8")
    split = max(2, int(len(x) * (1.0 - test_fraction)))
    if split >= len(x):
        split = len(x) - 1
    return x[:split], x[split:], y[:split], y[split:]


def make_estimator(model_name: str, random_state: int):
    try:
        from sklearn.gaussian_process import GaussianProcessRegressor
        from sklearn.gaussian_process.kernels import RBF, WhiteKernel
        from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
        from sklearn.multioutput import MultiOutputRegressor
        from sklearn.neural_network import MLPRegressor
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
        from sklearn.linear_model import Ridge
    except ImportError as exc:
        raise ImportError("Install ML dependencies with `pip install .[ml]`.") from exc

    if model_name == "gaussian_process":
        estimator = Pipeline(
            [
                ("scale", StandardScaler()),
                (
                    "model",
                    GaussianProcessRegressor(
                        kernel=RBF(length_scale=1.0, length_scale_bounds=(1e-6, 1e3)) 
                               + WhiteKernel(noise_level=1e-10, noise_level_bounds=(1e-6, 1e-1)),
                        normalize_y=True,
                        n_restarts_optimizer=4,
                        random_state=random_state,
                        alpha=1e-12,
                    ),
                ),
            ]
        )
        grid = {
            "model__alpha": [1e-14, 1e-12, 1e-10, 1e-8],
        }
    elif model_name == "mlp":
        estimator = Pipeline(
            [
                ("scale", StandardScaler()),
                (
                    "model",
                    MLPRegressor(
                        max_iter=8000,
                        early_stopping=True,
                        random_state=random_state,
                    ),
                ),
            ]
        )
        grid = {
            "model__hidden_layer_sizes": [(32,), (64,), (64, 32)],
            "model__alpha": [1e-8, 1e-6, 1e-4],
            "model__learning_rate_init": [1e-4, 5e-4, 1e-3],
        }
    elif model_name == "ridge":
        estimator = Pipeline(
            [
                ("scale", StandardScaler()),
                ("model", MultiOutputRegressor(Ridge())),
            ]
        )
        grid = {
            "model__estimator__alpha": [1e-12, 1e-10, 1e-8, 1e-6, 1e-4, 1e-2],
        }
    else:
        raise ValueError("Unknown model. Use: gaussian_process, mlp, or ridge.")

    return estimator, grid, GridSearchCV, TimeSeriesSplit


def rms(values: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.sum(values**2, axis=1))))


def train_body(
    calc: SolarSystemCalculator,
    body: str,
    observations: Sequence[Observation],
    model_name: str,
    test_fraction: float,
    cv_splits: int,
    random_state: int,
):
    if len(observations) < 6:
        raise ValueError(f"{body} needs at least 6 observations for rigorous tuning.")

    x, y, baseline, epoch_jd = build_training_matrices(calc, body, observations)
    x_train, x_test, y_train, y_test = split_train_test(x, y, test_fraction)
    estimator, grid, GridSearchCV, TimeSeriesSplit = make_estimator(model_name, random_state)
    splits = min(cv_splits, len(x_train) - 1)
    if splits < 2:
        raise ValueError(f"{body} needs more training rows for {cv_splits} CV splits.")

    search = GridSearchCV(
        estimator,
        grid,
        cv=TimeSeriesSplit(n_splits=splits),
        scoring="neg_mean_squared_error",
        n_jobs=None,
        refit=True,
    )
    search.fit(x_train, y_train)

    test_pred = search.predict(x_test)
    corrected_error = y_test - test_pred
    baseline_error = y_test
    improvement = 1.0 - (rms(corrected_error) / rms(baseline_error)) if rms(baseline_error) else 0.0

    return {
        "body": body,
        "model": search.best_estimator_,
        "epoch_jd": epoch_jd,
        "best_params": search.best_params_,
        "rows": len(observations),
        "train_rows": len(x_train),
        "test_rows": len(x_test),
        "baseline_rms_au": rms(baseline_error),
        "corrected_rms_au": rms(corrected_error),
        "improvement_fraction": improvement,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train residual correction models from ephemeris observations."
    )
    parser.add_argument("csv", type=Path, help="CSV with datetime,x_au,y_au,z_au and optional body columns.")
    parser.add_argument("--body", default="", help="Body name to use when the CSV has no body column.")
    parser.add_argument("--output", type=Path, default=Path("models/orbit_residual_model.joblib"))
    parser.add_argument("--model", choices=["gaussian_process", "mlp", "ridge"], default="gaussian_process")
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument("--cv-splits", type=int, default=5)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    try:
        import joblib
    except ImportError as exc:
        raise ImportError("Install ML dependencies with `pip install .[ml]`.") from exc

    calc = SolarSystemCalculator(precision="high")
    observations = read_observations(args.csv, default_body=args.body)
    grouped = group_by_body(observations)
    results = {}

    for body, rows in grouped.items():
        result = train_body(
            calc=calc,
            body=body,
            observations=rows,
            model_name=args.model,
            test_fraction=args.test_fraction,
            cv_splits=args.cv_splits,
            random_state=args.random_state,
        )
        results[body] = result
        print(f"{body}:")
        print(f"  rows: {result['rows']} train={result['train_rows']} test={result['test_rows']}")
        print(f"  best params: {result['best_params']}")
        print(f"  baseline RMS:  {result['baseline_rms_au']:.12e} AU")
        print(f"  corrected RMS: {result['corrected_rms_au']:.12e} AU")
        print(f"  improvement:   {100 * result['improvement_fraction']:.3f}%")

    payload = {
        "kind": "solarsystemcalculator.residual_correction",
        "model_name": args.model,
        "feature_version": 1,
        "bodies": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(payload, args.output)
    print(f"saved: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
