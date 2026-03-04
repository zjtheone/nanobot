"""CLI commands for managing agent teams."""

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="teams", help="Manage agent teams")
console = Console()


@app.command("list")
def list_teams():
    """List all configured agent teams."""
    from nanobot.config.loader import load_config

    config = load_config()
    teams = config.agents.teams

    if not teams:
        console.print("[yellow]No teams configured[/yellow]")
        console.print("\nAdd teams to ~/.nanobot/config.json under agents.teams")
        return

    table = Table(title="Agent Teams")
    table.add_column("Name", style="cyan")
    table.add_column("Members", style="green")
    table.add_column("Leader", style="yellow")
    table.add_column("Strategy", style="magenta")

    for team in teams:
        members_str = ", ".join(team.members)
        leader_str = team.leader or "-"
        strategy_str = team.strategy

        table.add_row(team.name, members_str, leader_str, strategy_str)

    console.print(table)
    console.print(f"\nTotal: {len(teams)} team(s)")


@app.command("info")
def team_info(team_name: str = typer.Argument(..., help="Team name")):
    """Show detailed information about a team."""
    from nanobot.config.loader import load_config
    from nanobot.agent.team.manager import TeamManager

    config = load_config()
    manager = TeamManager(config.agents)

    summary = manager.get_team_summary(team_name)

    if "error" in summary:
        console.print(f"[red]{summary['error']}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[cyan]Team:[/cyan] {summary['name']}")
    console.print(f"[cyan]Members:[/cyan] {summary['member_count']}")
    console.print(f"[cyan]Leader:[/cyan] {summary['leader'] or 'None'}")
    console.print(f"[cyan]Strategy:[/cyan] {summary['strategy']}")
    console.print(f"[cyan]Valid:[/cyan] {'✅ Yes' if summary['valid'] else '❌ No'}")

    if summary["errors"]:
        console.print("\n[red]Validation Errors:[/red]")
        for error in summary["errors"]:
            console.print(f"  • {error}")

    if summary["member_configs"]:
        console.print("\n[cyan]Member Details:[/cyan]")
        for member in summary["member_configs"]:
            console.print(f"  • {member['id']} (model: {member['model'] or 'default'})")


@app.command("status")
def team_status(team_name: str = typer.Argument(..., help="Team name")):
    """Show team member status (requires running gateway)."""
    console.print("[yellow]Team status requires a running gateway with --multi[/yellow]")
    console.print("This feature will be available in a future release.")


@app.command("validate")
def validate_team(team_name: str = typer.Argument(..., help="Team name to validate")):
    """Validate a team configuration."""
    from nanobot.config.loader import load_config
    from nanobot.agent.team.manager import TeamManager

    config = load_config()
    manager = TeamManager(config.agents)

    errors = manager.validate_team(team_name)

    if not errors:
        console.print(f"[green]✅ Team '{team_name}' is valid[/green]")
    else:
        console.print(f"[red]❌ Team '{team_name}' has {len(errors)} error(s):[/red]")
        for error in errors:
            console.print(f"  • {error}")
        raise typer.Exit(1)


# Alias for backward compatibility
validate = validate_team
