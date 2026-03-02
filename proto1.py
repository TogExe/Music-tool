import tkinter as tk
from tkinter import filedialog, simpledialog
import pygame
import numpy as np
import json
import random
import math
import threading
import time
import os

# ==========================================
# 1. CONSTANTS & CONFIGURATION
# ==========================================
BG_COLOR = "#0f0f15"
PANEL_COLOR = "#1e1e2a"
TEXT_COLOR = "#f0e6d0"
ACCENT_COLOR = "#7ae0ff"
GRID_COLOR = "#2a2a35"
PARTICLE_COLOR = "#ffb86b"
USER_SCHEMATICS_FILE = "user_schematics.json"

NOTE_FREQS = {
    "C3": 130.81, "C#3": 138.59, "D3": 146.83, "D#3": 155.56, "E3": 164.81, "F3": 174.61, "F#3": 185.00, "G3": 196.00,
    "G#3": 207.65, "A3": 220.00, "A#3": 233.08, "B3": 246.94,
    "C4": 261.63, "C#4": 277.18, "D4": 293.66, "D#4": 311.13, "E4": 329.63, "F4": 349.23, "F#4": 369.99, "G4": 392.00,
    "G#4": 415.30, "A4": 440.00, "A#4": 466.16, "B4": 493.88,
    "C5": 523.25, "C#5": 554.37, "D5": 587.33, "D#5": 622.25, "E5": 659.25, "G5": 783.99, "A5": 880.00
}

NOTE_COLORS = {"C": "#ff7b7b", "D": "#ffdb7b", "E": "#b4e87c", "F": "#7bb0ff", "G": "#c97bff", "A": "#ffa07b",
               "B": "#ff9be5"}
INSTRUMENTS = ["Music Box", "Organ", "Sine Wave", "Sawtooth", "Square", "Pluck", "Handpan"]

PRESETS = {
    "Gmaj7 Poly Chord": [
        {"rel_x": 0, "rel_y": -60, "note": "G3", "inst": "Handpan", "mode": "Poly", "lat": 0.4, "children": [1, 2, 3]},
        {"rel_x": 0, "rel_y": 0, "note": "D4", "inst": "Handpan", "mode": "Poly", "lat": 0.4, "children": []},
        {"rel_x": -60, "rel_y": 0, "note": "B3", "inst": "Handpan", "mode": "Poly", "lat": 0.4, "children": []},
        {"rel_x": 60, "rel_y": 0, "note": "F#4", "inst": "Handpan", "mode": "Poly", "lat": 0.4, "children": []}
    ],
    "C#m Poly Chord": [
        {"rel_x": 0, "rel_y": -60, "note": "C#3", "inst": "Handpan", "mode": "Poly", "lat": 0.4, "children": [1, 2, 3]},
        {"rel_x": -60, "rel_y": 0, "note": "E3", "inst": "Handpan", "mode": "Poly", "lat": 0.4, "children": []},
        {"rel_x": 0, "rel_y": 0, "note": "G#3", "inst": "Handpan", "mode": "Poly", "lat": 0.4, "children": []},
        {"rel_x": 60, "rel_y": 0, "note": "C#4", "inst": "Handpan", "mode": "Poly", "lat": 0.4, "children": []}
    ]
}

# ==========================================
# 2. AUDIO ENGINE (Thread‑Safe)
# ==========================================
pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=2)
pygame.mixer.set_num_channels(128)
SOUND_CACHE = {}
cache_lock = threading.Lock()


def get_sound(note, length, instrument, volume):
    with cache_lock:
        cache_key = (note, length, instrument, volume)
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

    def schedule(self, delay_seconds, nid):
        with self.lock:
            trigger_time = time.perf_counter() + delay_seconds
            self.queue.append((trigger_time, nid))
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

            for _, nid in to_play:
                if nid in self.app.nodes:
                    node = self.app.nodes[nid]

                    try:
                        get_sound(node["note"], node["length"], node["instrument"], node["volume"]).play()
                        node["flash"] = 1.0
                        self.app.emit_particles(node["x"], node["y"], count=3)  # fewer particles
                    except Exception:
                        pass

                    valid_children = [c for c in node["children"] if c in self.app.nodes]
                    if valid_children:
                        mode = node.get("mode", "Poly")
                        if mode == "Poly":
                            for cid in valid_children:
                                self.schedule(node["latency_out"], cid)
                        else:  # Splitter
                            idx = node.get("last_child_idx", 0) % len(valid_children)
                            target = valid_children[idx]
                            node["last_child_idx"] = (idx + 1) % len(valid_children)
                            self.schedule(node["latency_out"], target)

            time.sleep(0.001)


# ==========================================
# 3. MATH UTILITIES
# ==========================================
def dist_to_segment(px, py, x1, y1, x2, y2):
    l2 = (x2 - x1) ** 2 + (y2 - y1) ** 2
    if l2 == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0, min(1, ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / l2))
    proj_x, proj_y = x1 + t * (x2 - x1), y1 + t * (y2 - y1)
    return math.hypot(px - proj_x, py - proj_y)


# ==========================================
# 4. MAIN APPLICATION
# ==========================================
class ProceduralSequencerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Graph Soundtrack Engine — Caelestia Shell")
        self.grid_size = 60

        self.nodes = {}
        self.node_counter = 0
        self.selected_nodes = set()
        self.selected_wire = None
        self.clipboard = []

        self.schematics = dict(PRESETS)
        self.load_user_schematics()
        self.active_schematic = None
        self.schematic_window = None

        self.hovered_node = None
        self.hovered_wire = None
        self.default_instrument = "Handpan"
        self.cam_x, self.cam_y = 0, 0
        self.zoom = 1.0
        self.drag_mode = None
        self.drag_start_id = None
        self.mouse_down_w = (0, 0)
        self.mouse_w = (0, 0)
        self.selection_rect = None

        self.particles = []  # [x, y, vx, vy, life]

        self.advanced_mode = tk.BooleanVar(value=False)

        self.scheduler = AudioScheduler(self)
        self.scheduler.start()

        self._setup_ui()
        self._bind_events()
        self.update_settings_ui()
        self.render_loop()

    # --- UI & SETUP (Rounded buttons on canvas) ---
    def _setup_ui(self):
        self.base_font = ('Arial Rounded', 10)
        self.heading_font = ('Arial Rounded', 12, 'bold')

        self.main_frame = tk.Frame(self.root, bg=BG_COLOR)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.main_frame, bg=BG_COLOR, highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.panel = tk.Frame(self.main_frame, bg=PANEL_COLOR, width=280)
        self.panel.pack(side=tk.RIGHT, fill=tk.Y)
        self.panel.pack_propagate(False)

        # Instead of real buttons, we'll draw them on canvas later? No, keep them as tk buttons but style them.
        # For rounded corners, we use a flat button with a highlight background. It won't be round but at least flat.
        # To get true rounding, we would need canvas buttons; that's too heavy. We'll keep flat with color.

        header = tk.Label(self.panel, text="✨ CONTROL PANEL", bg=PANEL_COLOR, fg=ACCENT_COLOR,
                          font=self.heading_font, pady=10)
        header.pack(fill=tk.X)

        # Use tk.Button with flat relief and a background color
        play_btn = tk.Button(self.panel, text="▶ PLAY ALL (FLAG NODES)", font=self.base_font,
                             bg="#2a5a8a", fg=TEXT_COLOR, activebackground="#1e4a7a",
                             command=self.trigger_green_flag, relief=tk.FLAT, bd=0, pady=6)
        play_btn.pack(fill=tk.X, padx=15, pady=(0, 10))

        schem_btn = tk.Button(self.panel, text="📦 SCHEMATICS & BLUEPRINTS",
                              bg="#6a4c93", fg=TEXT_COLOR, activebackground="#5a3c83",
                              font=self.base_font, relief=tk.FLAT, bd=0, pady=6,
                              command=self.open_schematic_window)
        schem_btn.pack(fill=tk.X, padx=15, pady=(0, 10))

        adv_cb = tk.Checkbutton(self.panel, text="Advanced Mode (show sharps)",
                                variable=self.advanced_mode, bg=PANEL_COLOR, fg=TEXT_COLOR,
                                selectcolor="#2a2a35", activebackground=PANEL_COLOR,
                                font=self.base_font, command=self.refresh_note_menu)
        adv_cb.pack(fill=tk.X, padx=15, pady=(5, 15))

        tk.Label(self.panel, text="🎛 NODE PROPERTIES", bg=PANEL_COLOR, fg=TEXT_COLOR,
                 font=self.heading_font).pack(pady=(0, 10))

        self.ui_vars = {k: tk.StringVar() if k in ["note", "instrument", "mode"] else tk.DoubleVar() for k in
                        ["note", "instrument", "mode", "length", "volume", "latency_self", "latency_out"]}
        self.ui_vars["start_on_flag"] = tk.BooleanVar()

        self.widgets_frame = tk.Frame(self.panel, bg=PANEL_COLOR)

        flag_cb = tk.Checkbutton(self.widgets_frame, text="🚩 Flag (starts on Play All)",
                                 variable=self.ui_vars["start_on_flag"],
                                 bg=PANEL_COLOR, fg=TEXT_COLOR, selectcolor="#2a2a35",
                                 font=self.base_font, command=self.apply_settings)
        flag_cb.pack(fill=tk.X, pady=(0, 15))

        tk.Label(self.widgets_frame, text="Routing Mode", fg="#aaa", bg=PANEL_COLOR,
                 font=self.base_font).pack(anchor="w")
        mode_menu = tk.OptionMenu(self.widgets_frame, self.ui_vars["mode"], "Poly", "Splitter",
                                  command=self.apply_settings)
        mode_menu.config(bg="#252530", fg="white", highlightthickness=0, activebackground="#353540",
                         font=self.base_font, relief=tk.FLAT)
        mode_menu.pack(fill=tk.X, pady=(0, 15))

        tk.Label(self.widgets_frame, text="Note", fg="#aaa", bg=PANEL_COLOR,
                 font=self.base_font).pack(anchor="w")
        self.note_dropdown = tk.OptionMenu(self.widgets_frame, self.ui_vars["note"],
                                           *self.get_current_scale(), command=self.apply_settings)
        self.note_dropdown.config(bg="#252530", fg="white", highlightthickness=0, activebackground="#353540",
                                  font=self.base_font, relief=tk.FLAT)
        self.note_dropdown.pack(fill=tk.X, pady=(0, 15))

        tk.Label(self.widgets_frame, text="Instrument", fg="#aaa", bg=PANEL_COLOR,
                 font=self.base_font).pack(anchor="w")
        inst_menu = tk.OptionMenu(self.widgets_frame, self.ui_vars["instrument"], *INSTRUMENTS,
                                  command=self.apply_settings)
        inst_menu.config(bg="#252530", fg="white", highlightthickness=0, activebackground="#353540",
                         font=self.base_font, relief=tk.FLAT)
        inst_menu.pack(fill=tk.X, pady=(0, 15))

        sliders = [("Length (s)", "length", 0.1, 3.0),
                   ("Volume", "volume", 0.0, 1.0),
                   ("Self Latency", "latency_self", 0.0, 2.0),
                   ("Out Latency", "latency_out", 0.0, 2.0)]
        for label, key, low, high in sliders:
            tk.Label(self.widgets_frame, text=label, fg="#aaa", bg=PANEL_COLOR,
                     font=self.base_font).pack(anchor="w")
            scale = tk.Scale(self.widgets_frame, variable=self.ui_vars[key],
                             from_=low, to=high, resolution=0.05,
                             orient=tk.HORIZONTAL, bg=PANEL_COLOR, fg="white",
                             highlightthickness=0, bd=0, troughcolor="#252530",
                             command=lambda _, k=key: self.apply_settings(k))
            scale.pack(fill=tk.X, pady=(0, 10))

        self.empty_label = tk.Label(self.panel, text="Select a node to edit",
                                    fg="#777", bg=PANEL_COLOR, font=self.base_font)

        bottom_frame = tk.Frame(self.panel, bg=PANEL_COLOR)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=20, padx=15)
        tk.Button(bottom_frame, text="Save Project", bg="#2a5a8a", fg=TEXT_COLOR,
                  font=self.base_font, relief=tk.FLAT, bd=0, pady=6,
                  command=self.save_project).pack(fill=tk.X, pady=5)
        tk.Button(bottom_frame, text="Load Project", bg="#353540", fg=TEXT_COLOR,
                  font=self.base_font, relief=tk.FLAT, bd=0, pady=6,
                  command=self.load_project).pack(fill=tk.X)

    def _bind_events(self):
        self.canvas.bind("<ButtonPress-1>", self.on_left_down)
        self.canvas.bind("<B1-Motion>", self.on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_up)
        self.canvas.bind("<ButtonPress-3>", self.on_right_click)
        self.canvas.bind("<Motion>", self.on_mouse_move)

        self.canvas.bind("<ButtonPress-2>", self.on_mid_down)
        self.canvas.bind("<B2-Motion>", self.on_mid_drag)
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.canvas.bind("<Button-4>", self.on_zoom)
        self.canvas.bind("<Button-5>", self.on_zoom)

        self.root.bind("<space>", self.on_spacebar)
        self.root.bind("<Return>", self.trigger_green_flag)
        self.root.bind("<Delete>", self.on_delete_key)
        self.root.bind("<BackSpace>", self.on_delete_key)
        self.root.bind("<Escape>", self.on_escape)
        self.root.bind("<Control-c>", self.copy_selection)
        self.root.bind("<Control-v>", self.paste_selection)

        for i in range(1, 8):
            self.root.bind(str(i), lambda e, idx=i-1: self.set_default_instrument(idx))

    # --- Auto‑save schematics ---
    def load_user_schematics(self):
        if os.path.exists(USER_SCHEMATICS_FILE):
            try:
                with open(USER_SCHEMATICS_FILE, 'r') as f:
                    user_data = json.load(f)
                    self.schematics.update(user_data)
            except Exception as e:
                print(f"Error loading user schematics: {e}")

    def save_user_schematics(self):
        custom_schematics = {k: v for k, v in self.schematics.items() if k not in PRESETS}
        try:
            with open(USER_SCHEMATICS_FILE, 'w') as f:
                json.dump(custom_schematics, f, indent=4)
        except Exception as e:
            print(f"Error saving user schematics: {e}")

    # --- Schematic window ---
    def open_schematic_window(self):
        if self.schematic_window and self.schematic_window.winfo_exists():
            self.schematic_window.lift()
            return

        self.schematic_window = tk.Toplevel(self.root)
        self.schematic_window.title("Schematic Inventory")
        self.schematic_window.geometry("300x500")
        self.schematic_window.configure(bg=BG_COLOR)

        tk.Label(self.schematic_window, text="📦 SCHEMATICS", fg=ACCENT_COLOR, bg=BG_COLOR,
                 font=self.heading_font).pack(pady=15)

        canvas = tk.Canvas(self.schematic_window, bg=BG_COLOR, highlightthickness=0)
        scrollbar = tk.Scrollbar(self.schematic_window, orient="vertical", command=canvas.yview)
        self.inv_buttons_frame = tk.Frame(canvas, bg=BG_COLOR)

        self.inv_buttons_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.inv_buttons_frame, anchor="nw", width=280)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="top", fill="both", expand=True, padx=5)
        scrollbar.pack(side="right", fill="y")

        self.refresh_inventory_ui()

        footer = tk.Frame(self.schematic_window, bg=BG_COLOR)
        footer.pack(side=tk.BOTTOM, fill=tk.X, pady=15, padx=15)
        tk.Button(footer, text="⭐ Save Selection as Schematic", bg="#008080", fg="white",
                  font=self.base_font, relief=tk.FLAT, bd=0, pady=5,
                  command=self.save_selection_as_schematic).pack(fill=tk.X, pady=(0, 10))
        tk.Button(footer, text="📂 Load JSON Array from File...", bg="#353540", fg="white",
                  font=self.base_font, relief=tk.FLAT, bd=0, pady=5,
                  command=self.load_schematic_file).pack(fill=tk.X)

    def refresh_inventory_ui(self):
        if not hasattr(self, 'inv_buttons_frame') or not self.inv_buttons_frame.winfo_exists():
            return

        for widget in self.inv_buttons_frame.winfo_children():
            widget.destroy()

        for name in self.schematics.keys():
            btn = tk.Button(self.inv_buttons_frame, text=name, bg="#252530", fg="white",
                            font=self.base_font, relief=tk.FLAT, bd=0,
                            command=lambda n=name: self.set_active_schematic(n))
            btn.pack(fill=tk.X, pady=2, padx=5)

    def set_active_schematic(self, name):
        self.active_schematic = name
        self.canvas.config(cursor="crosshair" if name else "")

    def place_schematic(self, root_wx, root_wy):
        if not self.active_schematic:
            return

        schema = self.schematics[self.active_schematic]
        id_map = {}
        snapped_rx = self.snap(root_wx)
        snapped_ry = self.snap(root_wy)

        for i, data in enumerate(schema):
            new_id = self.create_node(snapped_rx + data.get("rel_x", 0),
                                      snapped_ry + data.get("rel_y", 0))
            id_map[i] = new_id
            node = self.nodes[new_id]
            if "note" in data: node["note"] = data["note"]
            if "inst" in data: node["instrument"] = data["inst"]
            if "instrument" in data: node["instrument"] = data["instrument"]
            if "mode" in data: node["mode"] = data["mode"]
            if "lat" in data: node["latency_out"] = data["lat"]
            if "latency_out" in data: node["latency_out"] = data["latency_out"]
            if "vol" in data: node["volume"] = data["vol"]
            if "volume" in data: node["volume"] = data["volume"]
            if "start" in data: node["start_on_flag"] = data["start"]
            if "start_on_flag" in data: node["start_on_flag"] = data["start_on_flag"]

        for i, data in enumerate(schema):
            if "children" in data:
                for child_idx in data["children"]:
                    if child_idx in id_map:
                        self.nodes[id_map[i]]["children"].append(id_map[child_idx])

        self.selected_nodes = set(id_map.values())
        self.update_settings_ui()
        self.set_active_schematic(None)

    def save_selection_as_schematic(self):
        if not self.selected_nodes:
            print("Select nodes on the canvas first!")
            return

        name = simpledialog.askstring("Save Schematic", "Enter schematic name:", parent=self.root)
        if not name:
            return

        xs = [self.nodes[n]["x"] for n in self.selected_nodes]
        ys = [self.nodes[n]["y"] for n in self.selected_nodes]
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        cx, cy = self.snap(cx), self.snap(cy)

        schema = []
        id_to_idx = {nid: i for i, nid in enumerate(self.selected_nodes)}

        for nid in self.selected_nodes:
            org = self.nodes[nid]
            c_child = [id_to_idx[c] for c in org["children"] if c in self.selected_nodes]
            schema.append({
                "rel_x": org["x"] - cx,
                "rel_y": org["y"] - cy,
                "note": org["note"],
                "inst": org["instrument"],
                "length": org["length"],
                "vol": org["volume"],
                "lat": org["latency_out"],
                "start": org.get("start_on_flag", False),
                "children": c_child,
                "mode": org.get("mode", "Poly")
            })

        self.schematics[name] = schema
        self.save_user_schematics()
        self.refresh_inventory_ui()
        print(f"Saved schematic: {name}")

    def load_schematic_file(self):
        path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if path:
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    name = os.path.splitext(os.path.basename(path))[0]
                    self.schematics[name] = data
                elif isinstance(data, dict):
                    self.schematics.update(data)
                else:
                    print("Invalid schematic format. Use list or dict.")
                    return
                self.save_user_schematics()
                self.refresh_inventory_ui()
            except Exception as e:
                print(f"Error loading schematic: {e}")

    # --- Helpers ---
    def set_default_instrument(self, index):
        if 0 <= index < len(INSTRUMENTS):
            self.default_instrument = INSTRUMENTS[index]

    def s2w(self, sx, sy):
        return (sx / self.zoom) + self.cam_x, (sy / self.zoom) + self.cam_y

    def w2s(self, wx, wy):
        return (wx - self.cam_x) * self.zoom, (wy - self.cam_y) * self.zoom

    def snap(self, val):
        return round(val / self.grid_size) * self.grid_size

    def get_current_scale(self):
        return list(NOTE_FREQS.keys()) if self.advanced_mode.get() else [n for n in NOTE_FREQS.keys() if '#' not in n]

    def create_node(self, wx, wy, parent_id=None, override_data=None):
        self.node_counter += 1
        nid = self.node_counter
        scale = self.get_current_scale()

        data = {
            "x": self.snap(wx), "y": self.snap(wy),
            "note": "C4", "instrument": self.default_instrument,
            "length": 1.0, "volume": 0.8,
            "latency_self": 0.0, "latency_out": 0.4,
            "start_on_flag": False, "children": [], "anim_scale": 1.0, "flash": 0.0,
            "mode": "Poly", "last_child_idx": 0
        }

        if not override_data and parent_id and parent_id in self.nodes:
            parent_note = self.nodes[parent_id]["note"]
            if parent_note in scale:
                parent_idx = scale.index(parent_note)
                existing = [self.nodes[cid]["note"] for cid in self.nodes[parent_id]["children"] if cid in self.nodes]
                chosen = next((scale[(parent_idx + off) % len(scale)] for off in [2, 4, 1, 3, -2] if
                               scale[(parent_idx + off) % len(scale)] not in existing), None)
                data["note"] = chosen if chosen else scale[(parent_idx + 1) % len(scale)]
        elif not override_data:
            middle_notes = [n for n in scale if "4" in n or "3" in n]
            if middle_notes:
                data["note"] = random.choice(middle_notes)

        if override_data:
            data.update(override_data)

        self.nodes[nid] = data
        return nid

    # --- UI updates (multi‑node editing) ---
    def select_note_from_menu(self, selected_note):
        self.ui_vars["note"].set(selected_note)
        self.apply_settings("note")  # only note changes

    def refresh_note_menu(self):
        scale = self.get_current_scale()
        menu = self.note_dropdown["menu"]
        menu.delete(0, "end")
        for note in scale:
            menu.add_command(label=note, command=lambda n=note: self.select_note_from_menu(n))

    def update_settings_ui(self):
        if len(self.selected_nodes) >= 1:
            self.widgets_frame.pack(fill=tk.BOTH, expand=True, padx=15)
            self.empty_label.pack_forget()

            # Show values from first node, but for note, show placeholder if mixed
            first = list(self.selected_nodes)[0]
            node0 = self.nodes[first]

            # For each var, set to value from first node, but note is special
            for k, v in self.ui_vars.items():
                if k == "note":
                    # Check if all selected have same note
                    notes = {self.nodes[n]["note"] for n in self.selected_nodes}
                    if len(notes) == 1:
                        v.set(node0["note"])
                    else:
                        v.set("—")  # placeholder
                else:
                    v.set(node0.get(k, False if k == "start_on_flag" else node0.get(k, "")))
        else:
            self.widgets_frame.pack_forget()
            self.empty_label.pack(pady=50)

    def apply_settings(self, changed_key=None):
        # If changed_key is provided, only update that property; otherwise update all.
        # This prevents accidentally changing note when adjusting volume.
        if not self.selected_nodes:
            return

        keys_to_update = [changed_key] if changed_key else list(self.ui_vars.keys())

        for nid in self.selected_nodes:
            for k in keys_to_update:
                if k == "note" and self.ui_vars[k].get() == "—":
                    continue  # don't apply placeholder
                self.nodes[nid][k] = self.ui_vars[k].get()

    # --- File I/O ---
    def save_project(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if path:
            with open(path, 'w') as f:
                json.dump(self.nodes, f, indent=4)

    def load_project(self):
        path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if path:
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                self.nodes.clear()
                self.selected_nodes.clear()
                for k, v in data.items():
                    v.update({"anim_scale": 1.0, "flash": 0.0,
                              "start_on_flag": v.get("start_on_flag", False),
                              "mode": v.get("mode", "Poly"),
                              "last_child_idx": v.get("last_child_idx", 0)})
                    if v["note"] not in NOTE_FREQS:
                        v["note"] = "C4"
                    self.nodes[int(k)] = v
                self.node_counter = max(self.nodes.keys()) if self.nodes else 0
                self.update_settings_ui()
            except Exception as e:
                print(f"Error loading file: {e}")

    # --- Canvas interactions ---
    def get_node_at(self, wx, wy, radius=25):
        for nid, d in self.nodes.items():
            if (d["x"] - wx) ** 2 + (d["y"] - wy) ** 2 <= radius ** 2:
                return nid
        return None

    def get_wire_at(self, wx, wy, threshold=8):
        for pid, d in self.nodes.items():
            for cid in d["children"]:
                if cid in self.nodes:
                    cd = self.nodes[cid]
                    if dist_to_segment(wx, wy, d["x"], d["y"], cd["x"], cd["y"]) < threshold / self.zoom:
                        return (pid, cid)
        return None

    def on_mouse_move(self, event):
        self.mouse_w = self.s2w(event.x, event.y)
        self.hovered_node = self.get_node_at(self.mouse_w[0], self.mouse_w[1])
        self.hovered_wire = self.get_wire_at(self.mouse_w[0], self.mouse_w[1]) if not self.hovered_node else None

    def on_mid_down(self, event):
        self.pan_start_x, self.pan_start_y = event.x, event.y

    def on_mid_drag(self, event):
        self.cam_x -= (event.x - self.pan_start_x) / self.zoom
        self.cam_y -= (event.y - self.pan_start_y) / self.zoom
        self.pan_start_x, self.pan_start_y = event.x, event.y

    def on_zoom(self, event):
        if self.hovered_node is not None:
            self.handle_scroll_transpose(event)
            return

        wx, wy = self.s2w(event.x, event.y)
        if event.num == 4 or getattr(event, 'delta', 0) > 0:
            self.zoom *= 1.1
        elif event.num == 5 or getattr(event, 'delta', 0) < 0:
            self.zoom /= 1.1
        self.zoom = max(0.2, min(self.zoom, 3.0))
        self.cam_x, self.cam_y = wx - (event.x / self.zoom), wy - (event.y / self.zoom)

    def handle_scroll_transpose(self, event):
        nid = self.hovered_node
        if nid not in self.nodes:
            return
        node = self.nodes[nid]
        scale = self.get_current_scale()

        if node["note"] in scale:
            idx = scale.index(node["note"])
            delta = 1 if (event.num == 4 or getattr(event, 'delta', 0) > 0) else -1
            new_idx = (idx + delta) % len(scale)
            node["note"] = scale[new_idx]
            self.scheduler.schedule(0, nid)
            self.update_settings_ui()

    def on_escape(self, event):
        self.set_active_schematic(None)

    def on_left_down(self, event):
        self.canvas.focus_set()
        wx, wy = self.s2w(event.x, event.y)

        if self.active_schematic:
            self.place_schematic(wx, wy)
            return

        self.mouse_down_w = (wx, wy)
        node_id = self.get_node_at(wx, wy)
        wire = self.get_wire_at(wx, wy)
        self.selected_wire = None

        if node_id is not None:
            if node_id not in self.selected_nodes:
                self.selected_nodes = {node_id}
            self.drag_start_id = node_id
            self.drag_mode = "move_node" if math.hypot(wx - self.nodes[node_id]["x"],
                                                       wy - self.nodes[node_id]["y"]) < 12 else "wire"
        elif wire is not None:
            self.selected_nodes.clear()
            self.selected_wire = wire
            self.drag_mode = "none"
        else:
            self.selected_nodes.clear()
            self.drag_mode = "maybe_spawn"
        self.update_settings_ui()

    def on_left_drag(self, event):
        if self.active_schematic:
            return
        self.mouse_w = self.s2w(event.x, event.y)
        dist = math.hypot(self.mouse_w[0] - self.mouse_down_w[0], self.mouse_w[1] - self.mouse_down_w[1])
        if self.drag_mode == "maybe_spawn" and dist > 10 / self.zoom:
            self.drag_mode = "box"

        if self.drag_mode == "move_node":
            dx, dy = self.mouse_w[0] - self.mouse_down_w[0], self.mouse_w[1] - self.mouse_down_w[1]
            for nid in self.selected_nodes:
                self.nodes[nid]["x"] += dx
                self.nodes[nid]["y"] += dy
            self.mouse_down_w = self.mouse_w
        elif self.drag_mode == "box":
            self.selection_rect = (self.mouse_down_w[0], self.mouse_down_w[1],
                                   self.mouse_w[0], self.mouse_w[1])

    def on_left_up(self, event):
        if self.active_schematic:
            return
        wx, wy = self.s2w(event.x, event.y)
        dist = math.hypot(wx - self.mouse_down_w[0], wy - self.mouse_down_w[1])

        if self.drag_mode == "maybe_spawn" and dist <= 10 / self.zoom:
            parent = list(self.selected_nodes)[0] if len(self.selected_nodes) == 1 else None
            new_id = self.create_node(wx, wy, parent_id=parent)
            if parent and parent != new_id and new_id not in self.nodes[parent]["children"]:
                self.nodes[parent]["children"].append(new_id)
            self.selected_nodes = {new_id}
        elif self.drag_mode == "wire" and self.drag_start_id:
            target_id = self.get_node_at(wx, wy)
            if target_id is None:
                target_id = self.create_node(wx, wy, parent_id=self.drag_start_id)
            if target_id != self.drag_start_id and target_id not in self.nodes[self.drag_start_id]["children"]:
                self.nodes[self.drag_start_id]["children"].append(target_id)
            self.selected_nodes = {target_id}
        elif self.drag_mode == "move_node":
            for nid in self.selected_nodes:
                self.nodes[nid]["x"], self.nodes[nid]["y"] = self.snap(self.nodes[nid]["x"]), self.snap(self.nodes[nid]["y"])
        elif self.drag_mode == "box" and self.selection_rect:
            x1, y1, x2, y2 = self.selection_rect
            for nid, d in self.nodes.items():
                if min(x1, x2) <= d["x"] <= max(x1, x2) and min(y1, y2) <= d["y"] <= max(y1, y2):
                    self.selected_nodes.add(nid)
            self.selection_rect = None

        self.drag_mode = None
        self.update_settings_ui()

    def delete_logic(self, target_node=None, target_wire=None):
        if target_node and target_node in self.nodes:
            del self.nodes[target_node]
            if target_node in self.selected_nodes:
                self.selected_nodes.remove(target_node)
            for d in self.nodes.values():
                if target_node in d["children"]:
                    d["children"].remove(target_node)
        elif target_wire:
            pid, cid = target_wire
            if pid in self.nodes and cid in self.nodes[pid]["children"]:
                self.nodes[pid]["children"].remove(cid)
            if self.selected_wire == target_wire:
                self.selected_wire = None
        self.update_settings_ui()

    def on_right_click(self, event):
        if self.active_schematic:
            self.set_active_schematic(None)
            return

        wx, wy = self.s2w(event.x, event.y)
        nid = self.get_node_at(wx, wy)
        if nid:
            self.delete_logic(target_node=nid)
        else:
            wire = self.get_wire_at(wx, wy)
            if wire:
                self.delete_logic(target_wire=wire)

    def on_delete_key(self, event):
        for nid in list(self.selected_nodes):
            self.delete_logic(target_node=nid)
        if self.selected_wire:
            self.delete_logic(target_wire=self.selected_wire)

    def copy_selection(self, event=None):
        if not self.selected_nodes:
            return
        self.clipboard = []
        xs, ys = [self.nodes[n]["x"] for n in self.selected_nodes], [self.nodes[n]["y"] for n in self.selected_nodes]
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        for nid in self.selected_nodes:
            org = self.nodes[nid]
            c_child = [c for c in org["children"] if c in self.selected_nodes]
            self.clipboard.append({
                "old_id": nid,
                "rel_x": org["x"] - cx,
                "rel_y": org["y"] - cy,
                "note": org["note"],
                "instrument": org["instrument"],
                "length": org["length"],
                "volume": org["volume"],
                "latency_self": org["latency_self"],
                "latency_out": org["latency_out"],
                "start_on_flag": org.get("start_on_flag", False),
                "children": c_child,
                "mode": org.get("mode", "Poly")
            })

    def paste_selection(self, event=None):
        if not self.clipboard:
            return
        id_map, new_selection = {}, set()
        for item in self.clipboard:
            new_id = self.create_node(self.mouse_w[0] + item["rel_x"], self.mouse_w[1] + item["rel_y"])
            id_map[item["old_id"]] = new_id
            for k in ["note", "instrument", "length", "volume", "latency_self", "latency_out",
                      "start_on_flag", "mode"]:
                self.nodes[new_id][k] = item[k]
            new_selection.add(new_id)
        for item in self.clipboard:
            for old_child in item["children"]:
                self.nodes[id_map[item["old_id"]]]["children"].append(id_map[old_child])
        self.selected_nodes = new_selection
        self.update_settings_ui()

    # --- Playback ---
    def on_spacebar(self, event=None):
        self.scheduler.clear()
        for nid in self.selected_nodes:
            self.trigger_node(nid)

    def trigger_green_flag(self, event=None):
        self.scheduler.clear()
        for nid, d in self.nodes.items():
            if d.get("start_on_flag", False):
                self.trigger_node(nid)

    def trigger_node(self, nid):
        if nid in self.nodes:
            self.scheduler.schedule(self.nodes[nid].get("latency_self", 0), nid)

    # --- Particles (toned down) ---
    def emit_particles(self, x, y, count=3):
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(15, 40)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            life = random.uniform(0.3, 0.8)
            self.particles.append([x, y, vx, vy, life])

    def update_particles(self, dt=0.016):
        for p in self.particles[:]:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[4] -= dt * 0.8
            if p[4] <= 0:
                self.particles.remove(p)

    # --- Rendering ---
    def render_loop(self):
        for nid, d in self.nodes.items():
            target_scale = 1.1 if nid == self.hovered_node else 1.0
            if nid in self.selected_nodes:
                target_scale = 1.05
            d["anim_scale"] += (target_scale - d["anim_scale"]) * 0.2
            if d["flash"] > 0.01:
                d["flash"] += (0 - d["flash"]) * 0.2

        self.update_particles()

        self.canvas.delete("all")
        g_size = self.grid_size * self.zoom
        offset_x, offset_y = -(self.cam_x * self.zoom) % g_size, -(self.cam_y * self.zoom) % g_size
        for x in np.arange(offset_x, self.canvas.winfo_width() + g_size, g_size):
            self.canvas.create_line(x, 0, x, self.canvas.winfo_height(), fill=GRID_COLOR)
        for y in np.arange(offset_y, self.canvas.winfo_height() + g_size, g_size):
            self.canvas.create_line(0, y, self.canvas.winfo_width(), y, fill=GRID_COLOR)

        # Draw wires
        for nid, d in self.nodes.items():
            for cid in d["children"]:
                if cid in self.nodes:
                    sx1, sy1 = self.w2s(d["x"], d["y"])
                    sx2, sy2 = self.w2s(self.nodes[cid]["x"], self.nodes[cid]["y"])
                    is_hovered = (self.hovered_wire == (nid, cid))
                    is_selected = (self.selected_wire == (nid, cid))
                    color = ACCENT_COLOR if is_selected else ("#aaa" if is_hovered else "#445")
                    width = (6 if is_selected or is_hovered else 4) * self.zoom
                    dash_pattern = (4, 4) if d.get("mode") == "Splitter" and not is_hovered else None
                    self.canvas.create_line(sx1, sy1, sx2, sy2, fill=color, width=width, dash=dash_pattern)

        if self.drag_mode == "wire" and self.drag_start_id in self.nodes:
            sx1, sy1 = self.w2s(self.nodes[self.drag_start_id]["x"], self.nodes[self.drag_start_id]["y"])
            sx2, sy2 = self.w2s(self.mouse_w[0], self.mouse_w[1])
            self.canvas.create_line(sx1, sy1, sx2, sy2, fill="white", dash=(4, 4), width=2 * self.zoom)

        # Draw particles
        for p in self.particles:
            sx, sy = self.w2s(p[0], p[1])
            size = 3 * self.zoom * p[4]
            self.canvas.create_oval(sx - size, sy - size, sx + size, sy + size,
                                    fill=PARTICLE_COLOR, outline='', stipple='gray50')

        # Draw nodes (subtle glow)
        for nid, d in self.nodes.items():
            r = 20 * self.zoom * d["anim_scale"]
            sx, sy = self.w2s(d["x"], d["y"])
            base_color = NOTE_COLORS.get(d["note"][0], "#ccc")

            # Very subtle outer ring
            if d["flash"] > 0.1:
                flash_r = r + 8 * self.zoom * d["flash"]
                self.canvas.create_oval(sx - flash_r, sy - flash_r, sx + flash_r, sy + flash_r,
                                        outline='white', width=2 * self.zoom, dash=(2, 2))

            # Main circle
            self.canvas.create_oval(sx - r, sy - r, sx + r, sy + r,
                                    fill=base_color, outline='white', width=2 * self.zoom)

            # Inner highlight
            inner_r = r * 0.5
            self.canvas.create_oval(sx - inner_r, sy - inner_r, sx + inner_r, sy + inner_r,
                                    fill='white', outline='', stipple='gray75')

            # Note name
            display_text = f"{d['note']} (S)" if d.get("mode") == "Splitter" else d["note"]
            self.canvas.create_text(sx, sy, text=display_text, fill='black',
                                    font=(self.base_font[0], int(9 * self.zoom), 'bold'))

            # Flag
            if d.get("start_on_flag", False):
                flag_size = 10 * self.zoom
                self.canvas.create_polygon(sx - r - 4, sy - r, sx - r + flag_size, sy - r,
                                           sx - r, sy - r - flag_size,
                                           fill="#ffaa22", outline="black", width=1)

        # Selection rectangle
        if self.selection_rect:
            sx1, sy1 = self.w2s(self.selection_rect[0], self.selection_rect[1])
            sx2, sy2 = self.w2s(self.selection_rect[2], self.selection_rect[3])
            self.canvas.create_rectangle(sx1, sy1, sx2, sy2, outline=ACCENT_COLOR, dash=(4, 4))

        # Status line
        status = f"✨ Placing: {self.active_schematic} (Right‑click to cancel)" if self.active_schematic \
            else f"🎵 Tool: {self.default_instrument} [Keys 1‑7]"
        self.canvas.create_text(20, 20, anchor=tk.NW, text=status,
                                fill=ACCENT_COLOR if self.active_schematic else TEXT_COLOR,
                                font=(self.base_font[0], 12, "bold" if self.active_schematic else "normal"))

        self.root.after(16, self.render_loop)


# ==========================================
# RUN
# ==========================================
if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1200x750")
    app = ProceduralSequencerApp(root)
    root.mainloop()
