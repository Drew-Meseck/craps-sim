"""
Craps bet types and pay tables.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from fractions import Fraction

from .game import DiceRoll, GamePhase, TableRules


class BetStatus(Enum):
    """Status of a bet."""
    ACTIVE = "active"     # Bet is in play
    WON = "won"           # Bet has won
    LOST = "lost"         # Bet has lost
    PUSH = "push"         # Bet is returned (tie)
    OFF = "off"           # Bet is temporarily off (not working)


@dataclass
class BetResult:
    """Result of resolving a bet."""
    status: BetStatus
    payout: float  # Net payout (0 for loss, bet amount for push, positive for win)
    message: str


class Bet(ABC):
    """Abstract base class for all bet types."""

    def __init__(self, amount: float, rules: TableRules):
        self.amount = amount
        self.rules = rules
        self.status = BetStatus.ACTIVE
        self.is_working = True  # Some bets can be turned off

    @property
    @abstractmethod
    def name(self) -> str:
        """Display name of the bet."""
        pass

    @abstractmethod
    def resolve(self, roll: DiceRoll, phase: GamePhase, point: Optional[int]) -> Optional[BetResult]:
        """
        Resolve the bet based on a roll.
        Returns BetResult if bet is resolved, None if bet remains active.
        """
        pass

    @property
    @abstractmethod
    def house_edge(self) -> float:
        """Return the house edge as a percentage."""
        pass


# =============================================================================
# Line Bets (Pass, Don't Pass, Come, Don't Come)
# =============================================================================

class PassLineBet(Bet):
    """
    Pass Line bet - the most common bet in craps.
    Win on 7/11 come-out, lose on 2/3/12 come-out.
    After point established, win on point, lose on 7.
    Pays even money (1:1).
    """

    def __init__(self, amount: float, rules: TableRules):
        super().__init__(amount, rules)
        self._point_established = False
        self._point_value: Optional[int] = None

    @property
    def name(self) -> str:
        return "Pass Line"

    @property
    def house_edge(self) -> float:
        return 1.41

    def resolve(self, roll: DiceRoll, phase: GamePhase, point: Optional[int]) -> Optional[BetResult]:
        total = roll.total

        if not self._point_established:
            # Come-out roll
            if total in (7, 11):
                return BetResult(BetStatus.WON, self.amount, f"Natural {total}! Pass line wins!")
            elif total in (2, 3, 12):
                return BetResult(BetStatus.LOST, 0, f"Craps {total}! Pass line loses.")
            else:
                # Point established
                self._point_established = True
                self._point_value = total
                return None
        else:
            # Point phase
            if total == self._point_value:
                return BetResult(BetStatus.WON, self.amount, f"Point {total} made! Pass line wins!")
            elif total == 7:
                return BetResult(BetStatus.LOST, 0, "Seven out! Pass line loses.")
            return None


class DontPassBet(Bet):
    """
    Don't Pass bet - betting against the shooter.
    Win on 2/3 come-out, push on 12, lose on 7/11 come-out.
    After point established, win on 7, lose on point.
    Pays even money (1:1).
    """

    def __init__(self, amount: float, rules: TableRules):
        super().__init__(amount, rules)
        self._point_established = False
        self._point_value: Optional[int] = None

    @property
    def name(self) -> str:
        return "Don't Pass"

    @property
    def house_edge(self) -> float:
        return 1.36

    def resolve(self, roll: DiceRoll, phase: GamePhase, point: Optional[int]) -> Optional[BetResult]:
        total = roll.total

        if not self._point_established:
            # Come-out roll
            if total in (2, 3):
                return BetResult(BetStatus.WON, self.amount, f"Craps {total}! Don't pass wins!")
            elif total == 12:
                return BetResult(BetStatus.PUSH, self.amount, "12 - Don't pass pushes (bar 12).")
            elif total in (7, 11):
                return BetResult(BetStatus.LOST, 0, f"Natural {total}! Don't pass loses.")
            else:
                self._point_established = True
                self._point_value = total
                return None
        else:
            # Point phase
            if total == 7:
                return BetResult(BetStatus.WON, self.amount, "Seven! Don't pass wins!")
            elif total == self._point_value:
                return BetResult(BetStatus.LOST, 0, f"Point {total} made! Don't pass loses.")
            return None


class ComeBet(Bet):
    """
    Come bet - like pass line, but placed after come-out roll.
    Uses the next roll as its own come-out roll.
    """

    def __init__(self, amount: float, rules: TableRules):
        super().__init__(amount, rules)
        self._come_point: Optional[int] = None

    @property
    def name(self) -> str:
        if self._come_point:
            return f"Come ({self._come_point})"
        return "Come"

    @property
    def house_edge(self) -> float:
        return 1.41

    def resolve(self, roll: DiceRoll, phase: GamePhase, point: Optional[int]) -> Optional[BetResult]:
        total = roll.total

        if self._come_point is None:
            # First roll for this come bet
            if total in (7, 11):
                return BetResult(BetStatus.WON, self.amount, f"Natural {total}! Come bet wins!")
            elif total in (2, 3, 12):
                return BetResult(BetStatus.LOST, 0, f"Craps {total}! Come bet loses.")
            else:
                self._come_point = total
                return None
        else:
            # Come point established
            if total == self._come_point:
                return BetResult(BetStatus.WON, self.amount, f"Come point {total} made!")
            elif total == 7:
                return BetResult(BetStatus.LOST, 0, "Seven out! Come bet loses.")
            return None


class DontComeBet(Bet):
    """
    Don't Come bet - like don't pass, but placed after come-out roll.
    """

    def __init__(self, amount: float, rules: TableRules):
        super().__init__(amount, rules)
        self._come_point: Optional[int] = None

    @property
    def name(self) -> str:
        if self._come_point:
            return f"Don't Come ({self._come_point})"
        return "Don't Come"

    @property
    def house_edge(self) -> float:
        return 1.36

    def resolve(self, roll: DiceRoll, phase: GamePhase, point: Optional[int]) -> Optional[BetResult]:
        total = roll.total

        if self._come_point is None:
            if total in (2, 3):
                return BetResult(BetStatus.WON, self.amount, f"Craps {total}! Don't come wins!")
            elif total == 12:
                return BetResult(BetStatus.PUSH, self.amount, "12 - Don't come pushes.")
            elif total in (7, 11):
                return BetResult(BetStatus.LOST, 0, f"Natural {total}! Don't come loses.")
            else:
                self._come_point = total
                return None
        else:
            if total == 7:
                return BetResult(BetStatus.WON, self.amount, "Seven! Don't come wins!")
            elif total == self._come_point:
                return BetResult(BetStatus.LOST, 0, f"Point {total} made! Don't come loses.")
            return None


# =============================================================================
# Odds Bets (True odds, no house edge)
# =============================================================================

class OddsBet(Bet):
    """
    Odds bet behind pass/come - pays true odds with no house edge.
    Must be attached to a pass line or come bet with an established point.
    """

    # True odds payouts
    ODDS_PAYOUTS = {
        4: Fraction(2, 1),   # 2:1
        5: Fraction(3, 2),   # 3:2
        6: Fraction(6, 5),   # 6:5
        8: Fraction(6, 5),   # 6:5
        9: Fraction(3, 2),   # 3:2
        10: Fraction(2, 1),  # 2:1
    }

    def __init__(self, amount: float, rules: TableRules, point: int):
        super().__init__(amount, rules)
        self.point = point

    @property
    def name(self) -> str:
        return f"Odds ({self.point})"

    @property
    def house_edge(self) -> float:
        return 0.0  # True odds!

    def resolve(self, roll: DiceRoll, phase: GamePhase, point: Optional[int]) -> Optional[BetResult]:
        total = roll.total

        if total == self.point:
            payout_ratio = self.ODDS_PAYOUTS[self.point]
            payout = float(self.amount * payout_ratio)
            return BetResult(BetStatus.WON, payout, f"Point {total}! Odds pays {payout_ratio}!")
        elif total == 7:
            return BetResult(BetStatus.LOST, 0, "Seven out! Odds bet loses.")
        return None


class LayOddsBet(Bet):
    """
    Lay odds behind don't pass/don't come - pays true odds (reversed).
    """

    LAY_PAYOUTS = {
        4: Fraction(1, 2),   # 1:2
        5: Fraction(2, 3),   # 2:3
        6: Fraction(5, 6),   # 5:6
        8: Fraction(5, 6),   # 5:6
        9: Fraction(2, 3),   # 2:3
        10: Fraction(1, 2),  # 1:2
    }

    def __init__(self, amount: float, rules: TableRules, point: int):
        super().__init__(amount, rules)
        self.point = point

    @property
    def name(self) -> str:
        return f"Lay Odds ({self.point})"

    @property
    def house_edge(self) -> float:
        return 0.0

    def resolve(self, roll: DiceRoll, phase: GamePhase, point: Optional[int]) -> Optional[BetResult]:
        total = roll.total

        if total == 7:
            payout_ratio = self.LAY_PAYOUTS[self.point]
            payout = float(self.amount * payout_ratio)
            return BetResult(BetStatus.WON, payout, f"Seven! Lay odds pays!")
        elif total == self.point:
            return BetResult(BetStatus.LOST, 0, f"Point {total} made! Lay odds loses.")
        return None


# =============================================================================
# Place Bets
# =============================================================================

class PlaceBet(Bet):
    """
    Place bet on a specific number (4, 5, 6, 8, 9, 10).
    Wins if number is rolled before 7.
    """

    PLACE_PAYOUTS = {
        4: Fraction(9, 5),   # 9:5
        5: Fraction(7, 5),   # 7:5
        6: Fraction(7, 6),   # 7:6
        8: Fraction(7, 6),   # 7:6
        9: Fraction(7, 5),   # 7:5
        10: Fraction(9, 5),  # 9:5
    }

    HOUSE_EDGES = {
        4: 6.67,
        5: 4.00,
        6: 1.52,
        8: 1.52,
        9: 4.00,
        10: 6.67,
    }

    def __init__(self, amount: float, rules: TableRules, number: int):
        if number not in (4, 5, 6, 8, 9, 10):
            raise ValueError(f"Invalid place bet number: {number}")
        super().__init__(amount, rules)
        self.number = number

    @property
    def name(self) -> str:
        return f"Place {self.number}"

    @property
    def house_edge(self) -> float:
        return self.HOUSE_EDGES[self.number]

    def resolve(self, roll: DiceRoll, phase: GamePhase, point: Optional[int]) -> Optional[BetResult]:
        if not self.is_working and phase == GamePhase.COME_OUT:
            return None

        total = roll.total

        if total == self.number:
            payout_ratio = self.PLACE_PAYOUTS[self.number]
            payout = float(self.amount * payout_ratio)
            return BetResult(BetStatus.WON, payout, f"{self.number} hits! Place bet wins!")
        elif total == 7:
            return BetResult(BetStatus.LOST, 0, "Seven out! Place bet loses.")
        return None


# =============================================================================
# Field Bet
# =============================================================================

class FieldBet(Bet):
    """
    Field bet - one-roll bet on 2, 3, 4, 9, 10, 11, 12.
    2 and 12 often pay double or triple.
    """

    FIELD_NUMBERS = {2, 3, 4, 9, 10, 11, 12}

    def __init__(self, amount: float, rules: TableRules):
        super().__init__(amount, rules)

    @property
    def name(self) -> str:
        return "Field"

    @property
    def house_edge(self) -> float:
        # Depends on whether 2 and/or 12 pay triple
        if self.rules.field_2_payout == 2 and self.rules.field_12_payout == 2:
            return 5.56  # Double 2, double 12
        elif self.rules.field_2_payout == 2 and self.rules.field_12_payout == 3:
            return 2.78  # Double 2, triple 12
        elif self.rules.field_2_payout == 3 and self.rules.field_12_payout == 3:
            return 0.0   # Triple both (rare)
        return 5.56

    def resolve(self, roll: DiceRoll, phase: GamePhase, point: Optional[int]) -> Optional[BetResult]:
        total = roll.total

        if total in self.FIELD_NUMBERS:
            if total == 2:
                payout = self.amount * self.rules.field_2_payout
                return BetResult(BetStatus.WON, payout, f"Field {total}! Pays {self.rules.field_2_payout}:1!")
            elif total == 12:
                payout = self.amount * self.rules.field_12_payout
                return BetResult(BetStatus.WON, payout, f"Field {total}! Pays {self.rules.field_12_payout}:1!")
            else:
                return BetResult(BetStatus.WON, self.amount, f"Field {total} wins!")
        else:
            return BetResult(BetStatus.LOST, 0, f"{total} - Field bet loses.")


# =============================================================================
# Proposition Bets (Single roll bets)
# =============================================================================

class AnyCrapsBet(Bet):
    """Any Craps - wins on 2, 3, or 12. Pays 7:1."""

    @property
    def name(self) -> str:
        return "Any Craps"

    @property
    def house_edge(self) -> float:
        return 11.11

    def resolve(self, roll: DiceRoll, phase: GamePhase, point: Optional[int]) -> Optional[BetResult]:
        if roll.total in (2, 3, 12):
            return BetResult(BetStatus.WON, self.amount * 7, f"Craps {roll.total}! Pays 7:1!")
        return BetResult(BetStatus.LOST, 0, f"{roll.total} - Any craps loses.")


class AnySevenBet(Bet):
    """Any Seven (Big Red) - wins on 7. Pays 4:1."""

    @property
    def name(self) -> str:
        return "Any Seven"

    @property
    def house_edge(self) -> float:
        return 16.67

    def resolve(self, roll: DiceRoll, phase: GamePhase, point: Optional[int]) -> Optional[BetResult]:
        if roll.total == 7:
            return BetResult(BetStatus.WON, self.amount * 4, "Seven! Pays 4:1!")
        return BetResult(BetStatus.LOST, 0, f"{roll.total} - Any seven loses.")


class HornBet(Bet):
    """
    Horn bet - covers 2, 3, 11, 12 with equal amounts.
    Pays based on which number hits.
    """

    @property
    def name(self) -> str:
        return "Horn"

    @property
    def house_edge(self) -> float:
        return 12.5

    def resolve(self, roll: DiceRoll, phase: GamePhase, point: Optional[int]) -> Optional[BetResult]:
        total = roll.total
        unit = self.amount / 4  # Split among 4 numbers

        if total == 2:
            payout = unit * 30 - (unit * 3)  # Win 30:1 on 2, lose other 3 units
            return BetResult(BetStatus.WON, payout, "2! Horn pays 30:1 on 2!")
        elif total == 12:
            payout = unit * 30 - (unit * 3)
            return BetResult(BetStatus.WON, payout, "12! Horn pays 30:1 on 12!")
        elif total == 3:
            payout = unit * 15 - (unit * 3)  # Win 15:1 on 3
            return BetResult(BetStatus.WON, payout, "3! Horn pays 15:1 on 3!")
        elif total == 11:
            payout = unit * 15 - (unit * 3)
            return BetResult(BetStatus.WON, payout, "Yo! Horn pays 15:1 on 11!")
        else:
            return BetResult(BetStatus.LOST, 0, f"{total} - Horn bet loses.")


class HardwayBet(Bet):
    """
    Hardway bet - bet on doubles (hard 4, 6, 8, or 10).
    Wins if number is rolled as doubles before 7 or "easy" version.
    """

    HARDWAY_PAYOUTS = {
        4: 7,   # Hard 4 pays 7:1
        6: 9,   # Hard 6 pays 9:1
        8: 9,   # Hard 8 pays 9:1
        10: 7,  # Hard 10 pays 7:1
    }

    HARDWAY_EDGES = {
        4: 11.11,
        6: 9.09,
        8: 9.09,
        10: 11.11,
    }

    def __init__(self, amount: float, rules: TableRules, number: int):
        if number not in (4, 6, 8, 10):
            raise ValueError(f"Invalid hardway number: {number}")
        super().__init__(amount, rules)
        self.number = number

    @property
    def name(self) -> str:
        return f"Hard {self.number}"

    @property
    def house_edge(self) -> float:
        return self.HARDWAY_EDGES[self.number]

    def resolve(self, roll: DiceRoll, phase: GamePhase, point: Optional[int]) -> Optional[BetResult]:
        total = roll.total

        if total == self.number:
            if roll.is_hard:
                payout = self.amount * self.HARDWAY_PAYOUTS[self.number]
                return BetResult(BetStatus.WON, payout, f"Hard {self.number}! Pays {self.HARDWAY_PAYOUTS[self.number]}:1!")
            else:
                return BetResult(BetStatus.LOST, 0, f"Easy {self.number}! Hardway loses.")
        elif total == 7:
            return BetResult(BetStatus.LOST, 0, "Seven! Hardway loses.")
        return None


# =============================================================================
# Bet Manager
# =============================================================================

class BetManager:
    """Manages all active bets for a player."""

    def __init__(self, rules: TableRules):
        self.rules = rules
        self.active_bets: list[Bet] = []
        self.resolved_bets: list[tuple[Bet, BetResult]] = []

    def place_bet(self, bet: Bet) -> bool:
        """Place a new bet. Returns True if successful."""
        if bet.amount < self.rules.minimum_bet:
            return False
        if bet.amount > self.rules.maximum_bet:
            return False
        self.active_bets.append(bet)
        return True

    def resolve_all(self, roll: DiceRoll, phase: GamePhase, point: Optional[int]) -> list[tuple[Bet, BetResult]]:
        """Resolve all active bets against a roll."""
        results = []
        remaining_bets = []

        for bet in self.active_bets:
            result = bet.resolve(roll, phase, point)
            if result is not None:
                bet.status = result.status
                results.append((bet, result))
                self.resolved_bets.append((bet, result))
            else:
                remaining_bets.append(bet)

        self.active_bets = remaining_bets
        return results

    def get_total_at_risk(self) -> float:
        """Get total amount of money in active bets."""
        return sum(bet.amount for bet in self.active_bets)

    def clear_bets(self) -> None:
        """Clear all bets."""
        self.active_bets.clear()
        self.resolved_bets.clear()
