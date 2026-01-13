"""
Iron Cross strategy - covers all numbers except 7.
"""
from typing import Optional
from ..strategy import Strategy
from ..game import GamePhase, TableRules
from ..bets import FieldBet, PlaceBet


class IronCrossStrategy(Strategy):
    """
    Iron Cross betting strategy.

    Places Field bet + Place bets on 5, 6, and 8. This covers all
    numbers except 7, providing high action and frequent wins,
    but with moderate house edge.
    """

    def __init__(self, starting_bankroll: float, rules: TableRules,
                 table_minimum: float = 5, units_per_bet: int = 1):
        """
        Initialize Iron Cross strategy.

        Args:
            starting_bankroll: Initial bankroll
            rules: Table rules
            table_minimum: Table minimum bet
            units_per_bet: Units of table minimum for each bet (field + each place)
        """
        super().__init__(starting_bankroll, rules)
        self.table_minimum = table_minimum
        self.units_per_bet = units_per_bet
        self.unit = table_minimum * units_per_bet

    @property
    def name(self) -> str:
        return "Iron Cross"

    @property
    def description(self) -> str:
        return f"Field + Place 5,6,8 ({self.units_per_bet}u each) - covers all except 7"

    def on_come_out_roll(self, phase: GamePhase, point: Optional[int]) -> None:
        """Don't bet during come-out roll."""
        pass

    def on_point_roll(self, phase: GamePhase, point: int) -> None:
        """Place iron cross bets once point is established."""
        total_needed = self.unit * 4  # field + 3 place bets

        if self.bet_interface.current_bankroll >= total_needed:
            # Place field bet
            if not self.bet_interface.has_active_bet(FieldBet):
                self.bet_interface.place_bet(FieldBet(self.unit, self.rules))

            # Place 5, 6, 8
            for num in [5, 6, 8]:
                # Check if we already have a place bet on this number
                has_bet = any(
                    isinstance(b, PlaceBet) and b.number == num
                    for b in self.bet_interface.get_active_bets_of_type(PlaceBet)
                )
                if not has_bet:
                    bet = PlaceBet(self.unit, self.rules, num)
                    bet.is_working = True  # Always working
                    self.bet_interface.place_bet(bet)
