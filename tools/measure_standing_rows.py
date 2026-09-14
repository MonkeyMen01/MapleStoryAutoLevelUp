"""Measure where the character actually stands, instead of deriving it.

Every route so far was drawn on rows taken from the map image - first from blob
bounding boxes, then from terrain top edges. Both disagree with where the dot
really sits by a few rows, and a few rows is enough to hand the character the
wrong level's command. The bottom walkway needed rows 125-127 while extraction
claimed 130.

So drive the character around and record the rows it occupies. Rows it never
occupies are not walkable, whatever the image suggests; rows it rests on are
exactly where the route lines belong.
"""
import sys, time, cv2, os
from collections import Counter
sys.path.insert(0, r"C:\Users\d0981\MapleStoryAutoLevelUp")
os.chdir(r"C:\Users\d0981\MapleStoryAutoLevelUp")
from src.utils.common import (load_yaml, override_cfg, get_minimap_loc_size,
                              get_player_location_on_minimap, find_pattern_sqdiff,
                              load_image)
from src.input.GameWindowCapturor import GameWindowCapturor

cfg = override_cfg(load_yaml('config/config_default.yaml'),
                   load_yaml('config/config_custom.yaml'))
img_map = load_image("minimaps/south_forest_training_ground_1/map.png", cv2.IMREAD_COLOR)
tb = cfg["game_window"]["title_bar_height"]
cap = GameWindowCapturor(cfg)

def sample():
    if cap.frame is None:
        return None
    nt = cap.frame[tb:, :]
    im = cv2.cvtColor(nt, cv2.COLOR_BGRA2BGR) if nt.shape[2] == 4 else nt
    w = cv2.resize(im, (1296, 700), interpolation=cv2.INTER_NEAREST)
    r = get_minimap_loc_size(w)
    if r is None:
        return None
    x, y, ww, hh = [int(v) for v in r]
    mm = w[y+1:y+hh-1, x+1:x+ww-1]
    d = get_player_location_on_minimap(mm, minimap_player_color=cfg["minimap"]["player_color"])
    if d is None:
        return None
    loc, _, _ = find_pattern_sqdiff(img_map, mm)
    return (loc[0] + d[0], loc[1] + d[1])

DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 120
pts, t0 = [], time.time()
while time.time() - t0 < DURATION:
    s = sample()
    if s:
        pts.append(s)
    time.sleep(0.4)

cap.is_terminated = True
try:
    cap.capture_control.stop()
except Exception:
    pass

rows = Counter(p[1] for p in pts)
print(f"{len(pts)} samples over {DURATION:.0f}s\n")
print(f"{'row':>4} {'hits':>5}  {'x range':>10}  {'':<20}")
for r in sorted(rows):
    xs = [p[0] for p in pts if p[1] == r]
    bar = "#" * min(40, rows[r])
    print(f"{r:4d} {rows[r]:5d}  {min(xs):3d}-{max(xs):<3d}   {bar}")
print("\nrows holding >=3% of samples are real standing levels:")
th = max(2, len(pts) * 0.03)
levels = []
for r in sorted(rows):
    if rows[r] >= th:
        xs = [p[0] for p in pts if p[1] == r]
        levels.append((r, min(xs), max(xs)))
for r, a, b in levels:
    print(f"   row {r:3d}  x{a}-{b}")
print("\nMEASURED = " + repr(levels))
