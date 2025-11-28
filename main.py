# main.py
import os
import asyncio
import configparser
import logging

# -----------------------
# Setup logging (errors only)
# -----------------------
logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# -----------------------
# Load config
# -----------------------
cfg = configparser.ConfigParser()
cfg.read("config.cfg")

MINIO_DATA_PATH = cfg.get("paths", "minio_data_path")
DEFAULT_AUDIO_FORMAT = cfg.get("paths", "default_audio_format", fallback="mp3")
DEFAULT_BUCKET_NAME = cfg.get("paths", "default_bucket_name", fallback="videos")
ALLOWED_FORMATS = ["mp3", "wav", "flac"]


async def extract_audio_bytes(bucket_name: str, video_path: str, audio_format: str = DEFAULT_AUDIO_FORMAT) -> bytes:
    """
    Extract audio from a video located in MinIO storage.
    Returns the full audio as bytes (in memory), no disk write.
    """
    if audio_format not in ALLOWED_FORMATS:
        raise ValueError(f"Invalid audio format '{audio_format}'. Allowed: {ALLOWED_FORMATS}")

    os_video_path = os.path.join(MINIO_DATA_PATH, bucket_name, video_path)
    print(f"[INFO] Video path resolved: {os_video_path}")

    if not os.path.exists(os_video_path):
        logging.error(f"Video file not found: {video_path}")
        raise FileNotFoundError(f"Video not found: {video_path}")

    video_minio_url = f'http://localhost:9001/api/v1/buckets/{bucket_name}/objects/download?prefix={video_path}&version_id=null'
    print(f'[INFO] Video MINIO URL resolved: {video_minio_url}')


    # FFmpeg codec mapping
    codec_map = {
        "mp3": "libmp3lame",
        "wav": "pcm_s16le",
        "flac": "flac"
    }
    codec = codec_map[audio_format]

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-i", video_minio_url,
        "-vn",
        "-acodec", codec,
        "-f", audio_format,
        "pipe:1"  # output to stdout
    ]

    print("[INFO] Running FFmpeg to extract full audio into memory...")
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    audio_bytes = bytearray()
    chunk_size = 8 * 1024 * 1024  # 4 MB
    while True:
        chunk = await process.stdout.read(chunk_size)
        if not chunk:
            break
        audio_bytes.extend(chunk)

    _, stderr = await process.communicate()
    if process.returncode != 0:
        logging.error(f"FFmpeg error: {stderr.decode()}")
        raise Exception(f"FFmpeg failed: {stderr.decode()}")

    print(f"[INFO] Audio extraction complete, size: {len(audio_bytes) / (1024*1024):.2f} MB")
    return bytes(audio_bytes)

