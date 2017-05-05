#!/usr/bin/python

from mpi4py import MPI

import os, sys, getopt

import numpy as np
from lammps import lammps

comm = MPI.COMM_WORLD
iam = comm.Get_rank()


bname  = "lj_pylmp_hac"  # base name of simulation files
datdir = "data/{}_test".format(bname)    # name of output data directory

te_init = 30.0
te_sim  = 94.4
pr_init = 1.0
pr_sim  = 1.0

nmin   = 200      # number of emin steps
dt_md  = 10.0      # timestep in fs
nsteps = 10000     # number of timesteps
nout   = 100      # output frequency

mass = 39.948
La = 6.0       # lattice spacing in A
L  = 34.68     #78.45  # length of single box dimension in A
Lx = L*(5.0/3.0)
Ly = L
Lz = L

x  = 1.0/La
y  = 1.0/La
z  = 1.0/La
xx = Lx*x
yy = Ly*y
zz = Lz*z

bdx = Lx/5.0  # buffer dx (width of each buffer slab)
# x-direction
llo = 0.0
lhi = llo + bdx
rhi = Lx
rlo = rhi - bdx

lje = 0.23748
ljs = 3.4
ljcut = 12.0

# frequencies for taking averages for buffer region particles
neve, nrep, nfre = 2, 5, 10   # avg over every 2 steps, 5 times (over 10 total steps)

# Output files of particles in buffer region for
#  DENSITY
rh_l_file = "{}/rh.lbuffer".format(datdir)
rh_r_file = "{}/rh.rbuffer".format(datdir)
#  VELOCITY
ux_l_file = "{}/ux.lbuffer".format(datdir)
ux_r_file = "{}/ux.rbuffer".format(datdir)
uy_l_file = "{}/uy.lbuffer".format(datdir)
uy_r_file = "{}/uy.rbuffer".format(datdir)
uz_l_file = "{}/uz.lbuffer".format(datdir)
uz_r_file = "{}/uz.rbuffer".format(datdir)
#  TEMPERATURE
te_l_file = "{}/te.lbuffer".format(datdir)
te_r_file = "{}/te.rbuffer".format(datdir)


def setup(lmp):
    print_mpi("Setting up simulation...\n")

    inputfile = read(sys.argv[1:])
    if (inputfile): lmp.file(inputfile)

    lmp.command("units real")
    lmp.command("newton on")

    lmp = create_box(lmp)
    lmp = init_positions(lmp)

    lmp.command("pair_style  lj/cut {}".format(ljcut))
    lmp.command("pair_coeff  1 1 {} {} {}".format(lje, ljs, ljcut))
    lmp.command("pair_modify shift yes")
    lmp.command("neighbor     3.0 bin")
    lmp.command("neigh_modify delay 0 every 20 check no")

    lmp.command("thermo_style multi")

    # WARN: LAMMPS claims the system must be init before write_dump can be used...
    lmp.command("write_dump all xyz {}/init_{}.xyz".format(datdir, bname))
    xyz_to_pdb("{}/init_{}.xyz".format(datdir, bname))
    lmp.command("restart {} {}_a.res {}_b.res".format(1000, bname, bname))
    return lmp

def create_box(lmp):
    lmp.command("dimension    3")
    lmp.command("boundary     p p p")
    lmp.command("atom_style   atomic")
    lmp.command("atom_modify  map hash")
    lmp.command("lattice      fcc {}".format(La))
    lmp.command("region mybox block 0 {} 0 {} 0 {}".format(xx, yy, zz))
    lmp.command("create_box   1 mybox")
    return lmp


def init_positions(lmp):
    lmp.command("create_atoms 1 region mybox units box")
    lmp.command("mass  1 {}".format(mass))
    return lmp


def init_velocities(lmp):
    lmp.command("velocity all create {} 87287 loop geom".format(0.1*te_sim))
    return lmp


def setup_buffer(lmp):
    # STEP 1: Define a "chunk" of atoms with an implicit buffer region
    lmp.command("compute cid_left  all chunk/atom bin/1d x {} {} discard yes bound x 0.0 0.2 units reduced".format("lower", 0.2))
    lmp.command("compute cid_right all chunk/atom bin/1d x {} {} discard yes bound x 0.8 1.0 units reduced".format(0.8, 0.2))

    # STEP 2: Use the pre-defined "chunk" from step 1 to compute an average
    # DENSITY
    lmp.command("fix rh_left  all ave/chunk {} {} {} cid_left  density/mass norm sample ave one file {}".format(neve, nrep, nfre, rh_l_file))
    lmp.command("fix rh_right all ave/chunk {} {} {} cid_right density/mass norm sample ave one file {}".format(neve, nrep, nfre, rh_r_file))
    # VELOCITIES
    lmp.command("fix ux_left  all ave/chunk {} {} {} cid_left  vx norm sample ave one file {}".format(neve, nrep, nfre, ux_l_file))
    lmp.command("fix ux_right all ave/chunk {} {} {} cid_right vx norm sample ave one file {}".format(neve, nrep, nfre, ux_r_file))
    lmp.command("fix uy_left  all ave/chunk {} {} {} cid_left  vy norm sample ave one file {}".format(neve, nrep, nfre, uy_l_file))
    lmp.command("fix uy_right all ave/chunk {} {} {} cid_right vy norm sample ave one file {}".format(neve, nrep, nfre, uy_r_file))
    lmp.command("fix uz_left  all ave/chunk {} {} {} cid_left  vz norm sample ave one file {}".format(neve, nrep, nfre, uz_l_file))
    lmp.command("fix uz_right all ave/chunk {} {} {} cid_right vz norm sample ave one file {}".format(neve, nrep, nfre, uz_r_file))
    # TEMPERATURE (OR PRESSURE)
    lmp.command("compute te_left_t  all temp/chunk cid_left  temp com yes")
    lmp.command("compute te_right_t all temp/chunk cid_right temp com yes")
    lmp.command("fix te_left  all ave/time {} {} {} c_te_left_t  ave one file {}".format(neve, nrep, nfre, te_l_file))
    lmp.command("fix te_right all ave/time {} {} {} c_te_right_t ave one file {}".format(neve, nrep, nfre, te_r_file))

    return lmp


def setup_wall(lmp):
    lmp.command("fix wall_xlo all wall/lj1043 xlo {} {} {} {} units box".format(-0.5*ljs, 0.25*lje, 0.5*ljs, 1.5*ljs))
    lmp.command("fix wall_xhi all wall/lj1043 xhi {} {} {} {} units box".format(Lx+0.5*ljs, 0.25*lje, 0.5*ljs, 1.5*ljs))
    return lmp


def finalize(lmp):
    lmp.close()
    MPI.Finalize()


def minimize(lmp, style='cg'):
    print_mpi(">>> Minimizing for {} steps...".format(nmin))
    lmp.command("thermo     100")
    lmp.command("dump       emin all dcd {} {}/em_{}.dcd".format(10, datdir, bname))

    lmp.command("min_style {}".format(style))
    lmp.command("minimize   0.0 0.0 {} {}".format(nmin, 100*nmin))
    lmp.command("write_dump all xyz {}/em_{}.xyz".format(datdir, bname))
    xyz_to_pdb("{}/em_{}.xyz".format(datdir, bname))

    lmp.command("undump emin")
    return lmp


def equilibrate(lmp, te_i, te_f):
    print_mpi(">>> NVT equilibration for 10000 steps...")
    lmp.command("thermo   100")
    lmp.command("timestep 1.0")
    lmp.command("fix      1 all nvt temp {} {} 100.0 tchain 1".format(te_i, te_f))
    lmp.command("dump     eq1 all dcd {} {}/eq1_{}.dcd".format(100, datdir, bname))

    lmp.command("run      10000")
    lmp.command("write_dump all xyz {}/eq1_{}.xyz".format(datdir, bname))
    xyz_to_pdb("{}/eq1_{}.xyz".format(datdir, bname))

    lmp.command("unfix 1")
    lmp.command("undump eq1")

    # print_mpi(">>> NVT equilibration for 10000 steps...")
    # lmp.command("thermo   100")
    # lmp.command("timestep 5.0")
    # lmp.command("fix      1 all nvt temp {} {} 100.0 tchain 1".format(te_f, te_f))
    # lmp.command("dump     eq2 all dcd {} {}/eq2_{}.dcd".format(100, datdir, bname))
    #
    # lmp.command("run      10000")
    # lmp.command("write_dump all xyz {}/eq2_{}.xyz".format(datdir, bname))
    # xyz_to_pdb("{}/eq2_{}.xyz".format(datdir, bname))
    #
    # lmp.command("unfix 1")
    # lmp.command("undump eq2")
    return lmp


def run_lammps(lmp, n_md):
    print_mpi(">>> Running NVE simulation for {} steps...".format(n_md))
    lmp.command("thermo {}".format(10*n_md))
    lmp.command("timestep {}".format(dt_md))
    lmp.command("fix      1 all nve")
    # lmp.command("dump     run all dcd {} {}/md_{}.dcd".format(nout, datdir, bname))

    lmp.command("run      {}".format(n_md))
    # lmp.command("write_dump all xyz {}/md_{}.xyz".format(datdir, bname))
    # xyz_to_pdb("{}/md_{}.xyz".format(datdir, bname))
    lmp.command("write_restart {}.res".format(bname))
    return lmp


def read(argv):
    inputfile = ''
    outputfile = ''
    try:
        opts, args = getopt.getopt(argv,"hi:o:",["ifile=","ofile="])
    except getopt.GetoptError:
        print 'test_lj.py -i <inputfile> -o <outputfile>'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'test_lj.py -i <inputfile> -o <outputfile>'
            sys.exit()
        elif opt in ("-i", "--ifile"):
            inputfile = arg
        elif opt in ("-o", "--ofile"):
            outputfile = arg
    return inputfile


def xyz_to_pdb(xyzfile):
    import MDAnalysis as mda
    u = mda.Universe(xyzfile)
    u.dimensions = np.array([Lx, Ly, Lz, 90.00, 90.00, 90.00])
    u.atoms.write(os.path.splitext(xyzfile)[0] + '.pdb')


def print_mpi(msg, iam=iam, print_id=0):
    if (iam == print_id): print(msg)



def add_position(x_md, atom_ids, dx, dy, dz):
    for aid in atom_ids:
        x_md[aid][0] += dx
        x_md[aid][1] += dy
        x_md[aid][2] += dz

def add_velocity(v_md, atom_ids, dvx, dvy, dvz):
    for aid in atom_ids:
        v_md[aid][0] += dvx
        v_md[aid][1] += dvy
        v_md[aid][2] += dvz

def add_force(f_md, atom_ids, dfx, dfy, dfz):
    for aid in atom_ids:
        f_md[aid][0] += dfx
        f_md[aid][1] += dfy
        f_md[aid][2] += dfz


if __name__ == "__main__":
    # from ctypes import *

    n_md = 10
    t_md = n_md*dt_md

    lmp = lammps()
    lmp = setup(lmp)
    # lmp = setup_wall(lmp)
    lmp = setup_buffer(lmp)
    lmp = init_velocities(lmp)

    # lmp = minimize(lmp)
    lmp = equilibrate(lmp, te_init, te_init)

    lmp.command("dump     run all dcd {} {}/md_{}.dcd".format(n_md, datdir, bname))
    lmp.command("dump_modify run pbc yes")

    natoms = lmp.get_natoms()
    # natoms = lmp.extract_global("natoms",0)

    x_md = lmp.extract_atom("x", 3)  # Pointer to underlying array in LAMMPS
    v_md = lmp.extract_atom("v", 3)
    f_md = lmp.extract_atom("f", 3)

    print_mpi('>>> v_md[0]: {:7.5f} {:7.5f} {:7.5f}'.format(v_md[0][0], v_md[0][1], v_md[0][2]))

    ### Run #######################
    eta = 2.084e-3  # in Poise (= 0.1 Pascal-seconds = 0.1 Pa s = g/cm/s)
    g = 45.5  # lattice geometry factor (from Giupponi, et al. JCP 2007)
    dx = 10.0  # HD cell size in Angstroms
    zeta_bare = 0.50  # bare friction coefficient
    zeta_eff = 1./zeta_bare + 1/(g*eta*dx)
    atom_ids = range(natoms)

    lmp.command("region  rid_left  block {} {} {} {} {} {} units box".format(0.0, Lx/5, 0.0, Ly, 0.0, Lz))
    lmp.command("region  rid_right block {} {} {} {} {} {} units box".format(4*Lx/5, Lx, 0.0, Ly, 0.0, Lz))
    #
    # lmp.command("fix df all addforce {} {} {}".format())
    lmp.command("group left_buf  dynamic all region rid_left  every {}".format(n_md))
    lmp.command("group right_buf dynamic all region rid_right every {}".format(n_md))

    lmp.command("fix lange_left  left_buf  langevin {} {} {} 12345".format(te_sim, te_sim, mass/zeta_bare))
    lmp.command("fix lange_right right_buf langevin {} {} {} 12345".format(te_sim, te_sim, mass/zeta_bare))

    # lmp.command("variable forcex atom fx")
    # fx_md = lmp.extract_variable("forcex", "left_buf", 1)
    # fy_md = lmp.extract_variable("fy", "left_buf", 1)
    # fz_md = lmp.extract_variable("fz", "left_buf", 1)

    for i in xrange(10):
        # lmp.command("variable fx equal $forcex")
        # fx_md = lmp.extract_variable("forcex", "left_buf", 1)
        # print_mpi(">>> Force on 1 atom via extract_variable: {}".format(len(fx_md)))
        lmp = run_lammps(lmp, 2000)

        # print_mpi('>>> v_md[0]: {}'.format(v_md[0][0]))
        # print_mpi('>>> v_md[0][1]: {}'.format(v_md[0][1]))
        # print_mpi('>>> v_md[0][2]: {}'.format(v_md[0][2]))

        # add_velocity(v_md, atom_ids, 0, epsilon, 0)

        # print_mpi('>>> v_md[0][0]: {}'.format(v_md[0][0]))
        # print_mpi('>>> v_md[0][1]: {}'.format(v_md[0][1]))
        # print_mpi('>>> v_md[0][2]: {}'.format(v_md[0][2]))







    # f_md = lmp.gather_atoms("f", 1, 3)
    # print('>>> ', len(f_md))
    # print("Global coords from gather_atoms =",f_md[0],f_md[1],f_md[31])

    # natoms = lmp.get_natoms()
    # n3 = 3*natoms
    # x = (n3*c_double)()
    # x[0] = x coord of atom with ID 1
    # x[1] = y coord of atom with ID 1
    # x[2] = z coord of atom with ID 1
    # x[3] = x coord of atom with ID 2
    # print('>>> ', x[1296])
    # x_md = np.asarray(x)
    # print('>>> ', x_md[1296])
    #
    #
    # x_md = lmp.gather_atoms("x", 1, 3)
    # print('>>> Global number of atomic coordinates: ', len(x_md))
    #
    # x_md = lmp.gather_atoms("x", 1, 3)
    # print('>>> Global number of atomic coordinates: ', type(x_md))
    #
    # x_md = lmp.gather_atoms("x", 1, 3)
    # print('>>> x_md[0]: ', x_md[0])
    # x_md = lmp.gather_atoms("x", 1, 3)
    # print('>>> x_md[0,1]: ', x_md[0][1])
    # x_md = lmp.gather_atoms("x", 1, 3)
    # print('>>> x_md[1296]: ', x_md[1296])
    # x_md = lmp.gather_atoms("x", 1, 3)
    # print('>>> x_md[3888]: ', x_md[3888])
