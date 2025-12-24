# api.py
import json
import configparser
import logging
import tornado.ioloop
import tornado.web
from main import extract_audio_stream

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

HOST = cfg.get("server", "host")
PORT = cfg.getint("server", "port")

MINIO_DATA_PATH = cfg.get("paths", "minio_data_path")
DEFAULT_AUDIO_FORMAT = cfg.get("paths", "default_audio_format", fallback="mp3")
DEFAULT_BUCKET_NAME = cfg.get("paths", "default_bucket_name", fallback="videos")
ALLOWED_FORMATS = ["mp3", "wav", "flac"]


class ExtractAudioHandler(tornado.web.RequestHandler):
    async def post(self):
        try:
            body = json.loads(self.request.body)
            video_path = body["video_path"]
            audio_format = body.get("audio_format", DEFAULT_AUDIO_FORMAT)
            bucket_name = body.get("bucket_name", DEFAULT_BUCKET_NAME)

            print(f"[INFO] Request received for bucket '{bucket_name}', video '{video_path}' with format '{audio_format}'")

            if audio_format not in ALLOWED_FORMATS:
                raise ValueError(f"Invalid audio format '{audio_format}'. Allowed: {ALLOWED_FORMATS}")

            self.set_header("Content-Type",
                            "audio/mpeg" if audio_format == "mp3" else f"audio/{audio_format}")
            self.set_header("Content-Disposition", f'attachment; filename="extracted.{audio_format}"')

            # Stream audio in chunks directly from FFmpeg
            async for chunk in extract_audio_stream(bucket_name, video_path, audio_format):
                self.write(chunk)
                await self.flush()

            print("[INFO] Audio stream finished sending")

        except FileNotFoundError as e:
            logging.error(str(e))
            self.set_status(404)
            self.write({"status": "error", "error": str(e)})

        except ValueError as e:
            logging.error(str(e))
            self.set_status(400)
            self.write({"status": "error", "error": str(e)})

        except Exception as e:
            logging.error(str(e))
            self.set_status(500)
            self.write({"status": "error", "error": str(e)})


def make_app():
    return tornado.web.Application([
        (r"/extract-audio", ExtractAudioHandler),
    ], autoreload=True)


if __name__ == "__main__":
    app = make_app()
    app.listen(PORT, address=HOST)
    print(f"[INFO] Tornado server running on http://{HOST}:{PORT}")
    tornado.ioloop.IOLoop.current().start()
