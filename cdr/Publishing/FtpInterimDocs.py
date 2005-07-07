#----------------------------------------------------------------------
#
# File Name: FtpInterimDocs.py
# ============================
# Package and submit interim update documents (mid-month updates) to the 
# CIPSFTP server and store files in the directory cdr.
# The documents are located in subdirectories named JobNNN with NNN
# being an integer number.  Provide all jobIDs for the documents that 
# should be packaged within one subdirectory on the FTP server as a
# command line argument.
# For instance, if an interim update ran under JobID=1234 and an
# interim remove ran under JobID=1235 you want to package these 
# documents by entering the command
#     FtpHotfixDocs 1234 1235
# 
# Once the documents have been packaged and copied to the FTP server 
# there is a post-process that will have to run on the FTP server.
#
# The original name of this program was FtpHotfixDocs.py but got
# renamed after the update process got named 'Interim Update'.
#
# $Id: FtpInterimDocs.py,v 1.1 2005-07-07 22:03:23 venglisc Exp $
# $Log: not supported by cvs2svn $
#----------------------------------------------------------------------
import sys, re, string, cdr, os, shutil, time

if len(sys.argv) < 2:
   sys.stder.write('usage: FtpInterimDocs jobID [JobID [...]]\n')
   sys.exit(1)

# Setting directory and file names
# --------------------------------
log      = "d:\\cdr\\log\\interim.log" 
outDir   = 'd:\\' + os.path.join('cdr', 'Output')
pubDir   = 'd:\\' + os.path.join('cdr', 'publishing')
hfDir    = os.path.join(outDir, 'mid-month')
dateStr  = time.strftime("%Y-%m-%d-%H%M", time.localtime())
newDir   = os.path.join(hfDir, dateStr)
manifest = 'media_catalog.txt'
rmDir    = 0
cdrDir   = 0

jobId = string.atoi(sys.argv[1])
divider = "=" * 60

# ------------------------------------------------------------
# Function to remove duplicate list elements from a given list
# ------------------------------------------------------------
def removeDups(list):
    result = []
    for item in list:
        if item not in result:
            result.append(item)
    return result

# Open Log file and enter start message
# -------------------------------------
open(log, "a").write("Job %d: %s\n    %d: Started at: %s\n" % \
                    (jobId, divider, jobId, time.ctime(time.time())))
try:

    print "Processing files..."
    rmDoc = re.compile('Removed this document')
    mfFiles = []
    for k in sys.argv[1:]:
        oldDir = os.path.join(outDir, 'Job' + k)
        print "In Directory: ", oldDir
        os.chdir(oldDir)
        filelist = os.listdir(oldDir)
        # print "File list:     ", filelist
        for file in filelist:
            # The interim update may contain invalid documents.  Skip
            # over the directory and continue to process the files.
            # -------------------------------------------------------
            if file != 'InvalidDocs':
                f = open(file, 'r')
                continue
            if file == manifest:
                # Read all lines of the manifest file into a list
                # that will later need to be sorted uniquely
                # -----------------------------------------------
                for line in f:
                    mfFiles.append(line)
                continue
            else:
                # Inspect the file to identify if document is removed or updated
                # --------------------------------------------------------------
                text = f.readline()
            f.close()

            # Create Directory with date stamp
            # --------------------------------
            if not os.path.exists(newDir):
                os.mkdir(newDir)

            # Move the removed files to the remove directory
            # ----------------------------------------------
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

            # A single manifest file gets written after all directories 
            # have been read 
            # ---------------------------------------------------------
            # elif file == manifest:
            #     pass
            # Move the updated files to the cdr directory
            # -------------------------------------------
            else:
                # Copy updated documents to update directory.
                # Create directory if it doesn't exist
                # -------------------------------------------
                # print 'File' + file + ' was updated'
                destDir = os.path.join(newDir, 'cdr')
   
                if not os.path.exists(destDir):
                    os.mkdir(destDir)
                    cdrDir = 1
        
                shutil.copy(file, destDir)
                open(log, "a").write("    %d: Copied %s to %s\n" %
                              (jobId, file, destDir))

    # After all directories have been read we need to write a combined
    # manifest file.  Sort and dedup the content before writing
    # ----------------------------------------------------------------
    if len(mfFiles):
        open(log, "a").write("    %d: Writing manifest file\n" %
                        (jobId))
        print "Writing media_catalog.txt file..."

        mfFiles.sort()
        noDups = removeDups(mfFiles)
        os.chdir(newDir)
        f = open(manifest, 'w')
        for line in noDups:
            print >> f, line,
        f.close()

    # Creating the FTP command file
    # -----------------------------
    open(log, "a").write("    %d: Creating ftp command file\n" %
                        (jobId))
    print "Writing ftp command file..."
    os.chdir(pubDir)
    ftpCmd = open ('FtpInterimDocs.txt', 'w')
    ftpCmd.write('open cipsftp.nci.nih.gov\n')
    ftpCmd.write('cdrdev\n')
    ftpCmd.write('***REMOVED***\n')
    ftpCmd.write('binary\n')
    ftpCmd.write('cd /u/ftp/qa/pdq/mid-month\n')
    ftpCmd.write('mkdir ' + dateStr + '\n')
    ftpCmd.write('cd ' + dateStr + '\n')
    ftpCmd.write('lcd d:/cdr/Output/mid-month/' + dateStr + '\n')

    # If a manifest file exists it needs to be pushed
    # -----------------------------------------------
    if len(mfFiles):
        ftpCmd.write('put ' + manifest + '\n')

    # Only add this part if updated documents exist.
    # ----------------------------------------------
    # print "cdrDir = " + str(cdrDir)
    if cdrDir:
        ftpCmd.write('mkdir cdr\n')
        ftpCmd.write('lcd cdr\n')
        ftpCmd.write('cd cdr\n')
        ftpCmd.write('mput *\n')
        ftpCmd.write('lcd ..\n')
        ftpCmd.write('cd ..\n')

    # Only add this part if removed documents exist.
    # ----------------------------------------------
    # print "rmDir = " + str(rmDir)
    if rmDir:
        ftpCmd.write('mkdir remove\n')
        ftpCmd.write('lcd remove\n')
        ftpCmd.write('cd  remove\n')
        ftpCmd.write('mput *\n')

    ftpCmd.write('bye\n')
    ftpCmd.close()

    open(log, "a").write("    %d: Copy files to ftp server\n" %
                        (jobId))
    print "Copy files to ftp server..."

    # FTP the Interim documents to ftpserver
    # --------------------------------------
    mycmd = cdr.runCommand("c:/Winnt/System32/ftp.exe -i -s:FtpInterimDocs.txt")

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
