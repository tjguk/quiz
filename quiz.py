import sys
import collections
import ConfigParser
import inspect
import itertools
import logging
import math
import random
import shlex
import threading
import time
try:
  import winsound
  def beep (frequency, duration):
    winsound.Beep (frequency, duration)
except ImportError:
  def beep (frequency, duration):
    pass

import pygame
import Pyro4

import core
import screen
import screens

_screens = dict ((cls.__name__.lower (), cls) for cls in screen.Screen.__subclasses__ ())

#
# Little piece of black magic to ensure no lag
# occurs when playing sound. Must be done before
# pygame.init
#
pygame.mixer.pre_init (44100, -16, 2, 1024)
pygame.init ()

def manage_instructions (instructions, feedback):
  daemon = Pyro4.Daemon (port=1234)
  Pyro4.Daemon.serveSimple (
    {
      instructions : "quiz.instructions",
      feedback : "quiz.feedback"
    },
    daemon=daemon,
    ns=False
  )

class Team (object):

  colours = itertools.cycle (["red", "green", "yellow", "blue", "purple", "orange", "royalblue", "salmon", "wheat"])
  names = iter (["Haddock", "Kippers", "Plaice", "Trout", "Salmon", "Halibut"])

  def __init__ (self, name, score=0):
    self.colour = core.Color (self.colours.next ())
    self.name = name or self.names.next ()
    self.text_colour = core.Color.light if self.colour.is_dark () else core.Color.dark
    self.score = score

  def __repr__ (self):
    return "<%s - %s>" % (self.__class__.__name__, self.name)

class Engine (object):

  positions = dict (
    left = (0, 0, 0.66, 1.0),
    right = (0.66, 0, 0.34, 1.0),
    full = (0, 0, 1, 1)
  )
  window_rect = core.Rect (0, 0, 400, 300)
  window_flags = pygame.RESIZABLE
  background_colour = core.Color.light

  def __init__ (self, ini_filepath=None):
    self.config = ConfigParser.ConfigParser ()
    if ini_filepath:
      self.config.load (ini_filepath)
    self.instructions = core.Queue ()
    self.feedback = core.Queue ()
    self.panels = dict (
      left = screens.Splash (self, greetings="Westpark Quiz"),
      right = screens.Scores (self)
    )
    self.teams = []

  def check_pygame_events (self, objs):
    for event in pygame.event.get ():
      core.log.debug ("Received %s", event)
      for obj in objs:
        if obj.handle_pygame_event (event):
          break

  def check_instructions (self, objects):
    for instruction in self.instructions:
      core.log.debug ("Engine Instruction: %r", instruction)
      parts = shlex.split (instruction.strip ())
      feedback = self.check_instruction (objects, parts)
      if feedback:
        self.publish (feedback)

  def handle_pygame_event (self, event):
    if event.type == pygame.QUIT:
      self.instructions.put ("QUIT")
      return True
    elif event.type == pygame.KEYUP and event.key == pygame.K_ESCAPE:
      self.instructions.put ("QUIT")
      return True
    elif event.type == pygame.VIDEORESIZE:
      self.on_resize (event.size)
      return True
    else:
      return False

  def check_instruction (self, objects, parts):
    verb = parts[0].lower ()
    if verb.endswith ("?"):
      action = "get_" + verb[:-1]
    else:
      action = "do_" + verb

    for obj in objects:
      if hasattr (obj, action):
        return getattr (obj, action) (*parts[1:])

  def on_resize (self, size=None):
    if size:
      self.window_rect.size = size
    self.window = pygame.display.set_mode (self.window_rect.size, self.window_flags)
    self.panel_rects = dict ()
    w, h = self.window_rect.size
    for position, (pleft, ptop, pwidth, pheight) in self.positions.items ():
      self.panel_rects[position] = core.Rect (w * pleft, h * ptop, w * pwidth, h * pheight).inflate (-4, -4)
    self.repaint ()

  def do_name (self, n_team, name):
    n_team = int (n_team)
    for i in range (1 + n_team - len (self.teams)):
      self.teams.append (Team (""))
    self.teams[n_team].name = name

  def do_remove (self, n_team):
    self.teams = self.teams[:n_team] + self.teams[n_team:]

  def do_score (self, which_team, value):
    try:
      which_team = int (which_team)
      team = self.teams[which_team]
    except ValueError:
      for n_team, team in enumerate (self.teams):
        if team.name.lower () == which_team.lower ():
          break
      else:
        raise RuntimeError ("No such team: %s" % n_team)
    score0 = team.score
    if value.startswith ("="):
      team.score = int (value[1:])
    else:
      team.score += int (value)
    if team.score > score0:
      beep (1440, 100)
      beep (2880, 200)
    elif team.score < score0:
      beep (440, 100)
      beep (220, 200)
    pygame.event.post (core.scores_changed_event)

  def do_quit (self):
    self.publish ("QUIT")
    pygame.time.wait (250)
    sys.exit ()

  def do_switch (self, position, screen_name):
    """Switch the left or right panel to a different screen
    """
    position = position.lower ()
    assert position in self.positions
    cls = _screens[screen_name.lower ()]
    self.panels[position] = cls (self)

  def _do_position (self, position, *rest):
    """Send a command to the left or right panel. NB This
    cannot be used to switch the screen underlying the panel;
    for that, use SWITCH.
    """
    screen = self.panels.get (position)
    if screen:
      core.log.debug ("Passing %s onto %s", [rest], screen)
      feedback = self.check_instruction ([screen], rest)
      if feedback:
        self.publish ("%s %s" % (position, feedback))

  def do_left (self, *rest):
    self._do_position ("left", *rest)

  def do_right (self, *rest):
    self._do_position ("right", *rest)

  def get_help (self, command=None):
    if command:
      fn = getattr (self, ("get_" if command.endswith ("?") else "do_") + command.lower (), None)
      if fn:
        args = inspect.getargspec (fn).args[1:]
        return "HELP %s %s" % (command.upper (), " ".join (args))
    else:
      commands = set ()
      for obj in [self] + self.panels.values ():
        commands.update (i[len ("do_"):] for i in dir (obj) if i.startswith ("do_"))
        commands.update (i[len ("get_"):] + "?" for i in dir (obj) if i.startswith ("get_"))
      return "HELP " + " ".join (sorted (commands))

  #~ def _get_position (self, position):
    #~ response = position.upper ()
    #~ screen = self.panels.get (position.lower ())
    #~ if screen:
      #~ response += " " + screen.get_state ()
    #~ return response

  def get_teams (self):
    return "TEAMS %s" % (" ".join ('"%s"' % team.name for team in self.teams))

  def get_scores (self):
    return "SCORES %s" % (" ".join ("%d" % team.score for team in self.teams))

  def get_colours (self):
    return "COLOURS %s" % (" ".join ("#%02x%02x%02x" % team.colour[:3] for team in self.teams))

  def repaint (self):
    self.window.fill (self.background_colour)
    for position, screen in self.panels.items ():
      screen.is_dirty = True

  def publish (self, message):
    core.log.debug ("Publish %s", message)
    self.feedback.put (message)

  def run (self):
    instruction_manager = threading.Thread (
      target=manage_instructions,
      args=(self.instructions, self.feedback)
    )
    instruction_manager.daemon = True
    instruction_manager.start ()

    self.on_resize ()
    pygame.display.set_caption ("Westpark Quiz")

    clock = pygame.time.Clock ()
    while True:
      for position, screen in self.panels.items ():
        screen.render (self.window, self.panel_rects[position])
      pygame.display.flip ()
      clock.tick (5)

      objects = self.panels.values () + [self]
      try:
        self.check_pygame_events (objects)
        self.check_instructions (objects)
      except Exception, err:
        core.log.exception ("Problem in main loop")
        # core.log errors and then ignore them in an attempt
        # not to crash out midstream

if __name__ == '__main__':
  Engine (*sys.argv[1:]).run ()
