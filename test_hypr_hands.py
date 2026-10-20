"""Self-checks for the pure logic: uv run test_hypr_hands.py"""
from hypr_hands import OneEuro, is_pointing, to_screen

MON = {"x": 0, "y": -2000, "width": 1920, "height": 1080, "scale": 1}

# Active area corners map to monitor corners; outside is clamped; mirror flips x.
assert to_screen(0.2, 0.2, MON, False) == (0, -2000)
assert to_screen(0.8, 0.8, MON, False) == (1919, -921)
assert to_screen(0.0, 1.0, MON, False) == (0, -921)
assert to_screen(0.2, 0.5, MON, True) == (1919, -1460)

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
