#!/usr/bin/env python3
"""Record the Python actually used on lxplus; never install or upgrade it."""
import argparse
import datetime
import importlib
import importlib.metadata
import json
import platform
import sys
from pathlib import Path

REQUIRED = ('numpy', 'pandas', 'scipy', 'matplotlib', 'uproot', 'iminuit',
            'lz4', 'coffea', 'awkward', 'mplhep', 'PIL')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    modules = {}
    for name in REQUIRED:
        try:
            module = importlib.import_module(name)
            modules[name] = {'import_ok': True, 'version': getattr(module, '__version__', None),
                             'file': getattr(module, '__file__', None)}
        except Exception as exc:
            modules[name] = {'import_ok': False, 'error': f'{type(exc).__name__}: {exc}'}
    packages = sorted([{'name': d.metadata.get('Name', ''), 'version': d.version}
                       for d in importlib.metadata.distributions()], key=lambda d: d['name'].lower())
    report = {'recorded_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'hostname': platform.node(), 'python': sys.version,
              'executable': sys.executable, 'prefix': sys.prefix,
              'modules': modules, 'installed_distributions': packages,
              'all_required_imports_pass': all(m['import_ok'] for m in modules.values()),
              'analysis_executed': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as out:
        json.dump(report, out, indent=2)
        out.write('\n')
    print('Python:', sys.executable, sys.version.split()[0])
    for name, item in modules.items():
        print(name, item.get('version') if item['import_ok'] else item['error'])
    print('Environment report:', args.output.resolve())
    return 0 if report['all_required_imports_pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
