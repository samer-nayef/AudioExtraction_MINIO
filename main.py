# main.py (replace extract_audio_stream only)
import os
import asyncio
import logging
import tempfile
from minio import Minio
import subprocess
import configparser

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

cfg = configparser.ConfigParser()
cfg.read("config.cfg")

MINIO_HOST = cfg.get("minio", "host") + ':' + cfg.get("minio", "port")
MINIO_ACCESS_KEY = cfg.get("minio", "access_key")
MINIO_SECRET_KEY = cfg.get("minio", "secret_key")
MINIO_SECURE = False  # True if using HTTPS

MINIO_DATA_PATH = cfg.get("paths", "minio_data_path")

DEFAULT_AUDIO_FORMAT = "mp3"
ALLOWED_FORMATS = ["mp3", "wav", "flac"]

minio_client = Minio(
    MINIO_HOST,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE
)

async def extract_audio_stream(bucket_name: str, object_name: str, audio_format: str = DEFAULT_AUDIO_FORMAT, chunk_size: int = 64*1024):
    """
    Download video (possibly multiple segments) from MinIO, merge if needed, extract audio with FFmpeg, yield chunks.
    """
    if audio_format not in ALLOWED_FORMATS:
        raise ValueError(f"Invalid audio format '{audio_format}'. Allowed: {ALLOWED_FORMATS}")

    # --- Create temp working dir ---
    temp_dir = tempfile.mkdtemp(prefix="audio_extract_")
    print(f"[DEBUG] Temporary working dir: {temp_dir}")

    # --- Collect segments ---
    segments = [object_name]
    idx = 2
    while True:
        part_name = f"{object_name}.part{idx}"
        try:
            minio_client.stat_object(bucket_name, part_name)
            segments.append(part_name)
            idx += 1
        except Exception:
            break
    print(f"[DEBUG] Segments to merge: {segments}")

    segment_files = []
    # Download all segments
    for seg in segments:
        local_path = os.path.join(temp_dir, os.path.basename(seg))
        minio_client.fget_object(bucket_name, seg, local_path)
        segment_files.append(local_path)
        print(f"[DEBUG] Downloaded segment: {local_path}")

    # --- Merge segments if multiple ---
    if len(segment_files) > 1:
        concat_file = os.path.join(temp_dir, "concat.txt")
        with open(concat_file, "w") as f:
            for fpath in segment_files:
                f.write(f"file '{fpath}'\n")
        merged_path = os.path.join(temp_dir, "merged.mp4")
        ffmpeg_merge_cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            merged_path
        ]
        print(f"[DEBUG] Running FFmpeg merge: {' '.join(ffmpeg_merge_cmd)}")
        result = subprocess.run(ffmpeg_merge_cmd, capture_output=True)
        if result.returncode != 0:
            print(f"[ERROR] FFmpeg merge failed: {result.stderr.decode()}")
            raise Exception(f"FFmpeg merge failed: {result.stderr.decode()}")
        video_path = merged_path
        print(f"[INFO] Segments merged successfully: {video_path}")
    else:
        video_path = segment_files[0]

    # --- Extract audio and stream ---
    codec_map = {"mp3": "libmp3lame", "wav": "pcm_s16le", "flac": "flac"}
    codec = codec_map[audio_format]

    ffmpeg_stream_cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-i", video_path,
        "-vn",
        "-acodec", codec,
        "-f", audio_format,
        "pipe:1"
    ]
    print(f"[DEBUG] Running FFmpeg stream: {' '.join(ffmpeg_stream_cmd)}")

    process = await asyncio.create_subprocess_exec(
        *ffmpeg_stream_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    try:
        while True:
            chunk = await process.stdout.read(chunk_size)
            if not chunk:
                break
            yield chunk

        _, stderr = await process.communicate()
        if process.returncode != 0:
            print(f"[ERROR] FFmpeg stream error: {stderr.decode()}")
            raise Exception(f"FFmpeg failed: {stderr.decode()}")

    finally:
        # Clean up everything
        for fpath in segment_files:
            if os.path.exists(fpath):
                os.remove(fpath)
        if os.path.exists(video_path) and video_path not in segment_files:
            os.remove(video_path)
        os.rmdir(temp_dir)
        print(f"[DEBUG] Cleaned up temporary files: {temp_dir}")
