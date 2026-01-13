"""
Pass Line with Odds strategy - conservative, low house edge.
"""
from typing import Optional
from ..strategy import Strategy
from ..game import GamePhase, TableRules
from ..bets import PassLineBet, OddsBet


class PassLineWithOddsStrategy(Strategy):
    """
    Pass Line with maximum odds betting strategy.

    Places pass line bet on come-out roll, then adds maximum odds
    once point is established. This is one of the lowest house edge
    strategies in craps (~0.4% with 3x odds).
    """

    def __init__(self, starting_bankroll: float, rules: TableRules,
                 table_minimum: float = 5, pass_units: int = 1, odds_multiple: int = 3):
        """
        Initialize Pass Line + Odds strategy.

        Args:
            starting_bankroll: Initial bankroll
            rules: Table rules
            table_minimum: Table minimum bet
            pass_units: Units of table minimum for pass line (default 1x)
            odds_multiple: Odds multiplier (1x, 2x, 3x, etc.)
        """
        super().__init__(starting_bankroll, rules)
        self.table_minimum = table_minimum
        self.pass_units = pass_units
        self.pass_amount = table_minimum * pass_units
        self.odds_multiple = odds_multiple

    @property
    def name(self) -> str:
        return f"Pass + {self.odds_multiple}x Odds"

    @property
    def description(self) -> str:
        return f"Pass Line {self.pass_units}u with {self.odds_multiple}x odds (low house edge)"

    def on_come_out_roll(self, phase: GamePhase, point: Optional[int]) -> None:
        """Place Pass Line bet if we don't have one."""
        # Only place pass line if we don't already have one
        if not self.bet_interface.has_active_bet(PassLineBet):
            if self.bet_interface.current_bankroll >= self.pass_amount:
                bet = PassLineBet(self.pass_amount, self.rules)
                self.bet_interface.place_bet(bet)

    def on_point_roll(self, phase: GamePhase, point: int) -> None:
        """Place odds bet if we have pass line and no odds yet."""
        # Only place odds if we have a pass line bet but no odds yet
        if self.bet_interface.has_active_bet(PassLineBet):
            if not self.bet_interface.has_active_bet(OddsBet):
                odds_amount = self.pass_amount * self.odds_multiple
                if self.bet_interface.current_bankroll >= odds_amount:
                    bet = OddsBet(odds_amount, self.rules, point)
                    self.bet_interface.place_bet(bet)
