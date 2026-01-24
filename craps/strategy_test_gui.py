"""
Strategy testing GUI window.

Provides interface for configuring and running strategy comparisons.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

from .strategy_runner import StrategyRunner, SimulationConfig
from .game import TableRules
from .strategies import (
    PassLineWithOddsStrategy,
    IronCrossStrategy,
    DontPassStrategy,
    Place68Strategy,
    RegressAndPressStrategy
)


class StrategyTestWindow:
    """
    Window for configuring and running strategy tests.

    Allows user to:
    - Select strategies to test
    - Configure simulation parameters
    - View results table
    - See comparison graph with overlaid equity curves
    """

    def __init__(self, parent_root: tk.Tk):
        """
        Initialize the strategy test window.

        Args:
            parent_root: Parent Tkinter root window
        """
        self.parent = parent_root
        self.window = tk.Toplevel(parent_root)
        self.window.title("Strategy Tester")
        self.window.geometry("1100x900")
        self.window.minsize(950, 700)  # Set minimum size
        self.window.configure(bg='#1a0f2e')

        # Available strategies
        self.available_strategies = [
            ("Pass Line + 3x Odds", PassLineWithOddsStrategy),
            ("Iron Cross", IronCrossStrategy),
            ("Don't Pass + Lay", DontPassStrategy),
            ("Place 6 & 8", Place68Strategy),
            ("Regress and Press", RegressAndPressStrategy),
        ]

        # Track which strategies are selected
        self.strategy_vars: dict[str, tk.BooleanVar] = {}

        # Results
        self.results = None
        self.fig = None
        self.ax = None
        self.canvas = None

        self._build_ui()

    def _build_ui(self):
        """Build the test configuration UI."""
        # Top: Configuration panel
        config_frame = tk.LabelFrame(
            self.window, text="Test Configuration",
            bg='#1a0f2e', fg='white', font=('Arial', 12, 'bold'),
            padx=10, pady=10
        )
        config_frame.pack(fill=tk.X, padx=10, pady=10)

        # Left side: Strategy selection
        left_frame = tk.Frame(config_frame, bg='#1a0f2e')
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 20))

        tk.Label(
            left_frame, text="Select Strategies:",
            bg='#1a0f2e', fg='white', font=('Arial', 10, 'bold')
        ).pack(anchor='w', pady=(0, 5))

        for name, strategy_class in self.available_strategies:
            var = tk.BooleanVar(value=True)
            cb = tk.Checkbutton(
                left_frame, text=name, variable=var,
                bg='#1a0f2e', fg='white', selectcolor='#2d1b4e',
                activebackground='#1a0f2e', activeforeground='white',
                font=('Arial', 10)
            )
            cb.pack(anchor='w', pady=2)
            self.strategy_vars[name] = var

        # Right side: Parameters
        right_frame = tk.Frame(config_frame, bg='#1a0f2e')
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=(20, 0))

        tk.Label(
            right_frame, text="Simulation Parameters:",
            bg='#1a0f2e', fg='white', font=('Arial', 10, 'bold')
        ).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 10))

        # Table Minimum
        tk.Label(
            right_frame, text="Table Minimum:",
            bg='#1a0f2e', fg='white', font=('Arial', 9)
        ).grid(row=1, column=0, sticky='w', pady=5)
        self.table_min_var = tk.StringVar(value="5")
        table_min_combo = ttk.Combobox(
            right_frame, textvariable=self.table_min_var,
            values=['5', '10', '15', '25'],
            width=12, font=('Arial', 9), state='readonly'
        )
        table_min_combo.grid(row=1, column=1, sticky='w', padx=(10, 0), pady=5)

        # Bankroll
        tk.Label(
            right_frame, text="Starting Bankroll:",
            bg='#1a0f2e', fg='white', font=('Arial', 9)
        ).grid(row=2, column=0, sticky='w', pady=5)
        self.bankroll_var = tk.StringVar(value="1000")
        tk.Entry(
            right_frame, textvariable=self.bankroll_var,
            width=15, font=('Arial', 9)
        ).grid(row=2, column=1, sticky='w', padx=(10, 0), pady=5)

        # Number of rolls
        tk.Label(
            right_frame, text="Number of Rolls:",
            bg='#1a0f2e', fg='white', font=('Arial', 9)
        ).grid(row=3, column=0, sticky='w', pady=5)
        self.rolls_var = tk.StringVar(value="1000")
        tk.Entry(
            right_frame, textvariable=self.rolls_var,
            width=15, font=('Arial', 9)
        ).grid(row=3, column=1, sticky='w', padx=(10, 0), pady=5)

        # Random seed
        tk.Label(
            right_frame, text="Random Seed (optional):",
            bg='#1a0f2e', fg='white', font=('Arial', 9)
        ).grid(row=4, column=0, sticky='w', pady=5)
        self.seed_var = tk.StringVar(value="")
        tk.Entry(
            right_frame, textvariable=self.seed_var,
            width=15, font=('Arial', 9)
        ).grid(row=4, column=1, sticky='w', padx=(10, 0), pady=5)

        # Run button
        tk.Button(
            right_frame, text="Run Test", font=('Arial', 12, 'bold'),
            bg='#cc0000', fg='white', command=self._run_test,
            width=15, height=2, relief=tk.RAISED, bd=3
        ).grid(row=5, column=0, columnspan=2, pady=15)

        # Middle: Results table
        results_frame = tk.LabelFrame(
            self.window, text="Results",
            bg='#1a0f2e', fg='white', font=('Arial', 12, 'bold'),
            padx=10, pady=10
        )
        results_frame.pack(fill=tk.X, padx=10, pady=10)

        # Treeview table
        columns = ("strategy", "final", "net", "roi")
        self.results_tree = ttk.Treeview(
            results_frame,
            columns=columns,
            show="headings",
            height=5
        )
        self.results_tree.heading("strategy", text="Strategy")
        self.results_tree.heading("final", text="Final Equity")
        self.results_tree.heading("net", text="Net Change")
        self.results_tree.heading("roi", text="ROI %")

        self.results_tree.column("strategy", width=200)
        self.results_tree.column("final", width=150, anchor='e')
        self.results_tree.column("net", width=150, anchor='e')
        self.results_tree.column("roi", width=150, anchor='e')

        self.results_tree.pack(fill=tk.X, padx=5, pady=5)

        # Bind selection to show detailed stats
        self.results_tree.bind('<<TreeviewSelect>>', self._on_strategy_selected)

        # Detailed statistics panel
        stats_frame = tk.LabelFrame(
            self.window, text="Detailed Statistics (select a strategy above)",
            bg='#1a0f2e', fg='white', font=('Arial', 11, 'bold'),
            padx=10, pady=10
        )
        stats_frame.pack(fill=tk.X, padx=10, pady=10)

        # Create two columns for stats
        left_stats = tk.Frame(stats_frame, bg='#1a0f2e')
        left_stats.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 20))

        right_stats = tk.Frame(stats_frame, bg='#1a0f2e')
        right_stats.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Left column stats
        self.stats_rolls_label = tk.Label(
            left_stats, text="Total Rolls: --",
            bg='#1a0f2e', fg='white', font=('Arial', 9), anchor='w'
        )
        self.stats_rolls_label.pack(fill=tk.X, pady=2)

        self.stats_shooters_label = tk.Label(
            left_stats, text="Total Shooters: --",
            bg='#1a0f2e', fg='white', font=('Arial', 9), anchor='w'
        )
        self.stats_shooters_label.pack(fill=tk.X, pady=2)

        self.stats_points_label = tk.Label(
            left_stats, text="Points Hit: --",
            bg='#1a0f2e', fg='#00ff00', font=('Arial', 9), anchor='w'
        )
        self.stats_points_label.pack(fill=tk.X, pady=2)

        # Right column stats
        self.stats_sevenouts_label = tk.Label(
            right_stats, text="Seven-Outs: --",
            bg='#1a0f2e', fg='#ff4444', font=('Arial', 9), anchor='w'
        )
        self.stats_sevenouts_label.pack(fill=tk.X, pady=2)

        self.stats_longest_label = tk.Label(
            right_stats, text="Longest Roll: --",
            bg='#1a0f2e', fg='#ffd700', font=('Arial', 9), anchor='w'
        )
        self.stats_longest_label.pack(fill=tk.X, pady=2)

        self.stats_avg_label = tk.Label(
            right_stats, text="Avg Rolls/Shooter: --",
            bg='#1a0f2e', fg='white', font=('Arial', 9), anchor='w'
        )
        self.stats_avg_label.pack(fill=tk.X, pady=2)

        # Roll distribution text
        tk.Label(
            stats_frame, text="Roll Distribution:",
            bg='#1a0f2e', fg='white', font=('Arial', 9, 'bold')
        ).pack(anchor='w', pady=(10, 2))

        self.distribution_label = tk.Label(
            stats_frame, text="--",
            bg='#1a0f2e', fg='#00aaff', font=('Courier', 8), anchor='w', justify=tk.LEFT
        )
        self.distribution_label.pack(fill=tk.X, pady=2)

        # Bottom: Graph
        graph_frame = tk.Frame(self.window, bg='#1a0f2e')
        graph_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Label(
            graph_frame, text="Strategy Comparison - Equity Over Time",
            bg='#1a0f2e', fg='#ffd700', font=('Arial', 12, 'bold')
        ).pack(pady=(0, 5))

        # Matplotlib canvas (will be created when test runs)
        self.graph_container = tk.Frame(graph_frame, bg='#1a0f2e')
        self.graph_container.pack(fill=tk.BOTH, expand=True)

    def _run_test(self):
        """Execute the strategy test."""
        # Parse configuration
        try:
            table_minimum = float(self.table_min_var.get())
            bankroll = float(self.bankroll_var.get())
            num_rolls = int(self.rolls_var.get())
            seed_str = self.seed_var.get().strip()
            seed = int(seed_str) if seed_str else None
        except ValueError:
            messagebox.showerror("Invalid Input", "Please check your parameter values")
            return

        # Build strategy list
        rules = TableRules(minimum_bet=int(table_minimum))
        strategies = []
        for name, strategy_class in self.available_strategies:
            if self.strategy_vars[name].get():
                # Instantiate with table minimum parameter
                strategy = strategy_class(bankroll, rules, table_minimum=table_minimum)
                strategies.append(strategy)

        if not strategies:
            messagebox.showinfo("No Strategies", "Please select at least one strategy")
            return

        # Create config
        config = SimulationConfig(
            strategies=strategies,
            num_rolls=num_rolls,
            starting_bankroll=bankroll,
            table_minimum=table_minimum,
            table_rules=rules,
            seed=seed
        )

        # Show busy cursor (try watch, fall back to default if not available)
        try:
            self.window.config(cursor="watch")
        except:
            pass
        self.window.update()

        try:
            # Run simulation
            runner = StrategyRunner(config)
            self.results = runner.run()

            # Update results table
            self._update_results_table()

            # Draw comparison graph
            self._draw_comparison_graph()

            messagebox.showinfo("Success", f"Test completed! Ran {num_rolls} rolls across {len(strategies)} strategies.")

        except Exception as e:
            messagebox.showerror("Error", f"Test failed: {str(e)}")
            import traceback
            traceback.print_exc()

        finally:
            try:
                self.window.config(cursor="")
            except:
                pass

    def _update_results_table(self):
        """Update the results tree with data."""
        # Clear existing
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

        # Add results
        for result in self.results:
            self.results_tree.insert(
                "", tk.END,
                values=(
                    result.strategy_name,
                    f"${result.final_equity:.2f}",
                    f"${result.net_change:+.2f}",
                    f"{result.roi_percent:+.2f}%"
                )
            )

        # Auto-select first result
        if self.results:
            first_item = self.results_tree.get_children()[0]
            self.results_tree.selection_set(first_item)
            self._update_detailed_stats(0)

    def _on_strategy_selected(self, event):
        """Handle strategy selection in results tree."""
        selection = self.results_tree.selection()
        if selection and self.results:
            # Get index of selected item
            item = selection[0]
            index = self.results_tree.index(item)
            self._update_detailed_stats(index)

    def _update_detailed_stats(self, result_index: int):
        """Update the detailed statistics panel for a specific result."""
        if not self.results or result_index >= len(self.results):
            return

        result = self.results[result_index]

        # Update basic stats
        bankrupt_text = " (BANKRUPT)" if result.went_bankrupt else ""
        self.stats_rolls_label.config(text=f"Total Rolls: {result.total_rolls}{bankrupt_text}")
        if result.went_bankrupt:
            self.stats_rolls_label.config(fg='#ff4444')
        else:
            self.stats_rolls_label.config(fg='white')

        self.stats_shooters_label.config(text=f"Total Shooters: {result.total_shooters}")
        self.stats_points_label.config(text=f"Points Hit: {result.points_hit}")
        self.stats_sevenouts_label.config(text=f"Seven-Outs: {result.seven_outs}")
        self.stats_longest_label.config(text=f"Longest Roll: {result.longest_roll}")

        # Calculate average rolls per shooter
        avg_rolls = result.total_rolls / result.total_shooters if result.total_shooters > 0 else 0
        self.stats_avg_label.config(text=f"Avg Rolls/Shooter: {avg_rolls:.1f}")

        # Format roll distribution as histogram
        dist_text = self._format_distribution(result.roll_distribution, result.total_rolls)
        self.distribution_label.config(text=dist_text)

    def _format_distribution(self, distribution: dict[int, int], total_rolls: int) -> str:
        """Format roll distribution as a text histogram."""
        if total_rolls == 0:
            return "No rolls"

        lines = []
        max_count = max(distribution.values()) if distribution else 1

        for roll_total in range(2, 13):
            count = distribution.get(roll_total, 0)
            percent = (count / total_rolls * 100) if total_rolls > 0 else 0

            # Create bar (scale to 30 chars max)
            bar_length = int((count / max_count) * 30) if max_count > 0 else 0
            bar = '█' * bar_length

            lines.append(f"{roll_total:2d}: {bar:<30} {count:4d} ({percent:5.2f}%)")

        return '\n'.join(lines)

    def _draw_comparison_graph(self):
        """Draw overlaid equity curves for all strategies."""
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        except ImportError:
            messagebox.showerror("Error", "matplotlib is required for graphs.\nInstall with: pip install matplotlib")
            return

        # Clear previous graph
        for widget in self.graph_container.winfo_children():
            widget.destroy()

        # Create figure with constrained layout
        self.fig, self.ax = plt.subplots(figsize=(10.5, 4.5), facecolor='#1a0f2e')
        self.ax.set_facecolor('#2d1b4e')

        # Color palette for strategies
        colors = ['#ffd700', '#00ff00', '#ff4444', '#00aaff', '#ff00ff']

        # Plot each strategy
        for i, result in enumerate(self.results):
            color = colors[i % len(colors)]
            self.ax.plot(
                result.rolls,
                result.equity_series,
                color=color,
                linewidth=2,
                label=result.strategy_name,
                alpha=0.9
            )

        # Reference line at starting bankroll
        if self.results:
            starting = self.results[0].starting_bankroll
            self.ax.axhline(
                y=starting,
                color='white',
                linestyle='--',
                linewidth=1,
                alpha=0.5,
                label='Starting Bankroll'
            )

        # Styling
        self.ax.set_xlabel('Roll Number', color='white', fontsize=10)
        self.ax.set_ylabel('Total Equity ($)', color='white', fontsize=10)
        self.ax.tick_params(colors='white')

        # Place legend outside plot area to the right
        self.ax.legend(
            facecolor='#2d1b4e',
            labelcolor='white',
            loc='center left',
            bbox_to_anchor=(1.02, 0.5),
            framealpha=0.95,
            fontsize=9
        )

        self.ax.grid(True, alpha=0.3, color='white', linestyle=':', linewidth=0.5)

        # Spines
        for spine in self.ax.spines.values():
            spine.set_color('white')

        # Adjust layout to prevent legend cutoff
        self.fig.subplots_adjust(right=0.82)

        # Embed in tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_container)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
