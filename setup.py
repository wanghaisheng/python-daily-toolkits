"""
something is from https://github.com/pypa/sampleproject
"""

"""A setuptools based setup module.
See:
https://packaging.python.org/guides/distributing-packages-using-setuptools/
https://github.com/pypa/sampleproject
"""

import pathlib

# Always prefer setuptools over distutils
from setuptools import find_packages, setup

here = pathlib.Path(__file__).parent.resolve()

# Get the long description from the README file
long_description = (here / "README.md").read_text(encoding="utf-8")

setup(
    name = "mbapy",
    version = "0.0.1",

    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: normal users",
        "Topic :: uitls",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3 :: Only",
    ],
        
    keywords = ("pip", "mbapy", "utils", "scripts"),
    description = "MyBA in Python",
    long_description = long_description,
    long_description_content_type='text/markdown',
    python_requires=">=3.7.0",
    license = "MIT Licence",

    url = "https://github.com/BHM-Bob/BA_PY",
    author = "BHM-Bob G",
    author_email = "bhmfly@foxmail.com",
    
    # package_dir={"": "src"},
    packages=["src/mbapy"],
    
    include_package_data = True,
    platforms = "any",
)
