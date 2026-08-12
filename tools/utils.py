import os, re, json
import awkward as ak

from collections import defaultdict

from coffea.nanoevents.methods import candidate
ak.behavior.update(candidate.behavior)

from coffea.util import load

import numpy as np

import yaml

D0_PDG_MASS = 1.864

Y1S_BR       = 0.0248
Y1S_BR_err   = 0.0005
Y2S_BR       = 0.0193
Y2S_BR_err   = 0.0017
Y3S_BR       = 0.0218
Y3S_BR_err   = 0.0021

Dstar_BR     = 0.677
Dstar_BR_err = 0.005
D0_BR        = 0.03947
D0_BR_err    = 0.00030

def atoi(text):
    return int(text) if text.isdigit() else text

def natural_keys(text):
    '''
    alist.sort(key=natural_keys) sorts in human order
    http://nedbatchelder.com/blog/200712/human_sorting.html
    (See Toothy's implementation in the comments)
    '''
    return [ atoi(c) for c in re.split(r'(\d+)', text) ]


def build_p4(acc):
    p4 = ak.zip({'x': acc['x'].value,
                 'y': acc['y'].value,
                 'z': acc['z'].value,
                 't': acc['t'].value}, with_name="LorentzVector")
    p4.rap = np.log((p4.energy + p4.z)/np.sqrt(p4.mass2 + p4.pt2))

    return p4


def build_acc(obj, name=None):

    from coffea import processor
    acc = processor.dict_accumulator({})
    for var in obj.fields:
        acc[var] = processor.column_accumulator(ak.to_numpy(ak.flatten(obj[var])))
    if name is not None:
        acc[f"n{name}"] = processor.column_accumulator(ak.to_numpy(ak.num(obj)))
    return acc

def association(cand1, cand2):
    ''' Function for association of the particles. The cuts that operates on all of them and 
    computation of quantities can go here. individual cuts can go on the main processing'''
    cand2 = cand2[cand2.associationIdx > -1]
    asso = ak.zip({'0': cand1[cand2.associationIdx], '1': cand2})
    
    cand1 = ak.zip({
            'pt': asso.slot0.pt,
            'eta': asso.slot0.eta,
            'phi': asso.slot0.phi,
            'mass': asso.slot0.mass,
            'charge': asso.slot0.charge}, with_name="PtEtaPhiMCandidate")

    cand2 = ak.zip({
            'pt': asso.slot1.pt,
            'eta': asso.slot1.eta,
            'phi': asso.slot1.phi,
            'mass': asso.slot1.mass,
            'charge': asso.slot1.charge}, with_name="PtEtaPhiMCandidate")

    asso['deltarap'] = asso.slot0.rap - asso.slot1.rap
    asso['deltapt'] = asso.slot0.pt - asso.slot1.pt
    asso['deltaeta'] = asso.slot0.eta - asso.slot1.eta
    asso['deltaphi'] = np.remainder(np.abs(asso.slot0.phi - asso.slot1.phi), np.pi)
    asso['cand'] = cand1 + cand2
    
    return asso

def get_files(paths, pattern='.root', exclude=None, recursive=False):
    files = []

    for path in paths:

        if recursive:
            candidates = []

            for root, _, names in os.walk(path):
                for name in names:
                    candidates.append(
                        os.path.join(root, name)
                    )

        else:
            candidates = [
                it.path
                for it in os.scandir(path)
                if it.is_file()
            ]

        for filepath in candidates:
            name = os.path.basename(filepath)

            if name.find(pattern) == -1:
                continue

            try:
                if os.path.getsize(filepath) == 0:
                    continue
            except OSError:
                continue

            if exclude is not None:
                if any(e in name for e in exclude):
                    continue

            files.append(filepath)

    files.sort(key=natural_keys)

    return files

def save_kin_hists(hists, cand, gen=False, get_deltam=False):
    hists['pt'].fill(pt=ak.flatten(cand.pt))
    hists['eta'].fill(eta=ak.flatten(cand.eta))
    hists['phi'].fill(phi=ak.flatten(cand.phi))
    if not gen: 
        if get_deltam: hists['deltam'].fill(deltam=ak.flatten(cand.deltamr))
        else: hists['mass'].fill(mass=ak.flatten(cand.mass))

def get_n(array):
    array2 = array[ak.fill_none(array, -1) > -1]
    return ak.num(array2)

def remove_none(array):
    return ak.fill_none(array, -99) > -1

def get_lumi(year, trigger):
    processed_lumi = 0
    with open("config/lumi.yaml", 'r') as f:
        lumis = yaml.load(f, Loader=yaml.FullLoader)
        for era in lumis[year]:
            processed_lumi += lumis[year][era][trigger]

    return processed_lumi

def get_trigger(year):
    with open("config/skim_trigger.yaml", "r") as f:
        trigger = yaml.load(f, Loader=yaml.FullLoader)['trigger'][year]
    return trigger

def get_xsec(dictionary_in, dictionary_out, group, eta_width, factor):
    for values in dictionary_in['values']:
        bins_width = float(values['x'][0]['high']) - float(values['x'][0]['low'])
        for y in values['y']:
            if y['group'] != group: continue
            value = float(y['value'])
            if '%' in y['errors'][0]['symerror']:
                error_stat = float(y['errors'][0]['symerror'][:-1])/100*value
                error_syst = float(y['errors'][1]['symerror'][:-1])/100*value
            else:
                error_stat = float(y['errors'][0]['symerror'][:-1])
                error_syst = float(y['errors'][1]['symerror'][:-1])
            dictionary_out['value'] += value*bins_width*eta_width*factor
            dictionary_out['error_stat'] += error_stat*bins_width*eta_width*factor
            dictionary_out['error_syst'] += error_syst*bins_width*eta_width*factor



def get_all_xsec():
    with open('data/cross_section/Y_1S_xsection.json', 'r') as f:
        Y_1S = json.load(f)

    with open('data/cross_section/Y_2S_xsection.json', 'r') as f:
        Y_2S = json.load(f)
        
    with open('data/cross_section/Y_3S_xsection.json', 'r') as f:
        Y_3S = json.load(f)

    with open('data/cross_section/open_charm_xsection.json', 'r') as f:
        open_charm = json.load(f)

    xsection_total = {
        'Y_1S': defaultdict(float),
        'Y_2S': defaultdict(float),
        'Y_3S': defaultdict(float),
        'D0': defaultdict(float),
        'D+': defaultdict(float),
        'D*+': defaultdict(float),
    }

    get_xsec(Y_1S, xsection_total['Y_1S'], 2, 2.4, 1e-12)
    get_xsec(Y_2S, xsection_total['Y_2S'], 2, 2.4, 1e-12)
    get_xsec(Y_3S, xsection_total['Y_3S'], 2, 2.4, 1e-12)
    get_xsec(open_charm, xsection_total['D0'], 1, 1, 1e-6)
    get_xsec(open_charm, xsection_total['D+'], 2, 1, 1e-6)
    get_xsec(open_charm, xsection_total['D*+'], 0, 1, 1e-6)

    return xsection_total

def get_evt_eff(hists_eff, data):
    from coffea.lookup_tools.dense_lookup import dense_lookup
    
    corr = {h:dense_lookup(hists_eff[h].values(), [ax.edges for ax in hists_eff[h].axes]) for h in hists_eff}

    effs = {}
    effs['acc_dimu']                  = ak.flatten(corr['acc_dimu'](data.dimu_pt, data.dimu_rap))
    effs['acc_dstar']                 = ak.flatten(corr['acc_dstar'](data.dstar_pt, data.dstar_rap))
    effs['eff_cuts_dimu']             = ak.flatten(corr['eff_cuts_dimu'](data.dimu_pt, data.dimu_rap))
    effs['eff_cuts_dstar']            = ak.flatten(corr['eff_cuts_dstar'](data.dstar_pt, data.dstar_rap))
    effs['eff_trigger_dimu']          = ak.flatten(corr['eff_trigger'](data.dimu_pt, data.dimu_rap))
    effs['eff_asso_pt']               = ak.flatten(corr['eff_asso_pt'](data.dimu_pt, data.dstar_pt))
    
    effs_err_up = {}
    effs_err_up['acc_dimu']           = ak.flatten(corr['acc_dimu_err_up'](data.dimu_pt, data.dimu_rap))
    effs_err_up['acc_dstar']          = ak.flatten(corr['acc_dstar_err_up'](data.dstar_pt, data.dstar_rap))
    effs_err_up['eff_cuts_dimu']      = ak.flatten(corr['eff_cuts_dimu_err_up'](data.dimu_pt, data.dimu_rap))
    effs_err_up['eff_cuts_dstar']     = ak.flatten(corr['eff_cuts_dstar_err_up'](data.dstar_pt, data.dstar_rap))
    effs_err_up['eff_trigger_dimu']   = ak.flatten(corr['eff_trigger_err_up'](data.dimu_pt, data.dimu_rap))
    effs_err_up['eff_asso_pt']        = ak.flatten(corr['eff_asso_pt_err_up'](data.dimu_pt, data.dstar_pt))

    effs_err_down = {}
    effs_err_down['acc_dimu']         = ak.flatten(corr['acc_dimu_err_down'](data.dimu_pt, data.dimu_rap))
    effs_err_down['acc_dstar']        = ak.flatten(corr['acc_dstar_err_down'](data.dstar_pt, data.dstar_rap))
    effs_err_down['eff_cuts_dimu']    = ak.flatten(corr['eff_cuts_dimu_err_down'](data.dimu_pt, data.dimu_rap))
    effs_err_down['eff_cuts_dstar']   = ak.flatten(corr['eff_cuts_dstar_err_down'](data.dstar_pt, data.dstar_rap))
    effs_err_down['eff_trigger_dimu'] = ak.flatten(corr['eff_trigger_err_down'](data.dimu_pt, data.dimu_rap))
    effs_err_down['eff_asso_pt']      = ak.flatten(corr['eff_asso_pt_err_down'](data.dimu_pt, data.dstar_pt))

    total_eff = np.prod([effs[h] for h in effs], axis=0)
    total_eff_err_up = total_eff*np.sqrt(np.sum([(effs_err_up[h]/effs[h])**2 for h in effs], axis=0))
    total_eff_err_down = total_eff*np.sqrt(np.sum([(effs_err_down[h]/effs[h])**2 for h in effs], axis=0))
    
    wgt = 1/total_eff

    return total_eff, total_eff_err_up, total_eff_err_down, wgt


def get_eff(year):
    years = ['2016APV', '2016', '2017', '2018']
    acc = None
    if str(year) not in years:
        raise ValueError('Year not valid!')
    base_folder = f'output/RunII_trigger_processed_vtxfit/{year}'
    for it in os.scandir(base_folder):
        if not it.is_dir(): continue
        for it in os.scandir(it.path):
            if not it.name.endswith('.coffea'): continue
            if acc:
                acc += load(it.path)
            else:
                acc = load(it.path)

    eff = np.mean(acc['DimuDstar']['eff'].value)
    eff_err_up = np.mean(acc['DimuDstar']['eff_err_up'].value)
    eff_err_down = np.mean(acc['DimuDstar']['eff_err_down'].value)

    return eff, eff_err_up, eff_err_down