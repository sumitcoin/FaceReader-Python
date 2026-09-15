"""Detect faces from a webcam and save face crops with basic metadata.

Controls:
    S - save every face currently detected
    Q - quit
"""

import csv
from datetime import datetime
from pathlib import Path

import cv2


OUTPUT_DIR = Path("face_data")
CSV_FILE = OUTPUT_DIR / "faces.csv"


def prepare_output() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not CSV_FILE.exists():
        with CSV_FILE.open("w", newline="", encoding="utf-8") as file:
            csv.writer(file).writerow(
                ["filename", "captured_at", "x", "y", "width", "height"]
            )


def save_faces(frame, faces) -> int:
    captured_at = datetime.now()
    timestamp = captured_at.strftime("%Y%m%d_%H%M%S_%f")
    rows = []

    for index, (x, y, width, height) in enumerate(faces, start=1):
        face_image = frame[y : y + height, x : x + width]
        filename = f"face_{timestamp}_{index}.jpg"
        cv2.imwrite(str(OUTPUT_DIR / filename), face_image)
        rows.append(
            [
                filename,
                captured_at.isoformat(timespec="milliseconds"),
                int(x),
                int(y),
                int(width),
                int(height),
            ]
        )

    if rows:
        with CSV_FILE.open("a", newline="", encoding="utf-8") as file:
            csv.writer(file).writerows(rows)

    return len(rows)


def main() -> None:
    prepare_output()

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    detector = cv2.CascadeClassifier(cascade_path)
    if detector.empty():
        raise RuntimeError("OpenCV face detector could not be loaded.")

    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        raise RuntimeError("Webcam could not be opened.")

    status = "Press S to save faces | Q to quit"

    try:
        while True:
            success, frame = camera.read()
            if not success:
                raise RuntimeError("Could not read a frame from the webcam.")

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = detector.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(80, 80),
            )

            for x, y, width, height in faces:
                cv2.rectangle(
                    frame,
                    (x, y),
                    (x + width, y + height),
                    (0, 255, 0),
                    2,
                )

            cv2.putText(
                frame,
                f"Faces: {len(faces)} | {status}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 255, 0),
                2,
            )
            cv2.imshow("Webcam Face Capture", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("s"):
                saved = save_faces(frame, faces)
                status = f"Saved {saved} face(s)" if saved else "No face detected"
            elif key == ord("q"):
                break
    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
