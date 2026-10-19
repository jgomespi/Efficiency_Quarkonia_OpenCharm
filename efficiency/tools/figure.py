import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import mplhep
import numpy as np
from matplotlib.text import Text
from hist.intervals import ratio_uncertainty
from hist import Hist
import os

from uncertainties import unumpy

plt.style.use(mplhep.style.CMS)
    
plt.rcParams.update({
    'font.size': 16,
    'axes.titlesize': 18,
    'axes.labelsize': 18,
    'xtick.labelsize': 14,
    'ytick.labelsize': 14
})

def create_plot1d(hist1d, labels=None, log=False, ax=None, lumi=None, **kwargs):
    from matplotlib.offsetbox import AnchoredOffsetbox, TextArea

    if ax == None:
        ax = plt.gca()

    artists = mplhep.histplot(hist1d, ax=ax, **kwargs)
    stairs_artists = [artist.stairs for artist in artists]
    #print(stairs_artists)
    if not labels == None:
        if len(labels) != len(stairs_artists): print("len of labels does not match artists")
        else: plt.legend(stairs_artists, labels)
    
    if not lumi == None:
        lumi = plt.text(1., 1., f'{lumi:.2f}' + r" fb$^{-1}$ (13 TeV)",
                        fontsize=18,
                        horizontalalignment='right',
                        verticalalignment='bottom',
                        transform=ax.transAxes
                       )
    
    if log:
        ax.set_yscale('log')
        ax.set_ylim(1, None)
    else:
        ax.ticklabel_format(axis='y', style='sci', scilimits=(0,3), useMathText=True)
    
    if isinstance(hist1d, Hist):
        centers = hist1d.axes.centers[0]
        values = hist1d.values()
        
        # compute mean and std:
        mean = np.sum(values*centers)/np.sum(values)
        std = np.sqrt(np.sum(values*((centers - mean)**2))/np.sum(values))
        
        annotation = TextArea(f"Total: {np.sum(values):.2e}" \
                        + "\n" + f"Mean: {mean:.2e}" \
                        + "\n" + f"Std: {std:.2e}", textprops=dict(size=14))
        
        at = AnchoredOffsetbox('upper right', child=annotation)
        at.patch.set_facecolor('None')
        ax.add_artist(at)
    
    return ax

def create_plot2d(hist2d, ax, limits=None):
    if ax == None:
        ax = plt.gca()
    
    artists = hist2d.plot2d(ax=ax)
    pcolormesh = artists.pcolormesh
    if limits is not None:
        pcolormesh.set_clim(limits)
    
    return ax

def acceptance_plot(hist_reco, hist_gen, ax=None, uncertainty_type ='efficiency', with_labels=True, with_unc=True):
    if ax == None:
        ax = plt.gca()
    
    ratio = hist_reco / hist_gen.values()

    n = [len(i.centers) for i in hist_reco.axes]

    if with_labels:
        try:
            err_down, err_up = ratio_uncertainty(hist_reco.values(), hist_gen.values(), uncertainty_type)
        except ValueError:
            print("Found numerator larger than denominator while calculating binomial uncertainty, switching to poison uncertainty calculation")
            err_down, err_up = ratio_uncertainty(hist_reco.values(), hist_gen.values())
        labels = []
        for ra, u, d in zip(ratio.values().ravel(), err_up.ravel(), err_down.ravel()):
            ra, u, d = f'{ra:.2f}', f'{u:.2f}', f'{d:.2f}'
            st = '$'+ra+'_{-'+d+'}^{+'+u+'}$'
            labels.append(st)
        labels = np.array(labels).reshape(*n)

        mplhep.hist2dplot(ratio, labels=labels, ax=ax)

        x = ax.get_children()
        for i0 in x:
            if isinstance(i0, Text):
                i0.set_size(10)

        return ax
    else:
        mplhep.hist2dplot(ratio, ax=ax)
        return ax

def load_acc(path):
    from coffea.util import load
    acc = []

    for p in path:
        for it in os.scandir(p):
            if it.name.find('.coffea') < 0: continue
            if len(acc) == 0:
                acc = load(it.path)
            else:
                acc += load(it.path)

    return acc

def plots(acc, path, lumi_year):
    hists = {
        'UpsilonDstar': {
            'Upsilon_pt': Hist.new.Regular(100, 0, 300, name='pt', label=r"$p_{T, \Upsilon}$ [GeV]").Double(),
            'Dstar_pt': Hist.new.Regular(100, 0, 300, name='pt', label=r"$p_{T, D^{*}}$ [GeV]").Double(),
        },
    }

    hists['UpsilonDstar']['Upsilon_pt'].fill(pt=acc['DimuDstar']['dimu_pt'].value)
    hists['UpsilonDstar']['Dstar_pt'].fill(pt=acc['DimuDstar']['dstar_pt'].value)

    for hist in hists['UpsilonDstar']:
        fig, ax = plt.subplots()
        create_plot1d(hists['UpsilonDstar'][hist], log=True, ax=ax, lumi=f'{lumi_year:.2f}')
        fig.savefig(f'{path}/{hist}.png')

def create_fom(fom, x_points, param, year, lumi=None):
    fig, ax = plt.subplots()
    if fom.dtype == 'O':
        ax.errorbar(x_points, unumpy.nominal_values(fom), yerr=unumpy.std_devs(fom), marker='o')
    else:
        ax.plot(x_points, fom, marker='o')
    ax.set_title(f'Fom of {param}')

    if not lumi == None:
        lumi = f'{lumi:.2f}'
        lumi = plt.text(1., 1., lumi + r" fb$^{-1}$ (13 TeV)",
                        fontsize=18,
                        horizontalalignment='right',
                        verticalalignment='bottom',
                        transform=ax.transAxes
                       )

    fig.savefig(f'plots/fom_vtxfit/{year}/fom_{param}.png')

if __name__ == '__main__':
    from hist import Hist
    import yaml

    with open('config/lumi.yaml', 'r') as f:
        lumi = yaml.load(f, Loader=yaml.FullLoader)
    with open('config/fit.yaml', 'r') as f:
        config_fit = yaml.load(f, Loader=yaml.FullLoader)
    with open('config/skim_trigger.yaml', 'r') as f:
        trigger = yaml.load(f, Loader=yaml.FullLoader)['trigger']

    years = ['2016', '2017', '2018']

    for year in years:
        lumi_year = sum([lumi[year][x][trigger[year]] for x in lumi[year]])
        acc = load_acc(config_fit['path'][year])
        os.system(f'mkdir -p plots/RunII_trigger_processed/{year}')
        plots(acc, f'plots/RunII_trigger_processed/{year}', lumi_year)
