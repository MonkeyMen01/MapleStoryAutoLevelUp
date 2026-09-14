"""Draw the route on rows the character was measured standing on.

Every earlier route was drawn on rows derived from the map image, and both
derivations disagreed with reality by a few rows - enough to hand the character
another level's command. These rows come from watching where the dot actually
rested while the map was walked by hand.

The layout deliberately avoids needing to know which platform sits under which:

  route1  every row walks LEFT, crosses a down-jump band, ends at a goal on the
          left edge
  route2  every row walks RIGHT, crosses an up-jump band, ends at a goal on the
          right edge

So the character falls its way down, hands over, climbs its way up, hands back.
A jump that does not land costs nothing: it keeps walking and takes the row's
goal instead, which is still progress rather than a deadlock.
"""
import cv2, yaml, sys, os

ROOT = r"C:\Users\d0981\MapleStoryAutoLevelUp"
sys.path.insert(0, ROOT); os.chdir(ROOT)
D = "minimaps/south_forest_training_ground_1"
cfg = yaml.safe_load(open("config/config_default.yaml", encoding="utf-8"))
RGB = {v: tuple(map(int, k.split(','))) for k, v in cfg["route"]["color_code"].items()}
bgr = lambda c: (c[2], c[1], c[0])
codes = {tuple(map(int, k.split(','))): v for k, v in cfg["route"]["color_code"].items()}

# row -> (hits, x0, x1), measured over 150s of hand driving
H = {
    46: (22, 31, 45), 48: (4, 46, 48), 49: (15, 43, 52), 51: (4, 41, 45),
    52: (8, 40, 45), 53: (17, 34, 45), 55: (6, 45, 48), 56: (9, 43, 45),
    58: (5, 43, 50), 59: (8, 40, 47), 62: (6, 27, 41), 63: (16, 25, 42),
    66: (13, 25, 35), 69: (4, 42, 45), 70: (16, 31, 47), 71: (7, 44, 52),
    74: (7, 39, 45), 75: (6, 37, 42), 79: (11, 31, 37), 82: (14, 28, 38),
    84: (4, 40, 44), 85: (9, 38, 43), 88: (11, 35, 43), 91: (11, 39, 48),
    92: (12, 31, 38), 94: (4, 46, 51), 95: (8, 48, 53), 98: (8, 44, 48),
    102: (7, 41, 43), 103: (6, 38, 41), 105: (4, 45, 48), 106: (4, 42, 44),
    108: (4, 42, 46), 109: (12, 43, 52), 113: (8, 32, 39), 116: (7, 31, 37),
    119: (4, 36, 41), 120: (6, 35, 38), 122: (5, 38, 45), 125: (8, 36, 53),
    126: (6, 31, 39), 127: (3, 26, 29),
}
# Use each row's OWN measured reach. Borrowing a neighbour's range looked like
# useful slack but a neighbouring row is often a different platform: row 127 was
# measured at x26-29, and merging that into row 126 put row 126's goal at x26,
# out past the edge the character can actually walk to. It then pressed left
# against the drop for a minute.
rows = sorted(H)
SPAN = {r: (H[r][1], H[r][2]) for r in rows}

m = cv2.imread(f"{D}/map.png")
r1, r2 = m.copy(), m.copy()
GOAL, BAND = 3, 4

for r in rows:
    x0, x1 = SPAN[r]
    if x1 - x0 + 1 < GOAL + BAND + 2:
        x0, x1 = max(25, x0 - 2), min(55, x1 + 2)
    c = (x0 + x1) // 2

    # route1: goal at the left edge, walk left, down jump band in the middle
    r1[r, x0 + GOAL:x1 + 1] = bgr(RGB["left none none"])
    r1[r, c - BAND // 2:c + BAND // 2 + 1] = bgr(RGB["none down jump"])
    r1[r, x0:x0 + GOAL] = bgr(RGB["none none goal"])

    # route2: goal at the right edge, walk right, up jump band in the middle
    r2[r, x0:x1 + 1 - GOAL] = bgr(RGB["right none none"])
    r2[r, c - BAND // 2:c + BAND // 2 + 1] = bgr(RGB["right none jump"])
    r2[r, x1 + 1 - GOAL:x1 + 1] = bgr(RGB["none none goal"])

cv2.imwrite(f"{D}/route1.png", r1)
cv2.imwrite(f"{D}/route2.png", r2)
print(f"drew {len(rows)} measured rows on both routes")

# the character must find a command wherever it was ever seen standing
miss = []
for name, img in (("route1", r1), ("route2", r2)):
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    for r in rows:
        for x in range(H[r][1], H[r][2] + 1):
            if tuple(int(v) for v in rgb[r, x]) not in codes:
                miss.append((name, r, x))
print(f"measured positions with no command: {len(miss)}")
print("sample row 92 on each route:")
for name, img in (("route1", r1), ("route2", r2)):
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    runs = []
    for x in range(25, 56):
        c = codes.get(tuple(int(v) for v in rgb[92, x]))
        if runs and runs[-1][2] == c:
            runs[-1][1] = x
        else:
            runs.append([x, x, c])
    print(f"  {name}: " + "  ".join(f"x{a}-{b}:{c}" for a, b, c in runs if c))
