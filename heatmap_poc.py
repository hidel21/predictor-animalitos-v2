from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
import random

console = Console(force_terminal=True)

def get_color(value):
    """Return a color based on intensity value (0-100)."""
    if value < 20: return "blue"
    if value < 40: return "cyan"
    if value < 60: return "green"
    if value < 80: return "yellow"
    return "red"

def create_heatmap():
    # 37 items
    items = list(range(1, 38))
    intensities = {item: random.randint(0, 100) for item in items}

    # Create table
    table = Table(show_header=False, show_edge=False, pad_edge=False, box=None, padding=0)
    
    # 7 columns
    for _ in range(7):
        table.add_column(width=6, justify="center")

    row_cells = []
    for item in items:
        intensity = intensities[item]
        color = get_color(intensity)
        
        # Create a block with the number and intensity
        # We use a Panel to create the box effect
        # style=f"on {color}" sets the background of the panel
        content = f"{item:02d}\n{intensity}%"
        panel = Panel(
            Text(content, justify="center", style="white"),
            style=f"on {color}",
            box=box.SQUARE,
            width=6,
            height=3
        )
        row_cells.append(panel)
        
        if len(row_cells) == 7:
            table.add_row(*row_cells)
            row_cells = []

    # Fill last row
    if row_cells:
        while len(row_cells) < 7:
            row_cells.append(Text("", style="on black"))
        table.add_row(*row_cells)

    console.print(table)

if __name__ == "__main__":
    create_heatmap()
