"""HOT-Jass web -- layout skeleton, informed by HI-Jass/Panel_proto's own
app_dashboard.py (rail + Cards, gray/turquoise/magenta 3D buttons, white
content boxes on a gray page) and app_dialog.py (pn.Modal machinery: Config/
Results/Assumptions/Help/References dialogs, LaTeX + Save-to-PDF, a real
threaded Start/Stop calculation with a progress bar). Deliberately a
SEPARATE, standalone project (its own folder, its own requirements.txt, no
sys.path reach into HI-Jass) -- this is the shell for a from-scratch web
port, not another HI-Jass/Panel_proto spike. The rail's fields and the 5
result tabs are placeholders (real DANTE numbers, real tab names, no solve
wired up yet) -- this file is about the LAYOUT, not the physics.

Layout (top to bottom, per the user's own spec):
  - A horizontal TOOLBAR, fixed height, grouped into labelled clusters:
    Machines (device preset, a RadioButtonGroup -- magenta = selected),
    Config (Read JSON / Save JSON / Assumptions -- all open a pn.Modal),
    Calculation (Start / Stop -- plain actions, no modal, drive a real
    threaded progress bar), Results (View / Save -- both open a pn.Modal),
    and a fourth, narrower group stacked VERTICALLY (Exit / Help / Refs)
    at the toolbar's far end -- a "session/meta" cluster set apart from the
    action groups by being a column instead of a row, in its own right-
    aligned slot.
  - Below it, a Row that fills the rest of the viewport: a vertical input
    RAIL on the left (the real "type numbers in" surface -- Presets are
    NOT here, they moved to the Machines toolbar group, unlike
    app_dashboard.py's own rail) and a plot VIEW AREA on the right, a
    pn.Tabs with 5 EMPTY placeholder tabs (Geometry / Plasma / Beam / Power
    / Fusion -- renamed 2026-09-23 per the user's own explicit ask; minus
    Dashboard/Assumptions/References, which live in the toolbar's modals
    instead).

Viewport-fit (the user's own hard requirement -- "not clipped" at launch):
  the whole page is one 100vh Column (`page`, styles height/width:100vh/vw
  + overflow:hidden) with `main_ui` (toolbar + main_row) and `main_row`
  (rail + view_area) both `sizing_mode="stretch_both"` plus a plain
  `min-height: 0` -- NOT a manual `display:flex`/`flex-direction` override
  anywhere: Panel's own Column/Row already renders as flexbox internally
  (confirmed via CDP -- a bare pn.Column's computed `display` is already
  `flex`), and re-declaring those two properties ourselves collided with
  Bokeh's own JS-driven layout writes badly enough to blank the ENTIRE page
  (every widget, not just the mis-sized one) -- confirmed by removing them.

  The real bug, also found via CDP (walking a widget's ancestor chain with
  getComputedStyle/getBoundingClientRect, the same shadow-DOM-aware
  technique HI-Jass/Panel_proto/app_dialog.py's own KEYBOARD_JS uses) rather
  than guessed: a CLOSED `pn.Modal` still reserves its full declared
  width/height as a track in its PARENT's flex layout -- it only becomes a
  position:fixed overlay, detached from flow, once opened. With all 7
  modals as direct siblings of `main_ui` inside `page`, their closed-state
  heights (260+440+600+280+280+300+300) summed to exactly 2460px, and
  `main_ui`'s stretch_both got computed against whatever was left of
  page's 100vh after that -- i.e. nothing, so it collapsed to 0 and the
  entire rail+toolbar+view area vanished. Confirmed independently via a
  panel-source reading (panel/models/modal.ts: the closed state only
  toggles the *inner* `.dialog-container`'s `display`, never the Modal
  model's own Bokeh layout box). Fixed by moving every modal into its own
  `modals = pn.Column(..., styles={"height": "0", "overflow": "hidden",
  "flex": "0 0 0"})` -- a single sibling that itself claims zero space,
  so the 7 modals inside it never compete with `main_ui` for page's height
  again, while each modal's own width/height still governs its floating
  dialog box normally once opened. Confirmed via CDP screenshot at three
  resolutions (1280x720, 1440x900, 1920x1080): no page-level scrollbar at
  any of them, and the rail/tab area both render down to the last pixel of
  the viewport.

Colors, per the user's own spec: turquoise/gray/magenta 3D raised buttons
(TURQUOISE_BUTTON_CSS/GRAY_BUTTON_CSS/MAGENTA_BUTTON_CSS below, the exact
same gradient stops as HI-Jass/Panel_proto/app_dashboard.py's own
BUTTON_CSS -- turquoise = primary/commit action in each group, gray =
secondary/neutral, magenta = the Machines radio's selected state) on a
gray (`BG_GRAY`) page/panel/dialog background, with white boxes
(`CONTENT_STYLE`) reserved for anything that is actually TEXT/plot content
the user reads, exactly the split app_dashboard.py's Dashboard pane and
app_dialog.py's `CONTENT_STYLE` already established.

Run:      .venv/bin/panel serve HOT-Jass_web/app.py --show
"""
from __future__ import annotations

import base64
import io
import json
import sys
import textwrap
import threading
import time
import urllib.parse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import panel as pn
from matplotlib.backends.backend_pdf import PdfPages

# HOT-Jass_web and HI-Jass are SIBLING directories (not nested), unlike
# HI-Jass/Panel_proto's own `sys.path.insert(0, dirname(dirname(...)))`
# (which reaches HI-Jass's own root from a subdirectory INSIDE it) -- this
# needs the explicit sibling path instead. First real import of HI-Jass's
# own calculation code into this file, per the user's own explicit "import
# all the calculation from HI-Jass (HotJass) code" ask -- supersedes an
# earlier memory note calling this app "standalone, no imports from
# HI-Jass"; that was a valid description of the layout-skeleton phase, not
# a constraint meant to survive into the real-calculation phase.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "HI-Jass"))
from hotjass_core import PlasmaParams, BeamParams, HotJassModel  # noqa: E402
from hotjass import physics as hj_physics  # noqa: E402

# Tippy.js (Panel's own `description=` "?"-icon tooltip library, already
# bundled) renders its popup portalled to <body>, outside every widget's own
# shadow root -- so unlike almost every other per-widget style in this file,
# it can ONLY be reached by a plain global stylesheet, not a `stylesheets=`
# list scoped to one widget. Font size matched to the rail's own dense
# RAIL_FONT_SIZE (12px) per the user's own ask that the data help popup use
# the same size as the name/value/units columns it describes.
pn.extension("modal", "mathjax", "tabulator", design="material", notifications=True,
             raw_css=["html, body { margin: 0; padding: 0; height: 100%; overflow: hidden; }",
                       ".tippy-content { font-size: 13px !important; }"])

# --------------------------------------------------------------------- logo
# nbr-logo-icon.png: nbr-logo.png cropped tight to its own content (the
# source image's ring/arrows already run almost edge to edge, confirmed by
# computing the non-white bounding box -- only ~5% margin to trim) and
# padded to a square, so it works as both a browser-tab favicon and a
# spinning "progress ring" at small sizes without a stray white border
# dominating the shape. Base64-embedded (not served as a static file):
# keeps both the favicon and the spinner fully self-contained in this one
# script, so `panel serve app.py` doesn't need a `--static-dirs`/
# `--ico-path` flag added to the README's own run commands.
LOGO_ICON_B64 = base64.b64encode(
    (Path(__file__).parent / "nbr-logo-icon.png").read_bytes()
).decode("ascii")

# Sets the browser tab's favicon to the logo -- `panel serve`'s own
# favicon.ico is only swappable via a CLI flag (`--ico-path`, and only for
# a .ico file at that), so this does it from inside the page instead: a
# <script>, run once per session, that creates a <link rel="icon"> and
# appends it to <head>. A plain <script> tag DOES execute when mounted via
# a Panel HTML pane -- confirmed elsewhere in this codebase (HI-Jass/
# Panel_proto/app_dialog.py's own KEYBOARD_JS relies on the same fact) --
# this just reuses that same, already-proven mechanism for a different job.
FAVICON_JS = f"""
<script>
(function() {{
    var link = document.querySelector("link[rel~='icon']");
    if (!link) {{
        link = document.createElement('link');
        link.rel = 'icon';
        document.head.appendChild(link);
    }}
    link.type = 'image/png';
    link.href = 'data:image/png;base64,{LOGO_ICON_B64}';
}})();
</script>
"""
favicon_setter = pn.pane.HTML(FAVICON_JS, width=0, height=0, margin=0, sizing_mode="fixed")

# ------------------------------------------------------------------- colors
# Classic Tk widget-background gray, same constant/reasoning as
# app_dashboard.py's own BG_GRAY: the page isn't inside any widget's shadow
# root, so a plain global stylesheet reaches it directly.
BG_GRAY = "#d9d9d9"
TOOLBAR_GRAY = "#c9c9c9"

# One shared heading size for "INPUT DATA", every toolbar group's caption
# (MACHINES/CONFIG/CALCULATION/RESULTS), and the View area's tab titles --
# per the user's ask that all of those read as the same size.
GROUP_TITLE_FONT_SIZE = "14px"
# Shared height for View/Save/Exit/Help/Refs -- 35px matches Panel's own
# default Button height (measured via CDP: an un-styled Button rendered at
# 34.8px), which is the size the user asked to keep for Results and match
# Exit/Help/Refs to, rather than the smaller 26px this constant used
# before. Set explicitly (not left at "default") so all five stay equal
# on purpose, not by two widgets coincidentally defaulting the same way.
TOOLBAR_BTN_HEIGHT = 35
# Config's own content width (Read+Save side by side, or Assumptions alone
# below them) -- Calculation's and Results' own action buttons are widened
# to match this exactly, per the user's own ask, so all three groups'
# CONTENT widths (and therefore, since they share the same GROUP_STYLE
# padding, their outer separator-to-separator widths too) end up equal
# without needing a second, independent "group width" number anywhere.
CONFIG_BTN_WIDTH = 88
ACTION_BTN_WIDTH = 2 * CONFIG_BTN_WIDTH + 6

# The one place text/plot CONTENT actually lives -- white, per the user's
# "only the text background is white" spec, everywhere else (page, toolbar,
# rail, modal chrome) stays BG_GRAY.
CONTENT_STYLE = {
    "background": "white", "border": "1px solid #b7b7b7", "border-radius": "4px",
    "padding": "10px", "box-sizing": "border-box",
}


def _raised_button_css(top: str, mid: str, bottom: str, border: str, lip: str,
                        text_color: str = "black") -> str:
    """Same top-lit-gradient + lip-shadow + press-in construction as
    app_dashboard.py's own BUTTON_CSS (and HI-Jass/Panel_proto/app_dialog.py's
    own port of it) -- !important is load-bearing there for why: Bokeh's own
    `button.bk-btn.bk-btn-default` rule out-specifies a plain single-class
    selector, so this has to out-rank it rather than out-specify it."""
    return f"""
    .bk-btn {{
        background: linear-gradient(180deg, {top} 0%, {mid} 55%, {bottom} 100%) !important;
        border: 1px solid {border} !important;
        color: {text_color} !important;
        font-weight: 600;
        box-shadow: 0 3px 0 {lip}, 0 5px 10px rgba(0, 0, 0, 0.35) !important;
        transition: box-shadow 0.08s, transform 0.08s, filter 0.15s;
    }}
    .bk-btn:hover {{ filter: brightness(1.06); }}
    .bk-btn:active {{
        box-shadow: 0 1px 0 {lip}, 0 2px 4px rgba(0, 0, 0, 0.35) !important;
        transform: translateY(2px);
    }}
    .bk-btn:disabled {{ filter: grayscale(0.6) brightness(0.95); box-shadow: none !important; }}
    """


TURQUOISE_BUTTON_CSS = _raised_button_css("#8ff5ee", "turquoise", "#24bdb3", "#17a399", "#128f86")
GRAY_BUTTON_CSS = _raised_button_css("#f5f5f5", "#c9c9c9", "#9a9a9a", "#8a8a8a", "#7a7a7a",
                                      text_color="#222")
# Exact same magenta stops as app_dashboard.py's own BUTTON_CSS `.bk-active`.
MAGENTA_BUTTON_CSS = _raised_button_css("#ff8bff", "magenta", "#c400c4", "#b800b8", "#8a008a",
                                         text_color="white")

# Shared modal chrome -- rounded corners, drop shadow -- same construction
# as HI-Jass/Panel_proto/app_dialog.py's own MODAL_CSS (injected via
# Modal(stylesheets=[...]), which lands inside the Modal's own shadow root;
# a global pn.extension(raw_css=...) rule can't reach in there).
MODAL_CSS = """
.dialog-content {
    padding: 0 !important;
    border-radius: 6px;
    border: 1px solid #999;
    box-shadow: 0 10px 34px rgba(0, 0, 0, .45);
    background: %s !important;
    overflow: hidden;
}
""" % BG_GRAY


def modal_footer(*buttons) -> pn.Row:
    return pn.Row(pn.HSpacer(), *buttons, styles={"padding": "10px 14px 14px 14px", "gap": "8px"})


# =============================================================== input rail
# Real DANTE numbers (duplicated on purpose, same convention as every other
# HI-Jass Panel prototype -- this project intentionally does NOT import
# hotjass_core; it is a layout skeleton, wired to real physics later).
# ECRH/ICRH field names (p_ecrh_MW/ecrh_f_e/p_icrh_MW/icrh_f_e/icrh_f_i) and
# NBI field names (P_NB [MW]/E_b [keV]) are copied from hi_jass_app.py's own
# rail (_add_entries calls in its "Aux heating"/"NBI-1"/"NBI-2"
# CollapsibleSections) -- not invented for this skeleton. ECRH/ICRH default
# to 0 MW (off), matching that same file's own PLASMA_PRESETS convention of
# leaving optional heating off unless a preset turns it on.
# LABEL_WIDTH widened from an earlier 108: at 13px bold, the real
# hi_jass_app.py label text now in use here ("Elongation kappa",
# "Triangularity delta", "Central n_e [m^-3]") wrapped to 2 lines even at
# 150px -- confirmed via screenshot, not assumed. The label's own "?"
# tooltip icon lives INSIDE the same flex box as the text (Bokeh nests it
# inside <label>, confirmed via CDP earlier this session), eating ~21px
# (icon + gap) out of LABEL_WIDTH before any text -- so the usable text
# width is smaller than LABEL_WIDTH itself, not equal to it. 185 accounts
# for that and fits all current labels on one line; RAIL_WIDTH grows to
# match so the value field doesn't have to shrink to make room.
# RAIL_WIDTH tuned to 328: per the user's own explicit target (section
# header buttons and data tables both left/right-aligned at x=20/x=340).
# Two corrections were needed, both measured via CDP, not guessed: (1)
# RAIL_WIDTH=330 rendered the header button at 334px (14px over target,
# since it drives that button's own `sizing_mode="stretch_width"` box) --
# BUT (2) once all 5 rail sections became tables tall enough to overflow
# the rail's own `overflow-y: auto` height, `rail`'s scrollbar started
# reserving a real ~12px gutter out of the button's available width too
# (confirmed: `rail`'s own scrollable Column measured `offsetWidth=340,
# clientWidth=328` with that scrollbar present) -- a first pass that only
# accounted for (1) landed the button 12px short. 316+12=328 accounts for
# both at once.
# FIELD_WIDTH trimmed 120->115: with the table's own outer box pinned to a
# fixed DATA_TABLE_WIDTH (see below), the two columns' own widths (185+120
# =305) left only a 2px margin against the ~303px actually available once
# the table's internal vertical scrollbar reserves its own gutter --
# confirmed via CDP (tableholder clientWidth=303 vs scrollWidth=305),
# which was enough to trigger an unwanted HORIZONTAL scrollbar on every
# table, not just the ones that need to scroll vertically. -5 gives real
# headroom instead of a hairline fit; 115 is still generous for any value
# this rail shows.
LABEL_WIDTH, FIELD_WIDTH, RAIL_WIDTH = 185, 115, 328
# The table's own outer box width, independent of LABEL_WIDTH+FIELD_WIDTH:
# lands its right edge on the user's explicit x=340 target (with
# DATA_TABLE_MARGIN's left=6 landing the left edge at x=20) regardless of
# how the two column widths above get tuned.
DATA_TABLE_WIDTH = 320

# A dense 3-column (name / value / units, HTML-subscripted names) rail was
# tried and then reverted per the user's own follow-up feedback ("not the
# best idea") in favor of matching HI-Jass/hi_jass_app.py's own real rail
# look instead: a single bold "label [units]" text (its exact field-label
# strings, e.g. "Elongation kappa", "Triangularity delta" -- copied from
# that file's own PLASMA_FIELDS/_add_entries calls, not reinvented) beside
# a plain value box, generously spaced. RAIL_FONT_SIZE/RAIL_ROW_HEIGHT stay
# as shared constants (still used by LABEL_LEFT_CSS + the rail's
# subheadings + the global Tippy tooltip font-size below) but sized back up
# to match that more spacious reference look rather than the dense take's
# numbers.
RAIL_FONT_SIZE = "13px"
RAIL_ROW_HEIGHT = 24
# Selects and checkboxes read noticeably smaller than the rest of the rail
# (its bold Parameter labels, table cells) at the shared RAIL_FONT_SIZE --
# per the user's own explicit ask to bump those two control types up. A
# separate constant, not a RAIL_FONT_SIZE increase, since that would also
# inflate every Tabulator table's own font size, which wasn't asked for.
CONTROL_FONT_SIZE = "15px"

# Collapsible-section headers: same 3D gray raised button as every other
# secondary button in this file (GRAY_BUTTON_CSS), just left-aligned with a
# leading arrow instead of centered -- a plain text label combined with an
# arrow GLYPH, never an arrow-only label: HI-Jass/Panel_proto/app_dialog.py's
# own min/max/close-button bug (a button whose `name` is a LONE special
# Unicode character can silently fail to register clicks in some browsers)
# was traced specifically to glyph-only labels; "▶  PLASMA" pairs the glyph
# with real text the same safe way that file's own "☰ Menu" button already
# did, so it isn't at risk of the same bug.
SECTION_HEADER_CSS = GRAY_BUTTON_CSS + """
.bk-btn { justify-content: flex-start !important; padding-left: 12px !important;
          font-size: 13px !important; }
"""
# Denser, larger-font, no-spinner numeric fields: a plain pn.widgets.TextInput
# (typed, no up/down spin buttons at all) rather than FloatInput/Spinner --
# the same "typed field, no spinner" choice HI-Jass/Panel_proto/app_dialog.py
# already made deliberately for its own density field (see
# GUI_design_next_steps.txt point 1: a Spinner auto-clamps, which never lets
# an invalid value exist long enough to show an error for). This skeleton
# doesn't wire up that field's own error-highlighting yet -- _parse_float
# below just falls back to 0.0 -- but keeps the same widget choice so that
# validation can be bolted on later without changing the input type again.
# Label-left fields, take 3. Take 1 (a pn.Row per (label, field) pair,
# stacked in a Column) broke under the user's own browser window -- label
# and value drifting apart into a "chess" pattern -- even after fixing the
# obvious cause (Panel's own `align=` centers a ROW within whatever leftover
# space its Column hands it, not the row's children; confirmed via
# Row.param.align's own docstring). Take 2 (pn.GridBox, a real 2-column CSS
# grid) fixed the pairing but the user then found the label text still sat
# visibly higher than its value box -- adding flex-centering to the label's
# OWN box didn't fully fix that either. Both takes shared the same root
# problem: label and field were two SEPARATE Panel objects (two DOM
# subtrees) that some layer of Panel/Bokeh's own layout math had to keep in
# sync, and kept failing to.
#
# This take doesn't pair two objects at all. Bokeh's own TextInput/Select
# already render as ONE flex container -- confirmed via CDP:
#   <div class="bk-input-group"><label>...</label><input class="bk-input">...
# with `label`/`input` as DIRECT SIBLINGS inside it. Overriding that ONE
# container's `flex-direction` from its own default (column: label above
# input) to `row` puts label and field side by side as two items of the
# SAME flex box -- so the browser's own flexbox engine centers them against
# each other, guaranteed, using the widget's own DOM rather than a second
# Panel object this file would otherwise have to keep aligned by hand.
# `description=` is Panel's own native tooltip (a small "?" icon, Tippy.js
# under the hood, already bundled) -- replaces this file's earlier
# hand-rolled `title=`-on-a-span trick, which needed that second HTML pane
# to exist in the first place. `.bk-description` (the "?" icon) is nested
# INSIDE the <label> as a block-level child (confirmed via CDP) -- without
# `display:flex` on the label itself too, it wraps onto its own line below
# the label text.
#
# `position: static` on the label is ALSO load-bearing, and was the actual
# remaining bug the first version of this CSS missed: this app uses
# `pn.extension(..., design="material")` for nicer Select/dropdown chevrons
# elsewhere, and Material design's own text-field skin gives the label
# `position: absolute; top: 0; transform: scale(0.75)` -- a floating label
# that overlaps the input until focused, then shrinks up above it.
# Confirmed via CDP getComputedStyle, not guessed: an isolated test page
# with plain `pn.extension()` (no design=) rendered flex-direction:row
# correctly on the first try, but the SAME CSS in this app left the label
# visibly overlapping the input's left edge -- `flex-direction` on the
# parent has no effect on a child that's been taken out of flow by
# `position: absolute` in the first place. `position: static !important`
# puts it back in normal flow, where the row layout below can actually
# reach it.
def _label_left_css(label_width: int) -> str:
    return f"""
.bk-input-group {{
    flex-direction: row !important;
    align-items: center !important;
    gap: 6px;
}}
.bk-input-group > label {{
    position: static !important;
    transform: none !important;
    background: transparent !important;
    width: {label_width}px;
    min-width: {label_width}px;
    flex: 0 0 {label_width}px;
    font-size: {CONTROL_FONT_SIZE};
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 3px;
    white-space: normal;
}}
.bk-input-group > .bk-input-container {{
    flex: 1 1 auto;
}}
input {{ font-size: {CONTROL_FONT_SIZE}; padding: 3px 8px; height: {RAIL_ROW_HEIGHT}px !important;
         min-height: {RAIL_ROW_HEIGHT}px !important; }}
/* `select` gets ONLY font-size, no forced height/padding -- forcing those
   on a native <select> (confirmed via CDP screenshot, not guessed) made its
   own OPTION TEXT render almost invisible (a near-white/very-light gray,
   not merely clipped) in this app's `design="material"` context, the same
   general class of "MDC theme variable silently overrides a native control's
   own rendering" bug as the Tabulator hover-text and slider-fill bugs found
   earlier this session -- squeezing a native select's box via `height`
   apparently pushes it into whatever degraded/themed rendering path
   produces that. A plain font-size bump alone doesn't trigger it. */
select {{ font-size: {CONTROL_FONT_SIZE}; }}
"""


LABEL_LEFT_CSS = _label_left_css(LABEL_WIDTH)
# Checkbox (and, per the user's later ask, alpha_confined_slider below)
# don't go through styled_field()/LABEL_LEFT_CSS at all (see Checkbox's own
# comment further down), so they need their own, much smaller, stylesheet
# just to pick up the same CONTROL_FONT_SIZE bump as the Selects above --
# `:host` covers the widget's own custom-element wrapper (whatever tag
# renders its own inline title/label inside), so this doesn't depend on
# knowing Bokeh's exact internal markup, and works the same for a
# Checkbox's inline label as for a FloatSlider's own title+value text.
CONTROL_TEXT_CSS = f":host {{ font-size: {CONTROL_FONT_SIZE}; }}\nlabel {{ font-size: {CONTROL_FONT_SIZE}; }}"


def _parse_float(text, fallback: float = 0.0) -> float:
    try:
        return float(text)
    except (TypeError, ValueError):
        return fallback


def styled_field(widget, label: str, tooltip: str,
                  label_width: int = LABEL_WIDTH, field_width: int = FIELD_WIDTH,
                  height: int | None = None):
    """Wires a TextInput/Select up as a dense, label-left rail field: sets
    the widget's OWN name (Bokeh's built-in label) and description (Panel's
    own hover tooltip) instead of building a second, separately-positioned
    label object, then applies LABEL_LEFT_CSS so that built-in label sits
    beside the field rather than above it. Returns the widget itself --
    nothing left to pair up by hand. `label_width`/`field_width` default to
    the shared rail constants but can be overridden per call -- same
    narrower-label/wider-field escape hatch HI-Jass/Panel_proto/
    app_dashboard.py's own `labeled_row()` already uses for its Confinement
    dropdown, whose longest option ("Kaye NSTX H-mode") got clipped behind
    its own chevron at the plain numeric-field label width. `height`
    defaults to Panel's own auto-sizing (unset) but can be pinned
    explicitly -- see NBI's own two direction selects for why: an
    un-pinned widget inside a `visible`-toggled collapsible_section wasn't
    reliably reporting its own true height back to Bokeh's layout engine
    after a batched multi-widget update (a device-preset switch touching
    the table AND this select AND 2 sliders all at once), letting
    following siblings (ECRH/ICRH/MODELS) render on top of it -- not
    reliably reproduced on demand, but the same general "unbounded
    auto-height widget inside a toggled Column" class of bug already hit
    (and fixed with an explicit height) for the Tabulator tables
    themselves earlier this session."""
    widget.name = label
    widget.description = tooltip
    widget.width = label_width + field_width + 10
    if height is not None:
        widget.height = height
    # Same left-shift as DATA_TABLE_MARGIN (defined further down, but the
    # margin VALUE, not the name, is what matters here): a plain
    # styled_field() widget's natural unshifted position turned out to be
    # x=12, identical to a Tabulator table's own natural position before
    # ITS alignment fix -- confirmed via CDP, not assumed. Reusing the same
    # (4, 0, 4, 6) here keeps every rail row (table OR plain widget) on the
    # same x=20 left edge the user asked for, instead of just the tables.
    widget.margin = (4, 0, 4, 6)
    widget.stylesheets = [LABEL_LEFT_CSS if label_width == LABEL_WIDTH else _label_left_css(label_width)]
    return widget


def collapsible_section(title: str, *content, collapsed: bool = True) -> pn.Column:
    """A rail section that looks like a 3D gray button with a leading
    ▶/▼ arrow -- folded (collapsed=True) by default, per the user's spec.
    A plain toggle Button + a `visible`-toggled Column, not pn.Card: Card's
    own header doesn't take a `stylesheets=` hook the way a bare Button
    does, so there's no direct way to give IT this exact 3D/leading-arrow
    look without fighting its internal markup."""
    body = pn.Column(*content, visible=not collapsed,
                      styles={"gap": "0px", "padding": "4px 4px 8px 4px"},
                      sizing_mode="stretch_width")
    state = {"collapsed": collapsed}
    header = pn.widgets.Button(name=("▶  " if collapsed else "▼  ") + title,
                                stylesheets=[SECTION_HEADER_CSS], height=30,
                                sizing_mode="stretch_width")

    def _toggle(event):
        state["collapsed"] = not state["collapsed"]
        body.visible = not state["collapsed"]
        header.name = ("▶  " if state["collapsed"] else "▼  ") + title

    header.on_click(_toggle)
    return pn.Column(header, body, margin=(0, 0, 4, 0), sizing_mode="stretch_width")


CONFINEMENT_MODES = ["Fixed tauE (input)", "Kaye NSTX L-mode", "Kaye NSTX H-mode",
                      "IPB98(y,2) ELMy H-mode"]
confinement_select = pn.widgets.Select(options=CONFINEMENT_MODES, value="Kaye NSTX H-mode")
# Checkbox doesn't support Panel's `description=` tooltip (raises a
# TypeError -- confirmed, not assumed) and already renders its own label
# INLINE next to the box natively, unlike TextInput/Select, so it's the one
# field here that doesn't go through styled_field()/LABEL_LEFT_CSS at all.
equip_checkbox = pn.widgets.Checkbox(name="electron-ion equipartition", value=True,
                                      margin=(4, 0, 4, 2), stylesheets=[CONTROL_TEXT_CSS])

# The 7 fields below are all real HI-Jass model toggles/choices, found via a
# dedicated research pass (don't re-derive -- re-check hotjass_core.py's own
# dataclass fields directly if this needs revisiting): `f_alpha` (line 34),
# `profile_averaging` (line 45, used on PLASMA not here), `shine_through_model`
# (BeamParams), `orbit_model` (line 44), `cx_model` (line 47),
# `rotation_model` (line 50), `enable_beam_beam` (line 53). Options/labels
# below are copied verbatim from hi_jass_app.py's own UI dicts
# (SHINE_LABEL_TO_MODEL/ORBIT_MODELS/CX_MODELS/ROTATION_MODELS, lines 53-70)
# -- stored here as plain display-label strings, matching how `confinement`
# above already works (no separate internal-code mapping; this is a layout
# skeleton with no physics wired up yet, same convention as everywhere else
# in this file). Associated numeric sub-parameters each model has in the
# real app (CX's own 3 fractions, rotation's manual v_phi/tau_phi, and each
# beam's own manual shine-through fraction) are added further down as
# `cx_manual_table`/`rotation_manual_table` (small Tabulator tables, same
# pattern as ECRH/ICRH) and as extra NBI1_ROWS/NBI2_ROWS table rows,
# respectively -- per the user's own explicit follow-up ask.
alpha_confined_slider = pn.widgets.FloatSlider(
    name="Alpha fraction confined (f_alpha)", start=0.0, end=1.0, step=0.01, value=1.0,
    stylesheets=[CONTROL_TEXT_CSS])
SHINE_THROUGH_MODELS = ["Riviere", "Janev", "Suzuki", "Manual"]
shine_through_select = pn.widgets.Select(options=SHINE_THROUGH_MODELS, value="Manual")
ORBIT_MODELS = ["Large-aspect (q* rho_Li)", "ST orbits - mean-shift (arbitrary A)",
                "ST orbits - pitch-resolved"]
orbit_model_select = pn.widgets.Select(options=ORBIT_MODELS, value="ST orbits - pitch-resolved")
CX_MODELS = ["Manual fraction", "Manual n0/ne", "Penetration (n0_LCFS/ne)"]
cx_model_select = pn.widgets.Select(options=CX_MODELS, value="Manual fraction")
ROTATION_MODELS = ["Off", "Manual v_phi", "Momentum balance"]
rotation_model_select = pn.widgets.Select(options=ROTATION_MODELS, value="Off")

# Display-label -> internal mode-string map, verbatim from hi_jass_app.py's
# own module-level dicts (lines 39-70) -- the SAME source the *_MODELS
# label lists above were already copied from, so every key here matches
# one of those lists' own entries exactly. Needed now (not before) because
# _build_model() below has to translate a Select's displayed label back
# into the string PlasmaParams/BeamParams actually store.
CONFINEMENT_MODE_MAP = {
    "Fixed tauE (input)": ("fixed", "fixed"),
    "Kaye NSTX L-mode": ("kaye_nstx_lmode", "kaye_nstx_lmode"),
    "Kaye NSTX H-mode": ("kaye_nstx_hmode", "kaye_nstx_hmode"),
    "IPB98(y,2) ELMy H-mode": ("iter98y2", "iter98y2"),
}
ORBIT_MODEL_MAP = {
    "Large-aspect (q* rho_Li)": "large_aspect",
    "ST orbits - mean-shift (arbitrary A)": "st_meanshift",
    "ST orbits - pitch-resolved": "st_pitch",
}
CX_MODEL_MAP = {
    "Manual fraction": "manual_fraction",
    "Manual n0/ne": "manual_n0",
    "Penetration (n0_LCFS/ne)": "penetration",
}
ROTATION_MODEL_MAP = {"Off": "off", "Manual v_phi": "manual", "Momentum balance": "momentum_balance"}
SHINE_LABEL_TO_MODEL = {"Riviere": "riviere", "Janev": "janev_suzuki", "Suzuki": "suzuki", "Manual": "manual"}
SHINE_MODEL_TO_LABEL = {v: k for k, v in SHINE_LABEL_TO_MODEL.items()}
CX_MODEL_TO_LABEL = {v: k for k, v in CX_MODEL_MAP.items()}
ORBIT_MODEL_TO_LABEL = {v: k for k, v in ORBIT_MODEL_MAP.items()}
beam_beam_checkbox = pn.widgets.Checkbox(name="Beam-beam fusion (reduced, NBI-1 x NBI-2)",
                                          value=False, margin=(4, 0, 4, 2),
                                          stylesheets=[CONTROL_TEXT_CSS])
# Real per-device field (hi_jass_app.py's own PLASMA_PRESETS), unlike the 7
# above which are global constructor defaults -- see DEVICE_PRESETS below.
profile_avg_checkbox = pn.widgets.Checkbox(
    name="profile-corrected 0-D (central n_e in; <T> + T0 out)", value=False, margin=(4, 0, 4, 6),
    stylesheets=[CONTROL_TEXT_CSS])

# CX's 3 manual/fixed sub-parameters (used depending on which cx_model_select
# option is active) and rotation's 2 (ditto for rotation_model_select) --
# real HI-Jass fields (hotjass_core.py PlasmaParams: cx_loss_fraction line
# 46, cx_n0_over_ne line 48, cx_n0_lcfs_over_ne line 49, manual_v_phi_m_s
# line 51, tau_phi_over_tauEi line 52), labels/defaults copied verbatim from
# hi_jass_app.py's own "Losses" section entries (lines 617-636). Small
# Tabulator tables, not standalone FloatInputs -- same reasoning as NBI's
# own tangent R/Z fold-in: tables have never been implicated in the
# NBI-overlap flexbox bug (see panel-bokeh-css-gotchas), standalone
# bk-input-group widgets have. Global defaults (not per-device), same
# convention as f_alpha/shine_through_model/etc. above -- see
# DEVICE_PRESETS below.
CX_MANUAL_ROWS = [
    ("cx_loss_fraction", "CX loss fraction (0-1)", "0.1",
     "Flat charge-exchange power-loss fraction, used when CX-loss model = Manual fraction."),
    ("cx_n0_over_ne", "CX n0/ne (manual n0)", "1.0e-5",
     "Uniform background-neutral density ratio n0/ne, used when CX-loss model = Manual n0/ne."),
    ("cx_n0_lcfs_over_ne", "CX n0_LCFS/ne (edge)", "0.02",
     "Edge neutral-density ratio n0_LCFS/ne_LCFS, used when CX-loss model = Penetration."),
]
ROTATION_MANUAL_ROWS = [
    ("manual_v_phi_m_s", "v_phi manual [m/s]", "0.0",
     "Bulk toroidal rotation velocity, used when Rotation model = Manual v_phi "
     "(positive = co-current)."),
    ("tau_phi_over_tauEi", "tau_phi/tauE,i (mom.)", "1.0",
     "Momentum confinement time as a multiple of tauE,i, used when Rotation model = "
     "Momentum balance."),
]

# PLASMA as a pn.widgets.Tabulator -- a prototype for the other 4 sections,
# per the user's own explicit ask to try Tabulator for "the data list" and
# their choice (asked, not assumed) to (a) convert PLASMA only first before
# touching NBI/ECRH/ICRH/MODELS, and (b) one small per-section table, NOT
# a 3-way name/value/units column split (that was the dense-rail take
# already tried and reverted earlier this session).
#
# Label text and tooltips are unchanged from the styled_field() version
# above (same hi_jass_app.py-matched wording) -- the "Parameter" column's
# own cells carry them as `<span title="...">` HTML (formatters={'Parameter':
# {'type': 'html'}}), since Tabulator has no native per-CELL tooltip
# parameter (only `header_tooltips`, confirmed via `'tooltip' in
# cls.param`, not assumed) -- a native browser tooltip, not the Tippy.js
# popup styled_field()'s `description=` used, but the simplest way to keep
# a hover explanation without hand-rolling a second mechanism.
#
# The DataFrame is indexed by the SAME internal keys rail_values()/
# apply_rail_values() already use (R0/a/kappa/...) so both functions can
# read/write it with a plain `.loc[key, "Value"]` -- `.loc` looks up by
# index LABEL, not row position, so this stays correct even if the user
# resorts the table (sorting is disabled below anyway, but this doesn't
# rely on that). Everything downstream (JSON read/save, device presets)
# goes through apply_rail_values()/rail_values() already, so none of that
# code needed to change at all.
#
# All 16 rows (and their default values below) are HI-Jass/hi_jass_app.py's
# own real PLASMA_FIELDS list -- the initial 7-row prototype only had a
# subset; this fills in the rest per the user's own explicit ask, EXCLUDING
# "model selections" (Confinement stays a MODELS-only dropdown, never a
# PLASMA table row). Same source also gave DANTE's own real per-field
# defaults below (PLASMA_PRESETS["DANTE"] in that file), not just the bare
# PLASMA_FIELDS default -- e.g. temp_peaking_i defaults to -1.0 as a
# "same as electron" SENTINEL in the field list itself, but DANTE's own
# preset overrides it to a real 1.0, which is what this table's default
# row (and DEVICE_PRESETS["DANTE"] below) both use, matching this file's
# own established convention that the table's un-preset default equals
# DANTE's preset.
PLASMA_ROWS = [
    ("R0", "R0 [m]", "0.65",
     "Plasma major radius: distance from the torus axis to the magnetic axis."),
    ("a", "a [m]", "0.35",
     "Plasma minor radius: half-width of the poloidal cross-section."),
    ("kappa", "Elongation kappa", "2.2",
     "Elongation: ratio of the plasma's vertical to horizontal half-width."),
    ("delta", "Triangularity delta", "-0.35",
     "Triangularity: D-shape asymmetry of the poloidal cross-section (0 = elliptical)."),
    ("Zeff", "Z_eff", "2.0",
     "Effective ion charge (line-averaged), accounting for impurities."),
    ("B0", "B0 [T]", "1.5",
     "Vacuum toroidal magnetic field at the major radius R0."),
    ("Ip", "Ip [MA]", "1.5",
     "Total plasma (toroidal) current."),
    ("density_peaking", "Density peaking", "0.1",
     "Density profile peaking exponent p_n in n_e(rho) = n_e0*(1-rho^2)^p_n."),
    ("temp_peaking", "Temp peaking (electron)", "1.0",
     "Electron temperature profile peaking exponent."),
    ("temp_peaking_i", "Temp peaking (ion, -1=same)", "1.0",
     "Ion temperature profile peaking exponent (-1 = same as electron)."),
    ("centrepost_r", "Centre-post R [m] (-1=R0-a)", "-1.0",
     "Centre-post (inboard leg) radius, for centre-post heat-load estimates (-1 = R0 - a)."),
    ("ne0", "Central n_e [m^-3]", "1.0e20",
     "Central (on-axis) electron density."),
    # Scan n_e min/max (density SCAN range) removed per the user's own ask
    # -- "we'll need it later maybe" -- not deleted from history, just not
    # a PLASMA table row for now. HI-Jass/hi_jass_app.py's own PLASMA_FIELDS
    # + PLASMA_PRESETS (n_e_min/n_e_max) is still the source to pull them
    # back from if/when they're wanted again.
    ("d_fraction", "D fraction", "0.2",
     "Deuterium fraction of the fuel-ion mix (D + T should sum to 1)."),
    ("t_fraction", "T fraction", "0.8",
     "Tritium fraction of the fuel-ion mix (D + T should sum to 1)."),
    # Only used when Confinement = "Fixed tauE (input)" -- every other
    # confinement option computes tauE from a real scaling law instead and
    # ignores these two. Added per the real-calculation wiring: HI-Jass's
    # own PlasmaParams needs a literal tauE_e/tauE_i value for that one
    # mode, and this rail had no row for it (the earlier MODELS-section
    # Confinement dropdown was model-choice only, no matching numeric
    # input). Defaults 0.15/0.15 match PlasmaParams' own defaults AND
    # hi_jass_app.py's own DANTE preset.
    ("tauE_e", "tauE,e [s] (Fixed mode only)", "0.15",
     "Electron energy confinement time, used when Confinement = Fixed tauE (input)."),
    ("tauE_i", "tauE,i [s] (Fixed mode only)", "0.15",
     "Ion energy confinement time, used when Confinement = Fixed tauE (input)."),
]
# NBI-1/NBI-2 split back into TWO tables, per the user's own explicit ask
# ("I'd split the data table in two parts, and add the target point coord
# sliders and direction switch below each NBI") -- each beam's own
# power/energy table is immediately followed by ITS OWN direction select,
# not one shared table with everything bolted on after both beams.
#
# Tangent R/Z (see the real-physics comment on NBI_TANGENT_TOOLTIP below)
# are TABLE ROWS here, not separate slider/spinner widgets -- moved in
# after TWO different standalone-widget approaches (FloatSlider, then
# FloatInput) both still overlapped ECRH/ICRH/MODELS below at high enough
# browser zoom (confirmed by the user directly, not this session's own
# CDP testing, which never reproduced it either way). Across every one of
# those reports the common thread was standalone `bk-input-group` widgets
# stacked in the toggled Column -- Tabulator tables themselves were never
# implicated once given an explicit height, at any row count. Folding R/Z
# into the table (same lenient free-text `Value` column as power/energy)
# cuts the standalone widgets per beam from 3 (direction, R, Z) down to
# 1 (direction only) -- Tabulator's own `editors=` is per COLUMN not per
# cell, so the categorical direction dropdown still can't join them here.
NBI_TANGENT_TOOLTIP = ("Tangent-point coordinate of this beam's injection line (used by the "
                       "deposition/shine-through geometry) -- R is the tangency radius, Z is "
                       "the vertical offset (0 for every real HI-Jass device preset).")
# Species (H/D/T) is the FIRST element of each beam tuple in HI-Jass's own
# MACHINE_HEATING_PRESETS (hi_jass_app.py:312-331) -- e.g. DANTE's own real
# mix is ("D", ...) for NBI-1 and ("T", ...) for NBI-2, every other device
# is D/D -- same source already used for power/energy/co_current. A table
# ROW (this file's own lenient free-text "Value" column, same as every
# other field here), per the user's own explicit ask, NOT a third
# standalone Select per beam: after the NBI-overlap bug (see
# panel-bokeh-css-gotchas) turned out to be about too many stacked
# widgets in one toggled Column, adding another standalone widget here
# would cut against the exact fix that resolved it.
NBI_SPECIES_TOOLTIP = "Beam ion species: H (hydrogen), D (deuterium), or T (tritium)."
# Manual shine-through fraction is a real PER-BEAM field (hotjass_core.py
# BeamParams.manual_shine_through_fraction, line 69; default 0.01, not
# overridden per device anywhere in MACHINE_HEATING_PRESETS) -- placed as
# the last row of each beam's own table, matching where hi_jass_app.py's
# own UI puts it (each NBI-n section's own entries block, line 553-554),
# right after that beam's tangent R/Z. Used when Shine-through model =
# Manual (shine_through_select in MODELS); Riviere/Janev instead compute
# their own physics-based fraction and ignore this value.
NBI_MANUAL_SHINE_TOOLTIP = ("Flat shine-through fraction for this beam, used when Shine-through "
                            "model = Manual (ignored by Riviere/Janev).")
NBI1_ROWS = [
    ("nbi1_species", "NBI-1 species (H/D/T)", "D", NBI_SPECIES_TOOLTIP),
    ("nbi1_power", "NBI-1 P_NB [MW]", "10.0", "NBI-1 injected neutral-beam power."),
    ("nbi1_energy", "NBI-1 E_b [keV]", "120.0", "NBI-1 beam injection energy."),
    ("nbi1_tangent_r", "NBI-1 tangent R [m]", "0.65", NBI_TANGENT_TOOLTIP),
    ("nbi1_tangent_z", "NBI-1 tangent Z [m]", "0.0", NBI_TANGENT_TOOLTIP),
    ("nbi1_manual_shine_frac", "NBI-1 shine frac", "0.01",
     NBI_MANUAL_SHINE_TOOLTIP),
]
NBI2_ROWS = [
    ("nbi2_species", "NBI-2 species (H/D/T)", "T", NBI_SPECIES_TOOLTIP),
    ("nbi2_power", "NBI-2 P_NB [MW]", "0.1", "NBI-2 injected neutral-beam power."),
    ("nbi2_energy", "NBI-2 E_b [keV]", "180.0", "NBI-2 beam injection energy."),
    ("nbi2_tangent_r", "NBI-2 tangent R [m]", "0.65", NBI_TANGENT_TOOLTIP),
    ("nbi2_tangent_z", "NBI-2 tangent Z [m]", "0.0", NBI_TANGENT_TOOLTIP),
    ("nbi2_manual_shine_frac", "NBI-2 shine frac", "0.01",
     NBI_MANUAL_SHINE_TOOLTIP),
]
NBI_STRING_KEYS = {"nbi1_species", "nbi2_species"}
ECRH_ROWS = [
    ("ecrh_power", "P_ECRH [MW]", "0.0", "Electron cyclotron resonance heating power (0 = off)."),
    ("ecrh_fe", "ECRH f_e (rest to ions)", "1.0",
     "Fraction of ECRH power delivered directly to electrons (rest to ions)."),
]
ICRH_ROWS = [
    ("icrh_power", "P_ICRH [MW]", "0.0", "Ion cyclotron resonance heating power (0 = off)."),
    ("icrh_fe", "ICRH f_e", "0.5", "Fraction of ICRH power delivered to electrons."),
    ("icrh_fi", "ICRH f_i", "0.5", "Fraction of ICRH power delivered to ions."),
]
# `theme="simple"` + this stylesheet: Tabulator's own default theme brings
# a Bootstrap-ish look (blue-tinted header, heavier borders) that clashed
# with this app's flat gray/white palette -- confirmed via screenshot, not
# guessed -- "simple" plus a thin override gets close to the rest of the
# rail's own BG_GRAY/white convention instead.
#
# The row-hover override fixes a real bug (not a style preference alone):
# Tabulator's own built-in hover rule
# (`.tabulator-row.tabulator-selectable:hover`) sets `color:
# var(--mdc-theme-on-primary)`, which resolves to white in this app's
# `design="material"` context -- confirmed via CDP `getComputedStyle`+
# reading the actual matched CSS rule text, not guessed -- but the
# matching `background-color: var(--mdc-theme-primary)` half of that same
# rule never resolves to anything visibly dark here, so hovering a row
# left WHITE TEXT ON A STILL-WHITE ROW, invisible. `!important` overrides
# both halves with an explicit magenta tint (this app's own established
# color for "highlighted/active" state -- DANTE's selected-machine button,
# the GUI-edit-mode toggle -- so this stays consistent with that) and
# keeps the text color dark/readable instead of relying on the (broken)
# on-primary variable.
#
# The ::-webkit-scrollbar rules make the table's own internal scrollbar
# (see DATA_TABLE_HEIGHT below) visible in turquoise -- Tabulator's/the
# browser's own default thin gray-on-gray scrollbar was barely visible
# against this table's white background, per the user's own explicit ask.
# `scrollbar-width`/`scrollbar-color` cover Firefox; `::-webkit-scrollbar*`
# covers Chromium/Safari (this session's own CDP testing browser included).
DATA_TABLE_CSS = f"""
.tabulator {{ font-size: {RAIL_FONT_SIZE}; border: 1px solid #b7b7b7 !important; }}
.tabulator-row {{ min-height: {RAIL_ROW_HEIGHT}px; background: white !important; }}
.tabulator-cell {{ padding: 3px 8px !important; }}
.tabulator-header {{ background: {TOOLBAR_GRAY} !important; font-weight: 700; }}
.tabulator-col-title {{ font-size: {RAIL_FONT_SIZE}; }}
/* Several labels ("Temp peaking (ion, -1=same)", "Centre-post R [m]
   (-1=R0-a)", "ECRH f_e (rest to ions)") are longer than LABEL_WIDTH can
   fit on one line -- Tabulator's own default cell CSS is nowrap+ellipsis
   (confirmed via CDP getComputedStyle, not guessed), which would silently
   truncate them. Wrapping (matching the tolerance the styled_field()-based
   MODELS section already has via LABEL_LEFT_CSS's own `white-space:
   normal`) keeps the full text visible instead of growing the column very
   wide for a few outlier rows. */
.tabulator-cell[tabulator-field="Parameter"] {{
    white-space: normal !important; text-overflow: clip !important; line-height: 1.3;
    overflow: visible !important; height: auto !important;
}}
.tabulator-row.tabulator-selectable:hover {{
    background-color: rgba(255, 0, 255, 0.16) !important;
    color: #1a1d21 !important;
}}
.tabulator-tableholder {{ scrollbar-width: auto; scrollbar-color: #24bdb3 #e5e5e5; }}
.tabulator-tableholder::-webkit-scrollbar {{ width: 11px; }}
.tabulator-tableholder::-webkit-scrollbar-track {{ background: #e5e5e5; }}
.tabulator-tableholder::-webkit-scrollbar-thumb {{
    background: #24bdb3; border-radius: 5px; border: 2px solid #e5e5e5;
}}
.tabulator-tableholder::-webkit-scrollbar-thumb:hover {{ background: #17a399; }}
"""
# DATA_TABLE_MARGIN's left=6: tables measured at x=12 pre-fix; rail's own
# +2 left-margin bump above (see `rail = pn.Column(...)`) moves that to 14,
# so 6 more here lands each table's own left edge on the same x=20 the
# section header buttons now hit, matching the user's explicit target.
DATA_TABLE_MARGIN = (4, 0, 4, 6)
# The table's own outer `height=` (see make_data_table below) was computed
# from RAIL_ROW_HEIGHT (24, the CSS *minimum* set on `.tabulator-row`
# above) plus a header allowance of 40 -- but a row's ACTUAL rendered
# height (input padding/line-height push it past that minimum) measured
# 36px via CDP, not 24, and the header measured exactly 40. The old
# formula under-allocated by 12px per row, which was invisible for
# PLASMA (already scrolling on purpose) but showed up as an unwanted
# internal scrollbar on every table sized to fit its content exactly (the
# new 2-row NBI-1/NBI-2 tables, plus ECRH/ICRH) -- confirmed via CDP
# (`.tabulator-tableholder` `clientHeight` 46 vs `scrollHeight` 72 for a
# nominal 2-row table), not guessed.
DATA_TABLE_ROW_HEIGHT = 36
DATA_TABLE_HEADER_HEIGHT = 40
CHANGED_CELL_CSS = "border: 2px solid #d90000; box-shadow: inset 0 0 0 1px #d90000;"
# A stronger, visually distinct marker from CHANGED_CELL_CSS (border-only,
# means "differs from the last-applied preset/JSON" -- not wrong, just
# edited) -- INVALID_CELL_CSS adds a filled background so a genuinely
# out-of-range/unparseable value reads as more urgent than a merely-edited
# one, since only this one also blocks Start (see _validate_all_inputs).
INVALID_CELL_CSS = "border: 2px solid #ff0000; background-color: #ffd0d0; box-shadow: inset 0 0 0 1px #ff0000;"


def _v_range(lo: float, hi: float):
    """Validator factory: value must parse as float and lie in [lo, hi]."""
    def check(value) -> bool:
        try:
            x = float(value)
        except (TypeError, ValueError):
            return False
        return lo <= x <= hi
    return check


def _v_range_or(lo: float, hi: float, *sentinels: float):
    """Like _v_range, but also accepts any of `sentinels` exactly -- for
    fields with a real "auto"/"same as electron" sentinel value (e.g.
    temp_peaking_i's -1 = "same as electron", centrepost_r's -1 = "R0-a")
    that would otherwise fall outside the field's own normal numeric range."""
    def check(value) -> bool:
        try:
            x = float(value)
        except (TypeError, ValueError):
            return False
        return x in sentinels or (lo <= x <= hi)
    return check


def _v_species(value) -> bool:
    return str(value).strip().upper() in ("H", "D", "T")


# Per-field validity rules, keyed by the SAME internal keys every ROWS list
# (PLASMA_ROWS/NBI1_ROWS/etc.) already uses -- one dict covering every
# numeric (and the 2 species) rail field, checked live (via _make_row_style
# below, so an invalid cell is highlighted the instant it's typed) AND at
# Start-click time (_validate_all_inputs, which blocks the calculation
# outright) -- per the user's own explicit "provide the input validity
# check for each numeric data... flag it and highlight the field, do not
# Start calculation" ask. Bounds are generous-but-physically-sane (catch
# garbage/negative-where-nonsensical/wildly-out-of-range entries, not
# enforce a narrow "realistic device" window) -- deliberately NOT
# cross-field (e.g. a > R0, d_fraction+t_fraction<=1 aren't checked here),
# since the ask was "for each numeric data" (per-field), not a full
# self-consistency pass.
FIELD_VALIDATORS = {
    # PLASMA_ROWS
    "R0": _v_range(0.01, 50.0), "a": _v_range(0.01, 20.0),
    "kappa": _v_range(0.3, 6.0), "delta": _v_range(-0.999, 0.999),
    "Zeff": _v_range(1.0, 10.0), "B0": _v_range(0.01, 25.0), "Ip": _v_range(0.001, 50.0),
    "density_peaking": _v_range(0.0, 5.0), "temp_peaking": _v_range(0.0, 5.0),
    "temp_peaking_i": _v_range_or(0.0, 5.0, -1.0),
    "centrepost_r": _v_range_or(0.001, 50.0, -1.0),
    "ne0": _v_range(1.0e15, 1.0e22),
    "d_fraction": _v_range(0.0, 1.0), "t_fraction": _v_range(0.0, 1.0),
    "tauE_e": _v_range(1.0e-6, 100.0), "tauE_i": _v_range(1.0e-6, 100.0),
    # NBI1_ROWS / NBI2_ROWS (same keys, both beams)
    "nbi1_species": _v_species, "nbi2_species": _v_species,
    "nbi1_power": _v_range(0.0, 1000.0), "nbi2_power": _v_range(0.0, 1000.0),
    "nbi1_energy": _v_range(0.1, 10000.0), "nbi2_energy": _v_range(0.1, 10000.0),
    "nbi1_tangent_r": _v_range(0.0, 50.0), "nbi2_tangent_r": _v_range(0.0, 50.0),
    "nbi1_tangent_z": _v_range(-50.0, 50.0), "nbi2_tangent_z": _v_range(-50.0, 50.0),
    "nbi1_manual_shine_frac": _v_range(0.0, 1.0), "nbi2_manual_shine_frac": _v_range(0.0, 1.0),
    # ECRH_ROWS / ICRH_ROWS
    "ecrh_power": _v_range(0.0, 1000.0), "ecrh_fe": _v_range(0.0, 1.0),
    "icrh_power": _v_range(0.0, 1000.0), "icrh_fe": _v_range(0.0, 1.0), "icrh_fi": _v_range(0.0, 1.0),
    # CX_MANUAL_ROWS / ROTATION_MANUAL_ROWS
    "cx_loss_fraction": _v_range(0.0, 1.0),
    "cx_n0_over_ne": _v_range(0.0, 1.0), "cx_n0_lcfs_over_ne": _v_range(0.0, 1.0),
    "manual_v_phi_m_s": _v_range(-1.0e7, 1.0e7), "tau_phi_over_tauEi": _v_range(0.001, 1000.0),
}


def _is_value_valid(key: str, value) -> bool:
    validator = FIELD_VALIDATORS.get(key)
    return True if validator is None else validator(value)


def _make_row_style(baseline: dict):
    """Closure factory, not a single shared function: each table needs its
    OWN baseline dict to compare against, so each gets its own style
    function bound to that specific dict. An INVALID value (per
    FIELD_VALIDATORS) takes visual precedence over a merely-CHANGED one --
    a cell can be both, but only the more urgent state needs to be shown."""
    def _row_style(row):
        styles = [""] * len(row)
        key = row.name
        value = row["Value"]
        col = row.index.get_loc("Value")
        if not _is_value_valid(key, value):
            styles[col] = INVALID_CELL_CSS
        elif str(value) != str(baseline.get(key, value)):
            styles[col] = CHANGED_CELL_CSS
        return styles
    return _row_style


def make_data_table(rows, visible_rows: int):
    """Builds one dense Parameter|Value Tabulator table -- shared by every
    numeric rail section (PLASMA/NBI/ECRH/ICRH). `rows`: list of
    (key, label, default_str, tooltip). Returns (table, keys, baseline);
    `baseline` is the "last-applied value" dict apply_rail_values() must
    update per key so preset/JSON loads don't show as user edits (see
    _make_row_style above) -- marks any edited "Value" cell that no longer
    matches it with a red border, registered ONCE via `table.style.apply()`
    below. Panel's own Tabulator re-runs that same function against the
    CURRENT `.value` every time a cell is edited AND every time `.value` is
    reassigned wholesale (confirmed by reading tables.py's own
    `_validate`/`_process_event`, not assumed: both paths preserve+replay
    `style._todo` against the new dataframe), so this one registration
    keeps working after device-preset switches and JSON loads without
    needing to be called again by hand."""
    keys = [key for key, _, _, _ in rows]
    df = pd.DataFrame(
        {"Parameter": [f'<span title="{tip}">{label}</span>' for _, label, _, tip in rows],
         "Value": [value for _, _, value, _ in rows]},
        index=keys,
    )
    baseline = {key: value for key, _, value, _ in rows}
    table = pn.widgets.Tabulator(
        df, show_index=False, header_filters=False, pagination=None,
        selectable=False, sortable=False, movable_columns=False,
        editors={"Parameter": None, "Value": "input"},
        formatters={"Parameter": {"type": "html"}},
        widths={"Parameter": LABEL_WIDTH, "Value": FIELD_WIDTH},
        theme="simple", stylesheets=[DATA_TABLE_CSS],
        disabled=False, margin=DATA_TABLE_MARGIN,
        # An explicit `width=` (not just per-column `widths=`) pins the
        # table's OWN rendered box to a fixed size -- without it, Tabulator
        # stretched a few px past its columns' own combined width whenever
        # its container had extra room to give (confirmed via CDP: table
        # right edge measured 343 instead of the target 340 after a
        # rail-width change that had nothing to do with the table itself).
        # DATA_TABLE_WIDTH is a separate constant from LABEL_WIDTH+
        # FIELD_WIDTH on purpose -- see its own comment above.
        width=DATA_TABLE_WIDTH,
        height=visible_rows * DATA_TABLE_ROW_HEIGHT + DATA_TABLE_HEADER_HEIGHT,
    )
    table.style.apply(_make_row_style(baseline), axis=1)
    return table, keys, baseline


# visible_rows caps PLASMA at ~8 rows tall (14 rows total -> internal
# scroll for the rest, see DATA_TABLE_CSS's scrollbar styling above);
# NBI/ECRH/ICRH are short enough that visible_rows == their own row count,
# so no scrolling is needed there in practice, but the explicit height is
# still what makes each table reserve the right amount of space in the
# rail's own layout flow (an unbounded/natural height was the actual cause
# of PLASMA's own last-row-covered-by-NBI bug, confirmed via screenshot,
# not just a "too tall" symptom) -- so every table gets one, not just
# PLASMA.
plasma_table, PLASMA_KEYS, plasma_baseline = make_data_table(PLASMA_ROWS, visible_rows=8)
nbi1_table, NBI1_KEYS, nbi1_baseline = make_data_table(NBI1_ROWS, visible_rows=len(NBI1_ROWS))
nbi2_table, NBI2_KEYS, nbi2_baseline = make_data_table(NBI2_ROWS, visible_rows=len(NBI2_ROWS))
ecrh_table, ECRH_KEYS, ecrh_baseline = make_data_table(ECRH_ROWS, visible_rows=len(ECRH_ROWS))
icrh_table, ICRH_KEYS, icrh_baseline = make_data_table(ICRH_ROWS, visible_rows=len(ICRH_ROWS))
cx_manual_table, CX_MANUAL_KEYS, cx_manual_baseline = make_data_table(
    CX_MANUAL_ROWS, visible_rows=len(CX_MANUAL_ROWS))
rotation_manual_table, ROTATION_MANUAL_KEYS, rotation_manual_baseline = make_data_table(
    ROTATION_MANUAL_ROWS, visible_rows=len(ROTATION_MANUAL_ROWS))


# Co-/counter-current direction per beam -- a real field in HI-Jass's own
# data (MACHINE_HEATING_PRESETS' 4th tuple element per beam, hi_jass_app.py
# lines 312-331: e.g. DANTE's NBI-2 and TCV's NBI-2 are the counter-current
# ones, everything else in that dict is co-current) that HOT-Jass_web
# hadn't surfaced anywhere until now -- DEVICE_PRESETS below only ever set
# power/energy per beam. NOT a table row: Tabulator's `editors=` is per
# COLUMN, not per cell, and the table's "Value" column is already
# committed to a plain text editor for the numeric rows -- a real Select
# widget (matching MODELS' own Confinement dropdown, same styled_field()
# pattern) is simpler and more correct than fighting Tabulator for a
# one-off categorical cell.
NBI_DIRECTIONS = ["Co-current", "Counter-current"]
nbi1_direction_select = pn.widgets.Select(options=NBI_DIRECTIONS, value="Co-current")
nbi2_direction_select = pn.widgets.Select(options=NBI_DIRECTIONS, value="Counter-current")

plasma_section = collapsible_section("PLASMA", plasma_table, profile_avg_checkbox)
# NBI split into two INDEPENDENT top-level collapsible sections (matching
# HI-Jass/hi_jass_app.py's own real rail structure -- separate "NBI-1"/
# "NBI-2" CollapsibleSections, not one merged section) rather than one
# "NBI" section with two beam-groups stacked inside it -- per the user's
# own explicit choice, after folding tangent R/Z into the tables (the
# OTHER option offered) turned out NOT to fully fix the ECRH/ICRH/MODELS
# overlap either. Confirmed via CDP with the overlap actually reproduced
# this time (a narrower-than-usual viewport plus rapid preset switching,
# unlike every earlier attempt this session): NBI-2's own direction
# Select measured a perfectly correct 52px-tall box (`height=52` was
# working exactly as set), but the ECRH header button after it still got
# positioned essentially AT the select's own top edge, not its bottom --
# proving the bug isn't about any one widget failing to report its size
# (the widget-swap fixes were treating a symptom), it's Bokeh's own
# flexbox layout failing to correctly accumulate offsets across a
# `visible`-toggled Column with SEVERAL stacked children after a batched
# multi-widget property update. Splitting into two separate top-level
# sections means each one's own toggle only ever has to reflow ONE small
# subtree (its own table + its own direction select), not both beams'
# content stacked together -- much less surface for that same class of
# bug to trigger on, independent of which widget types are involved.
nbi1_section = collapsible_section(
    "NBI-1",
    nbi1_table,
    styled_field(nbi1_direction_select, "NBI-1 direction",
                 "Beam injection direction relative to the plasma current: co-current "
                 "(same direction, adds momentum/current) or counter-current (opposite).",
                 label_width=140, field_width=155, height=52),
)
nbi2_section = collapsible_section(
    "NBI-2",
    nbi2_table,
    styled_field(nbi2_direction_select, "NBI-2 direction",
                 "Beam injection direction relative to the plasma current: co-current "
                 "(same direction, adds momentum/current) or counter-current (opposite).",
                 label_width=140, field_width=155, height=52),
)
ecrh_section = collapsible_section("ECRH", ecrh_table)
icrh_section = collapsible_section("ICRH", icrh_table)
# MODELS deliberately stays OUT of the table conversion -- per the user's
# own explicit instruction, model SELECTIONS (Confinement, a dropdown; the
# equipartition checkbox) live here, not as PLASMA table rows, and neither
# one is really "numerical data" a Parameter|Value table fits naturally.
models_section = collapsible_section(
    "MODELS",
    # Order per the user's own explicit follow-up ask: alpha-confined
    # slider 1st, equipartition checkbox 2nd, Confinement select 3rd --
    # everything else (shine-through onward) keeps its original order.
    alpha_confined_slider,
    equip_checkbox,
    styled_field(confinement_select, "Confinement",
                 "Energy confinement time scaling used to close the power balance.",
                 label_width=100, field_width=215),
    styled_field(shine_through_select, "Shine-through",
                 "NBI shine-through calculation: Riviere/Janev/Suzuki (optical-depth chord "
                 "integral) or Manual (flat fraction). Suzuki (1998) is the best-validated "
                 "choice below ~100 keV/amu -- Janev's own fit is only stated-valid above "
                 "that (extrapolated below it) and Riviere is not species- or Zeff-aware.",
                 label_width=100, field_width=215),
    styled_field(orbit_model_select, "Orbit model",
                 "First-orbit loss model for fast ions.",
                 label_width=100, field_width=215),
    styled_field(cx_model_select, "CX-loss",
                 "Charge-exchange loss model for fast ions.",
                 label_width=100, field_width=215),
    cx_manual_table,
    styled_field(rotation_model_select, "Rotation model",
                 "Toroidal rotation model.",
                 label_width=100, field_width=215),
    rotation_manual_table,
    beam_beam_checkbox,
)


def rail_values() -> dict:
    tables = [(plasma_table, PLASMA_KEYS), (nbi1_table, NBI1_KEYS), (nbi2_table, NBI2_KEYS),
              (ecrh_table, ECRH_KEYS), (icrh_table, ICRH_KEYS),
              (cx_manual_table, CX_MANUAL_KEYS), (rotation_manual_table, ROTATION_MANUAL_KEYS)]
    values = {}
    for table, keys in tables:
        df = table.value
        for key in keys:
            # species (H/D/T) is the one table field that's text, not a
            # number -- every other table row in this file is numeric, so
            # _parse_float would silently coerce "D" to 0.0 here.
            if key in NBI_STRING_KEYS:
                values[key] = df.loc[key, "Value"]
            else:
                values[key] = _parse_float(df.loc[key, "Value"])
    values["confinement"] = confinement_select.value
    values["equipartition"] = equip_checkbox.value
    values["nbi1_co_current"] = nbi1_direction_select.value == "Co-current"
    values["nbi2_co_current"] = nbi2_direction_select.value == "Co-current"
    values["profile_averaging"] = profile_avg_checkbox.value
    values["f_alpha"] = alpha_confined_slider.value
    values["shine_through_model"] = shine_through_select.value
    values["orbit_model"] = orbit_model_select.value
    values["cx_model"] = cx_model_select.value
    values["rotation_model"] = rotation_model_select.value
    values["enable_beam_beam"] = beam_beam_checkbox.value
    # `machine_state`/`custom_name_label` are defined further down (with the
    # rest of the MACHINES toolbar group) but only ever READ here inside a
    # function body -- resolved at call time, not at this def's own
    # definition time, so the later-in-file definition is fine (same as
    # every other module-level widget this function already reads). Saves
    # whichever name is CURRENTLY shown selected/highlighted: a real
    # preset's own name if a preset button is magenta, or a custom name
    # carried over from a previously loaded JSON whose own name didn't
    # match any preset (see `_on_read_json_load` below) -- either way, the
    # round-trip (Save then Read) reproduces the same highlighted button or
    # plain-text custom name it started from.
    values["device_name"] = machine_state["custom_name"] or machine_state["selected"]
    return values


def _apply_table_values(table, keys, baseline: dict, cfg: dict) -> None:
    df = table.value.copy()
    changed = False
    for key in keys:
        if key in cfg:
            df.loc[key, "Value"] = str(cfg[key])
            # A preset/JSON-applied value is the new "unedited" reference --
            # only further HAND edits in the table itself should show as
            # changed from here on (see _make_row_style above).
            baseline[key] = str(cfg[key])
            changed = True
    if changed:
        # Reassigning `.value` to a NEW DataFrame (not editing the existing
        # one in place) is what pushes the change to the table -- Panel's
        # param watchers fire on identity/equality change, and mutating a
        # DataFrame in place doesn't produce a new object for that check to
        # see.
        table.value = df


def apply_rail_values(cfg: dict) -> None:
    _apply_table_values(plasma_table, PLASMA_KEYS, plasma_baseline, cfg)
    _apply_table_values(nbi1_table, NBI1_KEYS, nbi1_baseline, cfg)
    _apply_table_values(nbi2_table, NBI2_KEYS, nbi2_baseline, cfg)
    _apply_table_values(ecrh_table, ECRH_KEYS, ecrh_baseline, cfg)
    _apply_table_values(icrh_table, ICRH_KEYS, icrh_baseline, cfg)
    _apply_table_values(cx_manual_table, CX_MANUAL_KEYS, cx_manual_baseline, cfg)
    _apply_table_values(rotation_manual_table, ROTATION_MANUAL_KEYS, rotation_manual_baseline, cfg)
    if "confinement" in cfg and cfg["confinement"] in CONFINEMENT_MODES:
        confinement_select.value = cfg["confinement"]
    if "equipartition" in cfg:
        equip_checkbox.value = cfg["equipartition"]
    if "nbi1_co_current" in cfg:
        nbi1_direction_select.value = "Co-current" if cfg["nbi1_co_current"] else "Counter-current"
    if "nbi2_co_current" in cfg:
        nbi2_direction_select.value = "Co-current" if cfg["nbi2_co_current"] else "Counter-current"
    if "profile_averaging" in cfg:
        profile_avg_checkbox.value = cfg["profile_averaging"]
    if "f_alpha" in cfg:
        alpha_confined_slider.value = cfg["f_alpha"]
    if "shine_through_model" in cfg and cfg["shine_through_model"] in SHINE_THROUGH_MODELS:
        shine_through_select.value = cfg["shine_through_model"]
    if "orbit_model" in cfg and cfg["orbit_model"] in ORBIT_MODELS:
        orbit_model_select.value = cfg["orbit_model"]
    if "cx_model" in cfg and cfg["cx_model"] in CX_MODELS:
        cx_model_select.value = cfg["cx_model"]
    if "rotation_model" in cfg and cfg["rotation_model"] in ROTATION_MODELS:
        rotation_model_select.value = cfg["rotation_model"]
    if "enable_beam_beam" in cfg:
        beam_beam_checkbox.value = cfg["enable_beam_beam"]


# margin=(8,10,8,8): left bumped 8->10 specifically to land the section
# header buttons' own left edge on x=20 (measured via CDP at x=18 before
# this change -- the button's own Panel-default 10px left margin plus
# rail's own 8px summed to 18, so +2 here closes that exact gap; see the
# DATA_TABLE_MARGIN above for the matching table-side fix).
# Magenta scrollbar for the rail's OWN overflow-y (the one scrollbar
# common to the whole rail, as opposed to a single table's own internal
# one -- still turquoise via DATA_TABLE_CSS above, deliberately left as
# the nested/per-section indicator, unlike this outer one) -- switched
# from its own earlier turquoise to magenta, per an explicit follow-up
# ask, matching VIEW_SCROLLBAR_CSS's own magenta (this app's other
# established scrollbar color, e.g. the view tabs' own scroll areas) for
# visual consistency between the two. `stylesheets=` on a plain pn.Column
# reaches its own shadow root the same way it does on a widget (confirmed
# by DATA_TABLE_CSS's own precedent), so this needs no `raw_css=`/
# page-level rule.
RAIL_SCROLLBAR_CSS = """
:host { scrollbar-width: auto; scrollbar-color: magenta #e5e5e5; }
:host::-webkit-scrollbar { width: 11px; }
:host::-webkit-scrollbar-track { background: #e5e5e5; }
:host::-webkit-scrollbar-thumb { background: magenta; border-radius: 4px; border: 2px solid #e5e5e5; }
:host::-webkit-scrollbar-thumb:hover { background: #c400c4; }
"""
# Magenta scrollbar for the view tabs (Geometry + every real-result slot,
# added further down this file) -- same mechanism as RAIL_SCROLLBAR_CSS
# just above, this app's own established magenta (MAGENTA_BUTTON_CSS's
# stops / the Machines-selected color) instead, and BOTH `width`/`height`
# set on `::-webkit-scrollbar` (not just `width`) since those boxes
# scroll in both directions, unlike the rail's vertical-only one.
# Defined here (near RAIL_SCROLLBAR_CSS, well before `geometry_slot` uses
# it) rather than next to `_result_slot_column()` itself, since
# `geometry_slot` is built earlier in the file and a module-level name
# has to exist before that point, unlike a function body's own free
# variables which resolve at CALL time. Per the user's own explicit
# "scrollbars are not visible -- make them in magenta" follow-up: a
# default OS/browser scrollbar can render thin/near-invisible against a
# white content box, which is why the scrollbars added for the earlier
# "views can be clipped" ask weren't actually noticeable even though they
# worked (confirmed via CDP scroll tests in that same round).
VIEW_SCROLLBAR_CSS = """
:host { scrollbar-width: auto; scrollbar-color: magenta #e5e5e5; }
:host::-webkit-scrollbar { width: 12px; height: 12px; }
:host::-webkit-scrollbar-track { background: #e5e5e5; }
:host::-webkit-scrollbar-thumb { background: magenta; border-radius: 4px; border: 2px solid #e5e5e5; }
:host::-webkit-scrollbar-thumb:hover { background: #c400c4; }
"""
rail = pn.Column(
    pn.pane.HTML(f'<span style="font-size:{GROUP_TITLE_FONT_SIZE}; font-weight:700; color:#333;">'
                 f'INPUT DATA</span>', styles={"margin": "2px 0 6px 6px"}),
    plasma_section, nbi1_section, nbi2_section, ecrh_section, icrh_section, models_section,
    styles={"overflow-y": "auto", "min-height": "0", "height": "100%", "background": BG_GRAY},
    width=RAIL_WIDTH + 24, margin=(8, 8, 8, 10), stylesheets=[RAIL_SCROLLBAR_CSS],
)

# =========================================================== status/toasts
status = pn.pane.Markdown("_Ready._", styles={"color": "#444", "font-size": "12px", "margin": "0"})

# ================================================================== Config
# Read JSON -- a modal wrapping a FileInput (native browser file-picker,
# confirmed working from inside an open pn.Modal in HI-Jass/Panel_proto/
# app_dialog.py's own Save/Load settings test) + Load/Close.
read_json_input = pn.widgets.FileInput(accept=".json", width=220)
read_json_status = pn.pane.Markdown("", styles={"font-size": "11px", "color": "#c0392b"})
read_json_load = pn.widgets.Button(name="Load", width=90, stylesheets=[TURQUOISE_BUTTON_CSS])
read_json_close = pn.widgets.Button(name="Close", width=90, stylesheets=[GRAY_BUTTON_CSS])
read_json_modal = pn.Modal(
    pn.Column(
        pn.pane.Markdown("### Read JSON", margin=(0, 0, 4, 0)),
        pn.pane.Markdown("Choose a previously saved config file, then **Load**.",
                          styles={"font-size": "12px", "color": "#444"}),
        read_json_input, read_json_status,
        styles=CONTENT_STYLE, margin=(14, 14, 0, 14),
    ),
    modal_footer(read_json_load, read_json_close),
    name="read-json-dialog", open=False, background_close=False,
    stylesheets=[MODAL_CSS], width=420, height=260, margin=0,
)


def _on_read_json_load(event):
    if not read_json_input.value:
        read_json_status.object = "Choose a file first."
        return
    try:
        cfg = json.loads(read_json_input.value.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        read_json_status.object = "Could not parse that file as JSON."
        return
    apply_rail_values(cfg)
    # `_apply_device_name` (defined further down alongside the MACHINES
    # button grid it updates) highlights the matching preset button, or --
    # if the JSON's own "device_name" doesn't match any of the 6 known
    # presets (a hand-edited/manually-corrected JSON, per the user's own
    # explicit scenario) -- shows it as plain custom text under the
    # buttons instead. Resolved at call time, so the later-in-file def is
    # fine, same as every other forward-reference in this function.
    _apply_device_name(cfg.get("device_name"))
    read_json_status.object = ""
    read_json_modal.open = False
    status.object = "_Config loaded from JSON._"
    pn.state.notifications.success("Config loaded.", duration=3000)


read_json_load.on_click(_on_read_json_load)
read_json_close.on_click(lambda event: setattr(read_json_modal, "open", False))

# Save JSON -- a modal previewing the current rail values as JSON, with a
# real FileDownload (same callback-returns-BytesIO pattern proven in
# app_dialog.py's Save settings) + Close.
save_json_preview = pn.pane.Markdown("", styles={"font-family": "monospace", "font-size": "11px",
                                                  "white-space": "pre-wrap"})
save_json_download = pn.widgets.FileDownload(
    callback=lambda: io.BytesIO(json.dumps(rail_values(), indent=2).encode("utf-8")),
    filename="hot_jass_config.json", label="Save JSON", width=120,
    stylesheets=[TURQUOISE_BUTTON_CSS],
)
save_json_close = pn.widgets.Button(name="Close", width=90, stylesheets=[GRAY_BUTTON_CSS])
save_json_modal = pn.Modal(
    pn.Column(
        pn.pane.Markdown("### Save JSON", margin=(0, 0, 4, 0)),
        pn.Column(save_json_preview, height=280, scroll="y-auto", styles=CONTENT_STYLE),
        margin=(14, 14, 0, 14),
    ),
    modal_footer(save_json_download, save_json_close),
    name="save-json-dialog", open=False, background_close=False,
    stylesheets=[MODAL_CSS], width=460, height=440, margin=0,
)
save_json_close.on_click(lambda event: setattr(save_json_modal, "open", False))


def _open_save_json(event):
    save_json_preview.object = f"```json\n{json.dumps(rail_values(), indent=2)}\n```"
    save_json_modal.open = True


# ------------------------------------------------------- Assumptions (doc)
# Ported verbatim from HI-Jass/Panel_proto/app_dialog.py's own assumptions
# dialog -- same content/rendering split (ASSUMPTIONS_BLOCKS is the ONE
# source for both the on-screen MathJax Markdown and the matplotlib/
# mathtext PDF, restricted to the LaTeX subset both renderers understand).
# `_last_result` (defined here, not next to `_calc_cancel` further down,
# so `_full_assumptions_blocks()`'s own reference to it is already valid
# the FIRST time `_assumptions_markdown()` runs -- at THIS module's own
# load time, building `assumptions_pane`'s initial `.object` a few lines
# below) is populated in `_calc_worker`'s own `_done()` on every
# successful solve, letting the Assumptions dialog show the ACTIVE
# device's real operating-point results (not just generic formulae)
# whenever it's (re)opened. `None` until the first successful Start.
_last_result = {"op": None, "model": None, "vol": None}
ASSUMPTIONS_BLOCKS = [
    ("h", "HI-Jass -- Key Physics Assumptions"),
    ("p", "A condensed excerpt of the model's core assumptions and governing "
          "equations, for reference alongside a run -- see the HI-Jass "
          "User_Manual.md for the full derivations, limitations and literature "
          "references."),
    ("h2", "Plasma shape (Miller D-shape)"),
    ("p", "The poloidal cross-section used throughout (geometry panels, chord "
          "integrals) is the single-triangularity Miller D-shape:"),
    ("eq", r"R(\theta) = R_0 + a\cos\left(\theta+\arcsin(\delta)\sin\theta\right),"
           r"\quad Z(\theta)=\kappa a\sin\theta"),
    ("h2", "Density profile and the Greenwald limit"),
    ("p", "Electron density follows an analytic peaking profile, compared "
          "against the empirical Greenwald density limit:"),
    ("eq", r"n_e(\rho) = n_{e0}(1-\rho^2)^{2p_n}, \quad 0 \leq \rho \leq 1"),
    ("eq", r"n_{GW} = \frac{I_p[\mathrm{MA}]}{\pi a^2}\times10^{20}\ \mathrm{m^{-3}}"),
    ("h2", "Energy confinement: IPB98(y,2) ELMy H-mode"),
    ("p", "The default confinement scaling (ITER Physics Basis, Nucl. Fusion "
          "39 (1999) 2175), fit from conventional-aspect-ratio devices and "
          "flagged as an extrapolation below A = R0/a < 2:"),
    ("eq", r"\tau_E = 0.0562\, I_p^{0.93} B_t^{0.15} n_{19}^{0.41} P_{loss}^{-0.69}"
           r" R_0^{1.97} \kappa^{0.78} \varepsilon^{0.58} M_{eff}^{0.19}"),
    ("h2", "Neutral-beam shine-through"),
    ("p", "The captured/shine-through power split comes from the optical "
          "depth along each beam's tangential chord through the shaped "
          "plasma, not a fixed efficiency:"),
    ("eq", r"\tau_b=\sigma_{stop}(E_b/A_b)\int_{chord} n_e(\rho(s))\,ds,"
           r"\quad f_{shine,b}=e^{-\tau_b}"),
    ("h2", "Fusion power (thermal + beam-target + beam-beam)"),
    ("p", "Thermal D-T fusion uses the Bosch-Hale reactivity at T_i; each "
          "beam's beam-target term integrates its slowing-down distribution "
          "against the stationary target-species cross-section:"),
    ("eq", r"P_{f,thermal}=n_{D0}\,n_{T0}\,\langle\sigma v\rangle_{DT}(T_i)\,V\,E_f"),
    ("p", "Beam-target: a fast beam ion slowing down through a stationary "
          "target-species population (the OTHER of D/T):"),
    ("eq", r"P_{f,beam}=n_{\text{target}}\!\int f_{\text{fast}}(E)\,"
           r"\langle\sigma v\rangle(E)\,dE\,V\,E_f"),
    ("p", "Beam-beam (only when enabled): a reduced, monoenergetic-"
          "population estimate for the pairwise reaction between two "
          "distinct NBI sources:"),
    ("eq", r"P_{f,bb}=n_{b,1}\,n_{b,2}\,\langle\sigma v\rangle(E_{rel})\,V\,E_f"),
]


def _full_assumptions_blocks() -> list:
    """ASSUMPTIONS_BLOCKS' own generic/default formulae (kept exactly
    as-is, per the user's own explicit "keep the generic expressions"
    ask) PLUS, once a calculation has actually run, `_operating_point_blocks()`'s
    own device-specific "models actually selected, their expressions, and
    their results" section. `_operating_point_blocks` itself is defined
    much later in this file (the real-calculation section, alongside
    `_tex_num`/`hj_physics`/etc. it needs) -- a forward reference, safe
    here for the same reason every other one in this file is: this
    function is only ever CALLED later (a button click / PDF download,
    both well after the whole module has finished loading), never at
    this point in the file's own top-to-bottom execution. Returns the
    bare ASSUMPTIONS_BLOCKS list (no forward-reference call at all) until
    the first successful Start, so the very first render at module-load
    time (building `assumptions_pane`'s own initial `.object` below) never
    risks calling a not-yet-defined function."""
    op, model, vol = _last_result["op"], _last_result["model"], _last_result["vol"]
    if op is None:
        return ASSUMPTIONS_BLOCKS
    return ASSUMPTIONS_BLOCKS + _operating_point_blocks(op, model, vol)


def _assumptions_markdown() -> str:
    parts = []
    for kind, text in _full_assumptions_blocks():
        if kind == "h":
            parts.append(f"# {text}")
        elif kind == "h2":
            parts.append(f"### {text}")
        elif kind == "eq":
            # Every block's own `text` is canonical, single-backslash real
            # LaTeX (`_render_assumptions_pdf()` below uses it verbatim,
            # matplotlib mathtext-compatible) -- but THIS path goes through
            # CommonMark first, which silently strips a lone backslash
            # before any escapable ASCII punctuation character (`%`, `,`,
            # `!`, `(`, `)`, ...) before MathJax ever sees it. Doubling
            # EVERY backslash here survives that stripping correctly in
            # BOTH cases: `\%` -> `\\%` -> (CommonMark) -> `\%` for MathJax
            # (punctuation, needed the double); `\tau` -> `\\tau` ->
            # (CommonMark's `\\` -> `\`, "tau" untouched) -> `\tau` for
            # MathJax (letters were never at risk, but doubling them is a
            # correct no-op, not a second bug -- confirmed via the exact
            # trace in this function's own docstring-equivalent comment on
            # `_operating_point_blocks`). Doing the doubling HERE (not by
            # hand-authoring pre-doubled text in the blocks themselves) is
            # what keeps ONE canonical LaTeX string correct for BOTH
            # renderers at once.
            one_backslash = "\\"
            two_backslashes = one_backslash + one_backslash
            parts.append(f"$$\n{text.replace(one_backslash, two_backslashes)}\n$$")
        else:
            parts.append(text)
    return "\n\n".join(parts)


_PDF_W_IN, _PDF_H_IN = 8.27, 11.69
_PDF_TOP, _PDF_BOTTOM, _PDF_LEFT, _PDF_WRAP = 0.94, 0.06, 0.09, 92


def _pdf_write_blocks(pdf: PdfPages, blocks: list, fig, y: float):
    """Writes (kind, text) blocks onto matplotlib text-only pages inside an
    open PdfPages, starting at Figure `fig`/y-position `y` -- paginating
    (savefig + a fresh Figure) whenever content would overflow the page.
    Returns the (fig, y) the caller is still writing onto, in case a future
    caller wants to keep appending more blocks onto the same running page.
    The caller is responsible for the final `pdf.savefig(fig)` once it has
    no more blocks to add. Factored out of `_render_assumptions_pdf()`
    (its own sole caller), which is now just this loop plus that one
    trailing savefig -- same behaviour, just a named/reusable step."""
    for kind, text in blocks:
        if kind == "h":
            lines, size, weight, ha, gap = [text], 17, "bold", "left", 0.05
        elif kind == "h2":
            lines, size, weight, ha, gap = [text], 13, "bold", "left", 0.035
        elif kind == "eq":
            # A long `\qquad`-joined multi-term eq (e.g. the Fusion tab's
            # own 3-channel row, reused verbatim on the new Operating-Point
            # PDF's page 2 -- the live on-screen MathJax version never hits
            # this, since a browser just wraps/scrolls it) can run past
            # `_PDF_W_IN`'s margins at the default size; mathtext has no
            # wrapping, so this shrinks the font instead of letting it clip
            # off the page edge. Character count is a crude proxy for
            # rendered width (ignores actual glyph widths), but is enough
            # to avoid the egregious case without an extra measurement pass.
            size = 13 if len(text) <= 70 else max(8, round(13 * 70 / len(text)))
            lines, weight, ha, gap = [f"${text}$"], "normal", "center", 0.045
        else:
            lines = textwrap.wrap(text, _PDF_WRAP) or [""]
            size, weight, ha, gap = 10, "normal", "left", 0.026
        need = gap * len(lines)
        if y - need < _PDF_BOTTOM:
            pdf.savefig(fig)
            fig = plt.Figure(figsize=(_PDF_W_IN, _PDF_H_IN))
            y = _PDF_TOP
        x = 0.5 if ha == "center" else _PDF_LEFT
        for line in lines:
            fig.text(x, y, line, fontsize=size, fontweight=weight, ha=ha, va="top")
            y -= gap
        y -= 0.012
    return fig, y


def _render_assumptions_pdf() -> io.BytesIO:
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        fig = plt.Figure(figsize=(_PDF_W_IN, _PDF_H_IN))
        fig, y = _pdf_write_blocks(pdf, _full_assumptions_blocks(), fig, _PDF_TOP)
        pdf.savefig(fig)
    buf.seek(0)
    return buf


assumptions_pane = pn.pane.Markdown(_assumptions_markdown(), styles={"font-size": "13px"})
assumptions_save = pn.widgets.FileDownload(
    callback=_render_assumptions_pdf, filename="hot_jass_assumptions.pdf",
    label="Save (PDF)", width=130, stylesheets=[TURQUOISE_BUTTON_CSS],
)
assumptions_close = pn.widgets.Button(name="Close", width=90, stylesheets=[GRAY_BUTTON_CSS])
assumptions_modal = pn.Modal(
    pn.Column(assumptions_pane, height=500, scroll="y-auto", styles=CONTENT_STYLE,
              margin=(14, 14, 0, 14)),
    modal_footer(assumptions_save, assumptions_close),
    name="assumptions-dialog", open=False, background_close=False,
    stylesheets=[MODAL_CSS], width=720, height=600, margin=0,
)
assumptions_close.on_click(lambda event: setattr(assumptions_modal, "open", False))


def _open_assumptions(event) -> None:
    # Rebuilds the pane EVERY open (not just once at module load) so it
    # always reflects the latest `_last_result` -- a device switch or a
    # fresh Start since the last time this was opened needs a re-render,
    # not the stale snapshot from page load. `_render_assumptions_pdf`
    # needs no equivalent call -- it already reads `_full_assumptions_blocks()`
    # itself, fresh, on every download click.
    assumptions_pane.object = _assumptions_markdown()
    assumptions_modal.open = True

# =============================================================== Machines
# ALL SIX devices' PLASMA numbers now come from HI-Jass/hi_jass_app.py's own
# real PLASMA_PRESETS dict (the main Tk app, not a Panel prototype) --
# confirmed by reading that dict directly, not re-derived or guessed. This
# updates two things vs. the previous version of this dict:
#  1. Adds 7 new PLASMA fields (Zeff/density_peaking/temp_peaking(_i)/
#     d_fraction/t_fraction) for all 6 devices, matching the PLASMA table's
#     own newly-expanded row set above (n_e_min/n_e_max exist in that same
#     source dict too, but were left out of the table per the user's own
#     ask -- "we'll need it later maybe" -- so no preset values for them
#     either, for now). `centrepost_r` isn't included anywhere --
#     hi_jass_app.py's own PLASMA_PRESETS never overrides it for ANY device
#     either, so every device just keeps the table's own generic -1.0
#     ("compute as R0-a") sentinel default.
#  2. CORRECTS ST40/TCV/T-15MD's previously-guessed R0/a/kappa/delta/Ip/
#     confinement values, which this file's own earlier comment here
#     flagged as "NOT independently verified against a primary source" --
#     now checked against that source directly, several were measurably
#     wrong (e.g. TCV's Ip was 1.0 vs the real 0.4; ST40's confinement mode
#     was "H-mode" vs the real "L-mode"). ITER's numbers turned out to
#     already match exactly. DANTE/JET (already sourced from
#     app_dashboard.py's own copy of the same data) needed no changes.
# UPDATE (same day): all 6 devices now also carry real NBI/ECRH/ICRH
# heating data (was: only DANTE/JET had any NBI mix at all, and NO device
# had ECRH/ICRH power) -- sourced from hi_jass_app.py's own
# MACHINE_HEATING_PRESETS dict (lines 312-331), the only place in the
# codebase with this data; see DEVICE_PRESETS' own per-device comments
# below for which of these are cross-checked against real sourced shots
# (DANTE/JET/TCV) vs "not validated anywhere in this repo" per that same
# file's own comment (ITER/ST40/T-15MD). Selecting ANY of the 6 machine
# buttons now resets Plasma AND NBI/ECRH/ICRH together, not just Plasma.
# NBI/ECRH/ICRH power now filled in for all 6 devices, from
# hi_jass_app.py's own MACHINE_HEATING_PRESETS dict (lines 312-331) -- the
# ONLY real source of this data in the codebase (confirmed via a dedicated
# research pass, not guessed; app_dashboard.py's own PRESETS_UI turned out
# to just be a DANTE/JET-only subset of the same numbers, not an
# independent source). That same file's own comment (lines 309-311) flags
# DANTE/JET/TCV as cross-checked against real sourced shots (JET's own
# 26.5 MW NBI / 4 MW ICRH matches real pulse #99971;
# TCV's own NBI-1/NBI-2 cite Karpushov 2017 and Karpushov et al. 2023) --
# but ITER/ST40/T-15MD's heating numbers are flagged there as "not
# validated anywhere in this repo" either, same caveat status as this
# file's own PLASMA numbers had before being checked. ecrh_fe/icrh_fe/
# icrh_fi are NOT per-device anywhere in HI-Jass -- they're global
# constructor defaults on PlasmaParams (hotjass_core.py:35-39:
# ecrh_f_e=1.0, icrh_f_e=0.5, icrh_f_i=0.5), so every device below resets
# them to that same global default rather than leaving them at whatever a
# previous device/hand-edit left in the table.
DEVICE_PRESETS = {
    "DANTE": {"R0": 0.65, "a": 0.35, "kappa": 2.2, "delta": -0.35, "Zeff": 2.0, "B0": 1.5, "Ip": 1.5,
              "density_peaking": 0.1, "temp_peaking": 1.0, "temp_peaking_i": 1.0,
              "ne0": 1.0e20,
              "d_fraction": 0.2, "t_fraction": 0.8, "confinement": "Kaye NSTX H-mode",
              "profile_averaging": False,
              "nbi1_species": "D", "nbi2_species": "T",
              "nbi1_power": 10.0, "nbi1_energy": 120.0, "nbi2_power": 0.1, "nbi2_energy": 180.0,
              "nbi1_co_current": True, "nbi2_co_current": False,
              "nbi1_tangent_r": 0.65, "nbi1_tangent_z": 0.0,
              "nbi2_tangent_r": 0.65, "nbi2_tangent_z": 0.0,
              "nbi1_manual_shine_frac": 0.01, "nbi2_manual_shine_frac": 0.01,
              "ecrh_power": 2.0, "ecrh_fe": 1.0, "icrh_power": 0.0, "icrh_fe": 0.5, "icrh_fi": 0.5,
              "f_alpha": 0.0, "shine_through_model": "Suzuki",
              "orbit_model": "ST orbits - pitch-resolved", "cx_model": "Manual fraction",
              "rotation_model": "Off", "enable_beam_beam": False,
              "cx_loss_fraction": 0.0, "cx_n0_over_ne": 1.0e-5, "cx_n0_lcfs_over_ne": 0.02,
              "manual_v_phi_m_s": 0.0, "tau_phi_over_tauEi": 1.0,
              "tauE_e": 0.15, "tauE_i": 0.15},
    "JET": {"R0": 2.96, "a": 1.25, "kappa": 1.7, "delta": 0.32, "Zeff": 1.5, "B0": 3.45, "Ip": 4.0,
            "density_peaking": 0.1, "temp_peaking": 1.0, "temp_peaking_i": 1.0,
            "ne0": 6.0e19,
            "d_fraction": 0.5, "t_fraction": 0.5, "confinement": "IPB98(y,2) ELMy H-mode",
            "profile_averaging": True,
            "nbi1_species": "D", "nbi2_species": "D",
            "nbi1_power": 13.25, "nbi1_energy": 108.0, "nbi2_power": 13.25, "nbi2_energy": 108.0,
            "nbi1_co_current": True, "nbi2_co_current": True,
            "nbi1_tangent_r": 2.96, "nbi1_tangent_z": 0.0,
            "nbi2_tangent_r": 2.96, "nbi2_tangent_z": 0.0,
            "nbi1_manual_shine_frac": 0.01, "nbi2_manual_shine_frac": 0.01,
            "ecrh_power": 0.0, "ecrh_fe": 1.0, "icrh_power": 4.0, "icrh_fe": 0.5, "icrh_fi": 0.5,
            "f_alpha": 0.0, "shine_through_model": "Janev",
            "orbit_model": "ST orbits - pitch-resolved", "cx_model": "Manual fraction",
            "rotation_model": "Off", "enable_beam_beam": False,
            "cx_loss_fraction": 0.1, "cx_n0_over_ne": 1.0e-5, "cx_n0_lcfs_over_ne": 0.02,
            "manual_v_phi_m_s": 0.0, "tau_phi_over_tauEi": 1.0,
            "tauE_e": 1.5, "tauE_i": 1.5},
    # User-provided preset (2026-09-25), replacing the earlier "not
    # independently validated" placeholder numbers -- loaded verbatim from
    # ITER_config.json (itself saved via this app's own Read/Save JSON
    # round-trip, i.e. real rail_values()-format keys, not hand-typed),
    # per an explicit "set the default preset... from ITER_config.json"
    # ask. Now also carries `centrepost_r`/`equipartition`, which the
    # OLD entry never set at all -- a real gap in the placeholder preset
    # (selecting ITER never touched those two fields, silently leaving
    # whatever a previously-selected device left behind), fixed as a
    # side effect of using the JSON's own complete key set.
    "ITER": {"R0": 6.2, "a": 2.0, "kappa": 1.85, "delta": 0.33, "Zeff": 1.7, "B0": 5.3, "Ip": 15.0,
             "density_peaking": 0.1, "temp_peaking": 1.0, "temp_peaking_i": 1.0,
             "centrepost_r": -1.0, "ne0": 1.0e20,
             "d_fraction": 0.5, "t_fraction": 0.5, "confinement": "IPB98(y,2) ELMy H-mode",
             "equipartition": True, "profile_averaging": True,
             "nbi1_species": "D", "nbi2_species": "D",
             "nbi1_power": 16.5, "nbi1_energy": 1000.0, "nbi2_power": 16.5, "nbi2_energy": 1000.0,
             "nbi1_co_current": True, "nbi2_co_current": True,
             "nbi1_tangent_r": 5.3, "nbi1_tangent_z": 0.6,
             "nbi2_tangent_r": 5.3, "nbi2_tangent_z": -0.6,
             "nbi1_manual_shine_frac": 0.01, "nbi2_manual_shine_frac": 0.01,
             "ecrh_power": 10.0, "ecrh_fe": 1.0, "icrh_power": 10.0, "icrh_fe": 0.5, "icrh_fi": 0.5,
             "f_alpha": 0.0, "shine_through_model": "Janev",
             "orbit_model": "Large-aspect (q* rho_Li)", "cx_model": "Manual fraction",
             "rotation_model": "Off", "enable_beam_beam": False,
             "cx_loss_fraction": 0.1, "cx_n0_over_ne": 1.0e-5, "cx_n0_lcfs_over_ne": 0.02,
             "manual_v_phi_m_s": 0.0, "tau_phi_over_tauEi": 1.0,
             "tauE_e": 3.7, "tauE_i": 3.7},
    # TCV's own two NBI beams ARE cited to real sources (Karpushov 2017;
    # Karpushov et al., Fusion Eng. Des. 187 (2023) 113384) -- ECRH/ICRH
    # power for TCV is not separately flagged either way in that comment.
    # TCV is also the ONLY device anywhere in HI-Jass with a real, sourced,
    # OFF-AXIS tangent_R_m (0.736 m, shared by both beams, same Karpushov
    # 2023 citation) -- every other device's tangent_R below is just its
    # own R0 (on-axis), the model's own fallback default, not a distinct
    # sourced geometry.
    "TCV": {"R0": 0.88, "a": 0.25, "kappa": 1.8, "delta": 0.5, "Zeff": 2.0, "B0": 1.43, "Ip": 0.4,
            "density_peaking": 0.1, "temp_peaking": 1.0, "temp_peaking_i": 1.0,
            "ne0": 5.0e19,
            "d_fraction": 1.0, "t_fraction": 0.0, "confinement": "IPB98(y,2) ELMy H-mode",
            "profile_averaging": False,
            "nbi1_species": "D", "nbi2_species": "D",
            "nbi1_power": 1.3, "nbi1_energy": 28.0, "nbi2_power": 1.0, "nbi2_energy": 55.0,
            "nbi1_co_current": True, "nbi2_co_current": False,
            "nbi1_tangent_r": 0.736, "nbi1_tangent_z": 0.0,
            "nbi2_tangent_r": 0.736, "nbi2_tangent_z": 0.0,
            "nbi1_manual_shine_frac": 0.01, "nbi2_manual_shine_frac": 0.01,
            "ecrh_power": 4.5, "ecrh_fe": 1.0, "icrh_power": 0.0, "icrh_fe": 0.5, "icrh_fi": 0.5,
            "f_alpha": 0.0, "shine_through_model": "Suzuki",
            "orbit_model": "ST orbits - pitch-resolved", "cx_model": "Manual fraction",
            "rotation_model": "Off", "enable_beam_beam": False,
            "cx_loss_fraction": 0.1, "cx_n0_over_ne": 1.0e-5, "cx_n0_lcfs_over_ne": 0.02,
            "manual_v_phi_m_s": 0.0, "tau_phi_over_tauEi": 1.0,
            "tauE_e": 0.005, "tauE_i": 0.005},
    # Not validated anywhere in HI-Jass itself (same caveat as ITER above).
    "ST40": {"R0": 0.45, "a": 0.30, "kappa": 1.8, "delta": 0.4, "Zeff": 1.5, "B0": 3.0, "Ip": 2.0,
             "density_peaking": 0.1, "temp_peaking": 1.0, "temp_peaking_i": 1.0,
             "ne0": 5.0e19,
             "d_fraction": 0.5, "t_fraction": 0.5, "confinement": "Kaye NSTX H-mode",
             "profile_averaging": False,
             "nbi1_species": "D", "nbi2_species": "D",
             "nbi1_power": 2.7, "nbi1_energy": 25.0, "nbi2_power": 0.0, "nbi2_energy": 25.0,
             "nbi1_co_current": True, "nbi2_co_current": True,
             "nbi1_tangent_r": 0.45, "nbi1_tangent_z": 0.0,
             "nbi2_tangent_r": 0.45, "nbi2_tangent_z": 0.0,
             "nbi1_manual_shine_frac": 0.01, "nbi2_manual_shine_frac": 0.01,
             "ecrh_power": 0.0, "ecrh_fe": 1.0, "icrh_power": 0.0, "icrh_fe": 0.5, "icrh_fi": 0.5,
             "f_alpha": 0.0, "shine_through_model": "Suzuki",
             "orbit_model": "ST orbits - pitch-resolved", "cx_model": "Manual fraction",
             "rotation_model": "Off", "enable_beam_beam": False,
             "cx_loss_fraction": 0.0, "cx_n0_over_ne": 1.0e-5, "cx_n0_lcfs_over_ne": 0.02,
             "manual_v_phi_m_s": 0.0, "tau_phi_over_tauEi": 1.0,
             "tauE_e": 0.01, "tauE_i": 0.01},
    # User-provided preset (2026-09-25), replacing the earlier "not
    # independently validated" placeholder numbers -- loaded verbatim from
    # T15_config.json (same provenance/reasoning as ITER's own comment
    # above). Now has real NBI power (was 0.0/0.0, "beams present,
    # unused") and switches both beams to Hydrogen at 80 keV -- E/A = 80
    # keV/amu for H (mass number 1), inside Suzuki's own high-energy
    # table's range (>=100 keV/amu) by only a little; still Suzuki, not
    # Janev, since T-15MD wasn't one of the 2 devices (ITER/JET) the
    # user's own device list kept on Janev.
    "T-15MD": {"R0": 1.5, "a": 0.67, "kappa": 1.8, "delta": 0.3, "Zeff": 1.5, "B0": 2.0, "Ip": 2.0,
               "density_peaking": 0.2, "temp_peaking": 0.5, "temp_peaking_i": 1.0,
               "centrepost_r": -1.0, "ne0": 4.0e19,
               "d_fraction": 0.5, "t_fraction": 0.5, "confinement": "IPB98(y,2) ELMy H-mode",
               "equipartition": True, "profile_averaging": False,
               "nbi1_species": "H", "nbi2_species": "H",
               "nbi1_power": 4.0, "nbi1_energy": 80.0, "nbi2_power": 4.0, "nbi2_energy": 80.0,
               "nbi1_co_current": True, "nbi2_co_current": True,
               "nbi1_tangent_r": 1.2, "nbi1_tangent_z": 0.1,
               "nbi2_tangent_r": 1.2, "nbi2_tangent_z": -0.1,
               "nbi1_manual_shine_frac": 0.01, "nbi2_manual_shine_frac": 0.01,
               "ecrh_power": 5.0, "ecrh_fe": 1.0, "icrh_power": 3.0, "icrh_fe": 0.5, "icrh_fi": 0.5,
               "f_alpha": 0.01, "shine_through_model": "Suzuki",
               "orbit_model": "Large-aspect (q* rho_Li)", "cx_model": "Manual fraction",
               "rotation_model": "Off", "enable_beam_beam": False,
               "cx_loss_fraction": 0.1, "cx_n0_over_ne": 1.0e-5, "cx_n0_lcfs_over_ne": 0.02,
               "manual_v_phi_m_s": 0.0, "tau_phi_over_tauEi": 1.0,
               "tauE_e": 0.1, "tauE_i": 0.1},
}
# 4 columns x 2 rows, per the user's spec; the two `None` slots are reserved
# for future devices without having to re-flow the grid.
MACHINE_GRID = [
    ["DANTE", "ITER", "TCV", None],
    ["ST40", "JET", "T-15MD", None],
]
MACHINE_BTN_WIDTH = 84
machine_buttons: dict[str, pn.widgets.Button] = {}
# `custom_name` holds a JSON-loaded device name that didn't match any of
# the 6 known presets (see `_apply_device_name` below) -- `None` whenever
# a real preset button is the one currently highlighted. `rail_values()`
# (defined further up) reads this dict at SAVE time to round-trip whichever
# is currently active.
machine_state = {"selected": "DANTE", "custom_name": None}
# Plain-text fallback for that custom-name case, per the user's own
# explicit spec: CAPITALS, bold ("thick"), magenta -- originally sat in
# normal flow under the preset button grid, then moved to a fixed pixel
# spot (x=150, y=160, the same page-viewport coordinate space the GUI Edit
# ruler tool's own readout uses) and doubled in font size, per the user's
# own explicit follow-up ask. `position: fixed` (not `absolute`) since the
# target is a literal page coordinate, not anchored to any specific
# toolbar group the way the progress-ring is to session_group (see
# RING_OFFSET_LEFT/TOP's own comment) -- this app's own page has no
# scrolling (`overflow: hidden` on html/body) so fixed and absolute-to-page
# would land identically here, but fixed is the more direct match for
# "put it at this exact screen position" and needs no positioned ancestor.
# Empty string (not just `visible=False`) by default so it takes zero
# layout height in the normal (real-preset-selected) case -- confirmed
# empty pn.pane.HTML renders with no visible box, no separate height
# reservation needed; `pointer-events: none` keeps it from ever
# intercepting clicks meant for whatever sits underneath.
CUSTOM_NAME_LEFT, CUSTOM_NAME_TOP = 150, 160
custom_name_label = pn.pane.HTML(
    "", styles={"position": "fixed", "left": f"{CUSTOM_NAME_LEFT}px",
                "top": f"{CUSTOM_NAME_TOP}px", "margin": "0", "line-height": "1.1",
                "z-index": "500", "pointer-events": "none"})


def _highlight_machine(name: str) -> None:
    """Updates ONLY the button-selection visuals + machine_state -- does
    NOT touch the rail's own values. Split out from `_select_machine` (which
    also applies that preset's canonical DEVICE_PRESETS values) because
    `_apply_device_name` below needs the highlight-only half: a loaded
    JSON's values are already applied via `apply_rail_values(cfg)` by the
    time it runs, and re-applying the preset's own canonical values on top
    would silently discard any hand-edited/manually-corrected fields the
    loaded JSON actually carried."""
    machine_state["selected"] = name
    machine_state["custom_name"] = None
    for n, b in machine_buttons.items():
        b.stylesheets = [MAGENTA_BUTTON_CSS if n == name else GRAY_BUTTON_CSS]
    custom_name_label.object = ""


def _select_machine(name: str) -> None:
    _highlight_machine(name)
    apply_rail_values(DEVICE_PRESETS[name])
    status.object = f"_Machine preset: **{name}**._"


def _apply_device_name(device_name) -> None:
    """Called after a JSON load (`_on_read_json_load` above) with that
    JSON's own "device_name" field (may be None for an older save from
    before this field existed -- left untouched in that case, same as any
    other cfg key `apply_rail_values` doesn't find). A name matching one of
    the 6 real presets highlights that button (WITHOUT reapplying its
    canonical values -- see `_highlight_machine`'s own docstring); any
    other non-empty name is a hand-edited/manually-corrected JSON, per the
    user's own explicit scenario -- deselect every preset button and show
    that name as the plain-text custom label instead."""
    if device_name is None:
        return
    if device_name in DEVICE_PRESETS:
        _highlight_machine(device_name)
        return
    machine_state["selected"] = None
    machine_state["custom_name"] = device_name
    for b in machine_buttons.values():
        b.stylesheets = [GRAY_BUTTON_CSS]
    custom_name_label.object = (
        f'<span style="font-weight:800; color:magenta; letter-spacing:0.5px; '
        f'font-size:24px;">{str(device_name).upper()}</span>')


machine_rows = []
for grid_row in MACHINE_GRID:
    row_widgets = []
    for name in grid_row:
        if name is None:
            row_widgets.append(pn.Spacer(width=MACHINE_BTN_WIDTH, height=26))
            continue
        css = MAGENTA_BUTTON_CSS if name == machine_state["selected"] else GRAY_BUTTON_CSS
        btn = pn.widgets.Button(name=name, width=MACHINE_BTN_WIDTH, height=26, stylesheets=[css])
        btn.on_click(lambda event, n=name: _select_machine(n))
        machine_buttons[name] = btn
        row_widgets.append(btn)
    machine_rows.append(pn.Row(*row_widgets, styles={"gap": "4px"}))
machine_group = pn.Column(*machine_rows, custom_name_label, styles={"gap": "4px"})
# DANTE is pre-highlighted above (machine_state["selected"]) but every
# widget's own hardcoded constructor `value=` is a separate "global
# default" (see the comment above `alpha_confined_slider` etc.) that can
# silently drift out of sync with DEVICE_PRESETS["DANTE"] -- exactly what
# happened when DANTE's own model defaults were changed but the widgets'
# own hardcoded values weren't (f_alpha/shine_through/cx_loss_fraction
# stayed at their old constructor values on first page load until a
# machine button was actually clicked). Applying the selected preset once
# here makes the very first render match DEVICE_PRESETS exactly, same as
# every subsequent button click already does -- single source of truth.
apply_rail_values(DEVICE_PRESETS[machine_state["selected"]])

# ============================================================= Calculation
# A real threaded placeholder calculation (same threading.Thread +
# pn.state.execute() + cooperative threading.Event pattern proven for the
# D:T scan in app_dialog.py) -- no HotJassModel call yet, just enough steps
# to drive a genuinely determinate progress bar + spinner + Stop.
CALC_STEPS = 12
# calc_progress/calc_spinner: HIDDEN (visible=False), not removed, per the
# user's own spec -- replaced on screen by progress_ring below, but kept in
# the object tree/layout so the original indicators still exist if ever
# needed again.
calc_progress = pn.indicators.Progress(value=0, max=CALC_STEPS, width=220, bar_color="info",
                                        visible=False)
calc_spinner = pn.indicators.LoadingSpinner(value=False, size=22, width=22, height=22,
                                             visible=False)
# progress_ring: the logo itself, spinning while a calculation runs. The
# animation is ALWAYS defined and running (`animation: ... infinite`), just
# `animation-play-state: paused` by default -- toggling the HOST element's
# own "logo-spin" class (via Panel's reactive `css_classes`, not raw JS)
# only flips that play-state between paused/running. This is the one thing
# that actually makes "stop where it is" work: pausing a running CSS
# animation freezes it at whatever rotation angle it's already reached,
# whereas removing the `animation` property entirely (the first approach
# tried) snaps the element back to its unrotated 0deg rest state instead --
# confirmed via CDP by reading the element's own computed `transform`
# matrix before/during/after toggling, not just eyeballed.
LOGO_SPIN_CSS = """
img.hotjass-logo {
    display: block;
    animation: hotjass-logo-spin 1s linear infinite;
    animation-play-state: paused;
}
:host(.logo-spin) img.hotjass-logo {
    animation-play-state: running;
}
@keyframes hotjass-logo-spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}
"""
# Reduced again, 180px -> 144px (20% smaller), per the user's follow-up.
# The previous "center it exactly between Start and View" placement made
# Results slide in close enough to Calculation that the ring covered both
# buttons regardless of size -- rather than guess another hardcoded point,
# this is now MOUSE-DRAGGABLE: drag the ring itself to wherever looks
# right, read the live X/Y off the small readout badge (top-left corner,
# always on screen even if the ring gets dragged near an edge), and report
# those two numbers back -- RING_CENTER_X/RING_CENTER_Y below get updated
# to match and the drag script comes back out once the position is final.
# pointer-events is intentionally NOT "none" while this is active: dragging
# needs the wrapper to receive its own mouse events, which also means it
# blocks clicks on whatever it happens to be sitting over meanwhile -- an
# acceptable trade-off for a temporary positioning tool, not the final
# state.
# 144 * 0.6 = 86.4 -> 86: radius reduced 40% per an explicit request, same
# CENTER (RING_OFFSET_LEFT/TOP below, untouched) -- the wrap div/img both
# use `transform:translate(-50%,-50%)` off that same left/top position, so
# shrinking only this one size constant keeps the center pinned exactly
# where it was and just shrinks the ring symmetrically around it.
LOGO_RING_SIZE = 86
# Anchored to session_group (the Exit/Help/Refs column) via plain CSS --
# `position:absolute` on this div, `position:relative` on session_group
# itself (see session_group's own definition below, which now includes
# progress_ring as one of its children) -- instead of the previous
# `position:fixed` at hardcoded VIEWPORT pixels. The difference matters
# for window resize: a viewport-pixel anchor stays put in screen space
# while every toolbar group slides around it as the window is resized
# (Results/Exit's own X position depends on total window width via the
# HSpacer), so the ring would drift out of alignment with Exit the moment
# the window changed size. Anchored to session_group's own box instead,
# it moves WITH Exit automatically, by ordinary CSS layout -- no resize
# listener needed at all. RING_OFFSET_LEFT/TOP are the ring's CENTER,
# relative to session_group's own top-left corner (negative left = to its
# left, matching where the "empty space" in the toolbar actually is).
# Final values, chosen by the user via the drag tool itself and reported
# back -- no longer a computed/measured default.
RING_OFFSET_LEFT = -107
RING_OFFSET_TOP = -57
RING_DRAG_JS = """
<script>
(function() {
    // Plain document.getElementById can't reach these IDs: this whole
    // block (divs + script) is Panel HTML-pane content, which lives inside
    // that pane's OWN shadow root -- same shadow-DOM-crossing requirement
    // as every other cross-widget lookup in this codebase (e.g.
    // HI-Jass/Panel_proto/app_dialog.py's own KEYBOARD_JS). Confirmed as
    // the actual bug behind an earlier version of this drag script not
    // working at all, not guessed: dispatching a real mousedown at the
    // ring's own on-screen coordinates left its cursor style unchanged,
    // meaning the listener below was never attached in the first place --
    // getElementById was silently returning null and the early-return
    // guard was firing every time.
    function* allRoots(root) {
        yield root;
        var walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
        var n;
        while (n = walker.nextNode()) { if (n.shadowRoot) { yield* allRoots(n.shadowRoot); } }
    }
    function findById(id) {
        for (var r of allRoots(document)) {
            var el = r.getElementById ? r.getElementById(id) : null;
            if (el) return el;
        }
        return null;
    }
    // session_group is a Panel object (its "hotjass-session-group" marker
    // is a css_classes entry, not an HTML id -- Panel layout objects don't
    // take a raw id= at all) -- getElementById can never find it. This was
    // the actual bug behind the "not movable, snaps back" report: `anchor`
    // silently came back null, tripping the early-return guard below, so
    // NEITHER the drag listeners NOR the resize-visibility check ever got
    // attached in the first place. Confirmed via CDP (dispatched a real
    // drag at the ring's own on-screen coordinates -- position never
    // changed at all, not even transiently), not guessed.
    function findByClass(cls) {
        for (var r of allRoots(document)) {
            var el = r.querySelector ? r.querySelector('.' + cls) : null;
            if (el) return el;
        }
        return null;
    }
    function findButton(text) {
        for (var r of allRoots(document)) {
            var btns = r.querySelectorAll ? r.querySelectorAll('button') : [];
            for (var i = 0; i < btns.length; i++) {
                if (btns[i].textContent.trim() === text) return btns[i];
            }
        }
        return null;
    }
    var wrap = findById('hotjass-ring-wrap');
    var img = wrap ? wrap.querySelector('img') : null;
    var label = findById('hotjass-ring-coords');
    var anchor = findByClass('hotjass-session-group');
    if (!wrap || !anchor || wrap.dataset.dragBound) return;
    wrap.dataset.dragBound = '1';

    // <img> is draggable="true" by default in every browser (native HTML5
    // drag-and-drop): dragging it starts THAT instead of/alongside the
    // custom mousedown-drag below, moving a translucent GHOST copy while
    // the real element's own left/top never actually change -- on drop,
    // the ghost vanishes and the image appears to "snap back", exactly
    // the bug reported. draggable="false" (set here AND as an HTML
    // attribute on the <img> tag itself, belt and suspenders) disables
    // the native path entirely, leaving only this script's own drag.
    if (img) { img.draggable = false; }

    var dragging = false;
    wrap.addEventListener('mousedown', function(e) {
        dragging = true;
        wrap.style.cursor = 'grabbing';
        if (label) { label.style.display = 'block'; }
        e.preventDefault();
    });
    // Positions are tracked relative to session_group's own box (not raw
    // viewport pixels) so the readout reports numbers directly usable as
    // RING_OFFSET_LEFT/RING_OFFSET_TOP above -- staying resize-safe even
    // while mid-drag.
    document.addEventListener('mousemove', function(e) {
        if (!dragging) return;
        var r = anchor.getBoundingClientRect();
        var left = e.clientX - r.left;
        var top = e.clientY - r.top;
        wrap.style.left = left + 'px';
        wrap.style.top = top + 'px';
        if (label) {
            label.textContent = 'RING_OFFSET_LEFT = ' + Math.round(left) +
                                 '   RING_OFFSET_TOP = ' + Math.round(top);
        }
    });
    document.addEventListener('mouseup', function() {
        if (!dragging) return;
        dragging = false;
        wrap.style.cursor = 'grab';
        if (label) { label.style.display = 'none'; }
    });

    // Tied to Exit's own on-screen visibility, per the user's own ask:
    // below some window width the toolbar's total content (fixed pixel
    // widths throughout, confirmed via CDP -- it doesn't reflow/wrap, it
    // just runs past the right edge of the viewport and gets clipped by
    // the page's own overflow:hidden) pushes Exit/Help/Refs off-screen.
    // Because the ring sits LEFT of session_group (a negative offset), it
    // would otherwise still be VISIBLE for a while after Exit itself is
    // already clipped away -- confirmed via screenshot at 1200px window
    // width, exactly the "overlapping the left Groups" the user flagged.
    // This check runs on load and on every resize and just toggles
    // display based on whether Exit's own rect is still fully on-screen.
    function syncVisibility() {
        var exit = findButton('Exit');
        if (!exit) return;
        var r = exit.getBoundingClientRect();
        var onScreen = r.right <= window.innerWidth && r.left >= 0 && r.width > 0;
        wrap.style.display = onScreen ? '' : 'none';
    }
    window.addEventListener('resize', syncVisibility);
    syncVisibility();
    // A second, delayed call: confirmed via CDP that the immediate call
    // above can race Bokeh's own async mounting of sibling widgets --
    // loading the page ALREADY at a narrow width sometimes finds Exit not
    // rendered yet, so findButton('Exit') returns null and the whole
    // function returns early having set nothing, silently leaving the
    // ring visible with no live resize event ever coming along afterward
    // to correct it. Re-checking once, shortly after initial mount,
    // catches that race without needing a retry loop.
    setTimeout(syncVisibility, 300);
})();
</script>
"""
progress_ring = pn.pane.HTML(
    f'<div id="hotjass-ring-wrap" style="position:absolute; left:{RING_OFFSET_LEFT}px; '
    f'top:{RING_OFFSET_TOP}px; transform:translate(-50%,-50%); width:{LOGO_RING_SIZE}px; '
    f'height:{LOGO_RING_SIZE}px; z-index:50; cursor:grab;">'
    f'<img class="hotjass-logo" width="{LOGO_RING_SIZE}" height="{LOGO_RING_SIZE}" draggable="false" '
    f'src="data:image/png;base64,{LOGO_ICON_B64}"></div>'
    f'<div id="hotjass-ring-coords" style="display:none; position:fixed; left:8px; top:8px; '
    f'z-index:9999; background:rgba(255,255,255,0.92); padding:4px 8px; border-radius:4px; '
    f'font-size:12px; font-family:monospace; color:#333; border:1px solid #999;">'
    f'RING_OFFSET_LEFT = {RING_OFFSET_LEFT:g}   RING_OFFSET_TOP = {RING_OFFSET_TOP:g}</div>'
    + RING_DRAG_JS,
    stylesheets=[LOGO_SPIN_CSS], css_classes=[],
    width=0, height=0, margin=0, sizing_mode="fixed", styles={"overflow": "visible"},
)
# Hidden (visible=False, not removed) per the same "hide, don't delete"
# convention as calc_progress/calc_spinner above -- the spinning logo alone
# now conveys running/frozen state, so the text status line under the
# buttons ("Idle." / "Step N/12..." / "Done..." / "Cancelled...") no longer
# needs to be shown.
calc_status = pn.pane.Markdown("_Idle._", styles={"font-size": "12px", "color": "#444", "margin": "0"},
                                visible=False)
# Widened to ACTION_BTN_WIDTH (matching Assumptions), per the user's ask
# that Calculation's/Results' own action buttons be as wide as Config's --
# since Calculation/Results/Config all share the same GROUP_STYLE padding,
# matching CONTENT width here is what makes the three groups' own outer
# (separator-to-separator) widths come out equal too, with no separate
# "group width" number needed anywhere.
start_btn = pn.widgets.Button(name="Start", width=ACTION_BTN_WIDTH, margin=(1, 0, 0, 0),
                               stylesheets=[TURQUOISE_BUTTON_CSS])
stop_btn = pn.widgets.Button(name="Stop", width=ACTION_BTN_WIDTH, margin=(3, 0, 0, 0), disabled=True,
                              stylesheets=[GRAY_BUTTON_CSS])
_calc_cancel = threading.Event()
# matplotlib's own global state (the mathtext parser's cache in
# particular) is NOT thread-safe -- confirmed the hard way: once
# `_calc_worker`'s background thread started building real matplotlib
# figures (the 4 result tabs) while the Ip-arrow animation's OWN periodic
# callback was concurrently redrawing the geometry figure on the main
# loop, both threads hit that shared cache at once and matplotlib raised
# a garbled `ParseException` on a perfectly valid title string -- a
# classic cross-thread corruption, not a bug in either piece of code on
# its own. `pn.state.execute()` (used to marshal `_calc_worker`'s own UI
# updates) does NOT prevent this: it's a Bokeh document-lock mechanism,
# unrelated to matplotlib's own separate global state. Every function
# that touches a matplotlib Figure (build/tight_layout/savefig, or the
# animation's own artist add/remove + `pane.param.trigger`) now acquires
# this RLock (reentrant -- `_tick_ip_animation`'s own fallback path calls
# `_refresh_geometry()`, which needs to re-acquire it from the same
# thread) before doing so.
_MPL_LOCK = threading.RLock()


def _calc_worker():
    # The per-step sleep(0.2) loop is now PURELY a UX pace-setter (keeps
    # the progress bar/Ip-arrow animation running for a couple seconds so
    # Start doesn't look instantaneous) -- the real solve below it is a
    # single 0-D operating point, not a slow per-step scan, so it runs
    # once, after the loop, not per step. `_build_model`/`build_*_tab`
    # etc. are all defined LATER in this file (the real-calculation
    # section, after Geometry) -- fine, resolved at this CALL time (a
    # background thread, well after the whole module has finished
    # loading), same as every other forward-reference already in this
    # file (e.g. `_refresh_geometry` used inside `_tick_ip_animation`).
    cancelled_at = None
    for i in range(CALC_STEPS):
        if _calc_cancel.is_set():
            cancelled_at = i
            break
        time.sleep(0.2)
        step = i + 1

        def _update(step=step):
            calc_progress.value = step
            calc_status.object = f"_Step {step}/{CALC_STEPS}..._"

        pn.state.execute(_update)

    result_error = None
    op = model = vol = None
    if cancelled_at is None:
        try:
            model = _build_model()
            op = model.operating_point()
            vol = model.plasma_volume()
            if not op.feasible:
                result_error = op.infeasible_reason or "Operating point not feasible at these inputs."
        except Exception as exc:  # surface, don't crash the session
            result_error = f"{type(exc).__name__}: {exc}"

    def _done():
        calc_spinner.value = False
        progress_ring.css_classes = []  # pauses the spin -- freezes at its current angle
        start_btn.disabled = False
        stop_btn.disabled = True
        # Stops for BOTH a normal finish and a cancellation (this same
        # _done() runs either way) -- one call covers both, no separate
        # stop needed in _on_stop -- same reasoning as
        # app_dialog.py's own _done()/_stop_ip_animation() split.
        _stop_ip_animation()
        if cancelled_at is not None:
            calc_status.object = f"_Cancelled at step {cancelled_at}/{CALC_STEPS}._"
        elif result_error is not None:
            calc_status.object = f"_Calculation failed: {result_error}_"
            _show_calc_error(result_error)
        else:
            calc_status.object = "**Done** -- operating point solved."
            _last_result["op"], _last_result["model"], _last_result["vol"] = op, model, vol
            _refresh_result_tabs(op, model, vol)

    pn.state.execute(_done)


# (table, rows) for every numeric/species rail section -- the single list
# both `_validate_all_inputs()` and, in principle, any future "check
# everything" pass should iterate, rather than each hand-rolling its own
# copy of these 7 pairs.
_ALL_RAIL_TABLES = [
    (plasma_table, PLASMA_ROWS), (nbi1_table, NBI1_ROWS), (nbi2_table, NBI2_ROWS),
    (ecrh_table, ECRH_ROWS), (icrh_table, ICRH_ROWS),
    (cx_manual_table, CX_MANUAL_ROWS), (rotation_manual_table, ROTATION_MANUAL_ROWS),
]


def _validate_all_inputs() -> list:
    """(label, value) for every rail cell that fails its own FIELD_VALIDATORS
    check, across all 7 tables -- the invalid cells are ALREADY highlighted
    live (via _make_row_style, on every edit), this is the separate
    Start-time gate that actually blocks the calculation per the user's own
    explicit "do not Start calculation" ask."""
    failures = []
    for table, rows in _ALL_RAIL_TABLES:
        for key, label, _, _ in rows:
            value = table.value.loc[key, "Value"]
            if not _is_value_valid(key, value):
                failures.append((label, value))
    return failures


def _on_start(event):
    failures = _validate_all_inputs()
    if failures:
        shown = "; ".join(f"{label} = {value!r}" for label, value in failures[:4])
        more = f"  (+{len(failures) - 4} more)" if len(failures) > 4 else ""
        calc_status.object = (f"**Invalid input(s) -- fix the highlighted field(s) "
                               f"before starting:** {shown}{more}")
        return
    _calc_cancel.clear()
    start_btn.disabled = True
    stop_btn.disabled = False
    calc_progress.value = 0
    calc_spinner.value = True
    progress_ring.css_classes = ["logo-spin"]  # resumes the spin from wherever it froze
    calc_status.object = "_Starting..._"
    # Runs the Ip arrow around the R0 axis for the duration of the
    # calculation, like a real toroidal current flowing -- per the user's
    # own explicit "make it run along the axis during Calculation
    # 'progress' (like proto app_dialog)" ask; ported from that
    # file's own `_start_ip_animation()`.
    _start_ip_animation()
    threading.Thread(target=_calc_worker, daemon=True).start()


def _on_stop(event):
    _calc_cancel.set()
    stop_btn.disabled = True


start_btn.on_click(_on_start)
stop_btn.on_click(_on_stop)

# =================================================================== Results
# "View" opens ONE summary dialog -- per the user's own explicit follow-up
# ask after the previous "Operating point / Scans" selection-dialog design
# ("The Results output is overloaded... show a dialog with a view panel,
# where all the 12 plots (from all the Tabs) are organized in a Table (3
# rows, 4 columns), and only the most important device parameters are
# shown below the table - the layout is similar to Summary in HI-Jass,
# nothing else!"). This REPLACES that earlier multi-page Inputs/Models/
# Settings + mosaic + per-tab-text design entirely -- no selection step,
# no Scans placeholder, just the one summary view. Modeled directly on
# HI-Jass/hi_jass_app.py's own `_render_summary`/`_summary_parameters`
# (`fig.subplots(3, 4)` + `fig.text(...)` params block below, one Figure
# exported as-is for both PNG and PDF via `_export_summary`), not
# reinvented -- the 12 panels are this app's own 5 tabs' individual plots
# (Geometry has 2, Plasma 2, Beam 4, Power 2, Fusion 2 = 12), not HI-Jass's
# own density-SCAN curves (this app has no scan solver -- see the
# now-removed "Scans (not active now)" placeholder from the prior design).


def _summary_parameters_text(op, model: HotJassModel) -> str:
    """Condensed monospace multi-line block of "the most important device
    parameters" -- device geometry/field/current, Greenwald fraction,
    confinement + tauE used, every MODELS on/off state, ECRH/ICRH, per-beam
    NBI, and the headline totals (P_total/P_fus/Q/neutron rate). Adapted
    from HI-Jass's own `_summary_parameters()` (same dense single-block
    style, `fig.text(..., family="monospace")` below the plot grid), using
    this app's own real field/widget names rather than HI-Jass's -- not a
    verbatim port, since the two rails don't expose identical state
    (e.g. this app's confinement_select.value IS the display label,
    HI-Jass keeps a separate confinement_var)."""
    plasma = model.plasma
    device = machine_state["custom_name"] or machine_state["selected"] or "(custom / hand-edited)"
    n_line, n_gw, f_gw = _greenwald(model)
    gw_warn = "  ! above Greenwald limit" if f_gw > 1.0 else ""
    alpha_state = (f"ON (f_alpha={alpha_confined_slider.value:.3g})"
                   if alpha_confined_slider.value > 0.0 else "off")
    p_total_mw = (op.P_e_w + op.P_i_w + op.P_aux_e_w + op.P_aux_i_w + op.P_alpha_w) * 1.0e-6
    q_val = op.pf_total_w / op.P_NB_total_w if op.P_NB_total_w else float("nan")
    lines = [
        f"Device: {device}    R0={plasma.major_radius:.3g} m    a={plasma.minor_radius:.3g} m    "
        f"kappa={plasma.elongation:.3g}    delta={plasma.triangularity:.3g}",
        f"B0={plasma.toroidal_field:.3g} T    Ip={plasma.plasma_current * 1.0e-6:.3g} MA    "
        f"Zeff={plasma.effective_charge:.3g}    ne0={plasma.central_density:.3g} m^-3",
        f"n_GW={n_gw:.3g} m^-3    <n_e>/n_GW={f_gw:.3g}{gw_warn}    "
        f"D/T={plasma.deuterium_fraction:.3g}/{plasma.tritium_fraction:.3g}",
        f"Confinement={confinement_select.value}    tauE,e={op.tau_E_s:.3g} s    "
        f"tauE,i={op.tau_Ei_s:.3g} s    equipartition={'ON' if equip_checkbox.value else 'off'}",
        f"Alpha heating={alpha_state}    first-orbit loss=ON [{orbit_model_select.value}]    "
        f"CX-loss={cx_model_select.value}",
        f"Rotation={rotation_model_select.value}    beam-beam fusion={'ON' if beam_beam_checkbox.value else 'off'}    "
        f"profile-corrected 0-D={'ON' if plasma.profile_averaging else 'off'}",
        f"ECRH={plasma.p_ecrh_MW:.3g} MW (f_e={plasma.ecrh_f_e:.3g})    "
        f"ICRH={plasma.p_icrh_MW:.3g} MW (f_e={plasma.icrh_f_e:.3g}, f_i={plasma.icrh_f_i:.3g})",
    ]
    for i, beam in enumerate(model.beams, start=1):
        lines.append(f"NBI-{i}: {beam.species.upper()}    P={beam.power_MW:.3g} MW    "
                      f"E={beam.beam_energy_keV:.3g} keV    "
                      f"{'co' if beam.co_current else 'counter'}-current")
    lines.append(f"P_total={p_total_mw:.3g} MW    P_fus={op.pf_total_w * 1.0e-6:.3g} MW    "
                 f"Q={q_val:.3g}    Y_n={op.neutron_rate_s:.3g} s^-1")
    return "\n".join(lines)


SUMMARY_FIGSIZE = (13.5, 9.0)


def _build_summary_fig(op, model: HotJassModel, vol: float):
    """One Figure: a 3x4 grid of the same 12 individual panels the 5 View
    Tabs already show (Geometry x2, Plasma x2, Beam x4, Power x2, Fusion
    x2), each independently re-plotted at a compact size (smaller fonts,
    fewer decorations) -- mirroring HI-Jass's own `_render_summary`, which
    likewise re-plots its own summary panels rather than reusing the
    full-size tab Figures verbatim (those are tuned for a single large
    panel, not a 12-up grid). Physics/data calls are the SAME helpers the
    live tabs use (`_beam_chord`, `_central_and_avg_temps`, `_greenwald`,
    `hj_physics.*`) -- only the plotting/decoration code is condensed, no
    numbers are re-derived differently. `model.plasma`/`model.beams` (the
    model actually solved for `op`), not a live rail re-read -- keeps this
    view consistent with the solved results even if the rail has since
    been hand-edited without pressing Start again."""
    plasma = model.plasma
    rho = model.rho_grid()
    density = model.density_profile(rho)
    Te = op.Te_keV or 1.0
    device = machine_state["custom_name"] or machine_state["selected"] or "(custom / hand-edited)"
    colors = ["tab:blue", "tab:orange"]
    chords = [_beam_chord(b, plasma, Te) for b in model.beams]

    fig = plt.Figure(figsize=SUMMARY_FIGSIZE, dpi=GEOM_DPI)
    axes = fig.subplots(3, 4)
    fs = 8.5

    # ---- row 1: Geometry (top view, poloidal cross-section), Plasma (n_e, T)
    ax = axes[0, 0]
    R0, a = plasma.major_radius, plasma.minor_radius
    r_cp = plasma.centrepost_radius if plasma.centrepost_radius > 0.0 else (R0 - a)
    th = np.linspace(0.0, 2.0 * np.pi, 200)
    for r in (R0 - a, R0 + a):
        ax.plot(r * np.cos(th), r * np.sin(th), "-", color="0.6", lw=0.8)
    ax.plot(R0 * np.cos(th), R0 * np.sin(th), "--", color="0.6", lw=0.8)
    ax.fill(r_cp * np.cos(th), r_cp * np.sin(th), color="0.75", zorder=0)
    lim = (R0 + a) * 1.15
    nb = len(model.beams)
    for i, beam in enumerate(model.beams):
        c = colors[i % len(colors)]
        phi = np.deg2rad(38.0 * (i - (nb - 1) / 2.0))
        Rt_raw = beam.tangent_R_m if beam.tangent_R_m is not None else R0
        Rt = min(Rt_raw if Rt_raw > 0.0 else R0, R0 + a)
        p = np.array([Rt * np.cos(phi), Rt * np.sin(phi)])
        d = np.array([-np.sin(phi), np.cos(phi)])
        t0, t1 = -0.85 * lim, 0.85 * lim
        if not beam.co_current:
            t0, t1 = -t1, -t0
            d = -d
        p1, p2 = p + d * t0, p + d * t1
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=c, lw=1.1)
        # Arrowhead (55% along, matching build_geometry_pane's own
        # placement/style) + impact-point dot -- per the user's own
        # explicit "show all the arrows (NBI, current), the beam impact
        # points... in the Results View" ask; this compact panel had
        # previously dropped both to save space, unlike the live Geometry
        # tab it's condensed from.
        ax.annotate("", xy=(p1 + (p2 - p1) * 0.55), xytext=p1,
                    arrowprops=dict(arrowstyle="-|>,head_length=0.7,head_width=0.3",
                                     color=c, lw=1.2, mutation_scale=11))
        ax.plot([p[0]], [p[1]], "o", color=c, ms=3)
    # Plasma-current arrow -- reuses the SAME `_draw_ip_arrow()` the live
    # Geometry tab itself calls (not reimplemented), at its resting angle
    # (pi) since this is a static post-calculation snapshot, not the
    # Start-time animation.
    _draw_ip_arrow(ax, R0)
    ax.text(-R0 * 1.1, 0.0, r"$I_p$", color="0.35", fontsize=fs, fontweight="bold", va="center", ha="right")
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect("equal")
    ax.set_title("Geometry (top view)", fontsize=fs)
    ax.tick_params(labelsize=fs * 0.8)

    ax = axes[0, 1]
    theta = np.linspace(0.0, 2.0 * np.pi, 300)
    delta_c = np.clip(plasma.triangularity, -0.999, 0.999)
    ax.plot(R0 + a * np.cos(theta + np.arcsin(delta_c) * np.sin(theta)), plasma.elongation * a * np.sin(theta))
    ax.plot(R0, 0.0, marker="+", color="tab:red", markersize=7)
    # Beam impact points (R,Z) -- same (tangent_R, tangent_Z) markers the
    # live Geometry tab shows on this same panel.
    for i, beam in enumerate(model.beams):
        Rt_raw = beam.tangent_R_m if beam.tangent_R_m is not None else R0
        ax.plot([Rt_raw], [beam.tangent_Z_m], marker="x", color=colors[i % len(colors)], ms=5, mew=1.5, zorder=5)
    ax.set_aspect("equal")
    ax.set_title("Plasma shape", fontsize=fs)
    ax.tick_params(labelsize=fs * 0.8)

    ax = axes[0, 2]
    ax.plot(rho, density / 1.0e20, color="tab:blue")
    ax.set_title(r"$n_e(\rho)$", fontsize=fs)
    ax.set_xlabel(r"$\rho$", fontsize=fs * 0.9)
    ax.tick_params(labelsize=fs * 0.8)
    ax.grid(alpha=0.25)

    ax = axes[0, 3]
    te_c, ti_c, te_avg, ti_avg = _central_and_avg_temps(op, plasma)
    te_profile = model.temperature_profile(rho, te_c)
    ti_profile = model.temperature_profile(rho, ti_c, ion=True)
    ax.plot(rho, te_profile, color="tab:green", label=r"$T_e$")
    ax.plot(rho, ti_profile, color="tab:red", label=r"$T_i$")
    ax.set_title(r"$T_e,\ T_i(\rho)$", fontsize=fs)
    ax.legend(fontsize=fs * 0.75)
    ax.tick_params(labelsize=fs * 0.8)
    ax.grid(alpha=0.25)

    # ---- row 2: Beam (tau_S, survival, birth-vs-rho, slowing-down dist.)
    ax = axes[1, 0]
    edge_cut = max(len(rho) - 4, 1)
    rho_tau = rho[:edge_cut]
    ne_floor = np.maximum(density[:edge_cut], 1.0e17)
    te_floor = np.maximum(model.temperature_profile(rho, Te)[:edge_cut], 0.05)
    for i, beam in enumerate(model.beams):
        c = colors[i % len(colors)]
        sp, eb = beam.species.upper(), beam.beam_energy_keV
        tau_prof = np.array([hj_physics.thermalization_time(float(nei), float(tei), eb, sp)
                              for nei, tei in zip(ne_floor, te_floor)])
        ax.plot(rho_tau, tau_prof * 1.0e3, color=c, label=f"NBI-{i + 1}")
    ax.set_yscale("log")
    ax.set_title(r"$\tau_S(\rho)$", fontsize=fs)
    ax.legend(fontsize=fs * 0.7)
    ax.tick_params(labelsize=fs * 0.8)
    ax.grid(alpha=0.25, which="both")

    ax = axes[1, 1]
    for i, ch in enumerate(chords):
        if ch is None:
            continue
        ax.plot(ch["s"], ch["survival"], color=colors[i % len(colors)], lw=1.2, label=f"NBI-{i + 1}")
    ax.set_ylim(0.0, 1.03)
    ax.set_title("Beam survival", fontsize=fs)
    ax.legend(fontsize=fs * 0.7)
    ax.tick_params(labelsize=fs * 0.8)
    ax.grid(alpha=0.25)

    ax = axes[1, 2]
    edges = np.linspace(0.0, 1.0, 26)
    ctr = 0.5 * (edges[:-1] + edges[1:])
    dr_ = edges[1] - edges[0]
    smooth = np.array([0.25, 0.5, 0.25])
    cutoffs = []
    for i, (beam, ch) in enumerate(zip(model.beams, chords)):
        if ch is None:
            continue
        c = colors[i % len(colors)]
        f_capt = op.f_capture[i] if op.f_capture else 1.0
        f_orb = op.f_orbit_loss[i] if op.f_orbit_loss else 0.0
        f_cx = op.f_cx_loss[i] if op.f_cx_loss else plasma.cx_loss_fraction
        w_mw = beam.power_MW * f_capt * (1.0 - f_orb) * (1.0 - f_cx)
        hist, _ = np.histogram(ch["rho"], bins=edges, weights=ch["birth"] * ch["ds"])
        if hist.sum() > 0:
            hist = hist / hist.sum() * w_mw / dr_
        hist = np.convolve(hist, smooth, mode="same")
        ax.plot(ctr, hist, color=c, lw=1.1, label=f"NBI-{i + 1}")
        rc = _orbit_cutoff_rho(beam, plasma)
        if rc < 0.999:
            cutoffs.append(rc)
            ax.axvline(rc, color=c, ls="--", lw=0.9, alpha=0.75)
    if cutoffs:
        # Per the user's own explicit "show... the orbit-loss region in
        # the Results View" ask -- this compact panel had dropped it,
        # unlike the live Beam tab's own equivalent panel.
        ax.axvspan(min(cutoffs), 1.0, color="0.5", alpha=0.12)
    ax.set_xlim(0.0, 1.0)
    ax.set_title("Fast-ion birth", fontsize=fs)
    ax.legend(fontsize=fs * 0.7)
    ax.tick_params(labelsize=fs * 0.8)
    ax.grid(alpha=0.25)

    ax = axes[1, 3]
    for i, beam in enumerate(model.beams):
        sp, eb = beam.species.upper(), beam.beam_energy_keV
        f_capt = op.f_capture[i] if op.f_capture else 1.0
        f_orb = op.f_orbit_loss[i] if op.f_orbit_loss else 0.0
        f_cx = op.f_cx_loss[i] if op.f_cx_loss else plasma.cx_loss_fraction
        p_use = beam.power_MW * 1.0e6 * f_capt * (1.0 - f_orb) * (1.0 - f_cx)
        tau_s = hj_physics.thermalization_time(op.ne0_m3, Te, eb, sp)
        nb0_i = p_use * tau_s / (eb * 1.0e3 * hj_physics.E_CHARGE * max(vol, 1.0e-9))
        grid = np.linspace(1.0e-3, eb, 200)
        fE = hj_physics.slowing_down_distribution(Te, nb0_i, eb, grid, sp)
        ax.plot(grid, fE, color=colors[i % len(colors)], label=f"NBI-{i + 1}")
    ax.set_ylim(bottom=0.0)
    ax.set_title("Slowing-down dist.", fontsize=fs)
    ax.legend(fontsize=fs * 0.7)
    ax.tick_params(labelsize=fs * 0.8)
    ax.grid(alpha=0.25)

    # ---- row 3: Power (waterfall, pie), Fusion (P_fus profile, pie)
    mw = 1.0e-6
    v = {"P_inj": op.P_NB_total_w * mw, "shine": op.P_shine_w * mw, "orbit": op.P_orbit_loss_w * mw,
         "cx": op.P_cx_loss_w * mw, "P_use": op.P_useful_w * mw, "P_e": op.P_e_w * mw, "P_i": op.P_i_w * mw}
    ax = axes[2, 0]
    bars = [(0.0, v["P_inj"], "#3b6fb0"), (v["P_inj"] - v["shine"], v["shine"], "#c0504d"),
            (v["P_inj"] - v["shine"] - v["orbit"], v["orbit"], "#c0504d"),
            (v["P_use"], v["cx"], "#c0504d"), (0.0, v["P_use"], "#4f9d5d"),
            (0.0, v["P_e"], "#3fa7a7"), (0.0, v["P_i"], "#e0913a")]
    for i, (bottom, height, color) in enumerate(bars):
        ax.bar(i, max(height, 0.0), bottom=bottom, width=0.62, color=color, edgecolor="black", linewidth=0.4)
    ax.set_xticks(range(len(bars)))
    ax.set_xticklabels(["inj", "shine", "orbit", "cx", "use", "e", "i"], fontsize=fs * 0.75)
    ax.set_title("Power flow [MW]", fontsize=fs)
    ax.tick_params(labelsize=fs * 0.8)
    ax.grid(axis="y", alpha=0.25)

    ax = axes[2, 1]
    wedges = [v["shine"], v["orbit"], v["cx"], v["P_e"], v["P_i"]]
    names = ["shine", "orbit", "cx", "e-heat", "i-heat"]
    pie_colors = ["#c0504d", "#b03a37", "#d98b88", "#3fa7a7", "#e0913a"]
    keep = [(w, n, c) for w, n, c in zip(wedges, names, pie_colors) if w > 1.0e-9]
    if keep:
        ws, ns, cs = zip(*keep)
        ax.pie(ws, labels=ns, colors=cs, autopct="%1.0f%%", textprops={"fontsize": fs * 0.7}, startangle=90)
    ax.set_title(f"Split of {v['P_inj']:.2f} MW", fontsize=fs)

    prof_on = plasma.profile_averaging
    ti_c_show = (op.Ti0_keV if prof_on and op.Ti0_keV is not None else op.Ti_keV) or 0.0
    p_ti_show = plasma.temp_peaking if plasma.temp_peaking_i < 0.0 else plasma.temp_peaking_i
    pk_n = 1.0 + 2.0 * max(plasma.density_peaking, 0.0) if prof_on else 1.0
    nD0_axis, nT0_axis, ne_axis = op.nD0_m3 * pk_n, op.nT0_m3 * pk_n, op.ne0_m3
    th_total = (
        hj_physics.thermal_fusion_power_density_profile(rho, nD0_axis, nT0_axis, ti_c_show,
                                                          plasma.density_peaking, p_ti_show)
        + hj_physics.thermal_dd_power_density_profile(rho, nD0_axis, ti_c_show, plasma.density_peaking, p_ti_show))
    bt_total = np.zeros_like(rho)
    for i, beam in enumerate(model.beams):
        sp, eb = beam.species.upper(), beam.beam_energy_keV
        # A hydrogen beam doesn't undergo D-T/D-D fusion -- skip it here
        # too (this re-derives the same profile the solver's own pf_beam_w
        # already excludes it from, see solve.py's own per-beam loop
        # comment; beam_target_power_density_profile() itself has no
        # species guard, so this plotting code needs the same explicit
        # skip or it would silently draw a bogus contribution).
        if sp not in ("D", "T"):
            continue
        f_capt = op.f_capture[i] if op.f_capture else 1.0
        f_orb = op.f_orbit_loss[i] if op.f_orbit_loss else 0.0
        f_cx = op.f_cx_loss[i] if op.f_cx_loss else plasma.cx_loss_fraction
        p_use = beam.power_MW * 1.0e6 * f_capt * (1.0 - f_orb) * (1.0 - f_cx)
        tau_s0 = hj_physics.thermalization_time(ne_axis, Te, eb, sp)
        nb0_axis = p_use * tau_s0 / (eb * 1.0e3 * hj_physics.E_CHARGE * max(vol, 1.0e-9))
        target_n = nT0_axis if sp == "D" else nD0_axis
        bt_total += hj_physics.beam_target_power_density_profile(
            rho, nb0_axis, target_n, Te, eb, sp, ne_axis, plasma.density_peaking, plasma.temp_peaking)
        if sp == "D" and nD0_axis > 0.0:
            bt_total += hj_physics.beam_target_dd_power_density_profile(
                rho, nb0_axis, nD0_axis, Te, eb, ne_axis, plasma.density_peaking, plasma.temp_peaking)
    ax = axes[2, 2]
    ax.plot(rho, th_total / 1.0e3, label="thermal")
    ax.plot(rho, bt_total / 1.0e3, label="beam")
    ax.set_title(r"$P_{fus}(\rho)$", fontsize=fs)
    ax.legend(fontsize=fs * 0.7)
    ax.tick_params(labelsize=fs * 0.8)
    ax.grid(alpha=0.25)

    channels = [(op.pf_thermal_w * mw, "DT-th", "#4f9d5d"), (op.pf_beam_w * mw, "DT-bt", "#3fa7a7"),
                (op.pf_bb_dt_w * mw, "DT-bb", "#8064a2"), (op.pf_dd_thermal_w * mw, "DD-th", "#e0913a"),
                (op.pf_dd_beam_w * mw, "DD-bt", "#c0504d"), (op.pf_bb_dd_w * mw, "DD-bb", "#4bacc6")]
    pf_tot_mw = op.pf_total_w * mw
    ax = axes[2, 3]
    keep = [(w, n, c) for w, n, c in channels if w > 0.005 * max(pf_tot_mw, 1.0e-9)]
    if keep:
        ws, ns, cs = zip(*keep)
        ax.pie(ws, labels=ns, colors=cs, autopct="%1.0f%%", textprops={"fontsize": fs * 0.65}, startangle=90)
    q_val = op.pf_total_w / op.P_NB_total_w if op.P_NB_total_w else float("nan")
    ax.set_title(f"Pfus={pf_tot_mw:.3g} MW (Q={q_val:.3g})", fontsize=fs)

    fig.suptitle(f"{device} -- Results summary", fontsize=15, fontweight="bold")
    fig.text(0.015, 0.012, _summary_parameters_text(op, model), fontsize=8.2, va="bottom", family="monospace")
    fig.subplots_adjust(left=0.045, right=0.99, top=0.93, bottom=0.24, wspace=0.38, hspace=0.55)
    return fig


def _render_summary_png() -> io.BytesIO:
    op, model, vol = _last_result["op"], _last_result["model"], _last_result["vol"]
    buf = io.BytesIO()
    if op is not None:
        with _MPL_LOCK:
            fig = _build_summary_fig(op, model, vol)
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    return buf


def _render_summary_pdf() -> io.BytesIO:
    op, model, vol = _last_result["op"], _last_result["model"], _last_result["vol"]
    buf = io.BytesIO()
    if op is not None:
        with _MPL_LOCK:
            fig = _build_summary_fig(op, model, vol)
        fig.savefig(buf, format="pdf", bbox_inches="tight")
    buf.seek(0)
    return buf


results_view_pane = pn.pane.Matplotlib(sizing_mode="stretch_width", height=620)
results_view_status = pn.pane.Markdown("", styles={"font-size": "13px", "color": "#c0504d"})
results_view_png = pn.widgets.FileDownload(
    callback=_render_summary_png, filename="hot_jass_summary.png",
    label="Save PNG", width=120, stylesheets=[TURQUOISE_BUTTON_CSS],
)
results_view_pdf = pn.widgets.FileDownload(
    callback=_render_summary_pdf, filename="hot_jass_summary.pdf",
    label="Save PDF", width=120, stylesheets=[TURQUOISE_BUTTON_CSS],
)
results_view_close = pn.widgets.Button(name="Close", width=90, stylesheets=[GRAY_BUTTON_CSS])
results_view_modal = pn.Modal(
    pn.Column(
        results_view_status, results_view_pane,
        styles=CONTENT_STYLE, margin=(14, 14, 0, 14), height=620, scroll="y-auto",
    ),
    modal_footer(results_view_png, results_view_pdf, results_view_close),
    name="results-view-dialog", open=False, background_close=False,
    stylesheets=[MODAL_CSS], width=1180, height=760, margin=0,
)
results_view_close.on_click(lambda event: setattr(results_view_modal, "open", False))


def _open_results_view(event) -> None:
    # Rebuilt fresh on every open (not cached) -- mirrors `_open_assumptions`'s
    # own established pattern, so a Start since the last time this was
    # opened is always reflected, not a stale snapshot.
    op, model, vol = _last_result["op"], _last_result["model"], _last_result["vol"]
    if op is None:
        results_view_pane.object = None
        results_view_status.object = "No calculation completed yet -- press Start first."
    else:
        with _MPL_LOCK:
            results_view_pane.object = _build_summary_fig(op, model, vol)
        results_view_status.object = ""
    results_view_modal.open = True

# RESULTS "Save" -- a checkbox-driven combined-PDF export ("ALL_info"),
# per the user's own explicit spec: "the list of checkboxes offers to
# Save PDF: 1) Input (similar to Config JSON), 2) Assumptions (similar to
# Config Assumptions), 3) Operation point Results - the text output
# summary from all the Views. The all checked items should be Saved in
# one ALL_info document (.pdf)". Each checked section becomes its own
# fresh page(s) in ONE PdfPages document (not 3 separate files) --
# `_pdf_write_blocks` (already shared by the Assumptions PDF and, before
# it, the summary view) handles within-section pagination; this function
# just forces a page break BETWEEN sections so they don't run together.


def _input_summary_blocks() -> list:
    """The rail's own CURRENT input state, human-readable -- the "similar
    to Config JSON" checkbox content, just as PDF text instead of a
    machine-readable file. Reuses the SAME (key, label, default, tooltip)
    row lists (PLASMA_ROWS/NBI1_ROWS/etc.) as the single source of truth
    for label text, and the same `table.value.loc[key, "Value"]` lookup
    _plasma_val/_nbi_val already use to read a cell -- kept as the raw
    string (not parsed to float) since this is a plain text report and
    species fields like "D"/"T" aren't numeric at all."""
    device = machine_state["custom_name"] or machine_state["selected"] or "(custom / hand-edited)"
    blocks: list = [("h", f"{device} -- Inputs")]

    def _rows(rows, table):
        return [("p", f"{label}: {table.value.loc[key, 'Value']}") for key, label, _, _ in rows]

    blocks.append(("h2", "Plasma"))
    blocks.extend(_rows(PLASMA_ROWS, plasma_table))
    blocks.append(("h2", "NBI-1"))
    blocks.append(("p", f"Direction: {nbi1_direction_select.value}"))
    blocks.extend(_rows(NBI1_ROWS, nbi1_table))
    blocks.append(("h2", "NBI-2"))
    blocks.append(("p", f"Direction: {nbi2_direction_select.value}"))
    blocks.extend(_rows(NBI2_ROWS, nbi2_table))
    blocks.append(("h2", "ECRH"))
    blocks.extend(_rows(ECRH_ROWS, ecrh_table))
    blocks.append(("h2", "ICRH"))
    blocks.extend(_rows(ICRH_ROWS, icrh_table))

    blocks.append(("h2", "Models"))
    blocks.append(("p", f"Confinement: {confinement_select.value}"))
    blocks.append(("p", f"Alpha fraction confined (f_alpha): {alpha_confined_slider.value:.3g}"))
    blocks.append(("p", f"Electron-ion equipartition: {'On' if equip_checkbox.value else 'Off'}"))
    blocks.append(("p", f"Shine-through: {shine_through_select.value}"))
    blocks.append(("p", f"Orbit model: {orbit_model_select.value}"))
    blocks.append(("p", f"CX-loss model: {cx_model_select.value}"))
    blocks.append(("p", f"Rotation model: {rotation_model_select.value}"))
    blocks.append(("p", f"Beam-beam fusion: {'On' if beam_beam_checkbox.value else 'Off'}"))
    blocks.append(("p", f"Profile-corrected 0-D: {'On' if profile_avg_checkbox.value else 'Off'}"))

    blocks.append(("h2", "Settings"))
    blocks.extend(_rows(CX_MANUAL_ROWS, cx_manual_table))
    blocks.extend(_rows(ROTATION_MANUAL_ROWS, rotation_manual_table))
    return blocks


def _parse_md_to_blocks(md: str) -> list:
    """A View Tab's own `\\n\\n`-joined markdown string (every tab builder
    in this file constructs its `md` this way: a plain '### ...' heading
    item, a self-contained '$$...$$' eq item, or a plain-text item, one
    per list entry) into the (kind, text) tuples `_pdf_write_blocks()`
    needs. Every tab builder pre-doubles its OWN "eq" backslashes (`\\\\%`
    etc, 2 real chars) for the CommonMark-then-MathJax on-screen path --
    see `build_plasma_tab`'s own comment for why -- but `_pdf_write_blocks()`
    feeds "eq" text straight to matplotlib mathtext with no CommonMark
    step at all, where a doubled backslash means "line break", not
    "escaped punctuation" (the exact bug `_render_assumptions_pdf()` hit
    once already). So this collapses every real double-backslash back to
    one, undoing that doubling, before handing "eq" text onward."""
    two_backslashes, one_backslash = "\\" + "\\", "\\"
    blocks = []
    for part in md.split("\n\n"):
        part = part.strip()
        if not part:
            continue
        if part.startswith("### "):
            blocks.append(("h2", part[4:]))
        elif part.startswith("$$") and part.endswith("$$"):
            blocks.append(("eq", part[2:-2].strip().replace(two_backslashes, one_backslash)))
        else:
            blocks.append(("p", part))
    return blocks


def _operating_point_results_blocks() -> list:
    """Each result tab's own parameter TEXT (not the plots) -- "the text
    output summary from all the Views", the 3rd checkbox's own content.
    Rebuilds Plasma/Beam/Power/Fusion fresh via the SAME builder functions
    the live tabs use (a little wasted Figure-construction work, accepted
    for guaranteed consistency with what's actually on screen, same
    trade-off this file's own earlier PDF-export features already made),
    then reads back just the markdown child -- `_result_slot_column`'s own
    content is always `[..., markdown]` (the Janev warning banner, when
    present, is prepended, not appended), so the LAST child is always the
    markdown pane regardless."""
    op, model, vol = _last_result["op"], _last_result["model"], _last_result["vol"]
    if op is None:
        return [("h", "Operating Point Results"),
                ("p", "No calculation completed yet -- press Start first.")]
    device = machine_state["custom_name"] or machine_state["selected"] or "(custom / hand-edited)"
    blocks: list = [("h", f"{device} -- Operating Point Results")]
    for name, col in (
        ("Plasma", build_plasma_tab(op, model)),
        ("Beam", build_beam_tab(op, model, vol)),
        ("Power", build_power_tab(op, model)),
        ("Fusion", build_fusion_tab(op, model, vol)),
    ):
        blocks.append(("h2", name))
        blocks.extend(_parse_md_to_blocks(col[-1].object))
    return blocks


results_save_input_cb = pn.widgets.Checkbox(name="Input (rail values)", value=True)
results_save_assumptions_cb = pn.widgets.Checkbox(name="Assumptions", value=True)
results_save_opresults_cb = pn.widgets.Checkbox(
    name="Operating Point Results (text summary from all Views)", value=True)


def _render_all_info_pdf() -> io.BytesIO:
    sections = []
    if results_save_input_cb.value:
        sections.append(_input_summary_blocks())
    if results_save_assumptions_cb.value:
        sections.append(_full_assumptions_blocks())
    if results_save_opresults_cb.value:
        sections.append(_operating_point_results_blocks())
    if not sections:
        sections = [[("p", "No sections selected -- check at least one box before saving.")]]
    buf = io.BytesIO()
    with _MPL_LOCK, PdfPages(buf) as pdf:
        fig = plt.Figure(figsize=(_PDF_W_IN, _PDF_H_IN))
        y = _PDF_TOP
        for i, blocks in enumerate(sections):
            if i > 0:
                pdf.savefig(fig)
                fig = plt.Figure(figsize=(_PDF_W_IN, _PDF_H_IN))
                y = _PDF_TOP
            fig, y = _pdf_write_blocks(pdf, blocks, fig, y)
        pdf.savefig(fig)
    buf.seek(0)
    return buf


results_save_download = pn.widgets.FileDownload(
    callback=_render_all_info_pdf, filename="hot_jass_all_info.pdf",
    label="Save PDF", width=140, stylesheets=[TURQUOISE_BUTTON_CSS],
)
results_save_close = pn.widgets.Button(name="Close", width=90, stylesheets=[GRAY_BUTTON_CSS])
results_save_modal = pn.Modal(
    pn.Column(
        pn.pane.Markdown(
            "### Save results\n\nChoose which sections to include -- all "
            "checked ones are combined into one PDF:",
            styles={"font-size": "13px"},
        ),
        results_save_input_cb, results_save_assumptions_cb, results_save_opresults_cb,
        styles=CONTENT_STYLE, margin=(14, 14, 0, 14), height=200,
    ),
    modal_footer(results_save_download, results_save_close),
    name="results-save-dialog", open=False, background_close=False,
    stylesheets=[MODAL_CSS], width=460, height=320, margin=0,
)
results_save_close.on_click(lambda event: setattr(results_save_modal, "open", False))

# ============================================================ Help / Refs
# Real, specific GUI documentation -- replaces the earlier layout-skeleton-
# era placeholder (which just named the 4 toolbar groups and called
# Calculation/Results "placeholder for now", stale since this session wired
# up the real solve). Per the user's own explicit "fill the Help button
# dialog with the GUI elements meaning" ask. Static (unlike Refs below) --
# nothing here depends on which device/model is currently selected.
HELP_MARKDOWN = """### Help

#### Machines
Six preset buttons (DANTE, ITER, TCV, ST40, JET, T-15MD) load a real
device's full parameter set -- Plasma shape, NBI-1/NBI-2, ECRH, ICRH, and
the confinement/profile-averaging choice -- onto every rail field at
once. The magenta button shows which preset (or custom device name from
a loaded JSON) is currently active. The small **GUI** button above
Machines toggles a pixel-coordinate readout used for UI layout work --
not part of the physics workflow.

#### Input Data (rail, left side)
Six collapsible sections, each a Parameter/Value table (or, for Models,
dropdowns/slider/checkboxes) you can edit directly:
- **Plasma**: shape (R0/a/kappa/delta), density/temperature profile
  shape, D/T fraction, confinement times (used only when Confinement =
  Fixed tauE below).
- **NBI-1 / NBI-2**: each beam's species, power, energy, tangent-radius
  geometry, co-/counter-current direction, and manual shine-through
  fraction.
- **ECRH / ICRH**: auxiliary heating power and electron/ion power split.
- **Models**: the physics MODEL CHOICES -- confinement scaling, alpha
  fraction confined, electron-ion equipartition, shine-through/first-
  orbit-loss/charge-exchange/rotation models (each with its own manual
  sub-parameters where relevant), and beam-beam fusion on/off.

A red cell border means that value has been hand-edited away from the
last applied preset or loaded file.

#### Config
- **Read**: load a previously saved JSON config onto the rail.
- **Save**: preview and download the CURRENT rail state as JSON.
- **Assumptions**: the model's governing physics formulae (always
  shown), plus -- once Start has completed -- the active device's own
  selected models and their real computed results. Has its own PDF
  export.

#### Calculation
- **Start**: runs the real HotJass solve for whatever's currently on
  the rail; the ring logo spins and the plasma-current arrow animates
  in the Geometry tab while it runs.
- **Stop**: cancels an in-progress run.

Changing ANY rail value -- by hand, or by clicking a Machines preset --
clears the Plasma/Beam/Power/Fusion tabs back to "Press START", since
their content would otherwise silently belong to the PREVIOUS inputs.
Geometry alone stays live; it redraws directly from the rail and never
needs a Start press.

#### Results
- **View** / **Save**: placeholders for now, not yet wired to the real
  solve output -- use each view tab's own content, and the Assumptions
  dialog's own PDF export, in the meantime.

#### View tabs (main area)
- **Geometry**: always live, redraws immediately from the rail.
- **Plasma / Beam / Power / Fusion**: populated after a successful
  Start; each shows real plots plus a LaTeX-rendered parameter panel.
"""
help_close = pn.widgets.Button(name="Close", width=90, stylesheets=[GRAY_BUTTON_CSS])
help_modal = pn.Modal(
    pn.Column(
        pn.pane.Markdown(HELP_MARKDOWN, styles={"font-size": "13px"}),
        height=440, scroll="y-auto", styles=CONTENT_STYLE, margin=(14, 14, 0, 14),
    ),
    modal_footer(help_close),
    name="help-dialog", open=False, background_close=False,
    stylesheets=[MODAL_CSS], width=520, height=520, margin=0,
)
help_close.on_click(lambda event: setattr(help_modal, "open", False))

# Real citations, copied from HI-Jass/Panel_proto/app_dialog.py's own
# REFERENCE_ENTRIES (itself copied from hi_jass_app.py's REFERENCES) -- not
# fabricated for this skeleton. These are the always-shown "Common" ones
# (beam stopping / fusion reactivity / orbit estimates / NRL formulary --
# apply regardless of which device is selected); the per-DEVICE section
# below (MACHINE_REFERENCES) is what actually varies with the active
# Machines preset, per the user's own explicit "Refs dlg - with the
# active Device relevant refs" ask.


def _scholar(query: str) -> str:
    """Google Scholar search-query URL -- ported verbatim from
    hi_jass_app.py's own `_scholar()`, used there (and here) for
    references that don't have a stable direct DOI on file. (`urllib.parse`
    is a top-of-file import, not a local one, unlike the source's own
    function-local import -- this file's own convention.) Moved to BEFORE
    REFERENCE_ENTRIES (was originally defined right after it, when no
    entry in that list needed it yet) once new entries here started
    calling it directly inside the list literal -- that executes at
    module-load time, not lazily inside a function body, so it needs
    `_scholar` to already exist as a name by this point, unlike every
    other forward-reference in this file (which are all inside function
    bodies, resolved only when later CALLED)."""
    return "https://scholar.google.com/scholar?q=" + urllib.parse.quote(query)


REFERENCE_ENTRIES = [
    ("Janev, Boley & Post, Nucl. Fusion 29 (1989) 2125 -- beam stopping cross-sections", ""),
    ("Suzuki, Shirai, Nemoto, Tobita, Kubo, Sugie, Sakasai & Kusama, Plasma Phys. "
     "Control. Fusion 40 (1998) 2097 -- beam stopping cross-sections, validated "
     "against JT-60U shine-through data down to 10 keV/amu",
     "https://doi.org/10.1088/0741-3335/40/12/009"),
    # Added per an explicit "add Riviere (HotJass/References)" ask --
    # `beam_stopping_cross_section_m2()` (hotjass/physics.py) is this
    # exact fit (the "Riviere" Shine-through model option), cited there
    # already ("PPPL-1280 Sect. 4.1... cites Riviere (1971, Nucl. Fusion
    # 11, 363)") but never added to this dialog's own list until now.
    # Confirmed title/volume/page directly from HotJass/references/
    # riviere1971.pdf's own first page, not guessed.
    ("Rivière, Nucl. Fusion 11 (1971) 363 -- penetration of fast hydrogen "
     "atoms into a fusion reactor plasma (the Riviere beam-stopping fit)",
     "https://doi.org/10.1088/0029-5515/11/4/006"),
    ("Bosch & Hale, Nucl. Fusion 32 (1992) 611 -- improved D-T fusion reactivity & cross-section",
     "https://doi.org/10.1088/0029-5515/32/4/I07"),
    # Added per an explicit "for the thermal power balance model - Jassby
    # work" ask. PPPL-1280 is already cited throughout hotjass/physics.py
    # as "this project's own beam-physics reference" (the 0-D energy-
    # balance structure the whole model follows, e.g. its own Eq. 2.5/2.9/
    # 4.1/Fig. 20(a)) -- this is that same report, confirmed from
    # HotJass/references/jassby_1976_pppl-1280_review.pdf's own title
    # page (D.L. Jassby, PPPL-1280, August 1976), not guessed.
    ("Jassby, PPPL-1280 (1976) -- Neutral-Beam-Injected Tokamak Fusion "
     "Reactors: A Review (the 0-D thermal power balance this whole "
     "model follows)",
     _scholar("Jassby 1976 PPPL-1280 neutral beam injected tokamak fusion reactors review")),
    ("Wesson, Tokamaks (4th ed., Oxford, 2011) -- Sect. 3.10 particle orbits", ""),
    # Added per an explicit "fast orbit models" ask -- the exact 3
    # references `st_orbit_widths()`'s own docstring already cites for
    # the ST orbit-width/first-orbit-loss models (large-aspect and
    # arbitrary-A), not newly chosen here.
    ("Akers et al., Nucl. Fusion 42 (2002) 122 -- NBI heating & fast-ion "
     "orbit losses in the START spherical tokamak",
     _scholar("Akers 2002 Nuclear Fusion 42 122 START neutral beam spherical tokamak")),
    ("Goldston, White & Boozer, Phys. Rev. Lett. 47 (1981) 1004 -- "
     "confinement of high-energy trapped particles (fast-ion first-orbit loss)",
     "https://doi.org/10.1103/PhysRevLett.47.1004"),
    ("Goldston & Rutherford, Introduction to Plasma Physics (IOP, 1995) "
     "-- Ch. 12, guiding-centre orbits",
     _scholar("Goldston Rutherford Introduction to Plasma Physics 1995")),
    # Added per an explicit "plasma rotation models" ask. NOT a citation
    # already in the code -- toroidal_rotation_velocity_ms()'s own
    # docstring says outright that tau_phi (momentum confinement time)
    # "has no widely validated scaling of its own" here, i.e. this
    # model's own rotation balance is a simple, uncited 0-D construction.
    # deGrassie's review is the standard, widely-cited general reference
    # for the underlying physics (NBI torque input, momentum confinement,
    # angular-momentum balance) that construction is a reduced version
    # of -- verified via a live search (DOI confirmed), not recalled from
    # memory alone, given no local PDF or in-code citation to check it
    # against the way every other entry here has one.
    ("deGrassie, Plasma Phys. Control. Fusion 51 (2009) 124047 -- tokamak "
     "toroidal rotation sources, transport and sinks",
     "https://doi.org/10.1088/0741-3335/51/12/124047"),
    # Added per an explicit "CX... models" ask -- the exact 2 references
    # cx_only_cross_section_m2()'s own docstring cites for the CX
    # cross-section fit actually used by this model's Manual-n0/ne and
    # Penetration CX-loss options (an EARLIER, unsourced version of this
    # function is explicitly noted there as replaced by this properly-
    # cited pair, so these 2 -- not the other CX-adjacent citations in
    # HI-Jass's own reference dict that this model doesn't actually use,
    # e.g. Freeman & Jones 1974 -- are the ones actually load-bearing).
    ("Janev & Smith, Nucl. Fusion Suppl. 4 (1993) Sect. 2.3.1 -- "
     "charge-exchange cross-section analytic form",
     _scholar("Janev Smith 1993 Nuclear Fusion Suppl 4 atomic plasma-material interaction data")),
    ("Swaczyna, Bzowski & Kubiak, arXiv:2411.13174 (2024) -- refit of the "
     "charge-exchange cross-section used here",
     "https://arxiv.org/abs/2411.13174"),
    ("NRL Plasma Formulary (2019 rev.) -- collision rates, thermal equilibration",
     "https://www.nrl.navy.mil/News-Media/Publications/nrl-plasma-formulary/"),
]


# Real per-device references, ported verbatim from hi_jass_app.py's own
# MACHINE_REFERENCES dict (lines 147-172) -- the device paper(s) each
# preset's own real parameters were actually sourced from where one
# exists, not fabricated for this app. DANTE has no external publication
# (an internal design point, per that file's own entry); every other
# device has at least one real citation, several (JET/TCV) more than one.
MACHINE_REFERENCES = {
    "DANTE": [("DANTE -- internal low-aspect design point; no external publication.", "")],
    "ITER": [("ITER Physics Basis, Ch. 1, Nucl. Fusion 39 (1999) 2137 -- device description & parameters",
              _scholar("ITER Physics Basis 1999 Nuclear Fusion 39 2137 overview"))],
    "JET": [("Rebut, Bickerton & Keen, Nucl. Fusion 25 (1985) 1011 -- the JET project & its prospects",
             _scholar("Rebut Bickerton Keen 1985 Nuclear Fusion 25 1011 JET project")),
            ("Ciric et al., Fusion Eng. Des. 82 (2007) 610 -- JET neutral beam enhancement "
             "(2 injector boxes, up to 8 PINIs each, >34 MW design)",
             _scholar("Ciric 2007 Fusion Engineering Design 82 610 JET neutral beam enhancement")),
            ("Maggi et al., Nucl. Fusion 64 (2024) 112012 -- JET DTE2 T/D-T overview; "
             "independently confirms pulse #99971's 26.5 MW NBI / 4 MW ICRH (N=1 D minority, "
             "29 MHz) / 15:85 D:T / 59 MJ record used by this preset",
             _scholar("Maggi 2024 Nuclear Fusion 64 112012 JET tritium deuterium-tritium overview")),
            ("Villari et al., Fusion Eng. Des. 217 (2025) 115133 -- JET D-T nuclear operations "
             "overview (DTE2/DTE3 neutron yields, 14 MeV calibration to +/-6%)",
             _scholar("Villari 2025 Fusion Engineering Design 217 115133 JET deuterium tritium nuclear operations"))],
    "ST40": [("Gryaznevich et al., Nucl. Fusion 62 (2022) 042008 -- ST40 compact high-field spherical tokamak",
              _scholar("Gryaznevich 2022 Nuclear Fusion ST40 spherical tokamak"))],
    "T-15MD": [("Khvostenko et al., Fusion Eng. Des. 146 (2019) 1108 -- T-15MD tokamak construction",
                _scholar("Khvostenko 2019 Fusion Engineering Design T-15MD tokamak"))],
    "TCV": [("Hofmann et al., Plasma Phys. Control. Fusion 36 (1994) B277 -- the TCV tokamak",
             _scholar("Hofmann 1994 Plasma Physics Controlled Fusion TCV tokamak")),
            ("Karpushov et al., Fusion Eng. Des. 187 (2023) 113384 -- TCV second high-energy "
             "NBI (NBI-2, 1.0 MW/55 keV, counter-injected vs. NBI-1's 1.3 MW/28 keV, co) upgrade",
             _scholar("Karpushov 2023 Fusion Engineering Design 187 113384 TCV second neutral beam"))],
}


def _refs_markdown() -> str:
    """Common references (always shown) + the CURRENTLY SELECTED device's
    own real citations from MACHINE_REFERENCES -- rebuilt every time the
    Refs dialog opens (`_open_refs` below), so switching Machines and
    reopening Refs shows the newly active device's own papers, not a
    stale snapshot from module-load time."""
    lines = ["### Common references", "",
             "Beam stopping, fusion reactivity, particle-orbit and plasma-"
             "formulary sources -- apply regardless of which device is "
             "selected.", ""]
    for label, url in REFERENCE_ENTRIES:
        lines.append(f"- [{label}]({url})" if url else f"- {label}")
    device = machine_state["custom_name"] or machine_state["selected"]
    lines += ["", f"### Device references -- {device or '(none selected)'}", ""]
    device_refs = MACHINE_REFERENCES.get(device, [])
    if device_refs:
        for label, url in device_refs:
            lines.append(f"- [{label}]({url})" if url else f"- {label}")
    else:
        lines.append("_No device-specific reference on file for this device "
                      "(a hand-edited/custom JSON, not one of the 6 built-in "
                      "presets)._")
    return "\n".join(lines)


refs_pane = pn.pane.Markdown(_refs_markdown(), styles={"font-size": "12.5px"})
refs_close = pn.widgets.Button(name="Close", width=90, stylesheets=[GRAY_BUTTON_CSS])
refs_modal = pn.Modal(
    pn.Column(refs_pane, height=440, scroll="y-auto", styles=CONTENT_STYLE, margin=(14, 14, 0, 14)),
    modal_footer(refs_close),
    name="refs-dialog", open=False, background_close=False,
    stylesheets=[MODAL_CSS], width=560, height=520, margin=0,
)
refs_close.on_click(lambda event: setattr(refs_modal, "open", False))


def _open_refs(event) -> None:
    refs_pane.object = _refs_markdown()
    refs_modal.open = True

# ==================================================================== Exit
main_ui = pn.Column(styles={"min-height": "0", "overflow": "hidden"},
                     sizing_mode="stretch_both")
exit_overlay = pn.Column(
    pn.pane.Markdown("## Session closed\n\nYou may now close this browser tab.",
                      styles={"text-align": "center", "margin-top": "160px", "color": "#333"}),
    visible=False,
)


def _on_exit(event):
    main_ui.visible = False
    exit_overlay.visible = True


# ================================================================= toolbar
# "gap" here (between the caption and its content row) is declared
# explicitly and reused identically in session_group below, rather than
# left to Panel's own default Column child-spacing -- that default isn't
# necessarily 4px, and Help/Refs need to land on the exact same row as
# View/Save, not "close".
GROUP_STYLE = {"border-right": "1px solid #aaa", "padding": "6px 14px", "align-items": "center",
               "gap": "4px"}
# height + flex/align-items: the caption occupies the SAME row height as
# Exit does in session_group below (TOOLBAR_BTN_HEIGHT) -- text sits at the
# bottom of that box, right above the button row, which is what actually
# keeps Help/Refs level with View/Save (see the comment above exit_btn).
# A plain <span> in pn.pane.HTML, not pn.pane.Markdown: Markdown wraps its
# text in a browser-default-margined <p>, confirmed to throw off this exact
# alignment by a few px even with the PANE's own margin zeroed (the <p>'s
# own margin lives one level deeper, outside CAPTION_STYLE's reach) --
# every other exact-pixel label in this file (rail tooltips, INPUT DATA)
# already uses HTML for the same reason.
# No bottom margin here: the Column's own "gap" (GROUP_STYLE) already
# spaces the caption from the row below it -- an extra CSS margin here
# would double up with that gap (confirmed: it was the exact remaining 4px
# that kept Help/Refs from landing on View/Save's row, after every other
# margin/padding mismatch above was already fixed).
CAPTION_STYLE = {"height": f"{TOOLBAR_BTN_HEIGHT}px", "display": "flex", "align-items": "flex-end",
                  "margin": "0 0 0 2px"}


def toolbar_group(caption: str, *rows, last: bool = False, header_extra=None) -> pn.Column:
    style = {} if last else GROUP_STYLE
    caption_html = pn.pane.HTML(
        f'<span style="font-size:{GROUP_TITLE_FONT_SIZE}; font-weight:700; color:#555; '
        f'letter-spacing:0.5px; text-transform:uppercase;">{caption}</span>',
        styles=CAPTION_STYLE, margin=0,
    )
    # header_extra: an optional small widget (e.g. the GUI-edit-mode pencil
    # toggle) placed at the caption's own right edge via HSpacer, instead
    # of the plain caption alone -- only Machines uses this.
    header = pn.Row(caption_html, pn.HSpacer(), header_extra, margin=0) if header_extra is not None \
        else caption_html
    return pn.Column(header, *rows, styles=style, margin=(4, 0, 4, 0))


# Config: 2 rows -- Read/Save side by side on top, Assumptions spanning
# their combined width below (CONFIG_BTN_WIDTH*2 + 6 gap = ACTION_BTN_WIDTH).
# margin=0 on every button here: Start/Stop/View/Save already had it
# (needed for the earlier Help/Refs-vs-View/Save row alignment fix) but
# Read/Save/Assumptions didn't -- Panel's own default per-button margin
# left Config measurably WIDER than Calculation/Results despite matching
# `width=` values, confirmed via CDP (251px vs 281px vs 211px before this
# fix), not assumed. Explicit margin=0 everywhere is what makes width= the
# only thing controlling each group's own content width.
# Per the user's own explicit target pixel coordinates (measured via the
# GUI Edit mode coordinate readout, not guessed): Read/Save tops at y=56,
# Assumptions bottom at y=133. Read/Save each get +1px margin-top (55->56);
# that 1px also cascades to push Assumptions down 1px in normal flow
# (131->132, confirmed via CDP remeasure), so Assumptions only needs +1px
# more of its own margin-top (132->133), not the full difference from its
# original position.
config_group = pn.Column(
    pn.Row(
        pn.widgets.Button(name="Read", width=CONFIG_BTN_WIDTH, margin=(1, 0, 0, 0), stylesheets=[GRAY_BUTTON_CSS],
                           on_click=lambda e: setattr(read_json_modal, "open", True)),
        pn.widgets.Button(name="Save", width=CONFIG_BTN_WIDTH, margin=(1, 0, 0, 0), stylesheets=[TURQUOISE_BUTTON_CSS],
                           on_click=_open_save_json),
        styles={"gap": "6px"},
    ),
    pn.widgets.Button(name="Assumptions", width=ACTION_BTN_WIDTH, margin=(1, 0, 0, 0), stylesheets=[GRAY_BUTTON_CSS],
                       on_click=_open_assumptions),
    styles={"gap": "6px"},
)
# progress_ring moved out to session_group (see its own definition) so it
# can anchor to Exit's own box for resize-safety -- calc_spinner/
# calc_progress/calc_status stay here, still hidden (visible=False, not
# removed) per the same convention as before. Their OWN wrapping Column
# doesn't collapse to true 0 width just because every child is
# visible=False, though -- confirmed via CDP: it measured 36px wide even
# with calc_progress/calc_spinner/calc_status each individually confirmed
# display:none, which was silently widening Calculation past Config/
# Results. The explicit width:0/overflow:hidden here forces it, the same
# technique already used for the `modals` wrapper elsewhere in this file.
# start_btn/stop_btn margins: same user-specified-coordinate approach as
# config_group above -- start_btn's own +1px margin-top hits y=56 for Start
# (was 55) and cascades +1px onto Stop via normal flow (129->130); Stop's
# own margin-top is then set to the REMAINING delta only (+3, not +4) to
# land its bottom at the target y=133.
calc_row = pn.Row(
    pn.Column(start_btn, stop_btn, styles={"gap": "4px"}),
    pn.Column(
        pn.Row(calc_spinner, calc_progress, styles={"align-items": "center"}),
        calc_status,
        styles={"gap": "2px", "width": "0", "overflow": "hidden"}, margin=0,
    ),
    styles={"gap": "0px", "align-items": "center"},
)
# Results: 2 rows -- View then Save, matching Calculation's own Start/Stop
# column so all 4 action groups share the same "stacked pair" shape.
# Group margin-top (was 5, now 1): per the user's explicit target
# coordinates, View's top needs to land at y=56 -- View itself still has
# margin=0, so this outer group margin is View's only vertical control.
# That -4px group-level shift also cascades onto Save below it (134->130),
# so Save's own margin-top makes up only the REMAINING difference (+3, not
# the full +/-) to land its bottom at the target y=133 -- same two-level
# "shift the group, then correct the second row" pattern used in
# config_group/calc_row for the same user request.
results_group = pn.Column(
    pn.widgets.Button(name="View", width=ACTION_BTN_WIDTH, height=TOOLBAR_BTN_HEIGHT, margin=0,
                       stylesheets=[GRAY_BUTTON_CSS], on_click=_open_results_view),
    pn.widgets.Button(name="Save", width=ACTION_BTN_WIDTH, height=TOOLBAR_BTN_HEIGHT, margin=(3, 0, 0, 0),
                       stylesheets=[TURQUOISE_BUTTON_CSS],
                       on_click=lambda e: setattr(results_save_modal, "open", True)),
    styles={"gap": "4px"}, margin=(1, 0, 0, 0),
)

# Exit/Help/Refs: same TOOLBAR_BTN_HEIGHT as View/Save, and the SAME
# 2-row-plus-caption shape as every other group -- Exit takes the row
# other groups spend on their caption (so it sits at the very top of the
# column, per the user's spec), and Help/Refs then land in the same two
# rows as View/Save so they line up across the toolbar. Confirmed by
# measuring both pairs' bounding rects via CDP, not just eyeballed --
# matching CAPTION_STYLE's own line-height (via an explicit height on the
# caption row below) is what actually makes Help/Refs land level with
# View/Save rather than a few px off.
exit_btn = pn.widgets.Button(name="Exit", width=70, height=TOOLBAR_BTN_HEIGHT, margin=0,
                              stylesheets=[GRAY_BUTTON_CSS])
help_btn = pn.widgets.Button(name="Help", width=70, height=TOOLBAR_BTN_HEIGHT, margin=0,
                              stylesheets=[GRAY_BUTTON_CSS])
refs_btn = pn.widgets.Button(name="Refs", width=70, height=TOOLBAR_BTN_HEIGHT, margin=0,
                              stylesheets=[GRAY_BUTTON_CSS])
exit_btn.on_click(_on_exit)
help_btn.on_click(lambda e: setattr(help_modal, "open", True))
refs_btn.on_click(_open_refs)
# Same 2-level shape as toolbar_group's own Column[caption, content] --
# exit_btn plays the caption's role (row 1), and the nested Column[Help,
# Refs] plays the content role (rows 2-3), with the SAME "4px" gap at both
# levels as GROUP_STYLE now uses, so this group's rows land on the same Y
# as every other group's.
# position:relative + a css_classes marker (Panel objects don't take a raw
# HTML `id`, but css_classes lands on this Column's own outer div, which
# `progress_ring`'s drag script below finds via the same shadow-root
# walker as everywhere else) -- this is what makes it the CSS containing
# block progress_ring's own `position:absolute` anchors to. progress_ring
# is included as a direct child here (not just visually near it) for
# exactly that reason -- CSS's "nearest positioned ancestor" rule only
# looks at real DOM ancestors, not visual proximity.
session_group = pn.Column(
    exit_btn,
    pn.Column(help_btn, refs_btn, styles={"gap": "4px"}),
    progress_ring,
    styles={"gap": "4px", "padding": "6px 8px", "position": "relative", "overflow": "visible"},
    css_classes=["hotjass-session-group"],
    margin=(4, 4, 4, 0),
)

# =============================================================== GUI edit
# A design-time MEASURING tool, toggled by the pencil button in MACHINES'
# own top-right corner: while on, hovering ANY element shows a crosshair
# ruler (full-height/width guide lines through the cursor) plus that
# element's own on-screen box, highlighted, with its exact x/y/width/
# height/center printed next to the cursor -- so positions like
# progress_ring's RING_OFFSET_LEFT/TOP above can be read directly off the
# running app instead of going back and forth over chat for another CDP
# measurement each time the layout changes.
#
# Deliberately NOT a full drag-and-resize-any-widget editor. That's a much
# bigger undertaking than this one screen's worth of code -- every widget
# TYPE renders through different DOM (a Button's own shadow-root structure
# has nothing in common with a Select's or a Column's), and even ONE
# custom draggable element (progress_ring, above) took three real,
# separately-diagnosed bugs to get right: a shadow-DOM id lookup, native
# <img> drag-and-drop fighting the custom drag, and a getElementById/
# css_classes mismatch. Generalizing that to "any control, draggable AND
# resizable" would multiply that surface across every widget type in the
# app. This ships the half of the idea that's actually cheap and robust --
# read measurements without needing to ask -- and stays out of the
# business of moving things around live for you; for that, either say
# where you want something and I'll place it, or ask for a specific
# element to be made draggable the same way progress_ring already is.
# Plain ASCII "GUI" label, not a pencil emoji: a lone special-Unicode-glyph
# button `name=` has a documented history of trouble in this exact
# codebase (HI-Jass/Panel_proto/app_dialog.py's own min/max/close-button
# bug) -- and here it was worse than that file's "click silently does
# nothing" finding: the rendered element's own textContent came back
# completely EMPTY (confirmed via CDP, not assumed), meaning the glyph
# never even reached the DOM. Swapped for the user's own alternative name
# for this button ("a small 'GUI' ... button"), which sidesteps the whole
# class of bug.
GUI_EDIT_TOGGLE_CSS = GRAY_BUTTON_CSS + """
.bk-btn { font-size: 10px !important; padding: 0 !important; min-height: 0 !important; }
"""
GUI_EDIT_TOGGLE_ACTIVE_CSS = MAGENTA_BUTTON_CSS + """
.bk-btn { font-size: 10px !important; padding: 0 !important; min-height: 0 !important; }
"""
edit_mode_btn = pn.widgets.Button(name="GUI", width=30, height=18, margin=0,
                                   stylesheets=[GUI_EDIT_TOGGLE_CSS],
                                   css_classes=["hotjass-edit-toggle"])
_edit_mode_state = {"on": False}


def _toggle_edit_mode(event):
    _edit_mode_state["on"] = not _edit_mode_state["on"]
    on = _edit_mode_state["on"]
    edit_mode_btn.css_classes = ["hotjass-edit-toggle"] + (["active"] if on else [])
    edit_mode_btn.stylesheets = [GUI_EDIT_TOGGLE_ACTIVE_CSS if on else GUI_EDIT_TOGGLE_CSS]


edit_mode_btn.on_click(_toggle_edit_mode)

RULER_JS = """
<script>
(function() {
    function* allRoots(root) {
        yield root;
        var walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
        var n;
        while (n = walker.nextNode()) { if (n.shadowRoot) { yield* allRoots(n.shadowRoot); } }
    }
    function findById(id) {
        for (var r of allRoots(document)) {
            var el = r.getElementById ? r.getElementById(id) : null;
            if (el) return el;
        }
        return null;
    }
    function findByClass(cls) {
        for (var r of allRoots(document)) {
            var el = r.querySelector ? r.querySelector('.' + cls) : null;
            if (el) return el;
        }
        return null;
    }
    var overlay = findById('hotjass-ruler-overlay');
    if (!overlay || overlay.dataset.bound) return;
    overlay.dataset.bound = '1';
    var vline = overlay.querySelector('.ruler-vline');
    var hline = overlay.querySelector('.ruler-hline');
    var label = overlay.querySelector('.ruler-label');
    var highlight = overlay.querySelector('.ruler-highlight');

    // The full crosshair+hover-highlight ruler turned out not to be useful
    // in practice (per user feedback) -- kept in place, just switched off,
    // so it can be flipped back on later without rewriting it. With this
    // false, GUI Edit mode instead just shows the raw cursor position,
    // which is what's actually needed to call out move-to coordinates.
    var SHOW_CROSSHAIR = false;

    // Real hover targets live inside possibly several NESTED shadow
    // roots (a Button inside a Column inside a Row...) --
    // elementFromPoint only sees the outermost light-DOM host by default;
    // walking into each hit's own .shadowRoot and re-querying the SAME
    // point finds the true deepest element, same idea as this file's own
    // allRoots() walker but for a single point instead of a whole-tree
    // search.
    function deepestAt(x, y) {
        var el = document.elementFromPoint(x, y);
        var guard = 0;
        while (el && el.shadowRoot && guard < 20) {
            var inner = el.shadowRoot.elementFromPoint(x, y);
            if (!inner || inner === el) break;
            el = inner;
            guard++;
        }
        return el;
    }

    document.addEventListener('mousemove', function(e) {
        var toggle = findByClass('hotjass-edit-toggle');
        var active = toggle && toggle.classList.contains('active');
        overlay.style.display = active ? 'block' : 'none';
        if (!active) return;
        var x = e.clientX, y = e.clientY;
        if (SHOW_CROSSHAIR) {
            vline.style.display = '';
            hline.style.display = '';
            vline.style.left = x + 'px';
            hline.style.top = y + 'px';
            var el = deepestAt(x, y);
            if (el && !overlay.contains(el)) {
                var r = el.getBoundingClientRect();
                highlight.style.left = r.left + 'px';
                highlight.style.top = r.top + 'px';
                highlight.style.width = r.width + 'px';
                highlight.style.height = r.height + 'px';
                highlight.style.display = 'block';
                label.textContent = 'x=' + Math.round(r.left) + ' y=' + Math.round(r.top) +
                                     ' w=' + Math.round(r.width) + ' h=' + Math.round(r.height) +
                                     '  cx=' + Math.round(r.left + r.width / 2) +
                                     ' cy=' + Math.round(r.top + r.height / 2);
            } else {
                highlight.style.display = 'none';
                label.textContent = 'x=' + Math.round(x) + ' y=' + Math.round(y);
            }
        } else {
            vline.style.display = 'none';
            hline.style.display = 'none';
            highlight.style.display = 'none';
            label.textContent = 'x=' + Math.round(x) + ' y=' + Math.round(y);
        }
        var labelLeft = x + 14, labelTop = y + 14;
        if (labelLeft > window.innerWidth - 220) { labelLeft = x - 220; }
        if (labelTop > window.innerHeight - 30) { labelTop = y - 30; }
        label.style.left = labelLeft + 'px';
        label.style.top = labelTop + 'px';
    });
})();
</script>
"""
ruler_overlay = pn.pane.HTML(
    '<div id="hotjass-ruler-overlay" style="display:none; pointer-events:none;">'
    '<div class="ruler-vline" style="position:fixed; display:none; top:0; bottom:0; width:1px; '
    'background:rgba(220,0,0,0.6); z-index:100000;"></div>'
    '<div class="ruler-hline" style="position:fixed; display:none; left:0; right:0; height:1px; '
    'background:rgba(220,0,0,0.6); z-index:100000;"></div>'
    '<div class="ruler-highlight" style="position:fixed; display:none; '
    'background:rgba(0,140,255,0.18); border:1px solid rgba(0,90,200,0.85); z-index:99999;"></div>'
    '<div class="ruler-label" style="position:fixed; background:rgba(0,0,0,0.82); color:#fff; '
    'font-family:monospace; font-size:11px; padding:3px 6px; border-radius:3px; '
    'z-index:100001; white-space:nowrap;"></div>'
    '</div>' + RULER_JS,
    width=0, height=0, margin=0, sizing_mode="fixed", styles={"overflow": "visible"},
)

toolbar = pn.Row(
    toolbar_group("Machines", machine_group, header_extra=edit_mode_btn),
    toolbar_group("Config", config_group),
    toolbar_group("Calculation", calc_row),
    toolbar_group("Results", results_group),
    pn.HSpacer(),
    session_group,
    styles={"background": TOOLBAR_GRAY, "border-bottom": "1px solid #999",
            "padding": "6px 10px", "flex": "0 0 auto"},
    sizing_mode="stretch_width",
)

# ================================================================= view area
PLOT_TABS = ["Geometry", "Plasma", "Beam", "Power", "Fusion"]


def _clear_result_tabs(event=None) -> None:
    """Resets Plasma/Beam/Power/Fusion back to their own "Press START"
    placeholder -- called whenever ANY rail input that feeds `_build_model()`
    changes (a device-preset switch, a JSON load, or a hand-edited cell/
    select/slider/checkbox), via the `.param.watch(...)` calls registered
    right after the Geometry ones below. Before this existed, those 4 tabs
    kept showing the PREVIOUS device's real numbers relabeled under the
    NEWLY selected device -- confirmed via CDP (switching DANTE -> ITER
    left the Plasma tab showing DANTE's own Te0=7.03 keV under the ITER
    button, not ITER's real ~213 keV) -- silently wrong, not just stale,
    since nothing in the UI indicated the numbers no longer matched the
    current inputs. Geometry is deliberately NOT reset this way -- it has
    its own separate live-refresh watchers (`_refresh_geometry`) and never
    needs a Start press to begin with, so there's no stale-results problem
    for it to have. References `plasma_slot`/etc, all defined later in
    this file -- a forward reference, safe here since this function is
    only ever CALLED later (a param-watch callback, long after the whole
    module has finished loading), same convention as every other one in
    this file; only the WATCH REGISTRATION itself (further down) needs
    this function to already be defined as a name, which it is at that
    point.

    Also switches the active view tab back to Geometry -- per the user's
    own explicit "when at least one input is modified, the View must
    switch to Geometry Tab automatically" ask, same trigger set as the
    tab-clearing above (any rail change already means Plasma/Beam/Power/
    Fusion are now stale, so landing on Geometry -- which never goes stale,
    it has its own live refresh -- is the one tab guaranteed to still
    match the current inputs)."""
    plasma_slot[:] = [_placeholder_tab("Plasma")]
    beam_slot[:] = [_placeholder_tab("Beam")]
    power_slot[:] = [_placeholder_tab("Power")]
    fusion_slot[:] = [_placeholder_tab("Fusion")]
    view_tabs.active = 0


def _placeholder_tab(name: str) -> pn.Column:
    # `display: flex` + `align-items/justify-content: center` on the
    # OUTER Column (not just `text-align: center` on the Markdown pane
    # itself, which only centers horizontally) -- per the user's own
    # explicit "in the middle" ask, both axes, not just top-anchored.
    return pn.Column(
        pn.pane.Markdown(
            '_Press **"START"** to calculate._',
            styles={"color": "#888", "text-align": "center", "margin": "0"},
        ),
        styles={**CONTENT_STYLE, "border-style": "dashed", "display": "flex",
                "align-items": "center", "justify-content": "center"},
        sizing_mode="stretch_both", margin=(8, 8, 8, 8),
    )


# ---------------------------------------------------------------- geometry
# Geometry is the ONE view tab that's always live -- no Start press needed
# -- per the user's own explicit ask, unlike Plasma/Beam/Power/Fusion
# (still plain "press Start" placeholders above, no physics wired up yet).
# Two matplotlib panels side by side, ported from HI-Jass/Panel_proto/
# app_dashboard.py's own `build_geometry_pane()` (itself a port of
# hi_jass_app.py's `_render_deposition` subplot 221 + `_render_scan`'s
# D-shape panel) -- same drawing logic, but reading straight off THIS
# file's own rail widgets (plasma_table/nbi{1,2}_table/nbi{1,2}_direction_
# select) instead of a `model.plasma`/`model.beams` object, since this is
# a layout skeleton with no live HotJassModel yet. Both panels are
# therefore always in sync with whatever's currently typed into the rail,
# not just whatever Start last solved.
GEOM_FIGSIZE = (8.4, 4.2)
GEOM_DPI = 100


def _plasma_val(key: str, fallback: float = 0.0) -> float:
    return _parse_float(plasma_table.value.loc[key, "Value"], fallback)


def _nbi_val(table, key: str, fallback: float = 0.0) -> float:
    return _parse_float(table.value.loc[key, "Value"], fallback)


# Ip-arrow animation state -- ported from HI-Jass/Panel_proto/app_dialog.py's
# own `ip_state`/`_tick_ip_animation`/`_start_ip_animation`/
# `_stop_ip_animation` (point 19 of that file's own module docstring),
# per the user's own explicit "make it run along the axis during
# Calculation 'progress', like proto app_dialog" ask. `angle` is the
# CENTER of the arrow's short arc on the R0 circle -- np.pi at rest
# (opposite the NBI beams, per the earlier ask), ticked forward by
# IP_ANIMATION_STEP_RAD every IP_ANIMATION_PERIOD_MS while `_on_start`'s
# calculation is running, imitating a real toroidal current flowing
# around the magnetic axis. `build_geometry_pane()` (below) reads
# `ip_state["angle"]` directly -- defined here, ABOVE that function, since
# `geometry_slot`'s own construction calls `build_geometry_pane()`
# immediately at module load time (not just from a later callback), so
# `ip_state` has to already exist by then.
# Measured (not guessed) via a standalone timing script against THIS
# file's own build_geometry_pane(): rebuilding the full 2-subplot figure
# from scratch costs ~113ms (matplotlib axis/tick object construction,
# profiled with cProfile -- dominated by Axis.__init__/_update_ticks, not
# by the actual plotting calls), and even just re-encoding an ALREADY-
# built, unchanged figure to PNG (fig.savefig, no rebuild at all) costs a
# further ~180-225ms on top -- so a full rebuild-and-serialize each tick
# runs ~300ms+ regardless of how short IP_ANIMATION_PERIOD_MS is asked to
# be, which is why an earlier 70ms-period attempt was still only landing
# ~1 new frame every ~400ms in the browser (confirmed via CDP: hashing
# the rendered <img> payload every 150ms only found a new frame roughly
# every 2-3 samples, not every sample). Per the user's own explicit "run
# faster and smoother (not pushing)" follow-up ask, `_tick_ip_animation`
# below now redraws ONLY the Ip-arrow artist (`_draw_ip_arrow`, cheap:
# no axis/tick reconstruction) on the SAME cached Figure instead of
# calling `build_geometry_pane()` fresh -- this can't beat the
# ~180-225ms PNG-encode floor (unavoidable: every visible frame is a new
# raster regardless of how cheaply the artist itself is updated), but it
# removes the ~113ms of AVOIDABLE rebuild cost from every tick, a real
# ~35-40% cut. IP_ANIMATION_PERIOD_MS is set close to that realistic
# floor (not the earlier over-optimistic 70ms) so requested ticks don't
# just pile up faster than they can ever be serviced; IP_ANIMATION_STEP_RAD
# is picked so each frame's own visible jump stays small (~9 deg) at
# that realistic frame rate, which is what actually reads as "smooth,
# not pushing" -- a large step at an unavailable frame rate was the
# actual cause of the original jerky look, not the nominal period value
# alone.
IP_ANIMATION_PERIOD_MS = 200
IP_ANIMATION_STEP_RAD = 0.16
ip_state = {"angle": np.pi}
_ip_animation = {"callback": None}
# Populated by build_geometry_pane() every FULL rebuild (device/table
# changes, or the very first render) -- `_tick_ip_animation`'s fast path
# reuses this cached Figure/Axes to redraw just the arrow; if it's ever
# missing or stale (R0 changed since the cache was filled -- e.g. the
# user edited PLASMA mid-calculation), it falls back to a full
# `_refresh_geometry()` rebuild instead of drawing the arrow in the
# wrong place on a stale figure.
_geom_cache = {"pane": None, "ax1": None, "R0": None, "ip_arrow": None}
IP_ARROW_HALF_SPAN = 0.03


def _draw_ip_arrow(ax1, R0: float):
    """Plasma-current arrow -- short & thick (per the user's own explicit
    spec, distinct from the thin beam-chord arrows), on the MAJOR RADIUS
    circle (R0, not the outer R0+a boundary). Resting position is
    OPPOSITE the NBI impact points (the beams are centered on angle 0, so
    "opposite side" = angle pi / negative-X); while a calculation is
    running, `ip_state["angle"]` is animated instead, ticking this arrow
    around the R0 axis to imitate a real flowing toroidal current --
    ported from HI-Jass/Panel_proto/app_dialog.py's own
    `_tick_ip_animation()`/`ip_state` (see its own docstring, point 19 of
    that file's own module docstring). Shrunk TWICE (0.12->0.06->0.03
    half-span, plus mutation_scale 22->11 and lw 3.2->1.8 the second
    time) per the user's own explicit "still too large, make it shorter
    by 50%" follow-up -- scaling the head + line width down TOGETHER
    with the span keeps proportions the same, just smaller; shrinking
    ONLY the span while leaving the arrowhead's own screen-space size
    (points, not data units) fixed is what made the first shrink alone
    look blob-like. Still drawn a0->a1 with a0<a1 (INCREASING angle =
    counter-clockwise in this standard X=cos/Y=sin top view) = positive
    Ip, matching hi_jass_app.py's own _render_deposition convention,
    unaffected by WHERE on the circle or WHEN in time it's drawn.
    Returns the created annotation artist so callers (the full rebuild
    AND the fast animation-only path below) can `.remove()` it later."""
    ip_center = ip_state["angle"]
    a0, a1 = ip_center - IP_ARROW_HALF_SPAN, ip_center + IP_ARROW_HALF_SPAN
    return ax1.annotate(
        "", xy=(R0 * np.cos(a1), R0 * np.sin(a1)), xytext=(R0 * np.cos(a0), R0 * np.sin(a0)),
        arrowprops=dict(arrowstyle="-|>,head_length=1.1,head_width=0.28",
                         color="0.35", lw=1.8, mutation_scale=11))


def _tick_ip_animation():
    ip_state["angle"] = (ip_state["angle"] + IP_ANIMATION_STEP_RAD) % (2.0 * np.pi)
    with _MPL_LOCK:
        ax1, R0, pane = _geom_cache["ax1"], _geom_cache["R0"], _geom_cache["pane"]
        if ax1 is None or pane is None:
            _refresh_geometry()  # no cache yet (shouldn't happen) -- full rebuild instead
            return
        old_arrow = _geom_cache["ip_arrow"]
        if old_arrow is not None:
            old_arrow.remove()
        _geom_cache["ip_arrow"] = _draw_ip_arrow(ax1, R0)
        # Same Figure object as before (only one small artist swapped) --
        # `.object` reassignment wouldn't even register as a param change
        # (identical object), so force the re-render explicitly instead of
        # rebuilding the whole pane the way `_refresh_geometry()` does.
        pane.param.trigger("object")


def _start_ip_animation():
    if _ip_animation["callback"] is None:
        _ip_animation["callback"] = pn.state.add_periodic_callback(
            _tick_ip_animation, period=IP_ANIMATION_PERIOD_MS)


def _stop_ip_animation():
    cb = _ip_animation["callback"]
    if cb is not None:
        cb.stop()
        _ip_animation["callback"] = None
    ip_state["angle"] = np.pi  # back to the resting position
    _refresh_geometry()


def build_geometry_pane() -> pn.pane.Matplotlib:
    R0 = _plasma_val("R0", 1.0)
    a = _plasma_val("a", 0.3)
    kappa = _plasma_val("kappa", 1.0)
    delta = _plasma_val("delta", 0.0)
    centrepost_r = _plasma_val("centrepost_r", -1.0)
    r_cp = centrepost_r if centrepost_r > 0.0 else (R0 - a)
    beams = [
        (_nbi_val(nbi1_table, "nbi1_tangent_r", R0), _nbi_val(nbi1_table, "nbi1_tangent_z", 0.0),
         nbi1_direction_select.value == "Co-current", "NBI-1"),
        (_nbi_val(nbi2_table, "nbi2_tangent_r", R0), _nbi_val(nbi2_table, "nbi2_tangent_z", 0.0),
         nbi2_direction_select.value == "Co-current", "NBI-2"),
    ]

    fig = plt.Figure(figsize=GEOM_FIGSIZE, dpi=GEOM_DPI)
    fs = 9

    # left: tokamak + NBI top view (torus outline, centrepost, beam chords)
    ax1 = fig.add_subplot(121)
    th = np.linspace(0.0, 2.0 * np.pi, 240)
    for r, st in ((R0 - a, "-"), (R0 + a, "-"), (R0, "--")):
        ax1.plot(r * np.cos(th), r * np.sin(th), st, color="0.6", lw=1.0)
    ax1.fill(r_cp * np.cos(th), r_cp * np.sin(th), color="0.75", zorder=0)
    lim = (R0 + a) * 1.32
    colors = ["tab:blue", "tab:orange"]
    nb = len(beams)
    for i, (Rt_raw, Zt_raw, co_current, label) in enumerate(beams):
        c = colors[i % len(colors)]
        phi = np.deg2rad(38.0 * (i - (nb - 1) / 2.0))
        Rt = min(Rt_raw if Rt_raw > 0.0 else R0, R0 + a)
        p = np.array([Rt * np.cos(phi), Rt * np.sin(phi)])
        d = np.array([-np.sin(phi), np.cos(phi)])
        # Beam length scaled to the PLOT extent (`lim`), not the minor
        # radius `a` -- per the user's own explicit "make the beams
        # longer, see the HI-Jass shot" ask/reference screenshot, where
        # each beam runs nearly the full height of the plot, well past
        # the outer torus circle on both ends, not just a short ~a-scale
        # segment through the plasma. Symmetric (-X, +X) around the
        # tangent point `p` either way, so the co/counter mirror below
        # (which negates BOTH the t-values and `d`) still lands the
        # tangent dot at the visual midpoint of the drawn line, same as
        # before -- only the overall length changed, not that structure.
        t_entry, t_end = -0.85 * lim, 0.85 * lim
        if not co_current:
            t_entry, t_end = -t_end, -t_entry
            d = -d
        p1, p2 = p + d * t_entry, p + d * t_end
        ax1.plot([p1[0], p2[0]], [p1[1], p2[1]], color=c, lw=1.5, alpha=0.9)
        # Arrowhead at 55% from p1 toward p2 -- lands just past the
        # tangent dot (the true midpoint, given the symmetric t-values
        # above) in the direction of travel, so it still visibly points
        # "into" the plasma along the beam's own co-/counter-current
        # direction (set by the `d`/t-value flip above) after lengthening.
        # Explicit head_length/head_width (not just a bare "-|>", whose
        # default proportions read as a small/stubby wedge at this line
        # weight) + a bigger mutation_scale -- per the user's own explicit
        # "make the beam arrows more clear (longer triangle)" ask.
        ax1.annotate("", xy=(p1 + (p2 - p1) * 0.55), xytext=p1,
                      arrowprops=dict(arrowstyle="-|>,head_length=1.0,head_width=0.4",
                                       color=c, lw=1.7, mutation_scale=16))
        ax1.plot([p[0]], [p[1]], "o", color=c, ms=4)
        # Label near the MIDPOINT of the ray (close to the arrowhead,
        # which sits at 55% -- just past center), not either endpoint --
        # per a follow-up "still out of bound... move them closer to the
        # arrow head (half-way)" report: BOTH p1 and p2 are offset from
        # the origin by the tangent point `p` (itself up to ~R0+a from
        # center) PLUS the full +-0.85*lim beam span, so either endpoint
        # can end up past `lim` (the plot's own xlim/ylim) depending on
        # the beam's own angle -- only a point near the ray's own middle
        # (p1+p2)/2, which is exactly `p` by construction (the same
        # symmetric span that already puts the tangent dot there), is
        # reliably inside the plot for every beam geometry. A small nudge
        # further ALONG the ray (past the arrowhead, which sits at 55%)
        # plus a larger offset PERPENDICULAR to it clears both the line
        # itself and the arrowhead triangle's own footprint, instead of
        # landing the text right on top of them.
        perp = np.array([-d[1], d[0]])
        label_pos = p + d * (0.08 * lim) + perp * (0.22 * lim)
        ax1.text(label_pos[0], label_pos[1], f"{label} ({'co' if co_current else 'ctr'})",
                  color=c, fontsize=fs * 0.85, ha="center", va="center")
    # Plasma-current arrow -- see `_draw_ip_arrow()`'s own docstring for
    # the full history (short & thick, on the R0 axis, opposite the NBI
    # beams, shrunk twice, sharper/narrower than the beam arrows). Factored
    # out to a standalone function so `_tick_ip_animation` below can redraw
    # ONLY this one small artist during the Start-animation (via
    # `_geom_cache`) instead of rebuilding the whole 2-subplot figure from
    # scratch on every tick -- see that cache's own comment for why.
    # `ax1`/`R0` cached here too (the fast animation path needs both, and
    # this is the one place both are still in scope with a freshly built
    # `ax1`); `pane` gets cached below, once the Matplotlib pane wrapping
    # this same `fig` actually exists.
    _geom_cache["ax1"] = ax1
    _geom_cache["R0"] = R0
    _geom_cache["ip_arrow"] = _draw_ip_arrow(ax1, R0)
    ax1.text(-R0 * 1.1, 0.0, r"$I_p$", color="0.35", fontsize=fs * 1.1,
              fontweight="bold", va="center", ha="right")
    ax1.set_xlim(-lim, lim)
    ax1.set_ylim(-lim, lim)
    ax1.set_aspect("equal")
    ax1.set_title("Tokamak + NBI geometry (top view)", fontsize=fs * 1.15, fontweight="bold")
    ax1.set_xlabel("X [m]", fontsize=fs)
    ax1.set_ylabel("Y [m]", fontsize=fs)
    ax1.tick_params(labelsize=fs * 0.85)
    ax1.grid(alpha=0.2)

    # right: plasma poloidal cross-section (Miller D-shape)
    ax2 = fig.add_subplot(122)
    theta = np.linspace(0.0, 2.0 * np.pi, 400)
    delta_c = np.clip(delta, -0.999, 0.999)
    ax2.plot(R0 + a * np.cos(theta + np.arcsin(delta_c) * np.sin(theta)), kappa * a * np.sin(theta))
    ax2.plot(R0, 0.0, marker="+", color="tab:red", markersize=9, markeredgewidth=1.5)
    # Beam hitting points -- each beam's own (tangent_R, tangent_Z), the
    # SAME two numbers the NBI-n table's own "tangent R [m]"/"tangent Z
    # [m]" rows and NBI_TANGENT_TOOLTIP already describe as "R is the
    # tangency radius, Z is the vertical offset" -- per the user's own
    # explicit "show the beam hitting points (R,Z) on the plasma
    # cross-section" ask. Plotted RAW (not clamped to R0+a the way the
    # top-view panel's own Rt is, for its own different reason -- keeping
    # the line drawable on that plot's own axes) so a tangent point
    # genuinely outside the plasma boundary still shows up honestly as
    # outside it here, not silently pulled back in.
    for i, (Rt_raw, Zt_raw, co_current, label) in enumerate(beams):
        c = colors[i % len(colors)]
        ax2.plot([Rt_raw], [Zt_raw], marker="x", color=c, ms=7, mew=2, zorder=5)
        ax2.annotate(label, (Rt_raw, Zt_raw), color=c, fontsize=fs * 0.8,
                      xytext=(4, 4), textcoords="offset points")
    ax2.set_title(
        f"Plasma shape\n$R_0$={R0:.2f}, $a$={a:.2f}, $\\kappa$={kappa:.2f}, $\\delta$={delta:.2f}",
        fontsize=fs * 1.05, fontweight="bold")
    ax2.set_xlabel("R [m]", fontsize=fs)
    ax2.set_ylabel("Z [m]", fontsize=fs)
    ax2.tick_params(labelsize=fs * 0.85)
    ax2.set_aspect("equal")
    ax2.grid(alpha=0.3)

    # Static margins (`subplots_adjust`), not `fig.tight_layout()` -- see
    # `_MPL_LOCK`'s own comment: `tight_layout()` (and `tight=True` below,
    # removed for the same reason) measures actual TEXT bounding boxes via
    # matplotlib's own mathtext parser, which turned out to be the exact
    # code path that crashed under concurrent access from the Ip-arrow
    # animation's own periodic redraw. Static margins need no such
    # measurement at all -- slightly less perfectly-fitted whitespace, but
    # immune to that whole class of bug, not just less likely to hit it.
    # `top=0.86` (was 0.90) -- ax2's own title is now 2 lines ("Plasma
    # shape" above the R0/a/kappa/delta line), needs the extra headroom.
    fig.subplots_adjust(left=0.08, right=0.97, bottom=0.13, top=0.86, wspace=0.32)
    w_px, h_px = int(GEOM_FIGSIZE[0] * GEOM_DPI), int(GEOM_FIGSIZE[1] * GEOM_DPI)
    pane = pn.pane.Matplotlib(fig, dpi=GEOM_DPI, width=w_px, height=h_px, sizing_mode="fixed")
    _geom_cache["pane"] = pane
    return pane


# A slot Column (not the pane itself) so `_refresh_geometry` can swap in a
# freshly-built pane wholesale -- matplotlib Figures aren't reactive
# objects Panel can patch in place, the whole pane has to be rebuilt and
# reinserted, same pattern as app_dashboard.py's own `results_slot[:] =
# [...]`. Wrapped in `styles=CONTENT_STYLE` (solid border, white bg) to
# match every other view-tab panel's own framing, `sizing_mode=
# "stretch_both"` with the Matplotlib pane itself pinned to a fixed pixel
# size inside it (own comment above) -- centers it rather than distorting
# its aspect ratio to fill the tab.
geometry_slot = pn.Column(
    build_geometry_pane(),
    # No `justify-content: center` here (unlike an earlier version) -- that
    # combined with overflow:auto is a known flexbox footgun where a
    # browser can clip the LEADING edge of an overflowing centered child
    # and never let you scroll back to it, which would defeat the
    # scrollbar this is specifically here to add. `align-items: center`
    # alone (horizontal centering only, matching `_result_slot_column`'s
    # own working pattern) doesn't have that problem. Per the user's own
    # explicit "add vertical/horizontal scrollbars to the views (they can
    # be clipped)" ask -- this tab previously had NO overflow handling at
    # all, unlike the other 4 (`_result_slot_column`'s own overflow-auto).
    # `min-height`/`min-width: 0` -- same flexbox fix as `_SLOT_MINSIZE`/
    # `_result_slot_column` below (this Column plays BOTH roles -- outer
    # slot AND scrollable box -- in one, since Geometry has no separate
    # wrapper): without it, this box won't shrink below its own fixed-
    # pixel Matplotlib child's intrinsic size, so it inflates past
    # `view_area`'s own `overflow: hidden` boundary and gets hard-clipped
    # there instead of scrolling here.
    styles={**CONTENT_STYLE, "align-items": "center", "overflow-x": "auto", "overflow-y": "auto",
            "min-height": "0", "min-width": "0"},
    stylesheets=[VIEW_SCROLLBAR_CSS],
    sizing_mode="stretch_both", margin=(8, 8, 8, 8),
)


def _refresh_geometry(event=None) -> None:
    with _MPL_LOCK:
        geometry_slot[:] = [build_geometry_pane()]


# Watches every rail widget the geometry panels actually read -- table
# `.value` fires on both a hand edit (cell blur/enter) AND a wholesale
# reassignment (device-preset switch, JSON load; see `_make_row_style`'s
# own comment on why that's reliable), so ONE watcher per table covers
# every path that can change R0/a/kappa/delta/tangent_r, no separate
# preset/JSON-load hook needed.
plasma_table.param.watch(_refresh_geometry, "value")
nbi1_table.param.watch(_refresh_geometry, "value")
nbi2_table.param.watch(_refresh_geometry, "value")
nbi1_direction_select.param.watch(_refresh_geometry, "value")
nbi2_direction_select.param.watch(_refresh_geometry, "value")

# Every rail widget `_build_model()` (further down) actually reads --
# broader than the 5 above, since the 4 calculated result tabs depend on
# ECRH/ICRH/MODELS too, not just plasma shape/NBI geometry. `.value`
# fires on both a hand edit and a wholesale reassignment (same
# reliability property noted above), so this one set of watchers covers
# every input-changing path uniformly. Per the user's own explicit bug
# report ("When the device selection is changed, all the tabs... are
# cleared away" -- verified via CDP to actually be worse than that,
# showing the PREVIOUS device's stale real numbers, not a placeholder;
# see `_clear_result_tabs`'s own docstring) -- these tabs now correctly
# reset to "Press START" on ANY input change, rather than either silently
# going stale (the real bug) or never resetting at all.
for _w in (plasma_table, nbi1_table, nbi2_table, ecrh_table, icrh_table,
           cx_manual_table, rotation_manual_table, confinement_select,
           equip_checkbox, nbi1_direction_select, nbi2_direction_select,
           profile_avg_checkbox, alpha_confined_slider, shine_through_select,
           orbit_model_select, cx_model_select, rotation_model_select,
           beam_beam_checkbox):
    _w.param.watch(_clear_result_tabs, "value")
del _w


# ======================================================= real calculation
# The 4 "press Start" placeholders (Plasma/Beam/Power/Fusion) below become
# real here -- per the user's own explicit "let's start to implement
# calculations... import all the calculation from HI-Jass (HotJass) code"
# ask. No new physics written anywhere in this section: every number comes
# from hotjass_core.HotJassModel.operating_point() (imported at the top of
# this file) or hj_physics's own functions, and every plot/formula is a
# direct port of hi_jass_app.py's own tab renderers (see this session's own
# plan file for the exact line numbers each piece came from).
RESULT_FIGSIZE = (8.4, 4.2)
# Beam tab is a 2x2 grid (4 plots) -- kept deliberately smaller per-plot
# than a naive 2x(8.4,4.2) stack would be, per the user's own explicit
# "smaller to fit the screen" ask; the tab's own `_result_slot_column`
# scrolls if it still doesn't fit a given browser window.
BEAM_FIGSIZE = (8.6, 7.2)
# Fusion tab's pie is now the only right-hand panel (the channel-breakdown
# bar was removed) -- wider than RESULT_FIGSIZE's default 2-panel split so
# the pie itself renders larger, per the user's own explicit ask.
FUSION_FIGSIZE = (10.2, 5.0)
RESULT_MD_STYLE = {"font-size": "13px", "padding": "4px 10px"}
# Power tab only -- larger than RESULT_MD_STYLE's 13px, and (paired with
# dropping "###" H3 headings in favor of plain **bold** lines at this same
# size in build_power_tab's own `md` list) EVERY line renders at one
# consistent size instead of jumping between a big heading and small
# paragraph text. Per the user's own explicit "make the text font larger
# and equal!" ask, scoped to the Power tab only (that's the only tab named
# in that sentence).
POWER_MD_STYLE = {"font-size": "16px", "padding": "4px 10px"}


def _result_pane(fig, figsize) -> pn.pane.Matplotlib:
    # No `tight=True` -- see `_MPL_LOCK`'s own comment: that flag defers a
    # tight-bbox measurement (mathtext parser again) to WHENEVER Panel/
    # Bokeh actually serializes this pane, outside this file's own control
    # and therefore outside `_MPL_LOCK`'s coverage too. Every caller
    # already sets its own static `fig.subplots_adjust(...)` margins
    # instead, so this isn't needed.
    w_px, h_px = int(figsize[0] * GEOM_DPI), int(figsize[1] * GEOM_DPI)
    return pn.pane.Matplotlib(fig, dpi=GEOM_DPI, width=w_px, height=h_px, sizing_mode="fixed")


def _result_slot_column(*content) -> pn.Column:
    """Same framing every real-result tab uses -- solid border (vs.
    `_placeholder_tab`'s dashed one, so a glance tells "has real content"
    from "still waiting on Start") + its own scrollbars in BOTH directions
    if the plot+text together run taller/wider than the tab area, rather
    than silently clipping -- per the user's own explicit "add vertical/
    horizontal scrollbars to the views (they can be clipped)" ask (the
    Beam tab's new 2x2 figure and the Fusion tab's now-larger pie are both
    tall/wide enough to clip in a smaller browser window otherwise).
    `min-height`/`min-width: 0` alongside `overflow: auto` -- this box is
    ITSELF a flex item (inside `plasma_slot` etc.) as well as a flex
    container (for the Matplotlib pane + Markdown pane inside it); without
    an explicit 0 min-size it won't shrink below ITS OWN children's
    intrinsic size either, which is what let it silently inflate past its
    allotted space instead of clipping its own overflow the way it looks
    like it should -- see `_SLOT_MINSIZE`'s own comment for the full
    mechanism (same bug, one level up)."""
    return pn.Column(*content, styles={**CONTENT_STYLE, "overflow-x": "auto", "overflow-y": "auto",
                                        "align-items": "center", "min-height": "0", "min-width": "0"},
                      stylesheets=[VIEW_SCROLLBAR_CSS],
                      sizing_mode="stretch_both", margin=(8, 8, 8, 8))


def _build_model() -> HotJassModel:
    """Rail values -> a real HotJassModel, for Start to actually solve.
    Reads the same tables/selects `build_geometry_pane()` already reads,
    plus everything the MODELS section adds. Field-by-field mapping is 1:1
    for nearly everything (this rail's own keys were named to match
    PlasmaParams/BeamParams from the start); the *_MODE_MAP dicts (defined
    alongside the MODELS-section selects above) translate a Select's
    displayed label back to hotjass_core's own internal mode string(s),
    and Ip/power need MA->A / MW->W unit conversion (PlasmaParams wants
    base SI; this rail's own table units match hi_jass_app.py's own
    DISPLAYED units, MA/MW). `enable_orbit_loss`/`alpha_heating` default
    True -- see this session's plan file: this rail has no separate on/off
    checkbox for either, only the model-CHOICE controls (orbit_model
    select, f_alpha slider), so picking a model already implies "model
    this."""
    ee_mode, ei_mode = CONFINEMENT_MODE_MAP.get(confinement_select.value, ("fixed", "fixed"))
    plasma = PlasmaParams(
        major_radius=_plasma_val("R0", 1.0),
        minor_radius=_plasma_val("a", 0.3),
        elongation=_plasma_val("kappa", 1.0),
        triangularity=_plasma_val("delta", 0.0),
        central_density=_plasma_val("ne0", 1.0e20),
        density_peaking=_plasma_val("density_peaking", 0.0),
        temp_peaking=_plasma_val("temp_peaking", 1.0),
        temp_peaking_i=_plasma_val("temp_peaking_i", -1.0),
        centrepost_radius=_plasma_val("centrepost_r", -1.0),
        effective_charge=_plasma_val("Zeff", 1.0),
        toroidal_field=_plasma_val("B0", 1.0),
        plasma_current=_plasma_val("Ip", 1.0) * 1.0e6,
        deuterium_fraction=_plasma_val("d_fraction", 0.5),
        tritium_fraction=_plasma_val("t_fraction", 0.5),
        tauE_e=_plasma_val("tauE_e", 0.15), tauE_i=_plasma_val("tauE_i", 0.15),
        alpha_heating=True, f_alpha=alpha_confined_slider.value,
        p_ecrh_MW=_nbi_val(ecrh_table, "ecrh_power", 0.0),
        ecrh_f_e=_nbi_val(ecrh_table, "ecrh_fe", 1.0),
        p_icrh_MW=_nbi_val(icrh_table, "icrh_power", 0.0),
        icrh_f_e=_nbi_val(icrh_table, "icrh_fe", 0.5),
        icrh_f_i=_nbi_val(icrh_table, "icrh_fi", 0.5),
        tau_Ee_mode=ee_mode, tau_Ei_mode=ei_mode,
        enable_orbit_loss=True,
        orbit_model=ORBIT_MODEL_MAP.get(orbit_model_select.value, "large_aspect"),
        profile_averaging=profile_avg_checkbox.value,
        cx_loss_fraction=_nbi_val(cx_manual_table, "cx_loss_fraction", 0.1),
        cx_model=CX_MODEL_MAP.get(cx_model_select.value, "manual_fraction"),
        cx_n0_over_ne=_nbi_val(cx_manual_table, "cx_n0_over_ne", 1.0e-5),
        cx_n0_lcfs_over_ne=_nbi_val(cx_manual_table, "cx_n0_lcfs_over_ne", 0.02),
        rotation_model=ROTATION_MODEL_MAP.get(rotation_model_select.value, "off"),
        manual_v_phi_m_s=_nbi_val(rotation_manual_table, "manual_v_phi_m_s", 0.0),
        tau_phi_over_tauEi=_nbi_val(rotation_manual_table, "tau_phi_over_tauEi", 1.0),
        enable_beam_beam=beam_beam_checkbox.value,
        enable_equipartition=equip_checkbox.value,
    )
    shine_model = SHINE_LABEL_TO_MODEL.get(shine_through_select.value, "manual")
    beam1 = BeamParams(
        # .strip().upper(): _BEAM_MASS_NUMBER/_BEAM_MASS_KG (hotjass/
        # physics.py) are case-sensitive ("H"/"D"/"T" only) -- this rail
        # cell is free text (NBI_STRING_KEYS), so a hand-typed lowercase
        # "d"/"h"/"t" would otherwise construct a BeamParams the solver
        # can't actually look up (a bare KeyError deep inside the solve),
        # even though _v_species (FIELD_VALIDATORS) accepts it case-
        # insensitively and wouldn't have blocked Start.
        species=str(nbi1_table.value.loc["nbi1_species", "Value"]).strip().upper(),
        power_MW=_nbi_val(nbi1_table, "nbi1_power", 0.0),
        beam_energy_keV=_nbi_val(nbi1_table, "nbi1_energy", 80.0),
        tangent_R_m=_nbi_val(nbi1_table, "nbi1_tangent_r", plasma.major_radius),
        tangent_Z_m=_nbi_val(nbi1_table, "nbi1_tangent_z", 0.0),
        shine_through_model=shine_model,
        manual_shine_through_fraction=_nbi_val(nbi1_table, "nbi1_manual_shine_frac", 0.01),
        co_current=(nbi1_direction_select.value == "Co-current"),
    )
    beam2 = BeamParams(
        species=str(nbi2_table.value.loc["nbi2_species", "Value"]).strip().upper(),
        power_MW=_nbi_val(nbi2_table, "nbi2_power", 0.0),
        beam_energy_keV=_nbi_val(nbi2_table, "nbi2_energy", 80.0),
        tangent_R_m=_nbi_val(nbi2_table, "nbi2_tangent_r", plasma.major_radius),
        tangent_Z_m=_nbi_val(nbi2_table, "nbi2_tangent_z", 0.0),
        shine_through_model=shine_model,
        manual_shine_through_fraction=_nbi_val(nbi2_table, "nbi2_manual_shine_frac", 0.01),
        co_current=(nbi2_direction_select.value == "Co-current"),
    )
    return HotJassModel(plasma=plasma, beams=[beam1, beam2])


def _greenwald(model: HotJassModel, n_e0: float | None = None):
    """(<n_e> line-average, n_GW, <n_e>/n_GW), all in m^-3 -- ported
    verbatim from hi_jass_app.py's own `_greenwald()`."""
    p = model.plasma
    n_e0 = p.central_density if n_e0 is None else float(n_e0)
    n_gw = (p.plasma_current / 1.0e6) / (np.pi * max(p.minor_radius, 1.0e-6) ** 2) * 1.0e20
    rho = np.linspace(0.0, 1.0, 201)
    shape = float(np.mean(np.maximum(1.0 - rho ** 2, 0.0) ** (2.0 * max(p.density_peaking, 0.0))))
    n_line = n_e0 * shape
    return n_line, n_gw, (n_line / n_gw if n_gw > 0.0 else float("inf"))


def _central_and_avg_temps(op, plasma):
    """(Te0, Ti0, <Te>, <Ti>) -- Te0/Ti0 are the central/on-axis values
    (same fallback `build_plasma_tab` always used for the profile plot);
    <Te>/<Ti> are the REAL volume average, central/(1+2*peaking) -- the
    closed-form volume-average relation for a (1-rho^2)^p profile over a
    circular cross-section (verified by hand: substituting u=1-rho^2
    collapses the integral to exactly 1/(1+p)), the SAME relationship
    hotjass/solve.py itself already uses to relate Te0_keV back to
    Te_keV. Shared between `build_plasma_tab` and `build_power_tab` so
    both use the identical, correct average -- factored out after a real
    bug where `<Te>`/`<Ti>` were shown as the flat/central value instead
    (the user caught it: "<Te>/<Ti> ... (= maximum)")."""
    prof_on = plasma.profile_averaging
    te_c = (op.Te0_keV if prof_on and op.Te0_keV is not None else op.Te_keV) or 0.0
    ti_c = (op.Ti0_keV if prof_on and op.Ti0_keV is not None else op.Ti_keV) or 0.0
    p_te = plasma.temp_peaking
    p_ti = plasma.temp_peaking_i if plasma.temp_peaking_i >= 0.0 else plasma.temp_peaking
    te_avg = te_c / (1.0 + 2.0 * p_te)
    ti_avg = ti_c / (1.0 + 2.0 * p_ti)
    return te_c, ti_c, te_avg, ti_avg


def _beam_chord(beam, plasma, Te_keV: float, n: int = 600):
    """Sample of a beam's real tangent chord -- ported from
    hi_jass_app.py's own `_beam_chord_samples()`, trimmed to what the Beam
    tab actually plots (survival + birth rate vs rho); `sigma` (the
    stopping cross-section) is a SINGLE scalar per this model (evaluated
    once at central n_e/T_e, not re-evaluated per rho -- see this
    session's own plan file, gap #3), returned alongside for the Beam
    tab's own parameter list."""
    rcp = plasma.centrepost_radius if plasma.centrepost_radius > 0.0 else None
    ch = hj_physics.tangential_chord(
        plasma.major_radius, plasma.minor_radius, plasma.elongation,
        tangent_R_m=beam.tangent_R_m, tangent_Z_m=beam.tangent_Z_m,
        R_centrepost_m=rcp, n_samples=n)
    if ch is None:
        return None
    s, rho, R = ch
    pk = max(plasma.density_peaking, 0.0)
    ne = plasma.central_density * np.maximum(1.0 - rho ** 2, 0.0) ** (2.0 * pk)
    A = hj_physics.beam_mass_number(beam.species.upper())
    shine_model = "riviere" if beam.shine_through_model == "manual" else beam.shine_through_model
    sigma = hj_physics.stopping_cross_section_m2(
        beam.beam_energy_keV / A, shine_model, plasma.central_density * 1.0e-6,
        max(Te_keV, 1.0), plasma.effective_charge, species=beam.species.upper())
    ds = np.gradient(s)
    tau = np.cumsum(ne * sigma * ds)
    tau = tau - tau[0]
    survival = np.exp(-tau)
    birth = ne * sigma * survival
    return dict(s=s, rho=rho, ne=ne, survival=survival, birth=birth, sigma=sigma, ds=ds)


def _orbit_cutoff_rho(beam, plasma) -> float:
    """Lower rho of the prompt first-orbit-loss zone for this beam (1.0 =
    no loss zone) -- ported verbatim from hi_jass_app.py's own
    `_orbit_cutoff_rho` (mirrors the criteria in
    physics.first_orbit_loss_fraction[_st]: gyro, passing-drift,
    trapped-tip), needed for the Beam tab's own "fast-ion birth vs
    normalised radius" panel's loss-zone shading."""
    if not plasma.enable_orbit_loss:
        return 1.0
    a = plasma.minor_radius
    sp = beam.species.upper()
    Ip_MA = plasma.plasma_current / 1.0e6
    rho_li = hj_physics.larmor_radius_m(beam.beam_energy_keV, plasma.toroidal_field, sp)
    co = bool(beam.co_current)
    if plasma.orbit_model in ("st_meanshift", "st_pitch"):
        w = hj_physics.st_orbit_widths(
            beam.beam_energy_keV, plasma.toroidal_field, Ip_MA, plasma.major_radius,
            a, plasma.elongation, plasma.triangularity, sp)
        wp, wb = w["w_pass"] / a, w["w_ban"] / a
        s = -1.0 if co else 1.0
        gyro = 1.0 - rho_li / a
        passing = 1.0 if co else 1.0 - wp
        trapped = 1.0 - 0.5 * wb - s * 0.25 * wp
        return float(max(0.0, min(gyro, passing, trapped)))
    if co:
        return 1.0
    dr = hj_physics.passing_orbit_width(
        beam.beam_energy_keV, plasma.toroidal_field, Ip_MA, plasma.major_radius,
        a, plasma.elongation, sp)
    return float(max(0.0, 1.0 - dr / a))


def _tex_num(x: float, sig: int = 3) -> str:
    """Format a number as LaTeX source, converting Python's `1.23e+20`
    exponential notation into `1.23\\times10^{20}` -- needed because
    Panel's Markdown pane only runs MathJax on `$$...$$` blocks (verified:
    single-`$` and `\\(...\\)` inline delimiters are NOT supported --
    `disable_mathjax` in panel/pane/markup.py only documents `$$`), so
    every number/label in the result tabs' parameter panels has to live
    inside a `$$...$$` block, LaTeX-native exponents included."""
    s = f"{x:.{sig}g}"
    if "e" in s:
        mantissa, exp = s.split("e")
        exp = int(exp)
        mantissa = mantissa.rstrip("0").rstrip(".") if "." in mantissa else mantissa
        if mantissa in ("1", "-1"):
            return ("-" if mantissa == "-1" else "") + f"10^{{{exp}}}"
        return f"{mantissa}\\times10^{{{exp}}}"
    return s


# Hoisted out of `_operating_point_blocks()` below so `_operating_point_
# page1_blocks()` (the new Results-View "Operating Point" PDF's own Models
# section) can cite the SAME governing-expression text without a second,
# separately-maintained copy of the same LaTeX strings.
CONFINEMENT_FORMULA = {
    "Kaye NSTX L-mode": r"\tau_E = 4.73\times10^{-4}\ I_p[\mathrm{A}]^{1.01}\,B_t^{0.70}\,n_e^{-0.07}\,"
                         r"P_{loss}[\mathrm{W}]^{-0.37}",
    "Kaye NSTX H-mode": r"\tau_E = 4.69\times10^{-9}\ I_p[\mathrm{A}]^{0.57}\,B_t^{1.08}\,n_e^{0.44}\,"
                         r"P_{heat}[\mathrm{W}]^{-0.73}",
    "IPB98(y,2) ELMy H-mode": r"\tau_E = 0.0562\ I_p^{0.93} B_t^{0.15} n_{19}^{0.41} P_{loss}^{-0.69}"
                               r" R_0^{1.97}\kappa^{0.78}\varepsilon^{0.58} M_{eff}^{0.19}",
}
CX_FORMULA = {
    "Manual fraction": r"f_{cx} = f_{cx,\text{manual}}\ \text{(fixed knob)}",
    "Manual n0/ne": r"f_{cx} = 1-\exp\!\left(-\!\int n_0\,\langle\sigma v\rangle_{cx}\,d\ell\right),"
                    r"\quad n_0 = (n_0/n_e)_{\text{manual}}\,n_e",
    "Penetration (n0_LCFS/ne)": r"n_0(\rho)\ \text{from edge penetration (}n_{0,\text{LCFS}}/n_e\text{)},"
                                  r"\quad f_{cx} = 1-\exp\!\left(-\!\int n_0\langle\sigma v\rangle_{cx}d\ell\right)",
}


def _operating_point_blocks(op, model: HotJassModel, vol: float) -> list:
    """Device name + the models ACTUALLY selected for this run (confinement,
    beam stopping, first-orbit loss, CX loss, rotation, fusion channels),
    each paired with its own governing expression and the real computed
    result from the just-solved OperatingPoint -- appended after
    ASSUMPTIONS_BLOCKS' own generic/default formulae by
    `_full_assumptions_blocks()` (kept exactly as-is, per the user's own
    explicit "keep the generic expressions" ask). Reuses the SAME
    `(kind, text)` tuple format ASSUMPTIONS_BLOCKS already uses -- no
    changes needed to `_assumptions_markdown()`/`_render_assumptions_pdf()`
    to render this too. Every "eq" block's own `text` goes through the
    exact same `$$...$$`-wrapping pipeline as every other result panel in
    this file -- any `%` inside it needs the same `\\%` (2 literal
    backslashes in a RAW string) treatment documented at length in
    `build_beam_tab`'s own loss-line comment, for the same CommonMark-
    escaping reason."""
    plasma = model.plasma
    device = machine_state["custom_name"] or machine_state["selected"] or "(custom / hand-edited)"
    blocks: list = [
        ("h2", f"Operating Point -- {device}"),
        ("p", "Models actually selected for this run, their governing "
              "expressions, and the resulting values -- regenerated from "
              "the most recently completed calculation (press Start again "
              "after changing inputs to refresh this section)."),
    ]

    # ---- Device settings ------------------------------------------------
    # Groups everything that's a per-device/per-run KNOB (confinement
    # choice, alpha confinement, e-i equipartition) under ONE heading,
    # rather than each getting its own top-level "h2" section -- per the
    # user's own explicit "Confinement applies to the active 'Device'
    # settings... Add the alpha confinement setting and i-e equipartition
    # (to Device settings)" ask. All formulas below use CANONICAL, single-
    # backslash, real LaTeX -- same convention as ASSUMPTIONS_BLOCKS' own
    # pre-existing content, and what `_render_assumptions_pdf()` needs
    # verbatim (matplotlib mathtext gets this `text` directly, with NO
    # markdown processing at all). `_assumptions_markdown()` is the one
    # place that doubles every backslash before wrapping in `$$...$$`,
    # since ONLY the on-screen path goes through CommonMark (which
    # silently strips a single backslash before escapable punctuation like
    # `%`/`,`/`!` -- see that function's own comment for the full
    # mechanism). Do NOT hand-double backslashes here -- confirmed the
    # hard way: an earlier version of this function DID pre-double them
    # (matching the OTHER tab builders' own convention, which don't ALSO
    # feed a raw-LaTeX PDF renderer), and `_render_assumptions_pdf()` then
    # silently failed on every "eq" block containing one (`\\%` parses in
    # mathtext as "line-break then bare %", not "escaped percent" -- a
    # `ParseException` inside the FileDownload callback, which Panel
    # swallows rather than surfacing, so the button visibly "worked" but
    # no PDF was ever produced).
    blocks.append(("h2", "Device settings"))
    conf_label = confinement_select.value
    conf_formula = CONFINEMENT_FORMULA.get(conf_label)
    blocks.append(("p", f"Confinement: {conf_label}"))
    blocks.append(("eq", conf_formula) if conf_formula else
                   ("p", "Fixed, user-specified tauE,e/tauE,i values -- no scaling law."))
    blocks.append(("eq", r"\tau_{E,e} = " + _tex_num(op.tau_E_s) + r"\ \mathrm{s}"
                          r"\qquad \tau_{E,i} = " + _tex_num(op.tau_Ei_s) + r"\ \mathrm{s}"))
    blocks.append(("p", f"Alpha fraction confined (f_alpha): {alpha_confined_slider.value:.3g}"))
    if alpha_confined_slider.value > 0.0:
        blocks.append(("eq", r"P_\alpha = " + _tex_num(op.P_alpha_w * 1.0e-6) + r"\ \mathrm{MW}"))
    eq_on = equip_checkbox.value
    blocks.append(("p", f"Electron-ion equipartition: {'On' if eq_on else 'Off'}"))
    if eq_on:
        blocks.append(("eq", r"P_{ei} = " + _tex_num(op.P_ei_w * 1.0e-6) + r"\ \mathrm{MW}"))

    # ---- Beam stopping / shine-through ---------------------------------
    blocks.append(("h2", f"Beam stopping: {shine_through_select.value}"))
    blocks.append(("eq", r"\tau_b=\sigma_{stop}(E_b/A_b)\int_{chord} n_e(\rho(s))\,ds,"
                          r"\quad f_{shine,b}=e^{-\tau_b}"))
    if op.f_capture:
        for i, fc in enumerate(op.f_capture):
            blocks.append(("eq",
                r"\text{NBI-" + str(i + 1) + r"}:\ f_{\text{shine}} = " + f"{100.0 * (1.0 - fc):.3g}"
                r"\%,\ \ f_{\text{capture}} = " + f"{100.0 * fc:.3g}" + r"\%"))

    # ---- First-orbit loss -----------------------------------------------
    orbit_label = orbit_model_select.value
    blocks.append(("h2", f"First-orbit loss: {orbit_label}"))
    if orbit_label == "Large-aspect (q* rho_Li)":
        blocks.append(("eq", r"\Delta r = q_*\,\rho_{Li},\quad f_{orbit}=f(\Delta r/a)"))
    else:
        blocks.append(("eq", r"w_{\text{pass}}=\varepsilon\,\rho_\theta,"
                              r"\quad w_{\text{ban}}=2\sqrt{\varepsilon}\,\rho_\theta"))
    if op.f_orbit_loss:
        for i, fo in enumerate(op.f_orbit_loss):
            blocks.append(("eq", r"\text{NBI-" + str(i + 1) + r"}:\ f_{\text{orbit}} = "
                                  + f"{100.0 * fo:.3g}" + r"\%"))

    # ---- Charge-exchange loss -------------------------------------------
    cx_label = cx_model_select.value
    cx_formula = CX_FORMULA.get(cx_label)
    blocks.append(("h2", f"Charge-exchange loss: {cx_label}"))
    if cx_formula:
        blocks.append(("eq", cx_formula))
    if op.f_cx_loss:
        for i, fcx in enumerate(op.f_cx_loss):
            blocks.append(("eq", r"\text{NBI-" + str(i + 1) + r"}:\ f_{cx} = "
                                  + f"{100.0 * fcx:.3g}" + r"\%"))

    # ---- Rotation ---------------------------------------------------------
    rot_label = rotation_model_select.value
    blocks.append(("h2", f"Rotation: {rot_label}"))
    if rot_label == "Off":
        blocks.append(("p", "v_phi = 0 -- no rotation correction applied to beam-target reactivity."))
    else:
        if rot_label == "Momentum balance":
            blocks.append(("eq", r"\frac{L}{\tau_\phi} = \sum_b \pm\tau_{NBI,b},"
                                  r"\quad \tau_\phi = \frac{\tau_\phi}{\tau_{Ei}}\,\tau_{Ei}"))
        blocks.append(("eq", r"v_\phi = " + _tex_num(op.v_phi_m_s) + r"\ \mathrm{m/s}"
                              r"\qquad \tau_{NBI} = " + _tex_num(op.torque_total_Nm) + r"\ \mathrm{N\,m}"))

    # ---- Fusion rates -------------------------------------------------------
    # Formulae (thermal/beam-target/beam-beam) live ONCE in the Common
    # section (ASSUMPTIONS_BLOCKS' own "Fusion power" block) -- this is
    # RESULTS only, per the user's own explicit "Fusion power formulae...
    # should be in the 'Common' section" ask (they were previously
    # duplicated here too).
    bb_on = beam_beam_checkbox.value
    blocks.append(("h2", "Fusion rates (thermal + beam-target"
                          + (" + beam-beam)" if bb_on else ")")))
    mw = 1.0e-6
    blocks.append(("eq", r"P_{DT} = " + _tex_num(op.pf_dt_w * mw) + r"\ \mathrm{MW}"
                          r"\qquad P_{DD} = " + _tex_num(op.pf_dd_w * mw) + r"\ \mathrm{MW}"))
    blocks.append(("eq", r"P_{fus} = " + _tex_num(op.pf_total_w * mw) + r"\ \mathrm{MW}"
                          r"\qquad Y_n = " + _tex_num(op.neutron_rate_s) + r"\ \mathrm{s}^{-1}"))

    return blocks


def build_plasma_tab(op, model: HotJassModel) -> pn.Column:
    """n_e(rho)/T_e,i(rho) profiles -- ported from hi_jass_app.py's own
    `_render_profiles` `ax_n`/`ax_t` panels -- plus a MathJax parameter
    panel (same `pn.pane.Markdown` + `$$...$$` mechanism the Assumptions
    modal already uses, per the user's own "(all in Tex)" ask). Every
    parameter line is its own `$$...$$` block -- see `_tex_num` docstring
    for why single-`$`/`\\(...\\)` don't render in Panel's Markdown pane."""
    plasma = model.plasma
    rho = model.rho_grid()
    density = model.density_profile(rho)
    te_c, ti_c, te_avg, ti_avg = _central_and_avg_temps(op, plasma)
    te_profile = model.temperature_profile(rho, te_c)
    ti_profile = model.temperature_profile(rho, ti_c, ion=True)

    fig = plt.Figure(figsize=RESULT_FIGSIZE, dpi=GEOM_DPI)
    fs = 9
    ax_n = fig.add_subplot(121)
    ax_n.plot(rho, density / 1.0e20, color="tab:blue")
    ax_n.set_title(r"$n_e(\rho)$, $p_n=%.2f$" % plasma.density_peaking, fontsize=fs * 1.1, fontweight="bold")
    ax_n.set_xlabel(r"$\rho$", fontsize=fs)
    ax_n.set_ylabel(r"$n_e$ [$10^{20}\,\mathrm{m}^{-3}$]", fontsize=fs)
    ax_n.tick_params(labelsize=fs * 0.85)
    ax_n.grid(alpha=0.3)

    ax_t = fig.add_subplot(122)
    ax_t.plot(rho, te_profile, color="tab:green", label=r"$T_e$")
    ax_t.plot(rho, ti_profile, color="tab:red", label=r"$T_i$")
    ax_t.set_title(r"$T_e(\rho),\ T_i(\rho)$", fontsize=fs * 1.1, fontweight="bold")
    ax_t.set_xlabel(r"$\rho$", fontsize=fs)
    ax_t.set_ylabel(r"$T$ [keV]", fontsize=fs)
    ax_t.tick_params(labelsize=fs * 0.85)
    ax_t.legend(fontsize=fs * 0.85)
    ax_t.grid(alpha=0.3)
    fig.suptitle("Plasma profiles", fontsize=fs * 1.2, fontweight="bold")
    fig.subplots_adjust(left=0.09, right=0.97, bottom=0.14, top=0.84, wspace=0.32)

    n_line, n_gw, f_gw = _greenwald(model)
    q_star = hj_physics.safety_factor_cyl_edge_arbitrary_A(
        plasma.plasma_current / 1.0e6, plasma.toroidal_field, plasma.major_radius,
        plasma.minor_radius, plasma.elongation, plasma.triangularity)
    gw_warn = r"\ \ (\textbf{above Greenwald limit})" if f_gw > 1.0 else ""
    # Fraction of the total ion density that's thermal (Maxwellian D+T)
    # rather than fast/beam ions -- op.nD0_m3/nT0_m3/nb0_m3 are all real
    # OperatingPoint fields already used elsewhere in this file (Beam/
    # Fusion tabs), not new physics.
    n_thermal = op.nD0_m3 + op.nT0_m3
    n_sum = n_thermal + op.nb0_m3
    n_therm_frac = n_thermal / n_sum if n_sum > 0.0 else float("nan")
    conf_label = confinement_select.value
    md = "\n\n".join([
        "### Profile formulae",
        r"$$n_e(\rho)=n_{e0}(1-\rho^2)^{2p_n}$$",
        r"$$T_{e,i}(\rho)=T_{e0,i0}(1-\rho^2)^{2p_T}$$",
        "### Parameters",
        f"$$n_{{e0}} = {_tex_num(op.ne0_m3)}\\ \\mathrm{{m}}^{{-3}}"
        f"\\qquad \\langle n_e\\rangle = {_tex_num(n_line)}\\ \\mathrm{{m}}^{{-3}}$$",
        f"$$\\langle T_e\\rangle = {_tex_num(te_avg)}\\ \\mathrm{{keV}}"
        f"\\qquad \\langle T_i\\rangle = {_tex_num(ti_avg)}\\ \\mathrm{{keV}}$$",
        f"$$T_{{e0}} = {_tex_num(te_c)}\\ \\mathrm{{keV}}"
        f"\\qquad T_{{i0}} = {_tex_num(ti_c)}\\ \\mathrm{{keV}}$$",
        # `\\\\%` (4 backslashes) is deliberate: CommonMark treats `\%` as
        # an escaped literal "%" and silently drops the backslash BEFORE
        # MathJax ever sees it (percent is in CommonMark's escapable-
        # punctuation set, unlike letters -- `\beta`/`\qquad` etc are safe
        # since backslash+letter isn't a CommonMark escape at all). Two
        # source backslashes survive that stripping as one real backslash,
        # which is what MathJax needs to render `%` instead of treating it
        # as a LaTeX comment that swallows the rest of the line.
        f"$$\\beta_T = {op.beta_t * 100.0:.3g}\\\\%$$",
        f"$$n_{{GW}} = {_tex_num(n_gw)}\\ \\mathrm{{m}}^{{-3}}"
        f"\\qquad \\langle n_e\\rangle / n_{{GW}} = {_tex_num(f_gw)}{gw_warn}$$",
        r"$$n_{\text{thermal}}/n_{\text{sum}} = " + _tex_num(n_therm_frac) + "$$",
        f"$$q_* = {_tex_num(q_star)}$$",
        (r"$$\tau_{E,e} = " + _tex_num(op.tau_E_s) + r"\ \mathrm{s}"
         r"\qquad \tau_{E,i} = " + _tex_num(op.tau_Ei_s) + r"\ \mathrm{s}"
         r"\qquad \text{(" + conf_label + r")}$$"),
    ])
    return _result_slot_column(_result_pane(fig, RESULT_FIGSIZE),
                                pn.pane.Markdown(md, styles=RESULT_MD_STYLE, sizing_mode="stretch_width"))


# Janev's own stated validity floor (hotjass/physics.py's own
# janev_suzuki_stopping_cross_section_m2 docstring) -- energy is no longer
# CLAMPED to this range there (extrapolated instead, per an explicit
# request), but a beam operating below the floor is still using a fit
# extrapolated past where it was fit. A later direct evaluation of Suzuki
# et al (1998) -- validated against real JT-60U data, and the reason
# "Suzuki" now exists as its own Shine-through option -- found this
# extrapolation actually tracks Suzuki reasonably well (within ~5-40%),
# much closer than Riviere does (5-18x off in the same regime) -- so this
# banner now points at Suzuki as the better-validated alternative for
# these beams, not Riviere.
JANEV_VALID_E_PER_AMU = (100.0, 1.0e4)
JANEV_WARNING_CSS = {
    "color": "#a30000", "font-weight": "bold", "font-size": "12.5px",
    "background": "#ffe2e2", "border": "1px solid #d90000", "border-radius": "4px",
    "padding": "6px 10px", "margin": "0 0 6px 0",
}


def _janev_range_warning(model: HotJassModel) -> str | None:
    """None if the active shine-through model isn't Janev, or every beam's
    E/A falls inside JANEV_VALID_E_PER_AMU; otherwise the warning text for
    build_beam_tab's own top-of-tab banner."""
    if shine_through_select.value != "Janev":
        return None
    lo, hi = JANEV_VALID_E_PER_AMU
    out_of_range = []
    for i, beam in enumerate(model.beams, start=1):
        A = hj_physics.beam_mass_number(beam.species.upper())
        e_per_amu = beam.beam_energy_keV / A
        if not (lo <= e_per_amu <= hi):
            out_of_range.append(f"NBI-{i} ({beam.species.upper()}, E/A={e_per_amu:.0f} keV/amu)")
    if not out_of_range:
        return None
    return (
        "⚠ Janev stopping cross-section is EXTRAPOLATED outside its validated "
        f"range ({lo:.0f}-{hi:.0f} keV/amu) for: " + "; ".join(out_of_range) + ". "
        "The Suzuki (1998) model is validated down to 10 keV/amu (against real "
        "JT-60U shine-through data) and tracks this extrapolation reasonably "
        "closely -- unlike Riviere, which runs 5-18x higher in this regime. "
        "Consider switching Shine-through model to Suzuki for these beams."
    )


def build_beam_tab(op, model: HotJassModel, vol: float) -> pn.Column:
    """2x2 grid, per the user's own explicit layout ask: upper row =
    tau_S(rho) + beam stopping/fast-ion birth rate along the beam PATH;
    lower row = fast-ion birth mapped to rho + steady-state slowing-down
    distribution vs E[keV]. The 3 new panels (everything but tau_S) are
    ported from hi_jass_app.py's own `_render_deposition` panels (2)/(3)/
    (4) -- panel (1) there, the top-view targeting geometry, is already
    covered by this app's own always-live Geometry tab, so it's not
    repeated here. sigma_S is a per-beam SCALAR (gap #3, plan file), shown
    in the parameter list, not plotted as a fabricated profile."""
    plasma = model.plasma
    rho = model.rho_grid()
    Te = op.Te_keV or 1.0
    colors = ["tab:blue", "tab:orange"]
    chords = [_beam_chord(b, plasma, Te) for b in model.beams]
    fig = plt.Figure(figsize=BEAM_FIGSIZE, dpi=GEOM_DPI)
    fs = 8.5

    # ---- upper-left: tau_S(rho) (unchanged panel from the previous layout)
    ax_tau = fig.add_subplot(221)
    edge_cut = max(len(rho) - 4, 1)
    rho_tau = rho[:edge_cut]
    density = model.density_profile(rho)
    ne_floor = np.maximum(density[:edge_cut], 1.0e17)
    te_floor = np.maximum(model.temperature_profile(rho, Te)[:edge_cut], 0.05)
    sigma_by_beam, tau_by_beam = [], []
    for i, (beam, ch) in enumerate(zip(model.beams, chords)):
        c = colors[i % len(colors)]
        sp = beam.species.upper()
        eb = beam.beam_energy_keV
        tau_prof = np.array([hj_physics.thermalization_time(float(nei), float(tei), eb, sp)
                              for nei, tei in zip(ne_floor, te_floor)])
        ax_tau.plot(rho_tau, tau_prof * 1.0e3, color=c, label=f"NBI-{i + 1} {sp} {eb:.0f} keV")
        tau_by_beam.append((i + 1, hj_physics.thermalization_time(op.ne0_m3, Te, eb, sp)))
        if ch is not None:
            e_per_amu = eb / hj_physics.beam_mass_number(sp)
            sigma_by_beam.append((i + 1, sp, ch["sigma"], e_per_amu))
    ax_tau.set_title(r"$\tau_S(\rho)$ (thermalization time)", fontsize=fs * 1.15, fontweight="bold")
    ax_tau.set_xlabel(r"$\rho$", fontsize=fs)
    ax_tau.set_ylabel(r"$\tau_S$ [ms]", fontsize=fs)
    ax_tau.set_yscale("log")
    ax_tau.tick_params(labelsize=fs * 0.8)
    ax_tau.legend(fontsize=fs * 0.7)
    ax_tau.grid(alpha=0.3, which="both")

    # ---- upper-right: beam stopping & fast-ion birth rate ALONG PATH (vs
    # s, distance from plasma entry) -- HI-Jass's own `_render_deposition`
    # panel (2), ported as-is including its shine-through/capture text box.
    ax_dep = fig.add_subplot(222)
    ax_dep2 = ax_dep.twinx()
    shine_lines = []
    for i, ch in enumerate(chords):
        if ch is None:
            continue
        c = colors[i % len(colors)]
        ax_dep.plot(ch["s"], ch["survival"], color=c, lw=1.6, label=f"NBI-{i + 1} survival")
        b = ch["birth"]
        ax_dep2.plot(ch["s"], b / (b.max() if b.max() > 0.0 else 1.0), color=c, lw=1.2, ls=":",
                     label=f"NBI-{i + 1} birth rate")
        f_capt = op.f_capture[i] if op.f_capture else 1.0
        shine_lines.append(f"NBI-{i + 1}: shine {100.0 * (1.0 - f_capt):.1f}% / "
                            f"capture {100.0 * f_capt:.1f}%")
    ax_dep.set_title("Beam stopping & fast-ion birth rate", fontsize=fs * 1.15, fontweight="bold")
    ax_dep.set_xlabel("distance along beam from plasma entry [m]", fontsize=fs)
    ax_dep.set_ylabel(r"survival $I(s)/I_0$", fontsize=fs)
    ax_dep.set_ylim(0.0, 1.03)
    ax_dep2.set_ylabel("birth rate (norm.)", fontsize=fs)
    ax_dep2.set_ylim(0.0, 1.05)
    ax_dep.tick_params(labelsize=fs * 0.8)
    ax_dep2.tick_params(labelsize=fs * 0.8)
    h1, l1 = ax_dep.get_legend_handles_labels()
    h2, l2 = ax_dep2.get_legend_handles_labels()
    ax_dep.legend(h1 + h2, l1 + l2, fontsize=fs * 0.65, loc="upper right")
    ax_dep.grid(alpha=0.3)
    if shine_lines:
        ax_dep.text(0.97, 0.45, "\n".join(shine_lines), transform=ax_dep.transAxes,
                    fontsize=fs * 0.7, va="center", ha="right",
                    bbox=dict(boxstyle="round", fc="white", ec="0.7", alpha=0.9))

    # ---- lower-left: fast-ion birth mapped to rho (chord-sampled
    # histogram) -- HI-Jass's own panel (3), incl. first-orbit-loss shading.
    ax_rho = fig.add_subplot(223)
    edges = np.linspace(0.0, 1.0, 26)
    ctr = 0.5 * (edges[:-1] + edges[1:])
    dr = edges[1] - edges[0]
    smooth = np.array([0.25, 0.5, 0.25])
    total = np.zeros_like(ctr)
    cutoffs = []
    for i, (beam, ch) in enumerate(zip(model.beams, chords)):
        if ch is None:
            continue
        c = colors[i % len(colors)]
        f_capt = op.f_capture[i] if op.f_capture else 1.0
        f_orb = op.f_orbit_loss[i] if op.f_orbit_loss else 0.0
        f_cx = op.f_cx_loss[i] if op.f_cx_loss else plasma.cx_loss_fraction
        w_mw = beam.power_MW * f_capt * (1.0 - f_orb) * (1.0 - f_cx)
        hist, _ = np.histogram(ch["rho"], bins=edges, weights=ch["birth"] * ch["ds"])
        if hist.sum() > 0:
            hist = hist / hist.sum() * w_mw / dr
        hist = np.convolve(hist, smooth, mode="same")
        ax_rho.plot(ctr, hist, color=c, lw=1.3, label=f"NBI-{i + 1}")
        total += hist
        rc = _orbit_cutoff_rho(beam, plasma)
        if rc < 0.999:
            cutoffs.append(rc)
            ax_rho.axvline(rc, color=c, ls="--", lw=1.0, alpha=0.75)
    if len(model.beams) > 1:
        ax_rho.plot(ctr, total, color="k", lw=1.8, label="total")
    if cutoffs:
        ax_rho.axvspan(min(cutoffs), 1.0, color="0.5", alpha=0.12, label="first-orbit-loss zone")
    ax_rho.set_xlabel(r"$\rho$", fontsize=fs)
    ax_rho.set_ylabel(r"deposited power [MW/unit $\rho$]", fontsize=fs)
    ax_rho.set_title("Fast-ion birth vs normalised radius", fontsize=fs * 1.15, fontweight="bold")
    ax_rho.set_xlim(0.0, 1.0)
    ax_rho.tick_params(labelsize=fs * 0.8)
    ax_rho.grid(alpha=0.3)
    ax_rho.legend(fontsize=fs * 0.65)

    # ---- lower-right: steady-state slowing-down distribution vs E [keV]
    # -- HI-Jass's own panel (4), same physics.slowing_down_distribution()/
    # average_fast_energy_keV() calls.
    ax_fe = fig.add_subplot(224)
    for i, beam in enumerate(model.beams):
        sp = beam.species.upper()
        eb = beam.beam_energy_keV
        f_capt = op.f_capture[i] if op.f_capture else 1.0
        f_orb = op.f_orbit_loss[i] if op.f_orbit_loss else 0.0
        f_cx = op.f_cx_loss[i] if op.f_cx_loss else plasma.cx_loss_fraction
        p_use = beam.power_MW * 1.0e6 * f_capt * (1.0 - f_orb) * (1.0 - f_cx)
        tau_s = hj_physics.thermalization_time(op.ne0_m3, Te, eb, sp)
        nb0_i = p_use * tau_s / (eb * 1.0e3 * hj_physics.E_CHARGE * max(vol, 1.0e-9))
        grid = np.linspace(1.0e-3, eb, 300)
        fE = hj_physics.slowing_down_distribution(Te, nb0_i, eb, grid, sp)
        mean_e = hj_physics.average_fast_energy_keV(Te, eb, sp)
        c = colors[i % len(colors)]
        ax_fe.plot(grid, fE, color=c,
                   label=fr"NBI-{i + 1} {sp} {eb:.0f} keV, $\langle E\rangle$={mean_e:.0f}")
        ax_fe.axvline(eb, color=c, ls=(0, (4, 3)), lw=1.0, alpha=0.8)
    ax_fe.set_xlabel("E [keV]", fontsize=fs)
    ax_fe.set_ylabel(r"$f(E)$ [m$^{-3}$ keV$^{-1}$]", fontsize=fs)
    ax_fe.set_ylim(bottom=0.0)
    ax_fe.set_title("Steady-state slowing-down distribution", fontsize=fs * 1.15, fontweight="bold")
    ax_fe.tick_params(labelsize=fs * 0.8)
    ax_fe.grid(alpha=0.3)
    ax_fe.legend(fontsize=fs * 0.65)

    fig.suptitle("Beam deposition & thermalization", fontsize=fs * 1.3, fontweight="bold")
    fig.subplots_adjust(left=0.09, right=0.90, bottom=0.07, top=0.92, wspace=0.55, hspace=0.45)

    sigma_lines = [
        f"$$\\text{{NBI-{i} ({sp})}}\\ \\ E/A = {e_per_amu:.3g}\\ \\mathrm{{keV/amu}}"
        f"\\qquad \\sigma_S = {_tex_num(sigma)}\\ \\mathrm{{m}}^2"
        f"\\ \\ \\text{{(constant along chord, at central }}n_e,T_e\\text{{)}}$$"
        for i, sp, sigma, e_per_amu in sigma_by_beam]
    tau_lines = [
        f"$$\\text{{NBI-{i}}}\\ \\ \\tau_S = {_tex_num(tau)}\\ \\mathrm{{s}}"
        f"\\ \\ \\text{{(at central }}n_e,T_e\\text{{)}}$$"
        for i, tau in tau_by_beam]

    # Fast-ion orbit characterization: Larmor radius + passing/banana orbit
    # widths + trapped fraction, all from `hj_physics.st_orbit_widths()` --
    # the SAME arbitrary-aspect-ratio function `_orbit_cutoff_rho()` already
    # calls for the first-orbit-loss cutoff shading above, just surfacing
    # its own returned dict fully now instead of only using `f_trap`/
    # `w_pass`/`w_ban` internally. Per the user's own explicit "add the
    # fast ion larmors, orbit widths (for passing and banana orbits),
    # passing/trapped fractions" ask.
    orbit_lines = []
    for i, beam in enumerate(model.beams):
        w = hj_physics.st_orbit_widths(
            beam.beam_energy_keV, plasma.toroidal_field, plasma.plasma_current / 1.0e6,
            plasma.major_radius, plasma.minor_radius, plasma.elongation, plasma.triangularity,
            beam.species.upper())
        f_trap = w["f_trap"]
        orbit_lines.append(
            r"$$\text{NBI-" + str(i + 1) + r"}\ \ \rho_{Li} = " + _tex_num(w["rho_Li"]) + r"\ \mathrm{m}"
            r"\qquad w_{\text{pass}} = " + _tex_num(w["w_pass"]) + r"\ \mathrm{m}"
            r"\qquad w_{\text{ban}} = " + _tex_num(w["w_ban"]) + r"\ \mathrm{m}$$")
        orbit_lines.append(
            # `\\%` here is 2 literal backslashes (this is a RAW string,
            # so no Python escape-collapsing happens the way it does in
            # an f-string -- unlike `_tex_num`'s own `\\\\%` callers
            # elsewhere, which are ordinary (non-raw) f-strings where
            # `\\\\` collapses to 2 real chars). CommonMark still strips
            # ONE level of backslash-escaping from `\%` before MathJax
            # sees it (percent is escapable ASCII punctuation), so 2 raw
            # backslashes survive as the 1 real backslash MathJax needs.
            r"$$\text{NBI-" + str(i + 1) + r"}\ \ f_{\text{trap}} = " + f"{f_trap * 100.0:.3g}"
            r"\\%\qquad f_{\text{pass}} = " + f"{(1.0 - f_trap) * 100.0:.3g}" + r"\\%$$")

    # Per-beam loss breakdown in both % (of that beam's own injected power)
    # and MW -- same shine-through/orbit/CX cascade `build_fusion_tab`'s own
    # `bt_total` loop and this tab's own `ax_rho` histogram loop already use
    # (op.f_capture/f_orbit_loss/f_cx_loss), just fully broken out per-stage
    # here instead of only the final `p_use`. Per the user's own explicit
    # "add the beam loss models with the losses values in % and MW" ask.
    loss_model_line = (
        f"Shine-through: **{shine_through_select.value}** &nbsp;&nbsp; "
        f"Orbit: **{orbit_model_select.value}** &nbsp;&nbsp; "
        f"CX-loss: **{cx_model_select.value}**")
    loss_lines = []
    for i, beam in enumerate(model.beams):
        f_capt = op.f_capture[i] if op.f_capture else 1.0
        f_orb = op.f_orbit_loss[i] if op.f_orbit_loss else 0.0
        f_cx = op.f_cx_loss[i] if op.f_cx_loss else plasma.cx_loss_fraction
        p_inj = beam.power_MW
        shine_mw = p_inj * (1.0 - f_capt)
        p_capt = p_inj * f_capt
        orbit_mw = p_capt * f_orb
        p_after_orbit = p_capt * (1.0 - f_orb)
        cx_mw = p_after_orbit * f_cx
        useful_mw = p_after_orbit * (1.0 - f_cx)
        shine_pct = 100.0 * (1.0 - f_capt)
        orbit_pct = 100.0 * f_capt * f_orb
        cx_pct = 100.0 * f_capt * (1.0 - f_orb) * f_cx
        useful_pct = 100.0 - shine_pct - orbit_pct - cx_pct
        loss_lines.append(
            r"$$\text{NBI-" + str(i + 1) + r"}\ \ P_{\text{shine}} = " + f"{shine_pct:.3g}"
            r"\\%\ (" + _tex_num(shine_mw) + r"\ \mathrm{MW})"
            r"\qquad P_{\text{orbit}} = " + f"{orbit_pct:.3g}"
            r"\\%\ (" + _tex_num(orbit_mw) + r"\ \mathrm{MW})$$")
        loss_lines.append(
            r"$$\text{NBI-" + str(i + 1) + r"}\ \ P_{\text{cx}} = " + f"{cx_pct:.3g}"
            r"\\%\ (" + _tex_num(cx_mw) + r"\ \mathrm{MW})"
            r"\qquad P_{\text{useful}} = " + f"{useful_pct:.3g}"
            r"\\%\ (" + _tex_num(useful_mw) + r"\ \mathrm{MW})$$")

    md = "\n\n".join([
        "### Parameters",
        f"$$n_{{b0}} = {_tex_num(op.nb0_m3)}\\ \\mathrm{{m}}^{{-3}}"
        f"\\qquad \\langle E_{{fast}}\\rangle = {_tex_num(op.avg_fast_energy_keV)}\\ \\mathrm{{keV}}$$",
        *sigma_lines, *tau_lines,
        "### Fast-ion orbits",
        *orbit_lines,
        "### Beam loss models",
        loss_model_line,
        *loss_lines,
    ])
    content = []
    janev_warning = _janev_range_warning(model)
    if janev_warning:
        content.append(pn.pane.Markdown(janev_warning, styles=JANEV_WARNING_CSS,
                                         sizing_mode="stretch_width"))
    content.append(_result_pane(fig, BEAM_FIGSIZE))
    content.append(pn.pane.Markdown(md, styles=RESULT_MD_STYLE, sizing_mode="stretch_width"))
    return _result_slot_column(*content)


def build_power_tab(op, model: HotJassModel) -> pn.Column:
    """Waterfall bar + pie of the NBI power-flow audit -- ported from
    hi_jass_app.py's own `_pf_waterfall`/`_pf_pie` (Sankey skipped). The
    bar was briefly removed and is now back per the user's own explicit
    "return back the waterfall to Power tab" follow-up ask. Now takes
    `model` too (was `op` alone) -- needed for `_central_and_avg_temps`,
    which the new fast/thermal energy ratio below uses."""
    mw = 1.0e-6
    v = {
        "P_inj": op.P_NB_total_w * mw, "shine": op.P_shine_w * mw,
        "orbit": op.P_orbit_loss_w * mw, "cx": op.P_cx_loss_w * mw,
        "P_use": op.P_useful_w * mw, "P_e": op.P_e_w * mw, "P_i": op.P_i_w * mw,
    }
    fig = plt.Figure(figsize=RESULT_FIGSIZE, dpi=GEOM_DPI)
    fs = 9
    ax_bar = fig.add_subplot(121)
    bars = [
        (0.0, v["P_inj"], "#3b6fb0"),
        (v["P_inj"] - v["shine"], v["shine"], "#c0504d"),
        (v["P_inj"] - v["shine"] - v["orbit"], v["orbit"], "#c0504d"),
        (v["P_use"], v["cx"], "#c0504d"),
        (0.0, v["P_use"], "#4f9d5d"),
        (0.0, v["P_e"], "#3fa7a7"),
        (0.0, v["P_i"], "#e0913a"),
    ]
    labels = ["$P_{inj}$", "shine-\nthrough", "first-\norbit", "CX\nloss", "$P_{useful}$", "electrons", "ions"]
    for i, (bottom, height, color) in enumerate(bars):
        ax_bar.bar(i, max(height, 0.0), bottom=bottom, width=0.62, color=color, edgecolor="black", linewidth=0.5)
        ax_bar.text(i, bottom + max(height, 0.0) + 0.02 * max(v["P_inj"], 1.0e-9), f"{height:.2f}",
                    ha="center", va="bottom", fontsize=fs * 0.8)
    ax_bar.set_xticks(range(len(bars)))
    ax_bar.set_xticklabels(labels, fontsize=fs * 0.8)
    ax_bar.set_ylabel("power [MW]", fontsize=fs)
    ax_bar.set_title("Power-flow waterfall", fontsize=fs * 1.1, fontweight="bold")
    ax_bar.tick_params(labelsize=fs * 0.85)
    ax_bar.grid(axis="y", alpha=0.3)

    ax_pie = fig.add_subplot(122)
    wedges = [v["shine"], v["orbit"], v["cx"], v["P_e"], v["P_i"]]
    names = ["shine-through", "first-orbit", "charge-exchange", "electron heating", "ion heating"]
    pie_colors = ["#c0504d", "#b03a37", "#d98b88", "#3fa7a7", "#e0913a"]
    keep = [(w, n, c) for w, n, c in zip(wedges, names, pie_colors) if w > 1.0e-9]
    if keep:
        ws, ns, cs = zip(*keep)
        ax_pie.pie(ws, labels=[f"{n}\n{w:.2f} MW" for n, w in zip(ns, ws)], colors=cs, autopct="%1.0f%%",
                   textprops={"fontsize": fs * 0.8}, startangle=90)
    ax_pie.set_title(f"Split of $P_{{inj}}$ = {v['P_inj']:.2f} MW", fontsize=fs * 1.1, fontweight="bold")
    closure = v["P_inj"] - (v["shine"] + v["orbit"] + v["cx"] + v["P_e"] + v["P_i"])
    fig.suptitle(f"NBI power-flow audit (closure {closure:+.3f} MW)", fontsize=fs * 1.15, fontweight="bold")
    fig.subplots_adjust(left=0.08, right=0.97, bottom=0.16, top=0.82, wspace=0.3)

    # Total heating power across EVERY source, not just NBI -- P_e_w/P_i_w
    # are "the pure BEAM heating split" (solve.py's own comment), so ECRH/
    # ICRH (P_aux_e_w/P_aux_i_w) and alpha (P_alpha_w) are real ADDITIONAL
    # OperatingPoint fields, not already folded into P_e_w/P_i_w -- summing
    # all 5 is the genuine total, not a re-count of the same power twice.
    p_total_heating_mw = (op.P_e_w + op.P_i_w + op.P_aux_e_w + op.P_aux_i_w + op.P_alpha_w) * mw
    # Fast (beam) vs. thermal (bulk ion) characteristic energy -- uses the
    # SAME real volume-averaged <T_i> `build_plasma_tab` shows (via the
    # shared `_central_and_avg_temps` helper), not the flat/central value,
    # so this doesn't reintroduce the exact bug that helper was factored
    # out to fix.
    _, _, _, ti_avg_pt = _central_and_avg_temps(op, model.plasma)
    fast_thermal_ratio = op.avg_fast_energy_keV / ti_avg_pt if ti_avg_pt > 0.0 else float("nan")
    # Fast/thermal ENERGY DENSITY ratio -- a genuinely different quantity
    # from the temperature-scale ratio above (compares STORED energy per
    # unit volume, u_fast=n_b0*<E_fast> vs u_thermal=(3/2)(ne*Te+n_i*Ti),
    # not per-particle energy). Not recomputed here -- `op.R_fast_thermal`
    # is a REAL, already-solved OperatingPoint field (hotjass/solve.py,
    # computed as physics.fast_ion_energy_density(...) /
    # physics.thermal_energy_density(...), both doing a proper rho-weighted
    # volume integral via physics.profile_volume_average -- more rigorous
    # than this file's own closed-form `_central_and_avg_temps` estimate),
    # so reusing it directly is both simpler and more correct than
    # re-deriving it from scratch here.
    fast_thermal_density_ratio = op.R_fast_thermal

    md = "\n\n".join([
        "**Loss models applied**",
        (f"Shine-through: **{shine_through_select.value}** &nbsp;&nbsp; "
         f"Orbit: **{orbit_model_select.value}** &nbsp;&nbsp; "
         f"CX-loss: **{cx_model_select.value}**"),
        "**Parameters**",
        f"$$P_e = {_tex_num(v['P_e'])}\\ \\mathrm{{MW}}"
        f"\\qquad P_i = {_tex_num(v['P_i'])}\\ \\mathrm{{MW}}"
        f"\\qquad P_{{useful}} = {_tex_num(v['P_use'])}\\ \\mathrm{{MW}}$$",
        f"$$P_{{ei}} = {_tex_num(op.P_ei_w * mw)}\\ \\mathrm{{MW}}"
        f"\\qquad P_{{\\alpha}} = {_tex_num(op.P_alpha_w * mw)}\\ \\mathrm{{MW}}$$",
        f"$$P_{{total}} = {_tex_num(p_total_heating_mw)}\\ \\mathrm{{MW}}"
        f"\\qquad \\langle E_{{fast}}\\rangle / \\langle T_i\\rangle = {_tex_num(fast_thermal_ratio)}$$",
        r"$$u_{\text{fast}}/u_{\text{thermal}} = " + _tex_num(fast_thermal_density_ratio) + "$$",
    ])
    return _result_slot_column(_result_pane(fig, RESULT_FIGSIZE),
                                pn.pane.Markdown(md, styles=POWER_MD_STYLE, sizing_mode="stretch_width"))


def build_fusion_tab(op, model: HotJassModel, vol: float) -> pn.Column:
    """P_fus(rho) radial profile (ported from hi_jass_app.py's own
    `_render_profiles` `ax_pf` panel) + pie (ported from `_render_fusion`)
    of the 6 fusion channels. The channel-breakdown bar chart was briefly
    added and is now removed again, per the user's own explicit "remove
    the bars from Fusion tab" follow-up ask (paired with putting the
    waterfall bar back on the Power tab)."""
    plasma = model.plasma
    rho = model.rho_grid()
    prof_on = plasma.profile_averaging
    Te = op.Te_keV or 1.0
    ti_c = (op.Ti0_keV if prof_on and op.Ti0_keV is not None else op.Ti_keV) or 0.0
    p_ti_show = plasma.temp_peaking if plasma.temp_peaking_i < 0.0 else plasma.temp_peaking_i
    pk_n = 1.0 + 2.0 * max(plasma.density_peaking, 0.0) if prof_on else 1.0
    nD0_axis = op.nD0_m3 * pk_n
    nT0_axis = op.nT0_m3 * pk_n
    ne_axis = op.ne0_m3
    th_total = (
        hj_physics.thermal_fusion_power_density_profile(rho, nD0_axis, nT0_axis, ti_c,
                                                          plasma.density_peaking, p_ti_show)
        + hj_physics.thermal_dd_power_density_profile(rho, nD0_axis, ti_c, plasma.density_peaking, p_ti_show)
    )
    bt_total = np.zeros_like(rho)
    for i, beam in enumerate(model.beams):
        sp = beam.species.upper()
        eb = beam.beam_energy_keV
        # A hydrogen beam doesn't undergo D-T/D-D fusion -- see the
        # matching skip + comment in _build_summary_fig for why this guard
        # has to live in the caller (beam_target_power_density_profile()
        # has no species check of its own).
        if sp not in ("D", "T"):
            continue
        f_capt = op.f_capture[i] if op.f_capture else 1.0
        f_orb = op.f_orbit_loss[i] if op.f_orbit_loss else 0.0
        f_cx = op.f_cx_loss[i] if op.f_cx_loss else plasma.cx_loss_fraction
        p_use = beam.power_MW * 1.0e6 * f_capt * (1.0 - f_orb) * (1.0 - f_cx)
        tau_s0 = hj_physics.thermalization_time(ne_axis, Te, eb, sp)
        nb0_axis = p_use * tau_s0 / (eb * 1.0e3 * hj_physics.E_CHARGE * max(vol, 1.0e-9))
        target_n = nT0_axis if sp == "D" else nD0_axis
        bt_total += hj_physics.beam_target_power_density_profile(
            rho, nb0_axis, target_n, Te, eb, sp, ne_axis, plasma.density_peaking, plasma.temp_peaking)
        if sp == "D" and nD0_axis > 0.0:
            bt_total += hj_physics.beam_target_dd_power_density_profile(
                rho, nb0_axis, nD0_axis, Te, eb, ne_axis, plasma.density_peaking, plasma.temp_peaking)

    fig = plt.Figure(figsize=FUSION_FIGSIZE, dpi=GEOM_DPI)
    fs = 9
    # width_ratios gives the pie panel more horizontal room than the
    # profile plot -- plus its own larger `radius=` below -- per the
    # user's own explicit "make the pie plot larger" ask.
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.35])
    ax_pf = fig.add_subplot(gs[0, 0])
    ax_pf.plot(rho, th_total / 1.0e3, label="thermal")
    ax_pf.plot(rho, bt_total / 1.0e3, label="beam-plasma")
    ax_pf.set_title(r"$P_{fus}(\rho)$ (D-T + D-D)", fontsize=fs * 1.1, fontweight="bold")
    ax_pf.set_xlabel(r"$\rho$", fontsize=fs)
    ax_pf.set_ylabel(r"$P_{fus}$ [kW/m$^3$]", fontsize=fs)
    ax_pf.tick_params(labelsize=fs * 0.85)
    ax_pf.legend(fontsize=fs * 0.8)
    ax_pf.grid(alpha=0.3)

    mw = 1.0e-6
    channels = [
        (op.pf_thermal_w * mw, "D-T thermal", "#4f9d5d"),
        (op.pf_beam_w * mw, "D-T beam-target", "#3fa7a7"),
        (op.pf_bb_dt_w * mw, "D-T beam-beam", "#8064a2"),
        (op.pf_dd_thermal_w * mw, "D-D thermal", "#e0913a"),
        (op.pf_dd_beam_w * mw, "D-D beam-target", "#c0504d"),
        (op.pf_bb_dd_w * mw, "D-D beam-beam", "#4bacc6"),
    ]
    pf_tot_mw = op.pf_total_w * mw

    ax_pie = fig.add_subplot(gs[0, 1])
    # `set_anchor("W")` -- a pie's circle is normally CENTERED within its
    # own (wide, per `width_ratios` above) axes box, so tightening
    # `wspace` alone only closes the gap between the two BOXES, not the
    # visual distance to the actual pie circle inside the right-hand one
    # (confirmed via a CDP screenshot: the circle barely moved despite a
    # much smaller wspace). Anchoring the axes' data area to the WEST
    # (left) edge of its box, instead of centering it, is what actually
    # pulls the drawn circle itself closer to the profile plot -- per the
    # user's own explicit "move the pie plot left" ask.
    ax_pie.set_anchor("W")
    keep = [(w, n, c) for w, n, c in channels if w > 0.005 * max(pf_tot_mw, 1.0e-9)]
    if keep:
        ws, ns, cs = zip(*keep)
        ax_pie.pie(ws, labels=[f"{n}\n{w:.3g} MW" for n, w in zip(ns, ws)], colors=cs, autopct="%1.1f%%",
                   pctdistance=0.78, radius=1.2, textprops={"fontsize": fs * 0.85}, startangle=90)
    else:
        ax_pie.text(0.5, 0.5, "no fusion power\nat this operating point", ha="center", va="center",
                    fontsize=fs, transform=ax_pie.transAxes)
    q_val = op.pf_total_w / op.P_NB_total_w if op.P_NB_total_w else float("nan")
    # `pad=` (title standoff) + extra `top=` margin below -- the larger
    # `radius=1.2` pie's own top wedge label sits high enough to collide
    # with a title placed at matplotlib's default pad otherwise.
    ax_pie.set_title(f"$P_{{fus}}$={pf_tot_mw:.3g} MW (Q={q_val:.3g})", fontsize=fs * 1.05,
                      fontweight="bold", pad=22)
    fig.suptitle("Fusion power", fontsize=fs * 1.2, fontweight="bold")
    # `wspace` tightened 0.45 -> 0.18 -- moves the pie panel closer to the
    # profile plot, per the user's own explicit "move the pie plot left"
    # ask (the two panels had a wide gap between them at the old spacing).
    fig.subplots_adjust(left=0.07, right=0.95, bottom=0.14, top=0.78, wspace=0.18)

    # Per-channel fusion power (D-T row, D-D row) + per-source neutron
    # yield (thermal/beam-target/beam-beam) -- per the user's own explicit
    # "values of fusion rates and neutrons from all sources, including
    # beam-beam" ask. `neutron_rate_thermal_s`/`beam_s`/`bb_s` are real
    # `OperatingPoint` fields (hotjass/solve.py line 280-282) that already
    # sum exactly to `neutron_rate_s` -- not derived/approximated here.
    def _tex_row(chs):
        parts = [r"\text{" + n + "} = " + _tex_num(w) + r"\ \mathrm{MW}" for w, n, _ in chs]
        return "$$" + r"\qquad ".join(parts) + "$$"

    md = "\n\n".join([
        "### Parameters",
        f"$$P_{{fus}} = {_tex_num(pf_tot_mw)}\\ \\mathrm{{MW}}"
        f"\\qquad Q = {_tex_num(q_val)}$$",
        "### Fusion power by channel",
        _tex_row(channels[0:3]),
        _tex_row(channels[3:6]),
        "### Neutron yield by source (incl. beam-beam)",
        r"$$Y_n = " + _tex_num(op.neutron_rate_s) + r"\ \mathrm{s}^{-1}"
        r"\qquad Y_n^{\text{thermal}} = " + _tex_num(op.neutron_rate_thermal_s) + r"\ \mathrm{s}^{-1}$$",
        r"$$Y_n^{\text{beam}} = " + _tex_num(op.neutron_rate_beam_s) + r"\ \mathrm{s}^{-1}"
        r"\qquad Y_n^{\text{beam-beam}} = " + _tex_num(op.neutron_rate_bb_s) + r"\ \mathrm{s}^{-1}$$",
    ])
    return _result_slot_column(_result_pane(fig, FUSION_FIGSIZE),
                                pn.pane.Markdown(md, styles=RESULT_MD_STYLE, sizing_mode="stretch_width"))


def _show_calc_error(msg: str) -> None:
    err = pn.pane.Markdown(f"**Calculation failed:**\n\n{msg}",
                            styles={"color": "#c0504d", "text-align": "center", "margin": "0"})
    for slot in (plasma_slot, beam_slot, power_slot, fusion_slot):
        slot[:] = [pn.Column(err, styles={**CONTENT_STYLE, "border-style": "dashed", "display": "flex",
                                           "align-items": "center", "justify-content": "center"},
                              sizing_mode="stretch_both", margin=(8, 8, 8, 8))]


def _refresh_result_tabs(op, model: HotJassModel, vol: float) -> None:
    # This runs on `_calc_worker`'s own background thread (via
    # `pn.state.execute`, which does NOT hop back to the main thread the
    # way its name suggests -- see `_MPL_LOCK`'s own comment) at the same
    # time the Ip-arrow animation may still be mid-tick on the main loop
    # (a small window right before `_stop_ip_animation()` -- called just
    # before this in `_done()` -- actually cancels it), so this needs the
    # same matplotlib lock as everything else that builds a Figure.
    with _MPL_LOCK:
        plasma_slot[:] = [build_plasma_tab(op, model)]
        beam_slot[:] = [build_beam_tab(op, model, vol)]
        power_slot[:] = [build_power_tab(op, model)]
        fusion_slot[:] = [build_fusion_tab(op, model, vol)]


# `min-height`/`min-width: 0` on EVERY one of these outer slot Columns --
# without it, a flex item's default `min-height/width: auto` refuses to
# shrink below its CONTENT's own intrinsic size (a well-known CSS
# flexbox footgun), which silently defeats `_result_slot_column`'s own
# `overflow: auto` one level down: instead of that inner box scrolling,
# THIS outer Column inflates to match the oversized fixed-pixel
# Matplotlib pane, and the excess then gets hard-clipped by `view_area`'s
# own `overflow: hidden` above -- with no scrollbar ever appearing, since
# the clipping happens a level above where the scroll CSS lives. This is
# exactly why content was "clipped at 100% zoom, fully visible only when
# zoomed out below ~80%" (per the user's own precise bug report): zooming
# out shrinks the DEMANDED content size in effective px below whatever
# the real browser window's own pixel height is, so the min-height:auto
# chain never needs to inflate past the visible viewport in the first
# place at that zoom level, masking the bug rather than fixing it.
_SLOT_MINSIZE = {"min-height": "0", "min-width": "0"}
plasma_slot = pn.Column(_placeholder_tab("Plasma"), styles=_SLOT_MINSIZE,
                          sizing_mode="stretch_both", margin=0)
beam_slot = pn.Column(_placeholder_tab("Beam"), styles=_SLOT_MINSIZE,
                        sizing_mode="stretch_both", margin=0)
power_slot = pn.Column(_placeholder_tab("Power"), styles=_SLOT_MINSIZE,
                         sizing_mode="stretch_both", margin=0)
fusion_slot = pn.Column(_placeholder_tab("Fusion"), styles=_SLOT_MINSIZE,
                          sizing_mode="stretch_both", margin=0)


# Tab titles matched to the Control (toolbar action) buttons' own font --
# measured via CDP, not guessed (`getComputedStyle` on the Start button:
# 16px / weight 500, vs. these tabs' previous 14px / 400 at
# GROUP_TITLE_FONT_SIZE) -- per the user's own explicit "larger and thick"
# ask. `.bk-tab` is Bokeh's own class for each tab header (confirmed via
# CDP), inside the Tabs widget's own shadow root, so this has to go
# through `stylesheets=` like every other per-widget CSS override in this
# file, not raw_css.
TABS_TITLE_CSS = ".bk-tab { font-size: 16px !important; font-weight: 500 !important; }"
# Geometry gets its own always-live `geometry_slot` (built above, no Start
# press needed); the other 4 now have their own real slots too (built just
# above, "press Start" placeholders until the first successful solve).
_VIEW_SLOTS = {"Geometry": geometry_slot, "Plasma": plasma_slot, "Beam": beam_slot,
                "Power": power_slot, "Fusion": fusion_slot}
view_tabs = pn.Tabs(*[(name, _VIEW_SLOTS[name]) for name in PLOT_TABS],
                     styles={"min-height": "0", "min-width": "0"}, stylesheets=[TABS_TITLE_CSS],
                     sizing_mode="stretch_both")
view_area = pn.Column(view_tabs, styles={"flex": "1 1 auto", "min-height": "0", "min-width": "0",
                                          "overflow": "hidden"},
                       sizing_mode="stretch_both", margin=(8, 8, 8, 8))

main_row = pn.Row(
    rail, view_area,
    styles={"min-height": "0", "overflow": "hidden"},
    sizing_mode="stretch_both",
)

main_ui[:] = [toolbar, main_row]

# Every closed modal's reserved flex-track space, neutralized -- see the
# "Viewport-fit" section of the module docstring for the full story.
modals = pn.Column(
    read_json_modal, save_json_modal, assumptions_modal,
    results_view_modal, results_save_modal, help_modal, refs_modal,
    styles={"height": "0", "min-height": "0", "overflow": "hidden", "flex": "0 0 0"},
)

# ===================================================================== page
page = pn.Column(
    favicon_setter, main_ui, exit_overlay, modals, ruler_overlay,
    styles={"background": BG_GRAY, "height": "100vh", "width": "100vw", "overflow": "hidden"},
    sizing_mode="stretch_both",
)
page.servable(title="HOT-Jass web")
