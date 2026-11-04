"""Per-source fetch metrics and the daily source report.

Every source adapter records what actually happened during a run:
last fetch time, HTTP-level status, duration, jobs discovered,
accepted, rejected as duplicates, merged, parser errors and the
permission status (robots.txt). One failing source never affects
another.

The pipeline writes two artifacts per run (overwritten daily, so the
repo does not grow):
- logs/source_report.json   (machine-readable, all metrics)
- logs/source_report.md     (human-readable daily report)

A successful HTTP response is NOT treated as proof that extraction
worked: sources that return zero jobs are listed explicitly so stale
or broken feeds are visible.
"""
import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

REPORT_JSON = os.path.join('logs', 'source_report.json')
REPORT_MD = os.path.join('logs', 'source_report.md')


class SourceMetrics:
    """Collects per-source run statistics."""

    def __init__(self):
        self.started_at = datetime.now().isoformat()
        self.sources = {}

    def record(self, name, **fields):
        """Record/merge stats for one source.

        Known keys: status ('ok', 'no-jobs', 'robots-disallowed',
        'fetch-failed', 'parse-error', 'not-configured'),
        permission ('allowed', 'disallowed', 'unverified'),
        duration_s, discovered, accepted, duplicates, merged,
        parser_errors, notes.
        """
        if not name:
            name = 'unknown'
        entry = self.sources.setdefault(name, {
            'source': name,
            'last_fetch': datetime.now().isoformat(),
        })
        for key, value in fields.items():
            if value is None:
                continue
            if key in ('discovered', 'accepted', 'duplicates', 'merged',
                       'parser_errors') and isinstance(entry.get(key), int) \
                    and isinstance(value, int):
                entry[key] = entry[key] + value
            else:
                entry[key] = value

    def note_pipeline_totals(self, **totals):
        """Attach whole-run totals (new jobs, expired, archived...)."""
        self.totals = dict(getattr(self, 'totals', {}))
        for key, value in totals.items():
            self.totals[key] = value

    def to_dict(self):
        sources = sorted(self.sources.values(), key=lambda s: s.get('source', ''))
        return {
            'run_started_at': self.started_at,
            'generated_at': datetime.now().isoformat(),
            'totals': dict(getattr(self, 'totals', {})),
            'sources': sources,
        }

    def needs_attention(self, entry):
        """A source needs attention when it failed or found nothing.

        Always returns a real bool (a raw falsy value like None from
        .get() must never leak out as the return value).
        """
        status = str(entry.get('status') or '')
        return bool(
            status in ('fetch-failed', 'parse-error', 'robots-disallowed', 'error')
            or status == 'no-jobs'
            or entry.get('parser_errors')
        )

    def write_report(self, json_path=REPORT_JSON, md_path=REPORT_MD):
        """Write the JSON + markdown reports. Failures never raise."""
        report = self.to_dict()
        try:
            os.makedirs(os.path.dirname(json_path), exist_ok=True)
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error('Failed to write %s: %s', json_path, e)
        if not md_path:
            return report
        try:
            os.makedirs(os.path.dirname(md_path), exist_ok=True)
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(self._markdown(report))
        except OSError as e:
            logger.error('Failed to write %s: %s', md_path, e)
        return report

    def _markdown(self, report):
        lines = []
        lines.append('# Sarkari Sarthi daily source report')
        lines.append('')
        lines.append('Run started: ' + str(report.get('run_started_at', ''))[:19])
        totals = report.get('totals') or {}
        if totals:
            lines.append('')
            lines.append('## Run totals')
            lines.append('')
            for key in sorted(totals):
                lines.append('- ' + key.replace('_', ' ') + ': ' + str(totals[key]))
        lines.append('')
        lines.append('## Sources')
        lines.append('')
        lines.append('| Source | Status | Duration | Found | New | Dup | Merged | Errors | Notes |')
        lines.append('|---|---|---|---|---|---|---|---|---|')
        for entry in report.get('sources', []):
            lines.append('| ' + ' | '.join(str(entry.get(k, '')) for k in (
                'source', 'status', 'duration_s', 'discovered',
                'accepted', 'duplicates', 'merged', 'parser_errors', 'notes',
            )) + ' |')
        attention = [e for e in report.get('sources', []) if self.needs_attention(e)]
        lines.append('')
        if attention:
            lines.append('## Needs attention')
            lines.append('')
            for entry in attention:
                reason = entry.get('status') or 'unknown'
                if entry.get('parser_errors'):
                    reason += ' (parser errors: %s)' % entry['parser_errors']
                lines.append('- ' + str(entry.get('source')) + ': ' + str(reason))
        else:
            lines.append('All sources returned data; no attention flags.')
        lines.append('')
        lines.append('A source returning HTTP 200 with zero extracted jobs still '
                     'appears above: extraction success is measured by parsed jobs, '
                     'not by HTTP status alone.')
        return '\n'.join(lines) + '\n'
