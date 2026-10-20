"""Drive the Hyprland cursor with the index fingertip.

Usage:
  uv run hypr_hands.py pc [video source]   # PC runs MediaPipe on the IP Webcam stream (or a camera index)
  uv run hypr_hands.py phone               # phone runs MediaPipe in Chrome (phone.html) and sends landmarks

Options: --monitor NAME (default: focused monitor), --no-mirror.
The cursor only moves while you point (index up, middle finger folded), so a relaxed hand never grabs it.
"""
import argparse
import json
import math
import os
import queue
import socket
import threading
import time
from pathlib import Path

ROOT = Path(__file__).parent
MODEL = ROOT / "models" / "hand_landmarker.task"
PHONE_PORT = 8765
# Fraction of the camera frame that maps to the whole monitor, so you don't have to reach the frame edges.
ACTIVE = (0.2, 0.2, 0.8, 0.8)
# Seconds of motion prediction to hide camera + inference + glide latency on fast moves.
LEAD = 0.06


class OneEuro:
    """One Euro filter (Casiez et al.): smooth when the hand is still, responsive when it moves fast."""

    def __init__(self, min_cutoff=1.0, beta=0.02, d_cutoff=1.0):
        self.min_cutoff, self.beta, self.d_cutoff = min_cutoff, beta, d_cutoff
        self.x = self.dx = self.t = None

    @staticmethod
    def _alpha(cutoff, dt):
        r = 2 * math.pi * cutoff * dt
        return r / (r + 1)

    def __call__(self, x, t):
        if self.t is None or t <= self.t:
            self.x, self.dx, self.t = x, 0.0, t
            return x
        dt = t - self.t
        dx = (x - self.x) / dt
        self.dx += self._alpha(self.d_cutoff, dt) * (dx - self.dx)
        cutoff = self.min_cutoff + self.beta * abs(self.dx)
        self.x += self._alpha(cutoff, dt) * (x - self.x)
        self.t = t
        return self.x


class Hypr:
    def __init__(self):
        sig = os.environ["HYPRLAND_INSTANCE_SIGNATURE"]
        self.path = f"{os.environ['XDG_RUNTIME_DIR']}/hypr/{sig}/.socket.sock"

    def cmd(self, text):
        # Hyprland closes the socket after each request, so one connection per command.
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(self.path)
            s.sendall(text.encode())
            chunks = []
            while chunk := s.recv(65536):
                chunks.append(chunk)
        return b"".join(chunks).decode()

    def monitor(self, name=None):
        mons = json.loads(self.cmd("j/monitors"))
        for m in mons:
            if m["name"] == name or (name is None and m["focused"]):
                return m
        raise SystemExit(f"monitor not found: {name}; have {[m['name'] for m in mons]}")


class Glide:
    """Moves the cursor toward the latest target at the monitor refresh rate, so ~25 fps hand updates don't look steppy."""

    def __init__(self, hypr, hz, tau=0.025):
        self.hypr, self.period, self.tau = hypr, 1 / hz, tau
        self.target = self.pos = None
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        last, t_prev = None, time.perf_counter()
        while True:
            time.sleep(self.period)
            t = time.perf_counter()
            dt, t_prev = t - t_prev, t
            target = self.target
            if target is None:
                self.pos = None
                continue
            if self.pos is None:
                cur = json.loads(self.hypr.cmd("j/cursorpos"))
                self.pos = (float(cur["x"]), float(cur["y"]))
            k = 1 - math.exp(-dt / self.tau)
            self.pos = tuple(p + (q - p) * k for p, q in zip(self.pos, target))
            xy = tuple(round(p) for p in self.pos)
            if xy != last:
                # Hyprland 0.56 dispatchers are Lua; the old "movecursor x y" form is rejected.
                reply = self.hypr.cmd(f"dispatch hl.dsp.cursor.move({{x={xy[0]},y={xy[1]}}})").strip()
                if reply != "ok":
                    print(f"hyprland rejected cursor move: {reply}", flush=True)
                    os._exit(1)
                last = xy


def is_pointing(lm):
    """Index tip above its middle joint and middle fingertip below its own (image y grows downward)."""
    return lm[8][1] < lm[6][1] and lm[12][1] > lm[10][1]


def to_screen(x, y, mon, mirror):
    x0, y0, x1, y1 = ACTIVE
    u = min(max((x - x0) / (x1 - x0), 0.0), 1.0)
    v = min(max((y - y0) / (y1 - y0), 0.0), 1.0)
    if mirror:
        u = 1 - u
    w, h = mon["width"] / mon["scale"], mon["height"] / mon["scale"]
    return round(mon["x"] + u * (w - 1)), round(mon["y"] + v * (h - 1))


def pc_source(src):
    """Yields (landmarks or None, frame_time) from MediaPipe running on this PC."""
    import cv2
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision

    from f0_view import LatestFrame

    landmarker = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODEL)), running_mode=vision.RunningMode.VIDEO))
    stream, seq, t0 = LatestFrame(src), 0, time.perf_counter()
    while True:
        frame, seq_new = stream.next(seq)
        if not stream.running:
            raise SystemExit("video stream ended")
        if frame is None or seq_new == seq:
            continue
        seq, t = seq_new, time.perf_counter()
        rgb = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        res = landmarker.detect_for_video(rgb, int((t - t0) * 1000))
        yield ([(p.x, p.y) for p in res.hand_landmarks[0]] if res.hand_landmarks else None), t


def phone_source():
    """Serves phone.html and the model, then yields landmarks the phone sends over a WebSocket."""
    from websockets.datastructures import Headers
    from websockets.http11 import Response
    from websockets.sync.server import serve

    files = {"/": (ROOT / "phone.html", "text/html; charset=utf-8"),
             "/hand_landmarker.task": (MODEL, "application/octet-stream")}
    latest = queue.Queue(maxsize=1)

    def process_request(conn, req):
        if req.path == "/ws":
            return None
        path, ctype = files.get(req.path, (None, None))
        if path is None:
            return conn.respond(404, "not found\n")
        return Response(200, "OK", Headers([("Content-Type", ctype), ("Cache-Control", "no-store")]), path.read_bytes())

    def handler(conn):
        print("phone connected")
        for msg in conn:
            data = json.loads(msg)
            hand = data.get("hand")
            item = ([tuple(p) for p in hand] if hand else None), time.perf_counter()
            try:
                latest.get_nowait()
            except queue.Empty:
                pass
            latest.put(item)
        print("phone disconnected")

    server = serve(handler, "127.0.0.1", PHONE_PORT, process_request=process_request, max_size=2**16)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"open http://localhost:{PHONE_PORT}/ on the phone (adb reverse tcp:{PHONE_PORT} tcp:{PHONE_PORT})")
    while True:
        yield latest.get()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", choices=["pc", "phone"])
    ap.add_argument("video", nargs="?", default="http://127.0.0.1:8090/video")
    ap.add_argument("--monitor")
    ap.add_argument("--no-mirror", dest="mirror", action="store_false")
    args = ap.parse_args()

    hypr = Hypr()
    mon = hypr.monitor(args.monitor)
    print(f"monitor {mon['name']} {mon['width']}x{mon['height']} at {mon['x']},{mon['y']}; Ctrl+C to stop")
    video = int(args.video) if args.video.isdigit() else args.video
    frames = pc_source(video) if args.source == "pc" else phone_source()

    # beta is in normalized frame units per second: high enough that fast moves don't lag.
    fx, fy = OneEuro(min_cutoff=0.8, beta=8.0), OneEuro(min_cutoff=0.8, beta=8.0)
    glide = Glide(hypr, mon["refreshRate"])
    n, t_report = 0, time.perf_counter()
    for lm, t in frames:
        n += 1
        if lm and is_pointing(lm):
            # Aim where the finger will be LEAD seconds from now, using the filter's velocity estimate.
            x, y = fx(lm[8][0], t), fy(lm[8][1], t)
            glide.target = to_screen(x + fx.dx * LEAD, y + fy.dx * LEAD, mon, args.mirror)
            t_point = t
        elif glide.target and t - t_point > 0.15:  # ignore one-frame detection flickers
            glide.target = None
        if t - t_report >= 2:
            print(f"{n / (t - t_report):4.1f} fps  hand={'yes' if lm else 'no '}  pointing={bool(lm and is_pointing(lm))}")
            n, t_report = 0, t


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
