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
    """Generic screen handler for pygame events which looks in a keys
    dictionary to find a mapping between a pygame key and an instruction.
    """
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

  @classmethod
  def _styles (cls):
    prefix = "render_"
    return [i[len (prefix):] for i in dir (cls) if i.startswith (prefix)]

  #
  # Default getters
  #
  def get_state (self):
    state = [self.name]
    info = {"styles" : self._styles ()}
    for s in self._state:
      info[s] = getattr (self, s, None)
    return self.name, info

  def get_styles (self):
    return "Styles", self.__class__._styles ()

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
  screen = Screen

  def __init__ (self, controller, position, *args, **kwargs):
    super (ScreenWidget, self).__init__ (*args, **kwargs)
    self.controller = controller
    self.position = position.lower ()

    overall_layout = QtGui.QVBoxLayout ()
    layout = QtGui.QHBoxLayout ()
    layout.addWidget (QtGui.QLabel ("Style"))
    self.styles = QtGui.QComboBox ()
    self.styles.addItems (self.screen._styles ())
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

  def send_command (self, *args):
    self.controller.send_command (self.position.upper (), *args)

  def on_style (self, index):
    log.debug ("Handling style change for position %s, style %s", self.position, index)
    log.debug (self.styles.itemText (index))
    self.send_command ("style", self.styles.currentText ())

  def on_apply (self):
    raise NotImplementedError

  def handle_reset (self, params):
    if "style" in params:
      style = params.pop ("style")
    for field, value in params.items ():
      pass

  def handle_default (self):
    raise NotImplementedError
