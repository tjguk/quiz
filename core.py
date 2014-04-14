import collections
import json
import logging
import Queue

import pygame

#
# NB Queue.Queue is an old-style class; you can't use super
#
class IPCQueue(Queue.Queue):

    def put(self, action, *args):
        Queue.Queue.put(self, (action, args))

    def __iter__(self):
        while True:
            try:
                yield self.get_nowait()
            except Queue.Empty:
                break

log = logging.getLogger("Quiz")
log.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s %(module)s %(levelname)s - %(message)s"))
log.addHandler(handler)
log.superdebug = log.debug

class Color(pygame.Color):

    light = pygame.Color("white")
    dark = pygame.Color("black")

    def is_dark(self):
        h, s, l, a = self.hsla
        return l < 72.0

class Rect(pygame.Rect):
    pass

class Font(pygame.font.Font):

    def __init__(self, *args, **kwargs):
        pygame.font.Font.__init__(self, *args, **kwargs)

    def render(self, text, colour):
        return pygame.font.Font.render(self, text, False, colour)

    def render_hollow(self, message, colour):
        notcolor = [c^0xFF for c in colour]
        base = self.render(message, 0, colour, notcolor)
        size = base.get_width() + 2, base.get_height() + 2
        img = pygame.Surface(size, 16)
        img.fill(notcolor)
        base.set_colorkey(0)
        img.blit(base, (0, 0))
        img.blit(base, (2, 0))
        img.blit(base, (0, 2))
        img.blit(base, (2, 2))
        base.set_colorkey(0)
        base.set_palette_at(1, notcolor)
        img.blit(base, (1, 1))
        img.set_colorkey(notcolor)
        return img

    def render_outlined(self, message, colour, outline_colour):
        base = self.render(message, 0, colour)
        outline = self.render_hollow(message, outline_colour)
        img = pygame.Surface(outline.get_size(), 16)
        img.blit(base, (1, 1))
        img.blit(outline, (0, 0))
        img.set_colorkey(0)
        return img

timer_event_type = pygame.USEREVENT + 1
scores_changed_event = pygame.event.Event(pygame.USEREVENT + 2)
