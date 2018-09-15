# Extra utilities

# Imports
import sys
import os
import platform
import numpy as np


def zeroWeights( criterion = None, archive = None, verbose = False ):

    '''
    Scans through each sub-integration and channel and zeros any bad scans to zero.
    '''

    if criterion is None:
        raise ValueError( "Please provide a rejection criterion" )
    elif archive is None:
        raise ValueError( "Please provide an archive" )

    for time, frequency in zip( np.where( criterion )[0], np.where( criterion )[1] ):
        if verbose:
            print( "Setting the weight of (subint: {}, channel: {}) to 0".format( time, frequency ) )
        archive.setWeights( 0, t = time, f = frequency )


def restart_line():
     sys.stdout.write( '\r' )
     sys.stdout.flush()

def display_status( iteration, MAX_ITER ):
    restart_line()

    sys.stdout.write('{0:<10d}[{1:>3d}%]'.format( iteration, int( 100 * float( iteration )/float( MAX_ITER ) ) ) )
    sys.stdout.flush()

# Checks if 'file' has extension 'ext' and, if not, adds it.
def addExtension( file, ext ):

    '''
    Add any desired extension to a file that doesn't have one.
    If the file does, that extension will be used instead.
    '''

    if not isinstance( ext, str ):
        raise TypeError( "Extension must be a string" )

    # Split the filename up into a root and extension
    root, end = os.path.splitext( file )

    # If file extension does not exist, add the extension
    if not end:
        end = '.' + ext
        fileout = root + end
    else:
        fileout = file

    return fileout


# Formats directories from UI to console
def formatMultipleDirectories( args ):
    if platform.system() == 'Darwin' or 'Linux':
        dirs = ' '.join( args )
        dirs = dirs.replace( ":", "," )
        dirs = dirs.replace( "Macintosh HD", "" )
        dirs = dirs.split( "," )

    elif platform.system() == 'Windows':
        dirs = args

    else:
        raise OSError( "Could not determine OS." )

    return dirs


def addMultipleDirectoryEndSeparators( dirs, shell ):
    if shell == 'Unix':
        for i, d in enumerate( dirs ):
            if not d.endswith("/"):
                dirs[i] += "/"

    elif shell == 'Windows':
        for i, d in enumerate( dirs ):
            if not d.endswith("\\"):
                dirs[i] += "\\"

    else:
        raise ValueError( "Shell not recognized. (Shell provided: {})".format( shell ) )

    return dirs


# Takes in a single directory followed by the rest in a list. I'm gonna change this...
def addDirectoryEndSeparators( dir, dirs ):
    if platform.system() == 'Darwin' or "Linux":
        directory = dir + "/"
        directories = addMultipleDirectoryEndSeparators( dirs, 'Unix' )

    elif platform.system() == "Windows":
        directory = dir + "\\"
        directories = addMultipleDirectoryEndSeparators( dirs, 'Windows' )

    else:
        raise OSError( "Could not determine OS." )

    return directory, directories
