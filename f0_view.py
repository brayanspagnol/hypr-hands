"""F0: show the camera feed with the hand skeleton, FPS and inference time.

Usage: uv run f0_view.py [source]
  source: camera index (0) or stream URL (default: IP Webcam via adb forward)
"""
import sys
import threading
import time
from pathlib import Path

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions, vision

MODEL = Path(__file__).parent / "models" / "hand_landmarker.task"
DEFAULT_SOURCE = "http://127.0.0.1:8090/video"
CONNECTIONS = [(c.start, c.end) for c in vision.HandLandmarksConnections.HAND_CONNECTIONS]


class LatestFrame:
    """Reads the stream in a thread and keeps only the newest frame, so we never process a stale buffered one."""

    def __init__(self, source):
        self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            sys.exit(f"cannot open video source: {source}")
        self.frame, self.seq, self.running = None, 0, True
        self.cond = threading.Condition()
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while self.running:
            ok, frame = self.cap.read()
            if not ok:
                self.running = False
                with self.cond:
                    self.cond.notify_all()
                return
            with self.cond:
                self.frame, self.seq = frame, self.seq + 1
                self.cond.notify_all()

    def next(self, last_seq):
        with self.cond:
            self.cond.wait_for(lambda: self.seq != last_seq or not self.running, timeout=2)
            return self.frame, self.seq


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SOURCE
    source = int(arg) if arg.isdigit() else arg
    if not MODEL.exists():
        sys.exit(f"missing model: {MODEL} (see README)")

    landmarker = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODEL)),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=2,
    ))
    stream = LatestFrame(source)
    seq, fps, last = 0, 0.0, time.perf_counter()
    t0 = last

    while True:
        frame, seq_new = stream.next(seq)
        if not stream.running:
            sys.exit("video stream ended")
        if frame is None or seq_new == seq:
            continue
        seq = seq_new

        t = time.perf_counter()
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), int((t - t0) * 1000))
        infer_ms = (time.perf_counter() - t) * 1000

        h, w = frame.shape[:2]
        for hand in result.hand_landmarks:
            pts = [(int(p.x * w), int(p.y * h)) for p in hand]
            for a, b in CONNECTIONS:
                cv2.line(frame, pts[a], pts[b], (0, 255, 0), 2)
            for p in pts:
                cv2.circle(frame, p, 4, (0, 0, 255), -1)

        now = time.perf_counter()
        fps = 0.9 * fps + 0.1 / max(now - last, 1e-6)
        last = now
        cv2.putText(frame, f"{w}x{h}  {fps:4.1f} fps  infer {infer_ms:4.1f} ms  hands {len(result.hand_landmarks)}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        cv2.imshow("hypr-hands F0 (q to quit)", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    stream.running = False


if __name__ == "__main__":
    main()
