# hypr-hands

Move Hyprland windows with your hands, Iron Man style. An Android phone on a tripod films you,
MediaPipe finds the hand landmarks, and the script drives Hyprland through its IPC socket.

## Setup

1. Phone: enable Developer options and **USB debugging**, install **IP Webcam**, tap "Start server".
2. PC: `adb` from Android platform-tools (installed in `~/.local/opt/platform-tools`, linked in `~/.local/bin`).
3. Forward the phone's camera stream over USB:
   `adb forward tcp:8090 tcp:8080` (local 8090: 8080 is taken by ps2-web serve.py)
4. Camera settings (IP Webcam HTTP API; switching camera resets the size, so set it last):
   `for q in ffc=on orientation=upsidedown video_size=640x480; do curl -s "http://127.0.0.1:8090/settings/${q%%=*}?set=${q#*=}"; done`
   (`ffc=on` is the selfie camera; `upsidedown` matches the phone's position on the tripod.)
5. Model (not in git):
   `curl -fLo models/hand_landmarker.task https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task`
6. Run: `uv run f0_view.py` (phone) or `uv run f0_view.py 0` (laptop webcam).

See ROADMAP.md for the plan.
