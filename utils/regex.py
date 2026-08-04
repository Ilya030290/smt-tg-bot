import re

PATTERN_DIMENSIONS = re.compile(r'^[\d.]+;[\d.]+;[\d.]+$')
PATTERN_MULTIPLICATION = re.compile(r'^\d+;\d+$')
PATTERN_COORDS = re.compile(r'^-?\d+(\.\d+)?;-?\d+(\.\d+)?$')
PATTERN_COORDS_ANGLE = re.compile(r'^-?\d+(\.\d+)?;-?\d+(\.\d+)?;-?\d+(\.\d+)?$')
PATTERN_PITCH = re.compile(r'^[\d.]+;[\d.]+$')
