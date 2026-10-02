#!/usr/bin/env python3
"""Setup script for jimoty (jimoty-cli)."""

from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="jimoty",
    version="0.1.0",
    description="Agent-native CLI tool and Python library for Japan Jimoty (jmty.jp) listings, search, scraping, and diagnostic evaluation.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="V",
    license="MIT",
    python_requires=">=3.9",
    packages=find_packages(include=["jimoty", "jimoty.*"]),
    install_requires=[
        "httpx>=0.24.0",
        "beautifulsoup4>=4.12.0",
    ],
    extras_require={
        "test": [
            "pytest>=7.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "jimoty = jimoty.cli:main",
            "jimoty-cli = jimoty.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Utilities",
    ],
)
