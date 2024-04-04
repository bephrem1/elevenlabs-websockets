import websockets
import json
import base64
import time
import asyncio
import inspect
from pydub import AudioSegment
from pydub.playback import play
from typing import Callable, Any

from src.Environment import Environment
from src.helpers.logging import LoggerFactory
from src.helpers.concurrency.tasks import InterruptibleAsyncTask

# import logging
# logging.basicConfig(level=logging.DEBUG) # uncomment to log socket activity
logger = LoggerFactory.get_logger(namespace="voicebox", color="green")

elevenlabs_api_key = Environment.get("ELEVENLABS_API_KEY")
tts_model_id = "eleven_turbo_v2"
tts_options = {
    "optimize_streaming_latency": 4,  # 0-4, 4 is max latency optimizations
    "output_format": "pcm_44100",
}
voice_settings = {
    "stability": 0.5,
    "similarity_boost": 0.5,
    "style": 0,
    "use_speaker_boost": False,
}

"""
speech_base64: base64 string of audio
"""
OnSpeech = Callable[[str], Any]


class Voicebox:
    def __init__(self, voice_id: str, on_speech: OnSpeech = None):
        self.voice_id = voice_id
        self.on_speech = on_speech

        # internal
        ## websocket
        self._websocket = None
        self._sequence_start_sent = False
        self._listening = False
        self._first_speech_sent = False
        self._first_speech_received = False
        self._generation_complete = False

        ## tasks
        self._prepare_task: InterruptibleAsyncTask = None
        self._websocket_listen_task: InterruptibleAsyncTask = None

        ## timing
        self._speech_generation_start_time = None
        self._first_speech_packet_sent_time = None

    """
    api
    """

    # methods

    def prepare(self, speech_generation_start_time: float):
        if self.is_ready():
            logger.error("voicebox already prepared")

            return

        logger.debug("preparing voicebox")

        # reset connection vars
        self._reset_connection_state_vars()
        self._speech_generation_start_time = speech_generation_start_time

        async def _prepare_routine():
            await self._connect_to_websocket()  # connect to websocket

            # send beginning of sequence message
            logger.debug("initializing stream")
            await self._send_bos_payload()
            self._sequence_start_sent = True

            # start listening on socket (in background)
            self._listen_on_socket()

        # run voicebox prep async
        self._prepare_task = InterruptibleAsyncTask(target_fn=_prepare_routine)
        self._prepare_task.schedule()

    async def feed_speech(self, text: str):
        if not self.is_ready():

            def _get_reason():
                if not self._websocket_connected():
                    return "websocket not connected"
                if not self._sequence_start_sent:
                    return "sequence start not sent"
                if not self._is_listening():
                    return "not listening on socket"

            reason = _get_reason()
            logger.error(f"voicebox not ready for speech yet ({reason})")

            return

        await self._send_speech_chunk_payload(text=text)

        """
        clock first speech sent time
        """
        if not self._first_speech_sent:
            self._first_speech_sent = True
            self._first_speech_packet_sent_time = time.time()

    async def feeding_finished(self):
        if not self.is_ready():
            return

        await self._send_eos_payload()

    async def reset(self):
        logger.debug("◐ resetting voicebox")
        reset_start_time = time.time()

        if self._websocket_connected():
            await self._send_eos_payload()  # send closing packet

        if self._is_listening():
            await self._stop_listening_on_socket()  # stop listening
        if self._prepare_task:
            await self._prepare_task.interrupt()
            self._prepare_task = None

        if self._websocket_connected():
            await self._disconnect_from_websocket()  # close connection

        # reset connection vars
        self._reset_connection_state_vars()

        reset_time_ms = round((time.time() - reset_start_time) * 1000)
        logger.debug(f"● voicebox reset (total {reset_time_ms}ms)")

    # state

    """
    since prepare() is non-blocking, clients will have to repeatedly
    check is_ready() to see if the voicebox is ready for speech ingestion
    """

    def is_ready(self):
        return (
            self._websocket_connected()
            and self._sequence_start_sent
            and self._is_listening()
        )

    def generation_complete(self):
        return self._generation_complete

    ########################
    # websocket
    ########################

    # connection

    ## connection management

    ### connecting

    async def _connect_to_websocket(self):
        if self._websocket_connected():
            logger.error("socket already connected")

            return

        logger.debug("◐ connecting to ElevenLabs")
        connection_start_time = time.time()

        self.url = self._get_websocket_url()
        self._websocket = await websockets.connect(self.url)

        connection_time_ms_log = LoggerFactory.get_latency_log(
            prefix="in",
            base_time_s=connection_start_time,
            interval_coloring=[
                ((0, 300), "green"),
                ((300, 500), "yellow"),
                ((500, 1000), "red"),
            ],
        )
        logger.debug(f"● connected {connection_time_ms_log}")

    async def _disconnect_from_websocket(self):
        if not self._websocket_connected():
            logger.error("socket not connected")

            return

        logger.debug("◐ disconnecting from ElevenLabs")
        disconnect_start_time = time.time()

        await self._websocket.close()
        self._websocket = None

        disconnect_time_log = LoggerFactory.get_latency_log(
            prefix="in",
            base_time_s=disconnect_start_time,
            interval_coloring=[
                ((0, 100), "green"),
                ((100, 200), "yellow"),
                ((200, 1000), "red"),
            ],
        )
        logger.debug(f"● disconnected {disconnect_time_log}")

    ### listening

    def _listen_on_socket(self):
        if not self._websocket_connected():
            logger.error("socket not connected")

            return

        if self._is_listening():
            logger.error("already listening")

            return

        self._websocket_listen_task = InterruptibleAsyncTask(
            target_fn=self._listen_on_socket_routine
        )
        self._websocket_listen_task.schedule()

    async def _listen_on_socket_routine(self):
        logger.debug("((•)) listening for speech")
        self._listening = True

        while True:
            try:
                message = await self._websocket.recv()

                # parse payload
                data = json.loads(message)
                base64_audio = data.get("audio", None)
                is_final = data.get("is_final", False)

                """
                process audio
                """
                if base64_audio is not None:
                    """
                    clock first speech received time
                    """
                    if not self._first_speech_received:
                        totelap_log = LoggerFactory.get_latency_log(
                            prefix="totelap",
                            base_time_s=self._speech_generation_start_time,
                            interval_coloring=LoggerFactory.ttfs_latency_coloring,
                        )
                        first_generation_latency_log = LoggerFactory.get_latency_log(
                            prefix="fgl",
                            base_time_s=self._first_speech_packet_sent_time,
                            interval_coloring=[
                                ((0, 500), "green"),
                                ((500, 750), "yellow"),
                                ((750, 30000), "red"),
                            ],
                        )

                        logger.debug(
                            f"first speech received {totelap_log} {first_generation_latency_log}"
                        )
                        self._first_speech_received = True

                    """
                    call on_speech callback
                    """
                    if self.on_speech is not None:
                        if inspect.iscoroutinefunction(self.on_speech):
                            await self.on_speech(base64_audio)
                        else:
                            self.on_speech(base64_audio)

                """
                if final chunk, stop listening
                """
                is_final = data.get("isFinal", False)
                if is_final:
                    self._generation_complete = True
                    break
            except websockets.exceptions.ConnectionClosed as e:
                logger.error(f"connection closed while listening: {e}")

                return

            await asyncio.sleep(0.005)  # 5ms

    async def _stop_listening_on_socket(self):
        if not self._is_listening():
            return

        if self._websocket_listen_task:
            await self._websocket_listen_task.interrupt()
            self._websocket_listen_task = None

        self._listening = False

    ## connection state

    def _websocket_connected(self):
        return self._websocket is not None and self._websocket.open

    def _is_listening(self):
        return self._listening and self._websocket_listen_task is not None

    # packets

    ## sending

    async def _send_bos_payload(self):
        payload = self._bos_payload()

        await self._send_ws_payload(p=payload)

    async def _send_speech_chunk_payload(self, text: str):
        payload = self._speech_chunk_payload(text=text)

        await self._send_ws_payload(p=payload)

    async def _send_eos_payload(self):
        payload = self._eos_payload()

        await self._send_ws_payload(p=payload)

    async def _send_ws_payload(self, p: str):
        try:
            await self._websocket.send(p)
        except websockets.exceptions.ConnectionClosedError:
            """
            20s+ of inactivity will lead socket to close
            """
            logger.error(f"connection timed-out (closed)")

            return
        except websockets.exceptions.ConnectionClosedOK:
            """
            "end of sequence" (EOS) message will close the whole connection
            (be careful to not accidentally send it)
            """
            logger.error(
                f"connection is closed (w/ OK status) (did you close the connection by accident?)"
            )

            return

    ## payloads

    def _bos_payload(self) -> str:  # BOS → "beginning-of-sequence"
        return self._ws_payload(
            text=" ", include_voice_settings=True, include_generation_config=True
        )

    def _speech_chunk_payload(self, text: str) -> str:
        return self._ws_payload(text=text + " ", try_trigger_generation=True)

    def _eos_payload(self) -> str:  # EOS → "end-of-sequence"
        return self._ws_payload(text="")

    def _ws_payload(
        self,
        *,
        text: str = " ",
        try_trigger_generation: bool = False,
        flush: bool = None,
        include_voice_settings=False,
        include_generation_config=False,
    ):
        fields = {}
        if text is not None:
            fields["text"] = text
        if try_trigger_generation is not None:
            fields["try_trigger_generation"] = try_trigger_generation
        if flush is not None:
            fields["flush"] = flush

        if include_voice_settings:
            fields["voice_settings"] = voice_settings
        if include_generation_config:
            fields["generation_config"] = {}

            fields["generation_config"]["chunk_length_schedule"] = [50]

        return json.dumps(
            {
                **fields,
                "xi_api_key": elevenlabs_api_key,
            }
        )

    # url

    def _get_websocket_url(self):
        eleven_labs_websocket_url = "wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input?model_id={model_id}&optimize_streaming_latency={optimize_streaming_latency}&output_format={output_format}"

        return eleven_labs_websocket_url.format(
            model_id=tts_model_id,
            voice_id=self.voice_id,
            optimize_streaming_latency=tts_options["optimize_streaming_latency"],
            output_format=tts_options["output_format"],
        )

    # variables

    def _reset_connection_state_vars(self):
        self._websocket = None
        self._sequence_start_sent = False
        self._listening = False
        self._first_speech_sent = False
        self._first_speech_received = False
        self._generation_complete = False

        self._prepare_task = None
        self._websocket_listen_task = None

        self._speech_generation_start_time = None
        self._first_speech_packet_sent_time = None

    ########################
    # other
    ########################

    @staticmethod
    def _play_base64_audio(
        base64_audio: str, sample_rate=44100, channels=1, sample_width=2
    ):
        """
        default:
        - sample_rate: 44100 Hz
        - channels: 1 (mono)
        - sample_width: 2 bytes (16 bit) per sample
        """
        audio_bytes = base64.b64decode(base64_audio)
        audio = AudioSegment(
            data=audio_bytes,
            sample_width=sample_width,
            frame_rate=sample_rate,
            channels=channels,
        )

        play(audio)
