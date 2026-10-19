#!/usr/bin/env python3
"""Compare a fresh nominal run with the collected lxplus result."""
import argparse
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate(run_dir):
    name = 'FINAL_NOMINAL_HIST_analysis_status.json'
    observed = json.loads((run_dir / name).read_text())
    expected = json.loads((ROOT / 'reference/current_results' / name).read_text())
    checks = []
    tolerances = {'fDPS': 2e-5, 'stat_down': 1e-4, 'stat_up': 1e-4,
                  'total_down': 1e-4, 'total_up': 1e-4,
                  'data_driven_fDPS': 5e-4, 'data_driven_total_sigma': 1e-3,
                  'gof_toy_pvalue': 3 * expected['gof_pvalue_mcse']}
    for field, tolerance in tolerances.items():
        value, reference = float(observed[field]), float(expected[field])
        checks.append({'item': field, 'value': value, 'reference': reference,
                       'absolute_tolerance': tolerance,
                       'passed': math.isfinite(value) and abs(value - reference) <= tolerance})
    for field in ('high_statistics_mode', 'actual_fit_grid', 'number_fit_parameters',
                  'gof_toys_requested', 'gof_toys_successful'):
        checks.append({'item': field, 'value': observed[field], 'reference': expected[field],
                       'passed': observed[field] == expected[field]})
    for field in ('sigma_eff_mb', 'sigma_eff_total_error_down_mb', 'sigma_eff_total_error_up_mb'):
        value, reference = observed['sigma_eff'][field], expected['sigma_eff'][field]
        checks.append({'item': 'template_based_' + field, 'value': value, 'reference': reference,
                       'absolute_tolerance': 2e-3, 'passed': abs(value - reference) <= 2e-3})
    with (run_dir / 'final_fdps_results_FINAL.csv').open() as handle:
        rows = list(csv.DictReader(handle))
    dd = next(row for row in rows if row['role'] == 'cross-check')
    for field, reference in [('region_dy_min', 2.2), ('region_dphi_min', 0.0), ('region_dphi_max', 1.0)]:
        value = float(dd[field])
        checks.append({'item': field, 'value': value, 'reference': reference,
                       'passed': abs(value - reference) < 1e-9})
    return {'current_code_reference_passed': all(c['passed'] for c in checks),
            'checks': checks, 'full_slide_27_reproduced': False,
            'unresolved': ['Historical template/data-driven combination formula and covariance are not present in the collected code.',
                           'The collected code computes sigma_eff from template fDPS; the slide uses combined fDPS.'],
            'publication_reportability': observed.get('reportability_status'),
            'meaning': 'A computational reproduction pass does not resolve pending physics inputs or establish the slide combination.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir', type=Path)
    args = parser.parse_args()
    result = validate(args.run_dir)
    output = args.run_dir / 'reproduction_validation.json'
    output.write_text(json.dumps(result, indent=2) + '\n')
    print('Current-code numerical reference:', 'PASS' if result['current_code_reference_passed'] else 'FAIL')
    print('Full final-slide reproduction: PENDING combination provenance')
    print(output)
    return 0 if result['current_code_reference_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
