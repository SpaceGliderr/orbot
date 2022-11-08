import logging

from dotenv import load_dotenv

from .orbot import client

logging.basicConfig(level=logging.INFO)

load_dotenv()

client.run()
