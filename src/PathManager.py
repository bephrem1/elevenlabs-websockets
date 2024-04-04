from pathlib import Path

PROJECT_PATH = Path(__file__).resolve().parent.parent


class PathManager:
    @staticmethod
    def project_root_path() -> Path:
        return PROJECT_PATH

    @staticmethod
    def env_path() -> Path:
        return PROJECT_PATH / ".env"
