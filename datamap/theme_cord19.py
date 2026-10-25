"""An optional look modelled on DataMapPlot's CORD-19 example map (`render --style cord19`).

Cinzel serif title with a small-caps subtitle, rainbow colours blended by position, thin
outlines around each group and small dots on white. The default look stays in theme.py.
Cinzel (SIL OFL 1.1) is embedded by DataMapPlot's offline mode, so the map works offline.
"""

from __future__ import annotations

from . import theme

DISPLAY = "Cinzel"
STACK = 'Georgia, "Times New Roman", serif'
INK, MUTED, LINE = "#111111", "#444444", "#e2e2e2"

PLOT_KWARGS = dict(
    font_family=DISPLAY,
    font_weight=600,
    tooltip_font_family=DISPLAY,
    tooltip_font_weight=400,
    background_color="#ffffff",
    noise_color="#bdbdbd",
    color_label_text=False,
    text_outline_width=8,
    text_outline_color="#ffffffdd",
    text_min_pixel_size=14,
    text_max_pixel_size=34,
    min_fontsize=14,
    max_fontsize=30,
    title_font_size=30,
    sub_title_font_size=15,
    cluster_boundary_polygons=True,
    color_cluster_boundaries=True,
    cluster_boundary_line_width=2,
    initial_zoom_fraction=0.9,  # start on the main mass, not far-off outliers
    point_radius_min_pixels=3,
    point_radius_max_pixels=10,
    tooltip_css=f"""
        font-family: Georgia, "Times New Roman", serif;
        font-size: 13px;
        line-height: 1.4;
        color: {INK};
        background: #ffffff;
        border: 1px solid {LINE};
        border-radius: 12px;
        box-shadow: 0 4px 18px rgba(0, 0, 0, 0.15);
        padding: 12px 14px;
        max-width: 400px;
    """,
)

HISTOGRAM_SETTINGS = {
    **theme.HISTOGRAM_SETTINGS,
    "histogram_bin_fill_color": "#555555",
    "histogram_bin_selected_fill_color": "#555555",
    "histogram_bin_unselected_fill_color": "#dddddd",
}

TOOLTIP_TEMPLATE = (
    f'<div style="font-family:\'{DISPLAY}\',{STACK};font-weight:700;font-size:14px;'
    f'margin-bottom:3px">{{doc_title}}</div>'
    f'<div style="font-size:12px;color:{MUTED};margin-bottom:8px">{{meta}}</div>'
    f'<div style="font-size:13px">{{snippet}}</div>'
)


def custom_css() -> str:
    return f"""
body {{ background: #ffffff; color: {INK}; }}
.container-box {{
  background: rgba(255, 255, 255, 0.9) !important;
  border-radius: 16px !important;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.12) !important;
}}
#title-container {{ margin: 8px !important; padding: 6px 14px !important; max-width: 90vw; }}
#title-container span:first-of-type {{ font-family: "{DISPLAY}", {STACK} !important; color: {INK} !important; }}
#title-container span:last-of-type {{
  font-family: "{DISPLAY}", {STACK} !important; color: {MUTED} !important; font-variant: small-caps;
}}
#search-container {{ margin: 0 8px !important; }}
#text-search {{
  font: 14px {STACK}; width: 200px; border: 1px solid #cccccc; border-radius: 8px; padding: 5px 8px;
}}
#loading {{ background: #ffffff !important; }}
"""


def custom_js() -> str:
    """Faster zoom and labels redrawn in Cinzel once the font has loaded (see theme.custom_js)."""
    return f"""
datamap.deckgl.setProps({{controller:
  {{scrollZoom: {{speed: 0.03, smooth: false}}, doubleClickZoom: true, touchZoom: true}}}});
(function () {{
  const search = document.getElementById("text-search");
  if (search) search.placeholder = "Search the map…";
  const redrawLabels = () => {{
    const old = datamap.labelLayer;
    if (!old) return false;
    const fresh = old.clone({{fontFamily: "{DISPLAY}", fontWeight: 600,
      fontSettings: {{sdf: true, buffer: 6, radius: 14, fontSize: 72}}}});
    datamap.labelLayer = fresh;
    datamap.layers = datamap.layers.map((l) => (l === old ? fresh : l));
    datamap.deckgl.setProps({{layers: [...datamap.layers]}});
    return true;
  }};
  document.fonts.load('600 24px "{DISPLAY}"').catch(() => {{}}).then(() => {{
    let tries = 0;
    const timer = setInterval(() => {{ if (redrawLabels() || ++tries > 50) clearInterval(timer); }}, 200);
  }});
}})();
"""
