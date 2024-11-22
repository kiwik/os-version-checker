#!/bin/bash

set -ex

conda init bash
source ~/.bashrc

conda create -y -n triton-cpu python=3.12
conda activate triton-cpu

# Install deps for Triton
conda install -y ninja cmake wheel pybind11
conda install -y -c conda-forge libstdcxx-ng=12
# Install deps for LLVM
conda install -y -c conda-forge gcc=14 gxx=14

# Config build env
export LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$LD_LIBRARY_PATH
echo $LD_LIBRARY_PATH

git clone --recursive https://github.com/triton-lang/triton-cpu.git
cd triton-cpu

## Customizer LLVM for openEuler aarch64
llvm_version=$(cat cmake/llvm-hash.txt)
mkdir llvm-project; cd llvm-project
git init
git remote add origin https://github.com/llvm/llvm-project.git
git fetch --depth 1 origin $llvm_version
git checkout -b pin-version FETCH_HEAD

## Build LLVM for Triton
mkdir build; cd build
cmake -G Ninja -DCMAKE_BUILD_TYPE=Release -DLLVM_ENABLE_ASSERTIONS=ON ../llvm \
  -DLLVM_ENABLE_PROJECTS="mlir;llvm" \
  -DLLVM_TARGETS_TO_BUILD="host;NVPTX;AMDGPU"
ninja
cd ../..

## Build Triton
pip install -e python

conda deactivate
