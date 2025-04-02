# Dynatrace Extensions Python SDK

[![PyPI - Version](https://img.shields.io/pypi/v/dt-extensions-sdk.svg)](https://pypi.org/project/dt-extensions-sdk)
[![PyPI - Python Version](https://img.shields.io/badge/python-3.10-blue)](https://img.shields.io/badge/python-3.10-blue)

-----

**Table of Contents**

- [Quick Start](#quick-start)
- [License](#license)
- [Developing](#developing)

## Documentation

The documentation can be found on [github pages](https://dynatrace-extensions.github.io/dt-extensions-python-sdk/) 

## Quick Start

### Requirements:

* Python 3.10 is recommended
* Running on later Python versions is possible, but you have to adjust command lines, and simulate does not work

### Install the SDK

```bash
pip install dt-extensions-sdk[cli]
# Note, on some shells like zsh you may need to escape the brackets - pip install dt-extensions-sdk\[cli\]
```

### Create signing certificates

```bash
dt-sdk gencerts
```

### Create a new extension

```bash
dt-sdk create my_first_extension
```

### Simulate

To simulate extension you need to run it on the same Python version as the framework, so Python 3.10

```bash
cd my_first_extension
dt-sdk run
```

### Build
   
On Python 3.10
 
```bash
dt-sdk build
```

On other versions of Python (e.g. 3.2) you need to specifically provide platforms that extension has to support, for example:

```bash
dt-sdk build -o -e win_amd64,manylinux1_x86_64
```


### Upload
    
```bash
# Note, you need to either set environment variables DT_API_URL and DT_API_TOKEN or pass them as arguments
dt-sdk upload
```

## Developing

### Testing

```console
hatch run test
```

### Linting

```console
hatch run lint:all
```

### Building

```console
hatch build
```

### Building docs

```console
hatch run docs:build
```

## License

`dt-extensions-sdk` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.


## Publishing to PyPI

It's automatically published to PyPi on each pushed tag, and uses [gh-action-pypi-publish](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/)
Version will be determined using __about__.py
