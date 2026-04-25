import pytest

from dospc_sim.dos_shell import DOSShell
from dospc_sim.filesystem import UserFilesystem


@pytest.fixture
def shell(tmp_path):
    user_dir = tmp_path / 'testuser'
    user_dir.mkdir()
    fs = UserFilesystem(str(user_dir), 'testuser')
    output_capture = []

    def output_callback(text):
        output_capture.append(text)

    shell = DOSShell(fs, 'testuser', output_callback)
    shell._output_capture = output_capture
    return shell
