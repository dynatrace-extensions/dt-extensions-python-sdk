Metric Type
===========

There are two types of metrics that can be sent to Dynatrace:

* **Gauge** - A gauge is a metric that represents a single numerical value
  that can arbitrarily go up and down. For example, current percentage of
  the CPU usage.
* **Counters** - A counter is a metric that is continuously increasing.
  For example, the number of bytes received over a network interface since
  the start of the process.

Members
^^^^^^^

.. autoclass:: dynatrace_extension.MetricType
    :members:
    :undoc-members:
