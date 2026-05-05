import pyautogui
import time

print("Move mouse. Press Ctrl+C to stop.\n")

try:
    while True:
        x, y = pyautogui.position()
        print(f"\rX:{x} Y:{y}\n", end="")
        time.sleep(0.05)
except KeyboardInterrupt:
    print("\nStopped")