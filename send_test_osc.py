
# Simple OSC sender to test the visualizer without Max/MSP
# Usage:
#   python send_test_osc.py
# It will send a C-major arpeggio via /schedule messages.

import time
from pythonosc.udp_client import SimpleUDPClient

IP = "127.0.0.1"
PORT = 57120
client = SimpleUDPClient(IP, PORT)

notes = [60, 64, 67, 72, 67, 64, 60]  # C major arpeggio
delay = 0
for n in notes:
    client.send_message("/schedule", [n, int(delay*1000)])
    delay += 0.4

print("Scheduled notes via OSC. Make sure the visualizer is running.")

