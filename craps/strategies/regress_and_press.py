"""
Regress and Press strategy - start big, regress after first hit, then press.
"""
from typing import Optional
from ..strategy import Strategy
from ..game import GamePhase, DiceRoll, TableRules
from ..bets import PlaceBet


class RegressAndPressStrategy(Strategy):
    """
    Regress and Press betting strategy.

    Starts with high place bets on 5, 6, 8, 9. After first hit, regresses
    to base units. Then presses each number by one unit each time it hits.
    First hit on 5 after regression places the 4, first hit on 9 places the 10.
    """

    def __init__(self, starting_bankroll: float, rules: TableRules,
                 table_minimum: float = 5,
                 initial_inside: tuple[int, int] = (100, 120),
                 base_units: tuple[int, int] = (25, 30)):
        """
        Initialize Regress and Press strategy.

        Args:
            starting_bankroll: Initial bankroll
            rules: Table rules
            table_minimum: Table minimum (not directly used, for compatibility)
            initial_inside: Initial bet amounts for (5/9, 6/8)
            base_units: Base unit amounts for (5/9, 6/8) after regression
        """
        super().__init__(starting_bankroll, rules)
        self.table_minimum = table_minimum

        # Initial high bets
        self.initial_5_9 = initial_inside[0]  # $100 default
        self.initial_6_8 = initial_inside[1]  # $120 default

        # Base units for pressing
        self.base_5_9 = base_units[0]  # $25 default
        self.base_6_8 = base_units[1]  # $30 default
        self.base_4_10 = base_units[0]  # Same as 5/9 for 4/10

        # State tracking
        self._reset_state()

    def _reset_state(self) -> None:
        """Reset all state for a new shooter."""
        self.phase = "initial"  # "initial" or "regressed"
        self.bets_placed_this_point = False

        # Current bet amounts (0 means not placed yet)
        self.current_amounts = {
            4: 0,
            5: 0,
            6: 0,
            8: 0,
            9: 0,
            10: 0,
        }

        # Track if 4/10 have been placed (first 5/9 hit after regression)
        self.four_placed = False
        self.ten_placed = False

    @property
    def name(self) -> str:
        return "Regress and Press"

    @property
    def description(self) -> str:
        return (f"Place ${self.initial_5_9} on 5/9, ${self.initial_6_8} on 6/8. "
                f"After first hit, regress to ${self.base_5_9}/${self.base_6_8}. "
                f"Press one unit on each hit. First 5 hit places 4, first 9 hit places 10.")

    def on_come_out_roll(self, phase: GamePhase, point: Optional[int]) -> None:
        """Don't bet during come-out roll."""
        pass

    def on_point_roll(self, phase: GamePhase, point: int) -> None:
        """Place/adjust bets once point is established."""
        if self.phase == "initial" and not self.bets_placed_this_point:
            # Place initial high bets on 5, 6, 8, 9
            self._place_initial_bets()
            self.bets_placed_this_point = True
        elif self.phase == "regressed":
            # Ensure all our current bets are on the table
            self._ensure_bets_placed()

    def _place_initial_bets(self) -> None:
        """Place the initial high bets."""
        # Calculate total needed
        total_needed = (self.initial_5_9 * 2) + (self.initial_6_8 * 2)

        if self.bet_interface.current_bankroll < total_needed:
            return

        # Place bets on 5, 6, 8, 9
        for num in [5, 9]:
            if not self._has_place_bet_on(num):
                bet = PlaceBet(self.initial_5_9, self.rules, num)
                bet.is_working = True
                if self.bet_interface.place_bet(bet):
                    self.current_amounts[num] = self.initial_5_9

        for num in [6, 8]:
            if not self._has_place_bet_on(num):
                bet = PlaceBet(self.initial_6_8, self.rules, num)
                bet.is_working = True
                if self.bet_interface.place_bet(bet):
                    self.current_amounts[num] = self.initial_6_8

    def _ensure_bets_placed(self) -> None:
        """Ensure all bets at current amounts are on the table."""
        for num in [4, 5, 6, 8, 9, 10]:
            if self.current_amounts[num] > 0 and not self._has_place_bet_on(num):
                if self.bet_interface.current_bankroll >= self.current_amounts[num]:
                    bet = PlaceBet(self.current_amounts[num], self.rules, num)
                    bet.is_working = True
                    self.bet_interface.place_bet(bet)

    def _has_place_bet_on(self, number: int) -> bool:
        """Check if we have a place bet on a specific number."""
        return any(
            isinstance(b, PlaceBet) and b.number == number
            for b in self.bet_interface.get_active_bets_of_type(PlaceBet)
        )

    def on_roll_complete(self, roll: DiceRoll, phase: GamePhase, point: Optional[int]) -> None:
        """Handle bet wins and adjust state."""
        total = roll.total

        # Check if a place number hit
        if total in [4, 5, 6, 8, 9, 10] and phase == GamePhase.POINT:
            self._handle_place_hit(total)

    def _handle_place_hit(self, number: int) -> None:
        """Handle when a place number is hit."""
        # Only process if we had a bet on this number
        if self.current_amounts[number] == 0:
            return

        if self.phase == "initial":
            # First hit - regress all bets
            self._regress_bets()
        else:
            # Already regressed - press the number that hit
            self._press_number(number)

    def _regress_bets(self) -> None:
        """Regress all bets to base units after first hit."""
        self.phase = "regressed"

        # Set all inside numbers to base amounts
        self.current_amounts[5] = self.base_5_9
        self.current_amounts[6] = self.base_6_8
        self.current_amounts[8] = self.base_6_8
        self.current_amounts[9] = self.base_5_9

        # 4 and 10 not placed yet
        self.current_amounts[4] = 0
        self.current_amounts[10] = 0

    def _press_number(self, number: int) -> None:
        """Press a number by one unit after it hits."""
        if number == 5:
            if not self.four_placed:
                # First 5 hit after regression - place the 4 instead of pressing 5
                self.current_amounts[4] = self.base_4_10
                self.four_placed = True
            else:
                # Subsequent 5 hits - press the 5
                self.current_amounts[5] += self.base_5_9

        elif number == 9:
            if not self.ten_placed:
                # First 9 hit after regression - place the 10 instead of pressing 9
                self.current_amounts[10] = self.base_4_10
                self.ten_placed = True
            else:
                # Subsequent 9 hits - press the 9
                self.current_amounts[9] += self.base_5_9

        elif number == 4:
            # Press the 4
            self.current_amounts[4] += self.base_4_10

        elif number == 10:
            # Press the 10
            self.current_amounts[10] += self.base_4_10

        elif number == 6:
            # Press the 6
            self.current_amounts[6] += self.base_6_8

        elif number == 8:
            # Press the 8
            self.current_amounts[8] += self.base_6_8

    def on_seven_out(self) -> None:
        """Reset state when seven-out occurs."""
        self._reset_state()

    def on_point_made(self, point: int) -> None:
        """Reset for new point cycle but keep progression state."""
        self.bets_placed_this_point = False
