import time
import yaml
import uproot
from hist.intervals import ratio_uncertainty
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

if config['mc_type'] == 'DPS-ccbar':
    mc_v = 'dps_official'
elif config['mc_type'] == 'SPS-ccbar':
    mc_v = 'sps_official'

years = ['2016APV', '2016', '2017', '2018']
ps = [
    '/eos/user/m/mabarros/Monte_Carlo/' + mc_v +  '/ccbar/JpsiPt9To30ToMuMuDstarToD0pi',
    '/eos/user/m/mabarros/Monte_Carlo/' + mc_v +  '/ccbar/JpsiPt30To50ToMuMuDstarToD0pi',
    '/eos/user/m/mabarros/Monte_Carlo/' + mc_v +  '/ccbar/JpsiPt50To100ToMuMuDstarToD0pi',
]

'''ps = [
    '/eos/user/m/mabarros/Monte_Carlo/2017/jpsi_bbbar_DPS_2017_13TeV/JpsiPt9To30ToMuMuDstarToD0pi',
    '/eos/user/m/mabarros/Monte_Carlo/2017/jpsi_bbbar_DPS_2017_13TeV/JpsiPt30To50ToMuMuDstarToD0pi',
    '/eos/user/m/mabarros/Monte_Carlo/2017/jpsi_bbbar_DPS_2017_13TeV/JpsiPt50To100ToMuMuDstarToD0pi',
]'''



exclude = [
    'DPS_D0ToKPi_JPsiPt-50To100_JPsiFilter_TuneCP5_13TeV-pythia8-evtgenRunIISummer20UL16RECO_41.root',
]



def create_eff_hists2D(hist_num, hist_den, bins, names, hist_labels):
    eff_hist = (
        Hist.new
        .Variable(bins[0], name=names[0], label=hist_labels[0])
        .Variable(bins[1], name=names[1], label=hist_labels[1])
        .Double()
    )

    num = hist_num.values()
    den = hist_den.values()

    values = np.where(
        (num > 0) & (den > 0),
        num/den,
        1.0,    
    )
    err_down, err_up = np.where(
        (den > 0),
        ratio_uncertainty(num, den, uncertainty_type='efficiency'),
        #ratio_uncertainty(num, den, uncertainty_type='poisson-ratio'),
        0.0
    )
    #err = np.where((err_up > err_down), err_up, err_down)

    eff_hist[...] = values
    #eff_hist[...] = np.stack([values, err**2], axis=-1)

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
    parser = argparse.ArgumentParser(description="Create efficiency plots")
    parser.add_argument("-y", "--year", help="Year to create efficiency", type=str, required=True, choices=years)
    parser.add_argument("-p", "--plot", help="Plot efficiency", action='store_true')
    args = parser.parse_args()   

    year = args.year

    paths = [f'{p}_{year}' for p in ps] #-v2 was removed (in kevin's)
    files = [get_files([p], exclude=exclude) for p in paths]

    output = []
    tstart = time.time()
    for f in files:
        data = {"test": f[:]}

        # It takes one sample at a time
        print(f[0])
        sample_cut = float(f[0][f[0].find('Pt')+2:f[0].find('To')])
        print(f"Treating file with Pt > {sample_cut}")

        output.append(
            processor.run_uproot_job(
                data, 
                treename='Events',
                processor_instance=EfficiencyProcessor(
                    dimu_cut=sample_cut,
                    year=year,
                    config=config,
                ),
                executor=processor.futures_executor,
                executor_args={"schema": BaseSchema, 'workers': 8, 'skipbadfiles': True},
                chunksize=360000,
            )
                                    
        )
    print(f"Process finished in: {time.time() - tstart:.2f} s")
    
    # Loop to return the number of events in the sample
    nevt = 0
    for i in range(0, len(output)):
        nevt +=output[i]['cutflow']['Number of events']
    print(f"Number of events: {nevt}")

    # Merge the hists
    hists = {}
    for i, out in enumerate(output):
        if i == 0:
            hists['Gen_Dimu']       = out['Gen_Dimu']
            hists['Reco_Dimu']      = out['Reco_Dimu']
            hists['Gen_Dstar']      = out['Gen_Dstar']
            hists['Reco_Dstar']     = out['Reco_Dstar']
            hists['Cuts_Dimu']      = out['Cuts_Dimu']
            hists['Cuts_Dstar']     = out['Cuts_Dstar']
            hists['Trigger_Dimu']   = out['Trigger_Dimu']
            hists['Num_Asso']       = out['Num_Asso']
            hists['Den_Asso']       = out['Den_Asso']
        else:
            hists['Gen_Dimu']       += out['Gen_Dimu']
            hists['Reco_Dimu']      += out['Reco_Dimu']
            hists['Gen_Dstar']      += out['Gen_Dstar']
            hists['Reco_Dstar']     += out['Reco_Dstar']
            hists['Cuts_Dimu']      += out['Cuts_Dimu']
            hists['Cuts_Dstar']     += out['Cuts_Dstar']
            hists['Trigger_Dimu']   += out['Trigger_Dimu']
            hists['Num_Asso']       += out['Num_Asso']
            hists['Den_Asso']       += out['Den_Asso']

    acc_dimu_hist, acc_dimu_err_up, acc_dimu_err_down = create_eff_hists2D(
        hists['Reco_Dimu'], 
        hists['Gen_Dimu'],
        (config['bins_pt_dimu'], config['bins_rap_dimu']),
        ('pt', 'rap'),
        (r'$p_{T, \mu^+\mu^-} [GeV/c]$', r'$|y_{\mu^+\mu^-}|$'),
    )
    acc_dstar_hist, acc_dstar_err_up, acc_dstar_err_down = create_eff_hists2D(
        hists['Reco_Dstar'], 
        hists['Gen_Dstar'],
        (config['bins_pt_dstar'], config['bins_rap_dstar']),
        ('pt', 'rap'),
        (r'$p_{T, D^*}$ [GeV/c]', r'$y_{D^*}$'),
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
