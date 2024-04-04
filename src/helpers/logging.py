import sys
from loguru import logger
from typing import List, Tuple


from src.helpers.strings import to_pascal_case
from src.helpers.time import now_epoch_ms


class LoggerFactory:
    _configured = False

    @staticmethod
    def get_logger(namespace: str, color: str = "blue"):
        # ensure logger is configured only on first retrieval
        if not LoggerFactory._configured:
            LoggerFactory._configure()

        return logger.bind(namespace=namespace, color=color)

    ########################
    # private methods
    ########################

    @staticmethod
    def _configure():
        if not LoggerFactory._configured:
            # remove all other handlers
            logger.remove()

            def custom_log_formatter(record):
                # time
                time_str = record["time"].strftime("%H:%M:%S")
                time = LoggerFactory._color_log(message=time_str, color="green")

                # log level
                log_level_str = record["level"].name.lower()
                log_level_color = LoggerFactory._get_log_level_color(
                    log_level=log_level_str
                )

                log_level = LoggerFactory._color_log(
                    message=log_level_str, color=log_level_color
                )

                # namespace
                namespace_str = record["extra"].get("namespace", "")
                namespace_str = to_pascal_case(s=namespace_str)

                namespace_color_str = record["extra"].get("color", "")

                namespace = LoggerFactory._color_log(
                    message=namespace_str, color=namespace_color_str
                )

                # message
                message = record["message"]
                if "{" in message:  # escape braces
                    message = message.replace("{", "{{").replace("}", "}}")

                return f"[{time}][{log_level}][{namespace}] {message}\n"

            logger.add(sys.stderr, format=custom_log_formatter)
            LoggerFactory._configured = True

    ########################
    # private helpers
    ########################

    @staticmethod
    def _color_log(message: str, color: str):
        if color == "green":
            return "\u001b[32m" + message + "\u001b[0m"
        elif color == "blue":
            return "\u001b[94m" + message + "\u001b[0m"
        elif color == "purple":
            return "\u001b[95m" + message + "\u001b[0m"
        elif color == "gray":
            return "\u001b[90m" + message + "\u001b[0m"
        elif color == "yellow":
            return "\u001b[33m" + message + "\u001b[0m"
        elif color == "red":
            return "\u001b[91m" + message + "\u001b[0m"
        elif color == "white":
            return "\u001b[37m" + message + "\u001b[0m"

        return message

    @staticmethod
    def _get_log_level_color(log_level: str = "info"):
        if log_level == "debug":
            return "gray"
        elif log_level == "info":
            return "blue"
        elif log_level == "success":
            return "green"
        elif log_level == "warning":
            return "yellow"
        elif log_level == "error" or log_level == "critical":
            return "red"

        return "blue"  # default to blue

    ########################
    # pre-baked logs
    ########################

    ttfs_latency_coloring = [
        ((0, 700), "green"),
        ((700, 1000), "yellow"),
        ((1000, 30000), "red"),
    ]
    white_latency_coloring = [
        ((0, 2147483647), "white"),
    ]

    """
    latency
    """

    @staticmethod
    def get_latency_log(
        *,
        prefix: str = None,
        base_time_s: float = None,
        base_time_ms: float = None,
        interval_coloring: List[Tuple[Tuple[int, int], str]] = white_latency_coloring,
    ) -> str:
        if base_time_s is None and base_time_ms is None:
            raise ("must provide either base_time_s or base_time_ms")

        if base_time_s is not None and base_time_ms is None:
            base_time_ms = base_time_s * 1000
        elif base_time_s is None and base_time_ms is not None:
            pass  # base_time_ms already set
        elif base_time_s is not None and base_time_ms is not None:
            pass  # will just use base_time_ms

        latency = round(now_epoch_ms() - base_time_ms)
        latency_color = LoggerFactory._get_latency_time_color(
            latency=latency, interval_coloring=interval_coloring
        )

        open_bracket = LoggerFactory._color_log(message="(", color="gray")
        if prefix is not None:
            prefix_log = LoggerFactory._color_log(message=f"{prefix}: ", color="gray")
        else:
            prefix_log = ""
        time_log_ms = LoggerFactory._color_log(
            message=f"{latency}", color=latency_color
        )
        ms_log = LoggerFactory._color_log(message=f"ms", color="gray")
        close_bracket = LoggerFactory._color_log(message=")", color="gray")

        return f"{open_bracket}{prefix_log}{time_log_ms}{ms_log}{close_bracket}"

    # helpers

    # [
    #   ((0, 700), "green"),
    #   ((700, 1000), "yellow"),
    #   ((1000, 30000), "red")
    # ]
    @staticmethod
    def _get_latency_time_color(
        latency: int, interval_coloring: List[Tuple[Tuple[int, int], str]]
    ) -> str:
        for interval, color in interval_coloring:
            if latency >= interval[0] and latency < interval[1]:
                return color

        return "red"
