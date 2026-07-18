"""Shared helper: inline the vendored Plotly + fonts into the standalone demos so
they work fully offline (no CDN). Run vendor_assets.py once to populate vendor/.
"""
from __future__ import annotations
from pathlib import Path

VENDOR = Path(__file__).resolve().parent.parent / "vendor"


def plotly_tag() -> str:
    js = (VENDOR / "plotly-2.35.2.min.js").read_text(encoding="utf-8")
    # guard against a literal </script> inside the JS closing our inline tag
    js = js.replace("</script>", "<\\/script>")
    return "<script>" + js + "</script>"


def fonts_tag() -> str:
    css = (VENDOR / "fonts_inline.css").read_text(encoding="utf-8")
    return "<style>" + css + "</style>"


def inline_offline(html: str) -> str:
    """Replace the __FONTS__ and __PLOTLY__ markers with the vendored assets."""
    return html.replace("__FONTS__", fonts_tag()).replace("__PLOTLY__", plotly_tag())
