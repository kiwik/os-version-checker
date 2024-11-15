#!/bin/bash

set -ex

conda init bash
source ~/.bashrc

conda create -y -n triton-cpu python=3.12
git clone --recursive https://github.com/triton-lang/triton-cpu.git;
cd triton-cpu

conda activate triton-cpu

# deps
conda install ninja cmake wheel pybind11
conda install -c conda-forge libstdcxx-ng=12

# build
pip install -e python

conda deactivate
