import time, random, threading
import pygame
from pygame import Rect
from pythonosc import dispatcher, osc_server

# ========================
# CLEFS (SMuFL)
# ========================

CLEF_TREBLE = "treble"
CLEF_BASS = "bass"
CLEF_ALTO = "alto"
CLEF_TENOR = "tenor"

CLEF_REFERENCE = {
    CLEF_TREBLE: 64,
    CLEF_BASS:   43,
    CLEF_ALTO:   60,
    CLEF_TENOR:  57,
}

CLEF_SYMBOLS = {
    CLEF_TREBLE: "\uE050",
    CLEF_BASS:   "\uE062",
    CLEF_ALTO:   "\uE05C",
    CLEF_TENOR:  "\uE05D",
}

# Correct musical anchor lines
CLEF_ANCHOR_LINE = {
    CLEF_TREBLE: -1,  # G line
    CLEF_BASS:   +1,  # F line
    CLEF_ALTO:    0,  # C line
    CLEF_TENOR:   0,
}

# ========================

WIDTH, HEIGHT = 1200, 360
FPS = 60
STAFF_Y_CENTER = HEIGHT // 2
LINE_SPACING = 12
MARGIN_LEFT = 80
MARGIN_RIGHT = 40

BG_COLOR = (245, 245, 245)
STAFF_COLOR = (30, 30, 30)
NOTE_COLOR = (20, 20, 20)

START_SPEED = 180
SEMITONE_TO_STAFF_STEP = 7/12

# ========================
# STAFF GEOMETRY
# ========================

def get_staff_line(index):
    return STAFF_Y_CENTER + index * LINE_SPACING

def midi_to_staff_y(midi, clef):
    ref_midi = CLEF_REFERENCE[clef]
    ref_y = get_staff_line(+2)

    semis = midi - ref_midi
    steps = semis * SEMITONE_TO_STAFF_STEP
    return ref_y - steps * (LINE_SPACING / 2.0)

# ========================
# NOTE
# ========================

class Note:
    def __init__(self, midi, x, speed, clef):
        self.midi = midi
        self.x = x
        self.speed = speed
        self.clef = clef
        self.y = midi_to_staff_y(midi, clef)
        self.dead = False

        self.rx = 10
        self.ry = 7

    def update(self, dt):
        self.x -= self.speed * dt
        if self.x < -60:
            self.dead = True

    def draw(self, surf):
        # === LEDGER LINES ===

        top_line = get_staff_line(-2)
        bottom_line = get_staff_line(+2)

        ledger_y_positions = []

        # below staff
        if self.y > bottom_line:
            pos = bottom_line + LINE_SPACING
            while self.y > pos - LINE_SPACING / 2:
                ledger_y_positions.append(pos)
                pos += LINE_SPACING

        # above staff
        elif self.y < top_line:
            pos = top_line - LINE_SPACING
            while self.y < pos + LINE_SPACING / 2:
                ledger_y_positions.append(pos)
                pos -= LINE_SPACING

        # draw ledger lines
        for ly in ledger_y_positions:
            pygame.draw.line(
                surf,
                STAFF_COLOR,
                (self.x - 14, ly),
                (self.x + 14, ly),
                2
            )

        # === NOTEHEAD ===

        rect = Rect(int(self.x - self.rx), int(self.y - self.ry),
                    int(self.rx*2), int(self.ry*2))
        pygame.draw.ellipse(surf, NOTE_COLOR, rect)

# ========================
# SPAWNER
# ========================

class Spawner:
    def __init__(self):
        self.notes = []
        self.lock = threading.Lock()

        self.speed = START_SPEED
        self.spawn_x = WIDTH - MARGIN_RIGHT

        self.clef = CLEF_TREBLE

    def spawn(self, midi):
        with self.lock:
            self.notes.append(Note(midi, self.spawn_x, self.speed, self.clef))

    def update(self, dt):
        with self.lock:
            for n in self.notes:
                n.speed = self.speed
                n.update(dt)
            self.notes = [n for n in self.notes if not n.dead]

    def draw(self, surf):
        with self.lock:
            for n in self.notes:
                n.draw(surf)

# ========================
# OSC
# ========================

class OSCBridge(threading.Thread):
    def __init__(self, spawner):
        super().__init__(daemon=True)
        self.spawner = spawner

    def _note(self, addr, *args):
        try:
            midi = int(args[0])
            vel = int(args[1]) if len(args) > 1 else 100
            self.spawner.spawn(midi)
        except Exception as e:
            print("OSC note error:", e)

    def _clef(self, addr, name):
        name = str(name).lower()
        if name in CLEF_REFERENCE:
            self.spawner.clef = name
            print("Clef:", name)

    def run(self):
        disp = dispatcher.Dispatcher()
        disp.map("/note", self._note)
        disp.map("/clef", self._clef)

        server = osc_server.ThreadingOSCUDPServer(("127.0.0.1", 57120), disp)
        print("OSC ready")
        server.serve_forever()

# ========================
# DRAW
# ========================

def draw_staff(surf):
    for i in range(-2, 3):
        y = get_staff_line(i)
        pygame.draw.line(surf, STAFF_COLOR,
                         (MARGIN_LEFT, y),
                         (WIDTH - MARGIN_RIGHT, y), 2)

def draw_clef(surf, clef, font):
    symbol = CLEF_SYMBOLS[clef]

    txt = font.render(symbol, True, STAFF_COLOR)
    rect = txt.get_rect()

    x = MARGIN_LEFT - 55

    # Musical anchor line
    anchor_y = get_staff_line(CLEF_ANCHOR_LINE[clef])

    # 🎯 CRITICAL FIX: Bravura offset per clef
    if clef == CLEF_TREBLE:
        y = anchor_y - rect.height * 0.72
    elif clef == CLEF_BASS:
        y = anchor_y - rect.height * 0.60
    elif clef == CLEF_ALTO:
        y = anchor_y - rect.height * 0.66
    elif clef == CLEF_TENOR:
        y = anchor_y - rect.height * 0.66
    else:
        y = anchor_y - rect.height * 0.5

    surf.blit(txt, (x, y))

# ========================
# MAIN
# ========================

def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()

    # 🔥 SCALE CLEF BASED ON STAFF
    clef_size = int(LINE_SPACING * 6.5)
    font_clef = pygame.font.Font("Bravura.otf", clef_size)

    spawner = Spawner()
    OSCBridge(spawner).start()

    last = time.time()
    running = True

    while running:
        now = time.time()
        dt = now - last
        last = now

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False

        spawner.update(dt)

        screen.fill(BG_COLOR)

        draw_staff(screen)
        draw_clef(screen, spawner.clef, font_clef)
        spawner.draw(screen)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()