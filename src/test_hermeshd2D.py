from mpi4py import MPI
import numpy as np

import hermeshd


################################################################################
L  = 80.0    #34.68     #78.45  # length of single box dimension in A
Lx = Ly = L
Lz = L/12
Lxu = Lx/2.0
Lyu = Ly/2.0
Lzu = Lz/2.0
Lxd = -Lx/2.0
Lyd = -Ly/2.0
Lzd = -Lz/2.0
bdy = 10.0
bb_lo = Lyd
bb_hi = Lyd + bdy
tb_lo = Lyu - bdy
tb_hi = Lyu
################################################################################

################################################################################
# This works
#------------------------------------------
# Get the communicator for Fortran
comm = MPI.COMM_WORLD
fcomm = comm.py2f()
rank = comm.Get_rank()
size = comm.Get_size()
print "Proc %d out of %d procs" % (rank,size)
#------------------------------------------

################################################################################
# Current testing
#------------------------------------------
# hermeshd.hermeshd.main(fcomm)

# Alias the Fortran subroutines
main = hermeshd.hermeshd.main
setup = hermeshd.hermeshd.setup
step = hermeshd.hermeshd.step
generate_output = hermeshd.hermeshd.generate_output
cleanup = hermeshd.hermeshd.cleanup

# xc = hermeshd.spatial.xc
# yc = hermeshd.spatial.yc
# zc = hermeshd.spatial.zc

# Instantiate some global parameters
# nx, ny, nz = 10, 10, 10
nx, ny, nz = 4, 4, 1
nQ, nB = 11, 8

# Field arrays
Qio = np.empty((nx, ny, nz, nQ, nB), order='F', dtype=np.float32)
Q1  = np.empty((nx, ny, nz, nQ, nB), order='F', dtype=np.float32)
Q2  = np.empty((nx, ny, nz, nQ, nB), order='F', dtype=np.float32)

# Time variables
t  = np.array(0.0,    dtype=float)  # works w/ np.float32 and None
tf = np.array(1.0e2,  dtype=float)
dt = np.array(1.0e-2, dtype=float)

# Timing and output variables
t1      = np.array(0.0, dtype=float)
t_start = np.array(0.0, dtype=float)
dtout   = np.array(0.0, dtype=float)
nout    = np.array(0,   dtype=int)  # works w/ np.int32 and None

################################################################################
# I. SETUP
#-----------------------------
setup(Qio, t, dt, t1, t_start, dtout, nout, fcomm)

################################################################################
# I. SIMULATION
#-----------------------------
while ( t < tf ):
    step(Qio, Q1, Q2, t, dt)
    generate_output(Qio, t, dt, t1, dtout, nout)


    # if rank == 0: print "t = {}   dt = {}   nout = {}".format(t, dt, nout)

################################################################################
# I. CLEANUP
#-----------------------------
cleanup(t_start)