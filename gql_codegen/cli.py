"""Command-line interface for gql-codegen."""

import click
from pathlib import Path

from .core.parser import SchemaParser
from .core.generator import CodeGenerator


@click.group()
@click.version_option()
def main():
    """Improved GraphQL code generator for Python.

    Generate typed Python code from GraphQL schemas.
    """
    pass


@main.command()
@click.option(
    "--schema",
    "-s",
    required=True,
    type=click.Path(exists=True),
    help="Path to GraphQL schema file or directory containing .graphqls files.",
)
@click.option(
    "--output",
    "-o",
    required=True,
    type=click.Path(),
    help="Output directory for generated code.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output.",
)
def generate(schema: str, output: str, verbose: bool):
    """Generate Python code from GraphQL schema.

    Examples:

        gql-codegen generate --schema ./schema --output ./generated

        gql-codegen generate -s ./schema.graphqls -o ./client
    """
    schema_path = Path(schema).resolve()
    output_path = Path(output).resolve()

    if verbose:
        click.echo(f"Schema: {schema_path}")
        click.echo(f"Output: {output_path}")

    # Parse schema
    click.echo("Parsing schema...")
    parser = SchemaParser(str(schema_path))
    ir = parser.parse_all()

    if verbose:
        click.echo(f"  Scalars: {len(ir.scalars)}")
        click.echo(f"  Enums: {len(ir.enums)}")
        click.echo(f"  Types: {len(ir.types)}")
        click.echo(f"  Inputs: {len(ir.inputs)}")
        click.echo(f"  Interfaces: {len(ir.interfaces)}")
        click.echo(f"  Queries: {len(ir.queries)}")
        click.echo(f"  Mutations: {len(ir.mutations)}")

    # Generate code
    click.echo("Generating code...")
    generator = CodeGenerator(ir, str(output_path))
    generator.generate()

    click.echo(f"Done! Generated code in {output_path}")


if __name__ == "__main__":
    main()

