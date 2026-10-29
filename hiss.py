"""A rotating cube refracted through an animated, chromatically dispersed flow."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from pathlib import Path
import sys

import moderngl
import pygame


SHADERS = Path(__file__).parent / "shaders"


@dataclass
class Settings:
    strength: float = 0.65
    dispersion: float = 0.45
    turbulence: float = 0.50
    speed: float = 0.40
    rotation: float = 0.35


PRESETS = {
    "Quiet": Settings(0.22, 0.20, 0.30, 0.25, 0.35),
    "Hiss": Settings(),
    "Rupture": Settings(0.94, 0.75, 0.70, 0.55, 0.25),
}


class Renderer:
    """Render a clean scene to a texture, then advect its RGB sample positions."""

    def __init__(self, ctx: moderngl.Context, size: tuple[int, int]):
        self.ctx = ctx
        vertex = (SHADERS / "fullscreen.vert").read_text()
        self.programs = {
            name: ctx.program(
                vertex_shader=vertex,
                fragment_shader=(SHADERS / f"{name}.frag").read_text(),
            )
            for name in ("scene", "hiss", "overlay")
        }
        self.vaos = {name: ctx.vertex_array(program, [])
                     for name, program in self.programs.items()}
        self.scene = None
        self.target = None
        self.ui = None
        self.resize(size)

    def resize(self, size: tuple[int, int]):
        if self.scene is not None:
            self.target.release()
            self.scene.release()
            self.ui.release()
        self.size = size
        self.scene = self.ctx.texture(size, 3)
        self.scene.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.scene.repeat_x = self.scene.repeat_y = False
        self.target = self.ctx.framebuffer(color_attachments=[self.scene])
        self.ui = self.ctx.texture(size, 4)

    def draw(self, destination, flow_time: float, angle: float,
             settings: Settings, original: bool = False):
        self.ctx.disable(moderngl.BLEND)
        self.ctx.viewport = (0, 0, *self.size)
        self.target.use()
        scene = self.programs["scene"]
        scene["resolution"].value = self.size
        scene["angle"].value = angle
        self.vaos["scene"].render(vertices=3)
        destination.use()
        self.ctx.viewport = (0, 0, *self.size)
        self.scene.use(0)
        effect = self.programs["hiss"]
        effect["source"].value = 0
        effect["resolution"].value = self.size
        effect["time"].value = flow_time
        effect["strength"].value = 0.0 if original else settings.strength
        effect["dispersion"].value = 0.0 if original else settings.dispersion
        effect["turbulence"].value = settings.turbulence
        self.vaos["hiss"].render(vertices=3)

    def overlay(self, surface: pygame.Surface):
        self.ui.write(pygame.image.tobytes(surface, "RGBA", True))
        self.ui.use(1)
        self.programs["overlay"]["source"].value = 1
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self.vaos["overlay"].render(vertices=3)
        self.ctx.disable(moderngl.BLEND)

    def release(self):
        self.target.release()
        self.scene.release()
        self.ui.release()
        for vao in self.vaos.values():
            vao.release()
        for program in self.programs.values():
            program.release()


class Controls:
    INK = (227, 232, 228)
    MUTED = (133, 146, 145)
    ACCENT = (180, 240, 205)
    FIELDS = (("strength", "Distortion"), ("dispersion", "RGB dispersion"),
              ("turbulence", "Flow detail"), ("speed", "Flow speed"),
              ("rotation", "Rotation"))

    def __init__(self):
        pygame.font.init()
        self.font = pygame.font.SysFont("monospace", 14)
        self.small = pygame.font.SysFont("monospace", 12)
        self.title = pygame.font.SysFont("sans", 38, bold=True)
        self.dragging = None
        self.sliders = {}
        self.buttons = {}

    def layout(self, size):
        width, height = size
        margin = 32 if width >= 850 else 20
        gap = 24
        cell = (width - margin * 2 - gap * 4) / 5
        self.sliders = {
            field: pygame.Rect(margin + i * (cell + gap), height - 66, cell, 18)
            for i, (field, _) in enumerate(self.FIELDS)
        }
        self.buttons = {
            name: pygame.Rect(width - margin - (3 - i) * 88, 35, 80, 30)
            for i, name in enumerate(PRESETS)
        }

    def handle(self, event, settings):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for name, rect in self.buttons.items():
                if rect.collidepoint(event.pos):
                    for field, value in vars(PRESETS[name]).items():
                        setattr(settings, field, value)
            for field, rect in self.sliders.items():
                if rect.inflate(12, 28).collidepoint(event.pos):
                    self.dragging = field
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = None
        if self.dragging and event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
            rect = self.sliders[self.dragging]
            setattr(settings, self.dragging,
                    max(0.0, min(1.0, (event.pos[0] - rect.x) / rect.width)))

    def draw(self, size, settings, paused, original, fps):
        self.layout(size)
        surface = pygame.Surface(size, pygame.SRCALPHA)
        width, height = size
        margin = 32 if width >= 850 else 20

        def text(value, pos, color=self.INK, font=None):
            surface.blit((font or self.font).render(value, True, color), pos)

        text("HISS", (margin, 23), font=self.title)
        text("CHROMATIC FLOW / 001", (margin + 122, 38), self.MUTED, self.small)
        text("A study in refraction", (margin + 122, 54), self.MUTED, self.small)
        for name, rect in self.buttons.items():
            selected = settings == PRESETS[name]
            pygame.draw.rect(surface, (29, 43, 39, 230) if selected else (19, 25, 26, 220),
                             rect, border_radius=5)
            pygame.draw.rect(surface, self.ACCENT if selected else (52, 64, 62),
                             rect, 1, border_radius=5)
            label = self.small.render(name.upper(), True, self.ACCENT if selected else self.MUTED)
            surface.blit(label, label.get_rect(center=rect.center))
        status = "ORIGINAL / RGB ALIGNED" if original else "FLOW FIELD / RGB OFFSET"
        text(status, (margin, 101), self.MUTED, self.small)
        text("PAUSED" if paused else f"LIVE / {fps:02.0f} FPS",
             (margin, height - 164), self.ACCENT, self.small)
        pygame.draw.rect(surface, (12, 17, 19, 238), (0, height - 130, width, 130))
        pygame.draw.line(surface, (44, 55, 54), (margin, height - 130),
                         (width - margin, height - 130))
        for field, label in self.FIELDS:
            rect = self.sliders[field]
            value = getattr(settings, field)
            text(label, (rect.x, rect.y - 32), font=self.small)
            text(f"{value:.2f}", (rect.right - 28, rect.y - 15), self.MUTED, self.small)
            y = rect.centery + 3
            pygame.draw.line(surface, (58, 70, 68), (rect.x, y), (rect.right, y), 2)
            x = round(rect.x + value * rect.width)
            pygame.draw.line(surface, self.ACCENT, (rect.x, y), (x, y), 2)
            pygame.draw.circle(surface, self.ACCENT, (x, y), 4)
        text("SPACE pause   TAB hold original   1/2/3 presets   R reset   H hide UI   ESC quit",
             (margin, height - 25), self.MUTED, self.small)
        return surface


def save_frame(framebuffer, path: Path):
    surface = pygame.image.frombytes(framebuffer.read(components=3, alignment=1),
                                     framebuffer.size, "RGB", True)
    path.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(surface, str(path))


def snapshot(args):
    """Render without a window; useful for previews and shader verification."""
    ctx = moderngl.create_standalone_context(require=330, backend="egl")
    renderer = Renderer(ctx, (args.width, args.height))
    output = ctx.simple_framebuffer(renderer.size)
    settings = replace(PRESETS[args.preset])
    renderer.draw(output, args.time * settings.speed, args.time * settings.rotation * 0.55,
                  settings, args.original)
    if args.ui:
        renderer.overlay(Controls().draw(renderer.size, settings, False, args.original, 0))
    save_frame(output, args.snapshot)
    print(f"Saved {args.snapshot} ({ctx.info['GL_RENDERER']})")
    output.release()
    renderer.release()
    ctx.release()
    pygame.quit()


def run(args):
    pygame.display.init()
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)
    pygame.display.set_mode((args.width, args.height), pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE)
    pygame.display.set_caption("HISS / chromatic flow")
    ctx = moderngl.create_context(require=330)
    renderer = Renderer(ctx, pygame.display.get_window_size())
    controls = Controls()
    controls.layout(renderer.size)
    settings = replace(PRESETS[args.preset])
    clock = pygame.time.Clock()
    running, paused, show_ui = True, False, True
    flow_time, angle = 0.0, 0.0
    try:
        while running:
            dt = min(clock.tick(60) / 1000.0, 0.05)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type in (pygame.WINDOWRESIZED, pygame.WINDOWSIZECHANGED):
                    size = pygame.display.get_window_size()
                    if min(size) > 0:
                        renderer.resize(size)
                        controls.layout(size)
                elif event.type == pygame.WINDOWFOCUSLOST:
                    controls.dragging = None
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_SPACE:
                        paused = not paused
                    elif event.key == pygame.K_h:
                        show_ui = not show_ui
                        controls.dragging = None
                    elif event.key == pygame.K_r:
                        settings = replace(PRESETS["Hiss"])
                        flow_time, angle = 0.0, 0.0
                    elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                        settings = replace(list(PRESETS.values())[event.key - pygame.K_1])
                if show_ui:
                    controls.handle(event, settings)
            if not paused:
                flow_time += dt * settings.speed
                angle += dt * settings.rotation * 0.55
            original = pygame.key.get_pressed()[pygame.K_TAB]
            renderer.draw(ctx.screen, flow_time, angle, settings, original)
            if show_ui:
                renderer.overlay(controls.draw(renderer.size, settings, paused, original, clock.get_fps()))
            pygame.display.flip()
    finally:
        renderer.release()
        ctx.release()
        pygame.quit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, default=1200)
    parser.add_argument("--height", type=int, default=800)
    parser.add_argument("--preset", choices=PRESETS, default="Hiss")
    parser.add_argument("--snapshot", type=Path, help="Save a PNG without opening a window (requires EGL).")
    parser.add_argument("--time", type=float, default=4.0, help="Snapshot animation time in seconds.")
    parser.add_argument("--original", action="store_true", help="Disable distortion in the snapshot.")
    parser.add_argument("--ui", action="store_true", help="Include controls in the snapshot.")
    args = parser.parse_args()
    if args.width < 640 or args.height < 480:
        parser.error("Use a canvas of at least 640 x 480.")
    try:
        snapshot(args) if args.snapshot else run(args)
    except (moderngl.Error, pygame.error) as error:
        print(f"Unable to start the OpenGL renderer: {error}", file=sys.stderr)
        print("An OpenGL 3.3 capable driver is required; snapshots also require EGL.", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
