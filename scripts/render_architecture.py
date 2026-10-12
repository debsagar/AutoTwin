"""Render README animation: uv run --with cairosvg --with pillow python scripts/render_architecture.py.

Documentation-only dependencies; the SVG is the editable source.
"""
from pathlib import Path
import io
import math
import cairosvg
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1] / 'docs/images'
base = Image.open(io.BytesIO(cairosvg.svg2png(url=str(root / 'architecture.svg')))).convert('RGB')
# Illustrative tool/evidence exchange, not measured execution telemetry.
routes = [([(290,235),(375,235)], '#6ce6cb'),
          ([(456,338),(456,356),(28,356),(28,486),(380,486),(380,506)], '#6ce6cb'),
          ([(825,506),(825,486),(1174,486),(1174,350),(748,350),(748,338)], '#b9a3ff'),
          ([(820,235),(905,235)], '#6ce6cb')]
frames = [base.copy()]
for points, color in routes:
    lengths = [math.dist(a,b) for a,b in zip(points,points[1:])]
    for i in range(12):
        distance = sum(lengths) * i / 11
        for a,b,length in zip(points,points[1:],lengths):
            if distance <= length:
                t = distance / length
                x,y = a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t
                break
            distance -= length
        frame = base.copy()
        draw = ImageDraw.Draw(frame)
        draw.ellipse((x-7,y-7,x+7,y+7), fill=color)
        draw.ellipse((x-3,y-3,x+3,y+3), fill='white')
        frames.append(frame)
frames.append(base.copy())
frames[0].save(root / 'architecture.gif', save_all=True, append_images=frames[1:],
               duration=[1000]+[110]*48+[2000], loop=1, optimize=True, disposal=1)
print(root / 'architecture.gif')
