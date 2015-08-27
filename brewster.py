#!/usr/bin/env python

"""This is Brewster: the golden retriever of smelly atmospheres"""


import numpy as np
import scipy as sp
import emcee
import testkit
import ciamod
import cPickle as pickle
from scipy.io.idl import readsav
from scipy import interpolate
from scipy.interpolate import interp1d


__author__ = "Ben Burningham"
__copyright__ = "Copyright 2015 - Ben Burningham"
__credits__ = ["Ben Burningham"]
__license__ = "GPL"
__version__ = "0.1"
__maintainer__ = "Ben Burningham"
__email__ = "burninghamster@gmail.com"
__status__ = "Development"


# set up the model arguments the drop these into theta(state vector) or runargs

# Here we'll use the temp and pressure profile from Mike, as used to produce sim
# spectrum

array = pickle.load(open("test_H2H2_H2He_CIA_H2O.pic", "rb")) 
leveltemp = array[0]
levelpress = array[1]
mikespec = np.array([array[2],array[3]],dtype='f')
mikespec[0] = 10000.0 / mikespec[0]
mikepress = np.empty(levelpress.size - 1,dtype='float64')
miketemp = np.empty(leveltemp.size -1, dtype='float64')
for i in range(0,mikepress.size):
    mikepress[i] = np.sqrt(levelpress[i] * levelpress[i+1])
mtfit = interp1d(np.log10(levelpress),leveltemp)
miketemp = mtfit(np.log10(mikepress))
# now the linelist
x=readsav('../Linelists/xsecarrH2O_1wno_500_10000.save')
inlinelist=x.xsecarr  #3D array with Nwavenubmers x Ntemps x Npressure
inlinetemps=np.asfortranarray(x.t,dtype='float64')
inpress=x.p
inwavenum=x.wno

# Here we are interpolating the linelist onto Mike's pressure scale. 
linelist = (np.ones([1,79,43,9501],order='F')).astype('float64', order='F')
for i in range (0,42):
    for j in range (0,9500):
        pfit = interp1d(np.log10(inpress),np.log10(inlinelist[:,i,j]))
        linelist[0,:,i,j] = np.asfortranarray(pfit(np.log10(mikepress)))
press = mikepress*1000.
intemp = miketemp

# This will be a variable in theta here - r2d2 = 1.
logg = 4.5
dlam = 0.
w1 = 1.0
w2 = 2.5
pcover = 1.0
do_clouds = 0
# cloudparams is structured array with 5 entries
# each one has a patch*cloud entries
cloudparams = np.ones(5)
# 5 entries in cloudparams for simple slab model are:
# 0) log10(number density)
# 1) top layer id (or pressure)
# 2) base ID (these are both in 61 layers)
# 3) rg
# 4) rsig
cloudparams[0] = -20.
cloudparams[1] = 10
cloudparams[2] = 12
cloudparams[3] = 1e-4
cloudparams[4] = 1e-5
# hardwired gas and cloud IDs
gasnum = np.asfortranarray(np.array([1],dtype='i'))
cloudnum = np.array([1],dtype='i')

# Get the cia bits
cia, ciatemps = ciamod.read_cia("final1_abel_CIA.dat",inwavenum)
cia = np.asfortranarray(cia, dtype='float32')
ciatemps = np.asfortranarray(ciatemps, dtype='float32')

# hardwired FWHM of data
fwhm = 0.005
#fixvmrs = -8.0

# get the observed spectrum
obspec = np.asfortranarray(np.loadtxt("sim_spectrum.dat",dtype='d',unpack='true'))

runargs = w1,w2,intemp, pcover, cloudparams,logg, dlam, do_clouds,gasnum,cloudnum,inlinetemps,press,inwavenum,linelist,cia,ciatemps,fwhm,obspec

# now set up the EMCEE stuff
ndim, nwalkers = 2, 4
p0 = np.empty([nwalkers,ndim])
p0[:,0] = -1.* np.random.rand(nwalkers).reshape(nwalkers) - 3.0
p0[:,1] = np.random.rand(nwalkers).reshape(nwalkers)
sampler = emcee.EnsembleSampler(nwalkers, ndim, testkit.lnprob, args=(runargs), threads = 4)
# run the sampler
sampler.run_mcmc(p0, 4)

# get rid of problematic bit of sampler object
del sampler.__dict__['pool']

def save_object(obj, filename):
    with open(filename, 'wb') as output:
        pickle.dump(obj, output, pickle.HIGHEST_PROTOCOL)

save_object(sampler,'retrieval_result.pk1')



