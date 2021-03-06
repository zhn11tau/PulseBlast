# Data Culling class, Python 3
# Henryk T. Haniewicz, 2018

# Local imports
import utils.pulsarUtilities as pu
import utils.plotUtils as pltu
import utils.otherUtilities as u
import utils.mathUtils as mathu

# PyPulse imports
from pypulse.archive import Archive
from pypulse.singlepulse import SinglePulse
from pypulse.utils import get_toa3

# Plotting imports
import matplotlib.pyplot as plt
import scipy.stats as spyst
import scipy.optimize as opt

# Other imports
import numpy as np
from scipy.fftpack import fft, fftshift
import math
import os
import sys

# Filter various annoying warnings (such as "cannot perform >= np.nan"). We know already...
import warnings
warnings.filterwarnings( "ignore" )


# Data culling class
class DataCull:

    '''
    Main class for data culling pulsar fits files to get a less noisy data set.
    '''

    def __init__( self, filename, template, directory = None, SNLim = 3000, verbose = False ):

        '''
        Initializes all archives and parameters in the data cube for a given file.
        Also requires a template to be parsed in.
        A custom signal / noise lower bound can also be set on initialization but
        the default is 3000. This will exit the current archive if the SNR is
        lower than the threshold.
        One can also set whether long arrays and other bits of console text
        are to be printed in full or in shorthand.
        '''

        if verbose:
            print( "Initializing DataCull object..." )

        self.SNError = False

        # Parse directory in string or choose CWD if no directory given
        if directory == None:
            self.directory = str( os.getcwd() )
        else:
            self.directory = str( directory )

        # Parse filename
        if os.path.isfile( self.directory + filename ):
            self.filename = str( filename )
        else:
            raise FileNotFoundError( "File {} not found in this directory...".format( filename ) )

        # Load the template
        self.template = self._loadTemplate( template )

        # Parse verbose option
        self.verbose = verbose

        # Parse SNLim
        self.SNLim = SNLim

        # Load the file in the archive
        self.ar = Archive( self.__str__(), verbose = self.verbose )

        # Togglable print options
        if self.verbose:
            np.set_printoptions( threshold = np.inf )

        # Check if Signal / Noise is too low
        if self.ar.getSN() < SNLim:
            if self.verbose:
                print( "Signal / Noise ratio is way too low. (Below {})".format( SNLim ) )
                print( "Data set to be thrown out..." )
            self.SNError = True

        # Load the data cube for the file
        self.data = self.ar.getData()


    def __repr__( self ):
        return "DataCull( filename = {}, template = {}, directory = {}, SNLim = {}, verbose = {} )".format( self.filename, self.templateName, self.directory, self.SNLim, self.verbose )

    def __str__( self ):
        return self.directory + self.filename


    def _loadTemplate( self, templateFilename ):

        '''
        Loads a template specified by the user. If no extension is given, the
        extension .npy will be used. Note that this code is designed for numpy
        arrays so it would be wise to use them.
        Returns the template.
        '''

        # Parse the template's filename into a string and ensure the correct extension
        self.templateName = str( templateFilename )
        self.templateName = u.addExtension( self.templateName, 'npy' )

        # Load the template
        template = np.load( self.templateName )

        return template


    def reject( self, criterion = 'chauvenet', iterations = 1, fourier = True, rms = True, binShift = True, showPlots = False ):

        '''
        Performs the rejection algorithm until the number of iterations has been
        reached or the data culling is complete, whichever comes first. The
        default number of iterations is 1.
        Requires the criterion to be set with the default criterion
        being Chauvenet's criterion.
        This is the function you should use to reject all outliers fully.
        '''

        if self.verbose:
            print( "Beginning data rejection for {}...".format( self.filename ) )

        # Initialize the completion flag to false
        self.rejectionCompletionFlag = False

        if fourier:
            if self.verbose:
                print( "Beginning FFT data rejection..." )

            for i in np.arange( iterations ):

                self.fourierTransformRejection( criterion, showPlots, showPlots )

                # If all possible outliers have been found and the flag is set to true, don't bother doing any more iterations.
                if self.rejectionCompletionFlag:
                    generation = i + 1
                    if self.verbose:
                        print( "RMS data rejection for {} complete after {} generations...".format( self.filename, generation ) )
                    break

            # If the completion flag is still false, the cycles finished before full excision
            if self.verbose and not self.rejectionCompletionFlag:
                print( "Maximum number of iterations ({}) completed...".format( iterations ) )

            # Re-initialize the completion flag to false
            self.rejectionCompletionFlag = False


        if rms:
            if self.verbose:
                print( "Beginning RMS data rejection..." )

            for i in np.arange( iterations ):

                self.rmsRejection( criterion, showPlots )

                # If all possible outliers have been found and the flag is set to true, don't bother doing any more iterations.
                if self.rejectionCompletionFlag:
                    generation = i + 1
                    if self.verbose:
                        print( "RMS data rejection for {} complete after {} generations...".format( self.filename, generation ) )
                    break

            # If the completion flag is still false, the cycles finished before full excision
            if self.verbose and not self.rejectionCompletionFlag:
                print( "Maximum number of iterations ({}) completed...".format( iterations ) )

            # Re-initialize the completion flag to false
            self.rejectionCompletionFlag = False

        if binShift:
            if self.verbose:
                print( "Beginning bin shift data rejection..." )

                for i in np.arange( iterations ):

                    self.binShiftRejection( showPlots )

                    # If all possible outliers have been found and the flag is set to true, don't bother doing any more iterations.
                    if self.rejectionCompletionFlag == True:
                        generation = i + 1
                        if self.verbose:
                            print( "Bin shift data rejection for {} complete after {} generations...".format( self.filename, generation ) )
                        break

            # If the completion flag is still false, the cycles finished before full excision
            if self.verbose and not self.rejectionCompletionFlag:
                print( "Maximum number of iterations ({}) completed...".format( iterations ) )


        # Re-load the data cube for the file
        self.data = self.ar.getData()


    def rmsRejection( self, criterion, showPlot = False ):

        '''
        Rejects outlier root mean squared values for off pulse regions and
        re-weights the data cube in the loaded archive.
        '''

        # Re-load the data cube for the file
        self.data = self.ar.getData()

        templateMask = pu.binMaskFromTemplate( self.template )

        rmsArray, linearRmsArray, mu, sigma = u.getRMSArrayProperties( self.data, templateMask )

        if showPlot == True:

            # Creates the histogram
            pltu.histogram_and_curves( linearRmsArray, mean = mu, std_dev = sigma, x_axis = 'Root Mean Squared', y_axis = 'Frequency Density', title = r'$\mu={},\ \sigma={}$'.format( mu, sigma ), show = True, curve_list = [spyst.norm.pdf, mathu.test_dist.test_pdf] )

        # Determine which criterion to use to reject data
        if criterion is 'chauvenet': # Chauvenet's Criterion

            rejectionCriterion = mathu.chauvenet( rmsArray, mu, sigma, 3 )

        elif criterion is 'DMAD': # Double Median Absolute Deviation

            rejectionCriterion = mathu.doubleMAD( linearRmsArray )
            rejectionCriterion = np.reshape( rejectionCriterion, ( self.ar.getNsubint(), self.ar.getNchan() ) )

        else:
            raise ValueError( "Allowed rejection criteria are either 'chauvenet' or 'DMAD'. Please use one of these..." )

        # Set the weights of potential noise in each profile to 0
        u.zeroWeights( rejectionCriterion, self.ar, self.verbose )

        # Checks to see if there were any data to reject. If this array has length 0, all data was good and the completion flag is set to true.
        if( len( np.where( rejectionCriterion )[0] ) == 0 ):
            self.rejectionCompletionFlag = True

        if self.verbose:
            print( "Data rejection cycle complete..." )


    def fourierTransformRejection( self, criterion, showTempPlot = False, showOtherPlots = False ):

        '''
        Uses FFT (Fast Fourier Transform) to get the break-down of signals in the
        profile and compares to the the template.
        '''

        # Re-load the data cube
        data = self.ar.getData()
        tempData = self.template

        # Initialize guess parameters and the curve to fit
        guess_params = [100, 100, 1024]
        curve = mathu.FFT_dist._pdf

        # Set up arrays for FFT
        profFFT = np.zeros_like( data )
        tempFFT = fft( tempData )

        # Normalize the template array w.r.t the max value and shift to middle
        tempFFT = abs( mathu.normalizeToMax( abs( tempFFT.T ) ) )
        tempFFT = fftshift( tempFFT )

        # Create template FFT mask
        fftTempMask = pu.binMaskFromTemplate( tempFFT )

        rmsArray, linearRmsArray, mu, sigma = u.getRMSArrayProperties( data, fftTempMask )

        tempParams = opt.curve_fit( curve, np.arange( len( tempFFT ) ), tempFFT, p0 = guess_params )

        t = np.arange( 0, len( tempFFT ), 0.01)

        temp_fit = mathu.normalizeToMax( curve( t, *tempParams[0] ) )

        if showTempPlot:
            pltu.plotAndShow( tempFFT, t, temp_fit )

        # Loop over the time and frequency indices (subints and channels)
        for time in np.arange( self.ar.getNsubint() ):
            for frequency in np.arange( self.ar.getNchan() ):

                # FFT then normalize and center FFT'd profile
                profFFT[time][frequency] = fft( data[time][frequency] )
                profFFT[time][frequency] = abs( mathu.normalizeToMax( abs( profFFT[time][frequency].T ) ) )
                profFFT[time][frequency] = fftshift( profFFT[time][frequency] )

                if all( profFFT[time][frequency] ) == 0:
                    continue

                # Get optimization parameters for each profile for the same curve used to fit the template.
                params = opt.curve_fit( curve, np.arange( len( tempFFT ) ), profFFT[time][frequency], p0 = guess_params )

                # Normalize the curve with the fitted parameters
                prof_fit = mathu.normalizeToMax( curve( t, *params[0] ) )

                if showOtherPlots:
                    pltu.plotAndShow( profFFT[time][frequency], t, prof_fit, temp_fit )

                # if not all( u.is_similar_array( tempParams[0], params[0], tolerance = [ 1e-1, 1, 2 ] ) ):
                #     print( "Not similar" )
                #     continue
                if params[0][1] < 0:
                    print( "Not similar" )

                    if self.verbose:
                        print( "Setting the weight of (subint: {}, channel: {}) to 0".format( time, frequency ) )
                    self.ar.setWeights( 0, t = time, f = frequency )

                else:
                    print( "Similar" )


                # # Check if profile FT RMS matches template FT RMS based on Chauvenet
                # if criterion is 'chauvenet': # Chauvenet's Criterion
                #
                #     rejectionCriterion = mathu.chauvenet( rmsArray, mu, sigma, 2 )
                #
                # elif criterion is 'DMAD': # Double Median Absolute Deviation
                #
                #     rejectionCriterion = mathu.doubleMAD( linearRmsArray )
                #     rejectionCriterion = np.reshape( rejectionCriterion, ( self.ar.getNsubint(), self.ar.getNchan() ) )
                #
                # else:
                #     raise ValueError( "Allowed rejection criteria are either 'chauvenet' or 'DMAD'. Please use one of these..." )
                #
                # if not rejectionCriterion:
                #     if self.verbose:
                #         print( "Setting the weight of (subint: {}, channel: {}) to 0".format( time, frequency ) )
                #     self.ar.setWeights( 0, t = time, f = frequency )

        # Re-load the data cube
        self.data = self.ar.getData()



    def binShiftRejection( self, showPlot = False ):

        '''
        Gets the bin shift and bin shift errors of each profile in the file and
        plots both quantities as a histogram.
        Then, rejects based on Chauvenet criterion
        '''

        nBinShift, nBinError = self.getBinShifts()

        # Reshape the bin shift and bin shift error arrays to be linear
        linearNBinShift, linearNBinError = np.reshape( nBinShift, ( self.ar.getNchan() * self.ar.getNsubint() ) ), np.reshape( nBinError, ( self.ar.getNchan() * self.ar.getNsubint() ) )

        # Mean and standard deviation of the bin shift
        muS, sigmaS = np.nanmean( linearNBinShift ), np.nanstd( linearNBinShift )

        # Mean and standard deviation of the bin shift error
        muE, sigmaE = np.nanmean( linearNBinError ), np.nanstd( linearNBinError )

        if showPlot == True:

            # Create the histograms as two subplots
            pltu.histogram_and_curves( linearNBinShift, mean = muS, std_dev = sigmaS, x_axis = r'Bin Shift from Template, $\hat{\tau}$', y_axis = 'Frequency Density', title = r'$\mu={},\ \sigma={}$'.format( muS, sigmaS ), show = True, curve_list = [spyst.norm.pdf] )
            pltu.histogram_and_curves( linearNBinError, mean = muE, std_dev = sigmaE, x_axis = r'Bin Shift Error, $\sigma_{\tau}$', y_axis = 'Frequency Density', title = r'$\mu={},\ \sigma={}$'.format( muE, sigmaE ), show = True, curve_list = [spyst.maxwell.pdf] )

            # Adjust subplots so they look nice
            #plt.subplots_adjust( top=0.92, bottom=0.15, left=0.15, right=0.95, hspace=0.55, wspace=0.40 )

        rejectionCriterionS, rejectionCriterionE = mathu.chauvenet( nBinShift, muS, sigmaS ), mathu.chauvenet( nBinError, muE, sigmaE )

        # Set the weights of potential noise in each profile to 0
        u.zeroWeights( rejectionCriterionS, self.ar, self.verbose )
        u.zeroWeights( rejectionCriterionE, self.ar, self.verbose )

        # Checks to see if there were any data to reject. If this array has length 0, all data was good and the completion flag is set to true.
        if len( np.where( rejectionCriterionS )[0] ) == 0 and len( np.where( rejectionCriterionE )[0] ) == 0:
            self.rejectionCompletionFlag = True

        if self.verbose:
            print( "Data rejection cycle complete..." )

    def getBinShifts( self ):

        '''
        Returns the bin shift and bin shift error.
        '''

        if self.verbose:
            print( "Getting bin shifts and errors from the template..." )

        # Re-load the data cube
        self.data = self.ar.getData()

        templateMask = pu.binMaskFromTemplate( self.template )

        # Return the array of RMS values for each profile
        rmsArray = mathu.rmsMatrix2D( self.data, mask = templateMask, nanmask = True )

        # Initialize the bin shifts and bin shift errors
        nBinShift = np.zeros( ( self.ar.getNsubint(), self.ar.getNchan() ), dtype = float )
        nBinError = np.zeros( ( self.ar.getNsubint(), self.ar.getNchan() ), dtype = float )

        # Use PyPulse utility get_toa3 to obtain tauhat and sigma_tau for each profile and feed them into the two arrays.
        for time in np.arange( self.ar.getNsubint() ):
            for frequency in np.arange( self.ar.getNchan() ):

                if all( amp == 0 for amp in self.data[time][frequency] ):

                    nBinShift[time][frequency] = np.nan
                    nBinError[time][frequency] = np.nan

                else:

                    # Attempt to calculate the bin shift and error. If not possible, set the profile to 0.
                    try:
                        tauccf, tauhat, bhat, sigma_tau, sigma_b, snr, rho = get_toa3( self.template, self.data[time][frequency], rmsArray[time][frequency], dphi_in=0.1, snrthresh=0., nlagsfit=5, norder=2 )

                        nBinShift[time][frequency] = tauhat
                        nBinError[time][frequency] = sigma_tau

                    except:
                        if self.verbose:
                            print( "Setting the weight of (subint: {}, channel: {}) to 0".format( time, frequency ) )
                        self.ar.setWeights( 0, t = time, f = frequency )

                        nBinShift[time][frequency] = np.nan
                        nBinError[time][frequency] = np.nan

        # Mask the nan values in the array so that histogram_and_curves doesn't malfunction
        nBinShift, nBinError = np.ma.array( nBinShift, mask = np.isnan( nBinShift ) ), np.ma.array( nBinError, mask = np.isnan( nBinError ) )

        return nBinShift, nBinError


# FOR TESTING
if __name__ == "__main__":

    dir = "/Volumes/Henryk_Data/PSR J1756-2251/1756-2251 Nancay Data November 2017/Nancay_BON_data/"
    temp = dir + "Lbandtemplate.npy"

    # Cycle through each file in the stored directory
    for i, file in enumerate( os.listdir( dir ) ):

        # Initialize DCO
        try:
            dco = DataCull( file, temp, dir, verbose = False )
        except SystemExit:
            continue
        if dco.ar.getFrontend() is 'ROACH':
            continue

        #dco.reject( criterion = 'chauvenet', iterations = 5, fourier = False, rms = True, binShift = False, showPlots = True )

        #dco.ar.tscrunch( nsubint = 4 )
        #dco.ar.fscrunch( nchan = 4 )

        dco.fourierTransformRejection( 'chauvenet', True, True )
