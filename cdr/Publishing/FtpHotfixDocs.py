#----------------------------------------------------------------------
#
# File Name: FtpHotfixDocs.py
# ============================
# Package and submit Hot-fix documents (mid-month updates) to the 
# CIPSFTP server and store files in the directory cdr.
# The documents are located in subdirectories named JobNNN with NNN
# being an integer number.  Provide all jobIDs for the documents that 
# should be packaged within one subdirectory on the FTP server as a
# command line argument.
# For instance, if a hot-fix export ran under JobID=1234 and a hot-fix
# remove ran under JobID=1235 you want to package these documents by
# entering the command
#     FtpHotfixDocs 1234 1235
# 
# Once the documents have been packaged and copied to the FTP server 
# there is a post-process that will have to run on the FTP server.
#
# $Id: FtpHotfixDocs.py,v 1.4 2005-01-24 22:48:25 venglisc Exp $
# $Log: not supported by cvs2svn $
# Revision 1.3  2004/10/15 20:25:22  bkline
# Fixed error of processing if no removed documents exist.
#
# Revision 1.2  2004/10/07 23:08:08  bkline
# Fixed the FTP process and changed the directory name to cdr from update.
#
# Revision 1.1  2004/10/06 21:48:44  bkline
# Initial version of program to package and copy hot-fix documents to the
# FTP server.
#
#----------------------------------------------------------------------
import sys, re, string, cdr, os, shutil, time

if len(sys.argv) < 2:
   sys.stder.write('usage: FtpHotfixDocs jobID [JobID [...]]\n')
   sys.exit(1)

# Setting directory and file names
# --------------------------------
log = "d:\\cdr\\log\\hotfix.log" 
outDir = 'd:\\' + os.path.join('cdr', 'Output')
pubDir = 'd:\\' + os.path.join('cdr', 'publishing')
hfDir  = os.path.join(outDir, 'mid-month')
dateStr = time.strftime("%Y-%m-%d-%H%M", time.localtime())
newDir = os.path.join(hfDir, dateStr)
rmDir  = 0

jobId = string.atoi(sys.argv[1])
divider = "=" * 60

# Open Log file and enter start message
# -------------------------------------
open(log, "a").write("Job %d: %s\n    %d: Started at: %s\n" % \
                    (jobId, divider, jobId, time.ctime(time.time())))
try:

    print "Processing files..."
    rmDoc = re.compile('Removed this document')
    for k in sys.argv[1:]:
       oldDir = os.path.join(outDir, 'Job' + k)
       os.chdir(oldDir)
       filelist = os.listdir(oldDir)
       # print filelist
       for file in filelist:
	  # Inspect the file to identify if document is removed or updated
	  # --------------------------------------------------------------
          f = open(file, 'r')
          text = f.readline()
	  f.close()

	  # Create Directory with date stamp
	  # --------------------------------
	  if not os.path.exists(newDir):
              os.mkdir(newDir)

          if re.search(rmDoc, text):
	     # Copy deleted documents to remove directory.
	     # Create directory if it doesn't exist
	     # -------------------------------------------
             # print 'File' + file + ' got deleted'
             destDir = os.path.join(newDir, 'remove')
   
	     if not os.path.exists(destDir):
	         os.mkdir(destDir)
                 rmDir = 1
	     
	     shutil.copy(file, destDir)
             open(log, "a").write("    %d: Copied %s to %s\n" %
                              (jobId, file, destDir))

          else:
	     # Copy updated documents to update directory.
	     # Create directory if it doesn't exist
	     # -------------------------------------------
             # print 'File' + file + ' was updated'
             destDir = os.path.join(newDir, 'cdr')
   
	     if not os.path.exists(destDir):
	         os.mkdir(destDir)
	    
	     shutil.copy(file, destDir)
             open(log, "a").write("    %d: Copied %s to %s\n" %
                              (jobId, file, destDir))

    # Creating the FTP command file
    # -----------------------------
    open(log, "a").write("    %d: Creating ftp command file\n" %
                        (jobId))
    os.chdir(pubDir)
    ftpCmd = open ('FtpHotfixDocs.txt', 'w')
    ftpCmd.write('open cipsftp.nci.nih.gov\n')
    ftpCmd.write('cdrdev\n')
    ftpCmd.write('***REMOVED***\n')
    ftpCmd.write('binary\n')
    ftpCmd.write('cd /u/ftp/qa/pdq/mid-month\n')
    ftpCmd.write('mkdir ' + dateStr + '\n')
    ftpCmd.write('cd ' + dateStr + '\n')
    ftpCmd.write('mkdir cdr\n')
    ftpCmd.write('lcd d:/cdr/Output/mid-month/' + dateStr + '\n')
    ftpCmd.write('lcd cdr\n')
    ftpCmd.write('cd cdr\n')
    ftpCmd.write('mput *\n')

    # Only add this part if removed documents exist.
    # ----------------------------------------------
    if rmDir:
       ftpCmd.write('mkdir ../remove\n')
       ftpCmd.write('lcd ../remove\n')
       ftpCmd.write('cd  ../remove\n')
       ftpCmd.write('mput *\n')
    ftpCmd.write('bye\n')
    ftpCmd.close()


    open(log, "a").write("    %d: Copy files to ftp server\n" %
                        (jobId))
    print "Copy files to ftp server..."

    # FTP the Hot-fix documents to ftpserver
    # --------------------------------------
    mycmd = cdr.runCommand("c:/Winnt/System32/ftp.exe -i -s:FtpHotfixDocs.txt")

    open(log, "a").write("    %d: FTP command return code: %s\n" %
                        (jobId, mycmd.code))
    if mycmd.code == 1:
       open(log, "a").write("    %d: ---------------------------\n%s\n" %
                        (jobId, mycmd.output))

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
