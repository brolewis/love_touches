#!/usr/bin/env python
"""Setup development environment."""
import subprocess

subprocess.run(["poetry", "install"], check=True)
subprocess.run(["poetry", "run", "pre-commit", "install"], check=True)
