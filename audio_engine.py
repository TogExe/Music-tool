import pygame
import numpy as np
import threading
import time
import random
from config import NOTE_FREQS

pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=2)
pygame.mixer.set_num_channels(128)

SOUND_CACHE = {}
cache_lock = threading.Lock()


def get_sound(note, length, instrument, volume):
    with cache_lock:
        cache_key = (note, round(length, 3), instrument, round(volume, 2))
        if cache_key in SOUND_CACHE:
            return SOUND_CACHE[cache_key]

        freq = NOTE_FREQS.get(note, 261.63)
        sample_rate = 44100
        t = np.linspace(0, length, int(sample_rate * length), False)

        if instrument == "Music Box":
            env = np.exp(-4 * t / length)
            wave = (np.sin(2 * np.pi * freq * t) + 0.2 * np.sin(2 * np.pi * freq * 2 * t)) * env
        elif instrument == "Organ":
            env = np.ones_like(t)
            fade = min(2000, len(t) // 2)
            env[:fade] = np.linspace(0, 1, fade)
            env[-fade:] = np.linspace(1, 0, fade)
            wave = (np.sin(2 * np.pi * freq * t) + 0.5 * np.sin(2 * np.pi * freq * 2 * t) + 0.25 * np.sin(
                2 * np.pi * freq * 3 * t)) * env
        elif instrument == "Sine Wave":
            env = np.ones_like(t)
            fade = min(1000, len(t) // 2)
            env[:fade] = np.linspace(0, 1, fade)
            env[-fade:] = np.linspace(1, 0, fade)
            wave = np.sin(2 * np.pi * freq * t) * env
        elif instrument == "Sawtooth":
            env = np.ones_like(t)
            fade = min(1000, len(t) // 2)
            env[:fade] = np.linspace(0, 1, fade)
            env[-fade:] = np.linspace(1, 0, fade)
            wave = 2.0 * (t * freq - np.floor(t * freq + 0.5)) * env
        elif instrument == "Square":
            env = np.ones_like(t)
            fade = min(1000, len(t) // 2)
            env[:fade] = np.linspace(0, 1, fade)
            env[-fade:] = np.linspace(1, 0, fade)
            wave = np.sign(np.sin(2 * np.pi * freq * t)) * env * 0.5
        elif instrument == "Pluck":
            env = np.exp(-12 * t / length)
            wave = (np.sin(2 * np.pi * freq * t) + 0.8 * np.sin(2 * np.pi * freq * 2 * t) + 0.4 * np.sin(
                2 * np.pi * freq * 3 * t)) * env
        elif instrument == "Handpan":
            env_body = np.exp(-3.5 * t / length)
            env_punch = np.exp(-30 * t / length)
            body_wave = (np.sin(2 * np.pi * freq * t) + 0.5 * np.sin(2 * np.pi * freq * 2 * t) + 0.25 * np.sin(
                2 * np.pi * freq * 2.98 * t)) * env_body
            punch_wave = np.sin(2 * np.pi * freq * t) * env_punch * 1.5
            wave = body_wave + punch_wave

        # --- Breakcore / Synth Instruments ---
        elif instrument == "Reese Bass":
            env = np.ones_like(t)
            fade = min(1000, len(t) // 2)
            env[:fade] = np.linspace(0, 1, fade)
            env[-fade:] = np.linspace(1, 0, fade)
            saw1 = 2.0 * (t * freq - np.floor(t * freq + 0.5))
            saw2 = 2.0 * (t * (freq * 1.01) - np.floor(t * (freq * 1.01) + 0.5))
            saw3 = 2.0 * (t * (freq * 0.99) - np.floor(t * (freq * 0.99) + 0.5))
            wave = (saw1 + saw2 + saw3) * env * 0.4
        elif instrument == "Gabe Kick":
            freq_env = np.linspace(freq * 3, freq * 0.5, len(t))
            phase = np.cumsum(freq_env * 2 * np.pi / sample_rate)
            env = np.exp(-8 * t / length)
            wave = np.sin(phase) * env
            wave = np.clip(wave * 4.0, -1.0, 1.0)
        elif instrument == "Synth Snare":
            noise_env = np.exp(-15 * t / length)
            tone_env = np.exp(-25 * t / length)
            noise = np.random.uniform(-1, 1, len(t)) * noise_env * 0.8
            tone = np.sin(2 * np.pi * (freq * 1.5) * t) * tone_env
            wave = noise + tone
        elif instrument == "Glitch Noise":
            env = np.exp(-20 * t / length)
            wave = np.random.uniform(-1, 1, len(t)) * env
            wave = np.round(wave * 8) / 8

        # --- Standard Drums ---
        elif instrument == "Kick":
            # Deep, clean electronic kick drum
            freq_env = np.linspace(150, 40, len(t))
            phase = np.cumsum(freq_env * 2 * np.pi / sample_rate)
            env = np.exp(-12 * t / length)
            wave = np.sin(phase) * env * 1.5
        elif instrument == "Snare":
            # Snare with snappy body and noise tail
            tone = np.sin(2 * np.pi * 180 * t) * np.exp(-18 * t / length)
            noise = np.random.uniform(-1, 1, len(t)) * np.exp(-12 * t / length)
            wave = (tone + noise * 0.6)
        elif instrument == "Hi-Hat":
            # Crisp, high-passed noise
            noise = np.random.uniform(-1, 1, len(t))
            noise = np.diff(noise, prepend=0)  # Simple high-pass trick
            env = np.exp(-40 * t / length)  # Very sharp decay
            wave = noise * env * 0.8
        else:
            wave = np.zeros_like(t)

        wave = wave * volume * 0.2
        wave = np.tanh(wave)
        wave = np.clip(wave * 32767, -32768, 32767).astype(np.int16)
        stereo_wave = np.ascontiguousarray(np.column_stack((wave, wave)))

        sound = pygame.sndarray.make_sound(stereo_wave)
        SOUND_CACHE[cache_key] = sound
        return sound


class AudioScheduler(threading.Thread):
    def __init__(self, app_ref):
        super().__init__(daemon=True)
        self.app = app_ref
        self.queue = []
        self.is_running = True
        self.lock = threading.Lock()

    def schedule(self, delay_seconds, nid, endless_mode=False):
        with self.lock:
            trigger_time = time.perf_counter() + delay_seconds
            self.queue.append((trigger_time, nid, endless_mode))
            self.queue.sort(key=lambda x: x[0])

    def clear(self):
        with self.lock:
            self.queue.clear()

    def run(self):
        while self.is_running:
            now = time.perf_counter()
            to_play = []

            with self.lock:
                while self.queue and self.queue[0][0] <= now:
                    to_play.append(self.queue.pop(0))

            for _, nid, endless in to_play:
                if nid in self.app.nodes:
                    node = self.app.nodes[nid]

                    bps = self.app.global_bpm.get() / 60.0
                    sec_per_beat = 1.0 / bps if bps > 0 else 1.0
                    length_sec = node.get("length", 1.0) * sec_per_beat

                    try:
                        sound = get_sound(node["note"], length_sec, node["instrument"], node["volume"])
                        channel = sound.play()

                        choke_grp = int(node.get("choke_group", 0))
                        if choke_grp > 0 and channel is not None:
                            with self.app.choke_lock:
                                if choke_grp in self.app.active_channels:
                                    self.app.active_channels[choke_grp].stop()
                                self.app.active_channels[choke_grp] = channel

                        node["flash"] = 1.0
                    except Exception:
                        pass

                    if endless and self.app.is_playing_endless:
                        self._schedule_endless(node, sec_per_beat)
                    elif not endless:
                        self._schedule_standard(node, sec_per_beat)

            time.sleep(0.001)

    def _schedule_standard(self, node, sec_per_beat):
        valid_children = [c for c in node["children"] if c in self.app.nodes]
        if not valid_children:
            return

        mode = node.get("mode", "Poly")
        lat_out_sec = node.get("latency_out", 0) * sec_per_beat

        if mode == "Poly":
            for cid in valid_children:
                self.schedule(lat_out_sec, cid, False)
        else:
            idx = node.get("last_child_idx", 0) % len(valid_children)
            target = valid_children[idx]
            node["last_child_idx"] = (idx + 1) % len(valid_children)
            self.schedule(lat_out_sec, target, False)

    def _schedule_endless(self, node, sec_per_beat):
        valid_children = [c for c in node["children"] if c in self.app.nodes]
        lat_out_sec = node.get("latency_out", 0) * sec_per_beat

        if valid_children:
            mode = node.get("mode", "Poly")
            if mode == "Poly":
                next_node = random.choice(valid_children)
                self.schedule(lat_out_sec, next_node, True)
            else:
                idx = node.get("last_child_idx", 0) % len(valid_children)
                next_node = valid_children[idx]
                node["last_child_idx"] = (idx + 1) % len(valid_children)
                self.schedule(lat_out_sec, next_node, True)
        elif self.app.nodes:
            jump_target = random.choice(list(self.app.nodes.keys()))
            self.schedule(max(1.0 * sec_per_beat, lat_out_sec), jump_target, True)