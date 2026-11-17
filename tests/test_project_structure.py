
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings

print(settings.app_name)
print(settings.app_env)
print(settings.app_version)
print(settings.api_v1_prefix)
print(settings.default_model)
print(settings.supported_models)