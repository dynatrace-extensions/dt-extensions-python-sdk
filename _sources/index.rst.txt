Dynatrace Extensions SDK for Python
===================================

``dt-extensions-sdk`` is a Python library and a toolbox for building Python
extensions for Extensions Framework 2.0. It provides a ready to use template
and a set of tools to build, test, package, and ship your extension.

.. raw:: html

   <p>
      <a href="https://pypi.org/project/dt-extensions-sdk">
         <img alt="PyPI" src="https://img.shields.io/pypi/v/dt-extensions-sdk.svg">
      </a>
      <a href="https://pypi.org/project/dt-extensions-sdk">
         <img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/dt-extensions-sdk.svg">
      </a>
   </p>

**What dt-sdk can do**

* Generate a new extension from template
* Run extensions locally
* Build and sign extensions

Installation
------------

``dt-extensions-sdk`` can be installed from PyPI.
For other installation options and :ref:`installation requirements`
please see :doc:`/guides/installation`.

.. code:: bash

   pip install dt-extensions-sdk[cli]

Installing in virtual environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This approach is recommended if you are working on several extensions:

.. code:: bash

   python -m venv .venv
   source .venv/bin/activate
   pip install dt-extensions-sdk

Keeping each extension in its own virtual environment is a good practice.
It guarantees that each extension has its own set of dependencies and
does not interfere with other extensions.

Quick Start
-----------

Once ``dt-sdk`` is installed, we are ready to create our first extension.

Create extension
^^^^^^^^^^^^^^^^

Let's generate a new extension called `my_extension` from scratch using the
:doc:`/cli/create` command:

.. code:: bash

   $ dt-sdk create my_extension
   Extension created at my_extension

This will create a new directory called `my_extension` with the following
structure:

.. code:: bash

   my_extension
   ├── README.md
   ├── activation.json
   ├── extension
   │   ├── activationSchema.json
   │   └── extension.yaml
   ├── my_extension
   │   ├── __init__.py
   │   └── __main__.py
   └── setup.py

.. admonition:: What do these files mean?
   :class: seealso

   Be sure to checkout the :doc:`/guides/extension_structure` guide for the detailed
   explanation of why each file is needed and what needs to be in there.

Run extension
^^^^^^^^^^^^^

In order to launch the extension locally, we can use the :doc:`/cli/run` command:

.. code:: bash
   
   $ cd my_extension
   $ dt-sdk run
   Running: .venv/dt-extensions-sdk/bin/python -m my_extension --activationconfig activation.json
   [INFO] api (MainThread): -----------------------------------------------------
   [INFO] api (MainThread): Starting <class '__main__.ExtensionImpl'> my_extension, version: 1.1.0
   [INFO] api (ThreadPoolExecutor-1_0): send_status: '{"status": "OK", "message": "", "timestamp": 1699993566909}'
   [INFO] api (ThreadPoolExecutor-1_1): send_sfm_metric: dsfm:datasource.python.threads,dt.extension.config.id="development_config_id" count,delta=4
   [INFO] dynatrace_extension.sdk.extension (ThreadPoolExecutor-0_0): query method started for my_extension.
   [INFO] dynatrace_extension.sdk.extension (ThreadPoolExecutor-0_0): query method ended for my_extension.

.. admonition:: Query method and scheduling
   :class: note

   The ``query()`` method in ``__main__.py`` file is scheduled to run every 60 seconds.
   You can also schedule other methods to run at different intervals by overriding
   :meth:`dynatrace_extension.Extension.initialize` method:
   schedule:

   .. code:: python

      def initialize(self):
          # Schedule the my_method method to run every 5 minutes
          self.schedule(self.my_method, timedelta(minutes=5))

We can see that the extension is running and the query method was successfully
executed. For now, it does not do anything useful, so it finishes immediately.

If we now press ``Ctrl+C`` to stop the execution, we will see the following output:

.. code:: bash

   ^C[INFO] api (MainThread): SIGINT captured. Flushing metrics and exiting...
   [INFO] api (MainThread): send_metric: my_metric,my_dimension="dimension1" gauge,1 1699993566910
   [INFO] api (MainThread): Sent 1 metric lines to EEC: [MintResponse(lines_ok=1, lines_invalid=0, error=None, warnings=None)]
   [INFO] api (MainThread): send_sfm_metric: dsfm:datasource.python.threads,dt.extension.config.id="development_config_id" count,delta=4
   [INFO] api (MainThread): send_sfm_metric: dsfm:datasource.python.execution.time,callback="query",dt.extension.config.id="development_config_id" gauge,0.0003
   [INFO] api (MainThread): send_sfm_metric: dsfm:datasource.python.execution.total.count,callback="query",dt.extension.config.id="development_config_id" count,delta=1
   [INFO] api (MainThread): send_sfm_metric: dsfm:datasource.python.execution.count,callback="query",dt.extension.config.id="development_config_id" count,delta=1
   [INFO] api (MainThread): send_sfm_metric: dsfm:datasource.python.execution.ok.count,callback="query",dt.extension.config.id="development_config_id" count,delta=1
   [INFO] api (MainThread): send_sfm_metric: dsfm:datasource.python.execution.timeout.count,callback="query",dt.extension.config.id="development_config_id" count,delta=0
   [INFO] api (MainThread): send_sfm_metric: dsfm:datasource.python.execution.exception.count,callback="query",dt.extension.config.id="development_config_id" count,delta=0

We can see here, that the extension has sent 1 metric to the Dynatrace. That's because
the ``query()`` contains the following line:

.. code:: python

   # Report metrics with
   self.report_metric("my_metric", 1, dimensions={"my_dimension": "dimension1"})

This code sends a single data point for the metric called ``my_metric`` with
value ``1`` and dimension ``my_dimension`` with value ``dimension1``.
The next data point for same metric will be sent in 60 seconds, when the ``query()``
method executes again.

.. admonition:: Self monitoring metrics
   :class: note

   You might have noticed that there are some additional metrics being sent
   to Dynatrace. These are called self monitoring metrics and they allow the environment
   to understand how the extension is performing and whether everything is fine with
   the assigned monitoring configuration.

Generate certificates
^^^^^^^^^^^^^^^^^^^^^

In order to sign the extension, we need to have a certificate that is uploaded
to the environment and to the OneAgent or Activegate hosts
that will run the extension.

.. admonition:: Already have the certificate?
   :class: hint

   If you already have the certificate and it is uploaded to the environment and hosts
   you can skip this step and go directly to the build step.

In order to generate a new certificate, we can use the :doc:`/cli/gencerts` command:

.. code:: bash
   
   $ dt-sdk gencerts
   Running: dt ext genca --ca-cert /Users/myuser/.dynatrace/certificates/ca.pem --ca-key
   /Users/myuser/.dynatrace/certificates/ca.key --no-ca-passphrase
   Generating CA...
   Wrote CA private key: /Users/myuser/.dynatrace/certificates/ca.key
   Wrote CA certificate: /Users/myuser/.dynatrace/certificates/ca.pem
   Running: dt ext generate-developer-pem --output /Users/myuser/.dynatrace/certificates/developer.pem --name Acme
   --ca-crt /Users/myuser/.dynatrace/certificates/ca.pem --ca-key /Users/myuser/.dynatrace/certificates/ca.key
   Loading CA private key /Users/myuser/.dynatrace/certificates/ca.key
   Loading CA certificate /Users/myuser/.dynatrace/certificates/ca.pem
   Generating developer certificate...
   Wrote developer certificate: /Users/myuser/.dynatrace/certificates/developer.pem
   Wrote developer private key: /Users/myuser/.dynatrace/certificates/developer.pem

This will place the developer certificates in the default directory.

.. admonition:: Detailed documentation
   :class: info

   For more information on how to generate and upload certificates, please see
   `certificates`_ documentation.

Build extension
^^^^^^^^^^^^^^^

Now that we have a working extension and a certificate to sing it with, 
we can build it using the :doc:`/cli/build` command, which will perform the following
steps:

1. Download the dependencies
2. Build a wheel
3. Package the build into a ``.zip`` archive
4. Sign the archive with the given certificate

.. code:: bash
   
   $ dt-sdk build
   Building and signing extension from my_extension to None
   Stage 1 - Download and build dependencies
   Cleaning my_extension/extension/lib
   Downloading dependencies to my_extension/extension/lib
   Running: .venv/dt-extensions-sdk/bin/python -m pip wheel -w extension/lib .
   Processing my_extension
   Preparing metadata (setup.py) ... done
   Collecting dt-extensions-sdk (from my-extension==0.0.1)
   Using cached dt_extensions_sdk-1.1.0-py3-none-any.whl.metadata (1.8 kB)
   Using cached dt_extensions_sdk-1.1.0-py3-none-any.whl (42 kB)
   Saved ./extension/lib/dt_extensions_sdk-1.1.0-py3-none-any.whl
   Building wheels for collected packages: my-extension
   Building wheel for my-extension (setup.py) ... done
   Created wheel for my-extension: filename=my_extension-0.0.1-py3-none-any.whl size=1985 sha256=19039181b70d68105512ad52b80129368724b3f15e0ba2a2b5fdb98cc710e705
   Stored in directory: /private/var/folders/jd/s1xmb3jj31gcd11g3p4ncctm5q47pj/T/pip-ephem-wheel-cache-zqkysr41/wheels/9c/1c/44/e47f092abb0d0b281251f7cfc7b8d5993c2c5678b3acd80751
   Successfully built my-extension
   Installed dependencies to my_extension/extension/lib
   Stage 2 - Create the extension zip file
   Running: dt ext assemble --source my_extension/extension --output my_extension/dist/extension.zip --force
   my_extension/dist/extension.zip file already exists, it will be overwritten!
   Building my_extension/dist/extension.zip from my_extension/extension
   Adding file: my_extension/extension/lib/my_extension-0.0.1-py3-none-any.whl as lib/my_extension-0.0.1-py3-none-any.whl
   Adding file: my_extension/extension/lib/dt_extensions_sdk-1.1.0-py3-none-any.whl as lib/dt_extensions_sdk-1.1.0-py3-none-any.whl
   Adding file: my_extension/extension/extension.yaml as extension.yaml
   Adding file: my_extension/extension/activationSchema.json as activationSchema.json
   Built the extension zip file to my_extension/dist/extension.zip
   Stage 3 - Sign the extension
   Signing file my_extension/dist/extension.zip to my_extension/dist/custom_my-extension-0.0.1.zip with certificate
   /Users/myuser/.dynatrace/certificates/developer.pem
   Running: dt ext sign --src my_extension/dist/extension.zip --output my_extension/dist/custom_my-extension-0.0.1.zip
   --key /Users/myuser/.dynatrace/certificates/developer.pem --force
   Created signed extension file my_extension/dist/custom_my-extension-0.0.1.zip
   Stage 4 - Delete my_extension/dist/extension.zip

Once completed, the signed build will be placed in the ``dist`` directory:

.. code:: bash

   dist/custom_my-extension-0.0.1.zip

Upload extension
^^^^^^^^^^^^^^^^

Finally, we can upload the extension to the environment using the :doc:`/cli/upload`
command. It requires us to provide the environment URL and an API token with the permission
to upload extensions. This can be done via environment variables or command line arguments

.. code:: bash

   $ dt-sdk upload
   Uploading extension dist/custom_my-extension-0.0.1.zip to https://<your_environment_url_here>/
   Extension upload successful!
   Extension dist/custom_my-extension-0.0.1.zip uploaded to https://<your_environment_url_here>/

Documentation
-------------

.. toctree::
   :caption: Guides
   :maxdepth: 3

   guides/installation
   guides/extension_structure
   guides/building
   guides/migration

.. toctree::
   :caption: All Commands
   :maxdepth: 3

   cli/create
   cli/build
   cli/run
   cli/upload
   cli/help
   cli/assemble
   cli/gencerts
   cli/sign
   cli/wheel

.. toctree::
   :caption: API Reference
   :maxdepth: 2

   api/extension
   api/events/index
   api/metrics/index

.. _certificates: https://docs.dynatrace.com/docs/extend-dynatrace/extensions20/sign-extension
