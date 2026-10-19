#!/usr/bin/env python3
"""Restore the active mixing-production inputs without submitting jobs."""
import argparse
import gzip
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path, help='A new local job directory')
    parser.add_argument('--eos-output-root', required=True, help='A new EOS output base; the frozen source pool is forbidden')
    parser.add_argument('--proxy', type=Path, required=True, help='Existing valid X.509 proxy path; its contents are never copied')
    args = parser.parse_args()
    output = args.eos_output_root.rstrip('/')
    frozen = json.loads((ROOT / 'config/paths.lxplus.json').read_text())['mixing_root']
    if not re.fullmatch(r'/eos/[A-Za-z0-9_./-]+', output):
        raise ValueError('Expected a plain absolute /eos/ path')
    # Both spellings address the same EOS home. Reject either frozen spelling.
    normalized = output.replace('/eos/home-j/jgomespi/', '/eos/user/j/jgomespi/')
    original = frozen.replace('/eos/home-j/jgomespi/', '/eos/user/j/jgomespi/')
    if normalized == original or normalized.startswith(original + '/'):
        raise ValueError('Use a new output root outside the frozen mixing pool')
    if not args.proxy.is_file():
        raise FileNotFoundError('The supplied proxy path is not an existing file')
    target = args.directory.expanduser().resolve()
    target.mkdir(parents=True)
    (target / 'filelists').mkdir()
    (target / 'logs').mkdir()
    with gzip.open(ROOT / 'reference/mixing_inputs.json.gz', 'rt') as handle:
        payload = json.load(handle)
    queue = []
    names = set()
    for job in payload['jobs']:
        basename = job['filelist_basename']
        if basename in names or Path(basename).name != basename:
            raise ValueError('Invalid or duplicate filelist basename')
        names.add(basename)
        (target / 'filelists' / basename).write_text('\n'.join(job['input_urls']) + '\n')
        queue.append(' '.join([job['tag'], 'filelists/' + basename, basename, job['output_subdir']]))
    (target / 'queue_Run2_100files.txt').write_text('\n'.join(queue) + '\n')
    shutil.copy2(ROOT / 'preparation/prepare_mixing.py', target / 'prepare_mixing.py')
    wrapper = (ROOT / 'preparation/run_prepare_mixing.sh').read_text()
    old = 'EOS_OUTPATH="/eos/user/j/jgomespi/SWAN_projects/Associated_Production_JPsi_Dstar/condor_data_preparation/output_noHLT_preassoc_v1/${OUTSUBDIR}"'
    if wrapper.count(old) != 1:
        raise RuntimeError('Unexpected original wrapper output anchor')
    (target / 'run_prepare_mixing.sh').write_text(wrapper.replace(old, 'EOS_OUTPATH="' + output + '/${OUTSUBDIR}"'))
    (target / 'run_prepare_mixing.sh').chmod(0o700)
    submit = (ROOT / 'preparation/submit_noHLT_preassoc_Run2.sub').read_text()
    proxy = str(args.proxy.resolve())
    if not re.fullmatch(r'/[A-Za-z0-9_./-]+', proxy):
        raise ValueError('Proxy path must not contain whitespace or submit-file syntax')
    submit = re.sub(r'^x509userproxy\s*=.*$', 'x509userproxy = ' + proxy, submit, flags=re.M)
    (target / 'submit_noHLT_preassoc_Run2.sub').write_text(submit)
    print('Prepared', len(queue), 'jobs in', target)
    print('Known bad input URLs excluded:', len(payload['known_bad_input_urls']))
    print('No jobs were submitted. The packed runtime remains an external CERN input.')


if __name__ == '__main__':
    main()
