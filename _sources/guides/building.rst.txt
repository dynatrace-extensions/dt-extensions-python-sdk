Building Extensions
###################

| This guide provides some best practices on:
| 

* Building extensions
* Python dependencies
* CI systems, offline installs

Native dependencies
===================

| Some python libraries require "native" dependencies, they are not written in pure python and usually contain C, C++, Rust or other compiled languages code.
| This means that they might be compiled for a very specific version of python, or for a specific operating system.
|

| Examples:
|

* **requests** requires **charset_normalizer**, a **native dependency**


| If you navigate to the `charset-normalizer pypi page`_ you will see dozens of different wheel files.
| Each one of these files is compiled for a different version of python, and for a different operating system.
|
| Your extension will run on a Dynatrace **Activegate** or **OneAgent**, which is a Linux or Windows machine, and it has a specific version of python.
| This means that your extension must be built on a machine that has the same version of python as the Activegate.
|
| At this time, Dynatrace extensions run on **python 3.10**.
|
| When you build the extension with **dt-sdk build**, it downloads the dependencies **whl** files and places them in the lib folder of the extension.  
| To obtain whl files for different a operating system than what the build machine is, the SDK provides the **--extra-platform** flag.
|
| In summary, when building from Windows, you should use:
|

.. code-block:: bash

    dt-sdk build --extra-platform manylinux2014_x86_64


| To get the correct extra wheel files for linux. Note, **manylinux2014_x86_64** works for several packages, but not all of them.
| You need to investigate the dependencies of your extension to find the correct extra platform if that is the case.
|
| When building from Linux, you should use:
|


.. code-block:: bash

     dt-sdk build --extra-platform win_amd64


| To get the correct extra wheel files for Windows.  
|

PyPI Access
===========

| When building extensions, the SDK downloads the dependencies from PyPI.
|
| In some organizations, you are not allowed to access the internet from the build machine.
| In most cases you will have either:
| 

* A local PyPI mirror
* A directory with all the wheel files present

|
| Both of these solutions can be used with the SDK.
|

PyPI Mirror
"""""""""""

| Suppose you have a local PyPi server running on http://my-pypi-server:8080.
|
| To use it with the SDK, run the build command as:
|

.. code-block:: bash

     PIP_INDEX_URL=http://my-pypi-server:8080/simple PIP_TRUSTED_HOST=my-pypi-server dt-sdk build


| This will tell the SDK to use the local PyPI server to download the dependencies. 
| The SDK uses **pip** under the covers, so all the environment variables that **pip** supports can be used with the SDK.
|
| Note, that assumes the build machine is a linux machine. If you are building from Windows on Powershell, you can use:
|

.. code-block:: bash

    $ENV:PIP_INDEX_URL="http://my-pypi-server:8080/simple"; $ENV:PIP_TRUSTED_HOST="my-pypi-server"; dt-sdk build





Local Directory
"""""""""""""""


| Another option is to manually download the different whl files you need, and place them in a directory on the build machine.
| In that case, that directory can be used as the source for the dependencies.
|

.. code-block:: bash

    dt-sdk build --find-links /path/to/whl/files


| This will tell the SDK to use the directory as the source for the dependencies.
|

Musl vs libc
============

| Extensions run on `libc`_ based systems, like Ubuntu, CentOS, Windows, etc.
| You should not use a  `musl`_ based system, like Alpine, to build extensions.
|
| This means that if you are using a docker container to build the extension, you should use the **python:3.10** image, or any other image that is based on a `libc`_ system.
|
| The reason for this is that a **musl** based system will download native whl files that are not compatible with **libc** based systems.

.. _charset-normalizer pypi page: https://pypi.org/project/charset-normalizer/#files
.. _musl: https://musl.libc.org/
.. _libc: https://en.wikipedia.org/wiki/C_standard_library
