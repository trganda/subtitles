import shutil
import subprocess

from src.utils.logger import logger


def combine_subtitles(video_path, srt_path, output_path):
    """Merge subtitles into video"""

    # Check if ffmpeg exists
    if shutil.which("ffmpeg") is None:
        logger.error("ffmpeg is not installed or not in system PATH")
        raise RuntimeError("ffmpeg is not installed or not in system PATH")

    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-acodec", "copy",
        "-vcodec", "libx264",
        "-preset", "medium",
        "-vf", f"subtitles={srt_path}",
        "-loglevel", "error",
        "-stats",
        "-y", output_path
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )

    while True:
        line = process.stdout.readline()
        if not line:
            break
        line = line.strip()
        if len(line) > 0:
            logger.info(f"{line}")

    process.wait()
    if process.returncode != 0:
        logger.error(f"ffmpeg failed with return code {process.returncode}")
        raise subprocess.CalledProcessError(process.returncode, cmd)

    subprocess.run(cmd, check=True)


def test_combine_subtitles(monkeypatch):
    """Unit test for combine_subtitles function."""
    import builtins
    import types
    
    called = {}

    # Mock shutil.which to simulate ffmpeg present
    monkeypatch.setattr('shutil.which', lambda x: 'ffmpeg' if x == 'ffmpeg' else None)

    # Mock logger
    class DummyLogger:
        def error(self, msg):
            called['error'] = msg
        def info(self, msg):
            called.setdefault('info', []).append(msg)
    monkeypatch.setattr('src.utils.logger', 'logger', DummyLogger())

    # Mock subprocess.Popen
    class DummyProcess:
        def __init__(self):
            self.stdout = types.SimpleNamespace(readline=lambda: '')
            self.returncode = 0
        def wait(self):
            return 0
    monkeypatch.setattr('subprocess.Popen', lambda *a, **k: DummyProcess())

    # Mock subprocess.run
    monkeypatch.setattr('subprocess.run', lambda *a, **k: None)

    # Call the function
    combine_subtitles('video.mp4', 'subs.srt', 'out.mp4')
    
    # Check that no error was logged
    assert 'error' not in called