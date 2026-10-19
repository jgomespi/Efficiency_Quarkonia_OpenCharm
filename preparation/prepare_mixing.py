#!/usr/bin/env python3
"""
Batch-oriented version of data_preparation_analysis.ipynb for JPsi+Dstar mixing inputs.

It reads a text file with ROOT files, runs the coffea processor, and writes one .coffea output.
"""

import argparse
import os
import sys
import time
import math

import awkward as ak
import numpy as np
import numba
import coffea
import uproot
import setuptools

from coffea import processor, hist
from coffea.nanoevents import BaseSchema
from coffea.nanoevents.methods import candidate
from coffea.lookup_tools import extractor
from coffea.util import save

ak.behavior.update(candidate.behavior)

ENABLE_HLT = False


def print_environment():
    print("python:", sys.version)
    print("executable:", sys.executable)
    print("setuptools:", setuptools.__version__)
    print("has setuptools.extern:", hasattr(setuptools, "extern"))
    try:
        import setuptools.extern.packaging.version as v
        print("setuptools.extern.packaging OK:", v.parse("4.3.7"))
    except Exception as exc:
        print("setuptools.extern.packaging FAILED:", repr(exc))
    print("numba expected 0.60.0, got", numba.__version__)
    print("awkward expected 1.7.0, got", ak.__version__)
    print("uproot:", uproot.__version__)
    print("numpy expected 1.22.4, got", np.__version__)
    print("coffea expected 0.7.7, got", coffea.__version__)


def normalize_input_path(path, redirector):
    path = path.strip()
    if not path:
        return path
    if path.startswith("root://"):
        return path
    if path.startswith("/store/"):
        return f"root://{redirector}//{path}"
    return path


def read_filelist(filelist, redirector, max_files=None):
    with open(filelist, "r", encoding="utf-8") as handle:
        files = [normalize_input_path(line, redirector) for line in handle]
    files = [f for f in files if f and f.endswith(".root")]
    if max_files is not None and max_files > 0:
        files = files[:max_files]
    if not files:
        raise RuntimeError(f"No ROOT files found in filelist: {filelist}")
    return files



# ---- from notebook cell 2 ----
muon_cols = ['Muon_charge', 'Muon_dxy', 'Muon_dxyErr', 'Muon_dz', 'Muon_dzErr', 'Muon_eta', 'Muon_isGlobal', 'Muon_mass',
             'Muon_phi', 'Muon_pt', 'Muon_ptErr', 'Muon_softId', 'Muon_vtxIdx', 'Muon_vtxFlag', 'Muon_simIdx', 'Muon_Id']

dimu_cols = ['Dimu_pt', 'Dimu_eta', 'Dimu_phi', 'Dimu_rap', 'Dimu_mass', 'Dimu_charge', 'Dimu_vtxIdx', 'Dimu_chi2', 'Dimu_dl',
             'Dimu_dlErr', 'Dimu_dlSig', 'Dimu_cosphi', 'Dimu_x', 'Dimu_y', 'Dimu_z', 'Dimu_t1muIdx', 'Dimu_t2muIdx', 'Dimu_simIdx']

d0_cols = ['D0_pt', 'D0_eta', 'D0_phi', 'D0_rap', 'D0_mass12', 'D0_mass21', 'D0_vtxIdx', 'D0_chi2', 'D0_dl', 'D0_dlErr', 'D0_dlSig',
           'D0_cosphi', 'D0_x', 'D0_y', 'D0_z', 'D0_hasMuon', 'D0_t1pt', 'D0_t1eta', 'D0_t1phi', 'D0_t1chindof', 'D0_t1nValid',
           'D0_t1nPix', 'D0_t1dxy', 'D0_t1dz', 'D0_t1chg', 'D0_t2pt', 'D0_t2eta', 'D0_t2phi', 'D0_t2chindof', 'D0_t2nValid',
           'D0_t2nPix', 'D0_t2dxy', 'D0_t2dz', 'D0_t2chg', 'D0_simIdx']

dstar_cols = ['Dstar_pt', 'Dstar_eta', 'Dstar_phi', 'Dstar_rap', 'Dstar_deltam', 'Dstar_deltamr', 'Dstar_vtxIdx', 'Dstar_hasMuon',
              'Dstar_D0pt', 'Dstar_D0eta', 'Dstar_D0phi', 'Dstar_D0mass', 'Dstar_D0chi2', 'Dstar_D0dl', 'Dstar_D0dlErr',
              'Dstar_D0dlSig', 'Dstar_D0cosphi', 'Dstar_D0x', 'Dstar_D0y', 'Dstar_D0z',
              'Dstar_Kpt', 'Dstar_Keta', 'Dstar_Kphi', 'Dstar_KvtxIdx', 'Dstar_Kchindof', 'Dstar_KnValid', 'Dstar_KnPix', 'Dstar_Kdxy',
              'Dstar_Kdz', 'Dstar_Kchg',
              'Dstar_pipt', 'Dstar_pieta', 'Dstar_piphi', 'Dstar_pivtxIdx', 'Dstar_pichindof', 'Dstar_pinValid', 'Dstar_pinPix',
              'Dstar_pidxy', 'Dstar_pidz', 'Dstar_pichg',
              'Dstar_pispt', 'Dstar_piseta', 'Dstar_pisphi', 'Dstar_pisvtxIdx', 'Dstar_pischindof', 'Dstar_pisnValid', 'Dstar_pisnPix',
              'Dstar_pisdxy', 'Dstar_pisdz', 'Dstar_simIdx', 'Dstar_promptFlag',
              'Dstar_associationIdx', 'Dstar_associationProb', 'Dstar_associationchi2',]

# Total number of reconstructed primary vertices
primary_vertex_cols = ['PV_chi2', 'PV_ndof', 'PV_npvs', 'PV_npvsGood', 'PV_score', 'PV_x', 'PV_y', 'PV_z']

# Primary vertices (AOD, with or w/o cuts)
primary_vertex_aod_cols = ['nPVtx' ,'PVtx_Id', 'PVtx_isGood', 'PVtx_x', 'PVtx_y', 'PVtx_z', 'PVtx_ntrk', 'PVtx_x', 'PVtx_sumPt']

# Interesting gen particles
gen_part_cols = ['GenPart_eta', 'GenPart_genPartIdxMother', 'GenPart_mass', 'GenPart_pdgId', "GenPart_phi", "GenPart_pt", 'GenPart_status',
                 'GenPart_Id', 'GenPart_parpdgId', 'GenPart_sparpdgId', 'GenPart_numberOfDaughters', 'GenPart_nstchgdaug', 'GenPart_vx', 
                 'GenPart_vy', 'GenPart_vz', 'GenPart_mvx', 'GenPart_mvy', 'GenPart_mvz', 'GenPart_recIdx']

hlt_cols_charm_2016 = ['HLT_Dimuon16_Jpsi']
hlt_cols_charm_2017 = ['HLT_Dimuon25_Jpsi']
hlt_cols_charm_2018 = ['HLT_Dimuon25_Jpsi']

D0_PDG_MASS = 1.864

# This function is called to keep the cols in a good way to be read on the EventSelectProcessor.py
def get_vars_dict(events, col_list):
    dict = {}
    col = ''
    for c in col_list:
        if c.startswith('Muon'):
            col = c[5:]
        elif c.startswith('Dimu'):
            col = c[4:]
            if col.startswith('_'): col = col[1:]
        elif c.startswith('D0'):
            col = c[2:]
            if col.startswith('_'): col = col[1:]
        elif c.startswith('Dstar'):
            col = c[5:]
            if col.startswith('_'): col = col[1:]
        elif c.startswith('PVtx'):
            col = c[5:]
            if col.startswith('_'): col = col[1:]
        elif c.startswith('GenPart'):
            col = c[8:]
            if col.startswith('_'): col = col[1:]
        elif c.startswith('HLT'):
            col = c[:]
        else:
            Exception('Not good!')

        if col == 'x' or col == 'y' or col == 'z':
            col = 'vtx_' + col

        if len(events[c]) == 0:
            dict[col] = np.array([])
        else:
            dict[col] = events[c]
    return dict


# ---- from notebook cell 3 ----
def build_4mom_string(candidate):
    return f'({candidate.pt:.2f}, {candidate.eta:.2f}, {candidate.phi:.2f}, {candidate.mass:.2f})'

def to_cartesian(cand):
    x = cand.pt*math.cos(cand.phi)
    y = cand.pt*math.sin(cand.phi)
    z = cand.pt*math.sinh(cand.eta)
    t = math.sqrt(x*x + y*y + z*z + cand.mass*cand.mass)

    return t, x, y, z

def sum_cand(cand1, cand2):
    t1, x1, y1, z1 = to_cartesian(cand1)
    t2, x2, y2, z2 = to_cartesian(cand2)

    tr = t1+t2
    xr = x1+x2
    yr = y1+y2
    zr = z1+z2

    r = math.sqrt(xr*xr + yr*yr + zr*zr)
    pt = math.sqrt(xr*xr + yr*yr)
    eta = math.asinh(zr / r)
    phi = math.atan2(yr, xr)
    mass = math.sqrt(tr*tr - xr*xr - yr*yr - zr*zr)

    return f'({pt:.2f},{eta:.2f},{phi:.2f},{mass:.2f})'


def print_candidate(candidate):
    quadrimom = build_4mom_string(candidate)
    print(f"PDGId: {candidate.pdgId}, motherId: {candidate.genPartIdxMother}, n_daughters: {candidate.numberOfDaughters}, status: {candidate.status}, 4-momentum (pt, eta, phi, mass): {quadrimom}")


# ---- from notebook cell 8 ----
def association(cand1, cand2):
    '''Build J/psi-D* associations.

    Nominal ntuples provide Dstar_associationIdx/Prob/chi2.
    Some Run2017F ntuples do not. For those files, fall back to a
    common-vertex association using Dimu_vtxIdx == Dstar_vtxIdx.
    '''
    if 'associationIdx' in cand2.fields:
        cand2 = cand2[cand2.associationIdx > -1]
        asso = ak.zip({'0': cand1[cand2.associationIdx], '1': cand2})
    else:
        cand2['associationProb'] = ak.ones_like(cand2.pt)
        cand2['associationchi2'] = -1.0 * ak.ones_like(cand2.pt)
        asso = ak.cartesian({'0': cand1, '1': cand2}, axis=1)
        asso = asso[asso.slot0.vtxIdx == asso.slot1.vtxIdx]
    
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


# ---- from notebook cell 9 ----
def build_p4(acc):

    '''
    This function is used to build the lorentzvector for a given particle accumulator
    
    acc (dict_accumulator): Accumulator with the particle information.

    It returns the four vector for the particle (x, y, z, t)

    '''
    # Uses awkward array zip method to build the four vector    
    p4 = ak.zip({'x': acc['x'].value, 
                 'y': acc['y'].value,
                 'z': acc['z'].value,
                 't': acc['t'].value}, with_name="LorentzVector")

    return p4


# ---- from notebook cell 10 ----
class EventSelectorProcessor(processor.ProcessorABC):
    def __init__(self,):
        self._accumulator = processor.dict_accumulator({
            'JpsiDstar': processor.dict_accumulator({
                'Jpsi_mass': hist.Hist("Events", hist.Bin("mass", "$M_{\mu^+\mu^-}$ [GeV/$c^2$]", 100, 2.95, 3.25)), 
                'Jpsi_p': hist.Hist("Events", 
                                    hist.Bin("pt", "$p_{T,\mu^+\mu^-}$ [GeV/c]", 100, 0, 150),
                                    hist.Bin("eta", "$\eta_{\mu^+\mu^-}$", 60, -2.5, 2.5),
                                    hist.Bin("phi", "$\phi_{\mu^+\mu^-}$", 70, -3.5, 3.5)),
                'Jpsi_rap': hist.Hist("Events", hist.Bin("rap", "y", 60, -2.5, 2.5)),
                'Jpsi_dl': hist.Hist("Events", hist.Bin("dl", "decay length [mm]", 100, -0.5, 1.5)),
                'Jpsi_dlSig': hist.Hist("Events", hist.Bin("dlSig", "dl Significance", 100, -50, 200)),
                'JpsiDstar_deltarap': hist.Hist("Events", hist.Bin("deltarap", "$\Delta y$", 50, -5, 5)),
                'JpsiDstar_deltaphi': hist.Hist("Events", hist.Bin("deltaphi", r"$|\phi_{J/\psi} - \phi_{D^*}|$ [rad]", 80, 0, 5)),
                'JpsiDstar_mass': hist.Hist("Events", hist.Bin("mass", "$m_{J/\psi D*}$ [$GeV/c^2$]", 100, 0, 120)),
                'JpsiDstar_deltamass': hist.Hist("Events", hist.Bin("dmass", "$M_{J/\psi D*}$ - $M_{\mu^+\mu^-}$ - $M_{D^*}$[$GeV/c^2$]", 100, 0, 120)),
                'JpsiDstar_pt': hist.Hist("Events", hist.Bin("pt", "$p_{T, J/\psi D*}$ [$GeV/c$]", 50, 0, 150)),
                'Dstar_p': hist.Hist("Events",
                                 hist.Cat("chg", "charge"), 
                                 hist.Bin("pt", "$p_{T,D*}$ [GeV/c]", 100, 0, 100),
                                 hist.Bin("eta", "$\eta_{D*}$", 80, -2.5, 2.5),
                                 hist.Bin("phi", "$\phi_{D*}$", 70, -3.5, 3.5)),
                'Dstar_rap': hist.Hist("Events", 
                                    hist.Cat("chg", "charge"), 
                                    hist.Bin("rap", "y", 60, -2.5, 2.5)),
                'Dstar_deltam': hist.Hist("Events", 
                                        hist.Cat("chg", "charge"), 
                                        hist.Bin("deltam", "$\Delta m$ [$GeV/c^2$]", 50, 0.138, 0.162)),
                'Dstar_deltamr': hist.Hist("Events", 
                                        hist.Cat("chg", "wrong_charge"), 
                                        hist.Bin("deltamr", "$\Delta m_{refit}$ [$GeV/c^2$]", 50, 0.138, 0.162)),
                'Dstar_deltamr_wrong': hist.Hist("Events", 
                                        hist.Cat("chg", "charge"), 
                                        hist.Bin("deltamr", "$\Delta m_{wrong}$ [$GeV/c^2$]", 50, 0.138, 0.162)),       
                'Dstar_D0pt': hist.Hist("Events", 
                                        hist.Cat("chg", "charge"), 
                                        hist.Bin("d0pt", "D$^0$ from D$^*$ - p$_{T}$ [GeV/c]", 80, 0, 80)),
                'Dstar_D0cosphi': hist.Hist("Events", 
                                        hist.Cat("chg", "charge"), 
                                        hist.Bin("d0cosphi", "D$^0$ from D$^*$ - pointing angle", 120, 0.9, 1)),
                'Dstar_D0dl': hist.Hist("Events", 
                                        hist.Cat("chg", "charge"), 
                                        hist.Bin("d0dl", "D$^0$ from D$^*$ - Decay length [mm]", 80, 0, 2)),
                'Dstar_D0dlSig': hist.Hist("Events", 
                                        hist.Cat("chg", "charge"), 
                                        hist.Bin("d0dlsig", "D$^0$ from D$^*$ - Decay length significance", 120, 0, 50)),
                'Dstar_D0dca': hist.Hist("Events", 
                                        hist.Cat("chg", "charge"), 
                                        hist.Bin("d0dca", "D$^0$ from D$^*$ - DCA  (cm)", 80, 0, 0.1)),
                'Dstar_Kpt': hist.Hist("Events", 
                                        hist.Cat("chg", "charge"), 
                                        hist.Bin("kpt", "K from D$^*$ - p$_{T}$ [GeV/c]", 80, 0, 100)),
                'Dstar_Kchindof': hist.Hist("Events", 
                                        hist.Cat("chg", "charge"), 
                                        hist.Bin("kchindof", "K from D$^*$  - reduced $\chi^2$", 60, 0, 10)),
                'Dstar_KnValid': hist.Hist("Events", 
                                        hist.Cat("chg", "charge"), 
                                        hist.Bin("knvalid", "K from D$^*$ - tracker hits", 80, 0, 30)),
                'Dstar_Kdxy': hist.Hist("Events", 
                                        hist.Cat("chg", "charge"), 
                                        hist.Bin("kdxy", "K from D$^*$ - dxy ", 60, 0, 5)),
                'Dstar_Kdz': hist.Hist("Events", 
                                        hist.Cat("chg", "charge"), 
                                        hist.Bin("kdz", "K from D$^*$ - dz", 80, 0, 10)),
                'Dstar_pispt': hist.Hist("Events", 
                                        hist.Cat("chg", "charge"), 
                                        hist.Bin("pispt", "$\pi_s$ from D$^*$ - p_{T}$ [GeV/c]", 60, 0, 30)),
                'Dstar_pischindof': hist.Hist("Events", 
                                        hist.Cat("chg", "charge"), 
                                        hist.Bin("pischindof", "$\pi_s$ from D$^*$ - reduced $\chi^2$", 60, 0, 10)),
                'Dstar_pisnValid': hist.Hist("Events", 
                                        hist.Cat("chg", "charge"), 
                                        hist.Bin("pisnValid", "$\pi_s$ from D$^*$ - tracker hits", 80, 0, 30)),
                'Dstar_pisdz': hist.Hist("Events", 
                                        hist.Cat("chg", "charge"), 
                                        hist.Bin("pisdz", "$\pi_s$ from D$^*$ - dz", 80, -2.5, 2.5)),
                'Dstar_associationchi2': hist.Hist("Events", 
                                        hist.Cat("chg", "charge"), 
                                        hist.Bin("associationchi2", "$\chi^2$ association vertex", 500, 0, 500)), 
                'Dstar_associationProb': hist.Hist("Events", 
                                        hist.Cat("chg", "charge"), 
                                        hist.Bin("associationprob", "association prob", 200, -10, 10)), 
                'Jpsi_dstard0_deltaz': hist.Hist("Events", 
                                        hist.Cat("chg", "charge"), 
                                        hist.Bin("jpsi_dstard0_dz", "$\Delta z_{J/\psi D^0}  $", 100, -20, 20)), 
                'Dstar_promptFlag': hist.Hist("Events", 
                                        hist.Cat("chg", "charge"), 
                                        hist.Bin("dstar_prompt_flag", "$D^* prompt flag  $", 50, -5, 5)),    
            }),
            'MixingInput': processor.dict_accumulator({
                # Pre-association J/psi pool
                'jpsi_pre_pt':   processor.column_accumulator(np.array([], dtype=np.float64)),
                'jpsi_pre_eta':  processor.column_accumulator(np.array([], dtype=np.float64)),
                'jpsi_pre_phi':  processor.column_accumulator(np.array([], dtype=np.float64)),
                'jpsi_pre_rap':  processor.column_accumulator(np.array([], dtype=np.float64)),
                'jpsi_pre_mass': processor.column_accumulator(np.array([], dtype=np.float64)),
                'jpsi_pre_dl':   processor.column_accumulator(np.array([], dtype=np.float64)),

                # Pre-association D* pool
                'dstar_pre_pt':       processor.column_accumulator(np.array([], dtype=np.float64)),
                'dstar_pre_eta':      processor.column_accumulator(np.array([], dtype=np.float64)),
                'dstar_pre_phi':      processor.column_accumulator(np.array([], dtype=np.float64)),
                'dstar_pre_rap':      processor.column_accumulator(np.array([], dtype=np.float64)),
                'dstar_pre_mass':     processor.column_accumulator(np.array([], dtype=np.float64)),
                'dstar_pre_d0cosphi': processor.column_accumulator(np.array([], dtype=np.float64)),
                'dstar_pre_d0mass':   processor.column_accumulator(np.array([], dtype=np.float64)),
                'dstar_pre_d0pt':     processor.column_accumulator(np.array([], dtype=np.float64)),
                'dstar_pre_d0dl':     processor.column_accumulator(np.array([], dtype=np.float64)),
                'dstar_pre_d0dlsig': processor.column_accumulator(np.array([], dtype=np.float64)),
                
                # Final associated data pairs
                'pair_data_dy':    processor.column_accumulator(np.array([], dtype=np.float64)),
                'pair_data_dphi':  processor.column_accumulator(np.array([], dtype=np.float64)),
                'pair_data_mass':  processor.column_accumulator(np.array([], dtype=np.float64)),

                # J/psi variables after J/psi-D* association
                'pair_data_jpsi_pt':    processor.column_accumulator(np.array([], dtype=np.float64)),
                'pair_data_jpsi_eta':   processor.column_accumulator(np.array([], dtype=np.float64)),
                'pair_data_jpsi_phi':   processor.column_accumulator(np.array([], dtype=np.float64)),
                'pair_data_jpsi_rap':   processor.column_accumulator(np.array([], dtype=np.float64)),
                'pair_data_jpsi_mass':  processor.column_accumulator(np.array([], dtype=np.float64)),
                'pair_data_jpsi_dl':    processor.column_accumulator(np.array([], dtype=np.float64)),
                'pair_data_jpsi_dlsig': processor.column_accumulator(np.array([], dtype=np.float64)),

                # D* variables after J/psi-D* association
                'pair_data_dstar_pt':       processor.column_accumulator(np.array([], dtype=np.float64)),
                'pair_data_dstar_eta':      processor.column_accumulator(np.array([], dtype=np.float64)),
                'pair_data_dstar_phi':      processor.column_accumulator(np.array([], dtype=np.float64)),
                'pair_data_dstar_rap':      processor.column_accumulator(np.array([], dtype=np.float64)),
                'pair_data_dstar_mass':     processor.column_accumulator(np.array([], dtype=np.float64)),
                'pair_data_dstar_deltamr':  processor.column_accumulator(np.array([], dtype=np.float64)),

                # D0-from-D* variables after J/psi-D* association
                'pair_data_dstar_d0cosphi': processor.column_accumulator(np.array([], dtype=np.float64)),
                'pair_data_dstar_d0mass':   processor.column_accumulator(np.array([], dtype=np.float64)),
                'pair_data_dstar_d0pt':     processor.column_accumulator(np.array([], dtype=np.float64)),
                'pair_data_dstar_d0dl':     processor.column_accumulator(np.array([], dtype=np.float64)),
                'pair_data_dstar_d0dlsig':  processor.column_accumulator(np.array([], dtype=np.float64)),
                'pair_data_dstar_d0dca':    processor.column_accumulator(np.array([], dtype=np.float64)),

                # Association variables
                'pair_data_associationProb': processor.column_accumulator(np.array([], dtype=np.float64)),
                'pair_data_associationchi2': processor.column_accumulator(np.array([], dtype=np.float64)),

                # Optional diagnostic variables
                'pair_data_dstar_promptFlag': processor.column_accumulator(np.array([], dtype=np.float64)),
                'pair_data_dstar_pisdz':      processor.column_accumulator(np.array([], dtype=np.float64)),
            }),
        })
           
    @property
    def accumulator(self):
        return self._accumulator

    def process(self, events):
        output = self.accumulator.identity()
        # Convert an awkward array into a flat NumPy array and store it as a coffea column accumulator.
        # This is needed because the mixing step requires event-level/candidate-level arrays,
        # not only histograms.
        def to_col(x):
            arr = ak.flatten(x, axis=None)
            arr = ak.to_numpy(arr)

            # In case awkward returns a masked array
            if np.ma.isMaskedArray(arr):
                arr = arr.compressed()

            arr = np.asarray(arr, dtype=np.float64)

            return processor.column_accumulator(arr)
        # test if there is any events in the file
        if len(events) == 0:
            return output
        
        ############### Get All the interesting candidates from NTuples
        Dimu = ak.zip({**get_vars_dict(events, dimu_cols)}, with_name="PtEtaPhiMCandidate")
        Muon = ak.zip({**get_vars_dict(events, muon_cols)}, with_name="PtEtaPhiMCandidate")
        D0 = ak.zip({'mass': events.D0_mass12, **get_vars_dict(events, d0_cols)}, with_name="PtEtaPhiMCandidate")
        # Some Run2017F files do not contain Dstar_associationIdx/Prob/chi2.
        # Keep all non-association Dstar columns mandatory, but treat the
        # association columns as optional and handled by association().
        dstar_association_cols = [
            'Dstar_associationIdx',
            'Dstar_associationProb',
            'Dstar_associationchi2',
        ]
        event_fields = set(events.fields)
        dstar_cols_available = [c for c in dstar_cols if c in event_fields]
        missing_dstar_cols = [c for c in dstar_cols if c not in event_fields]
        missing_required_dstar_cols = [
            c for c in missing_dstar_cols if c not in dstar_association_cols
        ]
        if missing_required_dstar_cols:
            raise RuntimeError(
                "Missing required Dstar branches: "
                + ", ".join(missing_required_dstar_cols)
            )

        Dstar = ak.zip({'mass': (events.Dstar_D0mass + events.Dstar_deltamr),
                        'charge': events.Dstar_pischg,
                        **get_vars_dict(events, dstar_cols_available)}, 
                        with_name="PtEtaPhiMCandidate")
        # Era-aware HLT selection.
        # 2016 uses HLT_Dimuon16_Jpsi; 2017/2018 use HLT_Dimuon25_Jpsi.
        hlt = ENABLE_HLT
        dataset_name = events.metadata.get("dataset", "")

        if hlt:
            if "Run2016" in dataset_name:
                hlt_candidates = ["HLT_Dimuon16_Jpsi", "HLT_Dimuon20_Jpsi", "HLT_Dimuon25_Jpsi"]
            else:
                hlt_candidates = ["HLT_Dimuon25_Jpsi", "HLT_Dimuon20_Jpsi", "HLT_Dimuon16_Jpsi"]

            available_hlt = [name for name in hlt_candidates if name in events.fields]

            if len(available_hlt) == 0:
                print(f"WARNING: no requested HLT branch found for {dataset_name}; disabling HLT for this chunk")
                trigger_cut = np.ones(len(Dimu), dtype=bool)
            else:
                trigger_name = available_hlt[0]
                print(f"Using HLT branch: {trigger_name}")
                trigger_cut = events[trigger_name]

            Dimu = Dimu[trigger_cut]
            Muon = Muon[trigger_cut]
            Dstar = Dstar[trigger_cut]

        if not hlt:
            trigger_cut = np.ones(len(Dimu), dtype=bool)

            Dimu = Dimu[trigger_cut]
            Muon = Muon[trigger_cut]
            Dstar = Dstar[trigger_cut]

        ############### Dimu cuts charge = 0, mass cuts and chi2...
        Dimu = ak.mask(Dimu, Dimu.charge == 0)
        
        Dimu = ak.mask(Dimu, ((Dimu.mass > 2.95) & (Dimu.mass < 3.25)))

        ############### Get the Muons from Dimu, for cuts in their params
        Muon = ak.zip({'0': Muon[Dimu.t1muIdx], '1': Muon[Dimu.t2muIdx]})

        # SoftId and Global Muon cuts
        soft_id = (Muon.slot0.softId > 0) & (Muon.slot1.softId > 0)
        Dimu = ak.mask(Dimu, soft_id)
        Muon = ak.mask(Muon, soft_id)
        ## pT and eta/rapidity cuts
    
        # Muon pT
        muon_pt_cut = (Muon.slot0.pt > 3) & (Muon.slot1.pt > 3)
        Dimu = ak.mask(Dimu, muon_pt_cut)
        Muon = ak.mask(Muon, muon_pt_cut)

        # Muon eta 
        muon_eta_cut = (np.absolute(Muon.slot0.eta) <= 2.4) & (np.absolute(Muon.slot1.eta) <= 2.4)
        Dimu = ak.mask(Dimu, muon_eta_cut)
        Muon = ak.mask(Muon, muon_eta_cut)

        # Dimuon pT
        dimu_pt_cut = (Dimu.pt > 25) & (Dimu.pt < 100)
        Dimu = ak.mask(Dimu, dimu_pt_cut)
        Muon = ak.mask(Muon, dimu_pt_cut)

        # Dimuon rapidity
        # Pergunta
        dimu_rap_cut = (np.absolute(Dimu.rap) <= 2.5)
        Dimu = ak.mask(Dimu, dimu_rap_cut)
        Muon = ak.mask(Muon, dimu_rap_cut)

        Dimu['is_ups'] = (Dimu.mass > 8.5) & (Dimu.mass < 11.5)
        Dimu['is_jpsi'] = (Dimu.mass > 2.9) & (Dimu.mass < 3.3)
        Dimu['is_psi'] = (Dimu.mass > 3.35) & (Dimu.mass < 4.05)

        ############### Cuts for Dstar

        # trks cuts
        #Dstar = Dstar[trigger_cut]
        #Dstar['wrg_chg'] = (Dstar.Kchg == Dstar.pichg)
        
        Dstar = Dstar[~Dstar.hasMuon]

        #Dstar = Dstar[Dstar.Kchg != Dstar.pichg]        

        Dstar = Dstar[(Dstar.pt > 4) & (Dstar.pt < 100)]

        Dstar = Dstar[np.absolute(Dstar.rap) < 2.5]

        Dstar = Dstar[(Dstar.Kpt > 1.6) & (Dstar.pipt > 1.6)]

        Dstar = Dstar[(Dstar.Kchindof < 2.5) & (Dstar.pichindof < 2.5)]

        Dstar = Dstar[(Dstar.KnValid > 4) & (Dstar.pinValid > 4) & (Dstar.KnPix > 1) & (Dstar.pinPix > 1)]

        Dstar = Dstar[(Dstar.Kdxy < 0.5) & (Dstar.pidxy < 0.5)]

        K_theta = 2 * np.arctan(np.exp(-Dstar.Keta))
        pi_theta = 2 * np.arctan(np.exp(-Dstar.pieta))
        Dstar = Dstar[(Dstar.Kdz < 0.5/np.sin(K_theta)) & (Dstar.pidz < 0.5/np.sin(pi_theta))]

        # pis cuts
        Dstar = Dstar[Dstar.pispt > 0.3]

        Dstar = Dstar[Dstar.pischindof < 3]

        Dstar = Dstar[Dstar.pisnValid > 2]

        # D0 of Dstar cuts
        Dstar = Dstar[Dstar.D0cosphi > 0.99]
        
        Dstar = Dstar[(Dstar.D0mass < D0_PDG_MASS + 0.028) & (Dstar.D0mass > D0_PDG_MASS - 0.028)]

        Dstar = Dstar[Dstar.D0pt > 4]
        
        Dstar = Dstar[Dstar.D0dlSig > 2.5]
        
        Dstar['wrg_chg'] = (Dstar.Kchg == Dstar.pichg)
        
        Dstar['D0dca'] = Dstar.D0dl * (1-Dstar.D0cosphi**2)**0.5
        
        Dstar = Dstar[(Dstar.deltamr > 0.143) & (Dstar.deltamr < 0.147)]
        # Build the right-charge and wrong-charge D* collections.
        # The right-charge collection is used for the nominal J/psi + D* candidate selection.
        # The wrong-charge collection can be used later as a control sample for combinatorial background.

        dstar_right_charge = Dstar[~Dstar.wrg_chg]
        dstar_wrong_charge = Dstar[Dstar.wrg_chg]
        
        #print(f'Dstar - right: {dstar_right_charge.deltamr}')
        #rint(f'Dstar - wrong: {dstar_wrong_charge.deltamr}')
        # Save the pre-association J/psi and D* candidate pools for the data-driven DPS mixing.
        # These objects have passed the individual J/psi and D* selections, but they have not yet
        # been required to form a good common-vertex J/psi-D* association.
        # This avoids building the DPS template only from objects already selected as associated pairs.
        
        # Pre-association pools for DPS mixing
        output['MixingInput']['jpsi_pre_pt']   += to_col(Dimu.pt)
        output['MixingInput']['jpsi_pre_eta']  += to_col(Dimu.eta)
        output['MixingInput']['jpsi_pre_phi']  += to_col(Dimu.phi)
        output['MixingInput']['jpsi_pre_rap']  += to_col(Dimu.rap)
        output['MixingInput']['jpsi_pre_mass'] += to_col(Dimu.mass)
        output['MixingInput']['jpsi_pre_dl']   += to_col(Dimu.dl)

        output['MixingInput']['dstar_pre_pt']       += to_col(dstar_right_charge.pt)
        output['MixingInput']['dstar_pre_eta']      += to_col(dstar_right_charge.eta)
        output['MixingInput']['dstar_pre_phi']      += to_col(dstar_right_charge.phi)
        output['MixingInput']['dstar_pre_rap']      += to_col(dstar_right_charge.rap)
        output['MixingInput']['dstar_pre_mass']     += to_col(dstar_right_charge.mass)

        # D0-from-D* variables, still before J/psi-D* association
        output['MixingInput']['dstar_pre_d0cosphi'] += to_col(dstar_right_charge.D0cosphi)
        output['MixingInput']['dstar_pre_d0mass']   += to_col(dstar_right_charge.D0mass)
        output['MixingInput']['dstar_pre_d0pt']     += to_col(dstar_right_charge.D0pt)
        output['MixingInput']['dstar_pre_d0dl']     += to_col(dstar_right_charge.D0dl)
        output['MixingInput']['dstar_pre_d0dlsig'] += to_col(dstar_right_charge.D0dlSig)
        
        ############### Dimu + OpenCharm associations
        # Build the nominal J/psi + D* associated candidate collection.
        # The association uses the index stored in the NanoAODPlus object and then applies
        # the common-vertex probability requirement used in the analysis selection.
        # This collection defines the real data distribution H_data for the DPS/SPS decomposition.

        DimuDstar = association(Dimu, dstar_right_charge)
        DimuDstar_wrong = association(Dimu, dstar_wrong_charge)
        
        DimuDstar = DimuDstar[DimuDstar.slot1.associationProb > 0.0]
        DimuDstar_wrong = DimuDstar_wrong[DimuDstar_wrong.slot1.associationProb > 0.0]
        
        DimuDstar = DimuDstar[ak.fill_none(DimuDstar.slot0.pt, -1) > -1]
        DimuDstar_wrong = DimuDstar_wrong[ak.fill_none(DimuDstar_wrong.slot0.pt, -1) > -1]
        # Build the four-vector of the associated J/psi-D* system.
        # This is used to compute pair-level observables such as invariant mass and transverse momentum.

        DimuDstar_p4 = ak.zip({'x': DimuDstar.cand.x, 
                               'y': DimuDstar.cand.y,
                               'z': DimuDstar.cand.z,
                               't': DimuDstar.cand.t}, with_name="LorentzVector")
        
        DimuDstar_wrong_p4 = ak.zip({'x': DimuDstar_wrong.cand.x, 
                               'y': DimuDstar_wrong.cand.y,
                               'z': DimuDstar_wrong.cand.z,
                               't': DimuDstar_wrong.cand.t}, with_name="LorentzVector")

        # Final associated data pairs: this is H_data for the mixing method
        # Compute the pair-level variables used in the DPS/SPS data-driven method.
        # Delta y measures the rapidity separation between the J/psi and the D*.
        # Delta phi is computed in the physical range [0, pi] using the canonical atan2 definition.

        pair_data_dy = abs(DimuDstar.slot0.rap - DimuDstar.slot1.rap)

        pair_data_dphi = np.abs(
            np.arctan2(
                np.sin(DimuDstar.slot0.phi - DimuDstar.slot1.phi),
                np.cos(DimuDstar.slot0.phi - DimuDstar.slot1.phi),
            )
        )
        # Save the final associated J/psi-D* pair observables.
        # These arrays define the real data template H_data(Delta y, Delta phi),
        # to be compared later with the mixed-event DPS template.

        # Final associated J/psi-D* pair observables.
        # These arrays define the real data template H_data after the J/psi-D* association.

        output['MixingInput']['pair_data_dy']   += to_col(pair_data_dy)
        output['MixingInput']['pair_data_dphi'] += to_col(pair_data_dphi)
        output['MixingInput']['pair_data_mass'] += to_col(DimuDstar_p4.mass)

        # J/psi variables after association
        output['MixingInput']['pair_data_jpsi_pt']    += to_col(DimuDstar.slot0.pt)
        output['MixingInput']['pair_data_jpsi_eta']   += to_col(DimuDstar.slot0.eta)
        output['MixingInput']['pair_data_jpsi_phi']   += to_col(DimuDstar.slot0.phi)
        output['MixingInput']['pair_data_jpsi_rap']   += to_col(DimuDstar.slot0.rap)
        output['MixingInput']['pair_data_jpsi_mass']  += to_col(DimuDstar.slot0.mass)
        output['MixingInput']['pair_data_jpsi_dl']    += to_col(DimuDstar.slot0.dl)
        output['MixingInput']['pair_data_jpsi_dlsig'] += to_col(DimuDstar.slot0.dlSig)

        # D* variables after association
        output['MixingInput']['pair_data_dstar_pt']      += to_col(DimuDstar.slot1.pt)
        output['MixingInput']['pair_data_dstar_eta']     += to_col(DimuDstar.slot1.eta)
        output['MixingInput']['pair_data_dstar_phi']     += to_col(DimuDstar.slot1.phi)
        output['MixingInput']['pair_data_dstar_rap']     += to_col(DimuDstar.slot1.rap)
        output['MixingInput']['pair_data_dstar_mass']    += to_col(DimuDstar.slot1.mass)
        output['MixingInput']['pair_data_dstar_deltamr'] += to_col(DimuDstar.slot1.deltamr)

        # D0-from-D* variables after association
        output['MixingInput']['pair_data_dstar_d0cosphi'] += to_col(DimuDstar.slot1.D0cosphi)
        output['MixingInput']['pair_data_dstar_d0mass']   += to_col(DimuDstar.slot1.D0mass)
        output['MixingInput']['pair_data_dstar_d0pt']     += to_col(DimuDstar.slot1.D0pt)
        output['MixingInput']['pair_data_dstar_d0dl']     += to_col(DimuDstar.slot1.D0dl)
        output['MixingInput']['pair_data_dstar_d0dlsig']  += to_col(DimuDstar.slot1.D0dlSig)

        # D0 DCA, already computed earlier as Dstar['D0dca']
        output['MixingInput']['pair_data_dstar_d0dca'] += to_col(DimuDstar.slot1.D0dca)

        # Association variables
        output['MixingInput']['pair_data_associationProb'] += to_col(DimuDstar.slot1.associationProb)
        output['MixingInput']['pair_data_associationchi2'] += to_col(DimuDstar.slot1.associationchi2)

        # Optional diagnostics
        output['MixingInput']['pair_data_dstar_promptFlag'] += to_col(DimuDstar.slot1.promptFlag)
        output['MixingInput']['pair_data_dstar_pisdz']      += to_col(DimuDstar.slot1.pisdz)
        ############### Leading and Trailing muon separation Gen_particles
        leading_mu = (Muon.slot0.pt > Muon.slot1.pt)
        Muon_lead = ak.where(leading_mu, Muon.slot0, Muon.slot1)
        Muon_trail = ak.where(~leading_mu, Muon.slot0, Muon.slot1)
        
        
        # Variables for histogram
        jpsi_mass = ak.flatten(DimuDstar.slot0.mass)
        jpsi_pt = ak.flatten(DimuDstar.slot0.pt)
        jpsi_eta = ak.flatten(DimuDstar.slot0.eta)
        
        jpsi_phi = ak.flatten(DimuDstar.slot0.phi)
        jpsi_rap = ak.flatten(DimuDstar.slot0.rap)
        jpsi_dlsig = ak.flatten(DimuDstar.slot0.dlSig)
        jpsi_dl = ak.flatten(DimuDstar.slot0.dl)

        # Dstar variables
        dstar_deltamr = ak.flatten(DimuDstar.slot1.deltamr)
        dstar_wrong_deltamr = ak.flatten(DimuDstar_wrong.slot1.deltamr)
        dstar_pt = ak.flatten(DimuDstar.slot1.pt)
        dstar_eta = ak.flatten(DimuDstar.slot1.eta)
        dstar_phi = ak.flatten(DimuDstar.slot1.phi)
        dstar_rap = ak.flatten(DimuDstar.slot1.rap)
        dstar_d0pt = ak.flatten(DimuDstar.slot1.D0pt)
        dstar_d0cosphi = ak.flatten(DimuDstar.slot1.D0cosphi)
        dstar_d0dl = ak.flatten(DimuDstar.slot1.D0dl)
        dstar_d0dlsig = ak.flatten(DimuDstar.slot1.D0dlSig)
        dstar_d0cda = ak.flatten(DimuDstar.slot1.D0dca)
        dstar_Kpt = ak.flatten(DimuDstar.slot1.Kpt)
        dstar_Kchindof = ak.flatten(DimuDstar.slot1.Kchindof)
        dstar_KnValid = ak.flatten(DimuDstar.slot1.KnValid)
        dstar_Kdxy = ak.flatten(DimuDstar.slot1.Kdxy)
        dstar_Kdz = ak.flatten(DimuDstar.slot1.Kdz)
        dstar_pispt = ak.flatten(DimuDstar.slot1.pispt)
        dstar_pischindof = ak.flatten(DimuDstar.slot1.pischindof)
        dstar_pisnValid = ak.flatten(DimuDstar.slot1.pisnValid)
              
        # JpsiDstar variables
        jpsi_dstar_deltarap = ak.flatten(DimuDstar.deltarap) # Takes module
        jpsi_dstar_deltarap_abs = abs(jpsi_dstar_deltarap)

        jpsi_dstar_deltaphi= ak.flatten(DimuDstar.deltaphi)
        jpsi_dstar_mass = ak.flatten(DimuDstar_p4.mass) 
        
        ###### New variables: test
        jpsi_dstar_asso_prob = ak.flatten(DimuDstar.slot1.associationProb)
        jpsi_dstar_asso_chi2 = ak.flatten(DimuDstar.slot1.associationchi2)
        jpsi_dstard0_dz = ak.flatten(DimuDstar.slot0.z - DimuDstar.slot1.D0z)
        dstar_prompt_flag = ak.flatten(DimuDstar.slot1.promptFlag)
        dstar_pisdz = ak.flatten(DimuDstar.slot1.pisdz)
        
        DimuDstar['deltamass'] = DimuDstar_p4.mass - DimuDstar.slot0.mass - DimuDstar.slot1.mass
        jpsi_dstar_deltamass = ak.flatten(DimuDstar.deltamass)
      
        # Histograms
        
        ## Jpsi
        output['JpsiDstar']['Jpsi_mass'].fill(mass=jpsi_mass)
        output['JpsiDstar']['Jpsi_p'].fill(pt=jpsi_pt,
                                           eta=jpsi_eta,
                                           phi=jpsi_phi,)
        output['JpsiDstar']['Jpsi_rap'].fill(rap=jpsi_rap)
        output['JpsiDstar']['Jpsi_dl'].fill(dl=jpsi_dl)
        
        # Dstar       
        output['JpsiDstar']['Dstar_deltamr'].fill(chg='right charge', deltamr=dstar_deltamr,)
        output['JpsiDstar']['Dstar_deltamr_wrong'].fill(chg='wrong_charge', deltamr=dstar_wrong_deltamr)
        output['JpsiDstar']['Dstar_p'].fill(chg='right charge', pt=dstar_pt,
                                                                eta=dstar_eta,
                                                                phi=dstar_phi,)
        output['JpsiDstar']['Dstar_rap'].fill(chg='right charge', rap=dstar_rap,)
        output['JpsiDstar']['Dstar_D0dca'].fill(chg='right charge', d0dca=dstar_d0cda,)
        
        # JpsiDstar
        output['JpsiDstar']['JpsiDstar_mass'].fill(mass=jpsi_dstar_mass,)
        #output['JpsiDstar']['JpsiDstar_pt'].fill(pt=jpsi_dstar_pt,)
        output['JpsiDstar']['JpsiDstar_deltaphi'].fill(deltaphi=jpsi_dstar_deltaphi,)
        output['JpsiDstar']['JpsiDstar_deltarap'].fill(deltarap=jpsi_dstar_deltarap_abs,)
        output['JpsiDstar']['JpsiDstar_deltamass'].fill(dmass=jpsi_dstar_deltamass)
        
        ###### New histograms
        output['JpsiDstar']['Dstar_associationProb'].fill(chg='right charge', associationprob=jpsi_dstar_asso_prob,)
        output['JpsiDstar']['Dstar_associationchi2'].fill(chg='right charge', associationchi2=jpsi_dstar_asso_chi2,)
        output['JpsiDstar']['Jpsi_dstard0_deltaz'].fill(chg='right charge', jpsi_dstard0_dz=jpsi_dstard0_dz,)
        output['JpsiDstar']['Dstar_promptFlag'].fill(chg='right charge', dstar_prompt_flag=dstar_prompt_flag,)
        output['JpsiDstar']['Dstar_pisdz'].fill(chg='right charge', pisdz=dstar_pisdz,)
        
        return output

    def postprocess(self, accumulator):
        return accumulator


def parse_args():
    parser = argparse.ArgumentParser(description="Run JPsi+Dstar data preparation with coffea.")
    parser.add_argument("--filelist", required=True, help="Text file with ROOT file paths or /store paths.")
    parser.add_argument("--tag", required=True, help="Dataset/output tag, e.g. 2017B_0001_part0000.")
    parser.add_argument("--output-dir", default=".", help="Directory where the .coffea file will be written.")
    parser.add_argument("--workers", type=int, default=4, help="Number of futures_executor workers.")
    parser.add_argument("--chunksize", type=int, default=360000, help="coffea chunksize.")
    parser.add_argument("--max-files", type=int, default=None, help="Optional cap for quick local tests.")
    parser.add_argument("--redirector", default="k8s-redir.ultralight.org:1094", help="XRootD redirector for /store paths.")
    parser.add_argument("--disable-hlt", action="store_true", help="Disable the HLT_Dimuon25_Jpsi cut.")
    return parser.parse_args()


def main():
    global ENABLE_HLT
    args = parse_args()
    ENABLE_HLT = not args.disable_hlt

    print_environment()
    print("ENABLE_HLT:", ENABLE_HLT)

    files = read_filelist(args.filelist, args.redirector, args.max_files)
    os.makedirs(args.output_dir, exist_ok=True)
    output_file = os.path.join(args.output_dir, f"output_mixing_{args.tag}.coffea")

    print("Dataset tag:", args.tag)
    print("Filelist   :", args.filelist)
    print("N files    :", len(files))
    print("First file :", files[0])
    print("Output     :", output_file)

    data = {args.tag: files}
    tstart = time.time()

    output = processor.run_uproot_job(
        data,
        treename="Events",
        processor_instance=EventSelectorProcessor(),
        executor=processor.futures_executor,
        executor_args={
            "schema": BaseSchema,
            "workers": args.workers,
            "skipbadfiles": True,
        },
        chunksize=args.chunksize,
    )

    print(f"Process finished in: {(time.time() - tstart)/60:.2f} min")

    save(output, output_file)
    print(f"Saved output file: {output_file}")

    mix = output["MixingInput"]
    print("Mixing input sizes:")
    print(f"Pre-association J/psi pool : {len(mix['jpsi_pre_pt'].value)}")
    print(f"Pre-association D* pool    : {len(mix['dstar_pre_pt'].value)}")
    print(f"Final associated pairs     : {len(mix['pair_data_dy'].value)}")


if __name__ == "__main__":
    main()

