#----------------------------------------------------------------------
#
# $Id: cdrmailer.py,v 1.1 2001-10-06 21:50:15 bkline Exp $
#
# Base class for mailer jobs
#
# $Log: not supported by cvs2svn $
#----------------------------------------------------------------------

import cdr, cdrdb, cdrxmllatex, os, re, smtplib, sys, time, xml.dom.minidom

#----------------------------------------------------------------------
# Object for managing mailer processing.
#----------------------------------------------------------------------
class MailerJob:

    #------------------------------------------------------------------
    # Class-level values.
    #------------------------------------------------------------------
    CDR_EMAIL     = "cdr@mmdb2.nci.nih.gov"
    SMTP_RELAY    = "MAILFWD.NIH.GOV"
    LOGFILE       = "d:/cdr/log/mailer.log"
    LATEX_OPTS    = "-halt-on-error -quiet -interaction batchmode"
    DEF_PRINTER   = "\\\\CIPSFS1\\HP8100"
    ADDR_PATTERN  = re.compile("<Address>(.*)</Address>", re.DOTALL)
    ERR_PATTERN   = re.compile("<Err>(.*)</Err>")

    #------------------------------------------------------------------
    # Constructor for base class.
    #------------------------------------------------------------------
    def __init__(self, jobId):
        self.id          = jobId
        self.nMailers    = 0
        self.docIds      = []
        self.recipients  = {}
        self.documents   = {}
        self.parms       = {}
        self.printer     = MailerJob.DEF_PRINTER
        
    #------------------------------------------------------------------
    # Driver for mailer job processing.
    #------------------------------------------------------------------
    def run(self):
        try:
            self.log("starting mailer job")
            self.loadSettings()
            self.createQueue()
            self.fillQueue()
            self.printQueue()
            self.cleanup("Success", "Processed %d mailers" % self.nMailers)
            self.log("finished mailer job")
        except:
            (eType, eValue) = sys.exc_info()[:2]
            errMessage = eValue and eValue or eType 
            self.log("ERROR: %s" % errMessage)
            self.cleanup("Failure", errMessage)

    #------------------------------------------------------------------
    # Append message to logfile.
    #------------------------------------------------------------------
    def log(self, message):
        try:
            now = time.ctime(time.time())
            msg = "[%s] Job %d: %s" % (now, self.id, message)
            open(MailerJob.LOGFILE, "a").write(msg + "\n")
        except:
            pass

    #------------------------------------------------------------------
    # Prepare initial settings for job.
    #------------------------------------------------------------------
    def loadSettings(self):
        self.getDates()
        self.getCdrSession()
        self.getDbConnection()
        self.loadDbInfo()

    #------------------------------------------------------------------
    # Calculate needed dates (now and two months from now).
    #------------------------------------------------------------------
    def getDates(self):
        now           = time.localtime(time.time())
        deadline      = (now[0], now[1] + 2, now[2], 0, 0, 0, 0, 0, -1)
        deadline      = time.localtime(time.mktime(deadline))
        self.now      = time.strftime("%Y-%m-%dT%H:%M:%S", now)
        self.deadline = time.strftime("%Y-%m-%d", deadline)
    
    #------------------------------------------------------------------
    # Log into the CDR server.
    #------------------------------------------------------------------
    def getCdrSession(self):
        rsp          = cdr.login("cdrmailers", "cdrmailers")
        match        = self.ERR_PATTERN.search(rsp)
        if match:
            raise "CDR login failure: %s" % match.group(1)
        self.session = rsp

    #------------------------------------------------------------------
    # Log into the CDR database.
    #------------------------------------------------------------------
    def getDbConnection(self):
        try:
            self.conn   = cdrdb.connect("CdrPublishing")
            self.cursor = self.conn.cursor()
        except cdrdb.Error, info:
            raise "database connection failure: %s" % info[1][0]

    #------------------------------------------------------------------
    # Load the settings for this job from the database.
    #------------------------------------------------------------------
    def loadDbInfo(self):
        self.getPubProcRow()
        self.getPubProcDocRows()
        self.getPubProcParmRows()

    #------------------------------------------------------------------
    # Load the row which matches this job from the pub_proc table.
    #------------------------------------------------------------------
    def getPubProcRow(self):
        try:
            self.cursor.execute("""\
                SELECT output_dir, email
                  FROM pub_proc
                 WHERE id = ?""", (self.id,))
            row = self.cursor.fetchone()
            if not row:
                raise "unable to find job %d" % self.id
            (self.outputDir, self.email) = row
        except cdrdb.Error, info:
            raise "database error retrieving pub_proc row: %s" % info[1][0]

    #------------------------------------------------------------------
    # Load the list of document IDs (with version numbers) for this job.
    #------------------------------------------------------------------
    def getPubProcDocRows(self):
        try:
            self.cursor.execute("""\
                SELECT doc_id, doc_version
                  FROM pub_proc_doc
                 WHERE pub_proc = ?""", (self.id,))
            self.docList = self.cursor.fetchall()
            if not self.docList:
                raise "no documents found for job %d" % self.id
            for doc in self.docList: 
                self.docIds.append(doc[0])
        except cdrdb.Error, err:
            raise "database error retrieving pub_proc_doc rows: %s" % err[1][0]

    #------------------------------------------------------------------
    # Load the parameters stored in the pub_proc_parm table for this job.
    #------------------------------------------------------------------
    def getPubProcParmRows(self):
        try:
            self.cursor.execute("""\
                SELECT parm_name, parm_value
                  FROM pub_proc_parm
                 WHERE pub_proc = ?
              ORDER BY id""", (self.id))
            rows = self.cursor.fetchall()
            if rows:
                for row in rows:
                    if not self.parms.has_key(row[0]):
                        self.parms[row[0]] = []
                    self.parms[row[0]].append(row[1])
                    if row[0] == "Printer":
                        self.printer = row[1]
        except cdrdb.Error, info:
            raise "database error retrieving job parms: %s" % info[1][0]

    #------------------------------------------------------------------
    # Create and populate the print queue.
    #------------------------------------------------------------------
    def createQueue(self):
        self.queue = []
        try:
            os.chdir(self.outputDir)
        except:
            raise "failure setting working directory to %s" % self.outputDir

    #------------------------------------------------------------------
    # Placeholder for method to populate the print queue for the job.
    #------------------------------------------------------------------
    def fillQueue(self):
        raise "fillQueue() must be defined by derived class"

    #------------------------------------------------------------------
    # Print the jobs in the queue.
    #------------------------------------------------------------------
    def printQueue(self):
        for job in self.queue:
            job.Print(self.printer, self.log)

    #------------------------------------------------------------------
    # Clean up.
    #------------------------------------------------------------------
    def cleanup(self, status, message):
        try:
            self.updateStatus(status, message)
            self.sendMail()
            if self.session: cdr.logout(self.session)
        except:
            pass
            
    #----------------------------------------------------------------------
    # Generate a document for tracking a mailer.
    #----------------------------------------------------------------------
    def addMailerTrackingDoc(self, doc, recipient, mailerType):
    
        recipId   = "CDR%010d" % recipient.id
        docId     = "CDR%010d" % doc.id
        addrMatch = MailerJob.ADDR_PATTERN.search(recipient.address)
        if not addrMatch:
            raise "address not found for %s" % (recipId)
        address = addrMatch.group(1)
        xml = """\
<CdrDoc Type="Mailer">
 <CdrDocCtl>
  <DocTitle>Mailer for document %s sent to %s</DocTitle>
 </CdrDocCtl>
 <CdrDocXml><![CDATA[
  <Mailer xmlns:cdr="cips.nci.nih.gov/cdr">
   <Type>%s</Type>
   <JobId>%d</JobId>
   <Recipient cdr:ref="%s">%s</Recipient>
   <Address>%s</Address>
   <Document cdr:ref="%s">%s</Document>
   <Sent>%s</Sent>
   <Deadline>%s</Deadline>
  </Mailer>]]>
 </CdrDocXml>
</CdrDoc>
""" % (docId, recipId, mailerType, self.id, recipId, recipient.name, 
       address, docId, doc.title, self.now, self.deadline)
        rsp   = cdr.addDoc(self.session, doc = xml, checkIn = "Y", ver = "Y")
        match = self.ERR_PATTERN.search(rsp)
        if match:
            err = match.group(1)
            raise "failure adding tracking document for %s: %s" % (docId, err)
        self.nMailers += 1
        digits = re.sub("[^\d]", "", rsp)
        return int(digits)

    #------------------------------------------------------------------
    # Update the pub_proc table's status.
    #------------------------------------------------------------------
    def updateStatus(self, status, message = None):
        try:
            if message:
                self.cursor.execute("""\
                    UPDATE pub_proc
                       SET status = ?,
                           messages = ?,
                           completed = GETDATE()
                     WHERE id = ?""", (status, message, self.id))
            else:
                self.cursor.execute("""\
                    UPDATE pub_proc
                       SET status = ?,
                           completed = GETDATE()
                     WHERE id = ?""", (status, self.id))
            self.conn.commit()
        except:
            pass

    #------------------------------------------------------------------
    # Inform the user that the job has completed.
    #------------------------------------------------------------------
    def sendMail(self):
        try:
            if self.email:
                server  = smtplib.SMTP(MailerJob.SMTP_RELAY)
                sender  = MailerJob.CDR_EMAIL
                subject = "CDR Mailer Job Status"
                message = """\
From: %s
To: %s
Subject: %s

Job %d has completed.  You can view a status report for this job at:

    http://mmdb2.nci.nih.gov/cgi-bin/cdr/PubStatus.py?id=%d

Please do not reply to this message.
""" % (sender, self.email, subject, self.id, self.id)
                server.sendmail(sender, [self.email], message)
                server.quit()
        except:
            (eType, eValue) = sys.exc_info()[:2]
            eMessage = eValue and eValue or eType
            self.log("failure sending email to %s: %s" % self.email, eMessage)

    #------------------------------------------------------------------
    # Retrieve the CIPS contact address for a mailer recipient.
    #------------------------------------------------------------------
    def getCipsContactAddress(self, id):
        docId   = cdr.normalize(id)
        filters = ["name:CIPS Contact Address"]
        result  = cdr.filterDoc(self.session, filters, docId)
        if type(result) == type(""):
            raise "failure extracting contact address for %s: %s" % (
                docId, 
                result)
        return result[0]

    #----------------------------------------------------------------------
    # Generate LaTeX source for a mailer document.
    #----------------------------------------------------------------------
    def makeLatex(self, docId, filters):

        # XXX Specify version when Mike's ready.
        docId = cdr.normalize(docId)
        result = cdr.filterDoc(self.session, filters, docId)
        if type(result) == type(""):
            raise "failure filtering Summary document %s: %s" % (docId, result)
        try:
            docDom = xml.dom.minidom.parseString(result[0])
            return cdrxmllatex.makeLatex(docDom, "Summary", "initial")
        except:
            (eType, eValue) = sys.exc_info()[:2]
            eMsg = eValue and eValue or eType
            raise "failure generating LaTeX for %s: %s" % (docId, eMsg)

    #----------------------------------------------------------------------
    # Convert LaTeX to PostScript.
    #----------------------------------------------------------------------
    def makePS(self, latex, passCount, basename, jobType):

        try:

            # Save the LaTeX source.
            filename = basename + ".tex"
            open(filename, "w").write(latex)

            # Convert it to PostScript.
            for i in range(passCount):
                rc = os.system("latex %s %s" % (self.LATEX_OPTS, filename))
                if rc:
                    raise "failure running LaTeX processor on %s" % filename
            rc = os.system("dvips -q %s" % basename)
            if rc:
                raise "failure running dvips processor on %s.dvi" % basename
            return PrintJob(basename + ".ps", jobType)

        except:
            (eType, eValue) = sys.exc_info()[:2]
            eMsg = eValue and eValue or eType
            raise "failure converting %s.tex to %s.ps: %s" % (basename,
                                                              basename, 
                                                              eMsg)

#----------------------------------------------------------------------
# Object to hold a document to be sent to the printer.
#----------------------------------------------------------------------
class PrintJob:
    MAINDOC       = 1
    COVERPAGE     = 2
    PAGES_PATTERN = re.compile("%%Pages: (\\d+)")
    MAX_STAPLED   = 25
    STAPLE_PROLOG = """\
\033%-12345X@PJL
@PJL SET FINISH=STAPLE
@PJL SET STAPLEOPTION=ONE
@PJL SET OUTBIN=OPTIONALOUTBIN2
@PJL ENTER LANGUAGE=POSTSCRIPT
"""
    def __init__(self, filename, type):
        self.filename = filename
        self.type     = type
        self.staple   = 0
        if type == PrintJob.MAINDOC:
            pages = None
            ps = open(filename)
            while 1:
                line = ps.readline()
                match = PrintJob.PAGES_PATTERN.match(line)
                if match:
                    pages = int(match.group(1))
                    break
            if not pages:
                raise "can't find page count in %s" % filename
            if pages <= PrintJob.MAX_STAPLED:
                self.staple = 1
            ps.close()

    #------------------------------------------------------------------
    # Send the current print job to the specified printer.
    #------------------------------------------------------------------
    def Print(self, printer, logFunc):
        logFunc("printing %s %s" % (
            self.filename,
            self.staple and "(stapled)" or ""))
        if 0:
            prn = open(printer, "w")
            doc = open(self.filename)
            prn.write((self.staple and STAPLE_PROLOG or "") + doc.read())
            doc.close()
            prn.close()

#----------------------------------------------------------------------
# Object to hold information about a mailer recipient.
#----------------------------------------------------------------------
class Recipient:
    def __init__(self, id, name, address = None):
        self.id      = id
        self.name    = name
        self.address = address
        self.docs    = []

#----------------------------------------------------------------------
# Object to hold information about a mailer document.
#----------------------------------------------------------------------
class Document:
    def __init__(self, id, title, docType):
        self.id         = id
        self.title      = title
        self.docType    = docType
