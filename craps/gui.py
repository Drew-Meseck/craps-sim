"""
Craps simulator GUI using tkinter.
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Optional
import random

from .game import CrapsGame, TableRules, DiceRoll, GamePhase
from .bets import (
    BetManager, BetResult, BetStatus,
    PassLineBet, DontPassBet, ComeBet, DontComeBet,
    PlaceBet, FieldBet, OddsBet,
    AnyCrapsBet, AnySevenBet, HornBet, HardwayBet
)


class DiceDisplay(tk.Canvas):
    """Canvas widget to display dice."""

    DOT_POSITIONS = {
        1: [(0.5, 0.5)],
        2: [(0.25, 0.25), (0.75, 0.75)],
        3: [(0.25, 0.25), (0.5, 0.5), (0.75, 0.75)],
        4: [(0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)],
        5: [(0.25, 0.25), (0.75, 0.25), (0.5, 0.5), (0.25, 0.75), (0.75, 0.75)],
        6: [(0.25, 0.25), (0.75, 0.25), (0.25, 0.5), (0.75, 0.5), (0.25, 0.75), (0.75, 0.75)],
    }

    def __init__(self, parent, size: int = 60):
        super().__init__(parent, width=size * 2 + 20, height=size + 10, bg='#1a5f1a')
        self.size = size
        self.die1 = 1
        self.die2 = 1
        self._draw_dice()

    def set_dice(self, die1: int, die2: int):
        """Update the dice display."""
        self.die1 = die1
        self.die2 = die2
        self._draw_dice()

    def _draw_dice(self):
        """Draw both dice."""
        self.delete("all")
        self._draw_single_die(5, 5, self.die1)
        self._draw_single_die(self.size + 15, 5, self.die2)

    def _draw_single_die(self, x: int, y: int, value: int):
        """Draw a single die at position (x, y)."""
        # Die body
        self.create_rectangle(
            x, y, x + self.size, y + self.size,
            fill='white', outline='black', width=2
        )

        # Dots
        dot_radius = self.size // 10
        for px, py in self.DOT_POSITIONS[value]:
            cx = x + px * self.size
            cy = y + py * self.size
            self.create_oval(
                cx - dot_radius, cy - dot_radius,
                cx + dot_radius, cy + dot_radius,
                fill='black'
            )


class BetButton(tk.Button):
    """A button representing a betting area on the craps table."""

    def __init__(self, parent, text: str, bet_type: str, callback, **kwargs):
        super().__init__(parent, text=text, **kwargs)
        self.bet_type = bet_type
        self.callback = callback
        self.configure(command=self._on_click)
        self.bet_amount = 0

    def _on_click(self):
        self.callback(self.bet_type)

    def update_display(self, amount: float):
        """Update button to show bet amount."""
        self.bet_amount = amount
        if amount > 0:
            self.configure(bg='yellow', text=f"{self.cget('text').split()[0]}\n${amount:.0f}")
        else:
            self.configure(bg='SystemButtonFace')


class CrapsGUI:
    """Main GUI for the craps simulator."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Craps Simulator")
        self.root.geometry("900x700")
        self.root.configure(bg='#1a5f1a')

        # Initialize game state
        self.rules = TableRules()
        self.game = CrapsGame(self.rules)
        self.bet_manager = BetManager(self.rules)
        self.bankroll = 1000.0
        self.current_bet_amount = 5

        # Track pending bets for current roll
        self.pending_bets: dict[str, float] = {}

        # Setup callbacks
        self._setup_game_callbacks()

        # Build UI
        self._build_ui()

    def _setup_game_callbacks(self):
        """Register game event callbacks."""
        self.game.on_roll(self._on_roll)
        self.game.on_point_established(self._on_point_established)
        self.game.on_point_won(self._on_point_won)
        self.game.on_seven_out(self._on_seven_out)

    def _build_ui(self):
        """Build the main UI."""
        # Top frame - bankroll and controls
        self._build_top_frame()

        # Middle frame - dice and point display
        self._build_dice_frame()

        # Main frame - betting areas
        self._build_betting_frame()

        # Bottom frame - history and messages
        self._build_bottom_frame()

    def _build_top_frame(self):
        """Build the top control frame."""
        frame = tk.Frame(self.root, bg='#1a5f1a')
        frame.pack(fill=tk.X, padx=10, pady=5)

        # Bankroll display
        self.bankroll_var = tk.StringVar(value=f"Bankroll: ${self.bankroll:.2f}")
        bankroll_label = tk.Label(
            frame, textvariable=self.bankroll_var,
            font=('Arial', 14, 'bold'), fg='white', bg='#1a5f1a'
        )
        bankroll_label.pack(side=tk.LEFT, padx=10)

        # Bet amount selector
        tk.Label(frame, text="Bet: $", fg='white', bg='#1a5f1a', font=('Arial', 12)).pack(side=tk.LEFT)
        self.bet_amount_var = tk.StringVar(value=str(self.current_bet_amount))
        bet_entry = tk.Entry(frame, textvariable=self.bet_amount_var, width=6, font=('Arial', 12))
        bet_entry.pack(side=tk.LEFT, padx=5)

        # Quick bet buttons
        for amount in [5, 10, 25, 100]:
            btn = tk.Button(
                frame, text=f"${amount}",
                command=lambda a=amount: self._set_bet_amount(a)
            )
            btn.pack(side=tk.LEFT, padx=2)

        # Settings button
        settings_btn = tk.Button(frame, text="Table Rules", command=self._show_settings)
        settings_btn.pack(side=tk.RIGHT, padx=10)

        # Roll button
        self.roll_btn = tk.Button(
            frame, text="ROLL DICE", font=('Arial', 14, 'bold'),
            bg='red', fg='white', command=self._roll_dice,
            width=12, height=1
        )
        self.roll_btn.pack(side=tk.RIGHT, padx=20)

    def _build_dice_frame(self):
        """Build the dice display area."""
        frame = tk.Frame(self.root, bg='#1a5f1a')
        frame.pack(fill=tk.X, padx=10, pady=10)

        # Dice display
        dice_container = tk.Frame(frame, bg='#1a5f1a')
        dice_container.pack(side=tk.LEFT, padx=20)

        tk.Label(dice_container, text="DICE", fg='white', bg='#1a5f1a', font=('Arial', 10)).pack()
        self.dice_display = DiceDisplay(dice_container, size=50)
        self.dice_display.pack()

        # Point display
        point_container = tk.Frame(frame, bg='#1a5f1a')
        point_container.pack(side=tk.LEFT, padx=40)

        tk.Label(point_container, text="POINT", fg='white', bg='#1a5f1a', font=('Arial', 10)).pack()
        self.point_var = tk.StringVar(value="OFF")
        self.point_label = tk.Label(
            point_container, textvariable=self.point_var,
            font=('Arial', 24, 'bold'), fg='yellow', bg='#1a5f1a',
            width=4
        )
        self.point_label.pack()

        # Phase display
        phase_container = tk.Frame(frame, bg='#1a5f1a')
        phase_container.pack(side=tk.LEFT, padx=40)

        tk.Label(phase_container, text="PHASE", fg='white', bg='#1a5f1a', font=('Arial', 10)).pack()
        self.phase_var = tk.StringVar(value="COME OUT")
        self.phase_label = tk.Label(
            phase_container, textvariable=self.phase_var,
            font=('Arial', 16, 'bold'), fg='white', bg='#1a5f1a'
        )
        self.phase_label.pack()

        # Last result display
        result_container = tk.Frame(frame, bg='#1a5f1a')
        result_container.pack(side=tk.RIGHT, padx=20)

        tk.Label(result_container, text="LAST ROLL", fg='white', bg='#1a5f1a', font=('Arial', 10)).pack()
        self.result_var = tk.StringVar(value="-")
        self.result_label = tk.Label(
            result_container, textvariable=self.result_var,
            font=('Arial', 24, 'bold'), fg='cyan', bg='#1a5f1a',
            width=3
        )
        self.result_label.pack()

    def _build_betting_frame(self):
        """Build the main betting area."""
        main_frame = tk.Frame(self.root, bg='#0d3d0d', relief=tk.RIDGE, bd=3)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Pass Line area
        pass_frame = tk.Frame(main_frame, bg='#0d3d0d')
        pass_frame.pack(fill=tk.X, padx=5, pady=5)

        self.pass_btn = tk.Button(
            pass_frame, text="PASS LINE\n(1.41% edge)", width=15, height=3,
            bg='#4a4a4a', fg='white', font=('Arial', 10, 'bold'),
            command=lambda: self._place_bet('pass')
        )
        self.pass_btn.pack(side=tk.LEFT, padx=5)

        self.dont_pass_btn = tk.Button(
            pass_frame, text="DON'T PASS\n(1.36% edge)", width=15, height=3,
            bg='#4a4a4a', fg='white', font=('Arial', 10, 'bold'),
            command=lambda: self._place_bet('dont_pass')
        )
        self.dont_pass_btn.pack(side=tk.LEFT, padx=5)

        self.come_btn = tk.Button(
            pass_frame, text="COME\n(1.41% edge)", width=12, height=3,
            bg='#4a4a4a', fg='white', font=('Arial', 10),
            command=lambda: self._place_bet('come')
        )
        self.come_btn.pack(side=tk.LEFT, padx=5)

        self.dont_come_btn = tk.Button(
            pass_frame, text="DON'T COME\n(1.36% edge)", width=12, height=3,
            bg='#4a4a4a', fg='white', font=('Arial', 10),
            command=lambda: self._place_bet('dont_come')
        )
        self.dont_come_btn.pack(side=tk.LEFT, padx=5)

        self.field_btn = tk.Button(
            pass_frame, text=f"FIELD\n2,3,4,9,10,11,12\n({self._get_field_edge():.2f}% edge)",
            width=15, height=3,
            bg='#4a4a4a', fg='white', font=('Arial', 9),
            command=lambda: self._place_bet('field')
        )
        self.field_btn.pack(side=tk.LEFT, padx=5)

        # Place bets
        place_frame = tk.Frame(main_frame, bg='#0d3d0d')
        place_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(place_frame, text="PLACE BETS:", fg='white', bg='#0d3d0d',
                 font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)

        self.place_btns = {}
        for num in [4, 5, 6, 8, 9, 10]:
            edge = PlaceBet.HOUSE_EDGES[num]
            btn = tk.Button(
                place_frame, text=f"{num}\n({edge:.2f}%)", width=8, height=2,
                bg='#4a4a4a', fg='white', font=('Arial', 9),
                command=lambda n=num: self._place_bet(f'place_{n}')
            )
            btn.pack(side=tk.LEFT, padx=3)
            self.place_btns[num] = btn

        # Hardways
        hard_frame = tk.Frame(main_frame, bg='#0d3d0d')
        hard_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(hard_frame, text="HARDWAYS:", fg='white', bg='#0d3d0d',
                 font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)

        self.hard_btns = {}
        for num in [4, 6, 8, 10]:
            payout = HardwayBet.HARDWAY_PAYOUTS[num]
            edge = HardwayBet.HARDWAY_EDGES[num]
            btn = tk.Button(
                hard_frame, text=f"Hard {num}\n{payout}:1\n({edge:.1f}%)", width=10, height=3,
                bg='#4a4a4a', fg='white', font=('Arial', 8),
                command=lambda n=num: self._place_bet(f'hard_{n}')
            )
            btn.pack(side=tk.LEFT, padx=3)
            self.hard_btns[num] = btn

        # Proposition bets
        prop_frame = tk.Frame(main_frame, bg='#0d3d0d')
        prop_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(prop_frame, text="PROPS:", fg='white', bg='#0d3d0d',
                 font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)

        self.any_craps_btn = tk.Button(
            prop_frame, text="Any Craps\n7:1\n(11.1%)", width=10, height=3,
            bg='#4a4a4a', fg='white', font=('Arial', 8),
            command=lambda: self._place_bet('any_craps')
        )
        self.any_craps_btn.pack(side=tk.LEFT, padx=3)

        self.any_seven_btn = tk.Button(
            prop_frame, text="Any 7\n4:1\n(16.7%)", width=10, height=3,
            bg='#4a4a4a', fg='white', font=('Arial', 8),
            command=lambda: self._place_bet('any_seven')
        )
        self.any_seven_btn.pack(side=tk.LEFT, padx=3)

        self.horn_btn = tk.Button(
            prop_frame, text="Horn\n2,3,11,12\n(12.5%)", width=10, height=3,
            bg='#4a4a4a', fg='white', font=('Arial', 8),
            command=lambda: self._place_bet('horn')
        )
        self.horn_btn.pack(side=tk.LEFT, padx=3)

        # Active bets display
        bets_frame = tk.LabelFrame(main_frame, text="Active Bets", bg='#0d3d0d', fg='white')
        bets_frame.pack(fill=tk.X, padx=5, pady=5)

        self.bets_text = tk.Text(bets_frame, height=3, width=80, bg='#1a1a1a', fg='white')
        self.bets_text.pack(padx=5, pady=5)

    def _build_bottom_frame(self):
        """Build the bottom message/history area."""
        frame = tk.LabelFrame(self.root, text="Game Log", bg='#1a5f1a', fg='white')
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Scrollable text area
        self.log_text = tk.Text(frame, height=8, bg='#1a1a1a', fg='#00ff00', font=('Consolas', 10))
        scrollbar = tk.Scrollbar(frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self._log("Welcome to Craps Simulator! Place your bets and roll the dice.")
        self._log(f"Table minimum: ${self.rules.minimum_bet}, Maximum: ${self.rules.maximum_bet}")

    def _get_field_edge(self) -> float:
        """Calculate field bet house edge based on rules."""
        if self.rules.field_2_payout == 2 and self.rules.field_12_payout == 2:
            return 5.56
        elif self.rules.field_2_payout == 2 and self.rules.field_12_payout == 3:
            return 2.78
        return 5.56

    def _set_bet_amount(self, amount: int):
        """Set the current bet amount."""
        self.current_bet_amount = amount
        self.bet_amount_var.set(str(amount))

    def _get_bet_amount(self) -> float:
        """Get the current bet amount from the entry."""
        try:
            amount = float(self.bet_amount_var.get())
            if amount < self.rules.minimum_bet:
                messagebox.showwarning("Invalid Bet", f"Minimum bet is ${self.rules.minimum_bet}")
                return 0
            if amount > self.rules.maximum_bet:
                messagebox.showwarning("Invalid Bet", f"Maximum bet is ${self.rules.maximum_bet}")
                return 0
            if amount > self.bankroll:
                messagebox.showwarning("Insufficient Funds", "You don't have enough money!")
                return 0
            return amount
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number")
            return 0

    def _place_bet(self, bet_type: str):
        """Place a bet of the specified type."""
        amount = self._get_bet_amount()
        if amount <= 0:
            return

        # Create the appropriate bet
        bet = None
        if bet_type == 'pass':
            if self.game.is_point_phase:
                messagebox.showinfo("Cannot Bet", "Cannot place Pass Line bet after point is established")
                return
            bet = PassLineBet(amount, self.rules)
        elif bet_type == 'dont_pass':
            if self.game.is_point_phase:
                messagebox.showinfo("Cannot Bet", "Cannot place Don't Pass bet after point is established")
                return
            bet = DontPassBet(amount, self.rules)
        elif bet_type == 'come':
            if self.game.is_come_out:
                messagebox.showinfo("Cannot Bet", "Cannot place Come bet during come-out roll")
                return
            bet = ComeBet(amount, self.rules)
        elif bet_type == 'dont_come':
            if self.game.is_come_out:
                messagebox.showinfo("Cannot Bet", "Cannot place Don't Come bet during come-out roll")
                return
            bet = DontComeBet(amount, self.rules)
        elif bet_type == 'field':
            bet = FieldBet(amount, self.rules)
        elif bet_type.startswith('place_'):
            num = int(bet_type.split('_')[1])
            bet = PlaceBet(amount, self.rules, num)
        elif bet_type.startswith('hard_'):
            num = int(bet_type.split('_')[1])
            bet = HardwayBet(amount, self.rules, num)
        elif bet_type == 'any_craps':
            bet = AnyCrapsBet(amount, self.rules)
        elif bet_type == 'any_seven':
            bet = AnySevenBet(amount, self.rules)
        elif bet_type == 'horn':
            bet = HornBet(amount, self.rules)

        if bet:
            if self.bet_manager.place_bet(bet):
                self.bankroll -= amount
                self._update_bankroll_display()
                self._update_bets_display()
                self._log(f"Placed ${amount:.2f} on {bet.name}")
            else:
                messagebox.showerror("Bet Failed", "Could not place bet")

    def _roll_dice(self):
        """Roll the dice and resolve bets."""
        if not self.bet_manager.active_bets:
            messagebox.showinfo("No Bets", "Please place at least one bet before rolling")
            return

        roll = self.game.roll_dice()
        self.dice_display.set_dice(roll.die1, roll.die2)
        self.result_var.set(str(roll.total))

    def _on_roll(self, roll: DiceRoll):
        """Handle a dice roll event."""
        self._log(f"Rolled {roll}")

        # Resolve all bets
        results = self.bet_manager.resolve_all(roll, self.game.phase, self.game.point)

        total_win = 0
        total_loss = 0

        for bet, result in results:
            if result.status == BetStatus.WON:
                winnings = result.payout + bet.amount  # Payout + original bet
                self.bankroll += winnings
                total_win += result.payout
                self._log(f"  WIN: {bet.name} - {result.message} (+${result.payout:.2f})")
            elif result.status == BetStatus.PUSH:
                self.bankroll += bet.amount  # Return original bet
                self._log(f"  PUSH: {bet.name} - {result.message}")
            else:
                total_loss += bet.amount
                self._log(f"  LOSE: {bet.name} - {result.message}")

        if total_win > 0:
            self._log(f"  Total won: +${total_win:.2f}")
        if total_loss > 0:
            self._log(f"  Total lost: -${total_loss:.2f}")

        self._update_bankroll_display()
        self._update_bets_display()

    def _on_point_established(self, point: int):
        """Handle point establishment."""
        self.point_var.set(str(point))
        self.phase_var.set("POINT")
        self._log(f"Point established: {point}")

    def _on_point_won(self):
        """Handle point being made."""
        self.point_var.set("OFF")
        self.phase_var.set("COME OUT")
        self._log("POINT MADE! New shooter.")

    def _on_seven_out(self):
        """Handle seven-out."""
        self.point_var.set("OFF")
        self.phase_var.set("COME OUT")
        self._log("SEVEN OUT! New shooter.")

    def _update_bankroll_display(self):
        """Update the bankroll display."""
        self.bankroll_var.set(f"Bankroll: ${self.bankroll:.2f}")

    def _update_bets_display(self):
        """Update the active bets display."""
        self.bets_text.delete(1.0, tk.END)
        if not self.bet_manager.active_bets:
            self.bets_text.insert(tk.END, "No active bets")
        else:
            for bet in self.bet_manager.active_bets:
                self.bets_text.insert(tk.END, f"{bet.name}: ${bet.amount:.2f}  ")

    def _log(self, message: str):
        """Add a message to the game log."""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    def _show_settings(self):
        """Show the table rules settings dialog."""
        dialog = TableRulesDialog(self.root, self.rules)
        if dialog.result:
            self.rules = dialog.result
            self.game.rules = self.rules
            self.bet_manager.rules = self.rules
            # Update field button text
            self.field_btn.configure(text=f"FIELD\n2,3,4,9,10,11,12\n({self._get_field_edge():.2f}% edge)")
            self._log(f"Table rules updated: Min ${self.rules.minimum_bet}, Max ${self.rules.maximum_bet}")
            self._log(f"Field 2 pays {self.rules.field_2_payout}:1, Field 12 pays {self.rules.field_12_payout}:1")


class TableRulesDialog(simpledialog.Dialog):
    """Dialog for adjusting table rules."""

    def __init__(self, parent, current_rules: TableRules):
        self.current_rules = current_rules
        self.result: Optional[TableRules] = None
        super().__init__(parent, "Table Rules")

    def body(self, master):
        tk.Label(master, text="Minimum Bet:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.min_bet_var = tk.StringVar(value=str(self.current_rules.minimum_bet))
        tk.Entry(master, textvariable=self.min_bet_var).grid(row=0, column=1, pady=2)

        tk.Label(master, text="Maximum Bet:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.max_bet_var = tk.StringVar(value=str(self.current_rules.maximum_bet))
        tk.Entry(master, textvariable=self.max_bet_var).grid(row=1, column=1, pady=2)

        tk.Label(master, text="Max Odds Multiplier:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.odds_var = tk.StringVar(value=str(self.current_rules.maximum_odds_multiplier))
        tk.Entry(master, textvariable=self.odds_var).grid(row=2, column=1, pady=2)

        tk.Label(master, text="Field 2 Payout (x:1):").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.field_2_var = tk.StringVar(value=str(self.current_rules.field_2_payout))
        ttk.Combobox(master, textvariable=self.field_2_var, values=["2", "3"]).grid(row=3, column=1, pady=2)

        tk.Label(master, text="Field 12 Payout (x:1):").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.field_12_var = tk.StringVar(value=str(self.current_rules.field_12_payout))
        ttk.Combobox(master, textvariable=self.field_12_var, values=["2", "3"]).grid(row=4, column=1, pady=2)

        return master

    def apply(self):
        try:
            self.result = TableRules(
                minimum_bet=int(self.min_bet_var.get()),
                maximum_bet=int(self.max_bet_var.get()),
                maximum_odds_multiplier=int(self.odds_var.get()),
                field_2_payout=int(self.field_2_var.get()),
                field_12_payout=int(self.field_12_var.get())
            )
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
            self.result = None


def run_gui():
    """Launch the craps simulator GUI."""
    root = tk.Tk()
    app = CrapsGUI(root)
    root.mainloop()
