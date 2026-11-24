"""
Jarvis floating bubble: a small translucent capsule pinned to the bottom of the
screen. The animated orb shows what Jarvis is doing; captions show what you
said and the sentence Jarvis is saying right now.

Rendering is plain Cairo + Pango on a transparent window. When gtk-layer-shell
is available (most Wayland desktops: COSMIC, KDE, Sway, Hyprland...), the bubble
floats above other windows at the bottom-center of the screen. Otherwise it
falls back to a borderless "keep above" window.
"""

import math
import time

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk, GLib, Gtk, Pango, PangoCairo  # noqa: E402

try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell  # noqa: E402
except (ValueError, ImportError):
    GtkLayerShell = None

# ---------------------------------------------------------------- design tokens
INK = (0.071, 0.086, 0.149)        # #121626 deep ink-blue glass
INK_ALPHA = 0.90
EDGE = (0.79, 0.63, 0.36)          # #C9A15B brass, used for the hairline edge
BRASS = (0.79, 0.63, 0.36)         # Jarvis speaking
EMBER = (0.43, 0.35, 0.23)         # #6E5A3A dim brass, sleeping
GLACIER = (0.61, 0.79, 0.89)       # #9CC9E3 listening
IVORY = (0.945, 0.918, 0.859)      # #F1EADB Jarvis' words
PEWTER = (0.55, 0.58, 0.66)        # #8C93A8 your words, hints

FONT_USER = "Fira Sans 11"
FONT_JARVIS = "C059 Italic 14"     # classic serif: the butler's voice
FONT_HINT = "Fira Sans Italic 11"

WIDTH = 600
PAD = 18
ORB = 64                           # orb well diameter
BTN = 34                           # control button diameter
MIN_H = 96
MAX_TEXT_LINES = 4
FADE_OUT = 0.18                    # seconds for the old caption to fade out
FADE_IN = 0.30                     # seconds for the new caption to fade in

HINTS = {
    "listening": "Listening…",
    "thinking": "Thinking…",
    "speaking": "",
    "sleeping": "Say “Hey Jarvis”",
}


def _rounded_rect(cr, x, y, w, h, r):
    r = min(r, h / 2, w / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


class Bubble(Gtk.Window):
    def __init__(self, assistant):
        super().__init__(title="Jarvis")
        self.assistant = assistant
        self.state = "sleeping"
        self.user_text = ""
        self.jarvis_text = ""
        self.hover = None
        self.buttons = {}            # name -> (cx, cy)
        self.orb_center = (0, 0)
        self.height = MIN_H
        self.shown_at = 0.0
        self._cap_text = None       # caption currently displayed
        self._cap_prev = None       # previous caption (fading out)
        self._cap_changed = 0.0
        settings = Gtk.Settings.get_default()
        self.reduced_motion = not settings.get_property("gtk-enable-animations")

        self.set_decorated(False)
        self.set_app_paintable(True)
        self.set_resizable(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual is not None:
            self.set_visual(visual)

        self.layer_shell = False
        if GtkLayerShell is not None and GtkLayerShell.is_supported():
            GtkLayerShell.init_for_window(self)
            GtkLayerShell.set_namespace(self, "jarvis")
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.BOTTOM, 28)
            GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.NONE)
            GtkLayerShell.set_exclusive_zone(self, 0)
            self.layer_shell = True
        else:
            self.set_keep_above(True)
            self.set_type_hint(Gdk.WindowTypeHint.UTILITY)

        self.area = Gtk.DrawingArea()
        self.area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK
                             | Gdk.EventMask.POINTER_MOTION_MASK
                             | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.area.connect("draw", self._draw)
        self.area.connect("button-press-event", self._on_click)
        self.area.connect("motion-notify-event", self._on_motion)
        self.area.connect("leave-notify-event", lambda *_: self._set_hover(None))
        self.add(self.area)
        self.connect("delete-event", lambda *_: self.hide() or True)
        self.set_size_request(WIDTH, MIN_H)
        self.area.show()
        GLib.timeout_add(16, self._tick)   # ~60 fps while visible

    # ------------------------------------------------------------ public API
    # (called from other threads through GLib.idle_add)
    def set_state(self, state):
        self.state = state
        if state == "listening":
            self.jarvis_text = ""
        if state != "sleeping" and not self.get_visible():
            self.shown_at = time.monotonic()
            self.show()
        self._relayout()
        return False

    def sleep_and_hide(self):
        self.state = "sleeping"
        self.user_text = ""
        self.jarvis_text = ""
        self._cap_text = self._cap_prev = None
        self.hide()
        return False

    def add_message(self, who, text):
        if who == "user":
            self.user_text = text
            self.jarvis_text = ""
        else:
            self.jarvis_text = text
        self._relayout()
        return False

    def add_separator(self):
        self.user_text = ""
        self.jarvis_text = ""
        return False

    # ------------------------------------------------------------ layout
    def _text_width(self):
        return WIDTH - PAD * 3 - ORB - (BTN * 2 + 10) - PAD

    def _layout(self, cr_or_ctx, text, font, width):
        layout = PangoCairo.create_layout(cr_or_ctx) if cr_or_ctx else None
        if layout is None:
            fm = PangoCairo.FontMap.get_default()
            layout = Pango.Layout.new(fm.create_context())
        layout.set_font_description(Pango.FontDescription.from_string(font))
        layout.set_width(int(width * Pango.SCALE))
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        layout.set_ellipsize(Pango.EllipsizeMode.END)
        layout.set_height(-MAX_TEXT_LINES)
        layout.set_text(text, -1)
        return layout

    def _caption(self):
        """What Jarvis is saying right now (synced with the voice), else the full reply."""
        current = self.assistant.current_caption() if self.state == "speaking" else None
        return current or self.jarvis_text

    def _relayout(self):
        w = self._text_width()
        h = PAD * 2
        if self.user_text:
            h += self._layout(None, self.user_text, FONT_USER, w).get_pixel_size()[1] + 6
        caption = self._caption() or HINTS.get(self.state, "")
        font = FONT_JARVIS if self._caption() else FONT_HINT
        h += self._layout(None, caption, font, w).get_pixel_size()[1]
        new_h = max(MIN_H, h)
        if abs(new_h - self.height) > 1:
            self.height = new_h
            self.set_size_request(WIDTH, new_h)
            self.resize(WIDTH, new_h)

    # ------------------------------------------------------------ animation
    def _tick(self):
        if self.get_visible():
            if self.state == "speaking":
                self._relayout()   # caption follows the sentence being spoken
            self.area.queue_draw()
        return True

    def _level(self):
        if self.state == "listening":
            return self.assistant.mic_level
        if self.state == "speaking":
            return self.assistant.voice_level()
        return 0.0

    # ------------------------------------------------------------ drawing
    def _draw(self, _widget, cr):
        w = self.get_allocated_width()
        h = self.get_allocated_height()
        t = time.monotonic()

        # clear to transparent
        cr.set_operator(1)  # cairo.OPERATOR_SOURCE
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(2)  # cairo.OPERATOR_OVER

        # entrance: a single short rise + fade when the bubble appears
        appear = 1.0 if self.reduced_motion else min(1.0, (t - self.shown_at) / 0.22)
        ease = 1 - (1 - appear) ** 3
        cr.push_group()
        cr.translate(0, (1 - ease) * 10)

        # capsule
        _rounded_rect(cr, 1, 1, w - 2, h - 2, min(30, h / 2))
        cr.set_source_rgba(*INK, INK_ALPHA)
        cr.fill_preserve()
        cr.set_source_rgba(*EDGE, 0.28)
        cr.set_line_width(1)
        cr.stroke()

        # orb
        ox, oy = PAD + ORB / 2, h / 2
        self.orb_center = (ox, oy)
        self._draw_orb(cr, ox, oy, t)

        # captions
        tx = PAD * 2 + ORB
        tw = self._text_width()
        caption = self._caption()
        # when the sentence changes: the old one fades out, then the new one fades in
        if caption != self._cap_text:
            self._cap_prev, self._cap_text, self._cap_changed = self._cap_text, caption, t
        dt = t - self._cap_changed
        cap_alpha = 1.0
        shown = caption
        if not self.reduced_motion and self._cap_prev and caption:
            if dt < FADE_OUT:
                shown, cap_alpha = self._cap_prev, 1 - dt / FADE_OUT
            else:
                cap_alpha = min(1.0, (dt - FADE_OUT) / FADE_IN)

        blocks = []
        if self.user_text:
            blocks.append((self._layout(cr, self.user_text, FONT_USER, tw), PEWTER, 6, 1.0))
        if shown:
            blocks.append((self._layout(cr, shown, FONT_JARVIS, tw), IVORY, 0, cap_alpha))
        else:
            hint = HINTS.get(self.state, "")
            if hint:
                blocks.append((self._layout(cr, hint, FONT_HINT, tw), PEWTER, 0, 1.0))
        total = sum(l.get_pixel_size()[1] + gap for l, _c, gap, _a in blocks)
        y = (h - total) / 2
        for layout, color, gap, alpha in blocks:
            cr.move_to(tx, y)
            cr.set_source_rgba(*color, alpha)
            PangoCairo.show_layout(cr, layout)
            y += layout.get_pixel_size()[1] + gap

        # controls (only the ones that make sense right now)
        self.buttons = {}
        names = []
        if self.state == "speaking":
            names.append("stop")
        if self.state in ("listening", "thinking", "speaking"):
            names.append("close")
        bx = w - PAD - BTN / 2
        for name in reversed(names):
            self.buttons[name] = (bx, h / 2)
            self._draw_button(cr, name, bx, h / 2)
            bx -= BTN + 10

        cr.pop_group_to_source()
        cr.paint_with_alpha(ease)

    def _draw_orb(self, cr, cx, cy, t):
        level = self._level()
        calm = self.reduced_motion

        if self.state == "sleeping":
            breathe = 0.5 if calm else 0.5 + 0.5 * math.sin(t * 2 * math.pi / 4)
            self._glow(cr, cx, cy, 14 + 4 * breathe, EMBER, 0.35 + 0.25 * breathe)
            return

        if self.state == "listening":
            # the core swells with your voice; a soft halo shows the mic is open
            core = 9 + 15 * min(1.0, level)
            self._glow(cr, cx, cy, core + 12, GLACIER, 0.25)
            cr.arc(cx, cy, core, 0, 2 * math.pi)
            cr.set_source_rgba(*GLACIER, 0.95)
            cr.fill()
            if not calm:
                p = (t * 0.6) % 1.0
                cr.arc(cx, cy, 12 + 18 * p, 0, 2 * math.pi)
                cr.set_source_rgba(*GLACIER, 0.35 * (1 - p))
                cr.set_line_width(1.5)
                cr.stroke()
            return

        if self.state == "thinking":
            # three brass beads orbiting, like a pocket watch working
            self._glow(cr, cx, cy, 16, BRASS, 0.18)
            spin = 0 if calm else t * 2.4
            for i in range(3):
                a = spin + i * 2 * math.pi / 3
                r = 20
                bx, by = cx + r * math.cos(a), cy + r * math.sin(a)
                cr.arc(bx, by, 3.2 - i * 0.6, 0, 2 * math.pi)
                cr.set_source_rgba(*BRASS, 1 - i * 0.25)
                cr.fill()
            cr.arc(cx, cy, 6, 0, 2 * math.pi)
            cr.set_source_rgba(*BRASS, 0.9)
            cr.fill()
            return

        # speaking: thin sound waves leaving the core, stronger when the voice is louder
        self._glow(cr, cx, cy, 14 + 12 * level, BRASS, 0.22)
        cr.set_line_width(1.4)
        if calm:
            cr.arc(cx, cy, 10 + 14 * level, 0, 2 * math.pi)
            cr.set_source_rgba(*BRASS, 0.7)
            cr.stroke()
        else:
            for k in range(3):
                p = (t * 0.85 + k / 3) % 1.0
                radius = 8 + 22 * p
                alpha = (1 - p) ** 1.5 * (0.2 + 0.8 * level)
                cr.arc(cx, cy, radius, 0, 2 * math.pi)
                cr.set_source_rgba(*BRASS, alpha)
                cr.stroke()
        cr.arc(cx, cy, 5 + 3.5 * level, 0, 2 * math.pi)
        cr.set_source_rgba(*BRASS, 1)
        cr.fill()

    @staticmethod
    def _glow(cr, cx, cy, radius, color, alpha):
        import cairo
        g = cairo.RadialGradient(cx, cy, 0, cx, cy, radius)
        g.add_color_stop_rgba(0, *color, alpha)
        g.add_color_stop_rgba(1, *color, 0)
        cr.arc(cx, cy, radius, 0, 2 * math.pi)
        cr.set_source(g)
        cr.fill()

    def _draw_button(self, cr, name, cx, cy):
        hovered = self.hover == name
        cr.arc(cx, cy, BTN / 2, 0, 2 * math.pi)
        cr.set_source_rgba(1, 1, 1, 0.12 if hovered else 0.05)
        cr.fill()
        color = IVORY if hovered else PEWTER
        cr.set_source_rgba(*color, 1)
        cr.set_line_width(1.8)
        cr.set_line_cap(1)
        if name == "stop":      # interrupt Jarvis
            s = 5.5
            _rounded_rect(cr, cx - s, cy - s, 2 * s, 2 * s, 2)
            cr.fill()
        else:                   # end the conversation
            s = 5.5
            cr.move_to(cx - s, cy - s)
            cr.line_to(cx + s, cy + s)
            cr.move_to(cx + s, cy - s)
            cr.line_to(cx - s, cy + s)
            cr.stroke()

    # ------------------------------------------------------------ input
    def _hit(self, x, y):
        for name, (bx, by) in self.buttons.items():
            if (x - bx) ** 2 + (y - by) ** 2 <= (BTN / 2 + 3) ** 2:
                return name
        ox, oy = self.orb_center
        if (x - ox) ** 2 + (y - oy) ** 2 <= (ORB / 2) ** 2:
            return "orb"
        return None

    def _set_hover(self, name):
        if name != self.hover:
            self.hover = name
            win = self.area.get_window()
            if win is not None:
                cursor = Gdk.Cursor.new_from_name(self.get_display(), "pointer") if name else None
                win.set_cursor(cursor)
        return False

    def _on_motion(self, _w, event):
        self._set_hover(self._hit(event.x, event.y))

    def _on_click(self, _w, event):
        target = self._hit(event.x, event.y)
        if target == "stop":
            self.assistant.stop_speaking()
        elif target == "close":
            self.assistant.end_conversation()
        elif target == "orb":
            # the orb is the main control: interrupt while speaking, cancel while
            # thinking, talk while idle
            if self.state == "speaking":
                self.assistant.stop_speaking()
            elif self.state == "thinking":
                self.assistant.end_conversation()   # cancels Claude's request
            elif self.state == "sleeping":
                self.assistant.manual_wake.set()
        return True
