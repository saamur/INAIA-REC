# INAIA-REC

This repository contains the implementation of **INAIA** – INcentive Allocation for Interest Alignment – along with several baseline methods.

The current implementation focuses on a specific application: a Renewable Energy Community (REC) setting, as defined by EU law and implemented in the Italian regulatory framework. In this setting, INAIA is used to train a central agent responsible for distributing community-level incentives among participants.

## Repository structure

- ``algorithms/``: Source code for INAIA and baseline algorithms.
- ``ernestogym/``: Environment implementation, including the battery digital twin used in simulation.
- ``experiments/``:  Scripts to reproduce the results presented in the paper.
- ``notebooks/``: Jupyter notebooks for visualizing experimental outcomes.

## Conda environment

To create a Conda environment with all packages needed in this repo, run:

```bash
conda env create -f conda_environment.yml
```

To activate it, run:

```bash
conda activate INAIA-REC
```

## Running an Example Experiment

To reproduce the reference scenario presented in the paper (three active nodes and one passive node) with the REC agent trained with INAIA, you can run the following script from the project root:

```bash
python experiments/3_active_1_passive/inaia.py
```

The trained models will be automatically saved in the ``trained_agents/`` directory, inside a subfolder named with the current date and time in the format ``YYYYMMDD_HHMMSS`` (e.g., ``trained_agents/20250601_120000/``).