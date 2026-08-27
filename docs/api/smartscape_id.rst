Smartscape ID
=============

Smartscape node IDs uniquely identify a node in the Dynatrace topology.
An ID is rendered as ``TYPE-<16 hex>`` (for example
``HOST-8B775215A352336E``), where the hex part is derived from the nodes's
type and its ordered id components.

Use :func:`dynatrace_extension.smartscape_id` (or the equivalent
:meth:`dynatrace_extension.Extension.get_smartscape_id` method) to compute the
ID for a node from its type and id components. The order of the id
components is significant and must match the rule's predefined component order.

.. code:: python

   from dynatrace_extension import smartscape_id

   entity_id = smartscape_id("TYPE", {"key1": "A", "key2": "B"})
   # -> "TYPE-8B775215A352336E"

Members
^^^^^^^

.. autofunction:: dynatrace_extension.smartscape_id
