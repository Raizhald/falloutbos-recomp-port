"""Menu navigation for the harnesses, driven by what the game loads.

The menus (Main_Menu.bik, Character_*.bik) fall back to the intro after a few
idle seconds, so pressing A on a fixed 5 s clock raced that timeout and
sometimes lost for minutes. This presses every 2 s and picks the button from
the last video the log shows: Start while an intro plays (skips it), A
everywhere else -- the default entries (Start New Game, One Player, Normal,
Nadia) are the ones wanted. With easy=True the difficulty menu gets an Up
first (Pansy). It stops 15 s after Carbon's level file appears.
"""
import re

CARBON = 'c1\\CRB_1a\\CRB_1a.ddf'
_BIK = re.compile(r'\\resx\\([A-Za-z0-9_ ]+)\.bik')


class MenuNav:
    def __init__(self, log_path, start=20.0, every=2.0, easy=False):
        self.log_path, self.next, self.every, self.easy = log_path, start, every, easy
        self.pos, self.tail = 0, ''
        self.video = ''
        self.char_presses = 0
        self.carbon_at = None

    def _read(self, elapsed):
        with open(self.log_path, 'rb') as f:
            f.seek(self.pos)
            chunk = f.read().decode('latin-1')
        self.pos += len(chunk)
        text = self.tail + chunk
        for m in _BIK.finditer(text):
            name = m.group(1).lower()
            if name != 'empty':
                if name.startswith('character_') and not self.video.startswith('character_'):
                    self.char_presses = 0
                self.video = name
        if self.carbon_at is None and CARBON in text:
            self.carbon_at = elapsed
        self.tail = chunk[-200:]

    def poll(self, elapsed):
        """Buttons to press now (live-file lines)."""
        self._read(elapsed)
        if self.carbon_at is not None and elapsed >= self.carbon_at + 15:
            return []
        if elapsed < self.next:
            return []
        self.next = elapsed + self.every
        if self.video in ('intro', 'interplay') and self.carbon_at is None:
            return ['start']
        if self.video.startswith('character_') and self.carbon_at is None:
            self.char_presses += 1
            if self.easy and self.char_presses == 2:
                return ['up', 'a']
        return ['a']
