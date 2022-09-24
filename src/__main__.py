import logging

from dotenv import load_dotenv

from .orbot import Orbot

logging.basicConfig(level=logging.INFO)

load_dotenv()

Orbot().run()
