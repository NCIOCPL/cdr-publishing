#----------------------------------------------------------------------
# File Name: NLMExport.py
# =======================
# Package and submit NLM protocol export documents (full updates
# or weekly updates) to the CIPSFTP server and store files in the 
# directory incoming.
# For instance, if the export ran under JobID=1234 you want to 
# enter the following command
#     python NLMExport 1234 monthly
# if this was a monthly production job or
#     python NLMExport 1234 weekly
# if this was a weekly hot-fix job.
#
# Once the documents have been packaged and copied to the FTP server 
# there is a post-process that will have to run on the FTP server.
#
# $Id: NLMExport.py,v 1.8 2008-06-03 21:43:05 bkline Exp $
# $Log: not supported by cvs2svn $
# Revision 1.7  2006/05/22 23:01:28  venglisc
# Modified the script to run the NlmClinicalStudies.xsl filter from the
# d:\cdr\utilities directory instead of the d:\home\cnetoper\NLM directory.
# (Bug 2184)
#
# Revision 1.6  2005/11/09 21:04:07  venglisc
# Removed section to update filter from CVS prior to running the data
# conversion. (Bug 1903)
#
# Revision 1.5  2005/08/05 17:59:25  venglisc
# Added test for existance of CVSROOT variable and added a few more log
# messages. (Bug 1715)
#
# Revision 1.4  2005/07/18 20:39:36  venglisc
# Modified code to allow to FTP a data set that had been correctly created
# as part of the weekly interim update but did not get copied.
# A third parameter can be specified indicating the date of the data set
# to be copied.
#
# Revision 1.3  2005/07/07 21:28:28  venglisc
# Modified code to log the command line arguments in the log file.
# I also changed the name of the log file from hotfix_NLM to interim_NLM.
# Additionally, I have modified the code to allow to skip the part that
# copies all vendor data to the VendorDocs directory to allow the process
# to be rerun without going through the lengthy copy process. (Bug 1751)
#
# Revision 1.2  2005/01/28 23:13:39  venglisc
# Modified script to adjust changes in directory structure on CIPSFTP.
#
# Revision 1.1  2004/12/30 18:45:04  venglisc
# Initial version of script to filter protocol data to NLM format and copy
# resulting documents to CIPSFTP.
#
#----------------------------------------------------------------------
import sys, re, string, cdr, os, shutil, time

if len(sys.argv) < 3:
   sys.stderr.write('usage: python NLMExport jobID jobType [copy]\n')
   sys.stderr.write('   eg: python NLMExport 12345 monthly|weekly copy\n')
   sys.exit(1)

# Setting directory and file names
# --------------------------------
log     = "d:\\cdr\\log\\interim_NLM.log" 
rootDir = os.getenv('SystemRoot')
outDir  = 'd:\\' + os.path.join('cdr', 'Output')
pubDir  = 'd:\\' + os.path.join('cdr', 'publishing')
utilDir = 'd:\\' + os.path.join('cdr', 'Utilities')
venDir  =          os.path.join(outDir, 'VendorDocs')
nlmProg = 'NlmFilter.py'
ftpFile = 'FtpNlmDocs.txt'

jobId   = string.atoi(sys.argv[1])
jobType = sys.argv[2]

divider = "=" * 60
dateStr = time.strftime("%Y-%m-%d-%H%M", time.localtime())

def outputExists(nlmDir):
   try:
      os.stat(nlmDir)
      return True
   except:
      return False


# Open Log file and enter start message
# -------------------------------------
open(log, "a").write("Job %d: %s\n    %d: Started at: %s\n" % \
                    (jobId, divider, jobId, time.ctime(time.time())))
open(log, "a").write("    %d: Input parameters: %s\n" %
                              (jobId, sys.argv))
try:
    # Need to change to Utilities directory because the *.xsl filter
    # is run from the working directory.
    # ----------------------------------------------------------------
    os.chdir(utilDir)

    # Remove the content of the VendorDocs directory and copy the
    # new data from directory JobNNNN (NNNN = JobId) to the VendorDocs
    # directory
    # ----------------------------------------------------------------
    if jobType == 'monthly':
       # Only refresh the content of the vendor directory if necessary
       # Passing 4th command line parameter copies the data.
       # -------------------------------------------------------------
       if len(sys.argv) == 4:
           open(log, "a").write("    %d: Removing files in %s\n" %
                              (jobId, venDir))
           print "Removing files..."
           os.chdir(outDir)
           shutil.rmtree(venDir)

           open(log, "a").write("    %d: Copying  files to %s\n" %
                              (jobId, venDir))
           print "Copying files..."
           oldDir = os.path.join(outDir, 'Job' + sys.argv[1])
           shutil.copytree(oldDir, venDir) 
       else:
           open(log, "a").write("    %d: Using files in %s\n" %
                              (jobId, venDir))
           print "Using existing files..."
           

       nlmFilter = nlmProg + ' m' + dateStr + ' ' + venDir

    # For a hot-fix publishing job the program looks in the database
    # for the latest job number and documents that need to be processed
    # -----------------------------------------------------------------
    elif jobType == 'weekly':
       # If the process extracting and converting the data set already
       # ran successfully but failed to FTP the data, a fourth 
       # parameter may be submitted indicating the location of the 
       # data to be FTP'ed.
       # -------------------------------------------------------------
       if len(sys.argv) == 4:
           dateStr = sys.argv[3]

           # Check if specified directory exists
           # -----------------------------------
           doesExist = outputExists(outDir + '\NLMExport\w' + dateStr)
           if not doesExist: 
              open(log, "a").write("    %d: ERROR: Directory does not exist\n" %
                              (jobId))
              open(log, "a").write("    %d: Ended   at: %s\nJob %d: %s\n" %
                        (jobId, time.ctime(time.time()), jobId, divider))
              sys.exit('ERROR: Directory specified does not exist.')

           open(log, "a").write("    %d: FTP existing data set: w%s\n" %
                              (jobId, dateStr))
           print "No data extraction."
           print "FTP existing data set w%s..." % dateStr
       else:
           open(log, "a").write("    %d: Creating data set: w%s\n" %
                              (jobId, dateStr))
           print "Creating data set w%s..." % dateStr

       nlmFilter = nlmProg + ' w' + dateStr
    else:
       print "ERROR:  jobType '%s' not allowed!" % jobType
       open(log, "a").write("    %d: ERROR: jobType '%s' not defined!\n" %
                              (jobId, jobType))
       open(log, "a").write("    %d: Ended   at: %s\nJob %d: %s\n" %
                        (jobId, time.ctime(time.time()), jobId, divider))
       sys.exit()

    # Process the active protocol files by running the NLMFilter.py
    # command
    # -------------------------------------------------------------
    open(log, "a").write("    %d: Processing files in %s\n" %
                              (jobId, utilDir))
    print "Processing files..."

    # Need to change to Utilities directory because the *.xsl filter
    # is run from the working directory.
    # ----------------------------------------------------------------
    os.chdir(utilDir)

    # Submitting the command to create the NLM Export data
    # -----------------------------------------------------
    open(log, "a").write("    %d: Run command:\n    %d: %s\n" %
                              (jobId, jobId, nlmFilter))


    rcResult = cdr.runCommand(nlmFilter)
    # if nlmcmd.code == 1:
    open(log, "a").write("    %d: ---------------------------\n%s\n" %
                        (jobId, rcResult.output))
    open(log, "a").write("    %d: ---------------------------\n" %
                        (jobId))
    print 'NLM: ', rcResult.output or 'OK'

    # Creating the FTP command file to copy files to CIPSFTP
    # ------------------------------------------------------
    open(log, "a").write("    %d: Creating ftp command file\n" %
                        (jobId))
    os.chdir(pubDir)
    print pubDir

    ftpCmd = open (ftpFile, 'w')
    ftpCmd.write('open cipsftp.nci.nih.gov\n')
    ftpCmd.write('cdrdev\n')
    ftpCmd.write('***REMOVED***\n')
    ftpCmd.write('binary\n')

    if jobType == 'monthly':
       ftpCmd.write('cd /u/ftp/qa/nlm/incoming/monthly\n')
       ftpCmd.write('lcd ' + outDir + '\NLMExport\m' + dateStr + '\n')
    else:
       ftpCmd.write('cd /u/ftp/qa/nlm/incoming/mid-month\n')
       ftpCmd.write('lcd ' + outDir + '\NLMExport\w' + dateStr + '\n')

    ftpCmd.write('mdel *.tar.bz2\n')
    ftpCmd.write('mput *.tar.bz2\n')

    # The manifest file is part of the zip file for hot-fix updates
    # -------------------------------------------------------------
    if jobType == 'weekly':
       ftpCmd.write('del dropped.txt\n')
       ftpCmd.write('put dropped.txt\n')
    
    ftpCmd.write('bye\n')
    ftpCmd.close()

    # FTP the vendor documents to ftpserver
    # --------------------------------------
    open(log, "a").write("    %d: Copy files to ftp server\n" %
                        (jobId))
    print "Copy files to ftp server..."

    ftpDocs = rootDir + "/System32/ftp.exe -i -s:" + ftpFile
    mycmd = cdr.runCommand(ftpDocs)

    open(log, "a").write("    %d: FTP command return code: %s\n" %
                        (jobId, mycmd.code))
    if mycmd.code != 0:
       open(log, "a").write("    %d: ---------------------------\n%s\n" %
                        (jobId, mycmd.output))

    print "Processing Complete"
    open(log, "a").write("    %d: Ended   at: %s\nJob %d: %s\n" %
                        (jobId, time.ctime(time.time()), jobId, divider))

except SystemExit:
    # If we've invoked sys.exit() then we've already done our logging.
    pass

except Exception, arg:
    open(log, "a").write("    %d: Failure: %s\n" % 
                        (jobId, arg[0]))
    open(log, "a").write("    %d: Ended   at: %s\nJob %d: %s\n" %
                        (jobId, time.ctime(time.time()), jobId, divider))

except:
    open(log, "a").write("    %d: Unexpected failure\nJob %d: %s\n" % 
                        (jobId, jobId, divider))
    open(log, "a").write("    %d: Ended   at: %s\nJob %d: %s\n" %
                        (jobId, time.ctime(time.time()), jobId, divider))
