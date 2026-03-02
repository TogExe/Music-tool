import tkinter as tk
from tkinter import filedialog, simpledialog, ttk
import json
import random
import math
import os
import numpy as np
import threading

from config import *
from utils import dist_to_segment
from audio_engine import AudioScheduler


# ==========================================
# CUSTOM WIDGET: Collapsible Category Pane
# ==========================================
class CollapsiblePane(tk.Frame):
    def __init__(self, parent, title, expanded_default=True):
        super().__init__(parent, bg=PANEL_COLOR)
        self.expanded = expanded_default

        # Title bar
        self.title_frame = tk.Frame(self, bg="#3a3a45")
        self.title_frame.pack(fill=tk.X, pady=(5, 0))

        self.toggle_btn = tk.Label(self.title_frame, text="[-] " + title if expanded_default else "[+] " + title,
                                   bg="#3a3a45", fg=TEXT_COLOR, font=("Arial", 10, "bold"), anchor="w", padx=10, pady=5,
                                   cursor="hand2")
        self.toggle_btn.pack(fill=tk.X)
        self.toggle_btn.bind("<Button-1>", self.toggle)

        # Content frame
        self.content_frame = tk.Frame(self, bg=PANEL_COLOR)
        if self.expanded:
            self.content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def toggle(self, event=None):
        self.expanded = not self.expanded
        if self.expanded:
            self.toggle_btn.config(text=self.toggle_btn.cget("text").replace("[+]", "[-]"))
            self.content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        else:
            self.toggle_btn.config(text=self.toggle_btn.cget("text").replace("[-]", "[+]"))
            self.content_frame.pack_forget()


# ==========================================
# HELPER: Scrollable Frame
# ==========================================
class ScrollableFrame(tk.Frame):
    """A frame that can be scrolled vertically."""

    def __init__(self, parent, bg=PANEL_COLOR, *args, **kwargs):
        super().__init__(parent, bg=bg, *args, **kwargs)

        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner_frame = tk.Frame(self.canvas, bg=bg)

        self.inner_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.inner_frame, anchor="nw", width=300)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Mouse wheel binding
        self.bind_mousewheel()

    def bind_mousewheel(self):
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.canvas.bind("<MouseWheel>", _on_mousewheel)
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))


# ==========================================
# MAIN APPLICATION
# ==========================================
class ProceduralSequencerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Graph Soundtrack Engine - Breakcore & Auto-Save")
        self.grid_size = 60

        self.nodes = {}
        self.node_groups = []
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
        self.default_instrument = INSTRUMENTS[0] if INSTRUMENTS else "Handpan"
        self.cam_x, self.cam_y = 0, 0
        self.zoom = 1.0
        self.drag_mode = None
        self.drag_start_id = None
        self.mouse_down_w = (0, 0)
        self.mouse_w = (0, 0)
        self.selection_rect = None

        self.advanced_mode = tk.BooleanVar(value=False)
        self.global_bpm = tk.DoubleVar(value=140.0)

        self.active_channels = {}
        self.choke_lock = threading.Lock()

        self.scheduler = AudioScheduler(self)
        self.scheduler.start()

        self._setup_ui()
        self._bind_events()
        self.update_settings_ui()
        self.render_loop()

    # ------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------
    def _setup_ui(self):
        self.main_frame = tk.Frame(self.root, bg=BG_COLOR)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # ----- Toolbar with instrument palette -----
        self.toolbar = tk.Frame(self.main_frame, bg="#2a2a35", height=40)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)
        self.toolbar.pack_propagate(False)

        tk.Label(self.toolbar, text="Instrument:", fg=TEXT_COLOR, bg="#2a2a35",
                 font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(10, 5))

        self.instrument_buttons = {}
        for inst in INSTRUMENTS:
            btn = tk.Button(self.toolbar, text=inst, bg="#444", fg="white",
                            relief=tk.FLAT, padx=8, pady=2,
                            command=lambda i=inst: self.set_default_instrument(i))
            btn.pack(side=tk.LEFT, padx=2)
            self.instrument_buttons[inst] = btn
        self._highlight_instrument_button(self.default_instrument)

        # Optional dropdown (kept for compatibility)
        tk.Label(self.toolbar, text="or", fg="#888", bg="#2a2a35").pack(side=tk.LEFT, padx=5)
        self.current_tool_var = tk.StringVar(value=self.default_instrument)
        self.tool_dropdown = ttk.Combobox(self.toolbar, textvariable=self.current_tool_var,
                                          values=INSTRUMENTS, state="readonly", width=12)
        self.tool_dropdown.pack(side=tk.LEFT, padx=5)
        self.tool_dropdown.bind("<<ComboboxSelected>>",
                                lambda e: self.set_default_instrument(self.current_tool_var.get()))

        # ----- Canvas -----
        self.canvas = tk.Canvas(self.main_frame, bg=BG_COLOR, highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ----- Right panel with notebook -----
        self.panel = tk.Frame(self.main_frame, bg=PANEL_COLOR, width=320)
        self.panel.pack(side=tk.RIGHT, fill=tk.Y)
        self.panel.pack_propagate(False)

        notebook = ttk.Notebook(self.panel)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Tab 1: Node Properties
        self.props_tab = tk.Frame(notebook, bg=PANEL_COLOR)
        notebook.add(self.props_tab, text="Node")
        self._build_properties_tab()

        # Tab 2: Groups & Schematics
        self.groups_tab = tk.Frame(notebook, bg=PANEL_COLOR)
        notebook.add(self.groups_tab, text="Groups")
        self._build_groups_tab()

        # Tab 3: Global Settings
        self.global_tab = tk.Frame(notebook, bg=PANEL_COLOR)
        notebook.add(self.global_tab, text="Global")
        self._build_global_tab()

        # ----- Status bar -----
        self.status_bar = tk.Label(self.root, text="Ready", bd=1, relief=tk.SUNKEN,
                                   anchor=tk.W, bg="#2a2a35", fg=TEXT_COLOR)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _build_properties_tab(self):
        """Fill the Node Properties tab with scrollable controls."""
        scroll = ScrollableFrame(self.props_tab, bg=PANEL_COLOR)
        scroll.pack(fill=tk.BOTH, expand=True)
        content = scroll.inner_frame

        # UI variables for node properties
        self.ui_vars = {k: tk.StringVar() if k in ["note", "instrument", "mode"] else tk.DoubleVar() for k in
                        ["note", "instrument", "mode", "length", "volume", "latency_self", "latency_out",
                         "choke_group"]}
        self.ui_vars["start_on_flag"] = tk.BooleanVar()

        # Placeholder when no node selected
        self.empty_label = tk.Label(content, text="\nSelect a node to view properties",
                                    fg="#777", bg=PANEL_COLOR, font=("Arial", 10, "italic"))
        self.empty_label.pack(pady=20)

        # Node properties container (initially hidden)
        self.node_props_parent = tk.Frame(content, bg=PANEL_COLOR)

        # --- Basics ---
        basic_pane = CollapsiblePane(self.node_props_parent, "Node: Basics", True)
        basic_pane.pack(fill=tk.X, padx=5, pady=2)

        tk.Label(basic_pane.content_frame, text="Note", fg="#aaa", bg=PANEL_COLOR).pack(anchor="w")
        self.note_dropdown = ttk.Combobox(basic_pane.content_frame, textvariable=self.ui_vars["note"],
                                          values=self.get_current_scale(), state="readonly")
        self.note_dropdown.pack(fill=tk.X, pady=(0, 5))
        self.note_dropdown.bind("<<ComboboxSelected>>", lambda e: self.apply_settings())

        tk.Label(basic_pane.content_frame, text="Instrument", fg="#aaa", bg=PANEL_COLOR).pack(anchor="w")
        inst_menu = ttk.Combobox(basic_pane.content_frame, textvariable=self.ui_vars["instrument"],
                                 values=INSTRUMENTS, state="readonly")
        inst_menu.pack(fill=tk.X, pady=(0, 5))
        inst_menu.bind("<<ComboboxSelected>>", lambda e: self.apply_settings())

        tk.Checkbutton(basic_pane.content_frame, text="Flag (Start on Play All)",
                       variable=self.ui_vars["start_on_flag"],
                       bg=PANEL_COLOR, fg="#aaa", selectcolor="#222", command=self.apply_settings).pack(anchor="w",
                                                                                                        pady=(5, 0))

        # --- Timing & Mix ---
        timing_pane = CollapsiblePane(self.node_props_parent, "Node: Timing & Mix", True)
        timing_pane.pack(fill=tk.X, padx=5, pady=2)

        sliders1 = [("Length (Beats)", "length", 0.05, 4.0),
                    ("Volume", "volume", 0.0, 1.0),
                    ("Self Latency (Beats)", "latency_self", 0.0, 4.0),
                    ("Out Latency (Beats)", "latency_out", 0.0, 4.0)]
        for label, key, low, high in sliders1:
            tk.Label(timing_pane.content_frame, text=label, fg="#aaa", bg=PANEL_COLOR).pack(anchor="w")
            tk.Scale(timing_pane.content_frame, variable=self.ui_vars[key], from_=low, to=high, resolution=0.05,
                     orient=tk.HORIZONTAL, bg=PANEL_COLOR, fg="white", highlightthickness=0, bd=0,
                     command=lambda _: self.apply_settings()).pack(fill=tk.X, pady=(0, 5))

        # --- Advanced Routing ---
        routing_pane = CollapsiblePane(self.node_props_parent, "Node: Advanced Routing", False)
        routing_pane.pack(fill=tk.X, padx=5, pady=2)

        tk.Label(routing_pane.content_frame, text="Routing Mode", fg="#aaa", bg=PANEL_COLOR).pack(anchor="w")
        mode_menu = ttk.Combobox(routing_pane.content_frame, textvariable=self.ui_vars["mode"],
                                 values=("Poly", "Splitter"), state="readonly")
        mode_menu.pack(fill=tk.X, pady=(0, 5))
        mode_menu.bind("<<ComboboxSelected>>", lambda e: self.apply_settings())

        tk.Label(routing_pane.content_frame, text="Choke Group (0=Off)", fg="#aaa", bg=PANEL_COLOR).pack(anchor="w")
        tk.Scale(routing_pane.content_frame, variable=self.ui_vars["choke_group"], from_=0, to=8, resolution=1.0,
                 orient=tk.HORIZONTAL, bg=PANEL_COLOR, fg="white", highlightthickness=0, bd=0,
                 command=lambda _: self.apply_settings()).pack(fill=tk.X)

    def _build_groups_tab(self):
        """Fill the Groups & Schematics tab."""
        scroll = ScrollableFrame(self.groups_tab, bg=PANEL_COLOR)
        scroll.pack(fill=tk.BOTH, expand=True)
        content = scroll.inner_frame

        # Group management
        group_frame = tk.Frame(content, bg=PANEL_COLOR)
        group_frame.pack(fill=tk.X, pady=(10, 5), padx=10)
        tk.Button(group_frame, text="Group (Ctrl+G)", bg="#445", fg="white", font=("Arial", 8),
                  relief=tk.FLAT, command=self.create_group).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        tk.Button(group_frame, text="Ungroup (Ctrl+U)", bg="#544", fg="white", font=("Arial", 8),
                  relief=tk.FLAT, command=self.ungroup).pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(2, 0))

        # Schematics section
        tk.Label(content, text="Schematics & Blueprints", bg=PANEL_COLOR,
                 fg=ACCENT_COLOR, font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(15, 5))
        tk.Button(content, text="Open Schematics Window", bg="#6a4c93", fg="white",
                  font=("Arial", 9, "bold"), relief=tk.FLAT, pady=5,
                  command=self.open_schematic_window).pack(fill=tk.X, padx=10, pady=2)
        tk.Button(content, text="Save Selection as Schematic", bg="#008080", fg="white",
                  font=("Arial", 9), relief=tk.FLAT, pady=5,
                  command=self.save_selection_as_schematic).pack(fill=tk.X, padx=10, pady=2)
        tk.Button(content, text="Load JSON Array from File...", bg="#2b2b3b", fg="white",
                  font=("Arial", 9), relief=tk.FLAT, pady=5,
                  command=self.load_schematic_file).pack(fill=tk.X, padx=10, pady=2)

        # Advanced mode toggle
        tk.Checkbutton(content, text="Advanced Mode (Sharps #)", variable=self.advanced_mode,
                       bg=PANEL_COLOR, fg="#aaa", selectcolor="#222", activebackground=PANEL_COLOR,
                       activeforeground="#fff", command=self.refresh_note_menu).pack(anchor="w", padx=10, pady=(15, 5))

    def _build_global_tab(self):
        """Fill the Global Settings tab."""
        scroll = ScrollableFrame(self.global_tab, bg=PANEL_COLOR)
        scroll.pack(fill=tk.BOTH, expand=True)
        content = scroll.inner_frame

        tk.Label(content, text="GLOBAL BPM", fg=ACCENT_COLOR, bg=PANEL_COLOR,
                 font=("Arial", 9)).pack(anchor="w", padx=10, pady=(10, 0))
        tk.Scale(content, variable=self.global_bpm, from_=60.0, to=300.0, resolution=1.0,
                 orient=tk.HORIZONTAL, bg=PANEL_COLOR, fg="white",
                 highlightthickness=0, bd=0).pack(fill=tk.X, padx=10, pady=(0, 15))

        tk.Button(content, text="Play All (Standard)", font=("Arial", 10, "bold"),
                  bg="#3a3a45", fg=TEXT_COLOR, command=self.trigger_green_flag,
                  relief=tk.FLAT, pady=8).pack(fill=tk.X, padx=10, pady=5)

        # Could add more global controls here later

    # ------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------
    def _highlight_instrument_button(self, active_inst):
        """Highlight the active instrument button."""
        for inst, btn in self.instrument_buttons.items():
            if inst == active_inst:
                btn.config(bg="#5a5a6a", relief=tk.SUNKEN)
            else:
                btn.config(bg="#444", relief=tk.FLAT)

    def set_default_instrument(self, instrument):
        """Set default instrument from button or dropdown."""
        self.default_instrument = instrument
        self.current_tool_var.set(instrument)
        self._highlight_instrument_button(instrument)

    # ------------------------------------------------------------
    # Existing methods (unchanged except for minor updates)
    # ------------------------------------------------------------
    def load_user_schematics(self):
        if os.path.exists(USER_SCHEMATICS_FILE):
            try:
                with open(USER_SCHEMATICS_FILE, 'r') as f:
                    user_data = json.load(f)
                    self.schematics.update(user_data)
            except Exception:
                pass

    def save_user_schematics(self):
        custom_schematics = {k: v for k, v in self.schematics.items() if k not in PRESETS}
        try:
            with open(USER_SCHEMATICS_FILE, 'w') as f:
                json.dump(custom_schematics, f, indent=4)
        except Exception:
            pass

    def open_schematic_window(self):
        if self.schematic_window is not None and self.schematic_window.winfo_exists():
            self.schematic_window.lift()
            return

        self.schematic_window = tk.Toplevel(self.root)
        self.schematic_window.title("Schematic Inventory")
        self.schematic_window.geometry("300x500")
        self.schematic_window.configure(bg="#1a1a22")
        self.schematic_window.attributes('-topmost', True)

        tk.Label(self.schematic_window, text="Inventory", fg=ACCENT_COLOR, bg="#1a1a22",
                 font=("Arial", 14, "bold")).pack(pady=15)

        canvas = tk.Canvas(self.schematic_window, bg="#1a1a22", highlightthickness=0)
        scrollbar = tk.Scrollbar(self.schematic_window, orient="vertical", command=canvas.yview)
        self.inv_buttons_frame = tk.Frame(canvas, bg="#1a1a22")

        self.inv_buttons_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        canvas.create_window((0, 0), window=self.inv_buttons_frame, anchor="nw", width=280)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="top", fill="both", expand=True, padx=5)
        scrollbar.pack(side="right", fill="y")

        self.refresh_inventory_ui()

        footer = tk.Frame(self.schematic_window, bg="#1a1a22")
        footer.pack(side=tk.BOTTOM, fill=tk.X, pady=15, padx=15)
        tk.Button(footer, text="Save Selection as Schematic", bg="#008080", fg="white", relief=tk.FLAT,
                  command=self.save_selection_as_schematic, pady=5).pack(fill=tk.X, pady=(0, 10))
        tk.Button(footer, text="Load JSON Array from File...", bg="#2b2b3b", fg="white", relief=tk.FLAT,
                  command=self.load_schematic_file).pack(fill=tk.X)

    def refresh_inventory_ui(self):
        if not hasattr(self, 'inv_buttons_frame') or not self.inv_buttons_frame.winfo_exists():
            return
        for widget in self.inv_buttons_frame.winfo_children():
            widget.destroy()
        for name in self.schematics.keys():
            tk.Button(self.inv_buttons_frame, text=name, bg="#333", fg="white", relief=tk.FLAT,
                      command=lambda n=name: self.set_active_schematic(n)).pack(fill=tk.X, pady=2, padx=5)

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
            new_id = self.create_node(snapped_rx + data.get("rel_x", 0), snapped_ry + data.get("rel_y", 0))
            id_map[i] = new_id
            node = self.nodes[new_id]
            for k in ["note", "instrument", "mode", "latency_out", "volume", "start_on_flag", "choke_group", "length"]:
                val = data.get(k, data.get(
                    "lat" if k == "latency_out" else "vol" if k == "volume" else "start" if k == "start_on_flag" else "inst" if k == "instrument" else k,
                    node[k]))
                node[k] = val

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
            return
        name = simpledialog.askstring("Save Schematic", "Enter schematic name:", parent=self.root)
        if not name:
            return

        xs = [self.nodes[n]["x"] for n in self.selected_nodes]
        ys = [self.nodes[n]["y"] for n in self.selected_nodes]
        cx, cy = self.snap(sum(xs) / len(xs)), self.snap(sum(ys) / len(ys))

        schema = []
        id_to_idx = {nid: i for i, nid in enumerate(self.selected_nodes)}

        for nid in self.selected_nodes:
            org = self.nodes[nid]
            c_child = [id_to_idx[c] for c in org["children"] if c in self.selected_nodes]
            schema.append({
                "rel_x": org["x"] - cx, "rel_y": org["y"] - cy,
                "note": org["note"], "instrument": org["instrument"],
                "length": org["length"], "volume": org["volume"],
                "latency_out": org["latency_out"], "start_on_flag": org.get("start_on_flag", False),
                "choke_group": org.get("choke_group", 0), "mode": org.get("mode", "Poly"),
                "children": c_child
            })

        self.schematics[name] = schema
        self.save_user_schematics()
        self.refresh_inventory_ui()

    def load_schematic_file(self):
        path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if path:
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self.schematics[os.path.splitext(os.path.basename(path))[0]] = data
                elif isinstance(data, dict):
                    self.schematics.update(data)
                self.save_user_schematics()
                self.refresh_inventory_ui()
            except Exception:
                pass

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
            "latency_self": 0.0, "latency_out": 0.5,
            "start_on_flag": False, "choke_group": 0, "children": [],
            "anim_scale": 1.0, "flash": 0.0, "mode": "Poly", "last_child_idx": 0
        }

        if not override_data and parent_id is not None and parent_id in self.nodes:
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

    def select_note_from_menu(self, selected_note):
        self.ui_vars["note"].set(selected_note)
        self.apply_settings()

    def refresh_note_menu(self):
        scale = self.get_current_scale()
        self.note_dropdown['values'] = scale
        if self.ui_vars["note"].get() not in scale:
            self.ui_vars["note"].set(scale[0] if scale else "C4")

    def update_settings_ui(self):
        if len(self.selected_nodes) >= 1:
            self.empty_label.pack_forget()
            self.node_props_parent.pack(fill=tk.BOTH, expand=True)
            node = self.nodes[list(self.selected_nodes)[0]]
            for k, v in self.ui_vars.items():
                if k == "note":
                    notes = {self.nodes[n]["note"] for n in self.selected_nodes}
                    v.set(node["note"] if len(notes) == 1 else "—")
                else:
                    v.set(node.get(k, False if k == "start_on_flag" else 0 if k == "choke_group" else node.get(k, "")))
        else:
            self.node_props_parent.pack_forget()
            self.empty_label.pack(pady=20)

    def apply_settings(self, *args):
        if not self.selected_nodes:
            return
        for nid in self.selected_nodes:
            for k, v in self.ui_vars.items():
                if k == "note" and v.get() == "—":
                    continue
                self.nodes[nid][k] = v.get()

    def save_project(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if path:
            with open(path, 'w') as f:
                json.dump({
                    "bpm": self.global_bpm.get(),
                    "nodes": self.nodes,
                    "groups": self.node_groups
                }, f, indent=4)

    def load_project(self):
        path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if path:
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                self.nodes.clear()
                self.selected_nodes.clear()
                self.node_groups = data.get("groups", [])

                nodes_data = data.get("nodes", data) if isinstance(data, dict) else data
                if isinstance(data, dict) and "bpm" in data:
                    self.global_bpm.set(data["bpm"])

                for k, v in nodes_data.items():
                    v.update({"anim_scale": 1.0, "flash": 0.0, "start_on_flag": v.get("start_on_flag", False),
                              "mode": v.get("mode", "Poly"), "last_child_idx": v.get("last_child_idx", 0),
                              "choke_group": v.get("choke_group", 0)})
                    if v["note"] not in NOTE_FREQS:
                        v["note"] = "C4"
                    self.nodes[int(k)] = v
                self.node_counter = max(self.nodes.keys()) if self.nodes else 0
                self.update_settings_ui()
            except Exception:
                pass

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

        self.root.bind("<Control-g>", self.create_group)
        self.root.bind("<Control-u>", self.ungroup)

        for i in range(1, 10):
            self.root.bind(str(i), lambda e, idx=i - 1: self.set_default_instrument(
                INSTRUMENTS[idx] if idx < len(INSTRUMENTS) else self.default_instrument))

    def on_mouse_move(self, event):
        self.mouse_w = self.s2w(event.x, event.y)
        self.hovered_node = self.get_node_at(self.mouse_w[0], self.mouse_w[1])
        self.hovered_wire = self.get_wire_at(self.mouse_w[0], self.mouse_w[1]) if not self.hovered_node else None
        self.update_status()

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
            node["note"] = scale[(idx + delta) % len(scale)]
            self.scheduler.schedule(0, nid, False)
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
            if not (event.state & 0x0001):  # Shift key not pressed
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
            self.selection_rect = (self.mouse_down_w[0], self.mouse_down_w[1], self.mouse_w[0], self.mouse_w[1])

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
                self.nodes[nid]["x"], self.nodes[nid]["y"] = self.snap(self.nodes[nid]["x"]), self.snap(
                    self.nodes[nid]["y"])
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
            return self.set_active_schematic(None)

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

    def create_group(self, event=None):
        if not self.selected_nodes:
            return
        colors = ["#ff595e", "#ffca3a", "#8ac926", "#1982c4", "#6a4c93"]
        self.node_groups.append({
            "nodes": list(self.selected_nodes),
            "color": random.choice(colors),
            "name": f"Group {len(self.node_groups) + 1}"
        })

    def ungroup(self, event=None):
        if not self.selected_nodes:
            return
        for g in self.node_groups[:]:
            if any(nid in g["nodes"] for nid in self.selected_nodes):
                self.node_groups.remove(g)

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
                "old_id": nid, "rel_x": org["x"] - cx, "rel_y": org["y"] - cy,
                "note": org["note"], "instrument": org["instrument"], "length": org["length"],
                "volume": org["volume"], "latency_self": org["latency_self"], "latency_out": org["latency_out"],
                "start_on_flag": org.get("start_on_flag", False), "children": c_child,
                "mode": org.get("mode", "Poly"), "choke_group": org.get("choke_group", 0)
            })

    def paste_selection(self, event=None):
        if not self.clipboard:
            return
        id_map, new_selection = {}, set()
        for item in self.clipboard:
            new_id = self.create_node(self.mouse_w[0] + item["rel_x"], self.mouse_w[1] + item["rel_y"])
            id_map[item["old_id"]] = new_id
            for k in ["note", "instrument", "length", "volume", "latency_self", "latency_out", "start_on_flag", "mode",
                      "choke_group"]:
                self.nodes[new_id][k] = item[k]
            new_selection.add(new_id)
        for item in self.clipboard:
            for old_child in item["children"]:
                self.nodes[id_map[item["old_id"]]]["children"].append(id_map[old_child])
        self.selected_nodes = new_selection
        self.update_settings_ui()

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
            bps = self.global_bpm.get() / 60.0
            sec_per_beat = 1.0 / bps if bps > 0 else 1.0
            self.scheduler.schedule(self.nodes[nid].get("latency_self", 0) * sec_per_beat, nid, endless_mode=False)

    def update_status(self):
        mode = "Placing" if self.active_schematic else "Select"
        self.status_bar.config(text=f"Mode: {mode} | Zoom: {self.zoom:.2f} | Selected: {len(self.selected_nodes)}")

    def render_loop(self):
        for nid, d in self.nodes.items():
            target_scale = 1.15 if nid == self.hovered_node else 1.0
            if nid in self.selected_nodes:
                target_scale = 1.1
            d["anim_scale"] += (target_scale - d["anim_scale"]) * 0.2
            if d["flash"] > 0.01:
                d["flash"] += (0 - d["flash"]) * 0.1

        self.canvas.delete("all")
        g_size = self.grid_size * self.zoom
        offset_x, offset_y = -(self.cam_x * self.zoom) % g_size, -(self.cam_y * self.zoom) % g_size

        for x in np.arange(offset_x, self.canvas.winfo_width() + g_size, g_size):
            self.canvas.create_line(x, 0, x, self.canvas.winfo_height(), fill=GRID_COLOR)
        for y in np.arange(offset_y, self.canvas.winfo_height() + g_size, g_size):
            self.canvas.create_line(0, y, self.canvas.winfo_width(), y, fill=GRID_COLOR)

        # Draw permanent group boxes
        for group in self.node_groups:
            valid_nodes = [nid for nid in group["nodes"] if nid in self.nodes]
            if not valid_nodes:
                continue

            xs = [self.nodes[nid]["x"] for nid in valid_nodes]
            ys = [self.nodes[nid]["y"] for nid in valid_nodes]

            padding = 40
            min_x, max_x = min(xs) - padding, max(xs) + padding
            min_y, max_y = min(ys) - padding, max(ys) + padding

            sx1, sy1 = self.w2s(min_x, min_y)
            sx2, sy2 = self.w2s(max_x, max_y)

            self.canvas.create_rectangle(sx1, sy1, sx2, sy2, outline=group["color"], width=2 * self.zoom, dash=(4, 4),
                                         fill="#22222b", stipple="gray25")
            self.canvas.create_text(sx1, sy1 - 10 * self.zoom, text=group["name"], fill=group["color"], anchor=tk.SW,
                                    font=("Arial", int(10 * self.zoom), "bold"))

        # Draw wires
        for nid, d in self.nodes.items():
            for cid in d["children"]:
                if cid in self.nodes:
                    sx1, sy1 = self.w2s(d["x"], d["y"])
                    sx2, sy2 = self.w2s(self.nodes[cid]["x"], self.nodes[cid]["y"])
                    is_hovered = (self.hovered_wire == (nid, cid))
                    is_selected = (self.selected_wire == (nid, cid))
                    base_wire = "#445"
                    color = ACCENT_COLOR if is_selected else ("#aaa" if is_hovered else base_wire)
                    width = (6 if is_selected or is_hovered else 4) * self.zoom

                    dash_pattern = (4, 4) if d.get("mode") == "Splitter" and not is_hovered else None
                    self.canvas.create_line(sx1, sy1, sx2, sy2, fill=color, width=width, dash=dash_pattern)

        # Draw pending wire
        if self.drag_mode == "wire" and self.drag_start_id in self.nodes:
            sx1, sy1 = self.w2s(self.nodes[self.drag_start_id]["x"], self.nodes[self.drag_start_id]["y"])
            sx2, sy2 = self.w2s(self.mouse_w[0], self.mouse_w[1])
            self.canvas.create_line(sx1, sy1, sx2, sy2, fill="white", dash=(4, 4), width=2 * self.zoom)

        # Draw nodes
        for nid, d in self.nodes.items():
            r = 20 * self.zoom * d["anim_scale"]
            sx, sy = self.w2s(d["x"], d["y"])
            base_color = NOTE_COLORS.get(d["note"][0], "#ccc")

            inst = d["instrument"]
            style = INSTRUMENT_STYLES.get(inst, {"shape": "circle", "size_mult": 1.0})
            r *= style["size_mult"]
            shape_type = style["shape"]

            r_flash = r + (10 * d["flash"] * self.zoom)
            if d["flash"] > 0.1:
                self.canvas.create_oval(sx - r_flash, sy - r_flash, sx + r_flash, sy + r_flash, fill="",
                                        outline=base_color, width=2 * self.zoom)

            fill_color = "white" if d["flash"] > 0.5 else base_color
            outline = "#ffffff" if nid in self.selected_nodes else "#111"
            w = 4 if nid in self.selected_nodes else 2

            if shape_type == "circle":
                self.canvas.create_oval(sx - r, sy - r, sx + r, sy + r, fill=fill_color, outline=outline, width=w)
            elif shape_type == "rectangle":
                self.canvas.create_rectangle(sx - r, sy - r, sx + r, sy + r, fill=fill_color, outline=outline, width=w)
            elif shape_type == "polygon_hex":
                points = [sx, sy - r, sx + r, sy + r * 0.8, sx - r, sy + r * 0.8]
                self.canvas.create_polygon(points, fill=fill_color, outline=outline, width=w)
            elif shape_type == "polygon_diamond":
                points = [sx, sy - r, sx + r, sy, sx, sy + r, sx - r, sy]
                self.canvas.create_polygon(points, fill=fill_color, outline=outline, width=w)

            if d.get("start_on_flag", False):
                flag_size = 10 * self.zoom
                self.canvas.create_polygon(sx - r - 2, sy - r, sx - r + flag_size, sy - r, sx - r, sy - r - flag_size,
                                           fill="#22aa22", outline="black", width=1)
                self.canvas.create_line(sx - r - 2, sy - r, sx - r - 2, sy - r - flag_size, fill="black", width=1)

            self.canvas.create_oval(sx - 10 * self.zoom, sy - 10 * self.zoom, sx + 10 * self.zoom, sy + 10 * self.zoom,
                                    outline="black", width=1, stipple="gray50")

            display_text = f"{d['note']} (S)" if d.get("mode") == "Splitter" else d["note"]
            self.canvas.create_text(sx, sy, text=display_text, fill="black", font=("Arial", int(9 * self.zoom), "bold"))

            if d.get("choke_group", 0) > 0:
                self.canvas.create_text(sx + r - 5, sy - r + 5, text=str(int(d["choke_group"])), fill="white",
                                        font=("Arial", int(8 * self.zoom), "bold"))

        if self.selection_rect:
            sx1, sy1 = self.w2s(self.selection_rect[0], self.selection_rect[1])
            sx2, sy2 = self.w2s(self.selection_rect[2], self.selection_rect[3])
            self.canvas.create_rectangle(sx1, sy1, sx2, sy2, outline=ACCENT_COLOR, dash=(4, 4))

        if self.active_schematic:
            self.canvas.create_text(20, 70, anchor=tk.NW,
                                    text=f"Placing Schematic: {self.active_schematic} (Right-Click to Cancel)",
                                    fill=ACCENT_COLOR, font=("Arial", 12, "bold"))

        self.update_status()
        self.root.after(16, self.render_loop)


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1200x750")
    app = ProceduralSequencerApp(root)
    root.mainloop()