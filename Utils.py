import sys
import os

def get_path(*path):
    base_path = os.path.dirname(sys.executable) if sys.argv[0].endswith('.exe') else ''
    return os.path.join(base_path, *path)

def get_resource(*path):
    base_path = None
    try:
        base_path = sys._MEIPASS
        return os.path.join(base_path, *path)
    except:
        return get_path(*path)
