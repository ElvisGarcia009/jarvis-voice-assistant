import os
import sys

# Import jarvis.py from the repository root (importing it starts nothing: no mic, GTK loop or service)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
