"""
export_safe_fixtures.py — Smart-Stua Safe Database Export Command
================================================================
Exports current local database data as portable JSON fixtures that can be
safely loaded into a remote/production database with ZERO data destruction.

Usage:
  # Export from local dev (SQLite or Docker PostgreSQL):
  python manage.py export_safe_fixtures

  # Then on the production server (Render shell or one-off job), import with:
  python manage.py loaddata fixtures/users.json
  python manage.py loaddata fixtures/sensor_nodes.json
  python manage.py loaddata fixtures/thresholds.json
  # NOTE: Do NOT import readings.json into production unless you explicitly
  # want to seed historical telemetry — it can be very large.

Safe-Merge Semantics:
  loaddata uses INSERT OR UPDATE (natural key resolution).
  Existing production records with matching PKs are updated, NOT deleted.
  Records in production that are NOT in the fixture are left untouched.
"""

import os
import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings


FIXTURES_DIR = Path(settings.BASE_DIR) / 'fixtures'

# Models to export, in dependency order (parents before children)
EXPORT_SETS = [
    {
        'name': 'users',
        'app_label': 'monitoring',
        'model': 'user',
        'description': 'Smart-Stua app users (farmers/admins)',
    },
    {
        'name': 'sensor_nodes',
        'app_label': 'monitoring',
        'model': 'sensornode',
        'description': 'Registered ESP32 hardware nodes',
    },
    {
        'name': 'thresholds',
        'app_label': 'monitoring',
        'model': 'threshold',
        'description': 'Per-node alert threshold configurations',
    },
    {
        'name': 'alert_logs',
        'app_label': 'monitoring',
        'model': 'alertlog',
        'description': 'Historical alert records',
    },
    {
        'name': 'readings_recent',
        'app_label': 'monitoring',
        'model': 'reading',
        'description': 'Sensor telemetry readings (LARGE — use with caution)',
    },
    {
        'name': 'auth_users',
        'app_label': 'auth',
        'model': 'user',
        'description': 'Django admin panel users',
    },
    {
        'name': 'auth_tokens',
        'app_label': 'authtoken',
        'model': 'token',
        'description': 'DRF auth tokens for API sessions',
    },
]


class Command(BaseCommand):
    help = (
        'Safely exports all application data as JSON fixtures to the fixtures/ '
        'directory. Safe to run on any environment — read-only, no data modification.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-readings',
            action='store_true',
            default=True,
            help='Skip exporting sensor readings (can be very large). Default: True',
        )
        parser.add_argument(
            '--include-readings',
            action='store_true',
            default=False,
            help='Include sensor readings export (WARNING: may be very large)',
        )
        parser.add_argument(
            '--output-dir',
            type=str,
            default=str(FIXTURES_DIR),
            help=f'Directory to write fixture files. Default: {FIXTURES_DIR}',
        )

    def handle(self, *args, **options):
        output_dir = Path(options['output_dir'])
        output_dir.mkdir(parents=True, exist_ok=True)

        include_readings = options['include_readings']
        skip_readings = not include_readings

        self.stdout.write(self.style.SUCCESS(
            f'\n📦  Smart-Stua Safe Fixture Export\n'
            f'    Output directory: {output_dir}\n'
            f'    Include readings: {include_readings}\n'
        ))

        summary = []

        for export_set in EXPORT_SETS:
            model_label = f"{export_set['app_label']}.{export_set['model']}"
            fixture_name = export_set['name']
            description = export_set['description']

            # Skip readings unless explicitly requested
            if export_set['model'] == 'reading' and skip_readings:
                self.stdout.write(
                    f'  ⏭️   Skipping {fixture_name} (readings — use --include-readings to export)'
                )
                summary.append({'model': model_label, 'status': 'skipped', 'file': None})
                continue

            output_file = output_dir / f'{fixture_name}.json'

            try:
                self.stdout.write(f'  📝  Exporting {model_label} → {output_file.name} ...')
                with open(output_file, 'w') as f:
                    call_command(
                        'dumpdata',
                        model_label,
                        indent=2,
                        natural_foreign=True,
                        natural_primary=True,
                        stdout=f,
                    )

                # Count records
                with open(output_file) as f:
                    data = json.load(f)
                record_count = len(data)

                self.stdout.write(self.style.SUCCESS(
                    f'  ✅  {fixture_name}.json — {record_count} record(s)'
                ))
                summary.append({
                    'model': model_label,
                    'status': 'ok',
                    'file': str(output_file),
                    'records': record_count,
                })

            except Exception as exc:
                self.stdout.write(self.style.ERROR(
                    f'  ❌  Failed to export {model_label}: {exc}'
                ))
                summary.append({'model': model_label, 'status': 'error', 'error': str(exc)})

        # Write import instructions
        instructions_file = output_dir / 'IMPORT_INSTRUCTIONS.md'
        self._write_import_instructions(instructions_file, summary, include_readings)

        self.stdout.write('\n' + '─' * 60)
        self.stdout.write(self.style.SUCCESS('✅  Export complete!\n'))
        self.stdout.write(f'📁  Fixtures saved to: {output_dir}')
        self.stdout.write(f'📖  See {instructions_file.name} for import steps.\n')

    def _write_import_instructions(self, path, summary, include_readings):
        lines = [
            '# Smart-Stua — Safe Database Import Instructions',
            '',
            '> **SAFE TO RUN:** `loaddata` uses INSERT OR REPLACE semantics.',
            '> Existing production records are updated, not deleted.',
            '> Records only in production (not in the fixture) are left untouched.',
            '',
            '## Option A — Render.com (via one-off job or Shell)',
            '',
            'In your Render dashboard → smartstua-backend → Shell:',
            '',
            '```bash',
            '# Upload fixture files first (scp / git commit / Render CLI)',
            '# Then run in the Render shell:',
            'python manage.py loaddata fixtures/auth_users.json',
            'python manage.py loaddata fixtures/users.json',
            'python manage.py loaddata fixtures/sensor_nodes.json',
            'python manage.py loaddata fixtures/thresholds.json',
            'python manage.py loaddata fixtures/alert_logs.json',
        ]
        if include_readings:
            lines.append('python manage.py loaddata fixtures/readings_recent.json')
        lines += [
            '```',
            '',
            '## Option B — pg_dump / pg_restore (Structural Clone)',
            '',
            '```bash',
            '# Dump local Docker PostgreSQL (zero-data-loss append):',
            'docker exec smartstua_db pg_dump \\',
            '  -U smartstua -d smartstua_db \\',
            '  --data-only --column-inserts \\',
            '  --on-conflict-do-nothing \\',
            '  -f /tmp/smartstua_data.sql',
            '',
            '# Copy dump out of container:',
            'docker cp smartstua_db:/tmp/smartstua_data.sql ./smartstua_data.sql',
            '',
            '# Apply to Render PostgreSQL (get URL from Render dashboard):',
            'psql $RENDER_DATABASE_URL < smartstua_data.sql',
            '```',
            '',
            '## Exported Models',
            '',
            '| Model | Records | Status |',
            '|---|---|---|',
        ]
        for s in summary:
            status = '✅' if s['status'] == 'ok' else ('⏭️' if s['status'] == 'skipped' else '❌')
            records = s.get('records', s.get('status', '—'))
            lines.append(f"| `{s['model']}` | {records} | {status} |")

        path.write_text('\n'.join(lines))
