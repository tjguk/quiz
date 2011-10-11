import os, sys
import inspect
import itertools
import threading
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
  """A team is mostly a Bunch class with a cycle of colours to choose from
  """

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

  def __init__ (self):
    """Create the instruction and feedback queues and default the screen
    to a left-handle splash panel and a right hand scores stack with no
    teams defined.
    """
    self.instructions = core.Queue ()
    self.feedback = core.Queue ()
    self.panels = dict (
      left = screens.Splash (self, greetings="Westpark Quiz"),
      right = screens.Scores (self)
    )
    self.teams = []

  def check_pygame_events (self, objects):
    """Pull all pygame events off the pygame queue and pass them to
    the first object which will have them.
    """
    for event in pygame.event.get ():
      for obj in objects:
        if obj.handle_pygame_event (event):
          break

  def check_instructions (self, objects):
    """Pull all instructions off the instruction queue and pass them to
    the first object which will have them. If the object's handler
    returns anything, push that back on the feedback queue.
    """
    for action, args in self.instructions:
      core.log.debug ("Engine Instruction: %r (%s)", action, args)
      feedback = self.check_instruction (objects, action.strip ().lower (), args)
      if feedback:
        self.publish (*feedback)

  def check_instruction (self, objects, action, args):
    """Find the first of a list of objects which can handle an action
    and return whatever its handler returns. NB an action which ends
    in a "?" invokes a get handler; any other action invokes a do handler.
    """
    core.log.debug ("check_instruction: %s, %s (%s)", objects, action, args)
    if action.endswith ("?"):
      verb = "get_" + action[:-1]
    else:
      verb = "do_" + action

    for obj in objects:
      if hasattr (obj, verb):
        return getattr (obj, verb) (*args)

  def handle_pygame_event (self, event):
    """Handle core pygame events: quit & resize. For unhandled events,
    return False so the caller will pass them onto other screens.
    """
    if event.type == pygame.QUIT:
      self.instructions.put ("QUIT")
      return True
    elif event.type == pygame.KEYUP and event.key == pygame.K_ESCAPE:
      self.instructions.put ("QUIT")
      return True
    elif event.type == pygame.VIDEORESIZE:
      self.do_resize (event.size)
      return True
    else:
      return False

  def do_resize (self, size=None):
    """Resize the window to a particular size, defaulting to the class's default
    window size so it can be used from the main engine.
    """
    if size:
      self.window_rect.size = size
    self.window = pygame.display.set_mode (self.window_rect.size, self.window_flags)
    self.panel_rects = dict ()
    w, h = self.window_rect.size
    for position, (pleft, ptop, pwidth, pheight) in self.positions.items ():
      self.panel_rects[position] = core.Rect (w * pleft, h * ptop, w * pwidth, h * pheight).inflate (-4, -4)
    self.repaint ()

  def do_name (self, n_team, name):
    """Set the name for a team (this is often done incrementally from
    the controller, so the name is likely to be a part name
    """
    for i in range (1 + n_team - len (self.teams)):
      self.teams.append (Team (""))
    self.teams[n_team].name = name

  def do_remove (self, n_team):
    """Remove a team from the scoreboard
    """
    self.teams = self.teams[:n_team] + self.teams[n_team:]

  def do_score (self, which_team, value):
    """Set the score for a team.
    """
    team = self.teams[which_team]
    score0 = team.score
    team.score = value
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
    if self.panels[position].name != screen_name:
      self.panels[position] = cls (self)
      return "SWITCH", position, screen_name

  def _do_position (self, position, *args):
    """Send a command to the left or right panel. NB This
    cannot be used to switch the screen underlying the panel;
    for that, use SWITCH.
    """
    screen = self.panels.get (position)
    if screen:
      core.log.debug ("Passing %s onto %s", args, screen)
      feedback = self.check_instruction ([screen], args)
      if feedback:
        self.publish (position, *feedback)

  def do_left (self, *args):
    """Pass the command and its parameters through to the left-hand panel
    """
    return self._do_position ("left", *args)

  def do_right (self, *args):
    """Pass the command and its parameters through to the right-hand panel
    """
    return self._do_position ("right", *args)

  def get_help (self, command=None):
    """If a command is specified, return the parameters for that command, otherwise
    return a list of valid commands
    """
    if command:
      fn = getattr (self, ("get_" if command.endswith ("?") else "do_") + command.lower (), None)
      if fn:
        args = inspect.getargspec (fn).args[1:]
        return "HELP", command.upper (), args
    else:
      commands = set ()
      for obj in [self] + self.panels.values ():
        commands.update (i[len ("do_"):] for i in dir (obj) if i.startswith ("do_"))
        commands.update (i[len ("get_"):] + "?" for i in dir (obj) if i.startswith ("get_"))
      return "HELP", sorted (commands)

  def get_positions (self):
    """Return a list of position names (typically "left" and "right")
    """
    return "POSITIONS", list (self.panels)

  def get_position (self, position):
    """Return the class of the panel at position `position`
    """
    return "POSITION", position, self.panels[position.lower ()].name

  def get_teams (self):
    """Return a list of teams
    """
    return "TEAM", [team.name for team in self.teams]

  def get_scores (self):
    """Return a list of scores, one for each team
    """
    return "SCORES", [team.score for team in self.teams]

  def get_colours (self):
    """Return a list of HTML-style #rrggbb colours, one for each team
    """
    return "COLOURS", ["#%02x%02x%02x" % team.colour[:3] for team in self.teams]

  def repaint (self):
    """Completely repaint the screen,
    """
    self.window.fill (self.background_colour)
    for position, screen in self.panels.items ():
      #
      # FIXME: is_dirty is probably redundant
      #
      screen.is_dirty = True

  def publish (self, message, *args):
    """Send a message and parameters back through the feedback queue
    """
    core.log.debug ("Publish %s: %s", message, args)
    self.feedback.put (message, *args)

  def run (self):
    #
    # Set up two Pyro-linked queues: one for instructions; the other
    # for feedback from the instruction handlers.
    #
    instruction_manager = threading.Thread (
      target=manage_instructions,
      args=(self.instructions, self.feedback)
    )
    instruction_manager.daemon = True
    instruction_manager.start ()

    #
    # Reset the screen to its default size and caption
    #
    self.do_resize ()
    pygame.display.set_caption ("Westpark Quiz")

    #
    # At no more than 5 frames a second, render all current panels
    # and check for incoming instructions or pygame events.
    #
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
