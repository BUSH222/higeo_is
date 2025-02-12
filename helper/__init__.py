import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

DATABASE_NAME = os.environ.get("DATABASE_NAME")
DATABASE_HOST = os.environ.get("DATABASE_HOST")
DATABASE_PORT = os.environ.get("DATABASE_PORT")
DATABASE_USER = os.environ.get("DATABASE_USER")
DATABASE_PASSWORD = os.environ.get("DATABASE_PASSWORD")

GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_DISCOVERY_URL = os.environ.get("GOOGLE_DISCOVERY_URL")
