import math


def distance_point_to_segment(px, py, x1, y1, x2, y2):
    dx = x2 - x1
    dy = y2 - y1

    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)

    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0, min(1, t))

    closest_x = x1 + t * dx
    closest_y = y1 + t * dy

    return math.hypot(px - closest_x, py - closest_y)


def find_nearest_segment(lat, lon, segments):
    min_distance = float("inf")
    best_segment = None

    for seg in segments:
        start = seg["start"]
        end = seg["end"]

        d = distance_point_to_segment(
            lat, lon,
            start["lat"], start["lon"],
            end["lat"], end["lon"]
        )

        if d < min_distance:
            min_distance = d
            best_segment = seg

    return best_segment





def project_point_on_segment(px, py, x1, y1, x2, y2):
    """
    Projects point (px, py) onto segment (x1,y1) → (x2,y2)

    Returns:
    - projected point (lat, lon)
    - t (progress along segment 0 → 1)
    """

    dx = x2 - x1
    dy = y2 - y1

    if dx == 0 and dy == 0:
        return (x1, y1, 0)

    # projection factor
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)

    # clamp between 0 and 1
    t = max(0, min(1, t))

    # projected point
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy

    return (proj_x, proj_y, t)
import math

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c