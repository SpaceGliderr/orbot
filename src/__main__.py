import logging

from .orbot import Orbot

logging.basicConfig(level=logging.INFO)

Orbot().run()
