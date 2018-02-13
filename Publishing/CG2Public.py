#----------------------------------------------------------------------
# Take the CDR publishing data (for Gatekeeper use) and convert to
# Licensee data.
# Validate the new licensee data against its DTD.
#
# BZIssue::4123
# BZIssue::4675 - Create UrlInfo block
# BZIssue::4881 - Modify publishing to include Drug Info Summary
# BZIssue::5093 - [Media] Adding Audio Files to Vendor Output
# OCECDR-3962: Simplify Rerunning Jobmaster Job (Windows)
# OCECDR-3960: Include current DTD in FTP Data Set
#----------------------------------------------------------------------
import cdr, cdrpub, os, os.path, shutil, sys, re, glob, optparse, time

OUTPUTBASE    = cdr.BASEDIR + "/Output/LicenseeDocs"
SOURCEBASE    = cdr.BASEDIR + "/Output"
DTDDIR        = "d:\\cdr\\Licensee"
PDQDTD        = "pdq.dtd"
# DTDPUBLIC     = "d:\\cdr\\Licensee\\pdq.dtd"
DTDPUBLIC     = "%s\\%s" % (DTDDIR, PDQDTD)
LOGNAME       = "CG2Public.log"
EXCLUDEDIRS   = ('InvalidDocs', 'media_catalog.txt')
AUXFILES      = ('media_catalog.txt',)
warnings      = False

# -------------------------------------------------------------------------
# -------------------------------------------------------------------------
class documentType:

    def __init__(self):
        self.filters = { 'CTGovProtocol': ['name:Vendor Filter: CG2Public'],
                         'GlossaryTerm':  ['name:Vendor Filter: CG2Public'],
                         'ProtocolActive':['name:Vendor Filter: CG2Public'],
                         'ProtocolClosed':['name:Vendor Filter: CG2Public'],
                         'Summary':       ['name:Vendor Filter: CG2Public'],
                         'Terminology':   ['name:Vendor Filter: CG2Public']}
        self.sourceBase  = cdr.BASEDIR + "/Output"
        self.jobDir      = self.lastJobDir()
        self.outputDir   = None
        self.inputDir    = None


    # -------------------------------------------------------------------
    # Find the last publishing directory
    # -------------------------------------------------------------------
    def lastJobDir(self):
        os.chdir(self.sourceBase)

        # The glob module is not flexible enough to test for jobs with
        # 4 or 5 digits.  This will have to be modified when we're
        # approaching Job99999+
        # jobDirs = glob.glob('Job?????')
        # ------------------------------------------------------------
        jobDirs = glob.glob('Job?????')
        if not jobDirs:
            l.write("*** Error: No publishing directory found",
                                                     stdout = True)
            sys.exit(1)

        jobDirs.sort()
        return jobDirs[-1:][0]


    # -------------------------------------------------------------------
    # Copying the content of the directories and filtering those
    # document types that need to be modified for the licensees.
    # -------------------------------------------------------------------
    def copy(self, directory):
        os.chdir('%s/%s' % (self.inputDir, directory))

        # Need to pick up xml, jpg, gif, and mp3 files
        # --------------------------------------------
        allDocs = glob.glob('*.[xjgm][mpip][lgf3]')

        # Create the output directory or - in test mode - delete
        # and recreate the directory
        # ------------------------------------------------------
        if allDocs:
            try:
                os.mkdir('%s/%s' % (self.outputDir, directory))
            except:
                if testMode:
                    pwd = os.getcwd()

                    # If an output directory has been specified that
                    # doesn't exist stop the operation.
                    # --------------------------------------------------
                    try:
                        os.chdir(self.outputDir)
                    except:
                        l.write("*** Error: Directory %s doesn't exist" % (
                                             self.outputDir), stdout = True)
                        sys.exit(1)

                    shutil.rmtree(directory)
                    os.mkdir(directory)
                    os.chdir(pwd)
                else:
                    print "Error: Directory %s already exists." % directory
                    raise

        l.write("Processing %s/%s..." % (self.inputDir, directory),
                                                             stdout = True)
        l.write("   Copy to %s/%s..." % (self.outputDir, directory),
                                                             stdout = True)

        # Processing all documents by reading, filtering, validating,
        # and writing the files, if necessary.
        # -------------------------------------------------------
        valError = ()
        # filt_warnings = ''
        for doc in allDocs:
            f = open(doc, "rb")
            xmlDoc = f.read()
            f.close()

            # Filter the CG document
            # ----------------------
            if directory in self.filters.keys():
                result = cdr.filterDoc('guest',
                                   filter = ['name:Vendor Filter: Convert' +
                                             ' CG to Public Data'],
                                   doc = xmlDoc)

                if type(result) not in (type([]), type(())):
                    errors = result or "Unspecified failure filtering document"
                    newDoc = None
                    l.write("*** Error: %s" % errors, stdout = True)
                    break

                newDoc = result[0]
                if result[1]:
                    l.write("*** Warning: %s" % result[1], stdout = True)
            else:
                newDoc = xmlDoc

            # Validate the document with the new Licensee DTD
            # Excluding Media files since these aren't XML files
            # --------------------------------------------------
            if not directory == 'Media':
                resp = cdrpub.Control.validate_doc(newDoc, DTDPUBLIC)
                if resp:
                    valError += (doc,)
                    l.write('*** Validation Error for %s:\n%s' % (doc, resp),
                                                               stdout = True)

            # Write the newly filtered (or unmodified) licensee file
            # ------------------------------------------------------
            exportFile = open('%s/%s/%s' % (self.outputDir,
                                                 directory, doc), 'wb')
            exportFile.write(newDoc)
            exportFile.close()

        return valError


# ------------------------------------------------------------
# Function to parse the command line arguments
# ------------------------------------------------------------
def parseArguments(args):
    """
    Assign all input parameters to variables and perform some error
    checking.
    """

    usage = "usage: %prog [--livemode | --testmode] [options]"
    parser = optparse.OptionParser(usage = usage)

    parser.set_defaults(testMode = True)
    parser.set_defaults(emailMode = True)
    parser.set_defaults(fullMode = True)
    parser.add_option('-t', '--testmode',
                      action = 'store_true', dest = 'testMode',
                      help = 'running in TEST mode')
    parser.add_option('-l', '--livemode',
                      action = 'store_false', dest = 'testMode',
                      help = 'running in LIVE mode')
    parser.add_option('-f', '--export',
                      action = 'store_true', dest = 'fullMode',
                      help = 'running in TEST mode')
    parser.add_option('-i', '--interim',
                      action = 'store_false', dest = 'fullMode',
                      help = 'running in LIVE mode')
    parser.add_option('-e', '--email',
                      action = 'store_true', dest = 'emailMode',
                      help = 'running in EMAIL mode')
    parser.add_option('-n', '--noemail',
                      action = 'store_false', dest = 'emailMode',
                      help = 'running in NOEMAIL mode')
    parser.add_option('-s', '--inputdir',
                      action = 'append', dest = 'inputdir',
                      help = 'specify full path of input directory')
    parser.add_option('-o', '--outputdir',
                      action = 'append', dest = 'outputdir',
                      help = 'specify full path of output directoryrun')

    # Exit if no command line argument has been specified
    # ---------------------------------------------------
    if len(args[1:]) == 0:
        parser.print_help()
        sys.exit('No arguments given!')

    (options, args) = parser.parse_args()
    # Read and process options, if any
    # --------------------------------
    if parser.values.testMode:
        l.write("Running in TEST mode", stdout = True)
    else:
        l.write("Running in LIVE mode", stdout = True)

    if parser.values.fullMode:
        l.write("Running in EXPORT mode", stdout = True)
    else:
        l.write("Running in INTERIM mode", stdout = True)

    if parser.values.emailMode:
        l.write("Running in EMAIL mode", stdout = True)
    else:
        l.write("Running in NOEMAIL mode", stdout = True)

    if parser.values.inputdir:
        inputdir = parser.values.inputdir[0] or None
        l.write("Input  directory: %s" % inputdir, stdout = True)
    if parser.values.outputdir:
        outputdir = parser.values.outputdir[0] or None
        l.write("Output directory: %s" % outputdir, stdout = True)

    return parser


# -------------------------------------------------------------
# Get a list of all published document types to be processed
# -------------------------------------------------------------
def getDocumentTypes(directory):
    os.chdir(directory)
    allDirs = glob.glob('[A-Z]*')

    docTypes = []
    for dir in allDirs:
        if os.path.isdir(dir):
            docTypes.append(dir)

    if not docTypes:
        l.write("No directories in latest publishing job")
        l.write("  %s" % directory)
        l.write("Error: No doctypes found in directory!!!", stdout = True)
        sys.exit(1)

    return docTypes


# ===================================================================
# Main Starts here
# ===================================================================
l = cdr.Log(LOGNAME)
l.write('CG2Public.py - Started',   stdout = True)
l.write('Arguments: %s' % sys.argv, stdout = True)
print ''

options   = parseArguments(sys.argv)
testMode  = options.values.testMode
emailMode = options.values.emailMode
fullMode  = options.values.fullMode
inputdir  = options.values.inputdir  and options.values.inputdir[0] or None
outputdir = options.values.outputdir and options.values.outputdir[0] or None
print ""

# Create the documentType instance and search for the latest
# publishing jobId
# ----------------------------------------------------------
d = documentType()
lastJobDir = d.jobDir
l.write("Latest publishing job: %s" % lastJobDir, stdout = True)

# Find the document types published
# ----------------------------------
if inputdir:
    # If the directory name is not fully specified
    # it must be located in the default directory
    # --------------------------------------------
    if not inputdir.find(':') == -1:
        d.inputDir = inputdir
    else:
        d.inputDir = '%s/%s' % (SOURCEBASE, inputdir)
else:
    d.inputDir = '%s/%s' % (SOURCEBASE, d.jobDir)

jobDir = inputdir or d.jobDir
l.write("Using  publishing job: %s" % jobDir, stdout = True)
pubDirs = getDocumentTypes(d.inputDir)

# Setting the path and creating the new directory for the
# licensee data to be stored.
# ---------------------------------------------------------
if testMode:
    d.outputDir = '%s/Test/%s' % (OUTPUTBASE, jobDir)
else:
    d.outputDir = '%s/%s' % (OUTPUTBASE, jobDir)

# If the output directory has been passed as a command line parameter
# we're using the full path instead
# -------------------------------------------------------------------
if outputdir:
    d.outputDir = outputdir

# Creating the output directory
# ------------------------------
try:
    l.write("Copying from directory: %s" % jobDir,  stdout = True)
    l.write("Creating directory: %s" % d.outputDir, stdout = True)
    os.mkdir(d.outputDir)
except OSError, info:
    l.write("Directory already exists",             stdout = True)
    if testMode:
        l.write("  OK in Testmode",                 stdout = True)
    else:
        l.write("  *** Error creating directory:" , stdout = True)
        l.write("      %s" % info,                  stdout = True)
        sys.exit(1)

# Process one directory at a time
# -------------------------------
for dir in pubDirs:
    if not dir in EXCLUDEDIRS:
        result = d.copy(dir)
        if result:
            warnings = True
            l.write("Validation error processing %s" % dir,
                                                    stdout = True)
            l.write("  Documents with Errors: %s" % str(result),
                                                    stdout = True)
    else:
        l.write("%s skipped" % dir, stdout = True)

if warnings:
    l.write('CG2Public.py - Finished with Warnings', stdout = True)
    sys.exit(1)

# A few auxiliary files also need to be copied
# --------------------------------------------
if fullMode:
    l.write("Writing aux files and DTD", stdout = True)
    for auxFile in AUXFILES:
        shutil.copy('%s/%s' % (d.inputDir, auxFile), d.outputDir)

    shutil.copy('%s/%s' % (DTDDIR, PDQDTD), d.outputDir)

l.write('CG2Public.py - Finished', stdout = True)
sys.exit(0)
