import os, sys
import shlex

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
