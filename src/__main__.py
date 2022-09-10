import logging

from .orbot import Orbot
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)

load_dotenv()

Orbot().run()
