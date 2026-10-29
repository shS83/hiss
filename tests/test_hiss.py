"""Exercise actual GPU output and pointer interactions without a desktop window."""

from dataclasses import replace
import unittest

import moderngl
import pygame

from hiss import Controls, PRESETS, Renderer, Settings


class RenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Fail visibly if the required EGL/OpenGL test environment is unavailable.
        cls.ctx = moderngl.create_standalone_context(require=330, backend="egl")
        cls.renderer = Renderer(cls.ctx, (320, 240))
        cls.output = cls.ctx.simple_framebuffer((320, 240))

    @classmethod
    def tearDownClass(cls):
        cls.output.release()
        cls.renderer.release()
        cls.ctx.release()

    def render(self, settings=None, time=0.7, angle=0.2, original=False):
        self.renderer.draw(self.output, time, angle, settings or Settings(), original)
        self.assertEqual(self.ctx.error, "GL_NO_ERROR")
        return self.output.read(components=3, alignment=1)

    @staticmethod
    def colored_pixels(pixels):
        return sum(max(r, g, b) - min(r, g, b) > 30
                   for r, g, b in zip(pixels[::3], pixels[1::3], pixels[2::3]))

    def test_original_is_exact_source_and_has_visible_cube(self):
        actual = self.render(original=True)
        source = self.renderer.target.read(components=3, alignment=1)
        self.assertEqual(actual, source)
        bright = sum(value > 100 for value in actual[::3])
        self.assertGreater(bright, 1000)
        self.assertLess(bright, 320 * 240 // 2)

    def test_zero_effect_matches_original(self):
        original = self.render(original=True)
        self.assertEqual(self.render(Settings(strength=0, dispersion=0)), original)

    def test_dispersion_creates_color_and_can_be_disabled(self):
        plain = self.render(Settings(dispersion=0))
        dispersed = self.render(Settings(dispersion=0.8))
        self.assertEqual(self.colored_pixels(plain), 0)
        self.assertGreater(self.colored_pixels(dispersed), 200)
        # RGB sampling is independently usable without silhouette advection.
        self.assertGreater(self.colored_pixels(self.render(Settings(strength=0))), 100)

    def test_flow_and_rotation_animate_independently(self):
        initial = self.render()
        self.assertNotEqual(initial, self.render(time=1.3))
        self.assertNotEqual(initial, self.render(angle=1.3))
        self.assertEqual(initial, self.render())

    def test_resize_and_overlay(self):
        output = self.ctx.simple_framebuffer((640, 480))
        try:
            self.renderer.resize((640, 480))
            self.renderer.draw(output, 0, 0, Settings())
            before = output.read()
            self.renderer.overlay(Controls().draw((640, 480), Settings(), False, False, 60))
            self.assertNotEqual(before, output.read())
            self.assertEqual(self.ctx.viewport, (0, 0, 640, 480))
            self.assertEqual(self.ctx.error, "GL_NO_ERROR")
        finally:
            self.output.use()
            output.release()
            self.renderer.resize((320, 240))


class ControlTests(unittest.TestCase):
    def test_drag_clamps_and_release_stops_updates(self):
        controls = Controls()
        controls.layout((1200, 800))
        settings = Settings()
        rect = controls.sliders["dispersion"]
        controls.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                        button=1, pos=rect.center), settings)
        controls.handle(pygame.event.Event(pygame.MOUSEMOTION,
                        pos=(rect.right + 300, rect.y)), settings)
        self.assertEqual(settings.dispersion, 1)
        controls.handle(pygame.event.Event(pygame.MOUSEMOTION,
                        pos=(rect.left - 300, rect.y)), settings)
        self.assertEqual(settings.dispersion, 0)
        controls.handle(pygame.event.Event(pygame.MOUSEBUTTONUP,
                        button=1, pos=rect.center), settings)
        controls.handle(pygame.event.Event(pygame.MOUSEMOTION,
                        pos=rect.center), settings)
        self.assertEqual(settings.dispersion, 0)

    def test_preset_does_not_mutate_default(self):
        controls = Controls()
        controls.layout((1200, 800))
        settings = Settings()
        expected = replace(PRESETS["Rupture"])
        controls.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                        pos=controls.buttons["Rupture"].center), settings)
        self.assertEqual(settings, expected)
        settings.strength = 0
        self.assertEqual(PRESETS["Rupture"], expected)


if __name__ == "__main__":
    unittest.main()
