# Hoshi Companion — Local AI Gaming Friend (Windows 11)

Hoshi is a small, original anime-style voice companion you can run on your own PC. You select a game window; Hoshi can inspect periodic screenshots of that window, make occasional spoken comments, and answer questions you ask by microphone. Screen understanding, speech recognition, and speech output all run locally after the models are installed.

**Status:** working prototype source, version 0.2. The original build has been reported working on Windows 11 by its user, but this new neural-voice update has not yet been tested on that computer. It is not an installer or a compiled `.exe`.

### Updating an existing installation (v0.1 or v0.1.1 → v0.2)

1. Close Hoshi. Extract the updated ZIP into **the same folder where you installed it**, choosing **Replace** for the existing project files.
2. Do **not** delete the existing `.venv` folder, or your existing `hoshi_settings.json`.
3. Double-click **`setup_neural_voice_windows.bat`** once. It installs Kokoro in the existing `.venv` and downloads the offline voice model and voice styles (roughly 192 MB total).
4. Double-click **`run_windows.bat`**. In Voice, choose **Kokoro — Nicole (soft, low)**, select the new personality **Reserved medic (Kal'tsit-inspired)**, and click Preview.

No need to reinstall Python, Ollama, the game-vision model, or Whisper. If the neural setup isn't ready, Hoshi falls back to the previous Windows voice so the app remains usable.

## What you need

- Windows 11, ideally **16 GB RAM or more** (a local model plus a demanding game can use significant memory).
- [Python 3.11, 64-bit](https://www.python.org/downloads/) installed with the Python Launcher (`py`).
- [Ollama for Windows](https://ollama.com/download/windows), running on your PC.
- A microphone and speakers/headphones.
- Internet for the **initial setup and model downloads only**. After that, game screenshots and voice audio are handled locally.

The default local vision model is [`gemma3:4b`](https://ollama.com/library/gemma3), which understands images. The first voice conversation downloads the `base.en` Faster-Whisper model. That model is then cached locally. The first AI response may take a while, especially on a CPU-only computer.

## Install (one time)

1. Download and extract `Hoshi-Companion-v0.1.zip` into a normal folder, for example `Documents\Hoshi-Companion`.
2. Install Python 3.11 (64-bit) and Ollama using the links above.
3. Open Ollama and allow it to run locally.
4. Double-click **`setup_model_windows.bat`** to download the vision model (several GB), or open Command Prompt and run:

   ```powershell
   ollama pull gemma3:4b
   ```

5. Double-click **`install_windows.bat`**. This creates a project-local Python environment and installs the open-source dependencies.
6. Double-click **`setup_neural_voice_windows.bat`** to download the local speech model and voice styles.
7. Double-click **`run_windows.bat`** to start Hoshi in later sessions.

If Windows SmartScreen warns about `.bat` files, you can inspect their contents in Notepad before running them. Both scripts contain plain, readable commands. The scripts are not signed.

## How to use it

1. Launch your game in **windowed or borderless-windowed mode**. Some exclusive-fullscreen games do not allow screen capture.
2. In Hoshi, click **Refresh**, choose the specific game window, and click **Start watching**.
3. Switch back to your game. Hoshi checks for a screenshot every 15 seconds, and asks the local model if there's something worth commenting on no more often than once a minute by default. It may deliberately stay quiet.
4. Press **F8** once to start microphone recording, speak, and press **F8** again to send. Recording automatically ends after 20 seconds. Hoshi uses local speech recognition, then speaks its answer aloud.
5. Press **F9** anytime to stop screen watching, discard microphone recording, clear its last screenshot, and interrupt speech. You can also use the on-screen **PANIC STOP** button.

The microphone is **not always listening**: it records only between two F8 presses (or button clicks). Hotkeys may conflict with a game's controls; the on-screen buttons remain available if the keyboard listener does not work.

### Changing Hoshi's voice and personality (v0.2)

Hoshi has a **Personality** dropdown, a **Voice** dropdown, a **Preview** button, and a **Speaking speed** slider. Choose a personality and voice, click Preview, adjust speed, and preview again. Your choices are saved automatically in `hoshi_settings.json` beside the app; this contains no conversations or screenshots.

The new default combines a **Kal'tsit-inspired reserved medic personality** with a gentle, restrained synthetic female voice. That personality takes inspiration from an analytical, dry, quietly protective manner. It is **not an exact recreation of the Arknights character, specific dialogue, or a voice actor's performance**; Hoshi remains an original companion.

Available neural voice choices:

- **Nicole** — soft, lower, soothing (the default).
- **Sarah** — poised and composed.
- **Heart** — warm and gentle.
- **Kore** — clear and mature.

These options use the [Kokoro ONNX](https://github.com/thewh1teagle/kokoro-onnx) CPU neural speech model entirely offline after setup. The `fp16` model is about 164 MB and voice styles about 28 MB. You can still choose the original Windows system voice or a named `System.Speech` voice. Click Rescan to update the Windows list. Some systems expose only one or two voices through that older interface.

You can change the screenshot interval and comment cooldown before clicking Start. You can also enter a different **locally installed vision-capable** Ollama model name (such as `qwen3-vl:4b`, if your Ollama version supports it).

## Privacy controls and limitations

| Feature | v0.1 behavior |
| --- | --- |
| Screenshots | Captured only when your **selected game window is in the foreground**. Held in memory, not saved as files. |
| Alt-tab | New captures pause. The most recent frame is cleared once the app notices the game lost focus. |
| Uploads | Screenshots are sent only to `http://127.0.0.1:11434` on your own computer, not to a cloud AI endpoint. An HTTP proxy is explicitly disabled for this connection. |
| Microphone | Off except while you use F8. Audio is kept in memory and transcribed locally. |
| Text | The visible session log is in memory; it disappears when the application closes. No persistent memory or chat history yet. |
| Voice and personality preferences | The selected voice name, speaking rate, and personality are saved in a local `hoshi_settings.json` settings file. |
| Neural speech | Synthesized on your PC using Kokoro ONNX; the generated audio plays directly from memory. No cloud speech API or recorded voice clip is used. |
| Emergency stop | F9 disables new capture, ends microphone recording, clears the frame, terminates ongoing speech, and suppresses responses from prior sessions. |

**Important screen-capture caveat:** The prototype captures pixels in the selected game's client-area rectangle while the game is active. Notifications, overlays, or other content drawn over the game inside those bounds **may appear in a screenshot**. There is also a small focus-change race between checking the foreground window and capturing pixels. For your privacy, disable desktop notifications and avoid showing sensitive overlays while watching. This is not as strict as a dedicated Windows Graphics Capture source targeting a window.

Stopping does not retroactively cancel a local Ollama inference already in progress, although any late response is discarded. Ollama retains loaded models in RAM for a while. The application does not attempt to bypass anti-cheat or protected-screen systems, inject into games, read game memory, press gameplay keys, or evade capture restrictions.

On initial setup, Ollama, Faster-Whisper, and the Kokoro setup script download model weights from their providers. Your gameplay screenshots and microphone recordings are **not** part of those downloads. No speech content is transmitted to cloud APIs. To keep Ollama confined to your PC, don't set its `OLLAMA_HOST` environment variable to a public network interface.

**Neural voice performance:** Speech is generated on the CPU. Hoshi might take an extra second or two to begin speaking, depending on your computer and how busy the game is. F9 interrupts spoken playback and prevents late responses, but it cannot instantly abort an ONNX calculation already executing in a background thread.

## Common problems

**"Cannot reach local Ollama"**: Open Ollama and make sure `ollama list` in Command Prompt lists `gemma3:4b`. If not, run `ollama pull gemma3:4b`.

**"model not found"**: The model field must match an installed model name from `ollama list`. A text-only model will not understand screenshots.

**No microphone / recording error**: In Windows Settings → Privacy & security → Microphone, allow desktop applications to use your microphone, then check your selected input device.

**Still hearing the old Windows voice**: Run `setup_neural_voice_windows.bat`, and confirm that Voice is set to a **Kokoro** option. The app intentionally falls back to Windows speech if those local voice model files are missing or incomplete.

**Neural voice setup fails**: Ensure Windows has enough free space for around 200 MB of models and the additional Python packages. Run the setup script again. If a model download was interrupted, delete only the incomplete file inside the `voice_models` folder before retrying.

**No spoken audio**: Make sure your output device and Windows volume are working. Preview a voice. If Kokoro fails, Hoshi attempts the offline Windows voice fallback.

**Capture is black**: Try borderless/windowed mode. Some protected games and anti-cheat systems block capture; Hoshi does not circumvent them.

**It's too slow or stutters**: Increase the screenshot interval to 30–60 seconds and the comment gap to 90–180 seconds. Reduce game graphics if memory is tight. The included Whisper recognizer uses CPU by default.

**F8/F9 don't work**: They may be intercepted by the game or another program. Use the buttons in Hoshi; this may briefly switch focus away from your game.

## Project files

- `companion.py` — desktop UI, screen watcher, microphone and speech queues, profiles, emergency stop.
- `neural_voice.py` — local Kokoro model loading, voice choices, and neural speech settings.
- `windows_capture.py` — enumeration and foreground checks for Windows windows, memory-only screenshot capture.
- `companion_core.py` — local Ollama client, response formatting, prompts, capture decision.
- `requirements.txt` — Python packages.
- `install_windows.bat`, `run_windows.bat`, `setup_model_windows.bat`, `setup_neural_voice_windows.bat` — readable Windows commands.
- `tests/test_core.py` — automated tests for privacy gating, prompts, and local-model requests.

To run the available tests from the project folder:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Next versions

Planned options after validating v0.2 on your PC: an animated original character avatar, optional game-state memory, lower-latency vision processing, optional TTS streaming, and tighter per-window capture using the Windows Graphics Capture API.
