import awkward as ak
import numpy as np
import coffea.processor as processor
from coffea.lookup_tools import extractor
import json
import correctionlib

from hist import Hist
import hist

from coffea.nanoevents.methods import candidate
ak.behavior.update(candidate.behavior)

from tools.collections import *
from tools.utils import D0_PDG_MASS, remove_none, association

pileup_file = '/afs/cern.ch/work/m/mabarros/public/CMSSW_10_6_12/src/analysis_monte_carlo/efficiencies_per_evt/data/corrections/pile_up_reweight_{year}.root'
#pileup_file_new = '/afs/cern.ch/work/m/mabarros/public/CMSSW_10_6_12/src/analysis_monte_carlo/efficiencies_per_evt/data/corrections/puWeights_{year}_UL.json'
muon_reco_file = '/afs/cern.ch/work/m/mabarros/public/CMSSW_10_6_12/src/analysis_monte_carlo/efficiencies_per_evt/data/corrections/Efficiency_muon_generalTracks_Run{year}_UL_trackerMuon.json'
muon_id_file = '/afs/cern.ch/work/m/mabarros/public/CMSSW_10_6_12/src/analysis_monte_carlo/efficiencies_per_evt/data/corrections/Efficiency_muon_trackerMuon_Run{year}_UL_ID.json'

import awkward as ak
import numpy as np


def get_weight(evaluator, Muon, Dimu, PVtx):
    
    pileup_weight = evaluator['weight_histogram'](ak.num(PVtx))[ak.num(Dimu)>0] # Kevin's: pileup_weight = evaluator['pileup'](ak.num(PVtx))[ak.num(Dimu)>0]
    muon = Muon[ak.num(Dimu)>0]
    mu0_reco_weight = evaluator['NUM_TrackerMuons_DEN_genTracks/abseta_pt_value'](np.absolute(muon.slot0.eta[:,0]), muon.slot0.pt[:,0])
    mu1_reco_weight = evaluator['NUM_TrackerMuons_DEN_genTracks/abseta_pt_value'](np.absolute(muon.slot1.eta[:,0]), muon.slot1.pt[:,0])
    mu0_id_weight = evaluator['NUM_SoftID_DEN_TrackerMuons/abseta_pt_value'](np.absolute(muon.slot0.eta[:,0]), muon.slot0.pt[:,0])
    mu1_id_weight = evaluator['NUM_SoftID_DEN_TrackerMuons/abseta_pt_value'](np.absolute(muon.slot1.eta[:,0]), muon.slot1.pt[:,0])
    weight = pileup_weight*mu0_reco_weight*mu1_reco_weight*mu0_id_weight*mu1_id_weight
    """ print(pileup_weight*mu0_reco_weight*mu1_reco_weight*mu0_id_weight*mu1_id_weight)
    for idx, i in enumerate(weight):
        print(muon.slot0.eta[idx,0], muon.slot0.pt[idx,0], dimu.pt[idx, 0], dimu.eta[idx,0])
        print(weight[idx], pileup_weight[idx], mu0_reco_weight[idx], mu1_reco_weight[idx], mu0_id_weight[idx], mu0_id_weight[idx]) """
    
    return weight


class EfficiencyProcessor(processor.ProcessorABC):
    def __init__(self, config, year, dimu_cut=0):
        self.config = config
        self.year = year
        self.dimu_cut = dimu_cut

        Gen_Dimu = (
            Hist.new
            .Variable(config['bins_pt_dimu'], name='pt', label=r'$p_{T}$ Gen $\mu^+\mu^-$ [GeV/c] ')
            .Variable(config['bins_rap_dimu'], name='rap', label=r'$|y|$ Gen $\mu^+\mu^-$')
            .Weight()
        )

        Reco_Dimu = (
            Hist.new
            .Variable(config['bins_pt_dimu'], name='pt', label=r'$p_{T}$ Reco $\mu^+\mu^-$ [GeV/c]')
            .Variable(config['bins_rap_dimu'], name='rap', label=r'$|y|$ Reco $\mu^+\mu^-$')
            .Weight()
        )

        Gen_Dstar = (
            Hist.new
            .Variable(config['bins_pt_dstar'], name='pt', label=r'$p_{T}$ Gen $D^*$ [GeV/c]')
            .Variable(config['bins_rap_dstar'], name='rap', label=r'$|y|$ Gen $D^*$')
            .Weight()
        )

        Reco_Dstar = (
            Hist.new
            .Variable(config['bins_pt_dstar'], name='pt', label=r'$p_{T}$ Reco $D^*$ [GeV/c]')
            .Variable(config['bins_rap_dstar'], name='rap', label=r'$|y|$ Reco $D^*$')
            .Weight()
        )

        Cuts_Dimu = (
            Hist.new
            .Variable(config['bins_pt_dimu'], name='pt', label=r'$p_{T} \mu^+\mu^-$ after sel. cuts [GeV/c]')
            .Variable(config['bins_rap_dimu'], name='rap', label=r'$|y| \mu^+\mu^-$ after sel. cuts')
            .Weight()
        )

        Cuts_Dstar = (
            Hist.new
            .Variable(config['bins_pt_dstar'], name='pt', label=r'$p_{T} D^*$ after sel. cuts [GeV/c]')
            .Variable(config['bins_rap_dstar'], name='rap', label=r'$|y| D^*$ after sel. cuts')
            .Weight()
        )

        Trigger_Dimu = (
            Hist.new
            .Variable(config['bins_pt_dimu'], name='pt', label=r'$p_{T} \mu^+\mu^-$ after trigger cuts [GeV/c]')
            .Variable(config['bins_rap_dimu'], name='rap', label=r'$|y| \mu^+\mu^-$ after trigger cuts')
            .Weight()
        )

        Num_Asso = (
            Hist.new
            .Variable(config['bins_pt_dimu'], name='pt_dimu', label=r'$p_{T} \mu^+\mu^-$ after asso. cut [GeV/c]')
            .Variable(config['bins_rap_dimu'], name='rap_dimu', label=r'$|y| \mu^+\mu^-$ after asso. cut')
            .Variable(config['bins_pt_dstar'], name='pt_dstar', label=r'$p_{T} D^*$ after asso. cut [GeV/c]')
            .Variable(config['bins_rap_dstar'], name='rap_dstar', label=r'$|y| D^*$ after asso. cut')
            .Weight()
        )

        Den_Asso = (
            Hist.new
            .Variable(config['bins_pt_dimu'], name='pt_dimu', label=r'$p_{T} \mu^+\mu^-$ before asso. cut [GeV/c]')
            .Variable(config['bins_rap_dimu'], name='rap_dimu', label=r'$|y| \mu^+\mu^-$ before asso. cut')
            .Variable(config['bins_pt_dstar'], name='pt_dstar', label=r'$p_{T} D^*$ before asso. cut [GeV/c]')
            .Variable(config['bins_rap_dstar'], name='rap_dstar', label=r'$|y| D^*$ before asso. cut')
            .Weight()
        )
               
        self._accumulator = {
            'Gen_Dimu': Gen_Dimu,
            'Reco_Dimu': Reco_Dimu,
            'Gen_Dstar': Gen_Dstar,
            'Reco_Dstar': Reco_Dstar,
            'Cuts_Dimu': Cuts_Dimu,
            'Cuts_Dstar': Cuts_Dstar,
            'Trigger_Dimu': Trigger_Dimu,
            'Num_Asso': Num_Asso,
            'Den_Asso': Den_Asso,
            'cutflow' : processor.defaultdict_accumulator(int),
            #'Num_Evts': Num_Evts,
            #'Num_Evts': Num_Evts,
        }

    @property
    def accumulator(self):
        return self._accumulator

    def process(self, events):
        output = self.accumulator
        
        # test if there are any events in the file
        if len(events) == 0:
            return output

        ############### Get All the interesting candidates from NTuples
        Dimu = ak.zip({**get_vars_dict(events, dimu_cols)}, with_name="PtEtaPhiMCandidate")
        Muon_all = ak.zip({**get_vars_dict(events, muon_cols)}, with_name="PtEtaPhiMCandidate")
        Dstar = ak.zip({'mass': (events.Dstar_D0mass + events.Dstar_deltamr),
                        'charge': events.Dstar_pischg,
                        **get_vars_dict(events, dstar_cols)}, 
                        with_name="PtEtaPhiMCandidate")
        GenPart = ak.zip({**get_vars_dict(events, gen_part_cols)}, with_name="PtEtaPhiMCandidate")
        PVtx = ak.zip({**get_vars_dict(events, pvtx_cols)})
        HLT = ak.zip({**get_hlt(events, [self.config['trigger'][self.year]])})

        output['cutflow']['Number of events'] += len(events)

        # GenParticles for Dimu and for Dstar
        GenPart_Muon = GenPart[(np.absolute(GenPart.pdgId) == 13) & (GenPart.genPartIdxMother > -1)]

        # Corrections for Muon and Pileup
        ext = extractor()
        ext.add_weight_sets([f"weight_histogram weight_histogram {pileup_file.format(year=self.year)}"]) # Weight name in Kevin's code: ext.add_weight_sets([f"pileup h_weights {pileup_file.format(year=self.year)}"])     
        # Adds muon ID anc RECO corrections
        ext.add_weight_sets([f"* * {muon_reco_file.format(year=self.year)}"])
        ext.add_weight_sets([f"* * {muon_id_file.format(year=self.year)}"])
        ext.finalize()
        evaluator = ext.make_evaluator()

        # Pile-up correction from json files
        """ pileup_corrector = correctionlib.CorrectionSet.from_file(pileup_file_new.format(year=self.year))
        if self.year == '2016APV' or self.year == '2016':
            pileup_correction = pileup_corrector["Collisions16_UltraLegacy_goldenJSON"]
        elif self.year == '2017':
            pileup_correction = pileup_corrector["Collisions17_UltraLegacy_goldenJSON"]
        elif self.year == '2018':
            pileup_correction = pileup_corrector["Collisions18_UltraLegacy_goldenJSON"] """
            
        ############### Acceptance

        if self.config['particle'] == 'J/psi':
            gen_pdgid = (GenPart_Muon.parpdgId == 443)
        elif self.config['particle'] == 'Y':
            gen_pdgid = (GenPart_Muon.parpdgId == 553) | (GenPart_Muon.parpdgId == 100553) | (GenPart_Muon.parpdgId == 200553)
        
        GenPart_Muon = GenPart_Muon[gen_pdgid]
        GenPart_Muon = GenPart_Muon[GenPart_Muon.pt > self.config['muon_pt_min']]
        GenPart_Muon = GenPart_Muon[np.absolute(GenPart_Muon.eta) < self.config['muon_eta']]
        GenPart_Muon = ak.combinations(GenPart_Muon, 2)
        leading_mu = (GenPart_Muon.slot0.pt > GenPart_Muon.slot1.pt)
        GenPart_Muon = ak.zip({'0': ak.where(leading_mu, GenPart_Muon.slot0, GenPart_Muon.slot1), '1': ak.where(~leading_mu, GenPart_Muon.slot0, GenPart_Muon.slot1)})
        GenPart_Muon = GenPart_Muon[GenPart_Muon.slot0.genPartIdxMother == GenPart_Muon.slot1.genPartIdxMother]
        
        GenPart_Dimu = GenPart[GenPart_Muon.slot0.genPartIdxMother]
        GenPart_Dimu = GenPart_Dimu[(GenPart_Dimu.pt > max(self.config['dimu_pt_min'], self.dimu_cut)) & (GenPart_Dimu.pt < self.config['dimu_pt_max'])]
        GenPart_Dimu['rap'] = np.log((GenPart_Dimu.t+GenPart_Dimu.z)/(GenPart_Dimu.t-GenPart_Dimu.z))/2       
        GenPart_Dimu = GenPart_Dimu[np.absolute(GenPart_Dimu.rap) < self.config['dimu_rap']]   
        arg_sort = ak.argsort(GenPart_Dimu.pt, axis=1, ascending=False)
        GenPart_Dimu = GenPart_Dimu[arg_sort]    

        GenPart_D0 = GenPart[(np.absolute(GenPart.pdgId) == 421) & (np.absolute(GenPart.parpdgId) == 413)]
        GenPart_Dstar = GenPart[GenPart_D0.genPartIdxMother]
        GenPart_Dstar = GenPart_Dstar[(GenPart_Dstar.pt > self.config['dstar_pt_min']) & (GenPart_Dstar.pt < self.config['dstar_pt_max'])]
        GenPart_Dstar['rap'] = np.log((GenPart_Dstar.t+GenPart_Dstar.z)/(GenPart_Dstar.t-GenPart_Dstar.z))/2
        GenPart_Dstar = GenPart_Dstar[np.absolute(GenPart_Dstar.rap) < self.config['dstar_rap']]
        arg_sort = ak.argsort(GenPart_Dstar.pt, axis=1, ascending=False)
        GenPart_Dstar = GenPart_Dstar[arg_sort]  

        Dimu = ak.mask(Dimu, Dimu.charge == 0)
        Dimu = ak.mask(Dimu, (Dimu.mass > self.config['dimu_mass_low']) & (Dimu.mass < self.config['dimu_mass_high']))
        Muon = ak.zip({'0': Muon_all[Dimu.t1muIdx], '1': Muon_all[Dimu.t2muIdx]})
        leading_mu = (Muon.slot0.pt > Muon.slot1.pt)
        Muon = ak.zip({'0': ak.where(leading_mu, Muon.slot0, Muon.slot1), '1': ak.where(~leading_mu, Muon.slot0, Muon.slot1)})

        muon_pt_cut = (Muon.slot0.pt > self.config['muon_pt_min']) & (Muon.slot1.pt > self.config['muon_pt_min'])
        muon_eta_cut = (np.absolute(Muon.slot0.eta) < self.config['muon_eta']) & (np.absolute(Muon.slot1.eta) < self.config['muon_eta'])
        muon_sim_cut = (Muon.slot0.simIdx > -1) & (Muon.slot1.simIdx > -1)
        dimu_pt_cut = (Dimu.pt > max(self.config['dimu_pt_min'], self.dimu_cut)) & (Dimu.pt < self.config['dimu_pt_max'])
        dimu_eta_cut = np.absolute(Dimu.rap) < self.config['dimu_rap']
        reco_cut = muon_eta_cut & muon_pt_cut & muon_sim_cut & dimu_pt_cut & dimu_eta_cut
        Muon = ak.mask(Muon, reco_cut)
        Dimu = ak.mask(Dimu, reco_cut)

        # Dstar cuts
        Dstar = Dstar[~Dstar.hasMuon]
        Dstar = Dstar[Dstar.Kchg != Dstar.pichg]
        Dstar = Dstar[(Dstar.pt > self.config['dstar_pt_min']) & (Dstar.pt < self.config['dstar_pt_max'])]
        Dstar = Dstar[np.absolute(Dstar.rap) < self.config['dstar_rap']]
        arg_sort = ak.argsort(Dstar.pt, axis=1, ascending=False)
        Dstar = Dstar[arg_sort]

        Dstar_sim = Dstar[Dstar.simIdx > -1]

        Dimu_aux = Dimu[remove_none(Dimu.pt)]
        Muon_aux = Muon[remove_none(Dimu.pt)]
        if ak.sum(ak.num(Dimu_aux)) > 0:
            arg_sort = ak.argsort(Dimu_aux.pt, axis=1, ascending=False)
            Dimu_aux = Dimu_aux[arg_sort]
            Muon_aux = Muon_aux[arg_sort]

        # Pile-up and muon ID/RECO corrections
        dimu_weight = get_weight(evaluator, Muon_aux, Dimu_aux, PVtx)
        dstar_weight = evaluator['weight_histogram'](ak.num(PVtx))[ak.num(Dstar_sim)>0]

        output['Gen_Dimu'].fill(
            pt=GenPart_Dimu[ak.num(GenPart_Dimu)>0].pt[:,0], 
            rap=np.absolute(GenPart_Dimu[ak.num(GenPart_Dimu)>0].rap[:,0]),
        )
        output['Reco_Dimu'].fill(
            pt=Dimu_aux[ak.num(Dimu_aux)>0].pt[:,0], 
            rap=np.absolute(Dimu_aux[ak.num(Dimu_aux)>0].rap[:,0]),
            weight=dimu_weight,
        )
        output['Gen_Dstar'].fill(
            pt=GenPart_Dstar[ak.num(GenPart_Dstar)>0].pt[:,0], 
            rap=np.absolute(GenPart_Dstar[ak.num(GenPart_Dstar)>0].rap[:,0]),
        )
        output['Reco_Dstar'].fill(
            pt=Dstar_sim[ak.num(Dstar_sim)>0].pt[:,0], 
            rap=np.absolute(Dstar_sim[ak.num(Dstar_sim)>0].rap[:,0]),
            weight=dstar_weight,
        )

        ############### /Acceptance

        ############### Cuts Efficiency
        soft_id = (Muon.slot0.softId > 0) & (Muon.slot1.softId > 0)
        Dimu = ak.mask(Dimu, soft_id)
        Muon = ak.mask(Muon, soft_id)

        Dstar = Dstar[(Dstar.Kpt > self.config['dstar_track_pt_cut']) & (Dstar.pipt > self.config['dstar_track_pt_cut'])]
        Dstar = Dstar[(Dstar.Kchindof < 2.5) & (Dstar.pichindof < 2.5)]
        Dstar = Dstar[(Dstar.KnValid > 4) & (Dstar.pinValid > 4) & (Dstar.KnPix > 1) & (Dstar.pinPix > 1)]
        Dstar = Dstar[(Dstar.Kdxy < 0.5) & (Dstar.pidxy < 0.5)]
        K_theta = 2 * np.arctan(np.exp(-Dstar.Keta))
        pi_theta = 2 * np.arctan(np.exp(-Dstar.pieta))
        Dstar = Dstar[(Dstar.Kdz < 0.5/np.sin(K_theta)) & (Dstar.pidz < 0.5/np.sin(pi_theta))]

        # pis cuts
        Dstar = Dstar[Dstar.pisptr > 0.3]
        Dstar = Dstar[Dstar.pischir < 3]
        Dstar = Dstar[Dstar.pisnValid > 2]

        # D0 of Dstar cuts
        Dstar = Dstar[Dstar.D0cosphi > self.config['dstar_d0_cosphi']]
        Dstar = Dstar[(Dstar.D0mass < D0_PDG_MASS + self.config['dstar_d0_mass']) & (Dstar.D0mass > D0_PDG_MASS - self.config['dstar_d0_mass'])]
        Dstar = Dstar[Dstar.D0pt > self.config['dstar_d0_pt']]
        Dstar = Dstar[Dstar.D0dlSig > self.config['dstar_d0_dlSig']]

        Dimu_aux = Dimu[remove_none(Dimu.pt)]
        Muon_aux = Muon[remove_none(Dimu.pt)]
        if ak.sum(ak.num(Dimu_aux)) > 0:
            arg_sort = ak.argsort(Dimu_aux.pt, axis=1, ascending=False)
            Dimu_aux = Dimu_aux[arg_sort]
            Muon_aux = Muon_aux[arg_sort]

        # Pile-up and muon ID/RECO corrections
        dimu_weight = get_weight(evaluator, Muon_aux, Dimu_aux, PVtx)
        dstar_weight = evaluator['weight_histogram'](ak.num(PVtx))[ak.num(Dstar)>0]

        output['Cuts_Dimu'].fill(
            pt=Dimu_aux[ak.num(Dimu_aux)>0].pt[:,0], 
            rap=np.absolute(Dimu_aux[ak.num(Dimu_aux)>0].rap[:,0]),
            weight=dimu_weight,
        )
        output['Cuts_Dstar'].fill(
            pt=Dstar[ak.num(Dstar)>0].pt[:,0], 
            rap=np.absolute(Dstar[ak.num(Dstar)>0].rap[:,0]),
            weight=dstar_weight,
        )

        ############### /Cuts Efficiency 

        ############### Trigger Efficiency

        trigger = HLT[self.config['trigger'][self.year]]
        Dimu = Dimu[trigger]
        Muon = Muon[trigger]
        Dstar = Dstar[trigger]
        PVtx = PVtx[trigger]

        Dimu_aux = Dimu[remove_none(Dimu.pt)]
        Muon_aux = Muon[remove_none(Dimu.pt)]
        if ak.sum(ak.num(Dimu_aux)) > 0:
            arg_sort = ak.argsort(Dimu_aux.pt, axis=1, ascending=False)
            Dimu_aux = Dimu_aux[arg_sort]
            Muon_aux = Muon_aux[arg_sort]

        dimu_weight = get_weight(evaluator, Muon_aux, Dimu_aux, PVtx)

        output['Trigger_Dimu'].fill(
            pt=Dimu_aux[ak.num(Dimu_aux)>0].pt[:,0], 
            rap=np.absolute(Dimu_aux[ak.num(Dimu_aux)>0].rap[:,0]),
            weight=dimu_weight,
        )

        ############### /Trigger Efficiency 

        ############### Association Efficiency
        DimuDstar = association(Dimu, Dstar)
        none_cut = remove_none(DimuDstar.slot0.pt)
        DimuDstar = DimuDstar[none_cut]

        Dstar = Dstar[Dstar.associationIdx > -1]
        MuonDstar = ak.zip({'0': Muon[Dstar.associationIdx], '1': Dstar})
        MuonDstar = MuonDstar[none_cut]

        if ak.sum(ak.num(DimuDstar)) > 0:
            arg_sort = ak.argsort(DimuDstar['cand'].pt, axis=1, ascending=False)
            DimuDstar = DimuDstar[arg_sort]
            MuonDstar = MuonDstar[arg_sort]

        weight = get_weight(evaluator, MuonDstar.slot0, DimuDstar.slot1, PVtx)

        output['Den_Asso'].fill(
            pt_dimu=DimuDstar[ak.num(DimuDstar)>0].slot0.pt[:,0], 
            rap_dimu=np.absolute(DimuDstar[ak.num(DimuDstar)>0].slot0.rap[:,0]),
            pt_dstar=DimuDstar[ak.num(DimuDstar)>0].slot1.pt[:,0], 
            rap_dstar=np.absolute(DimuDstar[ak.num(DimuDstar)>0].slot1.rap[:,0]),
            weight=weight,
        )

        DimuDstar = DimuDstar[DimuDstar.slot1.associationProb > self.config['vertex_probability_cut']]
        MuonDstar = MuonDstar[DimuDstar.slot1.associationProb > self.config['vertex_probability_cut']]

        weight = get_weight(evaluator, MuonDstar.slot0, DimuDstar.slot1, PVtx)

        output['Num_Asso'].fill(
            pt_dimu=DimuDstar[ak.num(DimuDstar)>0].slot0.pt[:,0], 
            rap_dimu=np.absolute(DimuDstar[ak.num(DimuDstar)>0].slot0.rap[:,0]),
            pt_dstar=DimuDstar[ak.num(DimuDstar)>0].slot1.pt[:,0], 
            rap_dstar=np.absolute(DimuDstar[ak.num(DimuDstar)>0].slot1.rap[:,0]),
            weight=weight,
        )

        ############### /Association Efficiency

        return output

    def postprocess(self, accumulator):
        return accumulator
