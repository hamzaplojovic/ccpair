import click
from claude_pair.messages import format_outgoing


def prompt(msg: dict) -> bool:
    click.echo(f"\n{format_outgoing(msg)}")
    return True
