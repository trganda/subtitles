import argparse
import logging
import os
import subprocess

from src.core.data.asr import ASRData
from src.core.processor.a2srt import transcribe_audio
from src.core.processor.merge import combine_subtitles
from src.core.processor.translater import translate_subtitle
from src.core.processor.v2a import extract_audio
from src.utils.logger import logger

def split_audio(audio_path, segment_length=180):
    """Split audio into segments no longer than 3 minutes (180 seconds)"""
    output_dir = os.path.join(os.path.dirname(audio_path), "segments")
    os.makedirs(output_dir, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-i", audio_path,
        "-f", "segment",
        "-segment_time", str(segment_length),
        "-c", "copy",
        os.path.join(output_dir, "segment_%03d.wav")
    ]
    subprocess.run(cmd, check=True)

    return sorted([
        os.path.join(output_dir, f)
        for f in os.listdir(output_dir)
        if f.startswith("segment_") and f.endswith(".wav")
    ])

def merge_srt_files(srt_files, output_path):
    """Merge multiple SRT files into one"""
    with open(output_path, 'w', encoding='utf-8') as outfile:
        for idx, srt_file in enumerate(srt_files):
            with open(srt_file, 'r', encoding='utf-8') as infile:
                content = infile.read()
                if idx > 0:
                    # Adjust timestamps for subsequent files
                    # (This is a simplified approach - you might need more sophisticated merging)
                    content = "\n\n".join([f"{i+idx*100}\n{c.split('\n', 1)[1]}" 
                                         for i, c in enumerate(content.split('\n\n'))])
                outfile.write(content)
                if idx < len(srt_files) - 1:
                    outfile.write("\n\n")

def main():
    parser = argparse.ArgumentParser(description="Generate Chinese subtitles for a video")
    parser.add_argument("-i", "--input_video", help="Path of input video file", required=True)
    parser.add_argument("-o", "--output_video", help="Path of output video with subtitles")
    parser.add_argument("-p", "--parallels_threads", default="6", help="Thread pool size for parallel processing")
    parser.add_argument("-t", "--target_language", help="Target language for translatation", default="简体中文")
    parser.add_argument("--style", help="Name of the subtitles style file", default="default")
    parser.add_argument("--work_path", default="output", help="Path for working files")
    parser.add_argument("--model", default="models/ggml-medium.en.bin", required=True, help="Path to whisper model")

    args = parser.parse_args()
    
    # Create output directory in current working directory
    output_dir = os.path.join(os.getcwd(), args.work_path)
    logger.info(f"Output directory: {output_dir}")

    os.makedirs(output_dir, exist_ok=True)

    video_name = os.path.splitext(os.path.basename(args.input_video))[0]
    video_extension = os.path.splitext(os.path.basename(args.input_video))[1]
    logger.info(f"Prepare for processing video file: {video_name}.{video_extension}")

    try:
        # Extract audio from video file
        audio_path = extract_audio(args.input_video, output_dir)
        logger.info(f"Extracted audio saved to: {audio_path}")

        srt_path = transcribe_audio(audio_path, args.model)
        # Collect ASR data
        asr_data = ASRData.from_subtitle_file(srt_path)
        # asr_data.split_to_word_segments()
        asr_data = translate_subtitle(int(args.parallels_threads), asr_data)
        asr_data.remove_punctuation()

        translate_subtitle_path = os.path.join(output_dir, f"{video_name}_translated.ass")
        style_file = os.path.join(os.path.dirname(__file__), "resources", "default")
        with open(style_file, 'r', encoding='utf-8') as f:
            default_style = f.read()
            asr_data.save(
                save_path=translate_subtitle_path,
                layout="译文在上",
                ass_style=default_style
            )

        if args.output_video:
            combine_subtitles(args.input_video, translate_subtitle_path, args.output_video)
        else:
            combine_subtitles(args.input_video, translate_subtitle_path, os.path.join(output_dir, f"{video_name}_translated.{video_extension}"))
        
    except Exception as e:
        logging.error(f"Error: {e}")

if __name__ == "__main__":
    main()