#!/usr/bin/env python3
"""Compare saved results with an explicit mixing-input reference; no physics rerun."""
import argparse
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def number_check(item, value, reference, tolerance):
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = math.nan
    reference = float(reference)
    return {'item': item, 'value': value if math.isfinite(value) else None,
            'reference': reference, 'absolute_tolerance': tolerance,
            'passed': math.isfinite(value) and abs(value - reference) <= tolerance}


def snapshot_checks(observed, expected, dd):
    # Preserve the original numerical tolerances for both input references.
    tolerances = {'fDPS': 2e-5, 'stat_down': 1e-4, 'stat_up': 1e-4,
                  'total_down': 1e-4, 'total_up': 1e-4,
                  'data_driven_fDPS': 5e-4, 'data_driven_total_sigma': 1e-3,
                  'gof_toy_pvalue': 3 * expected['gof_pvalue_mcse']}
    checks = [number_check(field, observed[field], expected[field], tolerance)
              for field, tolerance in tolerances.items()]
    for field in ('high_statistics_mode', 'actual_fit_grid', 'number_fit_parameters',
                  'gof_toys_requested', 'gof_toys_successful'):
        checks.append({'item': field, 'value': observed[field], 'reference': expected[field],
                       'passed': observed[field] == expected[field]})
    for field in ('sigma_eff_mb', 'sigma_eff_total_error_down_mb', 'sigma_eff_total_error_up_mb'):
        checks.append(number_check('template_based_' + field, observed['sigma_eff'][field],
                                   expected['sigma_eff'][field], 2e-3))
    for field, reference in [('region_dy_min', 2.2), ('region_dphi_min', 0.0), ('region_dphi_max', 1.0)]:
        checks.append(number_check(field, dd[field], reference, 1e-9))
    return checks


def read_summary(path):
    with path.open() as handle:
        rows = list(csv.DictReader(handle))
    summary = {row['quantity']: row['value'] for row in rows}
    if len(summary) != len(rows):
        raise ValueError('Duplicate quantities in mixed_template_summary.csv')
    return summary


def summary_checks(summary, expected):
    checks = []
    for quantity, reference in expected.items():
        value = summary.get(quantity)
        if isinstance(reference, str):
            checks.append({'item': quantity, 'value': value, 'reference': reference,
                           'passed': value == reference})
        else:
            checks.append(number_check(quantity, value, reference, 0))
    return checks


def selected_region(run_dir):
    with (run_dir / 'data_driven_region_scan.csv').open() as handle:
        matches = [row for row in csv.DictReader(handle)
                   if abs(float(row['dy_min']) - 2.2) < 1e-8
                   and abs(float(row['dphi_min'])) < 1e-8
                   and abs(float(row['dphi_max']) - 1.0) < 1e-8]
    if len(matches) != 1:
        raise ValueError('Expected exactly one nominal region in the saved DD scan')
    return matches[0]


def region_checks(region, expected):
    return [number_check('DD region: ' + field, region[field], reference, 1e-8)
            for field, reference in expected.items()]


def validate(run_dir, mixing_reference='historical'):
    run_dir = Path(run_dir)
    contracts = json.loads((ROOT / 'reference/mixing_reproduction_contracts.json').read_text())
    if mixing_reference not in ('historical', 'rebuilt-772'):
        raise ValueError('Unknown mixing reference: ' + mixing_reference)
    contract = contracts[mixing_reference]
    historical = contracts['historical']
    name = 'FINAL_NOMINAL_HIST_analysis_status.json'
    observed = json.loads((run_dir / name).read_text())
    expected_historical = json.loads((ROOT / 'reference/current_results' / name).read_text())
    with (run_dir / 'final_fdps_results_FINAL.csv').open() as handle:
        dd = next(row for row in csv.DictReader(handle) if row['role'] == 'cross-check')

    historical_checks = snapshot_checks(observed, expected_historical, dd)
    expected = dict(expected_historical)
    # Only the two DD reference values differ; common template/GOF/sigma_eff
    # expectations remain the collected historical values.
    expected.update({field: contract[field]
                     for field in ('data_driven_fDPS', 'data_driven_total_sigma')})
    checks = snapshot_checks(observed, expected, dd)
    summary = read_summary(run_dir / 'mixed_template_summary.csv')
    input_checks = summary_checks(summary, contract['summary'])
    region = selected_region(run_dir)
    regional_checks = region_checks(region, contract['region'])
    qdata, qmixed, purity = (float(region[key]) for key in
                             ('data_region_fraction', 'mixed_region_fraction', 'purity'))
    if not all(math.isfinite(x) for x in (qdata, qmixed, purity)) or qmixed <= 0:
        raise ValueError('Invalid saved data-driven regional normalization')
    predicted = qdata * purity / qmixed
    regional_checks.append(number_check('DD normalization identity', observed['data_driven_fDPS'],
                                       predicted, 1e-10))
    regional_checks.append(number_check('DD output/scan identity', observed['data_driven_fDPS'],
                                       region['f_before_closure'], 1e-10))

    selected_passed = all(c['passed'] for c in checks + input_checks + regional_checks)
    numerical_historical_passed = all(c['passed'] for c in historical_checks)
    historical_input_checks = summary_checks(summary, historical['summary'])
    historical_region_checks = region_checks(region, historical['region'])
    return {
        'mixing_reference': mixing_reference,
        'reference_description': contract['description'],
        'reference_evidence': contract['evidence'],
        'current_code_reference_passed': selected_passed,
        'historical_numerical_reference_passed': numerical_historical_passed,
        'historical_input_summary_passed': all(c['passed'] for c in historical_input_checks),
        'historical_result_contract_passed': all(c['passed'] for c in
            historical_checks + historical_input_checks + historical_region_checks),
        'checks': checks,
        'mixing_input_checks': input_checks,
        'dd_region_checks': regional_checks,
        'historical_comparison_checks': historical_checks,
        'mixing_shift': {
            'historical_files_loaded': historical['summary']['Mixing files loaded'],
            'observed_files_loaded': summary.get('Mixing files loaded'),
            'historical_mixed_region_fraction': historical['region']['mixed_region_fraction'],
            'observed_mixed_region_fraction': qmixed,
            'historical_data_driven_fDPS': historical['data_driven_fDPS'],
            'observed_data_driven_fDPS': observed['data_driven_fDPS'],
            'difference_percentage_points': 100 * (observed['data_driven_fDPS'] - historical['data_driven_fDPS']),
            'normalization_identity_fDPS': predicted,
        },
        'full_slide_27_reproduced': False,
        'unresolved': [
            'Historical template/data-driven combination formula and covariance are not present in the collected code.',
            'The collected code computes sigma_eff from template fDPS; the slide uses combined fDPS.',
            'The identity of the one failed historical mixing input and the historical cache hash are not recorded.',
        ],
        'publication_reportability': observed.get('reportability_status'),
        'meaning': ('A pass uses the explicitly selected mixing-input reference. The historical result and '
                    'its comparison are preserved. Comparing saved results with a baseline established '
                    'from this same run does not constitute a second independent rebuild or resolve pending physics inputs.'),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir', type=Path)
    parser.add_argument('--mixing-reference', choices=['historical', 'rebuilt-772'], default='historical')
    args = parser.parse_args()
    result = validate(args.run_dir, args.mixing_reference)
    # Preserve the original reproduction_validation.json from the first attempt.
    suffix = args.mixing_reference.replace('-', '_')
    output = args.run_dir / ('reproduction_validation_' + suffix + '.json')
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print('Selected mixing reference:', args.mixing_reference)
    print('Selected-reference validation:', 'PASS' if result['current_code_reference_passed'] else 'FAIL')
    print('Historical numerical reference:', 'PASS' if result['historical_numerical_reference_passed'] else 'DIFFERS')
    print('Historical result contract:', 'PASS' if result['historical_result_contract_passed'] else 'NOT REPRODUCED')
    print('Full final-slide reproduction: PENDING combination provenance')
    print(output)
    return 0 if result['current_code_reference_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
