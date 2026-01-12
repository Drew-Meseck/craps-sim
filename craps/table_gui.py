"""
Canvas-based craps table GUI with draggable chips.
"""
import tkinter as tk
from tkinter import messagebox
from typing import Optional
from dataclasses import dataclass
import math

from .game import CrapsGame, TableRules, DiceRoll, GamePhase
from .bets import (
    BetManager, BetResult, BetStatus,
    PassLineBet, DontPassBet, ComeBet, DontComeBet,
    PlaceBet, FieldBet, OddsBet, LayOddsBet,
    AnyCrapsBet, AnySevenBet, HornBet, HardwayBet
)
from .bankroll import BankrollTracker


# Color scheme - Purple theme
COLORS = {
    'felt': '#2d1b4e',           # Dark purple felt
    'felt_light': '#3d2a5c',     # Lighter purple for contrast
    'border': '#c9a227',         # Gold borders
    'text': '#ffffff',           # White text
    'text_accent': '#ffd700',    # Gold accent text
    'text_red': '#ff4444',       # Red text for certain areas
    'pass_line': '#4a3366',      # Pass line area
    'field': '#3d2a5c',          # Field area
    'come': '#2d1b4e',           # Come area
    'props': '#1a0f2e',          # Proposition bets area
}

# Chip colors and values
CHIP_COLORS = {
    1: '#ffffff',      # White - $1
    5: '#cc0000',      # Red - $5
    25: '#00aa00',     # Green - $25
    100: '#000000',    # Black - $100
    500: '#8b008b',    # Purple - $500
}

CHIP_VALUES = [1, 5, 25, 100, 500]


@dataclass
class BettingSpot:
    """Defines a betting area on the table."""
    name: str
    bet_type: str
    x: int
    y: int
    width: int
    height: int
    chips: list  # List of chip values placed here

    def contains(self, px: int, py: int) -> bool:
        """Check if point is within this betting spot."""
        return (self.x <= px <= self.x + self.width and
                self.y <= py <= self.y + self.height)

    def center(self) -> tuple[int, int]:
        """Get center point of this spot."""
        return (self.x + self.width // 2, self.y + self.height // 2)

    @property
    def total_bet(self) -> int:
        """Total value of chips on this spot."""
        return sum(self.chips)


class CrapsTableGUI:
    """Main GUI with canvas-based craps table and draggable chips."""

    # Table dimensions
    TABLE_WIDTH = 1000
    TABLE_HEIGHT = 600

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Craps Simulator")
        self.root.configure(bg='#1a0f2e')

        # Game state
        self.rules = TableRules()
        self.game = CrapsGame(self.rules)
        self.bet_manager = BetManager(self.rules)
        self.bankroll = 1000.0

        # Bankroll tracking
        self.tracker = BankrollTracker(self.bankroll)
        self.tracker.start_session(self.bankroll)

        # Chip being dragged
        self.dragging_chip: Optional[int] = None  # Chip value
        self.drag_chip_id: Optional[int] = None   # Canvas item id
        self.selected_chip_value: int = 5         # Default to $5 chip

        # Place bets working status (during come-out roll)
        # Default OFF during come-out (standard casino rules)
        self.place_bets_working: bool = False

        # Shooter mode - when ON, pass/don't pass can only be placed before point
        # When OFF (non-shooter), can place pass/don't pass anytime
        self.shooter_mode: bool = True

        # Betting spots on the table
        self.betting_spots: list[BettingSpot] = []

        # Come/Don't Come bets that have traveled to a point number
        # Key: point number (4,5,6,8,9,10), Value: list of chip values
        self.come_bets_on_number: dict[int, list[int]] = {}
        self.dont_come_bets_on_number: dict[int, list[int]] = {}

        # Odds on Come/Don't Come bets that have traveled
        self.come_odds_on_number: dict[int, list[int]] = {}
        self.dont_come_odds_on_number: dict[int, list[int]] = {}

        # Graph window reference for live updates
        self.graph_window = None
        self.graph_fig = None
        self.graph_ax = None
        self.graph_canvas = None

        # Setup callbacks
        self._setup_game_callbacks()

        # Build UI
        self._build_ui()
        self._create_betting_spots()
        self._draw_table()
        self._draw_chip_tray()

    def _setup_game_callbacks(self):
        """Register game event callbacks."""
        self.game.on_roll(self._on_roll)
        self.game.on_point_established(self._on_point_established)
        self.game.on_point_won(self._on_point_won)
        self.game.on_seven_out(self._on_seven_out)

    def _build_ui(self):
        """Build the main UI."""
        # Top frame - bankroll and controls
        top_frame = tk.Frame(self.root, bg='#1a0f2e')
        top_frame.pack(fill=tk.X, padx=10, pady=5)

        # Bankroll display frame
        bankroll_frame = tk.Frame(top_frame, bg='#1a0f2e')
        bankroll_frame.pack(side=tk.LEFT, padx=20)

        # Total equity (rack + bets)
        self.total_var = tk.StringVar(value=f"Total: ${self.bankroll:.2f}")
        tk.Label(
            bankroll_frame, textvariable=self.total_var,
            font=('Arial', 14, 'bold'), fg='#ffd700', bg='#1a0f2e'
        ).pack(side=tk.LEFT, padx=(0, 15))

        # Rack (chips in hand)
        self.rack_var = tk.StringVar(value=f"Rack: ${self.bankroll:.2f}")
        tk.Label(
            bankroll_frame, textvariable=self.rack_var,
            font=('Arial', 12), fg='#00ff00', bg='#1a0f2e'
        ).pack(side=tk.LEFT, padx=(0, 15))

        # Bets on table
        self.bets_var = tk.StringVar(value="Bets: $0.00")
        tk.Label(
            bankroll_frame, textvariable=self.bets_var,
            font=('Arial', 12), fg='#ff9900', bg='#1a0f2e'
        ).pack(side=tk.LEFT)

        # Point display
        point_frame = tk.Frame(top_frame, bg='#1a0f2e')
        point_frame.pack(side=tk.LEFT, padx=40)
        tk.Label(point_frame, text="POINT:", fg='white', bg='#1a0f2e',
                 font=('Arial', 12)).pack(side=tk.LEFT)
        self.point_var = tk.StringVar(value="OFF")
        self.point_label = tk.Label(
            point_frame, textvariable=self.point_var,
            font=('Arial', 16, 'bold'), fg='#ffd700', bg='#1a0f2e'
        )
        self.point_label.pack(side=tk.LEFT, padx=5)

        # Roll button
        self.roll_btn = tk.Button(
            top_frame, text="ROLL DICE", font=('Arial', 14, 'bold'),
            bg='#cc0000', fg='white', command=self._roll_dice,
            width=12, height=1, relief=tk.RAISED, bd=3
        )
        self.roll_btn.pack(side=tk.RIGHT, padx=20)

        # Clear bets button
        clear_btn = tk.Button(
            top_frame, text="Clear Bets", font=('Arial', 10),
            bg='#4a3366', fg='white', command=self._clear_all_bets,
            width=10
        )
        clear_btn.pack(side=tk.RIGHT, padx=10)

        # Shooter mode toggle
        self.shooter_mode_var = tk.StringVar(value="Shooter: ON")
        self.shooter_mode_btn = tk.Button(
            top_frame, textvariable=self.shooter_mode_var, font=('Arial', 10),
            bg='#00aa00', fg='white', command=self._toggle_shooter_mode,
            width=12
        )
        self.shooter_mode_btn.pack(side=tk.RIGHT, padx=10)

        # Place bets working toggle
        self.place_working_var = tk.StringVar(value="Place Bets: OFF")
        self.place_working_btn = tk.Button(
            top_frame, textvariable=self.place_working_var, font=('Arial', 10),
            bg='#cc0000', fg='white', command=self._toggle_place_bets_working,
            width=14
        )
        self.place_working_btn.pack(side=tk.RIGHT, padx=10)

        # Main canvas for the table
        canvas_frame = tk.Frame(self.root, bg='#1a0f2e')
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.canvas = tk.Canvas(
            canvas_frame,
            width=self.TABLE_WIDTH,
            height=self.TABLE_HEIGHT,
            bg=COLORS['felt'],
            highlightthickness=2,
            highlightbackground=COLORS['border']
        )
        self.canvas.pack()

        # Bind mouse events for chip dragging
        self.canvas.bind('<Button-1>', self._on_click)
        self.canvas.bind('<B1-Motion>', self._on_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_release)
        self.canvas.bind('<Button-3>', self._on_right_click)  # Remove chips
        self.canvas.bind('<Motion>', self._on_mouse_move)  # Hover highlighting

        # Bottom frame - chip tray and log
        bottom_frame = tk.Frame(self.root, bg='#1a0f2e')
        bottom_frame.pack(fill=tk.X, padx=10, pady=5)

        # Chip selector
        chip_frame = tk.LabelFrame(bottom_frame, text="Select Chip",
                                   bg='#1a0f2e', fg='white', font=('Arial', 10))
        chip_frame.pack(side=tk.LEFT, padx=10, pady=5)

        self.chip_buttons = {}
        for value in CHIP_VALUES:
            color = CHIP_COLORS[value]
            fg_color = 'white' if value == 100 else 'black'
            if value == 1:
                fg_color = 'black'
            btn = tk.Button(
                chip_frame, text=f"${value}", width=6, height=2,
                bg=color, fg=fg_color, font=('Arial', 10, 'bold'),
                command=lambda v=value: self._select_chip(v),
                relief=tk.RAISED, bd=3
            )
            btn.pack(side=tk.LEFT, padx=3, pady=5)
            self.chip_buttons[value] = btn

        # Highlight default selected chip
        self._select_chip(5)

        # Session stats frame
        session_frame = tk.LabelFrame(bottom_frame, text="Session Stats",
                                      bg='#1a0f2e', fg='white', font=('Arial', 10))
        session_frame.pack(side=tk.LEFT, padx=10, pady=5)

        self.stats_rolls_var = tk.StringVar(value="Rolls: 0")
        self.stats_shooters_var = tk.StringVar(value="Shooters: 1")
        self.stats_net_var = tk.StringVar(value="Net: $0.00")

        tk.Label(session_frame, textvariable=self.stats_rolls_var,
                 fg='white', bg='#1a0f2e', font=('Arial', 9)).pack(anchor='w', padx=5)
        tk.Label(session_frame, textvariable=self.stats_shooters_var,
                 fg='white', bg='#1a0f2e', font=('Arial', 9)).pack(anchor='w', padx=5)
        self.stats_net_label = tk.Label(session_frame, textvariable=self.stats_net_var,
                                        fg='#00ff00', bg='#1a0f2e', font=('Arial', 9, 'bold'))
        self.stats_net_label.pack(anchor='w', padx=5)

        # Shooter stats frame
        shooter_frame = tk.LabelFrame(bottom_frame, text="Current Shooter",
                                      bg='#1a0f2e', fg='white', font=('Arial', 10))
        shooter_frame.pack(side=tk.LEFT, padx=10, pady=5)

        self.shooter_num_var = tk.StringVar(value="Shooter #1")
        self.shooter_rolls_var = tk.StringVar(value="Rolls: 0")
        self.shooter_net_var = tk.StringVar(value="Net: $0.00")

        tk.Label(shooter_frame, textvariable=self.shooter_num_var,
                 fg='white', bg='#1a0f2e', font=('Arial', 9)).pack(anchor='w', padx=5)
        tk.Label(shooter_frame, textvariable=self.shooter_rolls_var,
                 fg='white', bg='#1a0f2e', font=('Arial', 9)).pack(anchor='w', padx=5)
        self.shooter_net_label = tk.Label(shooter_frame, textvariable=self.shooter_net_var,
                                          fg='#00ff00', bg='#1a0f2e', font=('Arial', 9, 'bold'))
        self.shooter_net_label.pack(anchor='w', padx=5)

        # Graph button
        graph_btn = tk.Button(
            bottom_frame, text="📈 Show Graph", font=('Arial', 10),
            bg='#4a3366', fg='white', command=self._show_bankroll_graph,
            width=12
        )
        graph_btn.pack(side=tk.LEFT, padx=10, pady=5)

        # Game log
        log_frame = tk.LabelFrame(bottom_frame, text="Game Log",
                                  bg='#1a0f2e', fg='white', font=('Arial', 10))
        log_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.log_text = tk.Text(log_frame, height=4, width=40,
                                bg='#0d0d0d', fg='#00ff00', font=('Consolas', 9))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self._log("Welcome to Craps!")
        self._log("Click a chip, then click the table to place bets.")
        self._log("Right-click a betting spot to remove chips.")

    def _create_betting_spots(self):
        """Define all betting spots on the table.

        Coordinates must match the _draw_table() canvas rectangles exactly.
        """
        # Pass Line - bottom of table: canvas draws at (50, 500, 650, 570)
        self.betting_spots.append(BettingSpot(
            "Pass Line", "pass", 50, 500, 600, 70, []
        ))

        # Pass Line Odds - behind pass line (left side near the pass line)
        self.betting_spots.append(BettingSpot(
            "Pass Odds", "pass_odds", 50, 575, 120, 40, []
        ))

        # Don't Pass Bar: canvas draws at (50, 450, 650, 495)
        self.betting_spots.append(BettingSpot(
            "Don't Pass", "dont_pass", 50, 450, 600, 45, []
        ))

        # Don't Pass Odds (Lay Odds) - next to don't pass
        self.betting_spots.append(BettingSpot(
            "Don't Pass Odds", "dont_pass_odds", 180, 575, 120, 40, []
        ))

        # Come: canvas draws at (150, 240, 650, 360)
        self.betting_spots.append(BettingSpot(
            "COME", "come", 150, 240, 500, 120, []
        ))

        # Don't Come Bar: canvas draws at (150, 80, 250, 145)
        self.betting_spots.append(BettingSpot(
            "Don't Come", "dont_come", 150, 80, 100, 65, []
        ))

        # Field: canvas draws at (150, 365, 650, 445)
        self.betting_spots.append(BettingSpot(
            "FIELD", "field", 150, 365, 500, 80, []
        ))

        # Place bets - canvas draws at x=260, width=62, spacing=67, y from 145 to 235
        place_x_start = 260
        place_width = 62
        place_spacing = 67  # place_width + 5
        place_y = 145
        place_height = 90
        for i, num in enumerate([4, 5, 6, 8, 9, 10]):
            x = place_x_start + i * place_spacing
            self.betting_spots.append(BettingSpot(
                f"Place {num}", f"place_{num}", x, place_y, place_width, place_height, []
            ))

        # Proposition bets area - canvas uses prop_x = 680
        prop_x = 680
        prop_inner_x = prop_x + 20  # Inner boxes start at prop_x + 20
        prop_width = 160  # Inner width is 180 - 20*2 buffer

        # Any Seven: canvas draws at (prop_x + 20, 95, prop_x + 180, 145)
        self.betting_spots.append(BettingSpot(
            "Any 7", "any_seven", prop_inner_x, 95, prop_width, 50, []
        ))

        # Hardways: Hard 6 at (prop_x + 20, 155, prop_x + 95, 200)
        # Hard 8 at (prop_x + 105, 155, prop_x + 180, 200)
        hardway_y = 155
        hardway_height = 45
        self.betting_spots.append(BettingSpot(
            "Hard 6", "hard_6", prop_inner_x, hardway_y, 75, hardway_height, []
        ))
        self.betting_spots.append(BettingSpot(
            "Hard 8", "hard_8", prop_x + 105, hardway_y, 75, hardway_height, []
        ))

        # Hard 4/10: at y=210
        hardway_y2 = 210
        self.betting_spots.append(BettingSpot(
            "Hard 4", "hard_4", prop_inner_x, hardway_y2, 75, hardway_height, []
        ))
        self.betting_spots.append(BettingSpot(
            "Hard 10", "hard_10", prop_x + 105, hardway_y2, 75, hardway_height, []
        ))

        # Any Craps: canvas draws at (prop_x + 20, 270, prop_x + 180, 330)
        self.betting_spots.append(BettingSpot(
            "Any Craps", "any_craps", prop_inner_x, 270, prop_width, 60, []
        ))

        # Horn: canvas draws at (prop_x + 20, 340, prop_x + 180, 400)
        self.betting_spots.append(BettingSpot(
            "Horn", "horn", prop_inner_x, 340, prop_width, 60, []
        ))

        # Yo-11: canvas draws at (prop_x + 20, 410, prop_x + 95, 455)
        # 2/12: canvas draws at (prop_x + 105, 410, prop_x + 180, 455)
        self.betting_spots.append(BettingSpot(
            "Yo (11)", "yo", prop_inner_x, 410, 75, 45, []
        ))
        self.betting_spots.append(BettingSpot(
            "Craps 2/12", "craps_2", prop_x + 105, 410, 75, 45, []
        ))

    def _draw_table(self):
        """Draw the craps table layout."""
        self.canvas.delete("table")  # Clear existing table elements

        # Draw outer border
        self._draw_rounded_rect(20, 20, self.TABLE_WIDTH - 40, self.TABLE_HEIGHT - 40,
                                20, COLORS['border'], COLORS['felt'], 3, "table")

        # Draw Pass Line area (bottom section only)
        self.canvas.create_rectangle(
            50, 500, 650, 570,
            fill=COLORS['pass_line'], outline=COLORS['border'], width=2, tags="table"
        )
        self.canvas.create_text(
            350, 535, text="PASS LINE", font=('Arial', 20, 'bold'),
            fill=COLORS['text'], tags="table"
        )

        # Odds betting areas (below pass line)
        # Pass Odds
        self.canvas.create_rectangle(
            50, 575, 170, 615,
            fill=COLORS['felt_light'], outline=COLORS['border'], width=1, tags="table"
        )
        self.canvas.create_text(
            110, 595, text="ODDS", font=('Arial', 10, 'bold'),
            fill=COLORS['text'], tags="table"
        )

        # Don't Pass Odds (Lay)
        self.canvas.create_rectangle(
            180, 575, 300, 615,
            fill=COLORS['felt_light'], outline=COLORS['border'], width=1, tags="table"
        )
        self.canvas.create_text(
            240, 595, text="LAY ODDS", font=('Arial', 10, 'bold'),
            fill=COLORS['text'], tags="table"
        )

        # Don't Pass Bar (above pass line)
        self.canvas.create_rectangle(
            50, 450, 650, 495,
            fill=COLORS['felt_light'], outline=COLORS['border'], width=2, tags="table"
        )
        self.canvas.create_text(
            350, 472, text="DON'T PASS BAR", font=('Arial', 14, 'bold'),
            fill=COLORS['text'], tags="table"
        )
        # Bar 12 dice
        self._draw_die_icon(560, 465, 6, 15, "table")
        self._draw_die_icon(590, 465, 6, 15, "table")

        # COME area
        self.canvas.create_rectangle(
            150, 240, 650, 360,
            fill=COLORS['come'], outline=COLORS['border'], width=2, tags="table"
        )
        self.canvas.create_text(
            400, 300, text="COME", font=('Arial', 36, 'bold'),
            fill=COLORS['text_red'], tags="table"
        )

        # Don't Come Bar (top left)
        self.canvas.create_rectangle(
            150, 80, 250, 145,
            fill=COLORS['felt_light'], outline=COLORS['border'], width=2, tags="table"
        )
        self.canvas.create_text(
            200, 100, text="Don't Come", font=('Arial', 10, 'bold'),
            fill=COLORS['text'], tags="table"
        )
        self.canvas.create_text(
            200, 120, text="Bar", font=('Arial', 9),
            fill=COLORS['text'], tags="table"
        )
        self._draw_die_icon(180, 128, 6, 12, "table")
        self._draw_die_icon(205, 128, 6, 12, "table")

        # FIELD area
        self.canvas.create_rectangle(
            150, 365, 650, 445,
            fill=COLORS['field'], outline=COLORS['border'], width=2, tags="table"
        )
        # Field numbers
        self.canvas.create_text(
            400, 385, text="2  3  4  9  10  11  12", font=('Arial', 16, 'bold'),
            fill=COLORS['text_accent'], tags="table"
        )
        self.canvas.create_text(
            400, 410, text="FIELD", font=('Arial', 20, 'bold'),
            fill=COLORS['text_accent'], tags="table"
        )
        self.canvas.create_text(
            200, 430, text="2 Pays Double", font=('Arial', 10),
            fill=COLORS['text'], tags="table"
        )
        self.canvas.create_text(
            600, 430, text="12 Pays Double", font=('Arial', 10),
            fill=COLORS['text'], tags="table"
        )

        # Place bets (4, 5, 6, 8, 9, 10)
        place_nums = [4, 5, 6, 8, 9, 10]
        place_x = 260
        place_width = 62
        for i, num in enumerate(place_nums):
            x = place_x + i * (place_width + 5)
            self.canvas.create_rectangle(
                x, 145, x + place_width, 235,
                fill=COLORS['felt_light'], outline=COLORS['border'], width=2, tags="table"
            )
            # Number display
            text = str(num) if num not in (6, 9) else ("SIX" if num == 6 else "NINE")
            self.canvas.create_text(
                x + place_width // 2, 190, text=text,
                font=('Arial', 18, 'bold'), fill=COLORS['text'], tags="table"
            )

        # Proposition bets area (right side)
        prop_x = 680
        self.canvas.create_rectangle(
            prop_x, 60, 880, 480,
            fill=COLORS['props'], outline=COLORS['border'], width=2, tags="table"
        )
        self.canvas.create_text(
            780, 80, text="PROPOSITION BETS", font=('Arial', 12, 'bold'),
            fill=COLORS['text_accent'], tags="table"
        )

        # Any Seven
        self.canvas.create_rectangle(
            prop_x + 20, 95, prop_x + 180, 145,
            fill=COLORS['felt_light'], outline=COLORS['border'], width=2, tags="table"
        )
        self.canvas.create_text(
            780, 110, text="Seven", font=('Arial', 14, 'bold'),
            fill=COLORS['text_accent'], tags="table"
        )
        self.canvas.create_text(
            780, 130, text="4 to 1", font=('Arial', 11),
            fill=COLORS['text'], tags="table"
        )

        # Hardways
        hardway_y = 155
        # Hard 6/8
        self.canvas.create_rectangle(
            prop_x + 20, hardway_y, prop_x + 95, hardway_y + 45,
            fill=COLORS['felt_light'], outline=COLORS['border'], width=2, tags="table"
        )
        self._draw_die_icon(prop_x + 35, hardway_y + 8, 3, 12, "table")
        self._draw_die_icon(prop_x + 60, hardway_y + 8, 3, 12, "table")
        self.canvas.create_text(
            prop_x + 57, hardway_y + 35, text="10:1", font=('Arial', 9),
            fill=COLORS['text'], tags="table"
        )

        self.canvas.create_rectangle(
            prop_x + 105, hardway_y, prop_x + 180, hardway_y + 45,
            fill=COLORS['felt_light'], outline=COLORS['border'], width=2, tags="table"
        )
        self._draw_die_icon(prop_x + 120, hardway_y + 8, 4, 12, "table")
        self._draw_die_icon(prop_x + 145, hardway_y + 8, 4, 12, "table")
        self.canvas.create_text(
            prop_x + 142, hardway_y + 35, text="10:1", font=('Arial', 9),
            fill=COLORS['text'], tags="table"
        )

        # Hard 4/10
        hardway_y2 = 210
        self.canvas.create_rectangle(
            prop_x + 20, hardway_y2, prop_x + 95, hardway_y2 + 45,
            fill=COLORS['felt_light'], outline=COLORS['border'], width=2, tags="table"
        )
        self._draw_die_icon(prop_x + 35, hardway_y2 + 8, 2, 12, "table")
        self._draw_die_icon(prop_x + 60, hardway_y2 + 8, 2, 12, "table")
        self.canvas.create_text(
            prop_x + 57, hardway_y2 + 35, text="8:1", font=('Arial', 9),
            fill=COLORS['text'], tags="table"
        )

        self.canvas.create_rectangle(
            prop_x + 105, hardway_y2, prop_x + 180, hardway_y2 + 45,
            fill=COLORS['felt_light'], outline=COLORS['border'], width=2, tags="table"
        )
        self._draw_die_icon(prop_x + 120, hardway_y2 + 8, 5, 12, "table")
        self._draw_die_icon(prop_x + 145, hardway_y2 + 8, 5, 12, "table")
        self.canvas.create_text(
            prop_x + 142, hardway_y2 + 35, text="8:1", font=('Arial', 9),
            fill=COLORS['text'], tags="table"
        )

        # Any Craps
        self.canvas.create_rectangle(
            prop_x + 20, 270, prop_x + 180, 330,
            fill=COLORS['felt_light'], outline=COLORS['border'], width=2, tags="table"
        )
        self.canvas.create_text(
            780, 290, text="Any Craps", font=('Arial', 14, 'bold'),
            fill=COLORS['text_accent'], tags="table"
        )
        self.canvas.create_text(
            780, 312, text="7 to 1", font=('Arial', 11),
            fill=COLORS['text'], tags="table"
        )

        # Horn
        self.canvas.create_rectangle(
            prop_x + 20, 340, prop_x + 180, 400,
            fill=COLORS['felt_light'], outline=COLORS['border'], width=2, tags="table"
        )
        self.canvas.create_text(
            780, 355, text="Horn", font=('Arial', 14, 'bold'),
            fill=COLORS['text_accent'], tags="table"
        )
        self.canvas.create_text(
            780, 375, text="2, 3, 11, 12", font=('Arial', 10),
            fill=COLORS['text'], tags="table"
        )

        # Yo-11 and 2 Craps
        self.canvas.create_rectangle(
            prop_x + 20, 410, prop_x + 95, 455,
            fill=COLORS['felt_light'], outline=COLORS['border'], width=2, tags="table"
        )
        self.canvas.create_text(
            prop_x + 57, 425, text="Yo-11", font=('Arial', 11, 'bold'),
            fill=COLORS['text_accent'], tags="table"
        )
        self.canvas.create_text(
            prop_x + 57, 443, text="15:1", font=('Arial', 9),
            fill=COLORS['text'], tags="table"
        )

        self.canvas.create_rectangle(
            prop_x + 105, 410, prop_x + 180, 455,
            fill=COLORS['felt_light'], outline=COLORS['border'], width=2, tags="table"
        )
        self.canvas.create_text(
            prop_x + 142, 425, text="2 or 12", font=('Arial', 11, 'bold'),
            fill=COLORS['text_accent'], tags="table"
        )
        self.canvas.create_text(
            prop_x + 142, 443, text="30:1", font=('Arial', 9),
            fill=COLORS['text'], tags="table"
        )

        # Draw dice display area
        self._draw_dice_area()

        # Draw place bets status indicator
        self._draw_place_bets_status()

    def _draw_rounded_rect(self, x: int, y: int, w: int, h: int, r: int,
                           outline: str, fill: str, width: int, tag: str):
        """Draw a rounded rectangle."""
        self.canvas.create_arc(x, y, x + 2*r, y + 2*r, start=90, extent=90,
                               fill=fill, outline=outline, width=width, tags=tag)
        self.canvas.create_arc(x + w - 2*r, y, x + w, y + 2*r, start=0, extent=90,
                               fill=fill, outline=outline, width=width, tags=tag)
        self.canvas.create_arc(x, y + h - 2*r, x + 2*r, y + h, start=180, extent=90,
                               fill=fill, outline=outline, width=width, tags=tag)
        self.canvas.create_arc(x + w - 2*r, y + h - 2*r, x + w, y + h, start=270, extent=90,
                               fill=fill, outline=outline, width=width, tags=tag)
        self.canvas.create_rectangle(x + r, y, x + w - r, y + h, fill=fill, outline='', tags=tag)
        self.canvas.create_rectangle(x, y + r, x + w, y + h - r, fill=fill, outline='', tags=tag)

    def _draw_die_icon(self, x: int, y: int, value: int, size: int, tag: str):
        """Draw a small die icon showing a specific value."""
        self.canvas.create_rectangle(x, y, x + size, y + size,
                                     fill='white', outline='black', tags=tag)

        dot_positions = {
            1: [(0.5, 0.5)],
            2: [(0.25, 0.25), (0.75, 0.75)],
            3: [(0.25, 0.25), (0.5, 0.5), (0.75, 0.75)],
            4: [(0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)],
            5: [(0.25, 0.25), (0.75, 0.25), (0.5, 0.5), (0.25, 0.75), (0.75, 0.75)],
            6: [(0.25, 0.25), (0.75, 0.25), (0.25, 0.5), (0.75, 0.5), (0.25, 0.75), (0.75, 0.75)],
        }

        r = max(1, size // 8)
        for px, py in dot_positions[value]:
            cx = x + px * size
            cy = y + py * size
            self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill='black', tags=tag)

    def _draw_dice_area(self):
        """Draw the dice display area."""
        self.canvas.delete("dice")

        # Dice area box
        dice_x, dice_y = 870, 520
        self.canvas.create_rectangle(
            dice_x, dice_y, dice_x + 100, dice_y + 60,
            fill='#1a1a1a', outline=COLORS['border'], width=2, tags="dice"
        )
        self.canvas.create_text(
            dice_x + 50, dice_y - 10, text="DICE", font=('Arial', 10, 'bold'),
            fill=COLORS['text'], tags="dice"
        )

        # Draw dice if we have a roll
        last_roll = self.game.get_last_roll()
        if last_roll:
            self._draw_die_icon(dice_x + 10, dice_y + 10, last_roll.die1, 35, "dice")
            self._draw_die_icon(dice_x + 55, dice_y + 10, last_roll.die2, 35, "dice")
            # Total
            self.canvas.create_text(
                dice_x + 50, dice_y + 55, text=f"= {last_roll.total}",
                font=('Arial', 12, 'bold'), fill=COLORS['text_accent'], tags="dice"
            )

    def _draw_chip_tray(self):
        """Draw the chip selection tray on the canvas."""
        pass  # Chips are in the bottom frame now

    def _select_chip(self, value: int):
        """Select a chip denomination."""
        self.selected_chip_value = value
        # Update button appearances
        for v, btn in self.chip_buttons.items():
            if v == value:
                btn.configure(relief=tk.SUNKEN, bd=5)
            else:
                btn.configure(relief=tk.RAISED, bd=3)

    def _on_click(self, event):
        """Handle click on canvas - place a chip."""
        x, y = event.x, event.y

        # Check if clicking on a number box - differentiate between come odds area and place bet area
        place_nums = [4, 5, 6, 8, 9, 10]
        place_x_start = 260
        place_width = 62
        place_spacing = 67
        place_y = 145
        place_height = 90

        for i, num in enumerate(place_nums):
            box_x = place_x_start + i * place_spacing
            if box_x <= x <= box_x + place_width and place_y <= y <= place_y + place_height:
                # Clicked on a number box
                # Top 30 pixels: come odds area (if come bet exists)
                # Bottom 30 pixels: don't come odds area (if don't come bet exists)
                # Middle: place bet area

                if y <= place_y + 30:
                    # Top area - try come odds
                    if self._try_place_come_odds(num, come_only=True):
                        return
                elif y >= place_y + place_height - 30:
                    # Bottom area - try don't come odds
                    if self._try_place_come_odds(num, dont_come_only=True):
                        return
                # Middle area or no come bet - fall through to place bet
                break

        # Check if clicking on a betting spot
        for spot in self.betting_spots:
            if spot.contains(x, y):
                self._place_chip_on_spot(spot)
                return

    def _try_place_come_odds(self, number: int, come_only: bool = False, dont_come_only: bool = False) -> bool:
        """Try to place come/don't come odds on a number. Returns True if placed."""
        if self.bankroll < self.selected_chip_value:
            return False  # Don't log here, let place bet handle it

        # Check if there's a come bet on this number (and no odds yet)
        if not dont_come_only and number in self.come_bets_on_number and self.come_bets_on_number[number]:
            # Only allow one odds bet per come bet
            if number in self.come_odds_on_number and self.come_odds_on_number[number]:
                self._log(f"Already have Come Odds on {number}")
                return True  # Block but don't place
            self.come_odds_on_number[number] = [self.selected_chip_value]
            self.bankroll -= self.selected_chip_value
            self._update_bankroll_display()
            self._redraw_chips()
            self._log(f"Placed ${self.selected_chip_value} Come Odds on {number}")
            return True

        # Check if there's a don't come bet on this number (and no odds yet)
        if not come_only and number in self.dont_come_bets_on_number and self.dont_come_bets_on_number[number]:
            # Only allow one odds bet per don't come bet
            if number in self.dont_come_odds_on_number and self.dont_come_odds_on_number[number]:
                self._log(f"Already have Don't Come Odds on {number}")
                return True  # Block but don't place
            self.dont_come_odds_on_number[number] = [self.selected_chip_value]
            self.bankroll -= self.selected_chip_value
            self._update_bankroll_display()
            self._redraw_chips()
            self._log(f"Placed ${self.selected_chip_value} Don't Come Odds on {number}")
            return True

        # No come/don't come bet on this number - allow place bet to be placed
        return False

    def _on_drag(self, event):
        """Handle drag motion."""
        pass  # Could implement visual drag feedback

    def _on_release(self, event):
        """Handle mouse release."""
        pass

    def _on_mouse_move(self, event):
        """Handle mouse movement - highlight betting spots on hover."""
        x, y = event.x, event.y

        # Clear previous highlight
        self.canvas.delete("highlight")

        # Check if hovering over a betting spot
        for spot in self.betting_spots:
            if spot.contains(x, y):
                # Draw highlight rectangle
                self.canvas.create_rectangle(
                    spot.x, spot.y, spot.x + spot.width, spot.y + spot.height,
                    outline='#ffff00', width=3, tags="highlight"
                )
                # Show spot name near cursor
                self.canvas.create_text(
                    x + 10, y - 15, text=spot.name,
                    font=('Arial', 10, 'bold'), fill='#ffff00',
                    anchor='w', tags="highlight"
                )
                return

    def _on_right_click(self, event):
        """Handle right-click - remove chips from spot."""
        x, y = event.x, event.y

        for spot in self.betting_spots:
            if spot.contains(x, y) and spot.chips:
                # Contract bets (Pass/Don't Pass) cannot be removed after point is established
                if spot.bet_type in ('pass', 'dont_pass') and self.game.is_point_phase:
                    self._log(f"Cannot remove {spot.name} bet - it's a contract bet!")
                    return

                # Remove the last chip placed
                removed = spot.chips.pop()
                self.bankroll += removed
                self._update_bankroll_display()
                self._redraw_chips()
                self._log(f"Removed ${removed} chip from {spot.name}")
                return

    def _place_chip_on_spot(self, spot: BettingSpot):
        """Place a chip on a betting spot."""
        if self.bankroll < self.selected_chip_value:
            self._log("Insufficient bankroll!")
            return

        # Check betting rules
        # In shooter mode, pass/don't pass can only be placed before point
        # In non-shooter mode, can place anytime (betting on someone else's roll)
        if self.shooter_mode:
            if spot.bet_type == 'pass' and self.game.is_point_phase:
                self._log("Cannot place Pass Line bet after point is established (Shooter mode)")
                return
            if spot.bet_type == 'dont_pass' and self.game.is_point_phase:
                self._log("Cannot place Don't Pass bet after point is established (Shooter mode)")
                return
        if spot.bet_type == 'come' and self.game.is_come_out:
            self._log("Cannot place Come bet during come-out roll")
            return
        if spot.bet_type == 'dont_come' and self.game.is_come_out:
            self._log("Cannot place Don't Come bet during come-out roll")
            return

        # Odds bets require point to be established and underlying bet
        if spot.bet_type == 'pass_odds':
            if not self.game.is_point_phase:
                self._log("Cannot place Pass Odds - no point established")
                return
            pass_spot = self._get_spot_by_type('pass')
            if not pass_spot or not pass_spot.chips:
                self._log("Cannot place Pass Odds - no Pass Line bet")
                return

        if spot.bet_type == 'dont_pass_odds':
            if not self.game.is_point_phase:
                self._log("Cannot place Don't Pass Odds - no point established")
                return
            dont_pass_spot = self._get_spot_by_type('dont_pass')
            if not dont_pass_spot or not dont_pass_spot.chips:
                self._log("Cannot place Don't Pass Odds - no Don't Pass bet")
                return

        # Deduct from bankroll and add chip
        self.bankroll -= self.selected_chip_value
        spot.chips.append(self.selected_chip_value)

        self._update_bankroll_display()
        self._redraw_chips()
        self._log(f"Placed ${self.selected_chip_value} on {spot.name}")

    def _redraw_chips(self):
        """Redraw all chips on the table."""
        self.canvas.delete("chips")

        # Draw chips on regular betting spots
        for spot in self.betting_spots:
            if spot.chips:
                cx, cy = spot.center()
                # Stack chips visually
                for i, chip_value in enumerate(spot.chips[:5]):  # Show max 5 chips
                    self._draw_chip(cx, cy - i * 4, chip_value)

                # Show total amount
                total = spot.total_bet
                self.canvas.create_text(
                    cx, cy + 25, text=f"${total}",
                    font=('Arial', 10, 'bold'), fill='white', tags="chips"
                )

        # Draw Come bets that have traveled to point numbers
        self._draw_traveled_come_bets()

    def _draw_traveled_come_bets(self):
        """Draw Come/Don't Come bets and their odds that have traveled to point numbers."""
        # Position calculations for the number boxes (must match _create_betting_spots)
        place_x_start = 260
        place_width = 62
        place_spacing = 67
        place_nums = [4, 5, 6, 8, 9, 10]

        for num in place_nums:
            idx = place_nums.index(num)
            box_x = place_x_start + idx * place_spacing + place_width // 2

            # Come bets go at the TOP of the number box
            if num in self.come_bets_on_number and self.come_bets_on_number[num]:
                chips = self.come_bets_on_number[num]
                cy = 155  # Near top of the box
                for i, chip_value in enumerate(chips[:3]):
                    self._draw_chip(box_x - 15, cy - i * 4, chip_value)

                # Come odds go next to come bet
                if num in self.come_odds_on_number and self.come_odds_on_number[num]:
                    odds_chips = self.come_odds_on_number[num]
                    for i, chip_value in enumerate(odds_chips[:3]):
                        self._draw_chip(box_x + 15, cy - i * 4, chip_value)
                    # Show combined label
                    total_bet = sum(chips) + sum(odds_chips)
                    self.canvas.create_text(
                        box_x, cy + 18, text=f"C+O:${total_bet}",
                        font=('Arial', 8, 'bold'), fill='#00ff00', tags="chips"
                    )
                else:
                    self.canvas.create_text(
                        box_x, cy + 18, text=f"C:${sum(chips)}",
                        font=('Arial', 8, 'bold'), fill='#00ff00', tags="chips"
                    )

            # Don't Come bets go at the BOTTOM of the number box
            if num in self.dont_come_bets_on_number and self.dont_come_bets_on_number[num]:
                chips = self.dont_come_bets_on_number[num]
                cy = 225  # Near bottom of the box
                for i, chip_value in enumerate(chips[:3]):
                    self._draw_chip(box_x - 15, cy - i * 4, chip_value)

                # Don't come odds go next to don't come bet
                if num in self.dont_come_odds_on_number and self.dont_come_odds_on_number[num]:
                    odds_chips = self.dont_come_odds_on_number[num]
                    for i, chip_value in enumerate(odds_chips[:3]):
                        self._draw_chip(box_x + 15, cy - i * 4, chip_value)
                    total_bet = sum(chips) + sum(odds_chips)
                    self.canvas.create_text(
                        box_x, cy + 18, text=f"DC+O:${total_bet}",
                        font=('Arial', 8, 'bold'), fill='#ff6666', tags="chips"
                    )
                else:
                    self.canvas.create_text(
                        box_x, cy + 18, text=f"DC:${sum(chips)}",
                        font=('Arial', 8, 'bold'), fill='#ff6666', tags="chips"
                    )

    def _draw_chip(self, x: int, y: int, value: int):
        """Draw a chip at the given position with poker chip styling."""
        color = CHIP_COLORS.get(value, '#888888')
        radius = 18
        inner_radius = 12

        # Darken color for inner circle
        def darken_color(hex_color: str, factor: float = 0.8) -> str:
            hex_color = hex_color.lstrip('#')
            r = int(int(hex_color[0:2], 16) * factor)
            g = int(int(hex_color[2:4], 16) * factor)
            b = int(int(hex_color[4:6], 16) * factor)
            return f'#{r:02x}{g:02x}{b:02x}'

        inner_color = darken_color(color, 0.85)

        # Outer chip body
        self.canvas.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            fill=color, outline='', tags="chips"
        )

        # Four rectangular edge markers at 12, 3, 6, 9 o'clock
        marker_width = 6
        marker_height = 8
        marker_color = 'white'

        # Top marker (12 o'clock)
        self.canvas.create_rectangle(
            x - marker_width // 2, y - radius,
            x + marker_width // 2, y - radius + marker_height,
            fill=marker_color, outline='', tags="chips"
        )
        # Bottom marker (6 o'clock)
        self.canvas.create_rectangle(
            x - marker_width // 2, y + radius - marker_height,
            x + marker_width // 2, y + radius,
            fill=marker_color, outline='', tags="chips"
        )
        # Left marker (9 o'clock)
        self.canvas.create_rectangle(
            x - radius, y - marker_width // 2,
            x - radius + marker_height, y + marker_width // 2,
            fill=marker_color, outline='', tags="chips"
        )
        # Right marker (3 o'clock)
        self.canvas.create_rectangle(
            x + radius - marker_height, y - marker_width // 2,
            x + radius, y + marker_width // 2,
            fill=marker_color, outline='', tags="chips"
        )

        # Inner circle
        self.canvas.create_oval(
            x - inner_radius, y - inner_radius, x + inner_radius, y + inner_radius,
            fill=inner_color, outline='', tags="chips"
        )

        # Value text
        text_color = 'black' if value in (1, 25) else 'white'
        text = f"${value}" if value < 100 else str(value)
        self.canvas.create_text(
            x, y, text=text, font=('Arial', 9, 'bold'),
            fill=text_color, tags="chips"
        )

    def _roll_dice(self):
        """Roll the dice and resolve bets."""
        # Convert chip placements to actual bets
        self._convert_chips_to_bets()

        # In shooter mode, require bets. In non-shooter mode, allow watching without betting.
        if self.shooter_mode and not self.bet_manager.active_bets and not self._get_total_bets_at_risk():
            self._log("Place some bets first!")
            return

        roll = self.game.roll_dice()
        self._draw_dice_area()

    def _convert_chips_to_bets(self):
        """Convert chip placements to bet objects."""
        for spot in self.betting_spots:
            if spot.chips and spot.total_bet > 0:
                amount = spot.total_bet
                bet = None

                if spot.bet_type == 'pass':
                    # Check if we already have a pass line bet
                    has_bet = any(isinstance(b, PassLineBet) for b in self.bet_manager.active_bets)
                    if not has_bet:
                        bet = PassLineBet(amount, self.rules)
                elif spot.bet_type == 'dont_pass':
                    has_bet = any(isinstance(b, DontPassBet) for b in self.bet_manager.active_bets)
                    if not has_bet:
                        bet = DontPassBet(amount, self.rules)
                elif spot.bet_type == 'come':
                    # Come bets can stack, but we handle them specially with traveled bets
                    # Only create if chips are in the Come spot (not yet traveled)
                    bet = ComeBet(amount, self.rules)
                elif spot.bet_type == 'dont_come':
                    bet = DontComeBet(amount, self.rules)
                elif spot.bet_type == 'field':
                    bet = FieldBet(amount, self.rules)
                elif spot.bet_type.startswith('place_'):
                    num = int(spot.bet_type.split('_')[1])
                    # Check if we already have this place bet active
                    has_bet = any(isinstance(b, PlaceBet) and b.number == num
                                  for b in self.bet_manager.active_bets)
                    if not has_bet:
                        bet = PlaceBet(amount, self.rules, num)
                        bet.is_working = self.place_bets_working
                elif spot.bet_type.startswith('hard_'):
                    num = int(spot.bet_type.split('_')[1])
                    # Check if we already have this hardway bet active
                    has_bet = any(isinstance(b, HardwayBet) and b.number == num
                                  for b in self.bet_manager.active_bets)
                    if not has_bet:
                        bet = HardwayBet(amount, self.rules, num)
                        self._log(f"  [DEBUG] Created Hard {num} bet for ${amount}")
                elif spot.bet_type == 'pass_odds':
                    # Pass line odds - requires point to be established
                    if self.game.point:
                        has_bet = any(isinstance(b, OddsBet) for b in self.bet_manager.active_bets)
                        if not has_bet:
                            bet = OddsBet(amount, self.rules, self.game.point)
                elif spot.bet_type == 'dont_pass_odds':
                    # Don't pass odds (lay odds) - requires point to be established
                    if self.game.point:
                        has_bet = any(isinstance(b, LayOddsBet) for b in self.bet_manager.active_bets)
                        if not has_bet:
                            bet = LayOddsBet(amount, self.rules, self.game.point)
                elif spot.bet_type == 'any_seven':
                    bet = AnySevenBet(amount, self.rules)
                elif spot.bet_type == 'any_craps':
                    bet = AnyCrapsBet(amount, self.rules)
                elif spot.bet_type == 'horn':
                    bet = HornBet(amount, self.rules)

                if bet:
                    # Find existing bet of same type and update or add new
                    if self.bet_manager.place_bet(bet):
                        pass  # Bet placed successfully
                    else:
                        self._log(f"  [DEBUG] Failed to place bet: {bet.name} ${bet.amount} (min: ${self.rules.minimum_bet})")

    def _on_roll(self, roll: DiceRoll):
        """Handle a dice roll event."""
        self._log(f"Rolled {roll}")
        total = roll.total

        # Record bankroll before resolution
        bankroll_before = self.bankroll
        bets_at_risk = self._get_total_bets_at_risk()

        # First, resolve come/don't come bets that have traveled to numbers
        self._resolve_traveled_come_bets(total)

        # Resolve all bets through bet manager
        results = self.bet_manager.resolve_all(roll, self.game.phase, self.game.point)

        total_win = 0

        # Bets that "ride" - stay up after winning (only payout is collected)
        riding_bet_types = ('place_4', 'place_5', 'place_6', 'place_8', 'place_9', 'place_10',
                           'hard_4', 'hard_6', 'hard_8', 'hard_10')

        for bet, result in results:
            # Find the corresponding spot
            spot_found = False
            for spot in self.betting_spots:
                if self._bet_matches_spot(bet, spot):
                    spot_found = True
                    is_riding_bet = spot.bet_type in riding_bet_types
                    # Debug for hardway bets
                    if isinstance(bet, HardwayBet):
                        self._log(f"  [DEBUG] Hard {bet.number} resolved: {result.status.value}, spot: {spot.bet_type}, chips: {spot.chips}")

                    if result.status == BetStatus.WON:
                        if is_riding_bet:
                            # Riding bets: only collect payout, bet stays up
                            self.bankroll += result.payout
                            self._log(f"  WIN: {bet.name} +${result.payout:.2f} (bet rides)")
                        else:
                            # Regular bets: collect payout + original bet
                            winnings = result.payout + sum(spot.chips)
                            self.bankroll += winnings
                            spot.chips.clear()
                            self._log(f"  WIN: {bet.name} +${result.payout:.2f}")
                        total_win += result.payout
                    elif result.status == BetStatus.PUSH:
                        self.bankroll += sum(spot.chips)
                        spot.chips.clear()
                        self._log(f"  PUSH: {bet.name}")
                    else:
                        # Loss - always clear chips
                        spot.chips.clear()
                        self._log(f"  LOSE: {bet.name}")
                    break

            # Debug: if no spot found for this bet
            if not spot_found and isinstance(bet, HardwayBet):
                self._log(f"  [DEBUG] No spot found for Hard {bet.number}!")

        # Handle Come/Don't Come bets traveling to numbers
        self._handle_come_bet_travel(total)

        # Clear one-roll bet spots (field, props) that weren't resolved
        for spot in self.betting_spots:
            if spot.bet_type in ('field', 'any_seven', 'any_craps', 'horn', 'yo', 'craps_2'):
                if spot.chips:
                    spot.chips.clear()

        # Record roll in tracker (bets_after = chips still on table after resolution)
        bets_after = self._get_total_bets_at_risk()
        self.tracker.record_roll(
            die1=roll.die1,
            die2=roll.die2,
            bankroll_before=bankroll_before,
            bankroll_after=self.bankroll,
            bets_before=bets_at_risk,
            bets_after=bets_after
        )

        self._update_bankroll_display()
        self._update_stats_display()
        self._redraw_chips()
        self._update_graph()  # Update live graph if open

    def _resolve_traveled_come_bets(self, total: int):
        """Resolve come/don't come bets and their odds that have traveled to point numbers."""
        # True odds payouts for come/don't come odds
        odds_payouts = {4: 2.0, 5: 1.5, 6: 1.2, 8: 1.2, 9: 1.5, 10: 2.0}
        lay_payouts = {4: 0.5, 5: 2/3, 6: 5/6, 8: 5/6, 9: 2/3, 10: 0.5}

        # Come bets on numbers: win if number hits, lose on 7
        if total in self.come_bets_on_number and self.come_bets_on_number[total]:
            chips = self.come_bets_on_number[total]
            bet_amount = sum(chips)
            payout = bet_amount  # Even money
            self.bankroll += payout + bet_amount  # Payout + original bet
            self._log(f"  WIN: Come ({total}) +${payout:.2f}")
            self.come_bets_on_number[total] = []

            # Also resolve come odds
            if total in self.come_odds_on_number and self.come_odds_on_number[total]:
                odds_chips = self.come_odds_on_number[total]
                odds_amount = sum(odds_chips)
                odds_payout = odds_amount * odds_payouts[total]
                self.bankroll += odds_payout + odds_amount
                self._log(f"  WIN: Come Odds ({total}) +${odds_payout:.2f}")
                self.come_odds_on_number[total] = []

        if total == 7:
            # All come bets on numbers lose
            for num in list(self.come_bets_on_number.keys()):
                if self.come_bets_on_number[num]:
                    self._log(f"  LOSE: Come ({num})")
                    self.come_bets_on_number[num] = []
            # All come odds lose
            for num in list(self.come_odds_on_number.keys()):
                if self.come_odds_on_number[num]:
                    self._log(f"  LOSE: Come Odds ({num})")
                    self.come_odds_on_number[num] = []

        # Don't Come bets on numbers: win on 7, lose if number hits
        if total in self.dont_come_bets_on_number and self.dont_come_bets_on_number[total]:
            self._log(f"  LOSE: Don't Come ({total})")
            self.dont_come_bets_on_number[total] = []
            # Don't come odds also lose
            if total in self.dont_come_odds_on_number and self.dont_come_odds_on_number[total]:
                self._log(f"  LOSE: Don't Come Odds ({total})")
                self.dont_come_odds_on_number[total] = []

        if total == 7:
            # All don't come bets on numbers win
            for num in list(self.dont_come_bets_on_number.keys()):
                if self.dont_come_bets_on_number[num]:
                    chips = self.dont_come_bets_on_number[num]
                    bet_amount = sum(chips)
                    payout = bet_amount  # Even money
                    self.bankroll += payout + bet_amount
                    self._log(f"  WIN: Don't Come ({num}) +${payout:.2f}")
                    self.dont_come_bets_on_number[num] = []

                    # Also resolve don't come odds (lay odds)
                    if num in self.dont_come_odds_on_number and self.dont_come_odds_on_number[num]:
                        odds_chips = self.dont_come_odds_on_number[num]
                        odds_amount = sum(odds_chips)
                        odds_payout = odds_amount * lay_payouts[num]
                        self.bankroll += odds_payout + odds_amount
                        self._log(f"  WIN: Don't Come Odds ({num}) +${odds_payout:.2f}")
                        self.dont_come_odds_on_number[num] = []

    def _handle_come_bet_travel(self, total: int):
        """Move Come/Don't Come bets to their point number when established."""
        # Point numbers that cause come bets to travel
        point_numbers = (4, 5, 6, 8, 9, 10)

        if total in point_numbers:
            # Check if there are chips in the Come spot
            come_spot = self._get_spot_by_type('come')
            if come_spot and come_spot.chips:
                # Move chips to the number
                if total not in self.come_bets_on_number:
                    self.come_bets_on_number[total] = []
                self.come_bets_on_number[total].extend(come_spot.chips)
                self._log(f"  Come bet travels to {total}")
                come_spot.chips.clear()

            # Check Don't Come spot
            dont_come_spot = self._get_spot_by_type('dont_come')
            if dont_come_spot and dont_come_spot.chips:
                if total not in self.dont_come_bets_on_number:
                    self.dont_come_bets_on_number[total] = []
                self.dont_come_bets_on_number[total].extend(dont_come_spot.chips)
                self._log(f"  Don't Come bet travels to {total}")
                dont_come_spot.chips.clear()

            # Remove ComeBet/DontComeBet objects from bet_manager that have traveled
            # (they are now tracked via come_bets_on_number/dont_come_bets_on_number)
            self.bet_manager.active_bets = [
                bet for bet in self.bet_manager.active_bets
                if not (isinstance(bet, ComeBet) and bet._come_point is not None)
                and not (isinstance(bet, DontComeBet) and bet._come_point is not None)
            ]

    def _get_spot_by_type(self, bet_type: str) -> Optional[BettingSpot]:
        """Get a betting spot by its type."""
        for spot in self.betting_spots:
            if spot.bet_type == bet_type:
                return spot
        return None

    def _bet_matches_spot(self, bet, spot: BettingSpot) -> bool:
        """Check if a bet matches a betting spot."""
        if isinstance(bet, PassLineBet) and spot.bet_type == 'pass':
            return True
        if isinstance(bet, DontPassBet) and spot.bet_type == 'dont_pass':
            return True
        if isinstance(bet, OddsBet) and spot.bet_type == 'pass_odds':
            return True
        if isinstance(bet, LayOddsBet) and spot.bet_type == 'dont_pass_odds':
            return True
        if isinstance(bet, ComeBet) and spot.bet_type == 'come':
            return True
        if isinstance(bet, DontComeBet) and spot.bet_type == 'dont_come':
            return True
        if isinstance(bet, FieldBet) and spot.bet_type == 'field':
            return True
        if isinstance(bet, PlaceBet) and spot.bet_type == f'place_{bet.number}':
            return True
        if isinstance(bet, HardwayBet) and spot.bet_type == f'hard_{bet.number}':
            return True
        if isinstance(bet, AnySevenBet) and spot.bet_type == 'any_seven':
            return True
        if isinstance(bet, AnyCrapsBet) and spot.bet_type == 'any_craps':
            return True
        if isinstance(bet, HornBet) and spot.bet_type == 'horn':
            return True
        return False

    def _on_point_established(self, point: int):
        """Handle point establishment."""
        self.point_var.set(str(point))
        self._log(f"Point established: {point}")
        # Draw point marker and clear place status (place bets always work during point)
        self._draw_point_marker(point)
        self.canvas.delete("place_status")  # Hide OFF puck when point is ON

    def _on_point_won(self):
        """Handle point being made."""
        self.point_var.set("OFF")
        self._log("POINT MADE! New shooter.")
        self._clear_point_marker()

    def _on_seven_out(self):
        """Handle seven-out."""
        self.point_var.set("OFF")
        self._log("SEVEN OUT! New shooter.")
        self._clear_point_marker()

        # Record shooter change in tracker
        self.tracker.end_shooter(seven_out=True)

        # Clear all bets on seven-out
        for spot in self.betting_spots:
            spot.chips.clear()

        # Clear any traveled come bets and their odds (they lose on 7)
        self.come_bets_on_number.clear()
        self.dont_come_bets_on_number.clear()
        self.come_odds_on_number.clear()
        self.dont_come_odds_on_number.clear()

        self._redraw_chips()
        self._update_stats_display()

    def _draw_point_marker(self, point: int):
        """Draw the ON puck on the point number."""
        self.canvas.delete("puck")

        # Find the place bet spot for this point (must match _create_betting_spots)
        place_nums = [4, 5, 6, 8, 9, 10]
        if point in place_nums:
            idx = place_nums.index(point)
            place_x_start = 260
            place_width = 62
            place_spacing = 67  # place_width + 5
            x = place_x_start + idx * place_spacing + place_width // 2
            y = 160

            # Draw ON puck
            self.canvas.create_oval(
                x - 20, y - 12, x + 20, y + 12,
                fill='white', outline='black', width=2, tags="puck"
            )
            self.canvas.create_text(
                x, y, text="ON", font=('Arial', 12, 'bold'),
                fill='black', tags="puck"
            )

    def _clear_point_marker(self):
        """Remove the point marker."""
        self.canvas.delete("puck")
        # Show OFF puck and place bets status when point is off
        self._draw_place_bets_status()

    def _draw_place_bets_status(self):
        """Draw visual indicator showing place bets working status during come-out."""
        self.canvas.delete("place_status")

        # Only show during come-out roll
        if self.game.is_come_out:
            # Draw OFF puck in the don't come area
            puck_x = 200
            puck_y = 112

            if self.place_bets_working:
                # Show "ON" puck - place bets are working
                self.canvas.create_oval(
                    puck_x - 20, puck_y - 12, puck_x + 20, puck_y + 12,
                    fill='white', outline='black', width=2, tags="place_status"
                )
                self.canvas.create_text(
                    puck_x, puck_y, text="ON", font=('Arial', 10, 'bold'),
                    fill='black', tags="place_status"
                )
            else:
                # Show "OFF" puck - place bets not working
                self.canvas.create_oval(
                    puck_x - 20, puck_y - 12, puck_x + 20, puck_y + 12,
                    fill='#1a1a1a', outline='white', width=2, tags="place_status"
                )
                self.canvas.create_text(
                    puck_x, puck_y, text="OFF", font=('Arial', 9, 'bold'),
                    fill='white', tags="place_status"
                )

    def _clear_all_bets(self):
        """Clear all bets and return chips to bankroll (except contract bets after point)."""
        cleared_any = False
        contract_bets_protected = False

        for spot in self.betting_spots:
            # Contract bets cannot be removed after point is established
            if spot.bet_type in ('pass', 'dont_pass') and self.game.is_point_phase and spot.chips:
                contract_bets_protected = True
                continue  # Skip this bet

            if spot.chips:
                self.bankroll += spot.total_bet
                spot.chips.clear()
                cleared_any = True

        self._update_bankroll_display()
        self._redraw_chips()

        if contract_bets_protected:
            self._log("Cleared bets (Pass/Don't Pass protected - contract bets)")
        elif cleared_any:
            self._log("All bets cleared")
        else:
            self._log("No bets to clear")

    def _toggle_place_bets_working(self):
        """Toggle whether place bets are working during come-out roll."""
        self.place_bets_working = not self.place_bets_working

        if self.place_bets_working:
            self.place_working_var.set("Place Bets: ON")
            self.place_working_btn.configure(bg='#00aa00')  # Green when ON
            self._log("Place bets are now WORKING during come-out")
        else:
            self.place_working_var.set("Place Bets: OFF")
            self.place_working_btn.configure(bg='#cc0000')  # Red when OFF
            self._log("Place bets are now OFF during come-out")

        # Update the visual indicator on the table
        self._draw_place_bets_status()

    def _toggle_shooter_mode(self):
        """Toggle shooter mode on/off."""
        self.shooter_mode = not self.shooter_mode

        if self.shooter_mode:
            self.shooter_mode_var.set("Shooter: ON")
            self.shooter_mode_btn.configure(bg='#00aa00')  # Green when ON
            self._log("Shooter mode ON - Pass/Don't Pass only before point")
        else:
            self.shooter_mode_var.set("Shooter: OFF")
            self.shooter_mode_btn.configure(bg='#cc0000')  # Red when OFF
            self._log("Shooter mode OFF - Can bet on others' rolls anytime")

    def _update_bankroll_display(self):
        """Update the bankroll display showing total, rack, and bets."""
        bets_on_table = self._get_total_bets_at_risk()
        total_equity = self.bankroll + bets_on_table

        self.total_var.set(f"Total: ${total_equity:.2f}")
        self.rack_var.set(f"Rack: ${self.bankroll:.2f}")
        self.bets_var.set(f"Bets: ${bets_on_table:.2f}")

    def _get_total_bets_at_risk(self) -> float:
        """Calculate total amount of chips on the table."""
        total = sum(spot.total_bet for spot in self.betting_spots)
        # Add traveled come bets and their odds
        for chips in self.come_bets_on_number.values():
            total += sum(chips)
        for chips in self.dont_come_bets_on_number.values():
            total += sum(chips)
        for chips in self.come_odds_on_number.values():
            total += sum(chips)
        for chips in self.dont_come_odds_on_number.values():
            total += sum(chips)
        return total

    def _update_stats_display(self):
        """Update the statistics display panel."""
        stats = self.tracker.get_session_stats()
        shooter_stats = self.tracker.get_shooter_stats()

        # Update session stats
        net = stats['net_change']
        net_color = '#00ff00' if net >= 0 else '#ff4444'
        net_str = f"+${net:.2f}" if net >= 0 else f"-${abs(net):.2f}"

        self.stats_rolls_var.set(f"Rolls: {stats['total_rolls']}")
        self.stats_shooters_var.set(f"Shooters: {stats['total_shooters']}")
        self.stats_net_var.set(f"Net: {net_str}")
        self.stats_net_label.configure(fg=net_color)

        # Update shooter stats
        shooter_net = shooter_stats['net_change']
        shooter_net_color = '#00ff00' if shooter_net >= 0 else '#ff4444'
        shooter_net_str = f"+${shooter_net:.2f}" if shooter_net >= 0 else f"-${abs(shooter_net):.2f}"

        self.shooter_num_var.set(f"Shooter #{shooter_stats['shooter_number']}")
        self.shooter_rolls_var.set(f"Rolls: {shooter_stats['roll_count']}")
        self.shooter_net_var.set(f"Net: {shooter_net_str}")
        self.shooter_net_label.configure(fg=shooter_net_color)

    def _show_bankroll_graph(self):
        """Display the total equity over time graph."""
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        except ImportError:
            messagebox.showerror("Error", "matplotlib is required for graphs.\nInstall with: pip install matplotlib")
            return

        # If graph window already exists and is open, just bring it to front
        if self.graph_window is not None:
            try:
                self.graph_window.lift()
                self._update_graph()
                return
            except tk.TclError:
                # Window was closed
                self.graph_window = None

        # Create graph window
        self.graph_window = tk.Toplevel(self.root)
        self.graph_window.title("Total Equity History (Live)")
        self.graph_window.configure(bg='#1a0f2e')

        # Handle window close
        def on_graph_close():
            try:
                import matplotlib.pyplot as plt
                if self.graph_fig:
                    plt.close(self.graph_fig)
            except Exception:
                pass
            self.graph_fig = None
            self.graph_ax = None
            self.graph_canvas = None
            if self.graph_window:
                try:
                    self.graph_window.destroy()
                except Exception:
                    pass
            self.graph_window = None

        self.graph_window.protocol("WM_DELETE_WINDOW", on_graph_close)

        # Create figure
        self.graph_fig, self.graph_ax = plt.subplots(figsize=(10, 6), facecolor='#1a0f2e')
        self.graph_ax.set_facecolor('#2d1b4e')

        # Embed in tkinter
        self.graph_canvas = FigureCanvasTkAgg(self.graph_fig, master=self.graph_window)
        self.graph_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Stats label
        self.graph_stats_var = tk.StringVar(value="")
        stats_frame = tk.Frame(self.graph_window, bg='#1a0f2e')
        stats_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(stats_frame, textvariable=self.graph_stats_var, fg='white', bg='#1a0f2e',
                 font=('Arial', 10)).pack()

        # Initial draw
        self._update_graph()

    def _update_graph(self):
        """Update the graph with current data."""
        if self.graph_ax is None or self.graph_canvas is None:
            return

        try:
            # Clear previous plot
            self.graph_ax.clear()

            # Get data (equity = cash + chips on table)
            rolls, equity = self.tracker.get_equity_series()
            shooter_boundaries = self.tracker.get_shooter_boundaries()

            # Plot equity line
            if rolls:
                self.graph_ax.plot(rolls, equity, color='#ffd700', linewidth=2, label='Total Equity')

                # Add starting bankroll reference line
                self.graph_ax.axhline(y=self.tracker.starting_bankroll, color='#888888',
                           linestyle='--', linewidth=1, label='Starting Bankroll')

                # Get y-axis range for label positioning
                y_min = min(min(equity), self.tracker.starting_bankroll) * 0.95
                y_max = max(max(equity), self.tracker.starting_bankroll) * 1.05
                self.graph_ax.set_ylim(y_min, y_max)

                # Mark shooter starts with vertical lines and labels
                shooter_starts = self._get_shooter_starts()
                for shooter_num, start_roll in shooter_starts:
                    # Draw vertical line at shooter start
                    self.graph_ax.axvline(x=start_roll, color='#00aaff', linestyle='-',
                                         linewidth=1.5, alpha=0.7)
                    # Add label at top of graph
                    self.graph_ax.text(start_roll + 0.3, y_max * 0.98, f'S{shooter_num}',
                                      color='#00aaff', fontsize=9, fontweight='bold',
                                      verticalalignment='top')

                # Fill area under curve
                self.graph_ax.fill_between(rolls, equity, self.tracker.starting_bankroll,
                                where=[e >= self.tracker.starting_bankroll for e in equity],
                                color='#00ff00', alpha=0.2)
                self.graph_ax.fill_between(rolls, equity, self.tracker.starting_bankroll,
                                where=[e < self.tracker.starting_bankroll for e in equity],
                                color='#ff4444', alpha=0.2)

            # Styling
            self.graph_ax.set_facecolor('#2d1b4e')
            self.graph_ax.set_xlabel('Roll Number', color='white')
            self.graph_ax.set_ylabel('Total Equity ($)', color='white')
            self.graph_ax.set_title('Total Equity Over Time (Live)', color='#ffd700', fontsize=14, fontweight='bold')
            self.graph_ax.tick_params(colors='white')
            self.graph_ax.spines['bottom'].set_color('white')
            self.graph_ax.spines['top'].set_color('white')
            self.graph_ax.spines['left'].set_color('white')
            self.graph_ax.spines['right'].set_color('white')
            self.graph_ax.legend(facecolor='#2d1b4e', labelcolor='white', loc='upper left')
            self.graph_ax.grid(True, alpha=0.3, color='white')

            self.graph_fig.tight_layout()
            self.graph_canvas.draw()

            # Update stats
            stats = self.tracker.get_session_stats()
            stats_text = (
                f"Total Rolls: {stats['total_rolls']}  |  "
                f"Shooters: {stats['total_shooters']}  |  "
                f"Winning Rolls: {stats['win_rolls']}  |  "
                f"Losing Rolls: {stats['loss_rolls']}  |  "
                f"ROI: {stats['roi_percent']:.2f}%"
            )
            self.graph_stats_var.set(stats_text)
        except Exception:
            pass  # Window might have been closed

    def _get_shooter_starts(self) -> list[tuple[int, int]]:
        """Get list of (shooter_number, start_roll) for all shooters."""
        shooter_starts = []

        # Add completed shooters
        for shooter in self.tracker.shooter_history:
            shooter_starts.append((shooter.shooter_number, shooter.start_roll))

        # Add current shooter if exists
        if self.tracker.current_shooter:
            shooter_starts.append((
                self.tracker.current_shooter.shooter_number,
                self.tracker.current_shooter.start_roll
            ))

        return shooter_starts

    def _log(self, message: str):
        """Add a message to the game log."""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)


def run_table_gui():
    """Launch the craps table GUI."""
    root = tk.Tk()
    app = CrapsTableGUI(root)
    root.mainloop()
