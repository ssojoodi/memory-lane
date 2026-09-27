"""Read embedded GPS coordinates locally using the existing libvips tools."""

import math
import subprocess
from fractions import Fraction


def coordinate(value, reference, positive, negative, limit):
    degrees, minutes, seconds = [float(Fraction(part)) for part in value.split("(", 1)[0].split()]
    direction = reference.split("(", 1)[0].strip()
    result = degrees + minutes / 60 + seconds / 3600
    if (direction not in (positive, negative)
            or not all(math.isfinite(n) for n in (degrees, minutes, seconds))
            or not 0 <= degrees <= limit or not 0 <= minutes < 60
            or not 0 <= seconds < 60 or result > limit):
        raise ValueError("Invalid GPS coordinates")
    return -result if direction == negative else result


def map_url(path):
    fields = {}
    for name in ("GPSLatitude", "GPSLatitudeRef", "GPSLongitude", "GPSLongitudeRef"):
        result = subprocess.run(
            ["vipsheader", "-f", "exif-ifd3-" + name, str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=2,
        )
        if result.returncode != 0:
            return None
        fields[name] = result.stdout
    try:
        lat = coordinate(fields["GPSLatitude"], fields["GPSLatitudeRef"], "N", "S", 90)
        lon = coordinate(fields["GPSLongitude"], fields["GPSLongitudeRef"], "E", "W", 180)
    except (ValueError, ZeroDivisionError, OverflowError):
        return None
    return f"https://www.openstreetmap.org/?mlat={lat:.6f}&mlon={lon:.6f}#map=16/{lat:.6f}/{lon:.6f}"
