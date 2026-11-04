import sys
from unittest.mock import MagicMock

# Mock dependencies of fetch_jobs
mock_modules = [
    'fitz', 'pdfplumber', 'telegram', 'telegram.error',
    'pandas', 'numpy', 'tqdm', 'colorlog', 'yaml', 'pathlib2', 'dotenv'
]

for module_name in mock_modules:
    sys.modules[module_name] = MagicMock()
