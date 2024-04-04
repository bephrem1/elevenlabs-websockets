from pathlib import Path
import sys
import asyncio


def add_modules_to_path():
    # add root directory to sys.path to use modules in src
    root_dir = Path().absolute().parent.parent

    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))


add_modules_to_path()

from src.Environment import Environment

Environment.load()  # Load .env file data

from src.voicebox.Voicebox import Voicebox
from src.helpers.logging import LoggerFactory
from src.helpers.time import now_epoch_ms


logger = LoggerFactory.get_logger(namespace="tester", color="white")


#######   ——————————————————————   #######


async def main():
    """
    setup audio queue
    """
    audio_queue = asyncio.Queue()

    async def on_speech(base64_audio):
        await audio_queue.put(base64_audio)

    async def process_audio_queue():
        while True:
            # collect & play
            base64_audio = await audio_queue.get()
            Voicebox._play_base64_audio(base64_audio)

            # signal done
            audio_queue.task_done()

            await asyncio.sleep(0.010)  # 10ms

    # init
    voicebox = Voicebox(
        voice_id="21m00Tcm4TlvDq8ikWAM",  # Rachel
        on_speech=on_speech,
    )

    # prepare (inits voicebox async)
    voicebox.prepare(speech_generation_start_time=now_epoch_ms() / 1000)

    """
    wait for voicebox to become ready
    """
    while not voicebox.is_ready():
        await asyncio.sleep(0.010)  # 10ms

    """
    begin processing audio queue in background
    """
    asyncio.create_task(process_audio_queue())

    """
    feed speech chunked to voicebox
    """
    speech_chunks = [
        "hello",
        ",",
        "welcome",
        "to",
        "the",
        "demo",
        ".",
        "my",
        "name",
        "is",
        "ben!",
        "I",
        "'",
        "m",
        "glad",
        "you",
        "are",
        "visiting",
        ".",
    ]
    for speech_chunk in speech_chunks:
        await voicebox.feed_speech(speech_chunk)  # ingest speech chunk
    await voicebox.feeding_finished()
    logger.debug("all chunks fed")

    # wait for generation to complete
    while not voicebox.generation_complete():
        await asyncio.sleep(0.010)  # 10ms

    # reset
    await voicebox.reset()

    """
    even if generation is complete, allow the speech to finish playing.
    we do an arbitrary wait here. (may still clip)
    """
    await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(main())
