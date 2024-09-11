Installation
============

.. _installation requirements:

Requirements
^^^^^^^^^^^^

``dt-extensions-sdk`` requires only the following dependencies to be
present in the environment.

- Python 3.10

Installing from PyPI
^^^^^^^^^^^^^^^^^^^^

``dt-extensions-sdk`` can both be installed as a system wide package and as
a dependency in a python project.

.. code:: bash

   pip install dt-extensions-sdk[cli]

Once installed, the ``dt-sdk`` binary will become available in the ``PATH``.

.. admonition:: Core package
   :class: warning

   When installing ``dt-extensions-sdk[cli]`` with the optional set of
   dependecies called ``[cli]``, multiple additional packages which are required
   to make command line tools work will be installed.
   For example, such packages as ``typer[all]``, ``pyyaml``, and ``dt-cli``.

   When extension is being built, these additional packages are ignored,
   because the core dependecy of every extension is just the ``dt-extensions-sdk``
   itself. When the optioncal ``[cli]`` part is omitted, only the core package
   that is required to make any Python extension work on ActiveGate and OneAgent
   will be installed.
