#!/usr/bin/env python

""" Module of bits to plug into Brewster """
import math
import gc
import numpy as np
import scipy as sp
import forwardmodel
import cloud
import TPmod
from scipy import interpolate
from astropy.convolution import convolve, convolve_fft
from astropy.convolution import Gaussian1DKernel
#from pysynphot import observation
#from pysynphot import spectrum

__author__ = "Ben Burningham"
__copyright__ = "Copyright 2015 - Ben Burningham"
__credits__ = ["Ben Burningham","The EMCEE DOCS"]
__license__ = "GPL"
__version__ = "0.1"
__maintainer__ = "Ben Burningham"
__email__ = "burninghamster@gmail.com"
__status__ = "Development"

# This bit is for flux conservation rebin of spectrum
#def rebinspec(wave, specin, wavenew,):
#    spec = spectrum.ArraySourceSpectrum(wave=wave, flux=specin)
#    f = np.ones(len(wave))
#    filt = spectrum.ArraySpectralElement(wave, f, waveunits='microns')
#    obs = observation.Observation(spec, filt, binset=wavenew, force='taper')
 
#    return obs.binflux



def lnlike(intemp, invmr, pcover, cloudtype, cloudparams, r2d2, logg, dlam, do_clouds,gasnum,cloudnum,inlinetemps,coarsePress,press,inwavenum,linelist,cia,ciatemps,use_disort,fwhm,obspec,logf,proftype):

    # Hard code nlayers
    nlayers = press.shape[0]
    npatch = cloudparams.shape[0]
    # set the profile
    temp = TPmod.set_prof(proftype,coarsePress,press,intemp)

    # get the ngas
    if (gasnum[gasnum.size-1] == 21):
        ngas = invmr.shape[0] + 1
    else:
        ngas = invmr.shape[0]
    # now loop through gases and get VMR for model
    # check if its a fixed VMR or a profile
    # VMR is log10(VMR) !!!
    logVMR = np.empty((ngas,nlayers),dtype='d')
    alkratio = 16.2 #  from Asplund et al (2009)
    if invmr.size > invmr.shape[0]:
        # this case is a profile
        # now sort Na and K
        tmpvmr = np.empty((ngas,nlayers),dtype='d')
        if (gasnum[gasnum.size-1] == 21):
            tmpvmr[0:(ngas-2),:] = invmr[0:(ngas-2),:]
            tmpvmr[ngas-2,:] = np.log10(10.**invmr[ngas-2,:] / (alkratio+1.))
            tmpvmr[ngas-1,:] = np.log10(10.**invmr[ngas-2,:] * (alkratio / (alkratio+1.)))                                
        else:
            tmpvmr[0:ngas,:] = invmr[0:ngas,:]
            
        for i in range(0,ngas):
            vfit = sp.interpolate.splrep(np.log10(coarsepress),tmpvmr[i,:],s=0)
            logVMR[i,:] = sp.interpolate.splev(np.log10(press),vfit,der=0)
    else:
        # This caseis fixed VMR
        # now sort Na and K
        tmpvmr = np.empty(ngas,dtype='d')
        if (gasnum[gasnum.size-1] == 21):
            tmpvmr[0:(ngas-2)] = invmr[0:(ngas-2)]
            tmpvmr[ngas-2] = np.log10(10.**invmr[ngas-2] / (alkratio+1.))
            tmpvmr[ngas-1] = np.log10(10.**invmr[ngas-2] * (alkratio / (alkratio+1.)))
        else:
            tmpvmr[0:ngas] = invmr[0:ngas]
            
        for i in range(0,ngas):                              
            logVMR[i,:] = tmpvmr[i]

    # now need to translate cloudparams in to cloud profile even
    # if do_clouds is zero..
    # 5 entries for cloudparams for simple slab model are:
    # 0) log10(number density / gas number density)
    # 1) top layer id (or pressure)
    # 2) base ID (these are both in 64 layers)
    # 3) rg
    # 4) rsig
    # in the case of a simple mixto cloud (i.e. cloudnum = 99) we have:
    # 0) ndens = dtau
    # 1) top layer ID
    # 2) bottom later ID
    # 3) rg = albedo
    # 4) rsig = asymmetry
    if (npatch > 1 or do_clouds == 1):
        cloudprof,cloudrad,cloudsig = cloud.atlas(do_clouds,cloudnum,cloudtype,cloudparams,press)
        npatch = cloudprof.shape[0]
        ncloud = cloudprof.shape[1]
    else:
        npatch = 1
        ncloud = 1
        cloudrad = np.ones((npatch,nlayers,ncloud),dtype='d')
        cloudsig = np.ones_like(cloudrad)
        cloudprof = np.ones_like(cloudrad)

    # now we can call the forward model
    outspec = forwardmodel.marv(temp,logg,r2d2,gasnum,logVMR,pcover,do_clouds,cloudnum,cloudrad,cloudsig,cloudprof,inlinetemps,press,inwavenum,linelist,cia,ciatemps,use_disort)
    # Trim to length where it is defined.
    nwave = inwavenum.size
    trimspec = np.zeros((2,nwave),dtype='d')
    trimspec[:,:] = outspec[:,:nwave]
    #print trimspec
    # now shift wavelen by delta_lambda
    shiftspec = np.empty_like(trimspec)
    shiftspec[0,:] =  trimspec[0,:] + dlam
    shiftspec[1,:] =  trimspec[1,:]
 
    # length and interval for later
    wlen = shiftspec.shape[1]
    wint =  shiftspec[0,0] - shiftspec[0,wlen-1]

    # convolve with instrumental profile
    # start by setting up kernel
    # First step is finding the array index length of the FWHM
    disp = wint / wlen
    gwidth = int((((fwhm / disp) // 2) * 2) +1)

    # needs to be odd
    # now get the kernel and convolve
    gauss = Gaussian1DKernel(gwidth)
    cspec = convolve(shiftspec[1,:],gauss,boundary='extend')
    spec = np.array([shiftspec[0,::-1],cspec[::-1]])
    
    # rebin to observed dispersion
    wfit = sp.interpolate.splrep(spec[0,:],spec[1,:],s=0)
    modspec = sp.interpolate.splev(obspec[0,:],wfit,der=0)
    
    # Below is method for rebinning using conserve flux method
    #    oblen = obspec.shape[1]
    #    modspec = np.empty((2,oblen),dtype='d')
    #    modspec[1,:] =  rebinspec(spec[0,:], spec[1,:], obspec[0,:])
    # get log-likelihood
    # We've lifted this from Mike's code, below is original from emcee docs
    # Just taking every 3rd point to keep independence
    s2=obspec[2,::3]**2 + 10.**logf
    lnLik=-0.5*np.sum((((obspec[1,::3] - modspec[::3])**2) / s2) + np.log(2.*np.pi*s2))


    return lnLik
    #chi2 log likelihood--can modify this
    #invsigma2 = 1.0/((obspec[2,::3])**2 + modspec[1,::3]**2 * np.exp(2*lnf))
    #return -0.5*(np.sum((obspec[1,::3] - modspec[1,::3])**2 * invsigma2 - np.log(invsigma2)))
    
    
def lnprob(theta,dist, pcover, cloudtype, cloudparams, do_clouds,gasnum,cloudnum,inlinetemps,coarsePress,press,inwavenum,linelist,cia,ciatemps,use_disort,fwhm,obspec,proftype):
    
    invmr = theta[0:9]
    logg = theta[9]
    r2d2 = theta[10]
    dlam = theta[11]
    logf = theta[12]

    nc = 0
    if (do_clouds == 1):
        if ((cloudtype == 2) and (cloudnum == 99)):
            cloudparams[1:5] = theta[13:17]
            nc = 4
        else:
            cloudparams = theta[13:18]
            nc = 5
        
    if (proftype == 1):
        gam = theta[13+nc]
        intemp = theta[14+nc:]
    elif (proftype == 2 or proftype ==3):
        intemp = theta[13+nc:]
    else:
        raise ValueError("not valid profile type %proftype" % (char, string))
    # now check against the priors, if not beyond them, run the likelihood
    lp = lnprior(theta,obspec,dist,proftype,press,do_clouds,gasnum,cloudnum,cloudtype)
    if not np.isfinite(lp):
        return -np.inf
    # else run the likelihood
    lnlike_value = lnlike(intemp, invmr,pcover, cloudtype,cloudparams,r2d2, logg, dlam, do_clouds,gasnum,cloudnum,inlinetemps,coarsePress,press,inwavenum,linelist,cia,ciatemps,use_disort,fwhm,obspec,logf,proftype)

    lnprb = lp+lnlike_value
    if np.isnan(lnprb):
        lnprb = -np.inf
    return lnprb


def lnprior(theta,obspec,dist,proftype,press,do_clouds,gasnum,cloudnum,cloudtype):
    # set up the priors here
    if (gasnum[gasnum.size-1] == 21):
        ngas = gasnum.size - 1
    else:
        ngas = gasnum.size
    invmr = theta[0:ngas]
    logg = theta[ngas]
    r2d2 = theta[ngas+1]
    dlam = theta[ngas+2]
    logf = theta[ngas+3]
    
    pc = ngas + 4
    nc = 0
    if (do_clouds == 1):
        if (cloudnum == 99):
            if (cloudtype == 1):
                cloudparams = theta[pc:pc+5]
                nc = 5
                cloud_tau0 = cloudparams[0]
                cloud_bot = cloudparams[1]
                cloud_top = cloudparams[2]
                cloud_height = 1.0
                w0 = cloudparams[3]
                gg = cloudparams[4]
                cloud_dens0 = -100.0
                rg = 1e-4
                rsig = 1e-6

            if (cloudtype == 2):
                cloudparams = theta[pc:pc+4]
                nc = 4
                cloud_tau0 = 1.0
                cloud_bot = press[press.size - 1]
                cloud_top = cloudparams[0]
                cloud_height = cloudparams[1]
                w0 = cloudparams[2]
                gg = cloudparams[3]
                cloud_dens0 = -100.0
                rg = 1e-4
                rsig = 1e-6
        else:
            if (cloudtype == 1):
                cloud_tau0 = 1.0
                cloud_bot = cloudparams[1]
                cloud_top = cloudparams[2]
                cloud_height = 1.0
                w0 = 0.5
                gg = 0.0
                cloud_dens0 = cloudparams[0]
                rg = cloudparams[3]
                rsig = cloudparams[4]

            if (cloudtype == 2):
                cloud_tau0 = 1.0
                cloud_bot = press[press.size-1]
                cloud_top = cloudparams[1]
                cloud_height = cloudparams[2]
                w0 =0.5
                gg =0.0
                cloud_dens0 = cloudparams[0]
                rg =  cloudparams[3]
                rsig =  cloudparams[4]
            
    else:
        cloud_tau0 = 1.0
        cloud_bot = press[press.size-1]
        cloud_top = press[0]
        cloud_height = 1.0
        w0 =0.5
        gg =0.0
        cloud_dens0 = -100.
        rg =  1e-4
        rsig = 1e-6
                

    if (proftype == 1):
        gam = theta[pc+nc]
        T = theta[pc+nc:]
        diff=np.roll(T,-1)-2.*T+np.roll(T,1)
        pp=len(T)
    
        #for mass prior
        D = 3.086e+16 * dist
        R = np.sqrt(r2d2) * D
        g = (10.**logg)/100.
        M = (R**2 * g/(6.67E-11))/1.898E27
        
        #         and  and (-5. < logbeta < 0))
        if (all(invmr[0:ngas] > -12.0) and (np.sum(10.**(invmr[0:ngas])) < 1.0) 
            and  0.0 < logg < 6.0 
            and 1. < M < 80. 
            and  0. < r2d2 < 1. 
            and -0.01 < dlam < 0.01 
            and (min(T) > 1.0) and (max(T) < 5000.) 
            and (gam > 0.)
            and ((0.01*np.min(obspec[2,:]**2)) < 10.**logf
                 < (100.*np.max(obspec[2,:]**2)))
            and (cloud_tau0 >= 0.0)
            and (0 < cloud_bot <= press[press.size-1])
            and (0 < cloud_top < cloud_bot)
            and (cloud_height > 0.0)
            and (0.0 < w0 < 1.0)
            and (-1.0 < gg < +1.0)
            and (cloud_dens0 < 0.0)
            and (rg > 1.e-5)
            and (rsig > 0.0)):
                 
            logbeta = -5.0
    	    beta=10.**logbeta
    	    alpha=1.0
    	    x=gam
    	    invgamma=((beta**alpha)/math.gamma(alpha)) * (x**(-alpha-1)) * np.exp(-beta/x)
            prprob = (-0.5/gam)*np.sum(diff[1:-1]**2) - 0.5*pp*np.log(gam) + np.log(invgamma)
            return prprob 
        
        return -np.inf

    elif (proftype ==2):
        a1 = theta[pc+nc]
        a2 = theta[pc+1+nc]
        P1 = theta[pc+2+nc]
        P3 = theta[pc+3+nc]
        T3 = theta[pc+4+nc]

        #for mass prior
        D = 3.086e+16 * dist
        R = np.sqrt(r2d2) * D
        g = (10.**logg)/100.
        M = (R**2 * g/(6.67E-11))/1.898E27
            
        if (all(invmr[0:ngas] > -12.0) and (np.sum(10.**(invmr[0:ngas])) < 1.0) 
            and  0.0 < logg < 6.0 
            and 1. < M < 80. 
            and  0. < r2d2 < 1. 
            and -0.01 < dlam < 0.01 
            and ((0.01*np.min(obspec[2,:]**2)) < 10.**logf
                 < (100.*np.max(obspec[2,:]**2)))
            and (cloud_tau0 >= 0.0)
            and (0. < cloud_bot <= press[press.size-1])
            and (0. < cloud_top < cloud_bot)
            and (cloud_height > 0.0)
            and (0.0 < w0 < 1.0)
            and (-1.0 < gg < +1.0)
            and (cloud_dens0 < 0.0)
            and (rg > 1.e-5)
            and (rsig > 0.0)
            and 0. < a1 < 1. and 0. < a2 < 1.0
            and T3 > 0.0 and P3 > P1 and P1 > press[0]
            and P3 < press[press.size-1]):
                
            return 0.0
        return -np.inf
        
    elif (proftype == 3):
        a1 = theta[pc+nc]
        a2 = theta[pc+1+nc]
        P1 = theta[pc+2+nc]
        P2 = theta[pc+3+nc]
        P3 = theta[pc+4+nc]
        T3 = theta[pc+5+nc]

        #for mass prior
        D = 3.086e+16 * dist
        R = np.sqrt(r2d2) * D
        g = (10.**logg)/100.
        M = (R**2 * g/(6.67E-11))/1.898E27
            
        if (all(invmr[0:ngas] > -12.0) and (np.sum(10.**(invmr[0:ngas])) < 1.0) 
            and  0.0 < logg < 6.0 
            and 1. < M < 80. 
            and  0. < r2d2 < 1. 
            and -0.01 < dlam < 0.01 
            and ((0.01*np.min(obspec[2,:]**2)) < 10.**logf
                 < (100.*np.max(obspec[2,:]**2)))
                        and (cloud_tau0 >= 0.0)
            and (0. < cloud_bot <= press[press.size-1])
            and (0. < cloud_top < cloud_bot)
            and (cloud_height > 0.0)
            and (0.0 < w0 < 1.0)
            and (-1.0 < gg < +1.0)
            and (cloud_dens0 < 0.0)
            and (rg > 1.e-5)
            and (rsig > 0.0)
            and 0. < a1 < 1. and 0. < a2 < 1.0
            and T3 > 0.0 and P3 > P2 and P2 > P1 and P1 > press[0]
            and P3 < press[press.size-1]):
                
            return 0.0
        return -np.inf


            



                
