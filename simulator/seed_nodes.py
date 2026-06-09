#!/usr/bin/env python3
"""
seed_nodes.py — Smart-Stua Simulator
=====================================
Registers the 3 simulated sensor nodes (NODE_001–NODE_003) directly
into the Django database so the simulator can post readings immediately.

Run this ONCE before starting simulator.py:

    cd Smart-stua/simulator
    python seed_nodes.py

Requirements:
  - Django server NOT required (writes direct to SQLite via Django ORM)
  - Must be run from the simulator/ directory (or pass --backend-dir)
"""

import argparse
import os
import sys
import io
import django

# Force UTF-8 output so box-drawing characters work on Windows PowerShell
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def setup_django(backend_dir):
    """Boot the Django ORM without running the web server."""
    sys.path.insert(0, backend_dir)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartstua.settings')
    django.setup()

# ── Node definitions — match DEFAULT_NODES in simulator.py ───────────────────
NODES_TO_SEED = [
    {
        'node_identifier': 'NODE_001',
        'location_label':  'Gulu Main Store - Section A',
        'gateway_id':      'SIM-001',
        'notes':           '[SIMULATED] Virtual node for pipeline testing.',
    },
    {
        'node_identifier': 'NODE_002',
        'location_label':  'Gulu Main Store - Section B',
        'gateway_id':      'SIM-002',
        'notes':           '[SIMULATED] Virtual node for pipeline testing.',
    },
    {
        'node_identifier': 'NODE_003',
        'location_label':  'Lira Transit Depot - Bay 1',
        'gateway_id':      'SIM-003',
        'notes':           '[SIMULATED] Virtual node for pipeline testing.',
    },
]

THRESHOLD_DEFAULTS = {
    'min_temp':      10.0,
    'max_temp':      35.0,
    'min_humidity':  40.0,
    'max_humidity':  75.0,
    'risk_duration': 6,
}


def seed(dry_run=False):
    from monitoring.models import SensorNode, Threshold, NodeStatus

    print('\n--- Smart-Stua Node Seeder -----------------------------------\n')

    for spec in NODES_TO_SEED:
        node, created = SensorNode.objects.get_or_create(
            node_identifier=spec['node_identifier'],
            defaults={
                'location_label': spec['location_label'],
                'gateway_id':     spec['gateway_id'],
                'status':         NodeStatus.ACTIVE,
                'notes':          spec['notes'],
            }
        )

        # Ensure existing nodes are active (idempotent)
        if not created and node.status != NodeStatus.ACTIVE:
            if not dry_run:
                node.status = NodeStatus.ACTIVE
                node.save(update_fields=['status'])
            print(f'  ~  {node.node_identifier:<12} - updated to ACTIVE')
        else:
            verb = 'CREATED' if created else 'EXISTS '
            print(f'  OK {node.node_identifier:<12} - {verb}  ({node.location_label})')

        # Create default threshold if missing
        if created:
            th, th_created = Threshold.objects.get_or_create(
                node=node, defaults=THRESHOLD_DEFAULTS)
            if th_created:
                print(f'       +- Threshold created (T:{th.min_temp}-{th.max_temp}C  H:{th.min_humidity}-{th.max_humidity}%)')

    print(f'\n  Total nodes in DB: {SensorNode.objects.count()}')
    print('\n-------------------------------------------------------------\n')
    print('  DONE! You can now run:  python simulator.py\n')


def main():
    p = argparse.ArgumentParser(description='Seed Smart-Stua simulator nodes into Django DB')
    p.add_argument('--backend-dir', default=os.path.join(os.path.dirname(__file__), '..', 'backend'),
                   help='Path to the Django backend directory (default: ../backend)')
    p.add_argument('--dry-run', action='store_true', help='Print what would be done without writing')
    args = p.parse_args()

    backend_dir = os.path.abspath(args.backend_dir)
    if not os.path.isdir(backend_dir):
        print(f'ERROR: backend directory not found at: {backend_dir}')
        sys.exit(1)

    setup_django(backend_dir)
    seed(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
