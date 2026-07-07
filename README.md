# Efficiency: $J/\psi$ D* - Run2

This repository contains the code for calculating the efficiency for $J/\psi$ D* analyses using DPS/SPS Monte Carlo samples.

Files to modify:

* **nanoAODplus_processor/EfficiencyProcessor.py**
* **config/efficiency.yaml**
* **nanoAODplus_efficiency.py**

To run:

```
python nanoAODplus_efficiency.py -y 2016APV -p
python nanoAODplus_efficiency.py -y 2016 -p
python nanoAODplus_efficiency.py -y 2017 -p
python nanoAODplus_efficiency.py -y 2018 -p
```
