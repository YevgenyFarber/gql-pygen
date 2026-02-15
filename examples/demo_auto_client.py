#!/usr/bin/env python3
"""Demonstration of the auto-generated GraphQL client.

This script shows how to:
1. Parse a GraphQL schema
2. Generate a client with typed methods
3. Build and display queries

Note: This demo doesn't make real API calls - it just demonstrates
the query generation capabilities.
"""

import tempfile
import tarfile
from pathlib import Path

from gql_pygen.core import (
    SchemaParser,
    ClientGenerator,
    QueryBuilder,
    FieldSelection,
)


def main():
    # Path to the schema bundle
    schema_path = Path.home() / "Downloads" / "graphql-schema-and-examples-bundle.tgz"
    
    if not schema_path.exists():
        print(f"Schema not found at {schema_path}")
        print("Please download the Cato GraphQL schema bundle.")
        return
    
    print("=== Auto GraphQL Client Demo ===\n")
    
    # Parse the schema
    print("1. Parsing GraphQL schema...")
    with tempfile.TemporaryDirectory() as tmpdir:
        with tarfile.open(schema_path, 'r:gz') as tar:
            tar.extractall(tmpdir)
        
        parser = SchemaParser(tmpdir)
        ir = parser.parse_all()
    
    print(f"   Found {len(ir.queries)} queries and {len(ir.mutations)} mutations")
    print(f"   {len(ir.types)} types, {len(ir.enums)} enums")
    
    # Create query builder
    print("\n2. Creating query builder...")
    builder = QueryBuilder(ir)
    
    # Find an interesting operation
    print("\n3. Example: Internet Firewall addRule mutation")
    for op in ir.mutations:
        if op.path == ['policy', 'internetFirewall', 'addRule']:
            print(f"   Operation: {'.'.join(op.path)}")
            print(f"   Return type: {op.return_type}")
            print(f"   Arguments:")
            for arg in op.all_arguments:
                opt = " (optional)" if arg.is_optional else ""
                print(f"     - {arg.name}: {arg.type_name}{opt}")
            
            # Show different query styles
            print("\n   === MINIMAL query (for quick checks) ===")
            q_min = builder.build(op, FieldSelection.MINIMAL)
            print(q_min)
            
            print("\n   === ALL fields query (for complete data) ===")
            q_all = builder.build(op, FieldSelection.ALL)
            lines = q_all.split('\n')
            print('\n'.join(lines[:20]))
            print(f"   ... ({len(lines)} total lines)")
            break
    
    # Show client generation
    print("\n\n4. Generating typed client code...")
    gen = ClientGenerator(ir)
    code = gen.generate_client_code()
    
    print(f"   Generated {len(code.split(chr(10)))} lines of client code")
    print(f"   {code.count('class ')} client classes")
    print(f"   {code.count('async def ')} async methods")
    
    # Show a sample client class
    print("\n   === Sample: InternetFirewall client (first 40 lines) ===")
    lines = code.split('\n')
    in_class = False
    class_lines = []
    for line in lines:
        if 'class Mutation_Policy_InternetFirewallClient' in line:
            in_class = True
        if in_class:
            class_lines.append(line)
            if len(class_lines) >= 40:
                break
    print('\n'.join(class_lines))
    print("   ...")
    
    print("\n=== Demo Complete ===")
    print("\nUsage example (once the client is generated):")
    print("""
    async with CatoClient(url=API_URL, api_key=API_KEY) as client:
        result = await client.policy.internet_firewall.add_rule(
            account_id="12345",
            input_internet_firewall_add_rule=InternetFirewallAddRuleInput(
                at=PolicyRulePositionInput(position=PolicyRulePositionEnum.LAST_IN_POLICY),
                rule=InternetFirewallRuleInput(
                    name="Block malicious IPs",
                    enabled=True,
                    action=InternetFirewallActionEnum.BLOCK,
                    # ... more fields
                )
            )
        )
        print(f"Created rule: {result.rule.rule.id}")
    """)


if __name__ == "__main__":
    main()

