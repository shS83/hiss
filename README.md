# Hiss

A real-time experiment inspired by the flowing refraction of the Hiss in *Control*:
a white rotating cube, warped through an animated velocity field, with offset RGB
sampling for chromatic dispersion. Built with Pygame and ModernGL (OpenGL 3.3).

```sh
uv sync
uv run main.py
```

Drag the five sliders to adjust distortion, RGB dispersion, flow detail, flow
speed, and cube rotation independently. Try **Quiet**, **Hiss**, and **Rupture**
for progressively stronger distortion.

| Control | Action |
| --- | --- |
| Space | Pause both animations; sliders remain active |
| Hold Tab | Compare against the undistorted cube |
| 1 / 2 / 3 | Select a preset |
| R | Reset settings and animation |
| H | Hide / show controls |
| Esc | Quit |

## How it works

1. `shaders/scene.frag` renders a shaded white cube into an offscreen texture.
2. `shaders/hiss.frag` backtraces screen coordinates through a smooth, animated
   flow field using seven midpoint integration steps. This folds and stretches
   the cube's silhouette into liquid shapes.
3. Red, green, and blue sample that texture at different offsets along the flow.
   Color appears at edges and shading transitions; a uniform white region stays
   white until a channel samples a different region.

This is a screen-space approximation of the reference's volumetric fluid
distortion, not a 3D fluid simulation. The flow is procedural, with no persistent
fluid state. The source texture could later be replaced with a rendered scene or
camera image. Set both distortion and dispersion to zero for the clean cube;
either effect can also be explored independently.

## Render a still

Headless snapshots require an EGL-capable OpenGL driver (Mesa software rendering
also works):

```sh
uv run main.py --snapshot /tmp/hiss.png --time 4 --ui
uv run main.py --snapshot /tmp/cube.png --time 4 --original
uv run main.py --snapshot /tmp/rupture.png --preset Rupture --time 8
```

The default window is 1200 × 800; use `--width` and `--height` to change it.
No images, videos, network connection, or external assets are needed at runtime.

Run the rendering and interaction checks with
`uv run python -m unittest discover -s tests -v` (requires EGL).
