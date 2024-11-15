#!/bin/bash

set -ex

conda create -y -n triton-cpu python=3.12
git clone https://github.com/triton-lang/triton-cpu.git;
cd triton-cpu

conda activate triton-cpu

pip install ninja cmake wheel pybind11
pip install -e python

conda deactivate
