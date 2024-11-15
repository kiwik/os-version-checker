#!/bin/bash

set -ex

conda init bash
source ~/.bashrc

conda create -y -n triton-cpu python=3.12
git clone --recursive https://github.com/triton-lang/triton-cpu.git;
cd triton-cpu

conda activate triton-cpu

# deps
conda install -y ninja cmake wheel pybind11
conda install -y -c conda-forge libstdcxx-ng=12

# build
export LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$LD_LIBRARY_PATH
echo $LD_LIBRARY_PATH
pip install -e python

conda deactivate
