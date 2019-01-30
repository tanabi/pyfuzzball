#!/usr/bin/env python3

import io

from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))

# Import the README and use it as the long-description.
# Note: this will only work if 'README.md' is present in your MANIFEST.in file!
try:
    with io.open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
        long_description = '\n' + f.read()
except FileNotFoundError:
    long_description = "None"


setup(
    name="pyfuzzball",
    version="1.0",
    description="Package for working with MUCKs and MCP.",
    long_description=long_description,
    long_description_content_type='text/markdown',
    author="HopeIslandCoder",
    author_email="cheetah@tanabi.org",
    python_requires=">=3.4.0",
    url="https://github.com/tanabi/pyfuzzball",
    py_modules=['pyfuzzball'],
    include_package_data=True,
    license='Public Domain'
)
