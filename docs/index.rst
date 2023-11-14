Dynatrace Extensions SDK for Python
===================================

``db-extensions-sdk`` is a Python library and a toolbox for building Python extensions for Extensions Framework 2.0.
It provides a ready to use template and a set of tools to build, test, package, and ship your extension.

.. raw:: html

   <p>
      <a href="https://pypi.org/project/dt-extensions-sdk"><img alt="PyPI" src="https://img.shields.io/pypi/v/dt-extensions-sdk.svg"></a>
      <a href="https://pypi.org/project/dt-extensions-sdk"><img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/dt-extensions-sdk.svg"></a>
   </p>

**What dt-sdk can do**

* Generate a new extension from template
* Run extensions locally
* Build and sign extensions

.. admonition:: Dynamic documentation
   :class: hint

   All code, command samples, and outputs below are dynamically generated during documentation build process using the latest version of ``db-extensions-sdk``.

Installation
------------

``db-extensions-sdk`` can be installed from PyPI.
For other installation options and :ref:`installation requirements` please see :doc:`/guides/installation`.

.. code:: bash

   pip install db-extensions-sdk

Getting Started
---------------

After installation, call ``dt-sdk --help`` to see the list of available commands:

.. program-output:: dt-sdk --help

Create extension
^^^^^^^^^^^^^^^^

To create a new extension, run ``dt-sdk create`` command:

.. command-output:: dt-sdk create my_extension

Full list of arguments that can be passed to ``dt-sdk create`` command:

.. program-output:: dt-sdk create --help

Documentation
-------------

.. toctree::
   :caption: Guides
   :maxdepth: 1

   guides/installation

.. toctree::
   :caption: API reference
   :maxdepth: 1

   api/extension
   api/metric
   api/event
