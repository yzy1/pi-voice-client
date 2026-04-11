from gpiozero import Button
from signal import pause

button = Button(17, pull_up=True, bounce_time=0.3)

def on_press():
    print("Button pressed!")

def on_release():
    print("Button released!")

button.when_pressed = on_press
button.when_released = on_release

print("Waiting for button press... (Ctrl+C to exit)")
pause()
