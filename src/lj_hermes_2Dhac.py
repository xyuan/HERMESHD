#!/usr/bin/python

from mpi4py import MPI
import numpy as np

import hermeshd

comm = MPI.COMM_WORLD
iam = comm.Get_rank()
nproc = comm.Get_size()

# Alias the Fortran subroutines
# main = hermeshd.hermeshd.main
# setup = hermeshd.hermeshd.setup
# step = hermeshd.hermeshd.step
# generate_output = hermeshd.hermeshd.generate_output
# cleanup = hermeshd.hermeshd.cleanup

xc = hermeshd.spatial.xc
yc = hermeshd.spatial.yc
zc = hermeshd.spatial.zc

# Instantiate some global parameters
nx, ny, nz = 4, 4, 1
nQ, nB = 11, 8

# Field arrays
Qio = np.empty((nx, ny, nz, nQ, nB), order='F', dtype=np.float32)
Q1  = np.empty((nx, ny, nz, nQ, nB), order='F', dtype=np.float32)
Q2  = np.empty((nx, ny, nz, nQ, nB), order='F', dtype=np.float32)

################################################################################
Qres_shape = (nx, ny, nz, nQ, 1)
Qres = np.empty(Qres_shape, order='F', dtype=np.float32)

sendbuf = Qres
recvbuf = None

if rank == 0:
    recvbuf = np.empty((nproc,)+Qres_shape, dtype=np.float32)

# Gather Qres from each rank
comm.Gather(sendbuf, recvbuf, root=0)

if rank == 0:
    # something about recvbuf

################################################################################

# Time variables
t  = np.array(0.0,   dtype=float)  # works w/ np.float32 and None
tf = np.array(1.0e2, dtype=float)

# Timing and output variables
t1      = np.array(0.0, dtype=float)
t_start = np.array(0.0, dtype=float)
dtout   = tf/1000
nout    = np.array(0,   dtype=int)  # works w/ np.int32 and None


def run_hermes(nstep_hd, Qio, Q1, Q2, t, dt, t1, dtout, nout):
    for i in xrange(nstep_hd):
        hermeshd.hermeshd.step(Qio, Q1, Q2, t, dt)
        hermeshd.hermeshd.generate_output(Qio, t, dt, t1, dtout, nout)
