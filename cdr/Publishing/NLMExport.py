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
# $Id: NLMExport.py,v 1.2 2005-01-28 23:13:39 venglisc Exp $
# $Log: not supported by cvs2svn $
# Revision 1.1  2004/12/30 18:45:04  venglisc
# Initial version of script to filter protocol data to NLM format and copy
# resulting documents to CIPSFTP.
#
#----------------------------------------------------------------------
import sys, re, string, cdr, os, shutil, time

if len(sys.argv) < 3:
   sys.stderr.write('usage: python NLMExport jobID jobType\n')
   sys.stderr.write('   eg: python NLMExport 12345 monthly|weekly\n')
   sys.exit(1)

# Setting directory and file names
# --------------------------------
log     = "d:\\cdr\\log\\hotfix_NLM.log" 
outDir  = 'd:\\' + os.path.join('cdr', 'Output')
pubDir  = 'd:\\' + os.path.join('cdr', 'publishing')
utilDir = 'd:\\' + os.path.join('cdr', 'Utilities')
venDir  =          os.path.join(outDir, 'VendorDocs')
homeDir = 'd:\\' + os.path.join('home', 'cnetoper')
sandBox =          os.path.join(homeDir, 'cdr', 'Utilities')
workDir =          os.path.join(homeDir, 'NLM')
nlmXsl  = 'NlmClinicalStudy.xsl'
nlmProg = utilDir + '\\NlmFilter.py'
ftpFile = 'FtpNlmDocs.txt'

jobId   = string.atoi(sys.argv[1])
jobType = sys.argv[2]

divider = "=" * 60
dateStr = time.strftime("%Y-%m-%d-%H%M", time.localtime())

# Open Log file and enter start message
# -------------------------------------
open(log, "a").write("Job %d: %s\n    %d: Started at: %s\n" % \
                    (jobId, divider, jobId, time.ctime(time.time())))
try:
    # Ensure we are using the latest filter from CVS
    # ----------------------------------------------
    os.chdir(sandBox)
    upNlm = 'cvs up ' + sandBox + '/' + nlmXsl
    cdr.runCommand(upNlm)
    cpNlm = 'cp ' + nlmXsl + ' ' + workDir
    cdr.runCommand(cpNlm)
    os.chdir(workDir)

    # Remove the content of the VendorDocs directory and copy the
    # new data from directory JobNNNN (NNNN = JobId) to the VendorDocs
    # directory
    # ----------------------------------------------------------------
    if jobType == 'monthly':
       open(log, "a").write("    %d: Removing files in %s\n" %
                              (jobId, venDir))
       print "Removing files..."
       os.chdir(outDir)
       shutil.rmtree(venDir)

       open(log, "a").write("    %d: Copying files to %s\n" %
                              (jobId, venDir))
       print "Copying files..."
       oldDir = os.path.join(outDir, 'Job' + sys.argv[1])
       shutil.copytree(oldDir, venDir) 

       nlmFilter = nlmProg + ' m' + dateStr + ' ' + venDir

    # For a hot-fix publishing job the program looks in the database
    # for the latest job number and documents that need to be processed
    # -----------------------------------------------------------------
    elif jobType == 'weekly':
       nlmFilter = nlmProg + ' w' + dateStr
    else:
       print "ERROR:  jobType '%s' not allowed!" % jobType
       sys.exit()

    # Process the active protocol files by running the NLMFilter.py
    # command
    # -------------------------------------------------------------
    open(log, "a").write("    %d: Processing files in %s\n" %
                              (jobId, workDir))
    print "Processing files..."
    os.chdir(workDir)
    nlmcmd = cdr.runCommand(nlmFilter)
    # if nlmcmd.code == 1:
    open(log, "a").write("    %d: ---------------------------\n%s\n" %
                        (jobId, nlmcmd.output))
    open(log, "a").write("    %d: ---------------------------\n" %
                        (jobId))

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

    ftpDocs = "c:/Winnt/System32/ftp.exe -i -s:" + ftpFile
    mycmd = cdr.runCommand(ftpDocs)

    open(log, "a").write("    %d: FTP command return code: %s\n" %
                        (jobId, mycmd.code))
    if mycmd.code != 0:
       open(log, "a").write("    %d: ---------------------------\n%s\n" %
                        (jobId, mycmd.output))

    print "Processing Complete"
    open(log, "a").write("    %d: Ended   at: %s\nJob %d: %s\n" %
                        (jobId, time.ctime(time.time()), jobId, divider))

except StandardError, arg:
    open(log, "a").write("    %d: Failure: %s\nJob %d: %s\n" % 
                        (jobId, arg[0], jobId, divider))

except SystemExit:
    # The mailers invoke sys.exit(0) when they're done, raising this exception.
    pass

except:
    open(log, "a").write("    %d: Unexpected failure\nJob %d: %s\n" % 
                        (jobId, jobId, divider))
