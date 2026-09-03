import time
import yaml
import uproot
from hist.intervals import ratio_uncertainty
from scipy.stats import beta
import pathlib
import subprocess

from coffea.nanoevents import BaseSchema

import awkward as ak
import numpy as np
import mplhep as hep
from coffea import processor

from hist import Hist
import hist

from nanoAODplus_processor.EfficiencyProcessor import EfficiencyProcessor
from coffea.nanoevents.methods import candidate
from coffea.util import load as coffea_load
from coffea.util import save as coffea_save
ak.behavior.update(candidate.behavior)

import matplotlib.pyplot as plt
plt.style.use(hep.style.CMS)
from matplotlib.text import Text

from tools.utils import *
from tools.collections import *
from tools.figure import create_plot2d

#python nanoAODplus_efficiency.py -y {year} -p

with open('config/efficiency.yaml', 'r') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

years = ['2016APV', '2016', '2017', '2018']

mc_types = [
    'DPS-ccbar',
    'DPS-bbbar',
    'SPS-ccbar',
    'SPS-bbbar',
]

with open('config/samples.yaml', 'r') as f:
    sample_config = yaml.load(
        f,
        Loader=yaml.FullLoader,
    )['samples']


def get_sample_specs(mc_type, year):
    if mc_type not in sample_config:
        raise ValueError(
            f"Unsupported mc_type={mc_type!r}; "
            f"choose from {sorted(sample_config)}"
        )

    specs = sample_config[mc_type].get(year, [])

    if not specs:
        raise RuntimeError(
            f"No input samples configured for {mc_type}, {year}. "
            "Fill config/samples.yaml before running this production."
        )

    return specs


def discover_xrootd_files(spec):
    """Resolve a Caltech/XRootD sample to an explicit list of ROOT URLs."""
    xrd = spec['xrootd']
    redirector = xrd.get('redirector', 'k8s-redir.ultralight.org:1094')
    base = xrd['base']
    include = [str(item) for item in xrd.get('include', [])]
    exclude_terms = [str(item) for item in xrd.get('exclude', [])]

    cmd = ['xrdfs', redirector, 'ls', '-R', '-u', base]
    print('Discovering remote files with:')
    print('  ' + ' '.join(cmd))

    completed = subprocess.run(
        cmd,
        check=True,
        text=True,
        capture_output=True,
    )

    files = []
    for line in completed.stdout.splitlines():
        path = line.strip()
        if not path.endswith('.root'):
            continue
        if include and not all(token in path for token in include):
            continue
        if exclude_terms and any(token in path for token in exclude_terms):
            continue
        if any(token in pathlib.PurePosixPath(path).name for token in exclude):
            continue
        files.append(path)

    files = sorted(set(files))

    if not files:
        raise RuntimeError(
            'No ROOT files matched XRootD specification: '
            f'redirector={redirector}, base={base}, include={include}, '
            f'exclude={exclude_terms}'
        )

    return files


def resolve_sample_files(spec):
    """Resolve local/EOS paths, explicit filelists, or XRootD discovery specs."""
    source_keys = [key for key in ('path', 'filelist', 'xrootd') if key in spec]
    if len(source_keys) != 1:
        raise ValueError(
            'Each sample specification must define exactly one of '
            "'path', 'filelist', or 'xrootd'."
        )

    source_key = source_keys[0]

    if source_key == 'path':
        path = spec['path']
        recursive = bool(spec.get('recursive', False))

        if not pathlib.Path(path).is_dir():
            raise FileNotFoundError(
                f'Input directory does not exist: {path}'
            )

        file_list = get_files(
            [path],
            exclude=exclude,
            recursive=recursive,
        )
        source = path

    elif source_key == 'filelist':
        filelist = pathlib.Path(spec['filelist'])
        if not filelist.is_file():
            raise FileNotFoundError(
                f'Input file list does not exist: {filelist}'
            )

        file_list = [
            line.strip()
            for line in filelist.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith('#')
        ]
        source = f'filelist:{filelist}'

    else:
        file_list = discover_xrootd_files(spec)
        xrd = spec['xrootd']
        source = (
            f"xrootd:{xrd.get('redirector', 'k8s-redir.ultralight.org:1094')}"
            f":{xrd['base']}"
        )

    if not file_list:
        raise RuntimeError(f'No ROOT files found for {source}')

    return source, file_list


def write_input_manifest(mc_type, year, samples):
    manifest_dir = pathlib.Path('output/efficiency/input_manifests')
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = manifest_dir / f'{mc_type}_{year}.txt'

    lines = []
    for source, sample_cut, file_list in samples:
        lines.append(f'# source={source} dimu_cut={sample_cut:g}')
        lines.extend(file_list)

    manifest.write_text('\n'.join(lines) + '\n')
    print(f'Input manifest written to: {manifest}')
    return manifest


exclude = [
    'DPS_D0ToKPi_JPsiPt-50To100_JPsiFilter_TuneCP5_13TeV-pythia8-evtgenRunIISummer20UL16RECO_41.root',
    'Jpsi_25to100_Dstar_SPS_bbbar_3FS_2017_13TeV_NanoAODPlus_1037.root',
]



def weighted_efficiency_statistics(
    hist_num,
    hist_den,
    coverage=0.682689492137,
):
    """
    Weighted efficiency and effective-statistics Clopper-Pearson interval.

    N_eff = (sum w)^2 / sum(w^2)

    The central efficiency remains sumw_num / sumw_den.
    """
    num = np.asarray(hist_num.values(flow=False), dtype=float)
    den = np.asarray(hist_den.values(flow=False), dtype=float)

    num_sumw2 = np.asarray(hist_num.variances(flow=False), dtype=float)
    den_sumw2 = np.asarray(hist_den.variances(flow=False), dtype=float)

    valid = (
        np.isfinite(num)
        & np.isfinite(den)
        & np.isfinite(num_sumw2)
        & np.isfinite(den_sumw2)
        & (den > 0.0)
        & (den_sumw2 > 0.0)
    )

    tolerance = 1.0e-10 * np.maximum(1.0, np.abs(den))
    inconsistent = valid & (
        (num < -tolerance)
        | (num > den + tolerance)
        | (num_sumw2 < 0.0)
        | (den_sumw2 < 0.0)
    )

    if np.any(inconsistent):
        indices = np.argwhere(inconsistent)
        raise RuntimeError(
            "Weighted numerator/denominator inconsistency in bins: "
            f"{indices.tolist()}"
        )

    num_clipped = np.minimum(np.maximum(num, 0.0), den)

    efficiency = np.full_like(den, np.nan)
    n_eff = np.full_like(den, np.nan)
    err_down = np.full_like(den, np.nan)
    err_up = np.full_like(den, np.nan)

    efficiency[valid] = num_clipped[valid] / den[valid]
    n_eff[valid] = den[valid] ** 2 / den_sumw2[valid]

    k_eff = np.full_like(den, np.nan)
    k_eff[valid] = efficiency[valid] * n_eff[valid]
    k_eff[valid] = np.minimum(
        np.maximum(k_eff[valid], 0.0),
        n_eff[valid],
    )

    alpha = 1.0 - coverage

    lower = np.zeros_like(den)
    upper = np.ones_like(den)

    has_pass = valid & (k_eff > 0.0)
    lower[has_pass] = beta.ppf(
        alpha / 2.0,
        k_eff[has_pass],
        n_eff[has_pass] - k_eff[has_pass] + 1.0,
    )

    has_fail = valid & (k_eff < n_eff)
    upper[has_fail] = beta.ppf(
        1.0 - alpha / 2.0,
        k_eff[has_fail] + 1.0,
        n_eff[has_fail] - k_eff[has_fail],
    )

    err_down[valid] = efficiency[valid] - lower[valid]
    err_up[valid] = upper[valid] - efficiency[valid]

    return {
        "efficiency": efficiency,
        "err_up": err_up,
        "err_down": err_down,
        "n_eff": n_eff,
        "num_sumw": num,
        "num_sumw2": num_sumw2,
        "den_sumw": den,
        "den_sumw2": den_sumw2,
    }

def weighted_ratio_statistics(hist_num, hist_den):
    """
    Ratio of two weighted histograms using first-order error propagation.

    Appropriate for response/correction ratios where numerator and
    denominator are not a strict binomial pass/total pair.

    The covariance is not available from the marginal histograms and is
    therefore omitted. This gives a conservative statistical estimate
    when numerator and denominator are positively correlated.
    """
    num = np.asarray(hist_num.values(flow=False), dtype=float)
    den = np.asarray(hist_den.values(flow=False), dtype=float)

    num_sumw2 = np.asarray(
        hist_num.variances(flow=False),
        dtype=float,
    )
    den_sumw2 = np.asarray(
        hist_den.variances(flow=False),
        dtype=float,
    )

    valid = (
        np.isfinite(num)
        & np.isfinite(den)
        & np.isfinite(num_sumw2)
        & np.isfinite(den_sumw2)
        & (den > 0.0)
        & (num_sumw2 >= 0.0)
        & (den_sumw2 > 0.0)
    )

    ratio = np.full_like(den, np.nan)
    variance = np.full_like(den, np.nan)
    n_eff = np.full_like(den, np.nan)

    ratio[valid] = num[valid] / den[valid]

    variance[valid] = (
        num_sumw2[valid] / den[valid]**2
        +
        num[valid]**2
        * den_sumw2[valid]
        / den[valid]**4
    )

    variance[valid] = np.maximum(
        variance[valid],
        0.0,
    )

    error = np.full_like(den, np.nan)
    error[valid] = np.sqrt(variance[valid])

    n_eff[valid] = (
        den[valid]**2
        / den_sumw2[valid]
    )

    return {
        "efficiency": ratio,
        "err_up": error,
        "err_down": error,
        "n_eff": n_eff,
        "num_sumw": num,
        "num_sumw2": num_sumw2,
        "den_sumw": den,
        "den_sumw2": den_sumw2,
    }

def create_eff_hists2D(
    hist_num,
    hist_den,
    bins,
    names,
    hist_labels,
    statistics="efficiency",
):
    eff_hist = (
        Hist.new
        .Variable(
            bins[0],
            name=names[0],
            label=hist_labels[0],
        )
        .Variable(
            bins[1],
            name=names[1],
            label=hist_labels[1],
        )
        .Double()
    )

    if statistics == "efficiency":
        stats = weighted_efficiency_statistics(
            hist_num,
            hist_den,
        )

    elif statistics == "ratio":
        stats = weighted_ratio_statistics(
            hist_num,
            hist_den,
        )

    else:
        raise ValueError(
            f"Unknown statistics mode: {statistics}"
        )

    values = stats["efficiency"]
    err_up = stats["err_up"]
    err_down = stats["err_down"]

    eff_hist[...] = values

    return eff_hist, err_up, err_down

def create_eff_plot2D(hist_eff, err_up, err_down, savename, year, with_labels=True, **kwargs):
    fig, ax = plt.subplots()

    if with_labels:
        eff = ak.flatten(hist_eff.values())
        eff_err_up = ak.flatten(err_up)
        eff_err_down = ak.flatten(err_down)
        n = [len(i.centers) for i in hist_eff.axes]

        labels = []
        for ra, u, d in zip(eff, eff_err_up, eff_err_down):
            ra, u, d = f'{ra:.2f}', f'{u:.2f}', f'{d:.2f}'
            st = '$'+ra+'_{-'+d+'}^{+'+u+'}$'
            labels.append(st)
        labels = np.array(labels).reshape(*n)

        artists = hep.hist2dplot(hist_eff, labels=labels, ax=ax, **kwargs)
        x = ax.get_children()
        for i0 in x:
            if isinstance(i0, Text):
                i0.set_size(11)
                i0.set_rotation(270)
        
        """ if ('dimu' in file_eff) or ('asso' in file_eff):
            ticks, labels = plt.xticks()
            for idx, i in enumerate(ticks):
                if i == 20.:
                    labels[idx] = None
            
            ax.set_xticklabels(labels) """
            #ax.set_xscale('log')
                
    else:
        artists = hep.hist2dplot(hist_eff, ax=ax, **kwargs)

    hep.cms.text('Simulation', loc=0)
    year_text = plt.text(1., 1., f"{year} (13 TeV)",
                    fontsize=18,
                    horizontalalignment='right',
                    verticalalignment='bottom',
                    transform=ax.transAxes
                    )
    fig.savefig(f'plots/efficiency/{savename}')
    plt.close()


def create_eff_plot1D(hist_num, hist_den, bins, names, hist_labels, savename, ylim=(0, 1.2), **kwargs):
    eff_hist = Hist.new.Variable(bins, name=names, label=hist_labels).Weight()
    
    num = hist_num.values()
    den = hist_den.values()

    values = np.where(
        (num > 0) & (den > 0),
        num/den,
        1.0,    
    )
    err_up, err_down = np.where(
        (den > 0),
        ratio_uncertainty(num, den, uncertainty_type='efficiency'),
        0.0
    )
    err = np.where((err_up > err_down), err_up, err_down)

    #eff_hist[...] = values
    eff_hist[...] = np.stack([values, err**2], axis=-1)

    fig, ax = plt.subplots()
    artists = hep.histplot(eff_hist, ax=ax, histtype='errorbar', xerr=True, **kwargs)
    ax.set_ylim(*ylim)
    plt.axhline(1.0, linestyle='--')
    hep.cms.text('Simulation', loc=0)
    year_text = plt.text(1., 1., f"{year} (13 TeV)",
                    fontsize=18,
                    horizontalalignment='right',
                    verticalalignment='bottom',
                    transform=ax.transAxes
                    )
    
    fig.savefig(f'plots/efficiency/{savename}')
    plt.close()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description="Create efficiency plots"
    )

    parser.add_argument(
        "-y",
        "--year",
        help="Year to create efficiency",
        type=str,
        required=True,
        choices=years,
    )

    parser.add_argument(
        "-m",
        "--mc-type",
        dest="mc_type",
        choices=mc_types,
        default=config.get("mc_type", "DPS-ccbar"),
        help="MC component. CLI value overrides config/efficiency.yaml.",
    )

    parser.add_argument(
        "-p",
        "--plot",
        help="Plot efficiency",
        action="store_true",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Number of futures workers",
    )

    parser.add_argument(
        "--from-cache",
        action="store_true",
        help="Skip NanoAOD processing and load the merged histogram cache.",
    )

    parser.add_argument(
        "--list-inputs",
        action="store_true",
        help="Resolve configured inputs, write the manifest, print them, and exit.",
    )

    args = parser.parse_args()

    year = args.year
    mc_type = args.mc_type

    # Keep the existing output-name machinery unchanged.
    config["mc_type"] = mc_type

    cache_dir = pathlib.Path("output/efficiency/cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    cache_file = (
        cache_dir
        / f"{mc_type}_{year}_merged.coffea"
    )

    if args.from_cache:

        if not cache_file.exists():
            raise FileNotFoundError(
                f"Cache not found: {cache_file}"
            )

        print(f"Loading merged histograms from: {cache_file}")
        hists = coffea_load(str(cache_file))

    else:

        specs = get_sample_specs(mc_type, year)

        samples = []

        for spec in specs:

            sample_cut = float(
                spec.get(
                    "dimu_cut",
                    config["dimu_pt_min"],
                )
            )

            source, file_list = resolve_sample_files(spec)

            samples.append(
                (source, sample_cut, file_list)
            )

        print(f"MC component: {mc_type}")
        print(f"Year: {year}")

        for source, sample_cut, file_list in samples:
            print(
                f"  {len(file_list):4d} ROOT files | "
                f"dimu_cut={sample_cut:g} GeV | "
                f"{source}"
            )

        manifest = write_input_manifest(mc_type, year, samples)

        if args.list_inputs:
            print(manifest.read_text())
            raise SystemExit(0)

        output = []
        tstart = time.time()

        for source, sample_cut, file_list in samples:

            data = {
                "test": file_list[:]
            }

            print(file_list[0])

            print(
                "Treating sample with generated "
                f"J/psi pT > {sample_cut:g} GeV"
            )

            output.append(
                processor.run_uproot_job(
                    data,
                    treename="Events",
                    processor_instance=EfficiencyProcessor(
                        dimu_cut=sample_cut,
                        year=year,
                        config=config,
                    ),
                    executor=processor.futures_executor,
                    executor_args={
                        "schema": BaseSchema,
                        "workers": args.workers,
                        "skipbadfiles": False,
                    },
                    chunksize=360000,
                )
            )

        print(
            f"Process finished in: "
            f"{time.time() - tstart:.2f} s"
        )

        # Merge the hists
        hists = {}

        keys_to_merge = [
            'Gen_Dimu',
            'Reco_Dimu',
            'Gen_Dstar',
            'Reco_Dstar',
            'Cuts_Dimu',
            'Cuts_Dstar',
            'Trigger_Dimu',
            'Num_Asso',
            'Den_Asso',
        ]

        nevt = 0

        for out in output:
            nevt += out['cutflow']['Number of events']

            for key in keys_to_merge:
                if key not in hists:
                    hists[key] = out[key].copy()
                else:
                    hists[key] += out[key]

        print(f"Number of events: {nevt}")

        print(f"Saving merged histogram cache to: {cache_file}")
        coffea_save(hists, str(cache_file))

    acc_dimu_hist, acc_dimu_err_up, acc_dimu_err_down = create_eff_hists2D(
        hists['Reco_Dimu'],
        hists['Gen_Dimu'],
        (config['bins_pt_dimu'], config['bins_rap_dimu']),
        ('pt', 'rap'),
        (r'$p_{T, \mu^+\mu^-} [GeV/c]$', r'$|y_{\mu^+\mu^-}|$'),
        statistics="ratio",
    )

    acc_dstar_hist, acc_dstar_err_up, acc_dstar_err_down = create_eff_hists2D(
        hists['Reco_Dstar'],
        hists['Gen_Dstar'],
        (config['bins_pt_dstar'], config['bins_rap_dstar']),
        ('pt', 'rap'),
        (r'$p_{T, D^*}$ [GeV/c]', r'$|y_{D^*}|$'),
        statistics="ratio",
    )

    eff_cuts_dimu_hist, eff_cuts_dimu_err_up, eff_cuts_dimu_err_down = create_eff_hists2D(
        hists['Cuts_Dimu'],
        hists['Reco_Dimu'],
        (config['bins_pt_dimu'], config['bins_rap_dimu']),
        ('pt', 'rap'),
        (r'$p_{T, \mu^+\mu^-}$ [GeV/c]', r'$|y_{\mu^+\mu^-}|$'),
        statistics="efficiency",
    )

    eff_cuts_dstar_hist, eff_cuts_dstar_err_up, eff_cuts_dstar_err_down = create_eff_hists2D(
        hists['Cuts_Dstar'],
        hists['Reco_Dstar'],
        (config['bins_pt_dstar'], config['bins_rap_dstar']),
        ('pt', 'rap'),
        (r'$p_{T, D^*}$ [GeV/c]', r'$|y_{D^*}|$'),
        statistics="efficiency",
    )

    eff_trigger_hist, eff_trigger_err_up, eff_trigger_err_down = create_eff_hists2D(
        hists['Trigger_Dimu'],
        hists['Cuts_Dimu'],
        (config['bins_pt_dimu'], config['bins_rap_dimu']),
        ('pt', 'rap'),
        (r'$p_{T, \mu^+\mu^-}$ [GeV/c]', r'$|y_{\mu^+\mu^-}|$'),
        statistics="efficiency",
    )

    eff_asso_pt_hist, eff_asso_pt_err_up, eff_asso_pt_err_down = create_eff_hists2D(
        hists['Num_Asso'].project('pt_dimu', 'pt_dstar'),
        hists['Den_Asso'].project('pt_dimu', 'pt_dstar'),
        (config['bins_pt_dimu'], config['bins_pt_dstar']),
        ('pt_dimu', 'pt_dstar'),
        (r'$p_{T, \mu^+\mu^-}$ [GeV/c]', r'$p_{T, D^*}$ [GeV/c]'),
        statistics="efficiency",
    )

    eff_asso_rap_hist, eff_asso_rap_err_up, eff_asso_rap_err_down = create_eff_hists2D(
        hists['Num_Asso'].project('rap_dimu', 'rap_dstar'),
        hists['Den_Asso'].project('rap_dimu', 'rap_dstar'),
        (config['bins_rap_dimu'], config['bins_rap_dstar']),
        ('rap_dimu', 'rap_dstar'),
        (r'$|y_{\mu^+\mu^-}|$', r'$|y_{D^*}|$'),
        statistics="efficiency",
    )

    # Save files to root
    pathlib.Path('output/efficiency').mkdir(parents=True, exist_ok=True)
    eff_file = uproot.recreate(
        f'output/efficiency/efficiencies_{config["mc_type"]}_{config["out_name"]}_{config["category"]}_{year}.root'
    )

    efficiency_payload = {
        'acc_dimu': (
            acc_dimu_hist,
            acc_dimu_err_up,
            acc_dimu_err_down,
            hists['Reco_Dimu'],
            hists['Gen_Dimu'],
            'ratio',
        ),
        'acc_dstar': (
            acc_dstar_hist,
            acc_dstar_err_up,
            acc_dstar_err_down,
            hists['Reco_Dstar'],
            hists['Gen_Dstar'],
            'ratio',
        ),
        'eff_cuts_dimu': (
            eff_cuts_dimu_hist,
            eff_cuts_dimu_err_up,
            eff_cuts_dimu_err_down,
            hists['Cuts_Dimu'],
            hists['Reco_Dimu'],
            'efficiency',
        ),
        'eff_cuts_dstar': (
            eff_cuts_dstar_hist,
            eff_cuts_dstar_err_up,
            eff_cuts_dstar_err_down,
            hists['Cuts_Dstar'],
            hists['Reco_Dstar'],
            'efficiency',
        ),
        'eff_trigger': (
            eff_trigger_hist,
            eff_trigger_err_up,
            eff_trigger_err_down,
            hists['Trigger_Dimu'],
            hists['Cuts_Dimu'],
            'efficiency',
        ),
        'eff_asso_pt': (
            eff_asso_pt_hist,
            eff_asso_pt_err_up,
            eff_asso_pt_err_down,
            hists['Num_Asso'].project('pt_dimu', 'pt_dstar'),
            hists['Den_Asso'].project('pt_dimu', 'pt_dstar'),
            'efficiency',
        ),
        'eff_asso_rap': (
            eff_asso_rap_hist,
            eff_asso_rap_err_up,
            eff_asso_rap_err_down,
            hists['Num_Asso'].project('rap_dimu', 'rap_dstar'),
            hists['Den_Asso'].project('rap_dimu', 'rap_dstar'),
            'efficiency',
        ),
    }

    def histogram_from_array(template, values):
        result = template.copy()
        result[...] = np.asarray(values, dtype=float)
        return result

    for key, (
        nominal,
        err_up,
        err_down,
        hist_num,
        hist_den,
        statistics_mode,
    ) in efficiency_payload.items():

        if statistics_mode == "efficiency":
            stats = weighted_efficiency_statistics(
                hist_num,
                hist_den,
            )
        elif statistics_mode == "ratio":
            stats = weighted_ratio_statistics(
                hist_num,
                hist_den,
            )
        else:
            raise RuntimeError(
                f"Unsupported statistics mode: {statistics_mode}"
            )

        eff_file[key] = nominal

        err_up_hist = histogram_from_array(
            nominal,
            err_up,
        )
        err_down_hist = histogram_from_array(
            nominal,
            err_down,
        )

        n_eff_hist = histogram_from_array(
            nominal,
            stats["n_eff"],
        )

        num_sumw_hist = histogram_from_array(
            nominal,
            stats["num_sumw"],
        )
        num_sumw2_hist = histogram_from_array(
            nominal,
            stats["num_sumw2"],
        )
        den_sumw_hist = histogram_from_array(
            nominal,
            stats["den_sumw"],
        )
        den_sumw2_hist = histogram_from_array(
            nominal,
            stats["den_sumw2"],
        )

        # Canonical uncertainty objects.
        eff_file[f'{key}_err_up'] = err_up_hist
        eff_file[f'{key}_err_down'] = err_down_hist

        # Explicit aliases for downstream auditing.
        eff_file[f'{key}_err_up_weighted'] = err_up_hist
        eff_file[f'{key}_err_down_weighted'] = err_down_hist
        eff_file[f'{key}_n_eff'] = n_eff_hist

        # Raw weighted sums required to reproduce the intervals.
        eff_file[f'raw/{key}_num_sumw'] = num_sumw_hist
        eff_file[f'raw/{key}_num_sumw2'] = num_sumw2_hist
        eff_file[f'raw/{key}_den_sumw'] = den_sumw_hist
        eff_file[f'raw/{key}_den_sumw2'] = den_sumw2_hist

    eff_file.close()

    if args.plot:
        pathlib.Path('plots/efficiency').mkdir(
            parents=True,
            exist_ok=True,
        )

        create_eff_plot2D(
            acc_dimu_hist,
            acc_dimu_err_up,
            acc_dimu_err_down,
            f'acc_dimu_{config["mc_type"]}_{year}.png',
            year,
        )

        create_eff_plot2D(
            acc_dstar_hist,
            acc_dstar_err_up,
            acc_dstar_err_down,
            f'acc_dstar_{config["mc_type"]}_{year}.png',
            year,
        )

        create_eff_plot2D(
            eff_cuts_dimu_hist,
            eff_cuts_dimu_err_up,
            eff_cuts_dimu_err_down,
            f'eff_cuts_dimu_{config["mc_type"]}_{year}.png',
            year,
        )

        create_eff_plot2D(
            eff_cuts_dstar_hist,
            eff_cuts_dstar_err_up,
            eff_cuts_dstar_err_down,
            f'eff_cuts_dstar_{config["mc_type"]}_{year}.png',
            year,
        )

        create_eff_plot2D(
            eff_trigger_hist,
            eff_trigger_err_up,
            eff_trigger_err_down,
            f'eff_trigger_{config["mc_type"]}_{year}.png',
            year,
        )

        create_eff_plot2D(
            eff_asso_pt_hist,
            eff_asso_pt_err_up,
            eff_asso_pt_err_down,
            f'eff_asso_pt_{config["mc_type"]}_{year}.png',
            year,
        )

        create_eff_plot2D(
            eff_asso_rap_hist,
            eff_asso_rap_err_up,
            eff_asso_rap_err_down,
            f'eff_asso_rap_{config["mc_type"]}_{year}.png',
            year,
        )

    print("Output written successfully.")
