import time, random, threading
import pygame
from pygame import Rect
from pythonosc import dispatcher, osc_server

# ========================
# CLEF SYSTEM
# ========================

CLEF_TREBLE = "treble"
CLEF_BASS = "bass"
CLEF_ALTO = "alto"
CLEF_TENOR = "tenor"

CLEF_REFERENCE = {
    CLEF_TREBLE: 64,  # E4
    CLEF_BASS:   43,  # G2
    CLEF_ALTO:   60,  # C4
    CLEF_TENOR:  57,  # A3
}

# ========================

USE_MIDI_IN = False

WIDTH, HEIGHT = 1200, 360
FPS = 60
STAFF_Y_CENTER = HEIGHT // 2
LINE_SPACING = 12
MARGIN_LEFT = 60
MARGIN_RIGHT = 40

BG_COLOR = (245, 245, 245)
STAFF_COLOR = (30, 30, 30)
NOTE_COLOR = (20, 20, 20)
LEDGER_COLOR = (50, 50, 50)
INFO_COLOR = (60, 60, 80)
ACCIDENTAL_COLOR = (20, 20, 20)

START_SPEED = 180

RANDOM_PITCH_MIN = 48
RANDOM_PITCH_MAX = 81

NOTE_NAMES_SHARP = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]

SEMITONE_TO_STAFF_STEP = 7/12


# ========================
# STAFF MAPPING (CLEF AWARE)
# ========================

def midi_to_staff_y(midi, clef):
    ref_midi = CLEF_REFERENCE[clef]
    ref_y = STAFF_Y_CENTER + 2 * LINE_SPACING

    semis = midi - ref_midi
    steps = semis * SEMITONE_TO_STAFF_STEP
    return ref_y - steps * (LINE_SPACING / 2.0)


# ========================

def need_ledger(y):
    top = STAFF_Y_CENTER - 2 * LINE_SPACING
    bottom = STAFF_Y_CENTER + 2 * LINE_SPACING
    return y < top or y > bottom

def ledger_positions_for_y(y):
    top = STAFF_Y_CENTER - 2 * LINE_SPACING
    bottom = STAFF_Y_CENTER + 2 * LINE_SPACING
    ledgers = []

    if y < top:
        pos = top - LINE_SPACING
        while y < pos + LINE_SPACING / 2:
            ledgers.append(pos)
            pos -= LINE_SPACING
    elif y > bottom:
        pos = bottom + LINE_SPACING
        while y > pos - LINE_SPACING / 2:
            ledgers.append(pos)
            pos += LINE_SPACING

    return ledgers

def is_sharp(midi):
    return midi % 12 in {1,3,6,8,10}


# ========================
# NOTE
# ========================

class Note:
    def __init__(self, midi, x, speed, clef, vel=100):
        self.midi = midi
        self.x = x
        self.speed = speed
        self.clef = clef
        self.vel = vel
        self.y = midi_to_staff_y(midi, clef)
        self.dead = False

        self.radius_x = 10
        self.radius_y = 7

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

        # stem
        if self.y >= STAFF_Y_CENTER:
            pygame.draw.line(surf, NOTE_COLOR,
                             (self.x + self.radius_x, self.y),
                             (self.x + self.radius_x, self.y - 32), 2)
        else:
            pygame.draw.line(surf, NOTE_COLOR,
                             (self.x - self.radius_x, self.y),
                             (self.x - self.radius_x, self.y + 32), 2)

        # accidental
        if is_sharp(self.midi):
            txt = font.render("#", True, ACCIDENTAL_COLOR)
            surf.blit(txt, (self.x - 26, self.y - 16))


# ========================
# SPAWNER
# ========================

class Spawner:
    def __init__(self):
        self.notes = []
        self.lock = threading.Lock()

        self.speed = START_SPEED
        self.spawn_x = WIDTH - MARGIN_RIGHT

        self.clef = CLEF_TREBLE  # default

    def spawn(self, midi, vel=100):
        with self.lock:
            self.notes.append(Note(midi, self.spawn_x, self.speed, self.clef, vel))

    def update(self, dt):
        with self.lock:
            for n in self.notes:
                n.speed = self.speed
                n.update(dt)
            self.notes = [n for n in self.notes if not n.dead]

    def draw(self, surf, font):
        with self.lock:
            for n in self.notes:
                n.draw(surf, font)


# ========================
# OSC
# ========================

class OSCBridge(threading.Thread):
    def __init__(self, spawner, ip="127.0.0.1", port=57120):
        super().__init__(daemon=True)
        self.spawner = spawner
        self.ip = ip
        self.port = port

    def _handle_note(self, addr, midi, vel):
        self.spawner.spawn(int(midi), int(vel))

    def _handle_clef(self, addr, clef_name):
        clef = str(clef_name).lower()
        if clef in CLEF_REFERENCE:
            self.spawner.clef = clef
            print("[OSC] Clef →", clef)

    def run(self):
        disp = dispatcher.Dispatcher()
        disp.map("/note", self._handle_note)
        disp.map("/clef", self._handle_clef)

        server = osc_server.ThreadingOSCUDPServer((self.ip, self.port), disp)
        print(f"[OSC] Listening on {self.ip}:{self.port}")
        server.serve_forever()


# ========================
# DRAW
# ========================

def draw_staff(surf):
    for i in range(-2, 3):
        y = STAFF_Y_CENTER + i * LINE_SPACING
        pygame.draw.line(surf, STAFF_COLOR,
                         (MARGIN_LEFT, y),
                         (WIDTH - MARGIN_RIGHT, y), 2)


def draw_clef(surf, clef, font):
    x = MARGIN_LEFT - 40
    y = STAFF_Y_CENTER - 40

    symbols = {
        CLEF_TREBLE: "𝄞",
        CLEF_BASS:   "𝄢",
        CLEF_ALTO:   "𝄡",
        CLEF_TENOR:  "𝄡",
    }

    txt = font.render(symbols.get(clef, "?"), True, STAFF_COLOR)
    surf.blit(txt, (x, y))


def draw_info(surf, font, spawner):
    text = f"Clef: {spawner.clef}   Speed: {int(spawner.speed)}"
    surf.blit(font.render(text, True, INFO_COLOR), (16, 10))


# ========================
# MAIN
# ========================

def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()

    font_small = pygame.font.SysFont("Arial", 20)
    font_info = pygame.font.SysFont("Arial", 16)
    font_clef = pygame.font.SysFont("Arial", 48)

    spawner = Spawner()
    OSCBridge(spawner).start()

    running = True
    last = time.time()

    while running:
        now = time.time()
        dt = now - last
        last = now

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        spawner.update(dt)

        screen.fill(BG_COLOR)

        draw_staff(screen)
        draw_clef(screen, spawner.clef, font_clef)
        spawner.draw(screen, font_small)
        draw_info(screen, font_info, spawner)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()