# api.py
import json
import os
import asyncio
import configparser
import logging
import tornado.ioloop
import tornado.web
from main import extract_audio_bytes, DEFAULT_AUDIO_FORMAT, DEFAULT_BUCKET_NAME, ALLOWED_FORMATS

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


class ExtractAudioHandler(tornado.web.RequestHandler):
    async def post(self):
        try:
            body = json.loads(self.request.body)
            video_path = body["video_path"]
            audio_format = body.get("audio_format", DEFAULT_AUDIO_FORMAT)
            bucket_name = body.get("bucket_name", DEFAULT_BUCKET_NAME)

            print(f"[INFO] Extracting {audio_format} audio from bucket '{bucket_name}' video '{video_path}'")

            if audio_format not in ALLOWED_FORMATS:
                raise ValueError(f"Invalid audio format '{audio_format}'. Allowed: {ALLOWED_FORMATS}")

            # Extract audio fully into memory
            audio_bytes = await extract_audio_bytes(bucket_name, video_path, audio_format)

            print(f"[INFO] Sending audio back, size: {len(audio_bytes)/(1024*1024):.2f} MB")

            self.set_header("Content-Type",
                            "audio/mpeg" if audio_format == "mp3" else f"audio/{audio_format}")
            self.set_header("Content-Disposition", f'attachment; filename="extracted.{audio_format}"')

            # Stream the audio bytes in 4 MB chunks
            chunk_size = 8 * 1024 * 1024
            for i in range(0, len(audio_bytes), chunk_size):
                self.write(audio_bytes[i:i+chunk_size])
                await self.flush()

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
