"""
api.py
======
Local runner for KYC — Know Your Courses.
Runs the Flask application defined in api/index.py.
"""

import subprocess
import sys
import os

if __name__ == "__main__":
    script = os.path.join(os.path.dirname(__file__), "api", "index.py")
    subprocess.run([sys.executable, script])
