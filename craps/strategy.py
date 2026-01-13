"""
Strategy base class and betting interface for craps strategies.

Strategies define betting behavior through callback methods that are
triggered at key points in the game flow.
"""
from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .bets import Bet, BetManager
    from .bankroll import BankrollTracker
    from .game import GamePhase, DiceRoll, TableRules


class StrategyBetInterface:
    """
    Limited interface for strategies to place bets safely.

    Prevents direct access to BetManager and BankrollTracker,
    ensuring strategies can't manipulate state improperly.
    """

    def __init__(self, bet_manager: 'BetManager', bankroll_tracker: 'BankrollTracker'):
        """
        Initialize the betting interface.

        Args:
            bet_manager: The bet manager for this strategy's game
            bankroll_tracker: The bankroll tracker for this strategy
        """
        self.bet_manager = bet_manager
        self.tracker = bankroll_tracker

    @property
    def current_bankroll(self) -> float:
        """Get current cash in hand (not including bets on table)."""
        return self.tracker.current_bankroll

    @property
    def current_equity(self) -> float:
        """Get total equity (bankroll + bets on table)."""
        return self.tracker.current_equity

    def place_bet(self, bet: 'Bet') -> bool:
        """
        Place a bet if bankroll is sufficient.

        Args:
            bet: The bet object to place

        Returns:
            bool: True if bet was placed successfully, False otherwise
        """
        # Check if enough bankroll
        if bet.amount > self.current_bankroll:
            return False

        # Try to place bet (will check table min/max)
        if self.bet_manager.place_bet(bet):
            # Update tracker
            self.tracker.current_bets += bet.amount
            self.tracker.current_bankroll -= bet.amount
            return True

        return False

    def has_active_bet(self, bet_type: type) -> bool:
        """
        Check if a bet of the given type is already active.

        Args:
            bet_type: The bet class to check for (e.g., PassLineBet)

        Returns:
            bool: True if at least one bet of this type is active
        """
        return any(isinstance(b, bet_type) for b in self.bet_manager.active_bets)

    def get_active_bets_of_type(self, bet_type: type) -> list['Bet']:
        """
        Get all active bets of a specific type.

        Args:
            bet_type: The bet class to filter by

        Returns:
            list[Bet]: All active bets matching the type
        """
        return [b for b in self.bet_manager.active_bets if isinstance(b, bet_type)]


class Strategy(ABC):
    """
    Abstract base class for all betting strategies.

    Strategies implement callback methods that are triggered at key
    points in the game flow (come-out roll, point roll, etc.).

    Subclasses should implement:
    - name: Display name of the strategy
    - description: Brief description of betting approach
    - on_come_out_roll(): Place bets before come-out roll
    - on_point_roll(): Place/adjust bets before point phase roll
    """

    def __init__(self, starting_bankroll: float, rules: 'TableRules'):
        """
        Initialize the strategy.

        Args:
            starting_bankroll: Initial bankroll amount
            rules: Table rules for this game
        """
        self.starting_bankroll = starting_bankroll
        self.rules = rules
        self.bet_interface: Optional[StrategyBetInterface] = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Display name of the strategy."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Brief description of the betting approach."""
        pass

    def _set_bet_interface(self, interface: StrategyBetInterface) -> None:
        """
        Set the betting interface (called by StrategyRunner).

        Args:
            interface: The betting interface for this strategy
        """
        self.bet_interface = interface

    @abstractmethod
    def on_come_out_roll(self, phase: 'GamePhase', point: Optional[int]) -> None:
        """
        Called before a come-out roll. Place bets here.

        Args:
            phase: Current game phase
            point: Current point (should be None during come-out)
        """
        pass

    @abstractmethod
    def on_point_roll(self, phase: 'GamePhase', point: int) -> None:
        """
        Called before a point phase roll. Place/adjust bets here.

        Args:
            phase: Current game phase
            point: Current point number (4, 5, 6, 8, 9, or 10)
        """
        pass

    def on_roll_complete(self, roll: 'DiceRoll', phase: 'GamePhase', point: Optional[int]) -> None:
        """
        Called after a roll is resolved. Optional hook for cleanup/tracking.

        Args:
            roll: The dice roll that just occurred
            phase: Current game phase after the roll
            point: Current point after the roll
        """
        pass

    def on_seven_out(self) -> None:
        """
        Called when seven-out occurs. Optional hook.
        """
        pass

    def on_point_made(self, point: int) -> None:
        """
        Called when point is made. Optional hook.

        Args:
            point: The point number that was made
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"
