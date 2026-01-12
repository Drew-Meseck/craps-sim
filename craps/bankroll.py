"""
Bankroll tracking and statistics for the craps simulator.
"""
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class RollRecord:
    """Record of a single roll's impact on bankroll."""
    roll_number: int
    shooter_number: int
    dice_total: int
    die1: int
    die2: int
    bankroll_before: float
    bankroll_after: float
    bets_before: float      # Chips on table before roll
    bets_after: float       # Chips on table after roll (bets still active)
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def equity_before(self) -> float:
        """Total equity before roll (cash + chips on table)."""
        return self.bankroll_before + self.bets_before

    @property
    def equity_after(self) -> float:
        """Total equity after roll (cash + chips on table)."""
        return self.bankroll_after + self.bets_after

    @property
    def net_change(self) -> float:
        """Net change in total equity from this roll."""
        return self.equity_after - self.equity_before

    @property
    def is_win(self) -> bool:
        """True if total equity increased."""
        return self.net_change > 0

    @property
    def is_loss(self) -> bool:
        """True if total equity decreased."""
        return self.net_change < 0


@dataclass
class ShooterRecord:
    """Record of a shooter's session."""
    shooter_number: int
    start_roll: int
    end_roll: Optional[int] = None
    bankroll_start: float = 0.0
    bankroll_end: float = 0.0
    rolls: list[RollRecord] = field(default_factory=list)

    @property
    def net_change(self) -> float:
        """Net change during this shooter's session."""
        return self.bankroll_end - self.bankroll_start

    @property
    def roll_count(self) -> int:
        """Number of rolls for this shooter."""
        return len(self.rolls)

    @property
    def is_complete(self) -> bool:
        """True if shooter has sevened out."""
        return self.end_roll is not None


class BankrollTracker:
    """Tracks bankroll history across rolls and shooters."""

    def __init__(self, starting_bankroll: float):
        self.starting_bankroll = starting_bankroll
        self.current_bankroll = starting_bankroll
        self.current_bets = 0.0  # Chips currently on table
        self.roll_history: list[RollRecord] = []
        self.shooter_history: list[ShooterRecord] = []
        self.current_shooter: Optional[ShooterRecord] = None
        self._roll_count = 0
        self._shooter_count = 0

    @property
    def current_equity(self) -> float:
        """Current total equity (cash + chips on table)."""
        return self.current_bankroll + self.current_bets

    def start_session(self, bankroll: float):
        """Start a new tracking session."""
        self.starting_bankroll = bankroll
        self.current_bankroll = bankroll
        self.current_bets = 0.0
        self.roll_history.clear()
        self.shooter_history.clear()
        self.current_shooter = None
        self._roll_count = 0
        self._shooter_count = 0
        self._start_new_shooter(bankroll)

    def _start_new_shooter(self, bankroll: float):
        """Start tracking a new shooter."""
        self._shooter_count += 1
        self.current_shooter = ShooterRecord(
            shooter_number=self._shooter_count,
            start_roll=self._roll_count + 1,
            bankroll_start=bankroll
        )

    def record_roll(self, die1: int, die2: int, bankroll_before: float,
                    bankroll_after: float, bets_before: float, bets_after: float):
        """Record a roll and its impact on bankroll and equity."""
        self._roll_count += 1
        self.current_bankroll = bankroll_after
        self.current_bets = bets_after

        # Ensure we have a shooter
        if self.current_shooter is None:
            self._start_new_shooter(bankroll_before + bets_before)

        record = RollRecord(
            roll_number=self._roll_count,
            shooter_number=self._shooter_count,
            dice_total=die1 + die2,
            die1=die1,
            die2=die2,
            bankroll_before=bankroll_before,
            bankroll_after=bankroll_after,
            bets_before=bets_before,
            bets_after=bets_after
        )

        self.roll_history.append(record)
        self.current_shooter.rolls.append(record)
        self.current_shooter.bankroll_end = bankroll_after + bets_after

        return record

    def end_shooter(self, seven_out: bool = True):
        """End the current shooter's session."""
        if self.current_shooter:
            self.current_shooter.end_roll = self._roll_count
            self.shooter_history.append(self.current_shooter)
            # Start new shooter
            self._start_new_shooter(self.current_bankroll)

    def get_session_stats(self) -> dict:
        """Get statistics for the current session."""
        if not self.roll_history:
            return {
                'total_rolls': 0,
                'total_shooters': 0,
                'net_change': 0.0,
                'win_rolls': 0,
                'loss_rolls': 0,
                'push_rolls': 0,
                'biggest_win': 0.0,
                'biggest_loss': 0.0,
                'current_equity': self.current_equity,
                'starting_bankroll': self.starting_bankroll,
                'roi_percent': 0.0,
            }

        win_rolls = sum(1 for r in self.roll_history if r.is_win)
        loss_rolls = sum(1 for r in self.roll_history if r.is_loss)
        push_rolls = len(self.roll_history) - win_rolls - loss_rolls

        changes = [r.net_change for r in self.roll_history]
        biggest_win = max(changes) if changes else 0.0
        biggest_loss = min(changes) if changes else 0.0

        net_change = self.current_equity - self.starting_bankroll
        roi_percent = (net_change / self.starting_bankroll * 100) if self.starting_bankroll > 0 else 0

        return {
            'total_rolls': self._roll_count,
            'total_shooters': self._shooter_count,
            'net_change': net_change,
            'win_rolls': win_rolls,
            'loss_rolls': loss_rolls,
            'push_rolls': push_rolls,
            'biggest_win': biggest_win,
            'biggest_loss': biggest_loss,
            'current_equity': self.current_equity,
            'starting_bankroll': self.starting_bankroll,
            'roi_percent': roi_percent,
        }

    def get_shooter_stats(self, shooter_number: Optional[int] = None) -> dict:
        """Get statistics for a specific shooter or current shooter."""
        if shooter_number is not None:
            # Find the shooter
            shooter = None
            for s in self.shooter_history:
                if s.shooter_number == shooter_number:
                    shooter = s
                    break
            if shooter is None and self.current_shooter and self.current_shooter.shooter_number == shooter_number:
                shooter = self.current_shooter
        else:
            shooter = self.current_shooter

        if shooter is None or not shooter.rolls:
            return {
                'shooter_number': 0,
                'roll_count': 0,
                'net_change': 0.0,
                'is_complete': False,
            }

        return {
            'shooter_number': shooter.shooter_number,
            'roll_count': shooter.roll_count,
            'net_change': shooter.net_change,
            'bankroll_start': shooter.bankroll_start,
            'bankroll_end': shooter.bankroll_end,
            'is_complete': shooter.is_complete,
        }

    def get_equity_series(self) -> tuple[list[int], list[float]]:
        """Get total equity values over time for graphing.

        Returns (roll_numbers, equity_values) where roll 0 is starting equity.
        Total equity = cash bankroll + chips on table.
        """
        roll_numbers = [0]
        equity_values = [self.starting_bankroll]

        for record in self.roll_history:
            roll_numbers.append(record.roll_number)
            equity_values.append(record.equity_after)

        return roll_numbers, equity_values

    def get_shooter_boundaries(self) -> list[int]:
        """Get roll numbers where shooters changed (for graph markers)."""
        boundaries = []
        for shooter in self.shooter_history:
            if shooter.end_roll:
                boundaries.append(shooter.end_roll)
        return boundaries
