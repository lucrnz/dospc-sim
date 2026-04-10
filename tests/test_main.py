"""Tests for the main DosPC Sim application."""

import pytest
from textual.widgets import Label, Footer
from dospc_sim.main import DosPCSimApp, ComingSoonScreen, main


class TestDosPCSimApp:
    """Test cases for the DosPCSimApp class."""

    @pytest.fixture
    def app(self):
        """Create a DosPCSimApp instance for testing."""
        return DosPCSimApp()

    def test_app_initialization(self, app):
        """Test that the app initializes correctly."""
        assert app is not None
        assert isinstance(app, DosPCSimApp)

    def test_dark_mode_default(self, app):
        """Test that dark mode is enabled by default."""
        assert app.dark_mode is True

    def test_bindings_exist(self, app):
        """Test that key bindings are configured."""
        bindings = app.BINDINGS
        assert len(bindings) >= 3

        # Check for quit binding (bindings are tuples: (key, action, description))
        quit_bindings = [b for b in bindings if b[1] == "quit"]
        assert len(quit_bindings) > 0

        # Check for theme toggle binding
        theme_bindings = [b for b in bindings if b[1] == "toggle_theme"]
        assert len(theme_bindings) > 0

    def test_action_toggle_theme(self, app):
        """Test theme toggle action changes dark_mode state."""
        initial_mode = app.dark_mode
        app.action_toggle_theme()
        assert app.dark_mode != initial_mode

        # Toggle back
        app.action_toggle_theme()
        assert app.dark_mode == initial_mode


class TestComingSoonScreen:
    """Test cases for the ComingSoonScreen widget."""

    @pytest.fixture
    def screen(self):
        """Create a ComingSoonScreen instance for testing."""
        return ComingSoonScreen()

    def test_screen_creation(self, screen):
        """Test that the screen can be created."""
        assert screen is not None
        assert isinstance(screen, ComingSoonScreen)

    @pytest.mark.asyncio
    async def test_screen_has_content(self):
        """Test that the screen contains expected content when composed."""
        app = DosPCSimApp()
        async with app.run_test() as pilot:
            # Create screen within app context
            screen = ComingSoonScreen()
            await app.mount(screen)

            # Check that screen is mounted
            assert screen.is_mounted
            # Check for labels in the screen
            labels = list(screen.query(Label))
            assert len(labels) > 0

    @pytest.mark.asyncio
    async def test_screen_title_present(self):
        """Test that the screen contains the title."""
        app = DosPCSimApp()
        async with app.run_test() as pilot:
            screen = ComingSoonScreen()
            await app.mount(screen)

            labels = list(screen.query(Label))
            label_texts = [str(label.render()) for label in labels]

            # Check that DOSPC SIM is in one of the labels
            assert any("DOSPC SIM" in text for text in label_texts)

    @pytest.mark.asyncio
    async def test_screen_coming_soon_present(self):
        """Test that the screen contains 'COMING SOON' text."""
        app = DosPCSimApp()
        async with app.run_test() as pilot:
            screen = ComingSoonScreen()
            await app.mount(screen)

            labels = list(screen.query(Label))
            label_texts = [str(label.render()) for label in labels]

            # Check that COMING SOON is in one of the labels
            assert any("COMING SOON" in text for text in label_texts)


class TestMainFunction:
    """Test cases for the main entry point."""

    def test_main_function_exists(self):
        """Test that the main function exists and is callable."""
        assert callable(main)

    def test_main_function_returns_none_when_not_run(self):
        """Test that main function can be imported without errors."""
        # Just verify the function exists and has correct signature
        import inspect

        sig = inspect.signature(main)
        assert len(sig.parameters) == 0


class TestThemeToggle:
    """Test cases for theme toggle functionality."""

    @pytest.fixture
    def app(self):
        """Create a DosPCSimApp instance for testing."""
        return DosPCSimApp()

    def test_theme_toggle_changes_state(self, app):
        """Test that toggling theme changes dark_mode state."""
        # Start with dark mode
        app.dark_mode = True

        # Toggle to light
        app.action_toggle_theme()
        assert app.dark_mode is False

        # Toggle back to dark
        app.action_toggle_theme()
        assert app.dark_mode is True

    def test_multiple_toggles(self, app):
        """Test that multiple toggles work correctly."""
        initial_state = app.dark_mode

        # Toggle 4 times should return to initial state
        for _ in range(4):
            app.action_toggle_theme()

        assert app.dark_mode == initial_state
