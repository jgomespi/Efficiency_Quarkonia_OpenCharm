import numpy as np

muon_cols = [
    'Muon_charge', 'Muon_dxy', 'Muon_dxyErr', 'Muon_dz', 'Muon_dzErr', 'Muon_eta', 'Muon_isGlobal', 'Muon_mass',
    'Muon_phi', 'Muon_pt', 'Muon_ptErr', 'Muon_softId', 'Muon_vtxIdx', 'Muon_vtxFlag', 'Muon_simIdx',
    ]

dimu_cols = [
    'Dimu_pt', 'Dimu_eta', 'Dimu_phi', 'Dimu_rap', 'Dimu_mass', 'Dimu_charge', 'Dimu_vtxIdx', 'Dimu_chi2', 'Dimu_dl',
    'Dimu_dlErr', 'Dimu_dlSig', 'Dimu_cosphi', 'Dimu_x', 'Dimu_y', 'Dimu_z', 'Dimu_t1muIdx', 'Dimu_t2muIdx',
    #'Dimu_Covxx', 'Dimu_Covyx', 'Dimu_Covzx', 'Dimu_Covyy', 'Dimu_Covzy', 'Dimu_Covzz',
]

d0_cols = [
    'D0_pt', 'D0_eta', 'D0_phi', 'D0_rap', 'D0_mass12', 'D0_mass21', 'D0_vtxIdx', 'D0_chi2', 'D0_dl', 'D0_dlErr', 'D0_dlSig',
    'D0_cosphi', 'D0_x', 'D0_y', 'D0_z', 'D0_hasMuon',
    #'D0_Covxx', 'D0_Covyx', 'D0_Covzx', 'D0_Covyy', 'D0_Covzy', 'D0_Covzz',
    'D0_t1pt', 'D0_t1eta', 'D0_t1phi', 'D0_t1chindof', 'D0_t1nValid', 'D0_t1nPix', 'D0_t1dxy', 'D0_t1dz', 'D0_t1chg', 
    'D0_t2pt', 'D0_t2eta', 'D0_t2phi', 'D0_t2chindof', 'D0_t2nValid', 'D0_t2nPix', 'D0_t2dxy', 'D0_t2dz', 'D0_t2chg',
]

dstar_cols = [
    'Dstar_pt', 'Dstar_eta', 'Dstar_phi', 'Dstar_rap', 'Dstar_deltam', 'Dstar_deltamr', 'Dstar_vtxIdx', 'Dstar_hasMuon',
    'Dstar_D0pt', 'Dstar_D0eta', 'Dstar_D0phi', 'Dstar_D0mass', 'Dstar_D0chi2', 'Dstar_D0dl', 'Dstar_D0dlErr', 'Dstar_simIdx',
    'Dstar_D0dlSig', 'Dstar_D0cosphi', 'Dstar_D0x', 'Dstar_D0y', 'Dstar_D0z', 'Dstar_D0recIdx', 
    'Dstar_Kpt', 'Dstar_Keta', 'Dstar_Kphi', 'Dstar_KvtxIdx', 'Dstar_Kchindof', 'Dstar_KnValid', 'Dstar_KnPix', 'Dstar_Kdxy',
    'Dstar_Kdz', 'Dstar_Kchg',
    'Dstar_pipt', 'Dstar_pieta', 'Dstar_piphi', 'Dstar_pivtxIdx', 'Dstar_pichindof', 'Dstar_pinValid', 'Dstar_pinPix',
    'Dstar_pidxy', 'Dstar_pidz', 'Dstar_pichg',
    'Dstar_pispt', 'Dstar_piseta', 'Dstar_pisphi', 'Dstar_pisvtxIdx', 'Dstar_pischindof', 'Dstar_pisnValid', 'Dstar_pisnPix',
    'Dstar_pisdxy', 'Dstar_pisdz',
    'Dstar_pisptr', 'Dstar_pisetar', 'Dstar_pisphir', 'Dstar_pischir',
    'Dstar_associationchi2', 'Dstar_associationIdx', 'Dstar_associationProb',
]

pvtx_cols = [
    'PVtx_isGood', 'PVtx_x', 'PVtx_y', 'PVtx_z', 'PVtx_Id', 'PVtx_sumPt', 'PVtx_ntrk',
    #'PVtx_Covxx', 'PVtx_Covyx', 'PVtx_Covzx', 'PVtx_Covyy', 'PVtx_Covzy', 'PVtx_Covzz',
]

hlt_cols = {
    '2016': ['HLT_Dimuon13_Upsilon', 'HLT_Dimuon8_Upsilon_Barrel'],
    '2017': ['HLT_Dimuon10_Upsilon_Barrel_Seagulls', 'HLT_Dimuon12_Upsilon_eta1p5', 'HLT_Dimuon24_Upsilon_noCorrL1'],
    '2018': [
        'HLT_Dimuon10_Upsilon_Barrel_Seagulls', 'HLT_Dimuon12_Upsilon_eta1p5', 'HLT_Dimuon12_Upsilon_y1p4',
        'HLT_Dimuon24_Upsilon_noCorrL1'
    ]
}

gen_part_cols = [
    'GenPart_eta', 'GenPart_genPartIdxMother', 'GenPart_mass', 'GenPart_pdgId', "GenPart_phi", "GenPart_pt", 
    'GenPart_status', 'GenPart_Id', 'GenPart_parpdgId', 'GenPart_sparpdgId', 'GenPart_numberOfDaughters', 
    'GenPart_nstchgdaug', 'GenPart_vx', 'GenPart_vy', 'GenPart_vz', 'GenPart_mvx', 'GenPart_mvy', 'GenPart_mvz', 
    'GenPart_recIdx',
]

def get_vars_dict(events, col_list):
    dict = {}
    col = ''
    for c in col_list:
        col = c[c.find("_")+1:]
        if len(events[c]) == 0:
            dict[col] = np.array([])
        else:
            dict[col] = events[c]

        if not c[:c.find("_")] == 'PVtx':
            if col == 'x' or col == 'y' or col == 'z':
                col = 'v' + col

        if len(events[c]) == 0:
            dict[col] = np.array([])
        else:
            dict[col] = events[c]
    return dict

def get_hlt(events, cols):
    dict = {}
    for col in cols:
        if not col in events.fields:
            if len(events['run']) == 0:
                dict[col] = np.array([])
            else:
                dict[col] = np.zeros(len(events), dtype=bool)
        else:
            if len(events[col]) == 0:
                dict[col] = np.array([])
            else:
                dict[col] = events[col]
    return dict
