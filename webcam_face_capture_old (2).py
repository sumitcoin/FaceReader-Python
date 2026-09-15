"""Automatic webcam face capture with an alignment circle.

Place one face inside the circle and hold still. The program saves the face
automatically after it remains correctly aligned for a short time.

Controls: Q or Esc = quit, R = reset after a capture.
"""

import csv
import math
import time
from datetime import datetime
from pathlib import Path

import cv2


OUTPUT_DIR = Path("face_data")
CSV_FILE = OUTPUT_DIR / "faces.csv"
STABLE_FRAMES_REQUIRED = 20
CAPTURE_COOLDOWN_SECONDS = 2.0
FACE_MARGIN = 0.20


def prepare_output():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not CSV_FILE.exists():
        with CSV_FILE.open("w", newline="", encoding="utf-8") as file:
            csv.writer(file).writerow(
                ["filename", "captured_at", "x", "y", "width", "height"]
            )


def face_is_aligned(face, circle_center, circle_radius):
    x, y, width, height = [int(value) for value in face]
    face_center = (x + width // 2, y + height // 2)
    center_distance = math.dist(face_center, circle_center)

    centered = center_distance < circle_radius * 0.22
    correct_size = circle_radius * 0.85 <= height <= circle_radius * 1.65
    inside_circle = (
        center_distance + math.hypot(width / 2, height / 2)
        < circle_radius * 1.08
    )
    return centered and correct_size and inside_circle


def save_face(frame, face):
    x, y, width, height = [int(value) for value in face]
    frame_height, frame_width = frame.shape[:2]
    margin_x, margin_y = int(width * FACE_MARGIN), int(height * FACE_MARGIN)
    left, top = max(0, x - margin_x), max(0, y - margin_y)
    right = min(frame_width, x + width + margin_x)
    bottom = min(frame_height, y + height + margin_y)

    captured_at = datetime.now()
    filename = f"face_{captured_at.strftime('%Y%m%d_%H%M%S_%f')}.jpg"
    crop = frame[top:bottom, left:right]
    if crop.size == 0 or not cv2.imwrite(str(OUTPUT_DIR / filename), crop):
        raise RuntimeError("The face image could not be saved.")

    with CSV_FILE.open("a", newline="", encoding="utf-8") as file:
        csv.writer(file).writerow(
            [filename, captured_at.isoformat(timespec="milliseconds"),
             x, y, width, height]
        )
    return filename


def draw_tick(frame, center, size=55):
    color = (0, 220, 0)
    start = (center[0] - size, center[1])
    middle = (center[0] - size // 5, center[1] + size // 2)
    end = (center[0] + size, center[1] - size)
    cv2.line(frame, start, middle, color, 14, cv2.LINE_AA)
    cv2.line(frame, middle, end, color, 14, cv2.LINE_AA)


def put_centered_text(frame, text, y, color, scale=0.75, thickness=2):
    size = cv2.getTextSize(
        text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness
    )[0]
    x = max(10, (frame.shape[1] - size[0]) // 2)
    cv2.putText(
        frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale,
        color, thickness, cv2.LINE_AA
    )


def main():
    prepare_output()

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    detector = cv2.CascadeClassifier(cascade_path)
    if detector.empty():
        raise RuntimeError("OpenCV face detector could not be loaded.")

    camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    if not camera.isOpened():
        camera.release()
        camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        raise RuntimeError("Webcam could not be opened.")

    stable_frames = 0
    captured = False
    captured_at_monotonic = 0.0
    last_filename = ""

    try:
        while True:
            success, raw_frame = camera.read()
            if not success:
                raise RuntimeError("Could not read a frame from the webcam.")

            raw_frame = cv2.flip(raw_frame, 1)
            display = raw_frame.copy()
            frame_height, frame_width = display.shape[:2]
            circle_center = (frame_width // 2, frame_height // 2)
            circle_radius = int(min(frame_width, frame_height) * 0.33)

            gray = cv2.cvtColor(raw_frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)
            faces = detector.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=6, minSize=(100, 100)
            )

            aligned_face = None
            if (
                len(faces) == 1
                and face_is_aligned(faces[0], circle_center, circle_radius)
            ):
                aligned_face = faces[0]

            if captured:
                circle_color = (0, 220, 0)
                draw_tick(display, circle_center)
                put_centered_text(
                    display, "FACE CAPTURED", 55, circle_color, 0.9, 3
                )
                if (
                    time.monotonic() - captured_at_monotonic
                    >= CAPTURE_COOLDOWN_SECONDS
                    and aligned_face is None
                ):
                    captured = False
                    stable_frames = 0
            else:
                if len(faces) > 1:
                    stable_frames = 0
                    circle_color = (0, 0, 255)
                    message = "Only one person should be visible"
                elif aligned_face is None:
                    stable_frames = max(0, stable_frames - 2)
                    circle_color = (0, 200, 255)
                    message = "Place your face inside the circle"
                else:
                    stable_frames += 1
                    circle_color = (0, 220, 0)
                    progress = min(
                        100,
                        stable_frames * 100 // STABLE_FRAMES_REQUIRED,
                    )
                    message = f"Hold still... {progress}%"

                    if stable_frames >= STABLE_FRAMES_REQUIRED:
                        last_filename = save_face(raw_frame, aligned_face)
                        captured = True
                        captured_at_monotonic = time.monotonic()
                        stable_frames = 0
                        draw_tick(display, circle_center)
                        message = "FACE CAPTURED"

                put_centered_text(
                    display, message, 55, circle_color, 0.8, 2
                )

            cv2.circle(
                display, circle_center, circle_radius,
                circle_color, 4, cv2.LINE_AA
            )
            footer = (
                f"Saved: {last_filename}" if last_filename
                else "Q: Quit    R: Reset"
            )
            put_centered_text(
                display, footer, frame_height - 30,
                (255, 255, 255), 0.55, 1
            )
            cv2.imshow("Automatic Face Capture", display)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("r"):
                captured = False
                stable_frames = 0
    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
