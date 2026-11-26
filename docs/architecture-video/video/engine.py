"""
Tiny animation engine for the Jarvis architecture video.

A Scene holds elements (nodes, edges, sequence diagrams, tables, charts...) and
a list of beats. Each beat has narration; the narration audio decides how long
the beat lasts, so pictures and voice stay in sync. A beat reveals items
(`show`), hides them (`hide`), animates data moving along edges (`flow`) and
highlights nodes (`focus`).

Rendering: Cairo + Pango into 1920x1080 frames, piped to ffmpeg.
"""
import math
import re

import cairo
import gi
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Pango, PangoCairo  # noqa: E402

W, H = 1920, 1080
FPS = 24

# ------------------------------------------------------------------ palette
def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


BG = hexrgb("#0E1220")
BG2 = hexrgb("#141A2C")
GRID = hexrgb("#1B2236")
INK = hexrgb("#1A2033")
TEXT = hexrgb("#EDE6D6")
MUTED = hexrgb("#8C93A8")
BRASS = hexrgb("#C9A15B")
GLACIER = hexrgb("#9CC9E3")
VIOLET = hexrgb("#B79CF2")
TEAL = hexrgb("#5CC8A6")
ORANGE = hexrgb("#F0875F")
ROSE = hexrgb("#E8829E")
RED = hexrgb("#E25B5B")
GREEN = hexrgb("#7BC77E")

# component kinds: one visual identity each (color, badge, shape)
KINDS = {
    "local":    dict(color=BRASS,   badge="JARVIS (PYTHON)", shape="rect"),
    "process":  dict(color=hexrgb("#D9C9A3"), badge="SUBPROCESO", shape="rect"),
    "external": dict(color=VIOLET,  badge="SERVICIO EXTERNO", shape="cloud"),
    "storage":  dict(color=TEAL,    badge="ARCHIVO", shape="cylinder"),
    "exec":     dict(color=ORANGE,  badge="COMANDO / SO", shape="terminal"),
    "audio":    dict(color=GLACIER, badge="AUDIO E/S", shape="pill"),
    "ui":       dict(color=ROSE,    badge="INTERFAZ", shape="rect"),
    "actor":    dict(color=TEXT,    badge="", shape="actor"),
    "model":    dict(color=GREEN,   badge="MODELO LOCAL", shape="rect"),
}
LEGEND = [("local", "Jarvis (Python)"), ("process", "Subproceso local"),
          ("model", "Modelo local"), ("external", "Servicio externo"),
          ("storage", "Persistencia"), ("exec", "Comandos / SO"),
          ("audio", "Audio E/S"), ("ui", "Interfaz")]

FONT = "Fira Sans"
MONO = "Fira Mono"


def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


# ------------------------------------------------------------------ text cache
_text_cache = {}


def text_surface(text, size, color=TEXT, width=None, weight="", align="left",
                 font=FONT, italic=False, line_spacing=1.0):
    key = (text, size, color, width, weight, align, font, italic, line_spacing)
    hit = _text_cache.get(key)
    if hit:
        return hit
    probe = cairo.ImageSurface(cairo.FORMAT_ARGB32, 4, 4)
    layout = PangoCairo.create_layout(cairo.Context(probe))
    desc = f"{font} {'Italic ' if italic else ''}{weight + ' ' if weight else ''}{size}"
    layout.set_font_description(Pango.FontDescription.from_string(desc))
    if width:
        layout.set_width(int(width * Pango.SCALE))
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
    if line_spacing != 1.0:
        layout.set_line_spacing(line_spacing)
    layout.set_alignment({"left": Pango.Alignment.LEFT, "center": Pango.Alignment.CENTER,
                          "right": Pango.Alignment.RIGHT}[align])
    layout.set_markup(text, -1) if "<" in text and ">" in text and "</" in text else layout.set_text(text, -1)
    ink, logical = layout.get_pixel_extents()
    tw = max(1, (width or logical.width) + 4)
    th = max(1, logical.height + 4)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(tw), int(th))
    cr = cairo.Context(surf)
    cr.set_source_rgb(*color)
    cr.move_to(2, 2)
    PangoCairo.show_layout(cr, layout)
    _text_cache[key] = (surf, tw, th)
    return _text_cache[key]


def draw_text(cr, x, y, text, size, color=TEXT, alpha=1.0, width=None, weight="",
              align="left", anchor="tl", font=FONT, italic=False, line_spacing=1.0):
    """Draws text; anchor: tl (top-left), tc (top-center), cc (center), cl (center-left)."""
    if alpha <= 0.01 or not text:
        return 0, 0
    surf, tw, th = text_surface(text, size, color, width, weight, align, font, italic, line_spacing)
    if anchor in ("tc", "cc"):
        x -= tw / 2
    if anchor in ("cc", "cl"):
        y -= th / 2
    cr.set_source_surface(surf, x, y)
    cr.paint_with_alpha(alpha)
    return tw, th


def rrect(cr, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def glow(cr, cx, cy, radius, color, alpha):
    g = cairo.RadialGradient(cx, cy, 0, cx, cy, radius)
    g.add_color_stop_rgba(0, *color, alpha)
    g.add_color_stop_rgba(1, *color, 0)
    cr.set_source(g)
    cr.arc(cx, cy, radius, 0, 2 * math.pi)
    cr.fill()


def arrow_head(cr, x, y, angle, size=13):
    cr.move_to(x, y)
    cr.line_to(x - size * math.cos(angle - 0.42), y - size * math.sin(angle - 0.42))
    cr.line_to(x - size * math.cos(angle + 0.42), y - size * math.sin(angle + 0.42))
    cr.close_path()
    cr.fill()


# ------------------------------------------------------------------ elements
class Element:
    """Base: an element with an id; `items` are sub-parts revealed one by one."""
    def __init__(self, id):
        self.id = id
        self.scene = None

    def ids(self):
        return [self.id]

    def alpha(self, t, id=None):
        return self.scene.alpha(id or self.id, t)

    def draw(self, cr, t):
        pass


class Node(Element):
    def __init__(self, id, title, sub="", kind="local", at=(0, 0), w=230, h=86, badge=None,
                 size=21):
        super().__init__(id)
        self.title, self.sub, self.kind = title, sub, kind
        self.cx, self.cy = at
        self.w, self.h = w, h
        self.badge = KINDS[kind]["badge"] if badge is None else badge
        self.size = size
        shape = KINDS[kind]["shape"]
        if shape != "actor":   # grow the box so the text always fits
            need = text_surface(title, size, TEXT, w - 24, "SemiBold", "center")[2] + 22
            need += text_surface(sub, 14, MUTED, w - 20, "", "center")[2] if sub else 0
            need += 15 if self.badge else 0
            need += {"terminal": 12, "cylinder": 12}.get(shape, 0)
            self.h = max(h, need)

    @property
    def rect(self):
        return self.cx - self.w / 2, self.cy - self.h / 2, self.w, self.h

    def border_point(self, tx, ty):
        """Where the line from the center towards (tx, ty) leaves the box."""
        dx, dy = tx - self.cx, ty - self.cy
        if dx == 0 and dy == 0:
            return self.cx, self.cy
        sx = (self.w / 2 + 6) / abs(dx) if dx else 1e9
        sy = (self.h / 2 + 6) / abs(dy) if dy else 1e9
        s = min(sx, sy)
        return self.cx + dx * s, self.cy + dy * s

    def draw(self, cr, t):
        a = self.alpha(t)
        if a <= 0.01:
            return
        k = KINDS[self.kind]
        col = k["color"]
        x, y, w, h = self.rect
        f = self.scene.focus_level(self.id, t)
        if f > 0:
            glow(cr, self.cx, self.cy, max(w, h) * 0.85, col, 0.32 * f * a)
        cr.save()
        shape = k["shape"]
        cr.set_line_width(2.4 if f > 0.2 else 1.8)
        if shape == "actor":
            cr.set_source_rgba(*col, a)
            cr.arc(self.cx, y + 22, 15, 0, 2 * math.pi)
            cr.stroke()
            cr.arc(self.cx, y + 78, 30, math.pi, 2 * math.pi)
            cr.stroke()
            draw_text(cr, self.cx, y + h - 6, self.title, self.size - 1, TEXT, a, anchor="tc",
                      weight="Medium")
            cr.restore()
            return
        if shape == "pill":
            rrect(cr, x, y, w, h, h / 2)
        elif shape == "cylinder":
            e = 12
            cr.move_to(x, y + e)
            cr.curve_to(x, y - e / 3, x + w, y - e / 3, x + w, y + e)
            cr.line_to(x + w, y + h - e)
            cr.curve_to(x + w, y + h + e / 3, x, y + h + e / 3, x, y + h - e)
            cr.close_path()
        else:
            rrect(cr, x, y, w, h, 12)
        cr.set_source_rgba(*INK, 0.96 * a)
        cr.fill_preserve()
        cr.set_source_rgba(*col, a)
        if shape == "cloud":
            cr.set_dash([9, 6])
        cr.stroke()
        cr.set_dash([])
        if shape == "cylinder":
            e = 12
            cr.move_to(x, y + e)
            cr.curve_to(x, y + e * 1.9, x + w, y + e * 1.9, x + w, y + e)
            cr.set_source_rgba(*col, 0.7 * a)
            cr.stroke()
        if shape == "terminal":
            cr.rectangle(x + 1, y + 1, w - 2, 16)
            cr.set_source_rgba(*col, 0.25 * a)
            cr.fill()
            for i, c in enumerate((RED, BRASS, GREEN)):
                cr.arc(x + 12 + i * 13, y + 9, 3.5, 0, 2 * math.pi)
                cr.set_source_rgba(*c, a)
                cr.fill()
        cr.restore()
        top = y + {"terminal": 22, "cylinder": 20}.get(shape, 10)
        if self.badge:
            draw_text(cr, x + 14, top, self.badge, 10, col, 0.85 * a, weight="Bold")
            top += 15
        body_h = h - (top - y)
        tsurf = text_surface(self.title, self.size, TEXT, w - 24, "SemiBold", "center")
        ssurf = text_surface(self.sub, 14, MUTED, w - 20, "", "center") if self.sub else None
        total = tsurf[2] + (ssurf[2] if ssurf else 0)
        ty = top + max(0, (body_h - total) / 2) - 2
        draw_text(cr, self.cx, ty, self.title, self.size, TEXT, a, width=w - 24,
                  weight="SemiBold", align="center", anchor="tc")
        if ssurf:
            draw_text(cr, self.cx, ty + tsurf[2] - 2, self.sub, 14, MUTED, a, width=w - 20,
                      align="center", anchor="tc")


class Group(Element):
    """A container box (e.g. the jarvis.py process)."""
    def __init__(self, id, title, rect, kind="local"):
        super().__init__(id)
        self.title, self.r, self.kind = title, rect, kind

    def draw(self, cr, t):
        a = self.alpha(t)
        if a <= 0.01:
            return
        x, y, w, h = self.r
        col = KINDS[self.kind]["color"]
        rrect(cr, x, y, w, h, 20)
        cr.set_source_rgba(*col, 0.05 * a)
        cr.fill_preserve()
        cr.set_source_rgba(*col, 0.55 * a)
        cr.set_line_width(1.5)
        cr.set_dash([4, 5])
        cr.stroke()
        cr.set_dash([])
        draw_text(cr, x + 18, y + 10, self.title, 15, col, 0.9 * a, weight="Bold")


class Edge(Element):
    def __init__(self, id, a, b, label="", color=None, dashed=False, bend=0, both=False,
                 lpos=0.5, loff=(0, -16), width=2.0):
        super().__init__(id)
        self.a, self.b, self.label = a, b, label
        self.color, self.dashed, self.bend, self.both = color, dashed, bend, both
        self.lpos, self.loff, self.width = lpos, loff, width

    def geometry(self):
        na, nb = self.scene.get(self.a), self.scene.get(self.b)
        p0 = na.border_point(nb.cx, nb.cy)
        p3 = nb.border_point(na.cx, na.cy)
        mx, my = (p0[0] + p3[0]) / 2, (p0[1] + p3[1]) / 2
        dx, dy = p3[0] - p0[0], p3[1] - p0[1]
        ln = math.hypot(dx, dy) or 1
        nx, ny = -dy / ln, dx / ln
        c = (mx + nx * self.bend, my + ny * self.bend)
        return p0, c, p3

    @staticmethod
    def point(g, u):
        (x0, y0), (cx, cy), (x1, y1) = g
        x = (1 - u) ** 2 * x0 + 2 * (1 - u) * u * cx + u * u * x1
        y = (1 - u) ** 2 * y0 + 2 * (1 - u) * u * cy + u * u * y1
        return x, y

    def draw(self, cr, t):
        a = self.alpha(t)
        if a <= 0.01:
            return
        g = self.geometry()
        col = self.color or MUTED
        flowing = self.scene.flow_level(self.id, t)
        cr.set_source_rgba(*col, (0.55 + 0.45 * flowing) * a)
        cr.set_line_width(self.width + 0.8 * flowing)
        if self.dashed:
            cr.set_dash([8, 6])
        (x0, y0), (cx, cy), (x1, y1) = g
        cr.move_to(x0, y0)
        cr.curve_to(x0 + 2 / 3 * (cx - x0), y0 + 2 / 3 * (cy - y0),
                    x1 + 2 / 3 * (cx - x1), y1 + 2 / 3 * (cy - y1), x1, y1)
        cr.stroke()
        cr.set_dash([])
        ex, ey = self.point(g, 0.97)
        arrow_head(cr, x1, y1, math.atan2(y1 - ey, x1 - ex))
        if self.both:
            sx, sy = self.point(g, 0.03)
            arrow_head(cr, x0, y0, math.atan2(y0 - sy, x0 - sx))
        if self.label:
            lx, ly = self.point(g, self.lpos)
            surf, tw, th = text_surface(self.label, 14, TEXT)
            bx, by = lx + self.loff[0] - tw / 2, ly + self.loff[1] - th / 2
            rrect(cr, bx - 6, by - 2, tw + 12, th + 4, 7)
            cr.set_source_rgba(*BG, 0.9 * a)
            cr.fill()
            draw_text(cr, bx, by, self.label, 14, TEXT, 0.95 * a)

    def draw_packets(self, cr, t):
        for start, end, tag, color in self.scene.flows_for(self.id):
            if not (start <= t <= end + 1.4):
                continue
            g = self.geometry()
            k = 0
            while True:
                t0 = start + k * 1.0
                if t0 > end or t0 > t:
                    break
                u = (t - t0) / 1.3
                k += 1
                if 0 <= u <= 1:
                    x, y = self.point(g, ease(u) * 0.94 + 0.03)
                    col = color or self.color or BRASS
                    glow(cr, x, y, 18, col, 0.55)
                    cr.arc(x, y, 5.5, 0, 2 * math.pi)
                    cr.set_source_rgb(*col)
                    cr.fill()
                    if tag:
                        surf, tw, th = text_surface(tag, 13, BG, weight="Bold")
                        rrect(cr, x + 10, y - 26, tw + 10, th + 2, 6)
                        cr.set_source_rgba(*col, 0.95)
                        cr.fill()
                        draw_text(cr, x + 15, y - 25, tag, 13, BG, 1, weight="Bold")


class Panel(Element):
    """Titled list of bullets; each bullet is revealed by its own id."""
    def __init__(self, id, title, bullets, rect, size=20, color=BRASS):
        super().__init__(id)
        self.title, self.r, self.size, self.color = title, rect, size, color
        self.bullets = [(f"{id}.{i}", b) for i, b in enumerate(bullets)]

    def ids(self):
        return [self.id] + [b[0] for b in self.bullets]

    def draw(self, cr, t):
        a = self.alpha(t)
        if a <= 0.01:
            return
        x, y, w, h = self.r
        rrect(cr, x, y, w, h, 16)
        cr.set_source_rgba(*BG2, 0.92 * a)
        cr.fill_preserve()
        cr.set_source_rgba(*self.color, 0.35 * a)
        cr.set_line_width(1.2)
        cr.stroke()
        cy = y + 18
        if self.title:
            draw_text(cr, x + 22, cy, self.title, self.size + 2, self.color, a, weight="SemiBold",
                      width=w - 40)
            cy += text_surface(self.title, self.size + 2, self.color, w - 40, "SemiBold")[2] + 10
        for bid, text in self.bullets:
            ba = self.alpha(t, bid) * a
            if ba <= 0.01:
                continue
            f = self.scene.focus_level(bid, t)
            col = TEXT if f < 0.2 else hexrgb("#FFF3D6")
            cr.arc(x + 30, cy + self.size * 0.72, 4, 0, 2 * math.pi)
            cr.set_source_rgba(*self.color, ba)
            cr.fill()
            _, th = draw_text(cr, x + 46, cy, text, self.size, col, ba, width=w - 70)
            cy += th + 8


class Code(Element):
    def __init__(self, id, title, lines, rect, size=17, notes=None):
        super().__init__(id)
        self.title, self.lines, self.r, self.size = title, lines, rect, size
        self.notes = notes or {}   # line index -> (id, text) annotation revealed separately

    def ids(self):
        return [self.id] + [n[0] for n in self.notes.values()]

    def draw(self, cr, t):
        a = self.alpha(t)
        if a <= 0.01:
            return
        x, y, w, h = self.r
        rrect(cr, x, y, w, h, 14)
        cr.set_source_rgba(*hexrgb("#0A0D17"), 0.97 * a)
        cr.fill_preserve()
        cr.set_source_rgba(*MUTED, 0.4 * a)
        cr.set_line_width(1)
        cr.stroke()
        if self.title:
            draw_text(cr, x + 18, y + 10, self.title, 14, MUTED, a, weight="Bold")
        ly = y + 40
        lh = self.size * 1.62
        for i, line in enumerate(self.lines):
            nid = self.notes.get(i)
            hl = self.scene.alpha(nid[0], t) if nid else 0
            if hl > 0.01:
                cr.rectangle(x + 8, ly - 3, w - 16, lh)
                cr.set_source_rgba(*BRASS, 0.13 * hl * a)
                cr.fill()
            col = GLACIER if line.lstrip().startswith("--") else TEXT
            if line.lstrip().startswith("#"):
                col = MUTED
            draw_text(cr, x + 20, ly, line, self.size, col, a, font=MONO)
            if nid and hl > 0.01:
                draw_text(cr, x + w + 18, ly - 1, "← " + nid[1], 16, BRASS, hl * a,
                          width=1880 - (x + w + 18))
            ly += lh


class Sequence(Element):
    """Sequence diagram: participants across, messages revealed one by one. Row
    heights follow each label, so long labels never overlap the next message."""
    def __init__(self, id, parts, msgs, rect, top=70, step=None, size=15):
        super().__init__(id)
        self.parts = parts      # [(pid, label, kind)]
        self.msgs = msgs        # [(mid, from, to, label, style)] style: "" | "dash" | "note" | "err" | "exec"
        self.r, self.top, self.size = rect, top, size
        x, y, w, h = rect
        n = len(parts)
        self.px = {p[0]: x + w * (i + 0.5) / n for i, p in enumerate(parts)}
        self.layout = []        # per message: (y, label x, label width, align)
        cy = y + top + 10
        min_step = step or 50
        for mid, fr, to, label, style in msgs:
            lx, lw, align = self._label_box(fr, to, style)
            th = text_surface(label, size, TEXT, lw, "SemiBold" if style == "note" else "", align)[2]
            row = max(min_step, th + (34 if style == "note" else 30))
            ymsg = cy + row - (14 if style != "note" else row / 2)
            self.layout.append((ymsg, lx, lw, align, th))
            cy += row

    def _label_box(self, fr, to, style):
        x, y, w, h = self.r
        x0, x1 = self.px[fr], self.px[to]
        if style == "note":
            lw = 520
            lx = min(max(x + 10, (x0 if fr == to else (x0 + x1) / 2) - lw / 2), x + w - lw - 10)
            return lx, lw, "left"
        if fr == to:
            avail = x + w - (x0 + 50) - 10
            if avail >= 280:
                return x0 + 50, min(400, avail), "left"
            lw = min(400, x0 - 50 - x - 10)
            return x0 - 50 - lw, lw, "right"
        lw = max(300, abs(x1 - x0) - 16)
        return (x0 + x1) / 2 - lw / 2, lw, "center"

    def ids(self):
        return [self.id] + [m[0] for m in self.msgs]

    def draw(self, cr, t):
        a = self.alpha(t)
        if a <= 0.01:
            return
        x, y, w, h = self.r
        pw = min(220, w / len(self.parts) - 16)
        for pid, label, kind in self.parts:
            px = self.px[pid]
            col = KINDS[kind]["color"]
            rrect(cr, px - pw / 2, y, pw, 54, 10)
            cr.set_source_rgba(*INK, a)
            cr.fill_preserve()
            cr.set_source_rgba(*col, a)
            cr.set_line_width(1.6)
            if KINDS[kind]["shape"] == "cloud":
                cr.set_dash([7, 5])
            cr.stroke()
            cr.set_dash([])
            draw_text(cr, px, y + 27, label, 16, TEXT, a, width=pw - 10, align="center",
                      anchor="cc", weight="SemiBold")
            cr.move_to(px, y + 56)
            cr.line_to(px, y + h)
            cr.set_source_rgba(*col, 0.3 * a)
            cr.set_line_width(1.2)
            cr.set_dash([3, 5])
            cr.stroke()
            cr.set_dash([])
        for (mid, fr, to, label, style), (my, lx, lw, align, th) in zip(self.msgs, self.layout):
            ma = self.alpha(t, mid) * a
            if ma > 0.01:
                prog = ease((t - self.scene.reveal_time(mid)) / 0.7)
                self._msg(cr, my, fr, to, label, style, ma, prog, self.scene.focus_level(mid, t),
                          lx, lw, align, th)

    def _msg(self, cr, y, fr, to, label, style, a, prog, focus, lx, lw, align, th):
        x0, x1 = self.px[fr], self.px[to]
        col = {"dash": GLACIER, "note": BRASS, "err": RED, "exec": ORANGE}.get(style, TEXT)
        if style == "note":
            surf, tw, _ = text_surface(label, self.size, BG, lw, "SemiBold")
            bx = lx + (lw - tw) / 2
            rrect(cr, bx - 8, y - th / 2 - 4, tw + 16, th + 8, 8)
            cr.set_source_rgba(*BRASS, 0.92 * a)
            cr.fill()
            draw_text(cr, bx, y - th / 2, label, self.size, BG, a, width=lw, weight="SemiBold")
            return
        if fr == to:
            d = 1 if align == "left" else -1
            cr.set_source_rgba(*col, a)
            cr.set_line_width(1.8)
            cr.move_to(x0, y - 8)
            cr.line_to(x0 + 40 * d, y - 8)
            cr.line_to(x0 + 40 * d, y + 10)
            cr.line_to(x0 + 4 * d, y + 10)
            cr.stroke()
            arrow_head(cr, x0 + 2 * d, y + 10, math.pi if d > 0 else 0, 10)
            surf, tw, _ = text_surface(label, self.size, TEXT, lw, "", align)
            tx = lx if align == "left" else lx + lw - tw
            draw_text(cr, tx, y + 1 - th / 2, label, self.size, TEXT, a, width=lw, align=align)
            return
        xe = x0 + (x1 - x0) * prog
        cr.set_source_rgba(*col, a)
        cr.set_line_width(2.2 if focus > 0.2 else 1.8)
        if style == "dash":
            cr.set_dash([7, 5])
        cr.move_to(x0, y)
        cr.line_to(xe, y)
        cr.stroke()
        cr.set_dash([])
        if prog > 0.98:
            arrow_head(cr, x1, y, 0 if x1 > x0 else math.pi, 11)
        else:
            glow(cr, xe, y, 14, col, 0.6)
        draw_text(cr, lx, y - th - 2, label, self.size, TEXT, a * min(1, prog * 1.5), width=lw,
                  align="center")


class Table(Element):
    def __init__(self, id, cols, rows, rect, widths=None, size=17, head_color=BRASS):
        super().__init__(id)
        self.cols, self.r, self.size, self.head_color = cols, rect, size, head_color
        self.rows = [(f"{id}.{i}", r) for i, r in enumerate(rows)]
        tot = sum(widths) if widths else len(cols)
        self.widths = [wd / tot for wd in widths] if widths else [1 / len(cols)] * len(cols)

    def ids(self):
        return [self.id] + [r[0] for r in self.rows]

    def draw(self, cr, t):
        a = self.alpha(t)
        if a <= 0.01:
            return
        x, y, w, h = self.r
        xs = [x]
        for f in self.widths:
            xs.append(xs[-1] + f * w)
        for i, c in enumerate(self.cols):
            draw_text(cr, xs[i] + 12, y, c, self.size, self.head_color, a, weight="Bold",
                      width=xs[i + 1] - xs[i] - 20)
        cy = y + self.size * 2.1
        cr.move_to(x, cy - 8)
        cr.line_to(x + w, cy - 8)
        cr.set_source_rgba(*self.head_color, 0.5 * a)
        cr.set_line_width(1.2)
        cr.stroke()
        for rid, row in self.rows:
            ra = self.alpha(t, rid) * a
            hmax = 0
            for i, cell in enumerate(row):
                if ra > 0.01:
                    col = TEXT if i else hexrgb("#FFF3D6")
                    _, th = draw_text(cr, xs[i] + 12, cy, cell, self.size - (0 if i else 0), col,
                                      ra, width=xs[i + 1] - xs[i] - 22,
                                      weight="SemiBold" if i == 0 else "")
                else:
                    th = text_surface(cell, self.size, TEXT, xs[i + 1] - xs[i] - 22)[2]
                hmax = max(hmax, th)
            if self.scene.focus_level(rid, t) > 0.05 and ra > 0.01:
                f = self.scene.focus_level(rid, t)
                rrect(cr, x - 4, cy - 6, w + 8, hmax + 10, 8)
                cr.set_source_rgba(*BRASS, 0.10 * f * ra)
                cr.fill()
            cy += hmax + 14
            if ra > 0.01:
                cr.move_to(x, cy - 7)
                cr.line_to(x + w, cy - 7)
                cr.set_source_rgba(*MUTED, 0.18 * ra)
                cr.set_line_width(1)
                cr.stroke()


class Series(Element):
    """Bar series (e.g. wake scores per 80 ms chunk) drawn progressively."""
    def __init__(self, id, title, values, rect, lines=(), labels=None, color=GLACIER,
                 ymax=1.0, regions=(), xlabel=""):
        super().__init__(id)
        self.title, self.values, self.r = title, values, rect
        self.lines = lines          # [(value, label, color)]
        self.labels = labels or {}  # index -> text
        self.color, self.ymax, self.regions, self.xlabel = color, ymax, regions, xlabel
        # regions: [(id, i0, i1, label, color)] revealed separately

    def ids(self):
        return [self.id] + [rg[0] for rg in self.regions]

    def draw(self, cr, t):
        a = self.alpha(t)
        if a <= 0.01:
            return
        x, y, w, h = self.r
        draw_text(cr, x, y - 34, self.title, 18, TEXT, a, weight="SemiBold")
        base = y + h
        cr.set_source_rgba(*MUTED, 0.5 * a)
        cr.set_line_width(1)
        cr.move_to(x, base)
        cr.line_to(x + w, base)
        cr.stroke()
        n = len(self.values)
        bw = w / n
        for rid, i0, i1, label, col in self.regions:
            ra = self.alpha(t, rid) * a
            if ra > 0.01:
                cr.rectangle(x + i0 * bw, y, (i1 - i0) * bw, h)
                cr.set_source_rgba(*col, 0.12 * ra)
                cr.fill()
                draw_text(cr, x + (i0 + i1) / 2 * bw, y + 6, label, 14, col, ra, anchor="tc",
                          width=max(80, (i1 - i0) * bw - 6), align="center", weight="SemiBold")
        prog = ease((t - self.scene.reveal_time(self.id)) / max(0.5, self.scene.span(self.id)))
        shown = int(n * prog)
        for i, v in enumerate(self.values[:shown]):
            vh = h * min(1, v / self.ymax)
            col = self.color
            for val, _l, c in self.lines:
                if v >= val:
                    col = c
            cr.rectangle(x + i * bw + 1.5, base - vh, bw - 3, vh)
            cr.set_source_rgba(*col, 0.9 * a)
            cr.fill()
            if i in self.labels:
                draw_text(cr, x + (i + 0.5) * bw, base + 6, self.labels[i], 13, MUTED, a,
                          anchor="tc")
        for val, label, c in self.lines:
            ly = base - h * val / self.ymax
            cr.set_source_rgba(*c, 0.8 * a)
            cr.set_dash([6, 5])
            cr.move_to(x, ly)
            cr.line_to(x + w, ly)
            cr.stroke()
            cr.set_dash([])
            draw_text(cr, x + w + 10, ly, label, 14, c, a, anchor="cl")
        if self.xlabel:
            draw_text(cr, x + w / 2, base + 28, self.xlabel, 14, MUTED, a, anchor="tc")


class Lanes(Element):
    """Concurrent activity: one row per thread/process, segments revealed by id."""
    def __init__(self, id, lanes, segs, rect, tmax=10, label_w=300, axis=""):
        super().__init__(id)
        self.lanes = lanes          # [(lid, label, kind)]
        self.segs = segs            # [(sid, lid, t0, t1, label, color or None)]
        self.r, self.tmax, self.label_w, self.axis = rect, tmax, label_w, axis

    def ids(self):
        return [self.id] + [s[0] for s in self.segs]

    def draw(self, cr, t):
        a = self.alpha(t)
        if a <= 0.01:
            return
        x, y, w, h = self.r
        lh = h / len(self.lanes)
        ly = {}
        for i, (lid, label, kind) in enumerate(self.lanes):
            cy = y + i * lh
            ly[lid] = cy
            col = KINDS[kind]["color"]
            draw_text(cr, x, cy + lh / 2, label, 16, col, a, anchor="cl", width=self.label_w - 14,
                      weight="SemiBold")
            cr.move_to(x + self.label_w, cy + lh / 2)
            cr.line_to(x + w, cy + lh / 2)
            cr.set_source_rgba(*col, 0.18 * a)
            cr.set_line_width(1)
            cr.stroke()
        tw = w - self.label_w
        for sid, lid, t0, t1, label, color in self.segs:
            sa = self.alpha(t, sid) * a
            if sa <= 0.01:
                continue
            kind = next(l[2] for l in self.lanes if l[0] == lid)
            col = color or KINDS[kind]["color"]
            prog = ease((t - self.scene.reveal_time(sid)) / 0.6)
            sx = x + self.label_w + tw * t0 / self.tmax
            sw = tw * (t1 - t0) / self.tmax * prog
            cy = ly[lid] + lh * 0.2
            rrect(cr, sx, cy, max(4, sw), lh * 0.6, 7)
            cr.set_source_rgba(*col, 0.28 * sa)
            cr.fill_preserve()
            cr.set_source_rgba(*col, 0.9 * sa)
            cr.set_line_width(1.4)
            cr.stroke()
            if label and prog > 0.6:
                draw_text(cr, sx + 8, cy + lh * 0.3, label, 14, TEXT, sa, anchor="cl",
                          width=max(60, sw - 10))
        if self.axis:
            draw_text(cr, x + self.label_w + tw / 2, y + h + 6, self.axis, 14, MUTED, a,
                      anchor="tc")


class Bars(Element):
    """Horizontal resource bars."""
    def __init__(self, id, title, bars, rect, size=18):
        super().__init__(id)
        self.title, self.r, self.size = title, rect, size
        self.bars = [(f"{id}.{i}",) + tuple(b) for i, b in enumerate(bars)]
        # (bid, label, value, vmax, text, color)

    def ids(self):
        return [self.id] + [b[0] for b in self.bars]

    def draw(self, cr, t):
        a = self.alpha(t)
        if a <= 0.01:
            return
        x, y, w, h = self.r
        draw_text(cr, x, y, self.title, self.size + 2, TEXT, a, weight="SemiBold")
        by = y + 46
        step = (h - 46) / max(1, len(self.bars))
        for bid, label, value, vmax, text, color in self.bars:
            ba = self.alpha(t, bid) * a
            if ba > 0.01:
                prog = ease((t - self.scene.reveal_time(bid)) / 0.9)
                draw_text(cr, x, by, label, self.size - 2, MUTED, ba)
                bx, bw = x, w
                rrect(cr, bx, by + 26, bw, 18, 9)
                cr.set_source_rgba(*GRID, ba)
                cr.fill()
                fw = max(6, bw * min(1, value / vmax) * prog)
                rrect(cr, bx, by + 26, fw, 18, 9)
                cr.set_source_rgba(*color, 0.9 * ba)
                cr.fill()
                surf, tw_, th_ = text_surface(text, self.size - 2, color, weight="SemiBold")
                draw_text(cr, x + w - tw_, by, text, self.size - 2, color, ba, weight="SemiBold")
            by += step


class Orb(Element):
    """The Jarvis bubble orb in one of its states (same drawing as jarvis_ui.py)."""
    def __init__(self, id, state, at, label="", sub="", scale=1.6, level=None):
        super().__init__(id)
        self.state, (self.cx, self.cy), self.label, self.sub = state, at, label, sub
        self.scale, self.level = scale, level

    def draw(self, cr, t):
        a = self.alpha(t)
        if a <= 0.01:
            return
        cx, cy, s = self.cx, self.cy, self.scale
        f = self.scene.focus_level(self.id, t)
        rrect(cr, cx - 70 * s, cy - 50 * s, 140 * s, 100 * s, 22 * s)
        cr.set_source_rgba(*hexrgb("#121626"), 0.95 * a)
        cr.fill_preserve()
        cr.set_source_rgba(*BRASS, (0.3 + 0.5 * f) * a)
        cr.set_line_width(1.2 + 1.5 * f)
        cr.stroke()
        level = self.level if self.level is not None else 0.5 + 0.5 * math.sin(t * 5.3) * math.sin(t * 2.1)
        cr.save()
        cr.translate(cx, cy)
        cr.scale(s, s)
        st = self.state
        ember, glac = hexrgb("#6E5A3A"), GLACIER
        if st == "sleeping":
            br = 0.5 + 0.5 * math.sin(t * 2 * math.pi / 4)
            glow(cr, 0, 0, 14 + 4 * br, ember, (0.35 + 0.25 * br) * a)
        elif st == "listening":
            core = 9 + 15 * min(1.0, abs(level))
            glow(cr, 0, 0, core + 12, glac, 0.25 * a)
            cr.arc(0, 0, core, 0, 2 * math.pi)
            cr.set_source_rgba(*glac, 0.95 * a)
            cr.fill()
            p = (t * 0.6) % 1.0
            cr.arc(0, 0, 12 + 18 * p, 0, 2 * math.pi)
            cr.set_source_rgba(*glac, 0.35 * (1 - p) * a)
            cr.set_line_width(1.5)
            cr.stroke()
        elif st == "thinking":
            glow(cr, 0, 0, 16, BRASS, 0.18 * a)
            for i in range(3):
                ang = t * 2.4 + i * 2 * math.pi / 3
                cr.arc(20 * math.cos(ang), 20 * math.sin(ang), 3.2 - i * 0.6, 0, 2 * math.pi)
                cr.set_source_rgba(*BRASS, (1 - i * 0.25) * a)
                cr.fill()
            cr.arc(0, 0, 6, 0, 2 * math.pi)
            cr.set_source_rgba(*BRASS, 0.9 * a)
            cr.fill()
        else:
            lv = abs(level)
            glow(cr, 0, 0, 14 + 12 * lv, BRASS, 0.22 * a)
            cr.set_line_width(1.4)
            for k in range(3):
                p = (t * 0.85 + k / 3) % 1.0
                cr.arc(0, 0, 8 + 22 * p, 0, 2 * math.pi)
                cr.set_source_rgba(*BRASS, (1 - p) ** 1.5 * (0.2 + 0.8 * lv) * a)
                cr.stroke()
            cr.arc(0, 0, 5 + 3.5 * lv, 0, 2 * math.pi)
            cr.set_source_rgba(*BRASS, a)
            cr.fill()
        cr.restore()
        if self.label:
            draw_text(cr, cx, cy + 58 * s, self.label, 20, TEXT, a, anchor="tc", weight="SemiBold")
        if self.sub:
            draw_text(cr, cx, cy + 58 * s + 30, self.sub, 15, MUTED, a, anchor="tc",
                      width=150 * s + 60, align="center")


class Terminal(Element):
    """A mock of the activity terminal window."""
    def __init__(self, id, title, lines, rect, size=17):
        super().__init__(id)
        self.title, self.r, self.size = title, rect, size
        self.lines = [(f"{id}.{i}",) + tuple(l) for i, l in enumerate(lines)]  # (lid, text, color)

    def ids(self):
        return [self.id] + [l[0] for l in self.lines]

    def draw(self, cr, t):
        a = self.alpha(t)
        if a <= 0.01:
            return
        x, y, w, h = self.r
        rrect(cr, x, y, w, h, 12)
        cr.set_source_rgba(*hexrgb("#0B0E14"), 0.97 * a)
        cr.fill_preserve()
        cr.set_source_rgba(*MUTED, 0.5 * a)
        cr.set_line_width(1.2)
        cr.stroke()
        cr.rectangle(x + 1, y + 1, w - 2, 34)
        cr.set_source_rgba(*hexrgb("#1A1F2B"), a)
        cr.fill()
        draw_text(cr, x + w / 2, y + 17, self.title, 15, TEXT, a, anchor="cc", weight="Bold")
        ly = y + 50
        for lid, text, color in self.lines:
            la = self.alpha(t, lid) * a
            if la > 0.01:
                _, th = draw_text(cr, x + 18, ly, text, self.size, color, la, font=MONO,
                                  width=w - 36)
            else:
                th = text_surface(text, self.size, color, w - 36, font=MONO)[2]
            ly += th + 4


class Caption(Element):
    """Free text block (titles, callouts)."""
    def __init__(self, id, text, at, size=22, color=TEXT, width=None, anchor="tl",
                 weight="", align="left", box=False, italic=False):
        super().__init__(id)
        self.text, self.at, self.size, self.color = text, at, size, color
        self.width, self.anchor, self.weight, self.align = width, anchor, weight, align
        self.box, self.italic = box, italic

    def draw(self, cr, t):
        a = self.alpha(t)
        if a <= 0.01:
            return
        x, y = self.at
        if self.box:
            surf, tw, th = text_surface(self.text, self.size, self.color, self.width,
                                        self.weight, self.align, italic=self.italic)
            bx = x - (tw / 2 if self.anchor in ("tc", "cc") else 0)
            by = y - (th / 2 if self.anchor in ("cc", "cl") else 0)
            rrect(cr, bx - 14, by - 10, tw + 28, th + 20, 12)
            cr.set_source_rgba(*BG2, 0.95 * a)
            cr.fill_preserve()
            cr.set_source_rgba(*self.color, 0.6 * a)
            cr.set_line_width(1.3)
            cr.stroke()
        draw_text(cr, x, y, self.text, self.size, self.color, a, width=self.width,
                  anchor=self.anchor, weight=self.weight, align=self.align, italic=self.italic)


# ------------------------------------------------------------------ scene
class Scene:
    def __init__(self, chapter, title, kind="diagram", subtitle=""):
        self.chapter, self.title, self.kind, self.subtitle = chapter, title, kind, subtitle
        self.elements = []
        self.by_id = {}
        self.beats = []        # dicts with say, show, hide, flow, focus
        self.timeline = {}     # id -> (reveal_t, hide_t)
        self.flows = {}        # edge id -> [(start, end, tag, color)]
        self.focus = {}        # id -> [(start, end)]
        self.duration = 0.0
        self.t0 = 0.0          # global start, for the progress bar

    # building
    def add(self, el):
        el.scene = self
        self.elements.append(el)
        self.by_id[el.id] = el
        return el

    def node(self, *a, **k):
        return self.add(Node(*a, **k))

    def edge(self, *a, **k):
        return self.add(Edge(*a, **k))

    def beat(self, say, show=(), hide=(), flow=(), focus=(), pause=0.4, min_dur=0.0):
        self.beats.append(dict(say=say, show=list(show), hide=list(hide), flow=list(flow),
                               focus=list(focus), pause=pause, min_dur=min_dur))

    def get(self, id):
        return self.by_id[id]

    def all_ids(self):
        out = []
        for e in self.elements:
            out += e.ids()
        return out

    # timing (durations come from the narration audio)
    def schedule(self, durations):
        t = 0.0
        for beat, d in zip(self.beats, durations):
            beat["t"], beat["d"] = t, d
            for i, sid in enumerate(self._expand(beat["show"])):
                if sid not in self.timeline:
                    self.timeline[sid] = [t + 0.15 + 0.12 * i, None, d]
            for sid in self._expand(beat["hide"]):
                if sid in self.timeline:
                    self.timeline[sid][1] = t
            for f in beat["flow"]:
                eid, tag, color = (f, "", None) if isinstance(f, str) else (tuple(f) + (None,))[:3]
                self.flows.setdefault(eid, []).append((t + 0.2, t + d - 1.2, tag, color))
            for fid in self._expand(beat["focus"]):
                self.focus.setdefault(fid, []).append((t, t + d))
            t += d
        self.duration = t

    def _expand(self, ids):
        out = []
        for i in ids:
            if i.endswith(".*"):
                base = i[:-2]
                el = self.by_id.get(base)
                out += el.ids() if el else []
            else:
                out.append(i)
        return out

    def reveal_time(self, id):
        return self.timeline.get(id, [1e9])[0]

    def span(self, id):
        return self.timeline.get(id, [0, None, 1])[2]

    def alpha(self, id, t):
        tl = self.timeline.get(id)
        if not tl:
            return 0.0
        a = ease((t - tl[0]) / 0.5)
        if tl[1] is not None:
            a *= 1 - ease((t - tl[1]) / 0.4)
        return a

    def focus_level(self, id, t):
        lvl = 0.0
        for s, e in self.focus.get(id, ()):
            if s <= t <= e + 0.5:
                lvl = max(lvl, ease((t - s) / 0.4) * (1 - ease((t - e) / 0.5)))
        return lvl * (0.75 + 0.25 * math.sin(t * 4))

    def flow_level(self, id, t):
        return 1.0 if any(s - 0.2 <= t <= e + 1.2 for s, e, *_ in self.flows.get(id, ())) else 0.0

    def flows_for(self, id):
        return self.flows.get(id, ())

    # drawing
    def draw(self, cr, t, toc, total, extra=None):
        draw_background(cr)
        if self.kind not in ("title",):
            draw_header(cr, self, t, toc, total)
        for el in self.elements:
            if isinstance(el, (Group,)):
                el.draw(cr, t)
        for el in self.elements:
            if isinstance(el, Edge):
                el.draw(cr, t)
        for el in self.elements:
            if not isinstance(el, (Edge, Group)):
                el.draw(cr, t)
        for el in self.elements:
            if isinstance(el, Edge):
                el.draw_packets(cr, t)
        if self.kind not in ("title",) and getattr(self, "legend", True):
            draw_legend(cr, self)


def draw_background(cr):
    cr.set_source_rgb(*BG)
    cr.paint()
    g = cairo.RadialGradient(W * 0.5, H * 0.45, 100, W * 0.5, H * 0.5, W * 0.75)
    g.add_color_stop_rgba(0, *BG2, 0.9)
    g.add_color_stop_rgba(1, *BG, 0)
    cr.set_source(g)
    cr.paint()
    cr.set_source_rgba(*GRID, 0.35)
    cr.set_line_width(1)
    for gx in range(0, W, 60):
        cr.move_to(gx + 0.5, 110)
        cr.line_to(gx + 0.5, H - 70)
    for gy in range(110, H - 70, 60):
        cr.move_to(0, gy + 0.5)
        cr.line_to(W, gy + 0.5)
    cr.stroke()


def draw_header(cr, scene, t, toc, total):
    cr.set_source_rgba(*hexrgb("#0A0D17"), 0.92)
    cr.rectangle(0, 0, W, 96)
    cr.fill()
    label = f"CAPÍTULO {scene.chapter}" if str(scene.chapter).isdigit() else str(scene.chapter).upper()
    draw_text(cr, 60, 18, label, 15, BRASS, 1, weight="Bold")
    draw_text(cr, 60, 40, scene.title, 30, TEXT, 1, weight="SemiBold")
    surf, tw, th = text_surface("JARVIS · REVISIÓN DE ARQUITECTURA", 14, MUTED, weight="Bold")
    draw_text(cr, W - 60 - tw, 20, "JARVIS · REVISIÓN DE ARQUITECTURA", 14, MUTED, 1, weight="Bold")
    if scene.subtitle:
        surf, tw, th = text_surface(scene.subtitle, 17, MUTED)
        draw_text(cr, W - 60 - tw, 50, scene.subtitle, 17, MUTED, 1)
    # progress through the whole video
    p = (scene.t0 + t) / total if total else 0
    cr.rectangle(0, 94, W, 2)
    cr.set_source_rgba(*GRID, 1)
    cr.fill()
    cr.rectangle(0, 94, W * p, 2)
    cr.set_source_rgba(*BRASS, 0.9)
    cr.fill()


def draw_legend(cr, scene):
    y = H - 46
    x = 60
    for kind, label in LEGEND:
        col = KINDS[kind]["color"]
        shape = KINDS[kind]["shape"]
        if shape == "pill":
            rrect(cr, x, y - 8, 26, 16, 8)
        elif shape == "cylinder":
            rrect(cr, x + 3, y - 9, 20, 18, 5)
        else:
            rrect(cr, x, y - 8, 26, 16, 4)
        cr.set_source_rgba(*col, 0.25)
        cr.fill_preserve()
        cr.set_source_rgba(*col, 0.95)
        cr.set_line_width(1.4)
        if shape == "cloud":
            cr.set_dash([4, 3])
        cr.stroke()
        cr.set_dash([])
        tw, _ = draw_text(cr, x + 34, y, label, 14, MUTED, 1, anchor="cl")
        x += 34 + tw + 26


# ------------------------------------------------------------------ narration text for TTS
PRONOUNCE = [
    (r"\bClaude Code\b", "Clod Cod"), (r"\bClaude\b", "Clod"), (r"\bfaster-whisper\b", "fáster uísper"),
    (r"\bWhisper\b", "Uísper"), (r"\bopenWakeWord\b", "open uéik uord"), (r"\bGroq\b", "Grok"),
    (r"\bEdge TTS\b", "Edch te te ese"), (r"\bEdge\b", "Edch"), (r"\bTTS\b", "te te ese"),
    (r"\bSTT\b", "ese te te"), (r"\bVAD\b", "vad"), (r"\bVRAM\b", "ve ram"), (r"\bGPU\b", "ge pe u"),
    (r"\bCPU\b", "se pe u"), (r"\bsystemd\b", "sístem de"), (r"\bPipeWire\b", "paip uáier"),
    (r"\bpw-record\b", "pe uve récord"), (r"\bpw-play\b", "pe uve pléi"), (r"\bGTK\b", "ge te ka"),
    (r"\bstream-json\b", "estrím yéison"), (r"\bJSON\b", "yéison"), (r"\bstreaming\b", "estríming"),
    (r"\bstdout\b", "salida estándar"), (r"\bstdin\b", "entrada estándar"), (r"\bMCP\b", "eme ce pe"),
    (r"\bAPI\b", "a pe i"), (r"\bplayerctl\b", "pléier control"), (r"\bMPRIS\b", "em pris"),
    (r"\bmemory\.json\b", "mémori punto yéison"), (r"\bHaiku\b", "Jaiku"), (r"\bSonnet\b", "Sónet"),
    (r"\bAnthropic\b", "Ántropic"), (r"\bWayland\b", "Uéiland"), (r"\bCUDA\b", "Cuda"),
    (r"\bSIGTERM\b", "sig term"), (r"\bSIGKILL\b", "sig kil"), (r"\bSIGUSR1\b", "señal iu ese erre uno"),
    (r"\bprompt\b", "prómpt"), (r"\bprompts\b", "prómpts"), (r"\btokens\b", "tókens"),
    (r"\btoken\b", "tóken"), (r"\bPython\b", "Páiton"), (r"\bHey Jarvis\b", "Jéi Yárvis"),
    (r"\bJarvis\b", "Yárvis"), (r"\bjarvis\.py\b", "yárvis punto pai"),
    (r"\bjarvis_stt\.py\b", "yárvis ese te te punto pai"), (r"\bjarvis_ui\.py\b", "yárvis iu ai punto pai"),
    (r"\bconfig\.toml\b", "config punto tóml"), (r"\bactivity\.log\b", "actíviti punto log"),
    (r"\bjarvis\.log\b", "yárvis punto log"), (r"\bBash\b", "Bash"), (r"\bonnx\b", "ónix"),
    (r"\bONNX\b", "ónix"), (r"\bKokoro\b", "Kokóro"), (r"\bSilero\b", "Siléro"), (r"\bdf\b", "de efe"),
    (r"\bcallback\b", "cólbac"), (r"\bfallback\b", "fólbac"),
    (r"\bbarge-in\b", "barch in"), (r"\bcosmic-term\b", "cósmic term"), (r"\bflag\b", "flag"),
    (r"\bcgroup\b", "se grup"), (r"\bonline\b", "onláin"), (r"\boffline\b", "ofláin"),
    (r"\bhardware\b", "járduer"), (r"\bsoftware\b", "sóftuer"), (r"\bpipeline\b", "páiplain"),
    (r"\bmock\b", "moc"), (r"\bheadset\b", "jédset"), (r"\bpatience\b", "péishens"),
    (r"\bthreshold\b", "tréshold"), (r"\bpre-roll\b", "pre rol"),
    (r"\bint8\b", "int ocho"), (r"\bfloat32\b", "flout treinta y dos"), (r"\bPCM\b", "pe ce eme"),
    (r"\bmp3\b", "eme pe tres"), (r"\bUSD\b", "dólares"), (r"\bOK\b", "okey"),
    (r"(\d+),(\d+)", r"\1 coma \2"), (r"(\d+)\s?%", r"\1 por ciento"), (r"(\d+)\s?GB\b", r"\1 gigas"),
    (r"(\d+)\s?MB\b", r"\1 megas"), (r"(\d+)\s?ms\b", r"\1 milisegundos"), (r"(\d+)\s?kHz\b", r"\1 kilohercios"),
    (r"\bms\b", "milisegundos"), (r"→", ", "), (r"·", ", "), 
]


def spoken(text):
    for pat, rep in PRONOUNCE:
        text = re.sub(pat, rep, text)
    return text
