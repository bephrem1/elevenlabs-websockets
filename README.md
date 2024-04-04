# ElevenLabs WebSocket API Sample

A Python sample showcasing a complete server-side integration w/ the [ElevenLabs WebSockets API](https://elevenlabs.io/docs/api-reference/websockets).

## Running

### Setup

#### 0) clone + cd:

```
git clone https://github.com/bephrem1/elevenlabs-websockets.git
cd elevenlabs-websockets
```

#### 1) install dependencies:

```
pip install -r requirements.txt
```

### Run

#### 3) run in terminal

```
python3 src/testing/voicebox.py
```

### Inspecting

#### 4) inspect files

```
src/voicebox/Voicebox.py → has all socket-related logic
src/testing/voicebox.py → driver file
```

## Overview

The sample showcases a `Voicebox` class wrapping around the WebSocket functionality with a simple API:

actions:

- `prepare(speech_generation_start_time: float)` _(non-blocking)_: This will prepare & initialize the socket connection (async).
  - If you are streaming text from an LLM you'd fire `prepare()` before your LLM request so both TTS prep + LLM inference proceed concurrently.
  - The voicebox should be ready to ingest speech within `200-300ms` (before your LLM would get its first token back to you).
- `async` `feed_speech(text: str)`: Once a connection is open, you can feed speech over the socket. Feed a string of any size (from a single character to a full sentence).
- `async` `feeding_finished()`: Signal to the voicebox that it has received all speech & transmission is finished.
  - This is a mandatory step — although speech generations may continue to come back (even when you have no more to send), ElevenLabs requires that you let it know that further speech will not be sent & that the transmission is complete.
- `async` `reset()`: This will close the socket connection & reset the voicebox for the next speech generation to run.
  - This is a required step, socket connections cannot be reused (at the time of this sample's writing) or kept alive (default timeout is 20s)

state:

- `is_ready()`: Check if the voicebox is ready for speech transmission.
  - You would check this in a loop after firing off `prepare()` (since `prepare()` will not block).
- `generation_complete()`: Returns `true` when all speech has been received back from ElevenLabs.
  - You would check this in a loop after calling `feeding_finished()` to actually know when all speech has been generated & sent back to you.
  - You can then safely call `reset()` to prepare for the next generation.

<br>

---

<br>

Just wanted to publish this as a quick sample — forgive any rough edges on code formatting, etc.

<a href="https://www.buymeacoffee.com/bephrem" target="_blank">
  <img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy Me A Coffee" style="height: 41px !important;width: 174px !important;box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;"/>
</a>
