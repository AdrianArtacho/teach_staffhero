
import time, random, threading
import pygame
from pygame import Rect
from pythonosc import dispatcher, osc_server

USE_MIDI_IN = False
try:
    if USE_MIDI_IN:
        import mido
        import rtmidi  # noqa: F401
except Exception:
    USE_MIDI_IN = False

WIDTH, HEIGHT = 1200, 360
FPS = 60
STAFF_Y_CENTER = HEIGHT // 2
LINE_SPACING = 12
MARGIN_LEFT = 40
MARGIN_RIGHT = 40
BG_COLOR = (245, 245, 245)
STAFF_COLOR = (30, 30, 30)
NOTE_COLOR = (20, 20, 20)
LEDGER_COLOR = (50, 50, 50)
INFO_COLOR = (60, 60, 80)
ACCIDENTAL_COLOR = (20, 20, 20)

START_SPEED = 180
RAPID_RANDOM_INTERVAL = 0.65
RANDOM_PITCH_MIN = 48
RANDOM_PITCH_MAX = 81

NOTE_NAMES_SHARP = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
def midi_to_name(m):
    n = NOTE_NAMES_SHARP[m % 12]
    o = (m // 12) - 1
    return f"{n}{o}"

REF_MIDI = 64
REF_Y = STAFF_Y_CENTER + 2 * LINE_SPACING
SEMITONE_TO_STAFF_STEP = 7/12

def midi_to_staff_y(midi):
    semis = midi - REF_MIDI
    steps = semis * SEMITONE_TO_STAFF_STEP
    return REF_Y - steps * (LINE_SPACING / 2.0)

def need_ledger(y):
    top_line_y = STAFF_Y_CENTER - 2 * LINE_SPACING
    bottom_line_y = STAFF_Y_CENTER + 2 * LINE_SPACING
    return y < top_line_y or y > bottom_line_y

def ledger_positions_for_y(y):
    top_line_y = STAFF_Y_CENTER - 2 * LINE_SPACING
    bottom_line_y = STAFF_Y_CENTER + 2 * LINE_SPACING
    ledgers = []
    if y < top_line_y:
        pos = top_line_y - LINE_SPACING
        while y < pos + LINE_SPACING / 2:
            ledgers.append(pos)
            pos -= LINE_SPACING
    elif y > bottom_line_y:
        pos = bottom_line_y + LINE_SPACING
        while y > pos - LINE_SPACING / 2:
            ledgers.append(pos)
            pos += LINE_SPACING
    return ledgers

def is_sharp(midi):
    return midi % 12 in {1,3,6,8,10}

class Note:
    def __init__(self, midi, x, speed, created=None, vel=100):
        self.midi = midi
        self.x = x
        self.speed = speed
        self.y = midi_to_staff_y(midi)
        self.vel = vel
        self.created = created if created is not None else time.time()
        self.radius_x = 10
        self.radius_y = 7
        self.dead = False

    def update(self, dt):
        self.x -= self.speed * dt
        if self.x < -60:
            self.dead = True

    def draw(self, surf, font):
        if need_ledger(self.y):
            for ly in ledger_positions_for_y(self.y):
                pygame.draw.line(surf, LEDGER_COLOR, (self.x - 18, ly), (self.x + 18, ly), 2)
        rect = Rect(int(self.x - self.radius_x), int(self.y - self.radius_y),
                    int(self.radius_x*2), int(self.radius_y*2))
        pygame.draw.ellipse(surf, NOTE_COLOR, rect)
        if self.y >= STAFF_Y_CENTER:
            pygame.draw.line(surf, NOTE_COLOR, (self.x + self.radius_x, self.y),
                             (self.x + self.radius_x, self.y - 32), 2)
        else:
            pygame.draw.line(surf, NOTE_COLOR, (self.x - self.radius_x, self.y),
                             (self.x - self.radius_x, self.y + 32), 2)
        if is_sharp(self.midi):
            txt = font.render("#", True, ACCIDENTAL_COLOR)
            surf.blit(txt, (self.x - 26, self.y - 16))

class Spawner:
    def __init__(self):
        self.notes = []
        self.lock = threading.Lock()
        self.speed = START_SPEED
        self.random_mode = False
        self.random_interval = RAPID_RANDOM_INTERVAL
        self.next_random_time = time.time() + self.random_interval
        self.spawn_x = WIDTH - MARGIN_RIGHT
        self.scheduled = []

    def spawn(self, midi, vel=100):
        with self.lock:
            self.notes.append(Note(midi, self.spawn_x, self.speed, vel=vel))

    def schedule(self, midi, delay_s, vel=100):
        when = time.time() + delay_s
        with self.lock:
            self.scheduled.append((when, midi, vel))

    def update(self, dt):
        t = time.time()
        with self.lock:
            due = [ev for ev in self.scheduled if ev[0] <= t]
            self.scheduled = [ev for ev in self.scheduled if ev[0] > t]
        for _, midi, vel in due:
            self.spawn(midi, vel)
        if self.random_mode and t >= self.next_random_time:
            midi = random.randint(RANDOM_PITCH_MIN, RANDOM_PITCH_MAX)
            self.spawn(midi, 100)
            self.next_random_time = t + self.random_interval
        with self.lock:
            for n in self.notes:
                n.speed = self.speed
                n.update(dt)
            self.notes = [n for n in self.notes if not n.dead]

    def draw(self, surf, font_small):
        with self.lock:
            for n in self.notes:
                n.draw(surf, font_small)

class OSCBridge(threading.Thread):
    def __init__(self, spawner, ip="127.0.0.1", port=57120):
        super().__init__(daemon=True)
        self.spawner = spawner
        self.ip = ip
        self.port = port
        self._server = None

    def _handle_note(self, addr, midi, vel):
        try:
            m = int(midi)
            v = int(vel)
            self.spawner.spawn(m, v)
        except Exception as e:
            print("OSC /note error:", e)

    def _handle_schedule(self, addr, midi, delay_ms):
        try:
            m = int(midi)
            d = int(delay_ms) / 1000.0
            self.spawner.schedule(m, d, 100)
        except Exception as e:
            print("OSC /schedule error:", e)

    def run(self):
        disp = dispatcher.Dispatcher()
        disp.map("/note", self._handle_note)
        disp.map("/schedule", self._handle_schedule)
        try:
            self._server = osc_server.ThreadingOSCUDPServer((self.ip, self.port), disp)
            print(f"[OSC] Listening on {self.ip}:{self.port}")
            self._server.serve_forever()
        except Exception as e:
            print("OSC server failed to start:", e)

def draw_staff(surf):
    for i in range(-2, 3):
        y = STAFF_Y_CENTER + i * LINE_SPACING
        pygame.draw.line(surf, STAFF_COLOR, (MARGIN_LEFT, y), (WIDTH - MARGIN_RIGHT, y), 2)

def draw_info(surf, font, spawner):
    text = f"Speed: {int(spawner.speed)} px/s   Random:{'ON' if spawner.random_mode else 'OFF'}  Interval:{spawner.random_interval:.2f}s"
    t_surf = font.render(text, True, INFO_COLOR)
    surf.blit(t_surf, (16, 10))

def main():
    pygame.init()
    pygame.display.set_caption("StaffWars-like (controllable)")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    font_small = pygame.font.SysFont("Arial", 20)
    font_info = pygame.font.SysFont("Arial", 16)

    spawner = Spawner()
    osc = OSCBridge(spawner); osc.start()

    running = True
    last_time = time.time()
    while running:
        now = time.time()
        dt = now - last_time
        last_time = now

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif event.key == pygame.K_SPACE:
                    m = random.randint(RANDOM_PITCH_MIN, RANDOM_PITCH_MAX)
                    spawner.spawn(m, 100)
                elif event.key == pygame.K_r:
                    spawner.random_mode = not spawner.random_mode
                    spawner.next_random_time = time.time() + spawner.random_interval
                elif event.key == pygame.K_UP:
                    spawner.speed = min(spawner.speed + 20, 600)
                elif event.key == pygame.K_DOWN:
                    spawner.speed = max(spawner.speed - 20, 40)
                elif event.key == pygame.K_RIGHT:
                    spawner.random_interval = max(spawner.random_interval - 0.05, 0.10)
                elif event.key == pygame.K_LEFT:
                    spawner.random_interval = min(spawner.random_interval + 0.05, 3.0)

        spawner.update(dt)

        screen.fill(BG_COLOR)
        draw_staff(screen)
        spawner.draw(screen, font_small)
        draw_info(screen, font_info, spawner)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()
