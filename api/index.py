import os
import sys
import importlib.util

# Add repository root to path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Load the Flask app from api.py at repo root
_api_py_path = os.path.join(_ROOT, "api.py")
_spec = importlib.util.spec_from_file_location("kyc_api", _api_py_path)
_module = importlib.util.module_from_spec(_spec)
sys.modules["kyc_api"] = _module
_spec.loader.exec_module(_module)

app = _module.app
