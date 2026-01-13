"""
Don't Pass with Lay Odds strategy - betting against the shooter.
"""
from typing import Optional
from ..strategy import Strategy
from ..game import GamePhase, TableRules
from ..bets import DontPassBet, LayOddsBet


class DontPassStrategy(Strategy):
    """
    Don't Pass with Lay Odds strategy.

    Bets against the shooter with Don't Pass and Lay Odds.
    Has slightly lower house edge than Pass Line (1.36% vs 1.41%).
    """

    def __init__(self, starting_bankroll: float, rules: TableRules,
                 table_minimum: float = 5, dont_pass_units: int = 1, lay_multiple: int = 2):
        """
        Initialize Don't Pass + Lay Odds strategy.

        Args:
            starting_bankroll: Initial bankroll
            rules: Table rules
            table_minimum: Table minimum bet
            dont_pass_units: Units of table minimum for don't pass (default 1x)
            lay_multiple: Lay odds multiplier
        """
        super().__init__(starting_bankroll, rules)
        self.table_minimum = table_minimum
        self.dont_pass_units = dont_pass_units
        self.dont_pass_amount = table_minimum * dont_pass_units
        self.lay_multiple = lay_multiple

    @property
    def name(self) -> str:
        return f"Don't Pass + {self.lay_multiple}x Lay"

    @property
    def description(self) -> str:
        return f"Don't Pass {self.dont_pass_units}u with {self.lay_multiple}x lay odds (against shooter)"

    def on_come_out_roll(self, phase: GamePhase, point: Optional[int]) -> None:
        """Place Don't Pass bet if we don't have one."""
        if not self.bet_interface.has_active_bet(DontPassBet):
            if self.bet_interface.current_bankroll >= self.dont_pass_amount:
                bet = DontPassBet(self.dont_pass_amount, self.rules)
                self.bet_interface.place_bet(bet)

    def on_point_roll(self, phase: GamePhase, point: int) -> None:
        """Place lay odds if we have don't pass and no lay odds yet."""
        if self.bet_interface.has_active_bet(DontPassBet):
            if not self.bet_interface.has_active_bet(LayOddsBet):
                lay_amount = self.dont_pass_amount * self.lay_multiple
                if self.bet_interface.current_bankroll >= lay_amount:
                    bet = LayOddsBet(lay_amount, self.rules, point)
                    self.bet_interface.place_bet(bet)
