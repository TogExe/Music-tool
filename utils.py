import math

def dist_to_segment(px, py, x1, y1, x2, y2):
    """Calculates distance from a point to a line segment (used for selecting wires)."""
    l2 = (x2 - x1) ** 2 + (y2 - y1) ** 2
    if l2 == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0, min(1, ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / l2))
    proj_x, proj_y = x1 + t * (x2 - x1), y1 + t * (y2 - y1)
    return math.hypot(px - proj_x, py - proj_y)