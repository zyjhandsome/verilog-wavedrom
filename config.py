"""
Configuration settings for Verilog to WaveDrom conversion pipeline.
"""

from pathlib import Path

# Directory settings
DATA_DIR = Path(__file__).parent / "verilog-wavedrom" / "data"
OUTPUT_DIR = Path(__file__).parent / "output"

# Processing settings
SUBSET_SIZE = 100  # Number of samples to process (0 for all)
MAX_SIGNALS = 20  # Maximum signals to include in WaveDrom
MAX_TIME_STEPS = 50  # Maximum time steps to show

# Signal priority for sorting (higher priority first)
SIGNAL_PRIORITY = ['clk', 'clock', 'rst', 'reset', 'en', 'enable']

# WaveDrom configuration
WAVEDROM_CONFIG = {"hscale": 2}
WAVEDROM_HEAD = {"text": "Timing Diagram", "tick": 0}
WAVEDROM_FOOT = {"text": "Cycle numbers", "tick": 0}

# Simulation settings
SIMULATION_TIMEOUT = 30  # seconds
VCD_DUMP_TIME = 1000  # simulation time units
