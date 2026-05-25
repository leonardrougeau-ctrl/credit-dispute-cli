#!/usr/bin/env python3
import csv
import click
from datetime import datetime
from metro2_encoder import generate_metro2_file

@click.group()
def cli():
    """Credit Dispute CLI Tool - Generate Metro 2 files for credit bureaus"""
    pass

@cli.command()
@click.option('--input', '-i', required=True, help='Input CSV file with dispute data')
@click.option('--output', '-o', required=True, help='Output Metro 2 file path')
@click.option('--bank', required=True, help='Bank name (appears in file header)')
@click.option('--preparer', default='Credit Dispute Tool', help='Preparer name (default: Credit Dispute Tool)')
@click.option('--file-id', default=None, help='File identifier (optional, auto-generated if not provided)')
def generate(input, output, bank, preparer, file_id):
    """Generate a Metro 2 compliant dispute file from a CSV input.
    
    Example:
        python3 cli.py generate -i disputes.csv -o output.dat --bank "First National Bank"
    """
    disputes = []
    with open(input, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if 'effective_date' in row and row['effective_date']:
                try:
                    datetime.strptime(row['effective_date'], '%Y-%m-%d')
                except:
                    click.echo(f"Warning: Invalid date {row['effective_date']}")
            disputes.append(row)
    
    if not disputes:
        click.echo("❌ No disputes found in CSV")
        return
    
    if not file_id:
        file_id = f"DISPUTE_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    header_data = {
        'bank_name': bank,
        'preparer_name': preparer,
        'file_id': file_id,
    }
    
    generate_metro2_file(header_data, disputes, output)
    click.echo(f"✓ Generated {len(disputes)} dispute records to {output}")

@cli.command()
@click.option('--file', '-f', required=True, help='Metro 2 file to validate')
def validate(file):
    """Validate a Metro 2 file structure.
    
    Example:
        python3 cli.py validate -f output.dat
    """
    with open(file, 'r') as f:
        lines = f.readlines()
    
    if len(lines) < 3:
        click.echo("❌ File too short (need header, details, trailer)")
        return
    
    errors = 0
    
    if lines[0][:2] != '01':
        click.echo("❌ Header missing (first line should start with '01')")
        errors += 1
    else:
        click.echo("✓ Header found")
    
    detail_count = 0
    for i, line in enumerate(lines[1:-1], 1):
        if line[:2] == '11':
            detail_count += 1
        elif line[:2] not in ['11', '99']:
            click.echo(f"⚠️ Line {i+1}: Unknown record type '{line[:2]}'")
    
    click.echo(f"✓ {detail_count} detail records found")
    
    if lines[-1][:2] != '99':
        click.echo("❌ Trailer missing (last line should start with '99')")
        errors += 1
    else:
        click.echo("✓ Trailer found")
    
    if errors == 0:
        click.echo("✅ File structure is valid")
    else:
        click.echo(f"❌ Found {errors} error(s)")

if __name__ == '__main__':
    cli()
