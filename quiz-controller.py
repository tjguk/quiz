import os, sys
import json
import logging
import shlex
import subprocess
import time

import Pyro4
from PyQt4 import QtCore, QtGui

import core
import screen
import screens

class FeedbackReader (QtCore.QThread):

  message_received = QtCore.pyqtSignal (unicode)

  def __init__ (self, proxy):
    super (FeedbackReader, self).__init__ ()
    self.feedback = proxy

  def run (self):
    while True:
      self.message_received.emit (self.feedback.get ())

class WidgetStack (QtGui.QGroupBox):

  def __init__ (self, controller, position, *args, **kwargs):
    super (WidgetStack, self).__init__ (position.title (), *args, **kwargs)
    self.controller = controller
    self.position = position.lower ()

    layout = QtGui.QVBoxLayout ()
    self.selector = QtGui.QComboBox ()
    self.selector.currentIndexChanged.connect (self.on_selector)

    layout.addWidget (self.selector)
    self.stack = QtGui.QStackedWidget ()
    layout.addWidget (self.stack)
    self.setLayout (layout)

    for cls in screen.ScreenWidget.__subclasses__ ():
      self.selector.addItem (cls.name)
      self.stack.addWidget (cls (controller, position))

  def on_selector (self, index):
    self.stack.setCurrentIndex (index)
    self.controller.send_command ("SWITCH %s %s" % (self.position, self.selector.itemText (index)))
    self.controller.send_command ("%s STYLES?" % self.position)

  def handle_styles (self, *rest):
    core.log.debug ("handle_styles: %s", rest)

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

    self.panel_layout = QtGui.QHBoxLayout ()
    self.panels = {}
    #
    # Panels wlil be added via the handle_position handler below
    #
    overall_layout.addLayout (self.panel_layout)
    self.add_controller (overall_layout)
    self.setLayout (overall_layout)

    self.send_command ("POSITIONS?")
    self.send_command ("TEAMS?")
    self.send_command ("COLOURS?")
    self.send_command ("SCORES?")
    self.send_command ("LEFT STATE?")
    self.send_command ("RIGHT STATE?")

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
      core.log.warn ("No command output")

  def position_widget (self, position):
    return self.groups.get (position.lower ())

  def handle_default (self, *args):
    core.log.debug ("handle_default: %s", str (args))

  def handle_positions (self, positions):
    """Handle the POSITIONS event by constructing a corresponding
    number of panels. Fire off a command to query for the screen
    each panel is currently showing.
    """
    for position in positions:
      panel = self.panels[position.lower ()] = Panel (self, position)
      self.panel_layout.addWidget (panel)
      self.send_command ("POSITION? %s" % position)

  def handle_position (self, position, screen_name):
    """Handle the POSITION event by selecting the corresponding
    screen from the stacked widget.
    """
    panel = self.panels[position.lower ()]
    if panel.selector.currentText () != screen_name:
      panel.selector.setCurrentText (screen_name)
      #
      # Changing the selector will cause a STATE? query to fire
      #

  def _handle_position (self, position, *rest):
    core.log.debug ("handle_position: %s, %s", position, rest)

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
    self._handle_position ("left", *rest)

  def handle_right (self, *rest):
    self._handle_position ("right", *rest)

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
    core.log.debug ("Response received: %s", message)
    self.responses.setText (message)
    parts = shlex.split (str (message))
    response, rest = parts[0].lower (), parts[1:]
    handler = getattr (self, "handle_" + response, self.handle_default)
    core.log.debug ("Response handler: %s", handler)
    return handler (*rest)

def main ():
  app = QtGui.QApplication ([])
  quiz_controller = QuizController()
  quiz_controller.show ()
  return app.exec_ ()

if __name__ == '__main__':
  sys.exit (main (*sys.argv[1:]))

