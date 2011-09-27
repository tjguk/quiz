import os, sys
import json
import logging
import shlex
import subprocess
import time

import Pyro4
from PyQt4 import QtCore, QtGui

log = logging.getLogger ("Quiz")
log.setLevel (logging.DEBUG)
log.addHandler (logging.StreamHandler ())

class FeedbackReader (QtCore.QThread):

  message_received = QtCore.pyqtSignal (unicode)

  def __init__ (self, proxy):
    super (FeedbackReader, self).__init__ ()
    self.feedback = proxy

  def run (self):
    while True:
      self.message_received.emit (self.feedback.get ())

class ScreenWidget (QtGui.QWidget):

  def __init__ (self, controller, position, *args, **kwargs):
    super (ScreenWidget, self).__init__ (*args, **kwargs)
    self.controller = controller
    self.position = position.lower ()

    overall_layout = QtGui.QVBoxLayout ()
    layout = QtGui.QHBoxLayout ()
    layout.addWidget (QtGui.QLabel ("Style"))
    self.styles = QtGui.QComboBox ()
    layout.addWidget (self.styles)
    overall_layout.addLayout (layout)

    widget_layout = self.widgets ()
    if widget_layout:
      overall_layout.addLayout (widget_layout)

    layout = QtGui.QHBoxLayout ()
    self.apply = QtGui.QPushButton ("Apply")
    layout.addWidget (self.apply)
    overall_layout.addLayout (layout)

    self.setLayout (overall_layout)

    self.styles.currentIndexChanged.connect (self.on_style)
    self.apply.clicked.connect (self.on_apply)

  @classmethod
  def _screens (cls):
    for subclass in cls.__subclasses__ ():
      yield subclass
      for s in subclass._screens ():
        yield s

  def widgets (self):
    """Set up some widgets; return a layout
    """
    return None

  def send_command (self, command):
    self.controller.send_command ("%s %s" % (self.position.upper (), command))

  def on_style (self, index):
    log.debug ("Handling style change for position %s, style %s", self.position, index)
    log.debug (self.styles.itemText (index))
    self.send_command ("STYLE %s" % self.styles.itemText (index))

  def on_apply (self):
    raise NotImplementedError

  def handler_default (self):
    raise NotImplementedError

class Splash (ScreenWidget):

  def widgets (self):
    layout = QtGui.QHBoxLayout ()
    self.greetings = QtGui.QLineEdit ("Quizzicals")
    self.greetings.textEdited.connect (self.on_greetings)
    layout.addWidget (self.greetings)
    return layout

  def on_greetings (self, new_greetings):
    self.send_command ('RESET "%s"' % new_greetings)

class Scores (ScreenWidget):

  pass

class Countdown (ScreenWidget):

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
    self.send_command ("COUNTDOWN %s %s %s" % (self.n_ticks.text (), self.big_tick_every_n.text (), self.tick_interval_secs.text ()))

  def on_start_pause (self):
    if self.start_pause.text () == "Start":
      self.send_command ("START")
      self.start_pause.setText ("Pause")
    else:
      self.send_command ("STOP")
      self.start_pause.setText ("Start")

class WidgetStack (QtGui.QGroupBox):

  def __init__ (self, controller, position, *args, **kwargs):
    super (WidgetStack, self).__init__ (position.title (), *args, **kwargs)
    self.position = position.lower ()

    layout = QtGui.QVBoxLayout ()
    self.selector = QtGui.QComboBox ()
    layout.addWidget (self.selector)
    self.stack = QtGui.QStackedWidget ()
    layout.addWidget (self.stack)
    self.setLayout (layout)

    for cls in ScreenWidget._screens ():
      self.selector.addItem (cls.__name__)
      self.stack.addWidget (cls (controller, position))

class QuizController (QtGui.QWidget):

  COMMAND_MAILSLOT_NAME = "quiz"
  RESPONSE_MAILSLOT_NAME = "sub"

  def __init__ (self, *args, **kwargs):
    super (QuizController, self).__init__ (*args, **kwargs)
    self.setWindowTitle ("Quiz Controller")

    self.controller = Pyro4.Proxy ("PYRO:quiz.instructions@localhost:1234")
    self.responder = FeedbackReader (Pyro4.Proxy ("PYRO:quiz.feedback@localhost:1234"))
    self.responder.message_received.connect (self.handle_response)
    self.responder.start ()

    overall_layout = QtGui.QVBoxLayout ()
    self.add_teams (overall_layout)

    groups_layout = QtGui.QHBoxLayout ()
    self.groups = {}
    for position in ("left", "right"):
      self.groups[position] = WidgetStack (self, position)
      groups_layout.addWidget (self.groups[position])

    overall_layout.addLayout (groups_layout)
    self.add_controller (overall_layout)
    self.setLayout (overall_layout)

    self.send_command ("TEAMS?")
    self.send_command ("COLOURS?")
    self.send_command ("SCORES?")
    self.send_command ("LEFT STATE?")
    self.send_command ("RIGHT STATE?")

  def switch (self, position):
    def _switch (index):
      group = self.groups[position]
      group.stack.setCurrentIndex (index)
      self.send_command ("SWITCH %s %s" % (position, group.selector.itemText (index)))
      self.send_command ("%s STYLES?" % position)
    return _switch

  def add_teams (self, overall_layout):
    self.teams = []
    for i in range (4):
      team = (
        team_name,
        team_score,
        team_plus,
        team_minus
      ) = (
        QtGui.QLineEdit (),
        QtGui.QLineEdit (""),
        QtGui.QPushButton ("+"),
        QtGui.QPushButton ("-")
      )
      self.teams.append (team)
      layout = QtGui.QHBoxLayout ()
      for widget in team:
        layout.addWidget (widget)
      overall_layout.addLayout (layout)

      def set_team_name (new_name, n_team=i, team_name=team_name, team_score=team_score):
        self.send_command ('NAME %d "%s"' % (n_team, team_name.text ()))
        if not team_name.styleSheet ():
          self.send_command ("COLOURS?")
      def set_team_score (new_score, n_team=i):
        self.send_command ('SCORE %d =%s' % (n_team, new_score))
      def set_team_plus (n_team=i, team_score=team_score):
        score = 1 + int (team_score.text () or 0)
        team_score.setText (str (score))
      def set_team_minus (n_team=i, team_score=team_score):
        score = int (team_score.text () or 0) - 1
        team_score.setText (str (score))

      team_name.textEdited.connect (set_team_name)
      team_score.textChanged.connect (set_team_score)
      team_plus.pressed.connect (set_team_plus)
      team_minus.pressed.connect (set_team_minus)

  def add_controller (self, overall_layout):
    command_label = QtGui.QLabel ("Command")
    self.command = QtGui.QLineEdit ()
    self.send = QtGui.QPushButton ("&Send")
    controller_layout = QtGui.QHBoxLayout ()
    controller_layout.addWidget (command_label)
    controller_layout.addWidget (self.command)
    controller_layout.addWidget (self.send)
    overall_layout.addLayout (controller_layout)
    self.send.clicked.connect (self.send_command)

    self.responses = QtGui.QLabel ()
    responses_layout = QtGui.QHBoxLayout ()
    responses_layout.addWidget (self.responses)
    overall_layout.addLayout (responses_layout)

  def send_command (self, command=None):
    command = unicode (command or self.command.text ()).encode ("iso-8859-1")
    if command:
      self.command.setText (command)
      self.controller.put (command)
    else:
      log.warn ("No command output")

  def position_widget (self, position):
    return self.groups.get (position.lower ())

  def handle_default (self, *args):
    log.debug ("handle_default: %s", str (args))

  def handle_position (self, position, *rest):
    log.debug ("handle_position: %s, %s", position, rest)

    cls_name = rest[0]
    group = self.groups[position]
    group.selector.setCurrentIndex (group.selector.findText (cls_name))
    screen_widget = group.stack.currentWidget ()
    params = dict (i.split ("=") for i in rest[1:])

    styles_combo = screen_widget.styles
    if "styles" in params:
      styles_combo.clear ()
      styles_combo.addItems ([item.strip () for item in params.pop ("styles").split (",")])
    if "style" in params:
      screen_widget.styles.setCurrentIndex (screen_widget.styles.findText (params.pop ("style")))
    for k, v in params.items ():
      subwidget = getattr (screen_widget, k.lower (), None)
      if subwidget:
        subwidget.setText (v)

  def handle_left (self, *rest):
    self.handle_position ("left", *rest)

  def handle_right (self, *rest):
    self.handle_position ("right", *rest)

  def handle_teams (self, *rest):
    for n_team, new_name in enumerate (rest):
      name, _, _, _ = self.teams[n_team]
      name.setText (new_name)

  def handle_colours (self, *rest):
    for n_team, new_colour in enumerate (rest):
      name, _, _, _ = self.teams[n_team]
      name.setStyleSheet ("* { background-color : %s; }" % new_colour)

  def handle_scores (self, *rest):
    for n_team, new_score in enumerate (rest):
      _, score, _, _ = self.teams[n_team]
      score.setText (new_score)

  def handle_quit (self):
    self.close ()

  def handle_response (self, message):
    log.debug ("Response received: %s", message)
    self.responses.setText (message)
    parts = shlex.split (str (message))
    response, rest = parts[0].lower (), parts[1:]
    handler = getattr (self, "handle_" + response, self.handle_default)
    log.debug ("Response handler: %s", handler)
    return handler (*rest)

def main ():
  app = QtGui.QApplication ([])
  quiz_controller = QuizController()
  quiz_controller.show ()
  return app.exec_ ()

if __name__ == '__main__':
  sys.exit (main (*sys.argv[1:]))

