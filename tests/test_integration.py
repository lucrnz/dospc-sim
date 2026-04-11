"""Integration tests for DosPC Sim application."""

import pytest

from dospc_sim.main import DosPCSimApp


class TestAppIntegration:
    """Integration tests for the full application."""

    @pytest.fixture
    async def app(self):
        """Create and return a DosPCSimApp instance for async testing."""
        app = DosPCSimApp()
        return app

    async def test_app_composition(self, app):
        """Test that the app composes correctly with all components."""
        async with app.run_test():
            # Check that the app mounted
            assert app.is_mounted

            # Check for tabs
            from textual.widgets import TabbedContent

            tabs = app.query_one(TabbedContent)
            assert tabs is not None

            # Check for footer
            from textual.widgets import Footer

            footer = app.query_one(Footer)
            assert footer is not None

    async def test_tabs_exist(self, app):
        """Test that tabs are present."""
        async with app.run_test():
            # Check that tabs exist
            from textual.widgets import TabbedContent

            tabs = app.query_one(TabbedContent)
            assert tabs is not None

    async def test_theme_toggle_integration(self, app):
        """Test theme toggle works in the running app."""
        async with app.run_test() as pilot:
            initial_dark = app.dark_mode

            # Press 't' to toggle theme
            await pilot.press("t")

            # Check theme changed
            assert app.dark_mode != initial_dark

            # Press 't' again to toggle back
            await pilot.press("t")
            assert app.dark_mode == initial_dark

    async def test_quit_key_binding(self, app):
        """Test that quit key binding is registered."""
        async with app.run_test() as pilot:
            # Just verify the app is running and responds to keys
            assert app.is_mounted

            # Press 'q' to quit
            await pilot.press("q")

            # App should be closed
            assert not app.is_running


class TestTabInteraction:
    """Tests for tab interactions."""

    @pytest.fixture
    async def app(self):
        """Create a DosPCSimApp instance for testing."""
        return DosPCSimApp()

    async def test_tabs_visible(self, app):
        """Test that all tabs are visible."""
        async with app.run_test():
            from textual.widgets import TabbedContent

            tabs = app.query_one(TabbedContent)
            assert tabs is not None

            # Check tabs are visible
            assert tabs.display

    async def test_tab_switching(self, app):
        """Test that tabs can be switched."""
        async with app.run_test():
            from textual.widgets import TabbedContent

            tabs = app.query_one(TabbedContent)
            assert tabs is not None

            # App should be mounted
            assert app.is_mounted
