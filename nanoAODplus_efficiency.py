import time
import yaml
import uproot
from hist.intervals import ratio_uncertainty
from scipy.stats import beta
import pathlib

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

            path = spec["path"]

            sample_cut = float(
                spec.get(
                    "dimu_cut",
                    config["dimu_pt_min"],
                )
            )

            recursive = bool(
                spec.get("recursive", False)
            )

            if not pathlib.Path(path).is_dir():
                raise FileNotFoundError(
                    f"Input directory does not exist: {path}"
                )

            file_list = get_files(
                [path],
                exclude=exclude,
                recursive=recursive,
            )

            if not file_list:
                raise RuntimeError(
                    f"No non-empty ROOT files found in: {path}"
                )

            samples.append(
                (path, sample_cut, file_list)
            )

        print(f"MC component: {mc_type}")
        print(f"Year: {year}")

        for path, sample_cut, file_list in samples:
            print(
                f"  {len(file_list):4d} ROOT files | "
                f"dimu_cut={sample_cut:g} GeV | "
                f"{path}"
            )

        output = []
        tstart = time.time()

        for path, sample_cut, file_list in samples:

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
                        "skipbadfiles": True,
                    },
                    chunksize=360000,
                )
            )

        print(
            f"Process finished in: "
            f"{time.time() - tstart:.2f} s"
        )

        nevt = 0

        for out in output:
            nevt += out["cutflow"]["Number of events"]

        print(f"Number of events: {nevt}")

        hists = {}

        keys = [
            "Gen_Dimu",
            "Reco_Dimu",
            "Gen_Dstar",
            "Reco_Dstar",
            "Cuts_Dimu",
            "Cuts_Dstar",
            "Trigger_Dimu",
            "Num_Asso",
            "Den_Asso",
        ]

        for i, out in enumerate(output):

            if i == 0:
                for key in keys:
                    hists[key] = out[key]

            else:
                for key in keys:
                    hists[key] += out[key]

        coffea_save(
            hists,
            str(cache_file),
        )

        print(
            f"Merged histograms saved to: "
            f"{cache_file}"
        )

    # Integrated summary for validation against AN Table 25
    def integral(histogram):
        return float(np.sum(histogram.values(flow=False)))

    integrated_efficiencies = {
        'acc_dimu': (
            integral(hists['Reco_Dimu']) /
            integral(hists['Gen_Dimu'])
        ),
        'acc_dstar': (
            integral(hists['Reco_Dstar']) /
            integral(hists['Gen_Dstar'])
        ),
        'eff_cuts_dstar': (
            integral(hists['Cuts_Dstar']) /
            integral(hists['Reco_Dstar'])
        ),
        'eff_cuts_dimu': (
            integral(hists['Cuts_Dimu']) /
            integral(hists['Reco_Dimu'])
        ),
        'eff_trigger': (
            integral(hists['Trigger_Dimu']) /
            integral(hists['Cuts_Dimu'])
        ),
        'eff_asso_pt': (
            integral(hists['Num_Asso']) /
            integral(hists['Den_Asso'])
        ),
    }

    integrated_efficiencies['global'] = np.prod([
        integrated_efficiencies['acc_dimu'],
        integrated_efficiencies['acc_dstar'],
        integrated_efficiencies['eff_cuts_dstar'],
        integrated_efficiencies['eff_cuts_dimu'],
        integrated_efficiencies['eff_trigger'],
        integrated_efficiencies['eff_asso_pt'],
    ])

    print("\nIntegrated efficiencies for AN Table 25 comparison:")
    for name, value in integrated_efficiencies.items():
        print(f"{name:20s}: {value:.8f}")
    print()

    def diagnose_efficiency_pair(name, num_hist, den_hist):
        num = np.asarray(num_hist.values(flow=False), dtype=float)
        den = np.asarray(den_hist.values(flow=False), dtype=float)

        valid = den > 0
        ratio = np.full_like(den, np.nan)
        ratio[valid] = num[valid] / den[valid]

        bad = valid & (num > den)

        print(f"\n===== {name} =====")
        print(f"max(num/den) = {np.nanmax(ratio):.8f}")
        print(f"bins with num > den = {np.count_nonzero(bad)}")

        for idx in np.argwhere(bad):
            idx = tuple(idx)
            print(
                f"  bin {idx}: "
                f"num={num[idx]:.8f}, "
                f"den={den[idx]:.8f}, "
                f"ratio={ratio[idx]:.8f}"
            )

    diagnose_efficiency_pair(
        "acc_dimu",
        hists["Reco_Dimu"],
        hists["Gen_Dimu"],
    )

    diagnose_efficiency_pair(
        "acc_dstar",
        hists["Reco_Dstar"],
        hists["Gen_Dstar"],
    )

    diagnose_efficiency_pair(
        "eff_cuts_dimu",
        hists["Cuts_Dimu"],
        hists["Reco_Dimu"],
    )

    diagnose_efficiency_pair(
        "eff_cuts_dstar",
        hists["Cuts_Dstar"],
        hists["Reco_Dstar"],
    )

    diagnose_efficiency_pair(
        "eff_trigger",
        hists["Trigger_Dimu"],
        hists["Cuts_Dimu"],
    )

    diagnose_efficiency_pair(
        "eff_asso_pt",
        hists["Num_Asso"].project("pt_dimu", "pt_dstar"),
        hists["Den_Asso"].project("pt_dimu", "pt_dstar"),
    )

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
        (r'$p_{T, D^*}$ [GeV/c]', r'$y_{D^*}$'),
        statistics="ratio",
    )
    eff_cuts_dimu_hist, eff_cuts_dimu_err_up, eff_cuts_dimu_err_down = create_eff_hists2D(
        hists['Cuts_Dimu'], 
        hists['Reco_Dimu'],
        (config['bins_pt_dimu'], config['bins_rap_dimu']),
        ('pt', 'rap'),
        (r'$p_{T, \mu^+\mu^-}$ [GeV/c]', r'$|y_{\mu^+\mu^-}|$'),
    )
    eff_cuts_dstar_hist, eff_cuts_dstar_err_up, eff_cuts_dstar_err_down = create_eff_hists2D(
        hists['Cuts_Dstar'], 
        hists['Reco_Dstar'],
        (config['bins_pt_dstar'], config['bins_rap_dstar']),
        ('pt', 'rap'),
        (r'$p_{T, D^*}$ [GeV/c]', r'$y_{D^*}$'),
    )
    eff_trigger_hist, eff_trigger_err_up, eff_trigger_err_down = create_eff_hists2D(
        hists['Trigger_Dimu'], 
        hists['Cuts_Dimu'],
        (config['bins_pt_dimu'], config['bins_rap_dimu']),
        ('pt', 'rap'),
        (r'$p_{T, \mu^+\mu^-}$ [GeV/c]', r'$|y_{\mu^+\mu^-}|$'),
    )
    eff_asso_pt_hist, eff_asso_pt_err_up, eff_asso_pt_err_down = create_eff_hists2D(
        hists['Num_Asso'].project('pt_dimu', 'pt_dstar'), 
        hists['Den_Asso'].project('pt_dimu', 'pt_dstar'),
        (config['bins_pt_dimu'], config['bins_pt_dstar']),
        ('pt_dimu', 'pt_dstar'),
        (r'$p_{T, \mu^+\mu^-}$ [GeV/c]', r'$p_{T, D^*}$ [GeV/c]'),
    )
    eff_asso_rap_hist, eff_asso_rap_err_up, eff_asso_rap_err_down = create_eff_hists2D(
        hists['Num_Asso'].project('rap_dimu', 'rap_dstar'), 
        hists['Den_Asso'].project('rap_dimu', 'rap_dstar'),
        (config['bins_rap_dimu'], config['bins_rap_dstar']),
        ('rap_dimu', 'rap_dstar'),
        (r'$|y_{\mu^+\mu^-}|$', r'$|y_{D^*}|$'),
    )

    # Save files to root
    pathlib.Path('output/efficiency').mkdir(parents=True, exist_ok=True)
    eff_file = uproot.recreate(f'output/efficiency/efficiencies_'+ config['mc_type'] + '_' + config['out_name'] + '_' + config['category'] + f'_{year}.root')

    acc_dimu_err_up_hist = (
        Hist.new
        .Variable(config['bins_pt_dimu'], name='pt_dimu', label=r'$p_{T, \mu^+\mu^-}$ [GeV/c]')
        .Variable(config['bins_rap_dimu'], name='rap_dimu', label=r'$y_{\mu^+\mu^-}$')
        .Double()
    )
    acc_dimu_err_down_hist = acc_dimu_err_up_hist.copy()
    eff_cuts_dimu_err_up_hist = acc_dimu_err_up_hist.copy()
    eff_cuts_dimu_err_down_hist = acc_dimu_err_up_hist.copy()
    eff_trigger_err_up_hist = acc_dimu_err_up_hist.copy()
    eff_trigger_err_down_hist = acc_dimu_err_up_hist.copy()

    acc_dstar_err_up_hist = (
        Hist.new
        .Variable(config['bins_pt_dstar'], name='pt_dstar', label=r'$p_{T, \mu^+\mu^-}$ [GeV/c]')
        .Variable(config['bins_rap_dstar'], name='rap_dstar', label=r'$y_{\mu^+\mu^-}$')
        .Double()
    )
    acc_dstar_err_down_hist = acc_dstar_err_up_hist.copy()
    eff_cuts_dstar_err_up_hist = acc_dstar_err_up_hist.copy()
    eff_cuts_dstar_err_down_hist = acc_dstar_err_up_hist.copy()
    
    eff_asso_pt_err_up_hist = (
        Hist.new
        .Variable(config['bins_pt_dimu'], name='pt_dimu', label=r'$p_{T, \mu^+\mu^-}$ [GeV/c]')
        .Variable(config['bins_pt_dstar'], name='pt_dstar', label=r'$p_{T, D^*}$ [GeV/c]')
        .Double()
    )
    eff_asso_pt_err_down_hist = eff_asso_pt_err_up_hist.copy()
    eff_asso_rap_err_up_hist = (
        Hist.new
        .Variable(config['bins_rap_dimu'], name='rap_dimu', label=r'$y_{\mu^+\mu^-}$')
        .Variable(config['bins_rap_dstar'], name='rap_dstar', label=r'$y_{D^*}$')
        .Double()
    )
    eff_asso_rap_err_down_hist = eff_asso_rap_err_up_hist.copy()
    
    acc_dimu_err_up_hist[...] = acc_dimu_err_up
    acc_dimu_err_down_hist[...] = acc_dimu_err_down
    acc_dstar_err_up_hist[...] = acc_dstar_err_up
    acc_dstar_err_down_hist[...] = acc_dstar_err_down
    eff_cuts_dimu_err_up_hist[...] = eff_cuts_dimu_err_up
    eff_cuts_dimu_err_down_hist[...] = eff_cuts_dimu_err_down
    eff_cuts_dstar_err_up_hist[...] = eff_cuts_dstar_err_up
    eff_cuts_dstar_err_down_hist[...] = eff_cuts_dstar_err_down
    eff_trigger_err_up_hist[...] = eff_trigger_err_up
    eff_trigger_err_down_hist[...] = eff_trigger_err_down
    eff_asso_pt_err_up_hist[...] = eff_asso_pt_err_up
    eff_asso_pt_err_down_hist[...] = eff_asso_pt_err_down
    eff_asso_rap_err_up_hist[...] = eff_asso_rap_err_up
    eff_asso_rap_err_down_hist[...] = eff_asso_rap_err_down

    eff_file['acc_dimu']                 = acc_dimu_hist.to_numpy()
    eff_file['acc_dstar']                = acc_dstar_hist.to_numpy()
    eff_file['eff_cuts_dimu']            = eff_cuts_dimu_hist.to_numpy()
    eff_file['eff_cuts_dstar']           = eff_cuts_dstar_hist.to_numpy()
    eff_file['eff_trigger']              = eff_trigger_hist.to_numpy()
    eff_file['eff_asso_pt']              = eff_asso_pt_hist.to_numpy()
    eff_file['eff_asso_rap']             = eff_asso_rap_hist.to_numpy()
    eff_file['acc_dimu_err_up']          = acc_dimu_err_up_hist.to_numpy()
    eff_file['acc_dimu_err_down']        = acc_dimu_err_down_hist.to_numpy()
    eff_file['acc_dimu_err_down']        = acc_dimu_err_down_hist.to_numpy()
    eff_file['acc_dstar_err_up']         = acc_dstar_err_up_hist.to_numpy()
    eff_file['acc_dstar_err_down']       = acc_dstar_err_down_hist.to_numpy()
    eff_file['eff_cuts_dimu_err_up']     = eff_cuts_dimu_err_up_hist.to_numpy()
    eff_file['eff_cuts_dimu_err_down']   = eff_cuts_dimu_err_down_hist.to_numpy()
    eff_file['eff_cuts_dstar_err_up']    = eff_cuts_dstar_err_up_hist.to_numpy()
    eff_file['eff_cuts_dstar_err_down']  = eff_cuts_dstar_err_down_hist.to_numpy()
    eff_file['eff_trigger_err_up']       = eff_trigger_err_up_hist.to_numpy()
    eff_file['eff_trigger_err_down']     = eff_trigger_err_down_hist.to_numpy()
    eff_file['eff_asso_pt_err_up']       = eff_asso_pt_err_up_hist.to_numpy()
    eff_file['eff_asso_pt_err_down']     = eff_asso_pt_err_down_hist.to_numpy()
    eff_file['eff_asso_rap_err_up']      = eff_asso_rap_err_up_hist.to_numpy()
    eff_file['eff_asso_rap_err_down']    = eff_asso_rap_err_down_hist.to_numpy()


    # Save weighted numerator/denominator statistics for reproducibility.
    efficiency_pairs = {
        "acc_dimu": (
            hists["Reco_Dimu"],
            hists["Gen_Dimu"],
        ),
        "acc_dstar": (
            hists["Reco_Dstar"],
            hists["Gen_Dstar"],
        ),
        "eff_cuts_dimu": (
            hists["Cuts_Dimu"],
            hists["Reco_Dimu"],
        ),
        "eff_cuts_dstar": (
            hists["Cuts_Dstar"],
            hists["Reco_Dstar"],
        ),
        "eff_trigger": (
            hists["Trigger_Dimu"],
            hists["Cuts_Dimu"],
        ),
        "eff_asso_pt": (
            hists["Num_Asso"].project("pt_dimu", "pt_dstar"),
            hists["Den_Asso"].project("pt_dimu", "pt_dstar"),
        ),
        "eff_asso_rap": (
            hists["Num_Asso"].project("rap_dimu", "rap_dstar"),
            hists["Den_Asso"].project("rap_dimu", "rap_dstar"),
        ),
    }

    print("\nWeighted effective-statistics summary:")

    for name, (num_hist, den_hist) in efficiency_pairs.items():

        if name in {"acc_dimu", "acc_dstar"}:
            stats = weighted_ratio_statistics(
                num_hist,
                den_hist,
            )
        else:
            stats = weighted_efficiency_statistics(
                num_hist,
                den_hist,
            )

        edges = tuple(
            np.asarray(axis.edges, dtype=float)
            for axis in den_hist.axes
        )

        eff_file[f"{name}_err_up_weighted"] = (
            stats["err_up"],
            *edges,
        )
        eff_file[f"{name}_err_down_weighted"] = (
            stats["err_down"],
            *edges,
        )
        eff_file[f"{name}_n_eff"] = (
            stats["n_eff"],
            *edges,
        )

        eff_file[f"raw/{name}_num_sumw"] = (
            stats["num_sumw"],
            *edges,
        )
        eff_file[f"raw/{name}_num_sumw2"] = (
            stats["num_sumw2"],
            *edges,
        )
        eff_file[f"raw/{name}_den_sumw"] = (
            stats["den_sumw"],
            *edges,
        )
        eff_file[f"raw/{name}_den_sumw2"] = (
            stats["den_sumw2"],
            *edges,
        )

        finite = stats["n_eff"][np.isfinite(stats["n_eff"])]

        if finite.size:
            print(
                f"{name:20s}: "
                f"N_eff min={finite.min():.2f}, "
                f"max={finite.max():.2f}, "
                f"bins<10={np.count_nonzero(finite < 10.0)}, "
                f"bins<25={np.count_nonzero(finite < 25.0)}"
            )
        else:
            print(f"{name:20s}: no valid bins")

    if args.plot:
        # Create plots of all the components
        for hist in hists:
            if not isinstance(hists[hist], Hist): continue
            fig, ax = plt.subplots()
            if len(hists[hist].axes) == 2:
                create_plot2d(hists[hist], ax=ax)
            else:
                create_plot2d(hists[hist].project("pt_dimu", "pt_dstar"), ax=ax)
            fig.savefig(f'plots/efficiency/{hist}_' + config['out_name'] + '_' + f'{year}.png')
            plt.close()

        if year == '2016APV':
            year_int = 2016
        else:
            year_int = int(year)
        # Create plots 2D for efficiencies
        create_eff_plot2D(
            acc_dimu_hist, acc_dimu_err_up, acc_dimu_err_down, 
            f'acc_dimu_' + config['out_name'] + '_' +  f'{year}.png', 
            year_int, 
            vmin=0, vmax=1
        )
        create_eff_plot2D(
            acc_dstar_hist, acc_dstar_err_up, acc_dstar_err_down, 
            f'acc_dstar_' + config['out_name'] + '_' +  f'{year}.png', 
            year_int, 
            vmin=0, vmax=1
        )
        create_eff_plot2D(
            eff_cuts_dimu_hist, eff_cuts_dimu_err_up, eff_cuts_dimu_err_down, 
            f'eff_cuts_dimu_' + config['out_name'] + '_' +  f'{year}.png', 
            year_int, 
            vmin=0, vmax=1
        )
        create_eff_plot2D(
            eff_cuts_dstar_hist, eff_cuts_dstar_err_up, eff_cuts_dstar_err_down, 
            f'eff_cuts_dstar_' + config['out_name'] + '_' +  f'{year}.png', 
            year_int, 
            vmin=0, vmax=1
        )
        create_eff_plot2D(
            eff_trigger_hist, eff_trigger_err_up, eff_trigger_err_down, 
            f'eff_trigger_' + config['out_name'] + '_' +  f'{year}.png', 
            year_int, 
            vmin=0, vmax=1
        )
        create_eff_plot2D(
            eff_asso_pt_hist, eff_asso_pt_err_up, eff_asso_pt_err_down, 
            f'eff_asso_pt_' + config['out_name'] + '_' +  f'{year}.png', 
            year_int, 
            vmin=0, vmax=1
        )
        create_eff_plot2D(
            eff_asso_rap_hist, eff_asso_rap_err_up, eff_asso_rap_err_down, 
            f'eff_asso_rap_' + config['out_name'] + '_' +  f'{year}.png', 
            year_int, 
            vmin=0, vmax=1
        )

        create_eff_plot1D(
            hists['Reco_Dimu'].project('pt'), 
            hists['Gen_Dimu'].project('pt'), 
            config['bins_pt_dimu'],
            'pt',
            r'$p_{T, \mu^+\mu^-}$ [GeV/c]',
            f'acc_dimu_pt_' + config['out_name'] + '_' +  f'{year}.png',
        )
        create_eff_plot1D(
            hists['Reco_Dimu'].project('rap'), 
            hists['Gen_Dimu'].project('rap'), 
            config['bins_rap_dimu'],
            'rap',
            r'$|y_{\mu^+\mu^-}|$',
            f'acc_dimu_rap_' + config['out_name'] + '_' +  f'{year}.png',
        )
        create_eff_plot1D(
            hists['Reco_Dstar'].project('pt'), 
            hists['Gen_Dstar'].project('pt'), 
            config['bins_pt_dstar'],
            'pt',
            r'$p_{T, \mu^+\mu^-}$ [GeV/c]',
            f'acc_dstar_pt_' + config['out_name'] + '_' +  f'{year}.png',
        )
        create_eff_plot1D(
            hists['Reco_Dstar'].project('rap'), 
            hists['Gen_Dstar'].project('rap'), 
            config['bins_rap_dstar'],
            'rap',
            r'$|y_{\mu^+\mu^-}|$',
            f'acc_dstar_rap_' + config['out_name'] + '_' +  f'{year}.png',
        )
        create_eff_plot1D(
            hists['Cuts_Dimu'].project('pt'), 
            hists['Reco_Dimu'].project('pt'), 
            config['bins_pt_dimu'],
            'pt',
            r'$p_{T, \mu^+\mu^-}$ [GeV/c]',
            f'eff_cuts_dimu_pt_' + config['out_name'] + '_' +  f'{year}.png',
        )
        create_eff_plot1D(
            hists['Cuts_Dimu'].project('rap'), 
            hists['Reco_Dimu'].project('rap'), 
            config['bins_rap_dimu'],
            'rap',
            r'$|y_{\mu^+\mu^-}|$',
            f'eff_cuts_dimu_rap_' + config['out_name'] + '_' +  f'{year}.png',
        )
        create_eff_plot1D(
            hists['Cuts_Dstar'].project('pt'), 
            hists['Reco_Dstar'].project('pt'), 
            config['bins_pt_dstar'],
            'pt',
            r'$p_{T, \mu^+\mu^-}$ [GeV/c]',
            f'eff_cuts_dstar_pt_' + config['out_name'] + '_' +  f'{year}.png',
        )
        create_eff_plot1D(
            hists['Cuts_Dstar'].project('rap'), 
            hists['Reco_Dstar'].project('rap'), 
            config['bins_rap_dstar'],
            'rap',
            r'$|y_{\mu^+\mu^-}|$',
            f'eff_cuts_dstar_rap_' + config['out_name'] + '_' +  f'{year}.png',
        )
        create_eff_plot1D(
            hists['Trigger_Dimu'].project('pt'), 
            hists['Cuts_Dimu'].project('pt'), 
            config['bins_pt_dimu'],
            'pt',
            r'$p_{T, \mu^+\mu^-}$ [GeV/c]',
            f'eff_trigger_pt_' + config['out_name'] + '_' +  f'{year}.png',
        )
        create_eff_plot1D(
            hists['Trigger_Dimu'].project('rap'), 
            hists['Cuts_Dimu'].project('rap'), 
            config['bins_rap_dimu'],
            'rap',
            r'$|y_{\mu^+\mu^-}|$',
            f'eff_trigger_rap_' + config['out_name'] + '_' +  f'{year}.png',
        )
