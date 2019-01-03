#!/usr/bin/env python
"""Execute pre-commit checks outside a commit."""
import subprocess
import sys

if "--setup" in sys.argv:
    subprocess.run(["python", "env-setup.py"], check=True)
subprocess.run(["poetry", "run", "pre-commit", "run"], check=True)
