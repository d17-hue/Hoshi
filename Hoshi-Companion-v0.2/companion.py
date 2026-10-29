"""Hoshi Companion v0.2 — local, permission-first Windows gaming companion."""

from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import scrolledtext, ttk

from companion_core import (
    DEFAULT_MODEL,
    LocalModelError,
    OllamaClient,
    PROFILE_HOSHI,
    PROFILE_RESERVED,
    conversation_prompt,
    observation_prompt,
)
from neural_voice import NEURAL_NICOLE, NEURAL_VOICES, LocalNeuralVoice, models_ready
import windows_capture


BG = "#101321"
PANEL = "#1b2031"
FG = "#f2f2ff"
MUTED = "#a6aec4"
ACCENT = "#b8a0ff"
SUCCESS = "#91e6c5"
VOICE_AUTO = "Auto (female voice — original)"
VOICE_DEFAULT = "Windows default voice"


class HoshiApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Hoshi Companion — local gaming friend")
        root.geometry("925x835")
        root.minsize(720, 695)
        root.configure(bg=BG)

        self.lock = threading.RLock()
        self.model_lock = threading.Lock()
        self.shutdown = threading.Event()
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.speech_queue: queue.Queue[tuple[int, str, str, int, int]] = queue.Queue()
        self.whisper_lock = threading.Lock()
        self.whisper_model = None

        self.epoch = 0
        self.watching = False
        self.recording = False
        self.voice_busy = False
        self.target_hwnd: int | None = None
        self.target_title = ""
        self.interval = 15
        self.cooldown = 60
        self.model_name = DEFAULT_MODEL
        self.last_frame: tuple[bytes, float] | None = None
        self.last_observation_at = 0.0
        self.audio_stream = None
        self.audio_chunks = []
        self.mic_started = 0.0
        self.mic_generation = 0
        self.hotkeys_held = set()
        self.speech_process: subprocess.Popen | None = None
        self.window_options: list[tuple[int, str]] = []
        self.hotkey_listener = None
        self.speech_serial = 0
        self.speech_playing = False
        self.neural_engine: LocalNeuralVoice | None = None
        self.warned_missing_neural = False
        self.settings_path = Path(__file__).with_name("hoshi_settings.json")
        voice_settings = self._load_voice_settings()
        previous_voice = voice_settings.get("voice", VOICE_AUTO)
        # Migrate the original default Windows voice to the new offline voice.
        self.selected_voice = (
            NEURAL_NICOLE if previous_voice == VOICE_AUTO else str(previous_voice)
        )
        self.profile = str(voice_settings.get("profile", PROFILE_RESERVED))
        if self.profile not in {PROFILE_HOSHI, PROFILE_RESERVED}:
            self.profile = PROFILE_RESERVED
        try:
            self.speech_rate = max(-4, min(5, int(voice_settings.get("rate", -2))))
        except (TypeError, ValueError):
            self.speech_rate = 1

        self.model_var = tk.StringVar(value=DEFAULT_MODEL)
        self.interval_var = tk.StringVar(value="15")
        self.cooldown_var = tk.StringVar(value="60")
        self.status_var = tk.StringVar(value="Stopped. Nothing is being captured.")
        self.voice_var = tk.StringVar(value=self.selected_voice)
        self.profile_var = tk.StringVar(value=self.profile)
        self.speech_rate_var = tk.IntVar(value=self.speech_rate)

        self._build_ui()
        self.refresh_windows()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(100, self._drain_events)

        threading.Thread(target=self._watch_loop, daemon=True, name="hoshi-screen").start()
        threading.Thread(target=self._speech_loop, daemon=True, name="hoshi-voice").start()
        self._start_hotkeys()
        self.detect_voices()
        if not models_ready():
            self._log("For natural Kokoro voices, run setup_neural_voice_windows.bat once. "
                      "Until then, voice playback uses a Windows fallback.")

    def _load_voice_settings(self) -> dict:
        try:
            value = json.loads(self.settings_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_voice_settings(self) -> None:
        # Only a voice name and speed, never audio or gameplay, are written.
        try:
            payload = {"voice": self.selected_voice, "rate": self.speech_rate,
                       "profile": self.profile}
            self.settings_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as exc:
            if hasattr(self, "log_widget"):
                self._log(f"Could not save voice preference: {exc}")

    def _build_ui(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Hoshi.TCombobox", fieldbackground=PANEL, background=PANEL, foreground=FG)
        style.map("Hoshi.TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", FG)])

        header = tk.Frame(self.root, bg=BG, padx=22, pady=14)
        header.pack(fill="x")
        tk.Label(header, text="✦  HOSHI", fg=ACCENT, bg=BG,
                 font=("Segoe UI", 25, "bold")).pack(anchor="w")
        tk.Label(header, text="Your private, local anime-style gaming companion · Version 0.2",
                 fg=MUTED, bg=BG, font=("Segoe UI", 10)).pack(anchor="w")

        main = tk.Frame(self.root, bg=PANEL, padx=18, pady=15)
        main.pack(fill="x", padx=20, pady=(0, 12))
        tk.Label(main, text="1. CHOOSE THE GAME WINDOW", fg=ACCENT, bg=PANEL,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        select_row = tk.Frame(main, bg=PANEL)
        select_row.pack(fill="x", pady=(6, 13))
        self.window_combo = ttk.Combobox(select_row, state="readonly", style="Hoshi.TCombobox",
                                         font=("Segoe UI", 10))
        self.window_combo.pack(side="left", fill="x", expand=True, padx=(0, 9))
        self._button(select_row, "Refresh", self.refresh_windows, neutral=True).pack(side="left")

        settings = tk.Frame(main, bg=PANEL)
        settings.pack(fill="x")
        for label, var, width in [
            ("Local Ollama model", self.model_var, 17),
            ("Screenshot interval (sec)", self.interval_var, 6),
            ("Minimum comment gap (sec)", self.cooldown_var, 6),
        ]:
            cell = tk.Frame(settings, bg=PANEL)
            cell.pack(side="left", padx=(0, 22))
            tk.Label(cell, text=label, bg=PANEL, fg=MUTED,
                     font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 4))
            tk.Entry(cell, textvariable=var, width=width, bg=BG, fg=FG,
                     insertbackground=FG, relief="flat", font=("Consolas", 10),
                     highlightthickness=1, highlightbackground="#3e455d").pack(anchor="w", ipady=5)

        watch_row = tk.Frame(main, bg=PANEL)
        watch_row.pack(fill="x", pady=(17, 4))
        self._button(watch_row, "▶  Start watching", self.start_watching).pack(side="left", padx=(0, 9))
        self._button(watch_row, "■  Stop watching", self.stop_watching, neutral=True).pack(side="left", padx=(0, 9))
        self._button(watch_row, "F9  PANIC STOP", self.stop_everything, danger=True).pack(side="left")

        speech = tk.Frame(self.root, bg=PANEL, padx=18, pady=14)
        speech.pack(fill="x", padx=20, pady=(0, 12))
        tk.Label(speech, text="2. SPEAK TO HOSHI", fg=ACCENT, bg=PANEL,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(speech,
                 text="Press F8 once to start microphone recording; press F8 again to send. "
                      "Or use the button below. Maximum 20 seconds.",
                 fg=MUTED, bg=PANEL, wraplength=820, justify="left",
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(5, 10))
        self.talk_button = self._button(speech, "🎙  Start talking (F8)", self.toggle_talk)
        self.talk_button.pack(anchor="w")

        profile_row = tk.Frame(speech, bg=PANEL)
        profile_row.pack(fill="x", pady=(12, 0))
        tk.Label(profile_row, text="PERSONALITY", fg=ACCENT, bg=PANEL,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 9))
        self.profile_combo = ttk.Combobox(
            profile_row, state="readonly", textvariable=self.profile_var,
            style="Hoshi.TCombobox", font=("Segoe UI", 10),
            values=[PROFILE_RESERVED, PROFILE_HOSHI], width=38,
        )
        self.profile_combo.pack(side="left")
        self.profile_combo.bind("<<ComboboxSelected>>", self._profile_selected)

        voices_row = tk.Frame(speech, bg=PANEL)
        voices_row.pack(fill="x", pady=(13, 0))
        tk.Label(voices_row, text="VOICE", fg=ACCENT, bg=PANEL,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 9))
        self.voice_combo = ttk.Combobox(
            voices_row, state="readonly", textvariable=self.voice_var,
            style="Hoshi.TCombobox", font=("Segoe UI", 10),
            values=list(NEURAL_VOICES) + [VOICE_AUTO, VOICE_DEFAULT], width=38,
        )
        self.voice_combo.pack(side="left", padx=(0, 9))
        self.voice_combo.bind("<<ComboboxSelected>>", self._voice_selected)
        self._button(voices_row, "▶ Preview", self.preview_voice, neutral=True).pack(side="left", padx=(0, 9))
        self._button(voices_row, "Rescan", self.detect_voices, neutral=True).pack(side="left")

        speed_row = tk.Frame(speech, bg=PANEL)
        speed_row.pack(fill="x", pady=(8, 0))
        tk.Label(speed_row, text="Speaking speed", fg=MUTED, bg=PANEL,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 8))
        tk.Scale(speed_row, from_=-4, to=5, orient="horizontal", resolution=1,
                 variable=self.speech_rate_var, command=self._rate_selected,
                 showvalue=True, length=220, bg=PANEL, fg=FG,
                 activebackground=ACCENT, highlightthickness=0,
                 troughcolor=BG).pack(side="left")

        status_box = tk.Frame(self.root, bg=BG, padx=23, pady=3)
        status_box.pack(fill="x")
        tk.Label(status_box, textvariable=self.status_var, fg=SUCCESS, bg=BG,
                 wraplength=820, anchor="w", justify="left",
                 font=("Segoe UI", 10, "bold")).pack(fill="x")

        transcript = tk.Frame(self.root, bg=PANEL, padx=14, pady=12)
        transcript.pack(fill="both", expand=True, padx=20, pady=(10, 16))
        top = tk.Frame(transcript, bg=PANEL)
        top.pack(fill="x", pady=(0, 8))
        tk.Label(top, text="SESSION ACTIVITY (not saved)", fg=ACCENT, bg=PANEL,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        self._button(top, "Clear text", self.clear_log, neutral=True).pack(side="right")
        self.log_widget = scrolledtext.ScrolledText(
            transcript, bg=BG, fg=FG, insertbackground=FG, relief="flat", wrap="word",
            font=("Segoe UI", 10), state="disabled", padx=12, pady=10,
        )
        self.log_widget.pack(fill="both", expand=True)
        self._log("Hoshi is offline until you start watching or ask a question.")
        self._log("No screen images, microphone audio, or transcripts are written to files.")

    def _button(self, parent, label: str, command, neutral=False, danger=False):
        bg = "#9c496c" if danger else ("#343a51" if neutral else "#7960bc")
        return tk.Button(parent, text=label, command=command, bg=bg, fg="white",
                         activebackground=ACCENT, activeforeground=BG,
                         relief="flat", borderwidth=0, padx=14, pady=9,
                         font=("Segoe UI", 9, "bold"), cursor="hand2")

    def _log(self, message: str) -> None:
        self.log_widget.config(state="normal")
        stamp = time.strftime("%H:%M:%S")
        self.log_widget.insert("end", f"[{stamp}] {message}\n")
        self.log_widget.see("end")
        self.log_widget.config(state="disabled")

    def clear_log(self) -> None:
        self.log_widget.config(state="normal")
        self.log_widget.delete("1.0", "end")
        self.log_widget.config(state="disabled")

    def _post(self, kind: str, message: str) -> None:
        if not self.shutdown.is_set():
            self.events.put((kind, message))

    def _drain_events(self) -> None:
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "log":
                    self._log(value)
                elif kind == "status":
                    self.status_var.set(value)
                elif kind == "hotkey":
                    if value == "F8":
                        self.toggle_talk()
                    elif value == "F9":
                        self.stop_everything()
                elif kind == "voices":
                    found = json.loads(value)
                    values = list(NEURAL_VOICES) + [VOICE_AUTO, VOICE_DEFAULT] + found
                    self.voice_combo["values"] = values
                    if self.selected_voice not in values:
                        self.selected_voice = NEURAL_NICOLE
                        self._save_voice_settings()
                        self._log("Previous voice unavailable; selecting Kokoro Nicole.")
                    self.voice_var.set(self.selected_voice)
                    self._log(f"Found {len(found)} installed Windows voice(s), plus four Kokoro options.")
        except queue.Empty:
            pass
        if not self.shutdown.is_set():
            self.root.after(100, self._drain_events)

    def refresh_windows(self) -> None:
        current = self.window_combo.get()
        try:
            self.window_options = windows_capture.enumerate_windows()
            choices = [f"{title[:85]}  [0x{hwnd:x}]" for hwnd, title in self.window_options]
            self.window_combo["values"] = choices
            if current in choices:
                self.window_combo.set(current)
            elif choices:
                self.window_combo.current(0)
            else:
                self.window_combo.set("")
                self._log("No windows found. Open your game and click Refresh.")
        except Exception as exc:
            self._log(f"Could not list windows: {exc}")

    def detect_voices(self) -> None:
        self._log("Checking installed Windows speech voices…")

        def query() -> None:
            script = (
                "Add-Type -AssemblyName System.Speech; "
                "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
                "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                "$s.GetInstalledVoices() | Where-Object { $_.Enabled } | "
                "ForEach-Object { $_.VoiceInfo.Name }"
            )
            try:
                result = subprocess.run(
                    ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                    encoding="utf-8", errors="replace", timeout=20,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if result.returncode:
                    self._post("log", "Voice scan failed: " + result.stderr[:250])
                    return
                names = [x.strip().lstrip("\ufeff") for x in result.stdout.splitlines() if x.strip()]
                self._post("voices", json.dumps(names))
            except Exception as exc:
                self._post("log", f"Voice scan failed: {exc}")

        threading.Thread(target=query, daemon=True, name="hoshi-voice-scan").start()

    def _voice_selected(self, unused=None) -> None:
        with self.lock:
            self.selected_voice = self.voice_var.get()
        self._save_voice_settings()

    def _profile_selected(self, unused=None) -> None:
        with self.lock:
            self.profile = self.profile_var.get()
        self._save_voice_settings()
        self._log("Personality set to: " + self.profile)

    def _rate_selected(self, unused=None) -> None:
        with self.lock:
            self.speech_rate = int(self.speech_rate_var.get())
        self._save_voice_settings()

    def preview_voice(self) -> None:
        self._kill_speech()
        self._log("Previewing the selected voice (offline).")
        sample = (
            "You appear to be doing well. Try not to let that make you careless. "
            "I'll be here if you need assistance."
            if self.profile == PROFILE_RESERVED else
            "Hey! I'm Hoshi, your gaming buddy. Ready to win this together?"
        )
        self._queue_speech(self.epoch, sample)

    def _queue_speech(self, epoch: int, message: str) -> None:
        with self.lock:
            self.speech_queue.put((epoch, message, self.selected_voice,
                                   self.speech_rate, self.speech_serial))

    def start_watching(self) -> None:
        index = self.window_combo.current()
        if index < 0 or index >= len(self.window_options):
            self._log("Choose a game window before starting.")
            return
        try:
            interval = max(5, min(120, int(self.interval_var.get())))
            cooldown = max(20, min(600, int(self.cooldown_var.get())))
        except ValueError:
            self._log("Intervals must be whole numbers. Suggested values: 15 and 60.")
            return
        model = self.model_var.get().strip()
        if not model:
            self._log("Enter a local Ollama model name, such as gemma3:4b.")
            return
        hwnd, title = self.window_options[index]
        with self.lock:
            self.epoch += 1
            self.target_hwnd = hwnd
            self.target_title = title
            self.model_name = model
            self.interval = interval
            self.cooldown = cooldown
            self.last_frame = None
            self.last_observation_at = 0
            self.watching = True
        self._log(f"Watching armed for: {title}. Only runs while this game has focus.")
        self.status_var.set("Armed. Switch to your game to start local screen analysis.")

    def stop_watching(self) -> None:
        with self.lock:
            self.watching = False
            self.epoch += 1
            self.last_frame = None
        self._log("Screen watching stopped. Last screenshot cleared from memory.")
        self.status_var.set("Screen watching stopped. Microphone is separately controlled by F8.")

    def _watch_loop(self) -> None:
        last_status = ""
        while not self.shutdown.wait(0.3):
            with self.lock:
                watching = self.watching
                epoch = self.epoch
                hwnd = self.target_hwnd
                title = self.target_title
                interval = self.interval
                cooldown = self.cooldown
                model = self.model_name
                profile = self.profile
                voice_busy = self.voice_busy or self.recording or self.speech_playing
                elapsed = time.monotonic() - self.last_observation_at
            if not watching or not hwnd:
                last_status = ""
                continue

            if not windows_capture.is_selected_game_active(hwnd, title):
                with self.lock:
                    self.last_frame = None
                status = "Paused: selected game is not the active window. No capture."
                if status != last_status:
                    self._post("status", status)
                    last_status = status
                self.shutdown.wait(0.65)
                continue

            status = "Watching selected game · local processing only · F8 talk · F9 stop"
            if last_status != status:
                self._post("status", status)
                last_status = status
            try:
                frame = windows_capture.capture_foreground_game(hwnd, title)
            except Exception as exc:
                self._post("log", f"Screen capture failed: {exc}")
                self.shutdown.wait(3)
                continue
            if frame is None:
                self.shutdown.wait(0.5)
                continue
            with self.lock:
                if self.epoch != epoch or not self.watching:
                    continue
                self.last_frame = (frame, time.monotonic())

            if not voice_busy and elapsed >= cooldown and self.model_lock.acquire(blocking=False):
                try:
                    # Recheck permission immediately before sending to the local model.
                    with self.lock:
                        still_ok = self.epoch == epoch and self.watching and not self.recording
                    if still_ok and windows_capture.is_selected_game_active(hwnd, title):
                        answer = OllamaClient(model).generate(observation_prompt(profile), frame)
                        with self.lock:
                            if self.epoch == epoch:
                                self.last_observation_at = time.monotonic()
                            permitted = self.epoch == epoch and self.watching and not self.recording
                        if answer and permitted and windows_capture.is_selected_game_active(hwnd, title):
                            self._post("log", f"Hoshi: {answer}")
                            self._queue_speech(epoch, answer)
                except LocalModelError as exc:
                    self._post("log", f"Local AI error: {exc}")
                    with self.lock:
                        self.last_observation_at = time.monotonic()
                except Exception as exc:
                    self._post("log", f"Screen analysis error: {exc}")
                finally:
                    self.model_lock.release()
            self.shutdown.wait(interval)

    def _start_hotkeys(self) -> None:
        try:
            from pynput import keyboard

            def on_press(key) -> None:
                # pynput can report held keys repeatedly: toggle just once.
                if key in self.hotkeys_held:
                    return
                if key == keyboard.Key.f8:
                    self.hotkeys_held.add(key)
                    self._post("hotkey", "F8")
                elif key == keyboard.Key.f9:
                    self.hotkeys_held.add(key)
                    self._post("hotkey", "F9")

            def on_release(key) -> None:
                self.hotkeys_held.discard(key)

            self.hotkey_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            self.hotkey_listener.daemon = True
            self.hotkey_listener.start()
            self._log("Global hotkeys enabled: F8 record/send; F9 emergency stop.")
        except Exception as exc:
            self._log(f"Global hotkeys unavailable ({exc}). Use the on-screen buttons.")

    def toggle_talk(self) -> None:
        with self.lock:
            recording = self.recording
        if recording:
            self._end_recording(discard=False)
        else:
            self._begin_recording()

    def _begin_recording(self) -> None:
        import sounddevice as sd

        self._kill_speech()
        with self.lock:
            if self.recording:
                return
            self.audio_chunks = []
            self.recording = True
            self.voice_busy = True
            self.mic_generation += 1
            generation = self.mic_generation
            self.mic_started = time.monotonic()

        def receive(indata, frames, time_info, status):
            if status:
                self._post("log", f"Mic status: {status}")
            with self.lock:
                if self.recording and self.mic_generation == generation:
                    self.audio_chunks.append(indata[:, 0].copy())

        try:
            stream = sd.InputStream(samplerate=16000, channels=1, dtype="float32", callback=receive)
            stream.start()
            self.audio_stream = stream
        except Exception as exc:
            with self.lock:
                self.recording = False
                self.voice_busy = False
            self._log(f"Microphone couldn't start: {exc}. Check Windows microphone permissions.")
            return
        self.talk_button.config(text="■  Stop & send (F8)", bg="#b94d80")
        self.status_var.set("Microphone recording locally. Press F8 again to send (20s maximum).")
        self.root.after(20000, lambda: self._auto_end_recording(generation))

    def _auto_end_recording(self, generation: int) -> None:
        with self.lock:
            current = self.recording and generation == self.mic_generation
        if current:
            self._end_recording(discard=False)

    def _end_recording(self, discard: bool) -> None:
        import numpy as np

        with self.lock:
            if not self.recording:
                return
            self.recording = False
            recorded_at = self.mic_started
            epoch = self.epoch
        stream, self.audio_stream = self.audio_stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception as exc:
                self._log(f"Mic shutdown note: {exc}")
        with self.lock:
            chunks, self.audio_chunks = self.audio_chunks, []
            generation = self.mic_generation
            if discard:
                self.voice_busy = False
        self.talk_button.config(text="🎙  Start talking (F8)", bg="#7960bc")
        if discard:
            self._log("Microphone recording discarded.")
            return
        if not chunks or time.monotonic() - recorded_at < 0.4:
            with self.lock:
                self.voice_busy = False
            self._log("Recording was too short. Try speaking for at least a second.")
            return
        audio = np.concatenate(chunks).astype(np.float32)
        self.status_var.set("Transcribing speech locally; first use may download Whisper weights…")
        threading.Thread(target=self._answer_voice, args=(audio, epoch, generation),
                         daemon=True, name="hoshi-transcription").start()

    def _answer_voice(self, audio, epoch: int, generation: int) -> None:
        try:
            from faster_whisper import WhisperModel

            with self.whisper_lock:
                if self.whisper_model is None:
                    self._post("log", "Loading offline Whisper speech recognition (base.en, CPU)…")
                    self.whisper_model = WhisperModel("base.en", device="cpu", compute_type="int8")
                model = self.whisper_model

            segments, _ = model.transcribe(audio, language="en", beam_size=1,
                                           vad_filter=True, condition_on_previous_text=False)
            said = " ".join(segment.text.strip() for segment in segments).strip()
            if not self._job_current(epoch, generation):
                return
            if not said:
                self._post("log", "Didn't hear clear speech. Try again closer to the microphone.")
                return
            self._post("log", f"You: {said}")
            self._post("status", "Thinking locally…")

            with self.lock:
                frame = self.last_frame
                watching = self.watching
                target = self.target_hwnd
                title = self.target_title
                model_name = self.model_name
                profile = self.profile
            # Never use an image from a previous session, or a stale game image.
            screenshot = None
            if (watching and frame and time.monotonic() - frame[1] < 40
                    and windows_capture.is_selected_game_active(target, title)):
                screenshot = frame[0]

            with self.model_lock:
                if not self._job_current(epoch, generation):
                    return
                reply = OllamaClient(model_name).generate(conversation_prompt(said, profile), screenshot)
            if reply:
                with self.lock:
                    if (not self.shutdown.is_set() and epoch == self.epoch
                            and generation == self.mic_generation and not self.recording):
                        self._post("log", f"Hoshi: {reply}")
                        self._queue_speech(epoch, reply)
        except LocalModelError as exc:
            self._post("log", f"Local AI error: {exc}")
        except Exception as exc:
            self._post("log", f"Voice conversation error: {exc}")
        finally:
            with self.lock:
                if generation == self.mic_generation and not self.recording:
                    self.voice_busy = False
            if self._job_current(epoch, generation):
                self._post("status", "Ready. F8 to talk; F9 to stop everything.")

    def _epoch_current(self, epoch: int) -> bool:
        with self.lock:
            return not self.shutdown.is_set() and epoch == self.epoch

    def _job_current(self, epoch: int, generation: int) -> bool:
        with self.lock:
            return (not self.shutdown.is_set() and epoch == self.epoch
                    and generation == self.mic_generation)

    def _speech_request_current(self, epoch: int, serial: int) -> bool:
        with self.lock:
            return (not self.shutdown.is_set() and epoch == self.epoch
                    and serial == self.speech_serial)

    def _speech_loop(self) -> None:
        # The chosen local speech engine owns this dedicated worker thread.
        # The Windows fallback receives all text and voice settings via JSON stdin.
        powershell = (
            "Add-Type -AssemblyName System.Speech; "
            "[Console]::InputEncoding = [System.Text.Encoding]::UTF8; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$p = [Console]::In.ReadToEnd() | ConvertFrom-Json; "
            "if ($p.voice -eq 'auto_female') { "
            "try { $s.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::Female) } catch {} "
            "} elseif ($p.voice -ne 'default') { $s.SelectVoice([string]$p.voice) }; "
            "$s.Rate = [int]$p.rate; "
            "if (-not [string]::IsNullOrWhiteSpace($p.text)) { $s.Speak([string]$p.text) }"
        )
        while not self.shutdown.is_set():
            try:
                epoch, reply, voice, rate, serial = self.speech_queue.get(timeout=0.25)
            except queue.Empty:
                continue
            if not self._speech_request_current(epoch, serial):
                continue
            with self.lock:
                self.speech_playing = True
            try:
                if voice in NEURAL_VOICES and models_ready():
                    try:
                        if self.neural_engine is None:
                            self._post("log", "Loading Kokoro's offline neural voice…")
                            self.neural_engine = LocalNeuralVoice()
                        samples, sample_rate = self.neural_engine.create(reply, voice, rate)
                        import sounddevice as sd

                        with self.lock:
                            if not self._speech_request_current(epoch, serial):
                                continue
                            sd.play(samples, sample_rate)
                        sd.wait()
                        continue
                    except Exception as exc:
                        if not self._speech_request_current(epoch, serial):
                            continue
                        self._post("log", f"Kokoro voice failed ({exc}). Using Windows fallback.")
                        self.neural_engine = None

                if voice in NEURAL_VOICES:
                    if not models_ready() and not self.warned_missing_neural:
                        self._post("log", "Natural voice isn't installed yet. Run "
                                   "setup_neural_voice_windows.bat once. Using Windows for now.")
                        self.warned_missing_neural = True
                    voice = VOICE_AUTO

                if not self._speech_request_current(epoch, serial):
                    continue
                voice_option = (
                    "auto_female" if voice == VOICE_AUTO else
                    "default" if voice == VOICE_DEFAULT else voice
                )
                payload = json.dumps({"voice": voice_option, "rate": rate, "text": reply})
                proc = subprocess.Popen(
                    ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", powershell],
                    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE, text=True, encoding="utf-8",
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                with self.lock:
                    if not self._speech_request_current(epoch, serial):
                        proc.terminate()
                        continue
                    self.speech_process = proc
                _, errors = proc.communicate(input=payload)
                with self.lock:
                    mic_active = self.recording
                if proc.returncode and self._speech_request_current(epoch, serial) and not mic_active:
                    self._post("log", "Windows speech engine error: " + (errors or "Unknown error")[:300])
            except Exception as exc:
                if self._speech_request_current(epoch, serial):
                    self._post("log", f"Speech playback failed: {exc}")
            finally:
                with self.lock:
                    self.speech_process = None
                    self.speech_playing = False
        if self.neural_engine is not None:
            self.neural_engine.close()

    def _kill_speech(self) -> None:
        with self.lock:
            self.speech_serial += 1
            proc = self.speech_process
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass
        try:
            while True:
                self.speech_queue.get_nowait()
        except queue.Empty:
            pass

    def stop_everything(self) -> None:
        # This is intentionally independent of the selected window and model.
        with self.lock:
            self.watching = False
            self.epoch += 1
            self.last_frame = None
            self.mic_generation += 1
            self.voice_busy = False
        self._end_recording(discard=True)
        self._kill_speech()
        self.status_var.set("PANIC STOP: capture off, microphone off, speech interrupted.")
        self._log("PANIC STOP activated. All new captures and responses are disabled.")

    def close(self) -> None:
        self.stop_everything()
        self.shutdown.set()
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        self.root.destroy()


def main() -> None:
    windows_capture.enable_dpi_awareness()
    root = tk.Tk()
    HoshiApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
