Metric
======

The :class:`dynatrace_extension.Metric` class is mostly used internally to
construct metrics that comply with the MINT protocol which is what Extension
Framework uses to send event to the environment.

When the :meth:`dynatrace_extension.Extension.report_metric` method is
called, it builds a :class:`Metric` object, which is. then added to the list
of metrics to be sent to the environment. The class has a useful method called
:meth:`dynatrace_extension.Metric.to_mint_line` which allows you to convert
the metric to a string that complies with the MINT protocol.

Members
^^^^^^^

.. autoclass:: dynatrace_extension.Metric
   :members:
   :undoc-members:
