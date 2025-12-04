from __future__ import annotations

import argparse
import logging

from rich.console import Console
from rich.table import Table

from .historial_client import HistorialClient
from .model import MarkovModel

from datetime import datetime
from .exceptions import PredictorError

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
)

console = Console()


def validate_dates(start: str, end: str) -> None:
    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Formato de fecha inválido. Use YYYY-MM-DD.")

    if start_dt > end_dt:
        raise ValueError("La fecha de inicio no puede ser posterior a la fecha de fin.")


def print_top_global(model: MarkovModel, top_n: int = 10) -> None:
    table = Table(title=f"Top {top_n} animalitos por probabilidad global")
    table.add_column("Animalito", justify="left")
    table.add_column("Probabilidad", justify="right")

    for animal, p in model.top_global(top_n):
        table.add_row(animal, f"{p*100:5.2f}%")

    console.print(table)


def print_top_next(model: MarkovModel, actual: str, top_n: int = 5) -> None:
    table = Table(
        title=f"Probables próximos después de '{actual}' (modelo Markov)"
    )
    table.add_column("Siguiente", justify="left")
    table.add_column("P(B|A)", justify="right")

    resultados = model.top_next(actual, top_n)
    if not resultados:
        console.print(
            f"[yellow]No hay transiciones suficientes para '{actual}'.[/yellow]"
        )
        return

    for animal, p in resultados:
        table.add_row(animal, f"{p*100:5.2f}%")

    console.print(table)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analizador estadístico de La Granjita (Lotoven)."
    )
    parser.add_argument(
        "--start", required=True, help="Fecha inicio (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end", required=True, help="Fecha fin (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--after",
        help="Animalito actual para estimar probables siguientes (opcional)",
    )
    parser.add_argument(
        "--mode",
        choices=["sequential", "same_hour"],
        default="sequential",
        help="Modo de análisis: 'sequential' (siguiente sorteo) o 'same_hour' (misma hora día siguiente). Default: sequential",
    )
    args = parser.parse_args()

    try:
        validate_dates(args.start, args.end)

        client = HistorialClient()
        
        with console.status("[bold green]Cargando historial desde Lotoven...[/bold green]", spinner="dots"):
            data = client.fetch_historial(args.start, args.end)

        if data.total_sorteos == 0:
            console.print("[yellow]No se encontraron resultados para La Granjita en el rango seleccionado.[/yellow]")
            return

        console.print(f"[green]Historial cargado correctamente.[/green]")
        console.print(f"Rango: {args.start} a {args.end}")
        console.print(f"Días con datos: {data.dias_con_datos}")
        console.print(f"Total sorteos: {data.total_sorteos}")
        console.print("")

        model = MarkovModel.from_historial(data, mode=args.mode)

        console.rule(f"[bold cyan]Historial {args.start} → {args.end} | Modo: {args.mode}")
        print_top_global(model, top_n=10)

        if args.after:
            console.rule(f"[bold magenta]Condicional P(B|A={args.after})")
            print_top_next(model, args.after, top_n=7)

    except PredictorError as e:
        console.print(f"[bold red]Error del sistema:[/bold red] {e}")
    except ValueError as e:
        console.print(f"[bold red]Error de validación:[/bold red] {e}")
    except Exception as e:
        console.print(f"[bold red]Error inesperado:[/bold red] {e}")


if __name__ == "__main__":
    main()
