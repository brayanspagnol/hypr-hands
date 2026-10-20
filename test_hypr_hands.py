"""Self-checks for the pure logic: uv run test_hypr_hands.py"""
from hypr_hands import OneEuro, is_pointing, to_screen

MON = {"x": 0, "y": -2000, "width": 1920, "height": 1080, "scale": 1}

# Active area: 0.6 of the frame width spans the monitor width; height follows the monitor aspect,
# so one unit of hand motion moves the cursor the same distance in both axes.
assert to_screen(0.2, 0.5, MON, False) == (0, -1460)
assert to_screen(0.8, 0.5, MON, False) == (1919, -1460)
assert to_screen(0.0, 1.0, MON, False) == (0, -921)  # clamped
assert to_screen(0.2, 0.5, MON, True) == (1919, -1460)
WIDE = {"x": 0, "y": 0, "width": 3440, "height": 1440, "scale": 1}
dx = to_screen(0.55, 0.5, WIDE, False)[0] - to_screen(0.5, 0.5, WIDE, False)[0]
dy = to_screen(0.5, 0.5 + 0.05 * 4 / 3, WIDE, False)[1] - to_screen(0.5, 0.5, WIDE, False)[1]
assert abs(dx - dy) <= 2, (dx, dy)  # same physical hand distance (4:3 frame) gives same cursor distance

# Pointing: index tip (8) above its PIP (6), middle tip (12) below its PIP (10).
hand = [(0.5, 0.5)] * 21
hand[8], hand[6], hand[12], hand[10] = (0.5, 0.2), (0.5, 0.4), (0.5, 0.6), (0.5, 0.45)
assert is_pointing(hand)
hand[12] = (0.5, 0.2)  # middle finger up too: open hand
assert not is_pointing(hand)

# One Euro: constant input stays put, a step converges toward the new value without overshoot.
f = OneEuro()
assert f(1.0, 0.0) == 1.0 and f(1.0, 0.05) == 1.0
ys = [f(2.0, 0.05 * i) for i in range(2, 40)]
assert all(1.0 < a <= b <= 2.0 for a, b in zip(ys, ys[1:])) and ys[-1] > 1.95
print("ok")
