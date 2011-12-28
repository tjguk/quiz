import math

import pygame
from PyQt4 import QtCore, QtGui

import core
import screen

class Blank (screen.Screen):

  name = "Blank"

  def render_default (self, surface, rect):
    pass

class BlankWidget (screen.ScreenWidget):

  screen = Blank
  name = screen.name

#
# Splash - screen & widget
#
class Splash (screen.Screen):

  name = "Splash"
  _state = screen.Screen._state + ["greetings"]

  def __init__ (self, engine, style="default", greetings="", *args, **kwargs):
    super (Splash, self).__init__ (engine)
    self.do_reset (greetings)

  def do_reset (self, greetings):
    self.greetings = greetings
    self.is_dirty = True

  def render_default (self, surface, rect):
    surface.fill (self.background_colour, rect)
    text = core.Font (self.typeface, rect.height / 10).render (self.greetings, self.foreground_colour)
    text_rect = text.get_rect ()
    text_rect.center = rect.center
    surface.blit (text, text_rect)

class SplashWidget (screen.ScreenWidget):

  screen = Splash
  name = screen.name

  def widgets (self):
    layout = QtGui.QHBoxLayout ()
    self.greetings = QtGui.QLineEdit ("Quizzicals")
    self.greetings.textEdited.connect (self.on_greetings)
    layout.addWidget (self.greetings)
    return layout

  def on_greetings (self, new_greetings):
    self.send_command ("reset", new_greetings)

#
# Countdown - screen & widget
#
class Countdown (screen.Screen):

  name = "Countdown"
  _state = screen.Screen._state + ["n_ticks", "big_tick_every_n", "tick_interval_secs", "final_furlong"]

  colours = {
    "little" : screen.Screen.foreground_colour,
    "big" : core.Color ("blue")
  }
  final_colours = {
    "big" : core.Color ("red"),
    "little" : core.Color ("yellow")
  }
  sounds = {
    "big" : (1720, 100),
    "little" : (880, 100)
  }
  font_quotients = {
    "little" : 3,
    "big" : 2
  }

  def __init__ (self, engine, style="default", n_ticks=60, big_tick_every_n=5, tick_interval_secs=1, final_furlong=None):
    super (Countdown, self).__init__ (engine)
    self.do_reset (n_ticks, big_tick_every_n, tick_interval_secs, final_furlong)

  def handle_pygame_event (self, event):
    if event.type == core.timer_event_type:
      self.engine.instructions.put ("TICK")
      return True
    else:
      return super (Countdown, self).handle_pygame_event (event)

  def render_countdown (self, surface, rect):
    tick_type = self.ticks[self.n_tick]
    if tick_type is not None:
      colours = self.final_colours if self.n_tick > self.n_ticks - self.final_furlong else self.colours
      font = core.Font (self.typeface, rect.height / self.font_quotients[tick_type])
      text = font.render ("%d" % (self.n_ticks - self.n_tick), colours[tick_type])
      text_rect = text.get_rect ()
      text_rect.center = rect.center
      surface.blit (text, text_rect)

  def render_vbars (self, surface, rect):
    tick_w = rect.width / 5
    tick_h = rect.height / self.n_ticks
    for n_tick, tick in enumerate (self.ticks):
      if tick is None: continue
      colours = self.final_colours if n_tick > self.n_ticks - self.final_furlong else self.colours
      tick_rect = core.Rect (0, 0, tick_w, tick_h).inflate (-4, -4)
      tick_rect.top = rect.top + tick_h * n_tick
      tick_rect.centerx = rect.centerx
      surface.fill (colours[tick], tick_rect)

  def render_clock (self, surface, rect):
    disc_size = {
      "big" : int (10 * 60.0 / self.n_ticks),
      "little" : int (8 * 60.0 / self.n_ticks)
    }
    radius = (rect.height - 100) / 2
    half_pi = math.pi / 2.0
    radian_gap = 2.0 * math.pi / self.n_ticks

    for n_tick, tick in enumerate (self.ticks):
      if tick is None: continue
      n = (radian_gap * n_tick) - half_pi
      x = int (math.cos (n) * radius)
      y = int (math.sin (n) * radius)
      colours = self.final_colours if n_tick > self.n_ticks - self.final_furlong else self.colours
      pygame.draw.circle (surface, colours[tick], (rect.centerx + x, rect.centery + y), disc_size[tick])

  render_default = render_clock

  def do_reset (self, n_ticks=60, big_tick_every_n=5, tick_interval_secs=1, final_furlong=None):
    self.is_active = False
    self.n_tick = 1

    self.n_ticks = int (n_ticks)
    self.big_tick_every_n = int (big_tick_every_n)
    self.tick_interval_secs = int (tick_interval_secs)
    if final_furlong is None:
      self.final_furlong = 2 * self.big_tick_every_n
    else:
      self.final_furlong = int (final_furlong)
    self.ticks = [None] + ["big" if t % self.big_tick_every_n == 0 else "little" for t in range (1, self.n_ticks + 1)]

    self.is_dirty = True

  def do_start (self):
    self.is_active = True
    pygame.time.set_timer (core.timer_event_type, 1000 * self.tick_interval_secs)

  def do_pause (self):
    self.is_active = False

  def do_stop (self):
    pygame.time.set_timer (core.timer_event_type, 0)
    self.is_active = False

  def do_finish (self):
    pygame.mixer.music.load ("media/alarm-clock.wav")
    pygame.mixer.music.play ()
    pygame.time.wait (1500)
    pygame.mixer.music.stop ()

  def do_tick (self):
    if self.is_active:
      self.is_dirty = True
      tick_type = self.ticks[self.n_tick]
      if tick_type in self.sounds:
        frequency, duration = self.sounds[tick_type]
        if self.n_tick > self.n_ticks - self.final_furlong:
          frequency *= 1.1
        elif self.n_tick > self.n_ticks / 2:
          frequency *= 1.05
        winsound.Beep (int (frequency), duration)
      self.ticks[self.n_tick] = None
      self.n_tick += 1
      if self.n_tick > self.n_ticks:
        self.engine.instructions.put ("STOP")
        self.engine.instructions.put ("FINISH")

  def get_countdown (self):
    return "COUNTDOWN", self.n_tick

class CountdownWidget (screen.ScreenWidget):

  screen = Countdown
  name = screen.name

  def widgets (self):
    layout = QtGui.QHBoxLayout ()
    layout.addWidget (QtGui.QLabel ("Ticks"))
    self.n_ticks = QtGui.QLineEdit ("60")
    layout.addWidget (self.n_ticks)
    layout.addWidget (QtGui.QLabel ("Big ticks at"))
    self.big_tick_every_n = QtGui.QLineEdit ("5")
    layout.addWidget (self.big_tick_every_n)
    layout.addWidget (QtGui.QLabel ("Tick interval"))
    self.tick_interval_secs = QtGui.QLineEdit ("1")
    layout.addWidget (self.tick_interval_secs)
    reset_countdown = QtGui.QPushButton ("Reset")
    layout.addWidget (reset_countdown)
    start_pause = QtGui.QPushButton ("Start")
    layout.addWidget (start_pause)

    reset_countdown.pressed.connect (self.on_reset)
    start_pause.pressed.connect (self.on_start_pause)

    return layout

  def on_reset (self):
    self.send_command ("COUNTDOWN", self.n_ticks.text (), self.big_tick_every_n.text (), self.tick_interval_secs.text ())

  def on_start_pause (self):
    if self.start_pause.text () == "Start":
      self.send_command ("START")
      self.start_pause.setText ("Pause")
    else:
      self.send_command ("STOP")
      self.start_pause.setText ("Start")

#
# Scores - screen & widget
#
class Scores (screen.Screen):

  name = "Scores"
  _state = screen.Screen._state + []

  title_colour = screen.Screen.foreground_colour
  title_typeface = score_typeface = screen.Screen.typeface
  score_colour = screen.Screen.foreground_colour

  def __init__ (self, engine, style="default"):
    super (Scores, self).__init__ (engine, style)

  def _render_team_title (self, team, surface, team_rect):
    max_height = int (self.engine.window.get_rect ().height / 3.0  / 6.0)
    rect = core.Rect (team_rect.left, team_rect.top, team_rect.width, min (team_rect.height / 6, max_height)).inflate (-2, -2)
    title_font = core.Font (self.title_typeface, rect.height - 8)
    team_title = title_font.render (team.name, self.title_colour)
    surface.fill (core.Color.dark, rect)
    title_rect = team_title.get_rect ()
    title_rect.center = rect.center
    surface.blit (team_title, title_rect)

  def _render_score (self, team, surface, team_rect):
    score_font = core.Font (self.score_typeface, team_rect.height / 3)
    score = score_font.render ("%d" % team.score, team.text_colour)
    score_rect = score.get_rect ()
    score_rect.center = team_rect.center
    surface.blit (score, score_rect)

  def render_even_boxes (self, surface, rect):
    if not self.engine.teams:
      return
    n_teams = len (self.engine.teams)
    n_cols = 1
    while n_cols * n_cols < n_teams:
      n_cols += 1
    team_w = rect.width / n_cols
    team_h = rect.height / n_cols

    score_font = core.Font (self.score_typeface, team_h / 2)
    for n_team, team in enumerate (self.engine.teams):
      across, down = divmod (n_team, n_cols)
      team_rect = core.Rect (rect.left + (across * team_w), rect.top + (down * team_h), team_w, team_h).inflate (-2, -2)
      surface.fill (team.colour, team_rect)
      self._render_team_title (team, surface, team_rect)
      self._render_score (team, surface, team_rect)

  def render_stacked (self, surface, rect):
    if not self.engine.teams:
      return
    teams = self.engine.teams
    height = rect.height / len (teams)
    top = rect.top
    for team in sorted (teams, key=lambda t: t.score, reverse=True):
      team_rect = core.Rect (rect.left, top, rect.width, height).inflate (-2, -2)
      surface.fill (team.colour, team_rect)
      self._render_team_title (team, surface, team_rect)
      self._render_score (team, surface, team_rect)
      top += height

  render_default = render_stacked

  def render (self, surface, rect):
    #
    # The default render mechanism resets to clean after
    # a render. But we have not means of knowing when the
    # scores change; so always consider ourselves dirty.
    #
    super (Scores, self).render (surface, rect)
    self.is_dirty = True

class ScoresWidget (screen.ScreenWidget):

  name = "Scores"
  screen = Scores

_screens = dict ((cls.__name__.lower (), cls) for cls in screen.Screen.__subclasses__ ())
_widgets = dict ((cls.name.lower (), cls) for cls in screen.ScreenWidget.__subclasses__ ())
