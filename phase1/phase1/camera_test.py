"""
===================================================================
SignConnect Live - Phase 1: Machine-Learning ISL Sign Recognition (v2)
===================================================================

Pipeline:
Webcam → MediaPipe 21 Landmarks → 83-Feature Scale Normalization → Trained MLP v2 Model → Anti-Flicker Stabilization → ISL Text & Confidence HUD
"""

from collections import deque, Counter
import cv2
import mediapipe as mp

try:
    from phase1.gesture_recognizer import classify_gesture
except ImportError:
    from gesture_recognizer import classify_gesture


def draw_hud(frame, hand_detected_count, predicted_sign, confidence):
    """
    Draws a clean, professional visual HUD overlay on the live webcam frame.
    """
    height, width, _ = frame.shape

    # 1. Top Header Banner
    cv2.rectangle(frame, (0, 0), (width, 50), (20, 20, 20), -1)
    cv2.putText(frame, "SIGNCONNECT LIVE - PHASE 1 (ISL SIGN -> TEXT)", (15, 33),
                cv2.FONT_HERSHEY_SIMPLEX, 0.70, (0, 255, 255), 2, cv2.LINE_AA)

    # 2. Hand Detection Status Badge
    if hand_detected_count > 0:
        status_text = f"Status: Hand Detected ({hand_detected_count})"
        status_color = (0, 255, 0)
    else:
        status_text = "Status: No Hand Detected"
        status_color = (0, 0, 255)

    cv2.putText(frame, status_text, (width - 290, 33),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, status_color, 2, cv2.LINE_AA)

    # 3. Bottom ISL Prediction Banner Card
    card_top = height - 90
    cv2.rectangle(frame, (0, card_top), (width, height), (25, 25, 25), -1)
    cv2.line(frame, (0, card_top), (width, card_top), (0, 255, 255), 2)

    cv2.putText(frame, "PREDICTED ISL SIGN:", (20, card_top + 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)

    # Display Prediction Text
    sign_color = (0, 255, 0) if "LOW CONFIDENCE" not in predicted_sign and predicted_sign not in ["NO HAND DETECTED", "Detecting..."] else (0, 165, 255)
    cv2.putText(frame, predicted_sign, (20, card_top + 70),
                cv2.FONT_HERSHEY_SIMPLEX, 1.1, sign_color, 3, cv2.LINE_AA)

    # Display Model Confidence Score
    if hand_detected_count > 0 and confidence > 0:
        cv2.putText(frame, f"Confidence: {confidence:.1f}%", (width - 230, card_top + 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2, cv2.LINE_AA)

    # Exit Instruction
    cv2.putText(frame, "Press 'Q' to Quit", (width - 160, height - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1, cv2.LINE_AA)


def main():
    # Step 1: Initialize MediaPipe Hands
    mp_hands = mp.solutions.hands
    mp_drawing = mp.solutions.drawing_utils
    mp_drawing_styles = mp.solutions.drawing_styles

    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.6
    )

    # Step 2: Open webcam (try DirectShow and indices 0, 1, 2)
    cap = None
    for idx in [0, 1, 2]:
        for backend in [cv2.CAP_DSHOW, cv2.CAP_ANY]:
            temp_cap = cv2.VideoCapture(idx, backend)
            if temp_cap.isOpened():
                ret, _ = temp_cap.read()
                if ret:
                    cap = temp_cap
                    print(f"Webcam opened successfully on index {idx} with backend {backend}.")
                    break
            temp_cap.release()
        if cap is not None:
            break

    if cap is None or not cap.isOpened():
        print("Error: Could not open webcam. Verify camera connection.")
        # Render fallback HUD window explaining no camera was found
        import numpy as np
        err_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(err_frame, "SIGNCONNECT LIVE - PHASE 1", (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 255), 2)
        cv2.putText(err_frame, "Status: No Working Webcam Detected", (30, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)
        cv2.putText(err_frame, "Please connect a webcam or check Windows privacy", (30, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.putText(err_frame, "settings to allow desktop camera access.", (30, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.putText(err_frame, "Press 'Q' to Close this window.", (30, 320), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)
        while True:
            cv2.imshow("SignConnect Live - Phase 1 ISL", err_frame)
            k = cv2.waitKey(30) & 0xFF
            if k == ord('q') or k == ord('Q') or cv2.getWindowProperty("SignConnect Live - Phase 1 ISL", cv2.WND_PROP_VISIBLE) < 1:
                break
        cv2.destroyAllWindows()
        hands.close()
        return

    print("==================================================")
    print("  SignConnect Live - Phase 1 ISL Application (v2) ")
    print("==================================================")
    print("Pipeline: Webcam -> MediaPipe -> 83-Feature Scale Normalization -> Regularized MLP v2 -> Stabilization -> UI")
    print("Press 'Q' in the window to quit.\n")

    # Anti-flicker stabilization buffer (7 frames majority voting)
    STABILIZATION_WINDOW_SIZE = 7
    gesture_history = deque(maxlen=STABILIZATION_WINDOW_SIZE)
    confidence_history = deque(maxlen=STABILIZATION_WINDOW_SIZE)

    current_stable_sign = "NO HAND DETECTED"
    current_confidence = 0.0
    last_logged_sign = None

    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                print("Error: Failed to read frame from webcam.")
                break

            # Mirror frame
            frame = cv2.flip(frame, 1)

            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Process frame with MediaPipe
            results = hands.process(rgb_frame)

            hand_count = 0
            frame_gesture = "NO HAND DETECTED"
            frame_conf = 0.0

            if results.multi_hand_landmarks:
                hand_count = len(results.multi_hand_landmarks)
                primary_hand = results.multi_hand_landmarks[0]

                # ML Inference with confidence calculation (v2 model)
                frame_gesture, frame_conf = classify_gesture(primary_hand)

                # Draw 21 landmarks on camera frame
                for hand_landmarks in results.multi_hand_landmarks:
                    mp_drawing.draw_landmarks(
                        frame,
                        hand_landmarks,
                        mp_hands.HAND_CONNECTIONS,
                        mp_drawing_styles.get_default_hand_landmarks_style(),
                        mp_drawing_styles.get_default_hand_connections_style()
                    )

            # Stabilization buffer logic
            gesture_history.append(frame_gesture)
            confidence_history.append(frame_conf)

            counter = Counter(gesture_history)
            most_common_gesture, count = counter.most_common(1)[0]

            if count >= 4:
                current_stable_sign = most_common_gesture
                current_confidence = sum(confidence_history) / len(confidence_history)
                if current_stable_sign != last_logged_sign and current_stable_sign not in ['NO HAND DETECTED', 'Detecting...']:
                    print(f'PREDICTED: {current_stable_sign} ({current_confidence:.1f}%)', flush=True)
                    last_logged_sign = current_stable_sign
            elif not gesture_history:
                current_stable_sign = "Detecting..."
                current_confidence = 0.0

            # Draw HUD visual overlay
            draw_hud(frame, hand_count, current_stable_sign, current_confidence)

            # Render frame
            cv2.imshow("SignConnect Live - Phase 1 ISL", frame)

            # Exit on 'Q'
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == ord('Q'):
                print("Exiting Phase 1 ISL application...")
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()
        hands.close()
        print("Webcam and MediaPipe resources released cleanly.")


if __name__ == "__main__":
    main()
