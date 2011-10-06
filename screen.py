import os, sys
import shlex

from PyQt4 import QtCore, QtGui
import pygame

import core

class Screen (object):

  name = ""
  _state = ["style"]

  KEYS = {}

  background_colour = core.Color.dark
  foreground_colour = core.Color.light
  typeface = r"c:\windows\fonts\tahomabd.ttf"
  default_font_height = 0.1

  def __init__ (self, engine, style="default"):
    self.engine = engine
    self.is_dirty = True
    self.style = None
    self.do_style (style)

  def handle_pygame_event (self, event):
    if event.type == pygame.KEYDOWN and event.key in self.KEYS:
      self.engine.instructions.put (KEYS[event.key])
      return True
    else:
      return False

  #
  # Default actions
  #
  def do_style (self, style="default"):
    style = style.lower ()
    renderer_name = "render_" + style
    if hasattr (self, renderer_name):
      self.renderer = getattr (self, renderer_name)
      self.style = style
      self.is_dirty = True
      core.log.info ("Using renderer %s", self.renderer)
    else:
      core.log.warn ("No renderer found named %s", renderer_name)

  def _styles (self):
    prefix = "render_"
    return [i[len (prefix):] for i in dir (self) if i.startswith (prefix)]

  def get_styles (self):
    return "%s STYLES %s" % (self.position, " ".join (self._styles ()))

  #
  # Default getters
  #
  def get_state (self):
    state = [self.name]
    state.append ('styles="%s"' % ",".join (self._styles ()))
    for s in self._state:
      state.append ('%s="%s"' % (s, getattr (self, s, None) or ""))
    return " ".join (state)

  def get_styles (self):
    return "STYLES %s" % " ".join (self._styles ())

  #
  # Renderers
  #
  def render_default (self, surface, rect):
    raise NotImplemented

  def render (self, surface, rect):
    if self.is_dirty:
      surface.fill (self.background_colour, rect)
      self.renderer (surface, rect.inflate (-8, -8))
      self.is_dirty = False

class ScreenWidget (QtGui.QWidget):

  name = ""

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

  def widgets (self):
    """Set up some widgets; return a layout
    """
    return None

  def send_command (self, command):
    self.controller.send_command ("%s %s" % (self.position.upper (), command))

  def on_style (self, index):
    log.debug ("Handling style change for position %s, style %s", self.position, index)
    log.debug (self.styles.itemText (index))
    self.send_command ("STYLE %s" % self.styles.currentText ())

  def on_apply (self):
    raise NotImplementedError

  def handle_reset (self, **kwargs):
    if "style" in kwargs:
      style = kwargs.pop ("style")
    for field, value in kwargs.items ():
      pass


  def handle_default (self):
    raise NotImplementedError
