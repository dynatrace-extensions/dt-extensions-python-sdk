# SPDX-FileCopyrightText: 2023-present Dynatrace LLC
#
# SPDX-License-Identifier: MIT

from unittest.mock import patch

import pytest


class MockTime:
    """Controls time.monotonic and the callback duration timer independently.

    The scheduler uses ``time.monotonic`` to decide when events are due.
    The ``WrappedCallback`` uses ``timer`` (timeit.default_timer) to measure
    how long a callback took.

    These two clocks are separate so that advancing the duration timer
    inside a callback (to simulate slow work) does NOT cause the scheduler
    to think more events are due — avoiding an infinite loop via
    ``delayfunc(0)`` yielding to the callback thread.
    """

    THREAD_SYNC_DELAY = 0.05  # seconds - enough for thread pool to finish

    def __init__(self, start: float = 1000.0):
        self._monotonic = start
        self._perf = start

    # -- Scheduler clock (time.monotonic) --

    @property
    def now(self) -> float:
        return self._monotonic

    def monotonic(self) -> float:
        return self._monotonic

    def advance(self, seconds: float) -> None:
        """Advance the scheduler clock (time.monotonic)."""
        self._monotonic += seconds

    # -- Duration timer (callback.timer / perf_counter) --

    def perf_counter(self) -> float:
        return self._perf

    def advance_perf(self, seconds: float) -> None:
        """Advance the duration timer only (does NOT affect the scheduler)."""
        self._perf += seconds


@pytest.fixture
def mock_time():
    """Fixture that patches time.monotonic and the callback perf timer.

    Returns a MockTime instance with two independent clocks:
    - ``advance()`` moves the scheduler clock forward
    - ``advance_perf()`` moves the duration timer forward (for simulating slow callbacks)

    NOTE: time.sleep is NOT patched so thread synchronization still works.
    """
    mt = MockTime()
    with (
        patch("time.monotonic", side_effect=mt.monotonic),
        # timer is imported as ``from timeit import default_timer as timer``
        # so we must patch the local name in the callback module
        patch("dynatrace_extension.sdk.callback.timer", side_effect=mt.perf_counter),
    ):
        yield mt
