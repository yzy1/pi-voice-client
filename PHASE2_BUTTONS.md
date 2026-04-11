================================================================================

&#x20; PHASE 2 — BUTTON SUPPORT FOR ACCESSIBILITY

&#x20; Date: April 2026

================================================================================





1\. PURPOSE

\--------------------------------------------------------------------------------



Phase 2 adds physical button support to the Raspberry Pi voice client. This

allows users who cannot speak to press a button and have a pre-recorded question

sent to the server. The server responds and the answer is spoken through the

speaker, just like voice mode.





2\. HARDWARE ADDED

\--------------------------------------------------------------------------------



Component: Momentary push button (simple press-and-release)

Connection: Two wires, no resistor needed (Pi has internal pull-up resistors)



Button 1 (installed):

&#x20; - Signal wire: Physical Pin 11 (BCM GPIO 17)

&#x20; - Ground wire: Physical Pin 6 (GND)

&#x20; - Question: "Tell me something about Guanyin"



Button 2 (future):

&#x20; - Signal wire: Physical Pin 13 (BCM GPIO 27)

&#x20; - Ground wire: Physical Pin 14 (GND)

&#x20; - Question: "Tell me something about the conservation effort on the Guanyin"



Button 3 (future):

&#x20; - Signal wire: Physical Pin 15 (BCM GPIO 22)

&#x20; - Ground wire: Physical Pin 14 (GND)

&#x20; - Question: "Tell me something about the history of the Guanyin statue"



Note: Buttons 2 and 3 can share the same GND pin (Pin 14). Any GND pin on

the Pi will work (Pin 6, 9, 14, 20, 25, 30, 34, 39).





3\. WIRING DIAGRAM

\--------------------------------------------------------------------------------



Raspberry Pi GPIO Header (looking down at the board, USB ports at bottom)



&#x20;                   Pin 1 \[3.3V]    \[5V]     Pin 2

&#x20;                   Pin 3 \[GPIO2]   \[5V]     Pin 4

&#x20;                   Pin 5 \[GPIO3]   \[GND]    Pin 6  <-- Button 1 GND

&#x20;                   Pin 7 \[GPIO4]   \[GPIO14] Pin 8

&#x20;                   Pin 9 \[GND]     \[GPIO15] Pin 10

Button 1 signal --> Pin 11 \[GPIO17] \[GPIO18] Pin 12

Button 2 signal --> Pin 13 \[GPIO27] \[GND]    Pin 14 <-- Button 2 \& 3 GND

Button 3 signal --> Pin 15 \[GPIO22] \[GPIO23] Pin 16





4\. SOFTWARE CHANGES

\--------------------------------------------------------------------------------



4.1 New Python packages installed:



&#x20; pip install gpiozero lgpio



&#x20; gpiozero: High-level GPIO library for buttons, LEDs, etc.

&#x20; lgpio: Low-level GPIO library required by gpiozero on Raspberry Pi 5.



&#x20; lgpio required additional system packages to build:

&#x20;   sudo apt install -y swig python3-lgpio liblgpio-dev



4.2 Changes to voice\_client.py:



&#x20; - Added imports: threading, gpiozero.Button

&#x20; - Added BUTTON\_QUESTIONS dictionary mapping GPIO pins to questions

&#x20; - Added BUTTON\_BOUNCE\_TIME = 0.3 seconds to prevent double-triggers

&#x20; - Added button\_queue (queue.Queue) for thread-safe button press handling

&#x20; - Added make\_button\_handler() function to create callbacks per button

&#x20; - Added setup\_buttons() function to initialize all configured buttons

&#x20; - Modified main loop to check button\_queue before processing audio

&#x20; - Button presses pause the mic, send question to server, speak answer,

&#x20;   then resume mic — same flow as voice input



4.3 Button configuration in voice\_client.py:



&#x20; BUTTON\_QUESTIONS = {

&#x20;     17: "Tell me something about Guanyin",

&#x20;     # 27: "Tell me something about the conservation effort on the Guanyin",

&#x20;     # 22: "Tell me something about the history of the Guanyin statue",

&#x20; }



&#x20; To add Button 2 and 3, uncomment the lines and set the correct GPIO pin.





5\. BUTTON BOUNCE — EXPLANATION

\--------------------------------------------------------------------------------



When a physical button is pressed, the metal contacts inside vibrate for a

few milliseconds, creating multiple rapid on/off signals. One physical press

can register as 5-15 presses. This is called "button bounce."



The fix is "debounce" — telling the software to ignore signals within a short

time window after the first press. We use bounce\_time=0.3 (300 milliseconds).



This is configured in BUTTON\_BOUNCE\_TIME and passed to gpiozero.Button.





6\. HOW THE BUTTON WORKS (ELECTRICAL)

\--------------------------------------------------------------------------------



&#x20; GPIO 17 (Pin 11) ----\[ Button ]---- GND (Pin 6)



&#x20; Button NOT pressed: GPIO 17 reads HIGH (pulled up internally by Pi)

&#x20; Button PRESSED:     GPIO 17 reads LOW (connected to ground through button)



&#x20; No external resistor is needed because gpiozero enables the Pi's internal

&#x20; pull-up resistor with pull\_up=True.





7\. TESTING THE BUTTON

\--------------------------------------------------------------------------------



A test script was created at \~/voice-client/test\_button.py:



&#x20; from gpiozero import Button

&#x20; from signal import pause



&#x20; button = Button(17, pull\_up=True, bounce\_time=0.3)



&#x20; def on\_press():

&#x20;     print("Button pressed!")



&#x20; def on\_release():

&#x20;     print("Button released!")



&#x20; button.when\_pressed = on\_press

&#x20; button.when\_released = on\_release



&#x20; print("Waiting for button press... (Ctrl+C to exit)")

&#x20; pause()



Run with:

&#x20; cd \~/voice-client

&#x20; source.venv/bin/activate

&#x20; python test\_button.py





8\. ADDING FUTURE BUTTONS — CHECKLIST

\--------------------------------------------------------------------------------



When you have Button 2 and/or Button 3 ready:



&#x20; 1. Wire the button:

&#x20;    - Signal wire to the correct physical pin (Pin 13 for Button 2, Pin 15

&#x20;      for Button 3)

&#x20;    - Ground wire to any GND pin (Pin 14 recommended)



&#x20; 2. Test the button with test\_button.py:

&#x20;    - Change GPIO number in the script (17 to 27 or 22)

&#x20;    - Run and verify it registers presses



&#x20; 3. Update voice\_client.py:

&#x20;    - Uncomment the corresponding line in BUTTON\_QUESTIONS

&#x20;    - Save the file



&#x20; 4. Restart the client:

&#x20;    - python voice\_client.py



&#x20; No other changes are needed. The code automatically initializes all

&#x20; buttons listed in BUTTON\_QUESTIONS.





9\. FULL SYSTEM FLOW WITH BUTTONS

\--------------------------------------------------------------------------------



&#x20; User presses Button 1

&#x20;   --> "Tell me something about Guanyin" placed in button\_queue

&#x20;   --> Mic paused

&#x20;   --> Question sent to Windows server via HTTP POST /agent/reply

&#x20;   --> Server runs RAG + Ollama, returns answer

&#x20;   --> Answer printed to terminal

&#x20;   --> Piper generates speech (mono WAV)

&#x20;   --> ffmpeg converts to stereo 48000Hz

&#x20;   --> aplay plays through USB speaker

&#x20;   --> Mic resumed

&#x20;   --> Waiting for next voice input or button press





================================================================================

&#x20; END OF PHASE 2 DOCUMENTATION

================================================================================

