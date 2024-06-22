# SPDX-FileCopyrightText: 2023-present Dynatrace LLC
#
# SPDX-License-Identifier: MIT

import logging
import random
from datetime import datetime, timedelta
from timeit import default_timer as timer
from typing import Callable, Dict, Optional, Tuple

from .activation import ActivationType
from .communication import Status, StatusValue


class WrappedCallback:
    def __init__(
        self,
        interval: timedelta,
        callback: Callable,
        logger: logging.Logger,
        args: Optional[Tuple] = None,
        kwargs: Optional[Dict] = None,
        running_in_sim=False,
        activation_type: Optional[ActivationType] = None,
    ):
        self.callback: Callable = callback
        if args is None:
            args = ()
        self.callback_args = args
        if kwargs is None:
            kwargs = {}
        self.callback_kwargs = kwargs
        self.interval: timedelta = interval
        self.logger = logger
        self.running: bool = False
        self.status = Status(StatusValue.OK)
        self.executions_total = 0  # global counter
        self.executions_per_interval = 0  # counter per interval = 1 min by default
        self.duration = 0  # global counter
        self.duration_interval_total = 0  # counter per interval = 1 min by default
        self.cluster_time_diff = 0
        self.start_timestamp = self.get_current_time_with_cluster_diff()
        self.running_in_sim = running_in_sim
        self.activation_type = activation_type
        self.ok_count = 0  # counter per interval = 1 min by default
        self.timeouts_count = 0  # counter per interval = 1 min by default
        self.exception_count = 0  # counter per interval = 1 min by default
        self.iterations = 0  # how many times we ran the callback iterator for this callback

    def get_current_time_with_cluster_diff(self):
        return datetime.now() + timedelta(milliseconds=self.cluster_time_diff)

    def __call__(self):
        self.logger.debug(f"Running scheduled callback {self}")
        if self.executions_total == 0:
            self.start_timestamp = self.get_current_time_with_cluster_diff()
        self.running = True
        self.executions_total += 1
        self.executions_per_interval += 1
        start_time = timer()
        failed = False
        try:
            self.callback(*self.callback_args, **self.callback_kwargs)
            self.status = Status(StatusValue.OK)
        except Exception as e:
            failed = True
            self.logger.exception(f"Error running callback {self}: {e!r}")
            self.status = Status(StatusValue.GENERIC_ERROR, repr(e))
            self.exception_count += 1

        self.running = False
        self.duration = timer() - start_time
        self.duration_interval_total += self.duration
        self.logger.debug(f"Ran scheduled callback {self} in {self.duration:.2f} seconds")
        if self.duration > self.interval.total_seconds():
            message = f"Callback {self} took {self.duration:.4f} seconds to execute, which is longer than the interval of {self.interval.total_seconds()}s"
            self.logger.warning(message)
            self.status = Status(StatusValue.GENERIC_ERROR, message)
            self.timeouts_count += 1
        elif not failed:
            self.ok_count += 1

    def __repr__(self):
        return f"Method={self.callback.__name__}"

    def name(self):
        return self.callback.__name__

    def initial_wait_time(self) -> float:
        if not self.running_in_sim:
            """
            Here we chose a random second between 1 and 59 to start the callback
            This is to distribute load for extension running on this host
            When running from the simulator, this is not done
            """

            now = self.get_current_time_with_cluster_diff()
            random_second = random.randint(1, 59)  # noqa: S311
            next_execution = datetime.now().replace(second=random_second, microsecond=0)
            if next_execution <= now:
                # The random chosen second already passed this minute
                next_execution += timedelta(minutes=1)
            wait_time = (next_execution - now).total_seconds()
            self.logger.debug(f"Randomly choosing next execution time for callback {self} to be {next_execution}")
            return wait_time
        return 0

    def get_adjusted_metric_timestamp(self) -> datetime:
        """
        Callbacks can't run all together, so they must start at random times
        This means that when reporting metrics for a callback, we need to consider
        the time the callback was started, instead of the current timestamp
        this is done to avoid situations like:
        - 14:00:55 - callback A runs
        - 14:01:03 - 8 seconds later, a metric is reported
        - 14:01:55 - callback A runs again (60 seconds after the first run)
        - 14:01:58 - 3 seconds later a metric is reported
        In this scenario a metric is reported twice in the same minute
        This can also cause minutes where a metric is not reported at all, creating gaps

        Here we calculate the metric timestamp based on the start timestamp of the callback
        If the callback started in the last minute, we use the callback start timestamp
        between 60 seconds and 120 seconds, we use the callback timestamp + 1 minute
        between 120 seconds and 180 seconds, we use the callback timestamp + 2 minutes, and so forth
        """
        now = self.get_current_time_with_cluster_diff()
        minutes_since_start = int((now - self.start_timestamp).total_seconds() / 60)
        return self.start_timestamp + timedelta(minutes=minutes_since_start)

    def clear_sfm_metrics(self):
        self.ok_count = 0
        self.timeouts_count = 0
        self.duration_interval_total = 0
        self.exception_count = 0
        self.executions_per_interval = 0

    def get_next_execution_timestamp(self) -> float:
        """
        Get the timestamp for the next execution of the callback
        This is done using execution total, the interval and the start timestamp
        :return: datetime
        """
        return (
            self.start_timestamp + timedelta(seconds=self.interval.total_seconds() * (self.iterations or 1))
        ).timestamp()
