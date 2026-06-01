from datetime import datetime, timezone
from typing import Iterable, Optional, Sequence, Tuple

import numpy as np

from .calculator import SolarSystemCalculator


class ObservationInterpolator:
    """
    Fit observation residuals on top of the deterministic orbital model.

    This intentionally does not use pretraining. It learns only from the dated
    observations supplied by the caller, then predicts a correction to the
    formula-based position at nearby times.
    """

    def __init__(self, calculator: Optional[SolarSystemCalculator] = None, kernel=None):
        try:
            from sklearn.gaussian_process import GaussianProcessRegressor
            from sklearn.gaussian_process.kernels import RBF, WhiteKernel
            from sklearn.pipeline import make_pipeline
            from sklearn.preprocessing import StandardScaler
        except ImportError as exc:
            raise ImportError(
                "ObservationInterpolator requires scikit-learn. Install with "
                "`pip install .[ml]`."
            ) from exc

        self.calculator = calculator or SolarSystemCalculator()
        self._make_pipeline = make_pipeline
        self._standard_scaler = StandardScaler
        self._regressor = GaussianProcessRegressor
        self._kernel = kernel or (RBF(length_scale=30.0) + WhiteKernel(noise_level=1e-10))
        self.body = None
        self._epoch_jd = None
        self._model = None

    def _julian_features(self, dates: Sequence[datetime]) -> np.ndarray:
        values = []
        for dt in dates:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            jd = float(self.calculator._julian_date(dt.astimezone(timezone.utc)))
            values.append(jd - self._epoch_jd)
        return np.asarray(values, dtype=float).reshape(-1, 1)

    def fit(
        self,
        body: str,
        dates: Sequence[datetime],
        observed_positions_au: Iterable[Tuple[float, float, float]],
    ) -> "ObservationInterpolator":
        observed = np.asarray(list(observed_positions_au), dtype=float)
        if observed.ndim != 2 or observed.shape[1] != 3:
            raise ValueError("observed_positions_au must be an iterable of (x, y, z) positions.")
        if len(dates) != len(observed):
            raise ValueError("dates and observed_positions_au must have the same length.")

        self.body = body
        first = dates[0]
        if first.tzinfo is None:
            first = first.replace(tzinfo=timezone.utc)
        self._epoch_jd = float(self.calculator._julian_date(first.astimezone(timezone.utc)))
        x = self._julian_features(dates)
        predicted = np.asarray([self.calculator.position(body, dt, unit='au') for dt in dates])
        residuals = observed - predicted
        self._model = self._make_pipeline(
            self._standard_scaler(),
            self._regressor(kernel=self._kernel, normalize_y=True),
        )
        self._model.fit(x, residuals)
        return self

    def predict_position(self, dt: datetime) -> Tuple[float, float, float]:
        if self._model is None or self.body is None:
            raise ValueError("Fit the interpolator before predicting.")

        base = np.asarray(self.calculator.position(self.body, dt, unit='au'))
        correction = self._model.predict(self._julian_features([dt]))[0]
        return tuple(float(v) for v in base + correction)
