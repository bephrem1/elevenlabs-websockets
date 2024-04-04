import time


def now_epoch_ms() -> int:
    return int(time.time() * 1000)
