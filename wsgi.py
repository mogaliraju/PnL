import sys
import os

# Add your app directory to path
path = '/home/SrikarMogaliraju/PnL'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ['DATA_DIR'] = '/home/SrikarMogaliraju/PnL/userdata'

from app import app as application
