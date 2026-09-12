#!/usr/bin/env python3
"""Add a static fallback for reduced motion to Platane/snk SVG output."""

from pathlib import Path
import xml.etree.ElementTree as ET

GENERATED = Path(__file__).resolve().parents[1] / "assets/generated"
FALLBACK = '<style id="reduced-motion">@media(prefers-reduced-motion:reduce){*{animation:none!important}}</style>'


def main():
    for theme in ("light", "dark"):
        path = GENERATED / f"snake-{theme}.svg"
        svg = path.read_text()
        if 'id="reduced-motion"' not in svg:
            svg = svg.replace("</svg>", FALLBACK + "</svg>")
        ET.fromstring(svg)
        path.write_text(svg)
        print(f"Validated {path.name}; reduced-motion fallback present.")


if __name__ == "__main__":
    main()
