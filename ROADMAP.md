# hypr-hands: roadmap

Goal: grab and drag Hyprland windows with hand gestures seen by the phone camera.

Stack: Python 3.12 (uv), OpenCV for capture, MediaPipe Hand Landmarker (21 landmarks per hand,
CPU), Hyprland IPC socket (`movecursor`, `movewindowpixel`, `setfloating`, `clients`).
Camera: Android phone with IP Webcam, MJPEG over USB via `adb forward`. Upgrade path if latency
hurts: `scrcpy --video-source=camera` into v4l2loopback (needs root and a kernel module).

Machine: Intel Raptor Lake iGPU, monitors eDP-1 1920x1080 + HDMI-A-1 3440x1440.

## Phases

- **F0 spike**: feed + hand skeleton + FPS/inference time (`f0_view.py`). Measure phone latency.
- **F1 cursor** (done 2026-10-20): index fingertip drives `movecursor`; calibration (usable camera rectangle to
  screen area), One Euro filter smoothing, both monitors.
- **F2 grab and drag**: thumb-index pinch with hysteresis scaled by hand size grabs the window
  under the cursor (made floating), `movewindowpixel` every frame, release on open hand.
- **F3 robustness**: Hyprland keybind to toggle on/off, lost-hand timeout (release after 300 ms),
  systemd user service.

## Later

- Two-hand pinch to resize.
- Throw a window to the other monitor by hand velocity.
- Swipe to change workspace; fist to send to special workspace or close.
- Use landmark depth (z) to push/pull and restack windows.
- HUD overlay (layer-shell) with the hand skeleton and the grabbed window highlighted.

## Status (2026-10-20)

- mediapipe pinned `<0.11`: 1.1.1 hangs in `HandLandmarker.create_from_options` here; 0.10.35 works.
- Laptop webcam 640x480, no hand in view: inference median 61 ms, max 107 ms (palm detector runs
  every frame when no hand is tracked). To check with a hand in view and with the phone feed.
- Phone: motorola edge 20, Android 13, adb over USB, `adb forward tcp:8090 tcp:8080` (local 8080 is
  taken by ps2-web serve.py). Stream set to 640x480 through IP Webcam's
  `/settings/video_size?set=640x480` (1920x1080 by default cost decode time: 16 fps loop).
- Phone at 640x480: raw stream 60 fps; with inference and no hand in view, loop 23 fps, inference
  median 41 ms. Inference is the bottleneck. To measure with a hand tracked.

## Status (2026-10-20, F1 done)

- `hypr_hands.py pc|phone` drives the cursor while pointing (index up, middle folded).
  - pc: MediaPipe on the laptop over the IP Webcam stream, ~25-30 fps.
  - phone: `phone.html` runs MediaPipe (tasks-vision 0.10.35, GPU delegate) in the phone's Chrome,
    served through `adb reverse tcp:8765`; ~23 fps, 43 ms inference on the phone. The user found it
    better than pc mode. IP Webcam must be stopped (camera is exclusive).
- Smoothing: One Euro (min_cutoff 0.8, beta 8), 60 ms motion prediction, glide thread at monitor
  refresh (tau 25 ms). Active area: 0.6 of frame width, height from monitor aspect (equal gain).
- Hyprland 0.56 dispatchers are Lua: `hl.dsp.cursor.move({x=..,y=..})`; old syntax errors out.
- Open: phone inference on CPU vs GPU delegate not compared; requestVideoFrameCallback not tried.
