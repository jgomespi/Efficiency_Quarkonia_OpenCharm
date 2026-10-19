#!/usr/bin/env python3
"""Run the selected J/psi+D* notebooks in a new output directory."""
import argparse
import datetime
import gzip
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def preflight(paths, hash_mixing=False):
    manifest = json.loads((ROOT / 'reference/input_manifest.json').read_text())
    checks = []
    for item in manifest['files']:
        root = Path(paths['efficiency_root' if item['kind'] == 'efficiency' else 'data_root'])
        path = root / item['relative_path']
        current = digest(path) if path.is_file() else None
        checks.append(dict(item, path=str(path), observed_sha256=current,
                           passed=current == item['sha256']))
    mixing = Path(paths['mixing_root'])
    files = sorted(mixing.glob(paths['mixing_glob']))
    with gzip.open(ROOT / 'reference/mixing_inputs.json.gz', 'rt') as handle:
        catalog = json.load(handle)
    expected = {job['output_subdir'] + '/output_mixing_' + job['tag'] + '.coffea' for job in catalog['jobs']}
    actual = {p.relative_to(mixing).as_posix() for p in files}
    rows = []
    for path in files:
        st = path.stat()
        row = {'path': path.relative_to(mixing).as_posix(), 'size_bytes': st.st_size,
               'modified_ns': st.st_mtime_ns}
        if hash_mixing:
            row['sha256'] = digest(path)
        rows.append(row)
    return {'root_inputs_passed': all(c['passed'] for c in checks), 'root_inputs': checks,
            'mixing_file_set_passed': actual == expected,
            'mixing_count': len(files), 'expected_mixing_count': len(expected),
            'missing_mixing_files': sorted(expected - actual), 'unexpected_mixing_files': sorted(actual - expected),
            'mixing_files': rows, 'mixing_contents_hashed': hash_mixing,
            'mixing_manifest_sha256': hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()}


def run_notebook(name, output, env):
    output.mkdir()
    command = [sys.executable, '-u', str(ROOT / 'scripts/execute_notebook_stdlib.py'),
               str(ROOT / 'analysis' / name), str(output / 'executed.ipynb')]
    print('Executing', name, 'log:', output / 'execution.log', flush=True)
    with (output / 'execution.log').open('x') as log:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'{name} failed with exit code {result.returncode}; inspect {output / "execution.log"}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['environment', 'preflight', 'nominal', 'systematics', 'all'])
    parser.add_argument('--paths', type=Path, default=ROOT / 'config/paths.lxplus.json')
    parser.add_argument('--run-dir', type=Path)
    parser.add_argument('--systematics-dir', type=Path)
    parser.add_argument('--mixing-reference', choices=['historical', 'rebuilt-772'], default='rebuilt-772',
                        help='Validation reference. This launcher rebuilds all 772 files; historical uses the older 771-file cache result.')
    parser.add_argument('--hash-mixing', action='store_true', help='Also SHA256 every mixing Coffea input; this reads the complete pool.')
    args = parser.parse_args()
    paths = json.loads(args.paths.read_text())
    parent = ROOT / 'runs'
    parent.mkdir(exist_ok=True)
    if args.run_dir:
        run = args.run_dir.expanduser().resolve()
        for key in ('project_root', 'data_root', 'efficiency_root', 'mixing_root'):
            source = Path(paths[key]).resolve()
            if run == source or source in run.parents:
                raise ValueError('The run directory must be outside all input/source directories')
        run.mkdir(parents=True)
    else:
        run = Path(tempfile.mkdtemp(prefix=datetime.datetime.now().strftime('%Y%m%d_%H%M%S_'), dir=parent))
    print('RUN DIRECTORY:', run, flush=True)
    state = {'stage': args.stage, 'run_dir': str(run), 'paths': paths,
             'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'mixing_reference': args.mixing_reference,
             'completed': False, 'full_slide_27_reproduced': False}
    try:
        env_file = run / 'environment.json'
        code = subprocess.call([sys.executable, str(ROOT / 'scripts/capture_environment.py'), '--output', str(env_file)])
        if code:
            raise RuntimeError('Required imports failed; use the recorded analysis environment. No installation was attempted.')
        if args.stage == 'environment':
            state['completed'] = True
            return 0
        report = preflight(paths, args.hash_mixing)
        (run / 'input_preflight.json').write_text(json.dumps(report, indent=2) + '\n')
        if not report['root_inputs_passed'] or not report['mixing_file_set_passed']:
            raise RuntimeError('Frozen-input preflight failed; inspect input_preflight.json. No notebook was executed.')
        print('Input preflight: PASS (18 ROOT inputs; exact 772-file mixing set)', flush=True)
        if args.stage == 'preflight':
            state['completed'] = True
            return 0
        # Control every notebook override. An unrelated shell's development flags
        # must not silently reduce production replicas or change a shape model.
        child = {k: v for k, v in os.environ.items() if not k.startswith('JPSIDSTAR_')}
        child.update({'MPLBACKEND': 'Agg', 'PYTHONNOUSERSITE': '1',
                      'JPSIDSTAR_PROJECT_DIR': paths['project_root'],
                      'JPSIDSTAR_DATA_DIR': paths['data_root'],
                      'JPSIDSTAR_EFF_DIR': paths['efficiency_root'],
                      'JPSIDSTAR_MIXING_INPUT_DIR': paths['mixing_root'],
                      'JPSIDSTAR_HIGH_STATISTICS_MODE': '1',
                      'JPSIDSTAR_REBUILD_MIXING_CACHE': '1'})
        systematic = (args.systematics_dir or ROOT / 'reference/efficiency_systematics').resolve()
        if args.stage in ('systematics', 'all'):
            systematic = run / 'efficiency_systematics'
            child['JPSIDSTAR_SYSTEMATICS_OUTPUT_DIR'] = str(systematic)
            run_notebook('efficiency_systematics.ipynb', systematic, child)
        if args.stage in ('nominal', 'all'):
            nominal = run / 'nominal'
            child['JPSIDSTAR_EFF_RESPONSE_SYST_DIR'] = str(systematic)
            child['JPSIDSTAR_OUTPUT_ROOT'] = str(nominal)
            run_notebook('nominal.ipynb', nominal, child)
            state['nominal_notebook_completed'] = True
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/validate_reproduction.py'), str(nominal),
                                     '--mixing-reference', args.mixing_reference])
            report_name = 'reproduction_validation_' + args.mixing_reference.replace('-', '_') + '.json'
            validation = json.loads((nominal / report_name).read_text())
            state['validation_report'] = str(nominal / report_name)
            state['numerical_validation_passed'] = validation['current_code_reference_passed']
            state['historical_result_contract_passed'] = validation['historical_result_contract_passed']
            if result.returncode:
                raise RuntimeError('The fresh run differs from the selected ' + args.mixing_reference + ' reference; inspect ' + report_name)
        state['completed'] = True
        return 0
    except Exception as exc:
        state['error'] = f'{type(exc).__name__}: {exc}'
        print(state['error'], file=sys.stderr, flush=True)
        return 1
    finally:
        state['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        (run / 'run_status.json').write_text(json.dumps(state, indent=2) + '\n')
        print('RUN STATUS:', run / 'run_status.json', flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
