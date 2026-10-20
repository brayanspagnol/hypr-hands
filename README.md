# hypr-hands

Move Hyprland windows with your hands, Iron Man style. An Android phone on a tripod films you,
MediaPipe finds the hand landmarks, and the script drives Hyprland through its IPC socket.

## Setup

1. Phone: enable Developer options and **USB debugging**, install **IP Webcam**, tap "Start server".
2. PC: `adb` from Android platform-tools (installed in `~/.local/opt/platform-tools`, linked in `~/.local/bin`).
3. Forward the phone's camera stream over USB:
   `adb forward tcp:8080 tcp:8080`
4. Model (not in git):
   `curl -fLo models/hand_landmarker.task https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task`
5. Run: `uv run f0_view.py` (phone) or `uv run f0_view.py 0` (laptop webcam).

See ROADMAP.md for the plan.
