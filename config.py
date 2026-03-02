# Constants and configurations
BG_COLOR = "#1e1e24"
PANEL_COLOR = "#2b2b36"
TEXT_COLOR = "#e0e0e0"
ACCENT_COLOR = "#00bfff"
ENDLESS_COLOR = "#4dff88"
GRID_COLOR = "#2a2a35"
USER_SCHEMATICS_FILE = "user_schematics.json"

NOTE_FREQS = {
    "C3": 130.81, "C#3": 138.59, "D3": 146.83, "D#3": 155.56, "E3": 164.81, "F3": 174.61, "F#3": 185.00, "G3": 196.00,
    "G#3": 207.65, "A3": 220.00, "A#3": 233.08, "B3": 246.94,
    "C4": 261.63, "C#4": 277.18, "D4": 293.66, "D#4": 311.13, "E4": 329.63, "F4": 349.23, "F#4": 369.99, "G4": 392.00,
    "G#4": 415.30, "A4": 440.00, "A#4": 466.16, "B4": 493.88,
    "C5": 523.25, "C#5": 554.37, "D5": 587.33, "D#5": 622.25, "E5": 659.25, "G5": 783.99, "A5": 880.00
}

NOTE_COLORS = {
    "C": "#ff595e", "D": "#ffca3a", "E": "#8ac926", "F": "#1982c4",
    "G": "#6a4c93", "A": "#ff924c", "B": "#ff9be5"
}

INSTRUMENTS = [
    "Music Box", "Organ", "Sine Wave", "Sawtooth", "Square", "Pluck", "Handpan",
    "Reese Bass", "Gabe Kick", "Synth Snare", "Glitch Noise",
    "Kick", "Snare", "Hi-Hat"
]

# Defines how each instrument is rendered in the node graph
# Available shapes: "circle", "rectangle", "polygon_hex", "polygon_diamond"
INSTRUMENT_STYLES = {
    "Music Box": {"shape": "circle", "size_mult": 1.0},
    "Organ": {"shape": "rectangle", "size_mult": 0.9},
    "Sine Wave": {"shape": "polygon_hex", "size_mult": 1.1},
    "Sawtooth": {"shape": "polygon_diamond", "size_mult": 1.1},
    "Square": {"shape": "rectangle", "size_mult": 0.9},
    "Pluck": {"shape": "circle", "size_mult": 0.8},
    "Handpan": {"shape": "circle", "size_mult": 1.0},
    "Reese Bass": {"shape": "polygon_hex", "size_mult": 1.1},
    "Gabe Kick": {"shape": "rectangle", "size_mult": 0.9},
    "Synth Snare": {"shape": "circle", "size_mult": 1.0},
    "Glitch Noise": {"shape": "rectangle", "size_mult": 0.9},
    "Kick": {"shape": "circle", "size_mult": 1.1},
    "Snare": {"shape": "rectangle", "size_mult": 0.8},
    "Hi-Hat": {"shape": "polygon_diamond", "size_mult": 0.7}
}

PRESETS = {
    "Gmaj7 Poly Chord": [
        {"rel_x": 0, "rel_y": -60, "note": "G3", "inst": "Handpan", "mode": "Poly", "lat": 1.0, "children": [1, 2, 3]},
        {"rel_x": 0, "rel_y": 0, "note": "D4", "inst": "Handpan", "mode": "Poly", "lat": 1.0, "children": []},
        {"rel_x": -60, "rel_y": 0, "note": "B3", "inst": "Handpan", "mode": "Poly", "lat": 1.0, "children": []},
        {"rel_x": 60, "rel_y": 0, "note": "F#4", "inst": "Handpan", "mode": "Poly", "lat": 1.0, "children": []}
    ]
}