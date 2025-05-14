import os
import subprocess
import shutil
from src.utils.logger import logger

def transcribe_audio(audio_path, model_path):
    """Transcribe audio segment using whisper-cli"""
    # Check if whisper-cli exists
    if shutil.which("whisper-cli") is None:
        logger.error("whisper-cli is not installed or not in system PATH")
        raise RuntimeError("whisper-cli is not installed or not in system PATH")

    srt_path = os.path.splitext(audio_path)[0]
    cmd = [
        "whisper-cli",
        "-m", model_path,
        "-f", audio_path,
        "-osrt",
        "-of", srt_path,
        "-pp",
        "-np",
    ]

    logger.info(f"Starting transcription for {audio_path}")
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
        logger.error(f"Error transcribing {audio_path}")
        raise subprocess.CalledProcessError(process.returncode, cmd)
    
    return srt_path + ".srt"