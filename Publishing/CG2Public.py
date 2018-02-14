#!/usr/bin/env python
"""
Convert the CDR publishing data (for Gatekeeper use) for PDQ data partner use

Validate the new licensee data against its DTD.

BZIssue::4123
BZIssue::4675 - Create UrlInfo block
BZIssue::4881 - Modify publishing to include Drug Info Summary
BZIssue::5093 - [Media] Adding Audio Files to Vendor Output
OCECDR-3962: Simplify Rerunning Jobmaster Job (Windows)
OCECDR-3960: Include current DTD in FTP Data Set
OCECDR-4211: Use new API directly for filtering documents
"""

import argparse
import glob
import os
import re
import shutil
import sys
import time
import cdr
import cdrpub
from cdrapi.users import Session
from cdrapi.docs import Doc

class Control:
    """
    Logic for filtering, copying, and validating docs for PDQ data partners
    """

    OUTPUTBASE = cdr.BASEDIR + "/Output/LicenseeDocs"
    SOURCEBASE = cdr.BASEDIR + "/Output"
    DTDDIR = "d:\\cdr\\Licensee"
    PDQDTD = "pdq.dtd"
    DTDPUBLIC = "%s\\%s" % (DTDDIR, PDQDTD)
    EXCLUDEDIRS = ("InvalidDocs", "media_catalog.txt")
    AUXFILES = ("media_catalog.txt",)
    FILTER = "name:Vendor Filter: Convert CG to Public Data"
    FILTERABLE = {"GlossaryTerm", "Summary", "Terminology"}

    def __init__(self):
        self.sourceBase  = cdr.BASEDIR + "/Output"
        self.jobDir      = self.last_job_directory()
        self.outputDir   = None
        self.inputDir    = None
        self.session     = Session("guest")

    def last_job_directory(self):
        """
        Find the most recent publishing output directory
        """

        os.chdir(self.sourceBase)
        job_id = 0
        for name in glob.glob("Job*"):
            match = re.match(r"^Job(\d+)$", name)
            if match:
                job_id = max(job_id, int(match.group(1)))
        if not job_id:
            logger.error("No publishing directory found")
            sys.exit(1)
        return "Job{:d}".format(job_id)

    def copy(self, directory):
        """
        Copy, filter, and validate contents of a single directory

        Filtering and/or validation are not done for some directories.

        Pass:
          directory - string for name of source directory
        """

        os.chdir("%s/%s" % (self.inputDir, directory))

        # Need to pick up xml, jpg, gif, and mp3 files
        # --------------------------------------------
        allDocs = glob.glob("*.[xjgm][mpip][lgf3]")

        # Create the output directory or - in test mode - delete
        # and recreate the directory
        # ------------------------------------------------------
        if allDocs:
            try:
                os.mkdir("%s/%s" % (self.outputDir, directory))
            except:
                if testMode:
                    source_dir = os.getcwd()

                    # If an output directory has been specified that
                    # doesn't exist stop the operation.
                    # --------------------------------------------------
                    try:
                        os.chdir(self.outputDir)
                    except:
                        message = "Directory %s doesn't exist"
                        logger.error(message, self.outputDir)
                        sys.exit(1)

                    shutil.rmtree(directory)
                    os.mkdir(directory)
                    os.chdir(source_dir)
                else:
                    message = "Directory {} already exists".format(directory)
                    raise Exception(message)

        logger.info("Processing %s/%s...", self.inputDir, directory)
        logger.info("   Copy to %s/%s...", self.outputDir, directory)

        # Processing all documents by reading, filtering, validating,
        # and writing the files, as appropriate.
        # -------------------------------------------------------
        validation_errors = []
        for filename in allDocs:
            with open(filename, "rb") as fp:
                xml = fp.read()

            # Filter the CG document
            # ----------------------
            if directory in self.FILTERABLE:
                doc = Doc(self.session, xml=xml)
                result = doc.filter(self.FILTER)
                newDoc = unicode(result.result_tree).encode("utf-8")
                if result.messages:
                    for message in result.messages:
                        logger.warning(message)
            else:
                newDoc = xml

            # Validate the document with the new Licensee DTD
            # Excluding Media files since these aren't XML files
            # --------------------------------------------------
            if directory != "Media":
                resp = cdrpub.Control.validate_doc(newDoc, self.DTDPUBLIC)
                if resp:
                    validation_errors.append(filename)
                    args = filename, resp
                    logger.warning("Validation error(s) for %s: %s", *args)

            # Write the newly filtered (or unmodified) licensee file
            # ------------------------------------------------------
            path = "%s/%s/%s" % (self.outputDir, directory, filename)
            with open(path, "wb") as fp:
                fp.write(newDoc)

        return validation_errors


def getDocumentTypes(directory):
    """
    Get a list of all published document types to be processed
    """

    os.chdir(directory)
    allDirs = glob.glob("[A-Z]*")
    docTypes = []
    for dir in allDirs:
        if os.path.isdir(dir):
            docTypes.append(dir)
    if not docTypes:
        logger.error("No directories in latest publishing job")
        sys.exit(1)
    return docTypes


# ===================================================================
# Main processing starts here.
# ===================================================================
parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument("--testmode", "-t", action="store_true")
group.add_argument("--livemode", "-l", action="store_true")
group = parser.add_mutually_exclusive_group()
group.add_argument("--export", "-f", action="store_true")
group.add_argument("--interim", "-i", action="store_true")
parser.add_argument("--inputdir", "-s")
parser.add_argument("--outputdir", "-o")
parser.add_argument("--console", "-c", action="store_true")
opts = parser.parse_args()
testMode  = opts.testmode
fullMode  = not opts.interim
inputdir  = opts.inputdir
outputdir = opts.outputdir
logger    = cdr.Logging.get_logger("CG2Public", console=opts.console)
modes     = (
    "TEST" if testMode else "LIVE",
    "EXPORT" if fullMode else "INTERIM",
)
logger.info("Running in %s mode", "/".join(modes))
if inputdir:
    logger.info("Input directory: %s", inputdir)
if outputdir:
    logger.info("Output directory: %s", outputdir)


# Create the Control instance, which finds the latest publishing job output
# ----------------------------------------------------------
control = Control()
lastJobDir = control.jobDir
logger.info("Latest publishing job: %s", lastJobDir)

# Find the document types published
# ----------------------------------
if inputdir:
    # If the directory name is not fully specified
    # it must be located in the default directory
    # --------------------------------------------
    if ":" in inputdir:
        control.inputDir = inputdir
    else:
        control.inputDir = "%s/%s" % (Control.SOURCEBASE, inputdir)
else:
    control.inputDir = "%s/%s" % (Control.SOURCEBASE, control.jobDir)

jobDir = os.path.basename(control.jobDir)
logger.info("Using publishing job: %s", jobDir)
pubDirs = getDocumentTypes(control.inputDir)

# Setting the path and creating the new directory for the
# licensee data to be stored.
# ---------------------------------------------------------
if outputdir:
    control.outputDir = outputdir
elif testMode:
    control.outputDir = "%s/Test/%s" % (Control.OUTPUTBASE, jobDir)
else:
    control.outputDir = "%s/%s" % (Control.OUTPUTBASE, jobDir)

# Creating the output directory
# ------------------------------
try:
    logger.info("Copying from directory: %s", jobDir)
    logger.info("Creating directory: %s", control.outputDir)
    os.mkdir(control.outputDir)
except:
    if testMode:
        logger.warning("Directory already exists...OK in TEST mode")
    else:
        logger.exception("Error creating directory...bailing")
        sys.exit(1)

# Process one directory at a time
# -------------------------------
warnings = False
for directory in pubDirs:
    if directory not in Control.EXCLUDEDIRS:
        try:
            failed_validation = control.copy(directory)
        except Exception as e:
            logger.exception("Copying %s failed", directory)
            sys.exit(1)
        if failed_validation:
            warnings = True
            logger.warning("Validation error(s) processing %s", directory)
            logger.warning("Documents with Errors: %r", failed_validation)
    else:
        logger.info("%s skipped", directory)

if warnings:
    logger.warnings("CG2Public.py - Finished with Warnings")
    sys.exit(1)

# A few auxiliary files also need to be copied
# --------------------------------------------
if fullMode:
    logger.info("Writing aux files and DTD")
    for auxFile in Control.AUXFILES:
        shutil.copy("%s/%s" % (control.inputDir, auxFile), control.outputDir)
    shutil.copy("%s/%s" % (Control.DTDDIR, Control.PDQDTD), control.outputDir)

logger.info("CG2Public.py - Finished")
sys.exit(0)
