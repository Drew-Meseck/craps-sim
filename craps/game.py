"""
Core craps game logic - dice rolling, point system, and game state management.
"""
import random
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Callable


class GamePhase(Enum):
    """Represents the current phase of the craps game."""
    COME_OUT = "come_out"  # Initial roll, establishing the point
    POINT = "point"        # Point has been established, rolling for point or 7


@dataclass
class DiceRoll:
    """Represents a single roll of two dice."""
    die1: int
    die2: int

    @property
    def total(self) -> int:
        return self.die1 + self.die2

    @property
    def is_hard(self) -> bool:
        """Returns True if both dice show the same number (hardway)."""
        return self.die1 == self.die2

    def __str__(self) -> str:
        return f"({self.die1}, {self.die2}) = {self.total}"


@dataclass
class TableRules:
    """Configurable table rules for the craps game."""
    minimum_bet: int = 5
    maximum_bet: int = 5000
    maximum_odds_multiplier: int = 3  # 3x, 4x, 5x odds commonly offered

    # Field bet payouts (2 and 12 often pay extra)
    field_2_payout: int = 2   # 2:1 on 2
    field_12_payout: int = 2  # 2:1 on 12 (some tables pay 3:1)

    # Big 6/8 payout (even money, worse than place bets)
    big_6_8_payout: float = 1.0

    def __post_init__(self):
        if self.minimum_bet < 1:
            raise ValueError("Minimum bet must be at least 1")
        if self.maximum_bet < self.minimum_bet:
            raise ValueError("Maximum bet must be >= minimum bet")


class CrapsGame:
    """
    Main craps game controller handling game state and dice rolls.
    """

    def __init__(self, rules: Optional[TableRules] = None):
        self.rules = rules or TableRules()
        self.phase = GamePhase.COME_OUT
        self.point: Optional[int] = None
        self.roll_history: list[DiceRoll] = []
        self.shooter_rolls: int = 0

        # Callbacks for game events
        self._on_roll_callbacks: list[Callable[[DiceRoll], None]] = []
        self._on_point_established_callbacks: list[Callable[[int], None]] = []
        self._on_point_won_callbacks: list[Callable[[], None]] = []
        self._on_seven_out_callbacks: list[Callable[[], None]] = []

    def roll_dice(self) -> DiceRoll:
        """Roll the dice and process the result."""
        die1 = random.randint(1, 6)
        die2 = random.randint(1, 6)
        roll = DiceRoll(die1, die2)

        self.roll_history.append(roll)
        self.shooter_rolls += 1

        # Notify roll callbacks
        for callback in self._on_roll_callbacks:
            callback(roll)

        # Process the roll based on current phase
        self._process_roll(roll)

        return roll

    def _process_roll(self, roll: DiceRoll) -> None:
        """Process a roll based on the current game phase."""
        total = roll.total

        if self.phase == GamePhase.COME_OUT:
            self._process_come_out_roll(total)
        else:
            self._process_point_roll(total)

    def _process_come_out_roll(self, total: int) -> None:
        """Process a come-out roll."""
        if total in (7, 11):
            # Natural - pass line wins, don't pass loses
            # Phase stays COME_OUT for next roll
            pass
        elif total in (2, 3, 12):
            # Craps - pass line loses, don't pass wins (12 pushes for don't)
            # Phase stays COME_OUT for next roll
            pass
        else:
            # Point established (4, 5, 6, 8, 9, 10)
            self.point = total
            self.phase = GamePhase.POINT
            for callback in self._on_point_established_callbacks:
                callback(total)

    def _process_point_roll(self, total: int) -> None:
        """Process a roll during the point phase."""
        if total == self.point:
            # Point made - pass line wins
            for callback in self._on_point_won_callbacks:
                callback()
            self._reset_for_new_shooter(keep_shooter=True)
        elif total == 7:
            # Seven out - pass line loses, new shooter
            for callback in self._on_seven_out_callbacks:
                callback()
            self._reset_for_new_shooter(keep_shooter=False)

    def _reset_for_new_shooter(self, keep_shooter: bool = False) -> None:
        """Reset game state for a new come-out roll."""
        self.phase = GamePhase.COME_OUT
        self.point = None
        if not keep_shooter:
            self.shooter_rolls = 0

    def on_roll(self, callback: Callable[[DiceRoll], None]) -> None:
        """Register a callback for when dice are rolled."""
        self._on_roll_callbacks.append(callback)

    def on_point_established(self, callback: Callable[[int], None]) -> None:
        """Register a callback for when a point is established."""
        self._on_point_established_callbacks.append(callback)

    def on_point_won(self, callback: Callable[[], None]) -> None:
        """Register a callback for when the point is made."""
        self._on_point_won_callbacks.append(callback)

    def on_seven_out(self, callback: Callable[[], None]) -> None:
        """Register a callback for when shooter sevens out."""
        self._on_seven_out_callbacks.append(callback)

    @property
    def is_come_out(self) -> bool:
        """Returns True if in come-out phase."""
        return self.phase == GamePhase.COME_OUT

    @property
    def is_point_phase(self) -> bool:
        """Returns True if a point has been established."""
        return self.phase == GamePhase.POINT

    def get_last_roll(self) -> Optional[DiceRoll]:
        """Get the most recent roll."""
        return self.roll_history[-1] if self.roll_history else None
