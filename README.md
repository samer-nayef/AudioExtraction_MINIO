# Audio Extraction API for High-Quality Video Transcription

This project provides a **Tornado-based API** to extract audio from high-quality video files stored locally (from MinIO storage) and stream it directly to the caller. It is optimized for transcription tasks using models like Whisper, supporting both default compressed audio and lossless formats.  

---

## Features

- Extract audio from local videos without uploading back to MinIO  
- Default format: **MP3 320 kbps** (good balance between size and fidelity)  
- Optional formats: **WAV** or **FLAC** for maximum transcription accuracy  
- Streaming audio back directly to the caller without saving permanently  
- Prints for monitoring progress and logging errors only  
- Fully configurable via `config.cfg`  

---

## Requirements

- Python 3.8+  
- [Tornado](https://www.tornadoweb.org/)  
- [FFmpeg](https://ffmpeg.org/) installed and in PATH  
- Standard Python libraries: `asyncio`, `subprocess`, `configparser`, `logging`, `json`, `os`  

Install Tornado using pip:

```bash
pip install tornado
```
---
## Configuration

- Edit config.cfg to set paths and defaults:

```ini
[server]
host = 0.0.0.0
port = 8888

[paths]
temp_dir = /tmp
default_audio_format = mp3
minio_data_path = /data/minio
bucket_name = videos
```
## Config fields:

- temp_dir: temporary storage for audio extraction (deleted after processing)
- default_audio_format: default audio format (mp3)
- minio_data_path: local path where MinIO stores video files
- bucket_name: name of the MinIO bucket (used to construct full video path)

---

## Running the API

**Start the server:**
```bash
python api.py
```

**Console output example:**
```ini
[INFO] Tornado server running on http://0.0.0.0:8888
```
---
## Running as a Systemd Service

You can configure the API to run automatically as a systemd service. Example unit file:

**Path:** /usr/lib/systemd/system/audio-extraction_minio.service
```ini
[Unit]
Description=Audio Extraction From MINIO Service
After=network.target

[Service]
User=user9
WorkingDirectory=/path to project
ExecStart=/bin/bash -c 'source venv/bin/activate && python3 api.py'
Restart=always

[Install]
WantedBy=multi-user.target
```
**Enable and start the service:**
```ini
sudo systemctl daemon-reload
sudo systemctl enable audio-extraction_minio.service
sudo systemctl start audio-extraction_minio.service
sudo systemctl status audio-extraction_minio.service
```
---
## API Usage

**Endpoint:** /extract-audio

**Method:** POST

**Content-Type:** application/json

## Request Body
| Field          | Type   | Description                                                            | Default  |
| -------------- | ------ | ---------------------------------------------------------------------- | -------- |
| `savepath`     | string | Relative path of the video inside bucket, e.g., `"youtube/abc123.mp4"` | required |
| `audio_format` | string | Audio format to extract (`mp3`, `wav`, `flac`)                         | `mp3`    |




## Example - Default MP3
```bash
curl -X POST http://<machine-c>:8888/extract-audio \
-H "Content-Type: application/json" \
-d '{"savepath":"youtube/abc123.mp4"}' \
--output audio.mp3
```
## Example - High-Fidelity WAV
```bash
curl -X POST http://<machine-c>:8888/extract-audio \
-H "Content-Type: application/json" \
-d '{"savepath":"youtube/abc123.mp4","audio_format":"wav"}' \
--output audio.wav
```
---
## Behavior

- Progress prints: video path resolution, temp audio file creation, FFmpeg start/finish, bytes sent, temp cleanup
- Error logging: only logs errors to console
- Temporary files: automatically deleted after extraction
- Invalid formats: returns HTTP 400 error with allowed formats
- Missing video: returns HTTP 404 error
---
## Recommended Usage for TV-Quality Videos
| Format       | Notes                                         | Approx. Size per 1 hr |
| ------------ | --------------------------------------------- | --------------------- |
| MP3 320 kbps | Fast, small size, good transcription accuracy | ~70–80 MB             |
| WAV          | Maximum fidelity, uncompressed                | ~600–700 MB           |
| FLAC         | Maximum fidelity, compressed                  | ~100–200 MB           |

Avoid very low bitrate formats (<128 kbps MP3, AMR, GSM) as they degrade transcription accuracy
---
## Notes

- Ensure the FFmpeg executable is in the system PATH
- The API is optimized for streaming audio to transcription services like Whisper
- Works directly with local MinIO storage paths, no need for MinIO access keys
---

## Architecture Diagram
```ini
flowchart LR
    A[Machine A: Yaraa Service & PostgreSQL] -->|send savepath| B[Machine B: GPU Transcription]
    B -->|request audio| C[Machine C: MinIO Storage & Audio Extraction API]
    C -->|return audio bytes| B
    B -->|return transcription| A
```
## Flow Explanation:

1- Machine A sends the savepath of a video to Machine B (GPU)

2- Machine B calls the audio extraction API on Machine C, which reads the video file locally and streams back audio bytes

3- Machine B runs transcription on the received audio (e.g., Whisper) and returns the transcription to Machine A

---