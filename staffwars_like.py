import time, threading
import pygame
from pygame import Rect
from pythonosc import dispatcher, osc_server

# ========================
# CLEFS
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

CLEF_ANCHOR_LINE = {
    CLEF_TREBLE: -1,
    CLEF_BASS:   +1,
    CLEF_ALTO:    0,
    CLEF_TENOR:   0,
}

CLEF_OFFSET = {
    CLEF_TREBLE: (30, -188),
    CLEF_BASS:   (-5, -20),
    CLEF_ALTO:   (-5, -25),
    CLEF_TENOR:  (-5, -25),
}

# ========================

FPS = 60
START_SPEED = 180
SEMITONE_TO_STAFF_STEP = 7/12

BG_COLOR = (245, 245, 245)
STAFF_COLOR = (30, 30, 30)
NOTE_COLOR = (20, 20, 20)

NOWLINE_COLOR = (200, 60, 60)

# 🎯 4 players
PLAYER_COLORS = {
    "red": (220, 60, 60),
    "green": (60, 200, 80),
    "blue": (60, 120, 220),
    "gray": (140, 140, 140),
}

# active player notes
player_notes = {}

# ========================
# GLOBALS
# ========================

WIDTH = 1200
HEIGHT = 600
STAFF_Y_CENTER = HEIGHT // 2
LINE_SPACING = 12
MARGIN_LEFT = 120
MARGIN_RIGHT = 60
NOWLINE_X = 300

# ========================
# GEOMETRY
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

        self.rx = int(LINE_SPACING * 0.8)
        self.ry = int(LINE_SPACING * 0.5)

    def update(self, dt):
        self.x -= self.speed * dt
        if self.x < -60:
            self.dead = True

    def draw(self, surf):
        top = get_staff_line(-2)
        bottom = get_staff_line(+2)

        # ledger lines
        if self.y > bottom:
            pos = bottom + LINE_SPACING
            while self.y > pos - LINE_SPACING/2:
                pygame.draw.line(surf, STAFF_COLOR,
                                 (self.x - 16, pos),
                                 (self.x + 16, pos), 2)
                pos += LINE_SPACING

        elif self.y < top:
            pos = top - LINE_SPACING
            while self.y < pos + LINE_SPACING/2:
                pygame.draw.line(surf, STAFF_COLOR,
                                 (self.x - 16, pos),
                                 (self.x + 16, pos), 2)
                pos -= LINE_SPACING

        rect = Rect(self.x - self.rx, self.y - self.ry,
                    self.rx*2, self.ry*2)
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
            self.spawner.spawn(midi)
        except Exception as e:
            print("OSC note error:", e)

    def _clef(self, addr, name):
        name = str(name).lower()
        if name in CLEF_REFERENCE:
            self.spawner.clef = name

    def _speed(self, addr, *args):
        try:
            val = float(args[0])
            self.spawner.speed = max(10, min(val, 1000))
        except Exception as e:
            print("OSC speed error:", e)

    def _player(self, addr, *args):
        try:
            color = str(args[0]).lower()
            midi = int(args[1])
            vel = int(args[2]) if len(args) > 2 else 0

            key = (color, midi)

            if vel > 0:
                player_notes[key] = True
            else:
                player_notes.pop(key, None)

        except Exception as e:
            print("OSC player error:", e)

    def run(self):
        disp = dispatcher.Dispatcher()
        disp.map("/note", self._note)
        disp.map("/clef", self._clef)
        disp.map("/speed", self._speed)
        disp.map("/player", self._player)

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

    anchor_y = get_staff_line(CLEF_ANCHOR_LINE[clef])
    dx, dy = CLEF_OFFSET[clef]

    surf.blit(txt, (MARGIN_LEFT - 50 + dx, anchor_y + dy))

def draw_nowline(surf):
    pygame.draw.line(surf, NOWLINE_COLOR,
                     (NOWLINE_X, 0),
                     (NOWLINE_X, HEIGHT), 3)

def draw_player_notes(surf, clef):
    for (color_name, midi) in player_notes.keys():
        color = PLAYER_COLORS.get(color_name, (255, 0, 0))
        y = midi_to_staff_y(midi, clef)

        # 🎯 slightly smaller → matches noteheads better
        radius = int(LINE_SPACING * 0.9)

        pygame.draw.circle(
            surf,
            color,
            (int(NOWLINE_X), int(y)),
            radius,
            3
        )

# ========================
# MAIN
# ========================

def main():
    global WIDTH, HEIGHT, STAFF_Y_CENTER, LINE_SPACING, NOWLINE_X

    pygame.init()

    info = pygame.display.Info()
    WIDTH, HEIGHT = info.current_w, info.current_h

    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
    pygame.mouse.set_visible(False)

    STAFF_Y_CENTER = HEIGHT // 2
    LINE_SPACING = int(HEIGHT * 0.02)
    NOWLINE_X = int(WIDTH * 0.25)

    clock = pygame.time.Clock()

    clef_size = int(LINE_SPACING * 6)
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
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False

        spawner.update(dt)

        screen.fill(BG_COLOR)

        draw_staff(screen)
        draw_nowline(screen)
        draw_clef(screen, spawner.clef, font_clef)
        draw_player_notes(screen, spawner.clef)
        spawner.draw(screen)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()