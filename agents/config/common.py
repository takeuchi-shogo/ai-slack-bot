import os

from dotenv import load_dotenv

load_dotenv()

SLACK_CHANNEL_IDS = os.getenv("SLACK_CHANNEL_IDS")
