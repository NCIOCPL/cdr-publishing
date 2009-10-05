import ftplib, time

FTPSERVER  = 'cipsftp.nci.nih.gov'
FTPUSER    = 'cdrdev'
FTPPWD     = '***REMOVED***'
ftpDir     = '/u/ftp/test/pdq/incoming/full'
ftp        = ftplib.FTP(FTPSERVER, timeout = 10)
ftp.login(FTPUSER, FTPPWD)
chCwd      = ftp.cwd(ftpDir)
print "chCwd: %s" % chCwd
ftpFile    = 'Job6123.tar.gz'
now        = time.strftime("%Y%m%d%H%M%S")
target     = "Job6123-%s.tar.gz" % now
ftp.storbinary('STOR %s' % target, open(ftpFile, 'rb'))
