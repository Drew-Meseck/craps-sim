"""
Place 6 and 8 strategy - simplest low house edge approach.
"""
from typing import Optional
from ..strategy import Strategy
from ..game import GamePhase, TableRules
from ..bets import PlaceBet


class Place68Strategy(Strategy):
    """
    Place 6 and 8 only strategy.

    Places bets only on 6 and 8, which have the lowest house edge
    among place bets (1.52%). Simple and effective strategy with
    moderate risk.
    """

    def __init__(self, starting_bankroll: float, rules: TableRules,
                 table_minimum: float = 5, place_units: int = 2):
        """
        Initialize Place 6 & 8 strategy.

        Args:
            starting_bankroll: Initial bankroll
            rules: Table rules
            table_minimum: Table minimum bet
            place_units: Units of table minimum for each place bet (default 2x for proper payouts)
        """
        super().__init__(starting_bankroll, rules)
        self.table_minimum = table_minimum
        self.place_units = place_units
        self.place_amount = table_minimum * place_units

    @property
    def name(self) -> str:
        return "Place 6 & 8"

    @property
    def description(self) -> str:
        return f"Place {self.place_units}u on 6 and 8 only (lowest house edge place bets)"

    def on_come_out_roll(self, phase: GamePhase, point: Optional[int]) -> None:
        """Don't bet during come-out roll."""
        pass

    def on_point_roll(self, phase: GamePhase, point: int) -> None:
        """Place 6 and 8 during point phase."""
        for num in [6, 8]:
            # Check if we already have a place bet on this number
            has_bet = any(
                isinstance(b, PlaceBet) and b.number == num
                for b in self.bet_interface.get_active_bets_of_type(PlaceBet)
            )
            if not has_bet:
                if self.bet_interface.current_bankroll >= self.place_amount:
                    bet = PlaceBet(self.place_amount, self.rules, num)
                    bet.is_working = True  # Always working
                    self.bet_interface.place_bet(bet)
