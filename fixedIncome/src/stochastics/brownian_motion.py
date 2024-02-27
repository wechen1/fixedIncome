"""
This script contains a class for generating multi-dimensional Brownian Motion paths with optional correlation.

Unit tests are contained in fixedIncome.tests.test_stochastics.test_brownian_motion.py
"""

import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import math
import numpy as np
from typing import Optional
from collections.abc import Callable
from itertools import pairwise
import pandas as pd

from fixedIncome.src.scheduling_tools.schedule_enumerations import DayCountConvention
from fixedIncome.src.scheduling_tools.day_count_calculator import DayCountCalculator
from fixedIncome.src.scheduling_tools.scheduler import Scheduler

def datetime_to_path_call(
        datetime_obj: datetime,
        start_date_time: datetime,
        end_date_time: datetime,
        day_count_convention: DayCountConvention,
        path: Optional[np.ndarray] = None
) -> float | np.ndarray:
    """
    A generic function for interpolating a path, represented as a np.ndarray, using a
    start and end datetime which are assumed to be the datetimes of the starting and
    ending indices of the array. The function will linearly interpolate path values
    between the nearest indices corresponding to the provided datetime.
    """
    if path is None:
        raise ValueError('Brownian Motion called when path is None. '
                         'First call generate_path method with set_path variable set to True.')

    if datetime_obj < start_date_time or datetime_obj > end_date_time:
        raise ValueError(f'Provided datetime {str(datetime_obj)} is outside of'
                         f'the range {str(start_date_time)} to {str(end_date_time)}.')

    num_steps = path.shape[1] if len(path.shape) >= 2 else len(path)

    time_diff = DayCountCalculator.compute_accrual_length(start_date=start_date_time,
                                                          end_date=end_date_time,
                                                          dcc=day_count_convention)

    time_since_start = DayCountCalculator.compute_accrual_length(start_date=start_date_time,
                                                                 end_date=datetime_obj,
                                                                 dcc=day_count_convention)

    interpolation_float = (num_steps - 1) * time_since_start / time_diff
    interpolated_lower_index = math.floor(interpolation_float)
    interpolated_upper_index = math.ceil(interpolation_float)

    if interpolated_lower_index == interpolated_upper_index:
        return path[:, interpolated_lower_index]

    prev_value = path[:, interpolated_lower_index]
    next_value = path[:, interpolated_upper_index]

    time_since_prev_index = interpolation_float - interpolated_lower_index
    time_to_next_index = interpolated_upper_index - interpolation_float
    total_time = time_since_prev_index + time_to_next_index

    return (time_since_prev_index * next_value + prev_value * time_to_next_index) / total_time

class BrownianMotion(Callable):
    """
    A class for multidimensional brownian motion with optional correlation.
    """
    def __init__(self,
                 start_date_time: datetime,
                 end_date_time: datetime,
                 dimension: int = 1,
                 correlation_matrix: Optional[np.ndarray] = None,
                 day_count_convention: DayCountConvention = DayCountConvention.ACTUAL_OVER_ACTUAL) -> None:

        self._start_date_time = start_date_time
        self._end_date_time = end_date_time
        self._dimension = dimension
        self.correlation_matrix = correlation_matrix if correlation_matrix is not None else np.eye(self._dimension)
        assert dimension, dimension == self.correlation_matrix.shape
        self.lower_triangular_mat = np.linalg.cholesky(self.correlation_matrix)
        self._path = None
        self.day_count_convention = day_count_convention

    @property
    def start_date_time(self) -> datetime:
        return self._start_date_time

    @property
    def end_date_time(self) -> datetime:
        return self._end_date_time

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def path(self):
        return self._path

    def __call__(self, datetime_obj: datetime) -> np.array:
        """
        Shortcut to allow the user to directly call the BrownianMotion datetime rather
        than index and interpolate the path directly.
        """
        return datetime_to_path_call(datetime_obj,
                                     start_date_time=self.start_date_time,
                                     end_date_time=self.end_date_time,
                                     day_count_convention=self.day_count_convention,
                                     path=self.path)

    def generate_increments(
            self,
            dt: timedelta | relativedelta,
            seed: Optional[int] = None
    ) -> tuple[np.ndarray, np.array]:
        """
        Returns a num_increments x num_steps numpy nd.array, where each row corresponds to a
        Correlated Brownian Motion increments are generated by applying the Cholesky Decomposition to the correlation matrix
        and multiplying the resulting lower-triangular matrix to the uncorrelated brownian motion increments.
        See Brigo and Mercurio's *Interest Rate Models-Theory and Practice Second Ed.*, page 31.
        """
        datetimes = Scheduler.generate_dates_by_increments(start_date=self.start_date_time,
                                                           end_date=self.end_date_time,
                                                           increment=dt,
                                                           max_dates=1_000_000)
        if datetimes[-1] < self.end_date_time:
            datetimes.append(self.end_date_time)

        accruals = (DayCountCalculator.compute_accrual_length(self.start_date_time,
                                                              datetime_obj,
                                                              self.day_count_convention)
                    for datetime_obj in datetimes)
        dt_increments = np.array([end-start for start, end in pairwise(accruals)])

        num_steps = len(dt_increments)
        np.random.seed(seed=seed)
        brownian_increments = np.random.standard_normal((self.dimension, num_steps)) * np.sqrt(dt_increments)
        brownian_increments = self.lower_triangular_mat @ brownian_increments  # induce correlation
        return brownian_increments, dt_increments

    def generate_path(self, dt: timedelta | relativedelta, set_path: bool = True, seed: Optional[int] = None) -> np.array:
        """
        Generates Brownian Motion sample paths.

        dt is a float whose scale is years, that is dt=1 corresponds to dt increments of a single year.
        """
        brownian_increments, _ = self.generate_increments(dt, seed=seed)
        brownian_paths = np.zeros((self.dimension, brownian_increments.shape[1] + 1))
        brownian_paths[:, 1:] = brownian_increments.cumsum(axis=1)

        if set_path:
            self._path = brownian_paths

        return brownian_paths

    def generate_num_steps_from_dt(self, dt: float) -> int:
        """ """
        time_diff = self.end_date_time - self.start_date_time
        time_diff_in_years = math.ceil(DayCountCalculator.time_fraction_in_years(time_diff))
        num_steps = math.ceil(time_diff_in_years / dt)
        return num_steps

    def plot(self):
        plural = 's' if self.dimension > 1 else ''
        title_str = f'Brownian Motion Sample Path{plural}'
        plt.figure(figsize=(10, 6))
        plt.title(title_str)
        date_range = pd.date_range(start=self.start_date_time, end=self.end_date_time, periods=self.path.shape[1])
        plt.plot(date_range, self.path.T, linewidth=0.5, alpha=1)
        plt.grid(alpha=0.25)
        plt.show()



#------------------------------------------------------------------------------

if __name__ == '__main__':
    rho = 0.75
    correlation_matrix = np.array([[1.0, rho, rho], [rho, 1.0, rho], [rho, rho, 1.0]])

    start_time = datetime(2023, 10, 15, 0, 0, 0, 0)
    end_time = datetime(2024, 10, 15, 0, 0, 0, 0)

    bm = BrownianMotion(start_date_time=start_time,
                        end_date_time=end_time,
                        dimension=3,
                        correlation_matrix=correlation_matrix)

    paths = bm.generate_path(dt=relativedelta(hours=1), seed=1)
    bm.plot()

    print('Brownian motion call value:', bm(end_time))
    print('Last element of path:', paths[-1, -1])


