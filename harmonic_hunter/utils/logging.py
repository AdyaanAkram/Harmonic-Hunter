from rich.console import Console

console = Console()

def info(msg: str) -> None:
    console.print(f"[bold cyan]INFO[/bold cyan] {msg}")

def warn(msg: str) -> None:
    console.print(f"[bold yellow]WARN[/bold yellow] {msg}")

def error(msg: str) -> None:
    console.print(f"[bold red]ERROR[/bold red] {msg}")
