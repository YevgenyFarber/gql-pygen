"""Command-line interface for gql-pygen."""

import click
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path

from .core.parser import SchemaParser
from .core.generator import CodeGenerator
from .core.client_generator import ClientGenerator


def extract_archive(archive_path: Path) -> str:
    """Extract archive to temp directory. Returns path to extracted content."""
    temp_dir = tempfile.mkdtemp()
    if archive_path.suffix == ".zip":
        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            zip_ref.extractall(temp_dir)
    elif archive_path.name.endswith((".tar.gz", ".tgz")):
        with tarfile.open(archive_path, "r:gz") as tar_ref:
            tar_ref.extractall(temp_dir)
    else:
        shutil.rmtree(temp_dir)
        raise ValueError(f"Unsupported archive format: {archive_path.suffix}")
    return temp_dir


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
    help="Path to GraphQL schema file, directory, or archive (.zip, .tar.gz, .tgz).",
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

        gql-pygen generate --schema ./schema --output ./generated

        gql-pygen generate -s ./schema.graphqls -o ./client

        gql-pygen generate -s ./schema.tgz -o ./generated
    """
    schema_path = Path(schema).resolve()
    output_path = Path(output).resolve()
    temp_dir = None

    try:
        # Handle archives
        actual_schema_path = schema_path
        if schema_path.is_file() and schema_path.name.lower().endswith(
            (".zip", ".tar.gz", ".tgz")
        ):
            click.echo(f"Extracting archive {schema_path.name}...")
            temp_dir = extract_archive(schema_path)
            actual_schema_path = Path(temp_dir)
            if verbose:
                click.echo(f"  Extracted to: {temp_dir}")

        if verbose:
            click.echo(f"Schema: {actual_schema_path}")
            click.echo(f"Output: {output_path}")

        # Parse schema
        click.echo("Parsing schema...")
        parser = SchemaParser(str(actual_schema_path))
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
    finally:
        # Clean up temp directory
        if temp_dir:
            shutil.rmtree(temp_dir)


@main.command()
@click.option(
    "--schema",
    "-s",
    required=True,
    type=click.Path(exists=True),
    help="Path to GraphQL schema file, directory, or archive (.zip, .tar.gz, .tgz).",
)
@click.option(
    "--output",
    "-o",
    required=True,
    type=click.Path(),
    help="Output file for generated client code (e.g., client.py).",
)
@click.option(
    "--client-name",
    "-n",
    default="GraphQLClient",
    help="Name of the generated client class (default: GraphQLClient).",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output.",
)
def client(schema: str, output: str, client_name: str, verbose: bool):
    """Generate auto-client with typed methods from GraphQL schema.

    This generates a nested client structure like:
        client.policy.internet_firewall.add_rule(...)

    The generated client includes all queries and mutations as typed async methods.

    Examples:

        gql-pygen client --schema ./schema.tgz --output ./client.py

        gql-pygen client -s ./schema -o ./client.py --client-name MyClient
    """
    schema_path = Path(schema).resolve()
    output_path = Path(output).resolve()
    temp_dir = None

    try:
        # Handle archives
        actual_schema_path = schema_path
        if schema_path.is_file() and schema_path.name.lower().endswith(
            (".zip", ".tar.gz", ".tgz")
        ):
            click.echo(f"Extracting archive {schema_path.name}...")
            temp_dir = extract_archive(schema_path)
            actual_schema_path = Path(temp_dir)
            if verbose:
                click.echo(f"  Extracted to: {temp_dir}")

        if verbose:
            click.echo(f"Schema: {actual_schema_path}")
            click.echo(f"Output: {output_path}")

        # Parse schema
        click.echo("Parsing schema...")
        parser = SchemaParser(str(actual_schema_path))
        ir = parser.parse_all()

        if verbose:
            click.echo(f"  Types: {len(ir.types)}")
            click.echo(f"  Enums: {len(ir.enums)}")
            click.echo(f"  Queries: {len(ir.queries)}")
            click.echo(f"  Mutations: {len(ir.mutations)}")
            click.echo(f"  Nested operations: {len([op for op in ir.all_operations if len(op.path) > 1])}")

        # Generate client code
        click.echo(f"Generating client code (class: {client_name})...")
        generator = ClientGenerator(ir, client_name=client_name)
        code = generator.generate_client_code()

        # Count stats
        num_lines = len(code.split('\n'))
        num_classes = code.count('class ')
        num_methods = code.count('async def ')

        if verbose:
            click.echo(f"  Lines: {num_lines}")
            click.echo(f"  Classes: {num_classes}")
            click.echo(f"  Async methods: {num_methods}")

        # Create output directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the file
        click.echo(f"Writing to {output_path}...")
        with open(output_path, 'w') as f:
            f.write(code)

        click.echo(f"Done! Generated {num_classes} client classes with {num_methods} methods.")
        click.echo(f"Output: {output_path}")

    finally:
        # Clean up temp directory
        if temp_dir:
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    main()

