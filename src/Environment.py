import json
import os
from dotenv import load_dotenv
from src.PathManager import PathManager

required_keys = ["ENV", "ELEVENLABS_API_KEY"]


class Environment:
    @staticmethod
    def load():
        # load the environment variables from .env into os.environ
        if PathManager.env_path().exists():
            load_dotenv(dotenv_path=PathManager.env_path())

        # assert required environment variables are present
        missing_keys = [
            key
            for key in required_keys
            if key not in os.environ or os.environ[key] in [None, ""]
        ]
        if missing_keys:
            raise AssertionError(
                f"Required environment variables missing: {missing_keys}"
            )

    @staticmethod
    def get(key):
        if key in os.environ:
            return try_parse_json(os.environ[key])
        else:
            return None

    @classmethod
    def is_development(cls):
        return cls.get("ENV") in ["dev", "develop", "development"]

    @classmethod
    def is_staging(cls):
        return cls.get("ENV") == "staging"

    @classmethod
    def is_production(cls):
        return cls.get("ENV") in ["prod", "production"]


def try_parse_json(value):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value
