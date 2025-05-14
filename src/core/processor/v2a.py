import os
import shutil
import subprocess

from src.utils.logger import logger


def extract_audio(video_path, output_dir):
    """Extract audio from video file and save as WAV"""

    # Check if ffmpeg exists
    if shutil.which("ffmpeg") is None:
        logger.error("ffmpeg is not installed or not in system PATH")
        raise RuntimeError("ffmpeg is not installed or not in system PATH")

    audio_path = os.path.join(output_dir, "extracted_audio.wav")

    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-map", "0:a",
        "-ac", "1",
        "-ar", "16000",
        "-af", "aresample=async=1",
        "-loglevel", "error",
        "-progress", "pipe:1",
        "-y", audio_path
    ]

    # 获取视频总时长(秒)
    duration = float(subprocess.check_output([
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ]).decode().strip())

    logger.info(f"Starting audio extraction (Total duration: {duration:.1f}s)")
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
        
        if line.startswith("out_time_ms="):
            time_ms = int(line.split("=")[1])
            time_sec = time_ms / 1000000
            progress = min(100, (time_sec / duration) * 100)
            logger.info(f"Extracting: {progress:.1f}% ({time_sec:.1f}s/{duration:.1f}s)", extra={'oneline': True})
        elif line == "progress=end":
            # logger on a new line
            print()
            logger.info("Audio extraction completed successfully")
            break

    process.wait()
    if process.returncode != 0:
        logger.error("Audio extraction failed, ffmpeg return code: %d", process.returncode)
        raise subprocess.CalledProcessError(process.returncode, cmd)
    
    return audio_path