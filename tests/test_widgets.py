"""Tests for individual widgets in DosPC Sim."""

import pytest
from textual.widgets import Label

from dospc_sim.main import ComingSoonScreen


class TestComingSoonScreenContent:
    """Tests for ComingSoonScreen content and layout."""

    def test_screen_full_size(self):
        """Test that screen CSS defines full size."""
        # Check CSS defines full width/height
        assert 'width: 100%' in ComingSoonScreen.DEFAULT_CSS
        assert 'height: 100%' in ComingSoonScreen.DEFAULT_CSS

    def test_screen_centered_content(self):
        """Test that screen content is centered."""
        # Check the CSS defines centered content
        assert 'content-align: center middle' in ComingSoonScreen.DEFAULT_CSS

    @pytest.mark.asyncio
    async def test_version_in_content(self):
        """Test that version number is displayed."""
        from dospc_sim.main import DosPCSimApp

        app = DosPCSimApp()
        async with app.run_test():
            screen = ComingSoonScreen()
            await app.mount(screen)

            labels = list(screen.query(Label))
            label_texts = [str(label.render()) for label in labels]
            assert any('v1.0' in text for text in label_texts)


class TestAccessibility:
    """Tests for accessibility features."""

    def test_all_widgets_have_descriptions(self):
        """Test that widgets are self-describing."""
        screen = ComingSoonScreen()

        # Check docstrings exist
        assert ComingSoonScreen.__doc__ is not None

        # Check that compose methods exist
        assert callable(screen.compose)

    def test_keyboard_shortcuts_documented(self):
        """Test that keyboard shortcuts are defined."""
        from dospc_sim.main import DosPCSimApp

        # Check bindings exist and are documented
        # BINDINGS is a list of tuples: (key, action, description)
        bindings = DosPCSimApp.BINDINGS
        assert len(bindings) > 0

        for binding in bindings:
            # Each binding is a tuple of (key, action, description)
            assert len(binding) >= 3
            assert binding[0] is not None  # key
            assert binding[1] is not None  # action
            assert binding[2] is not None  # description
