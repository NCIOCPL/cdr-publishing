#----------------------------------------------------------------------
# File Name: FtpVendorDocs.py
# ===========================
# Package and submit export documents (full updates) to the 
# CIPSFTP server and store files in the directory incoming.
# The documents are located in subdirectories of the publishing 
# directory named JobNNNN with NNNN being an integer number.  
# For instance, if the export ran under JobID=1234 you want to 
# enter the following command
#     python FtpVendorDocs 1234
# 
# Once the documents have been packaged and copied to the FTP server 
# there is a post-process that will have to run on the FTP server.
#
# $Id: FtpVendorDocs.py,v 1.1 2004-12-16 22:47:44 venglisc Exp $
# $Log: not supported by cvs2svn $
#----------------------------------------------------------------------
import sys, re, string, cdr, os, shutil, time

if len(sys.argv) < 2:
   sys.stder.write('usage: FtpVendorDocs jobID\n')
   sys.exit(1)

# Setting directory and file names
# --------------------------------
log = "d:\\cdr\\log\\vendor.log" 
outDir = 'd:\\' + os.path.join('cdr', 'Output')
pubDir = 'd:\\' + os.path.join('cdr', 'publishing')
venDir  = os.path.join(outDir, 'VendorDocs')

jobId = string.atoi(sys.argv[1])
divider = "=" * 60

# Open Log file and enter start message
# -------------------------------------
open(log, "a").write("Job %d: %s\n    %d: Started at: %s\n" % \
                    (jobId, divider, jobId, time.ctime(time.time())))
try:
    # Remove the content of the VendorDocs directory and copy the
    # new data from directory JobNNNN (NNNN = JobId) to the VendorDocs
    # directory
    # ----------------------------------------------------------------
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
    os.chdir(venDir)
    oldlist = os.listdir(venDir)
    print "Processing files..."

    # Select all directories from the VendorDocs directory
    # and bzip them so they can easily be ftp'ed to CIPSFTP
    # -----------------------------------------------------
    for file in oldlist:
       if os.path.isdir(file):
          open(log, "a").write("    %d: Creating %s.tar.bz2\n" %
                              (jobId, file))
          print "  Creating zip file for %s ..." % file
          zipfile = "tar cvfj %s.tar.bz2 %s" % (file, file)
          zipit = cdr.runCommand(zipfile)
          shutil.rmtree(file)

    # Creating the FTP command file
    # -----------------------------
    open(log, "a").write("    %d: Creating ftp command file\n" %
                        (jobId))
    os.chdir(pubDir)
    print pubDir

    ftpCmd = open ('FtpVendorDocs.txt', 'w')
    ftpCmd.write('open cipsftp.nci.nih.gov\n')
    ftpCmd.write('cdrdev\n')
    ftpCmd.write('***REMOVED***\n')
    ftpCmd.write('binary\n')
    ftpCmd.write('cd /u/ftp/qa/pdq/monthly/incoming/monthly\n')
    ftpCmd.write('lcd ' + venDir + '\n')
    ftpCmd.write('mdel *.tar.bz2\n')
    ftpCmd.write('del  media_catalog.txt\n')
    ftpCmd.write('mput *.tar.bz2\n')
    ftpCmd.write('put  media_catalog.txt\n')
    ftpCmd.write('bye\n')
    ftpCmd.close()

    open(log, "a").write("    %d: Copy files to ftp server\n" %
                        (jobId))
    print "Copy files to ftp server..."

    # FTP the vendor documents to ftpserver
    # --------------------------------------
    mycmd = cdr.runCommand("c:/Winnt/System32/ftp.exe -i -s:FtpVendorDocs.txt")

    open(log, "a").write("    %d: FTP command return code: %s\n" %
                        (jobId, mycmd.code))
    if mycmd.code == 1:
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
