#----------------------------------------------------------------------
#
# $Id: BoardSummaryMailer.py,v 1.1 2001-10-05 20:38:09 bkline Exp $
#
# Master driver script for processing PDQ Editorial Board Member mailings.
#
# $Log: not supported by cvs2svn $
#----------------------------------------------------------------------

import cdr, cdrdb, cdrmailer, os, re, smtplib, sys, time, xml.dom.minidom

LOGFILE       = 'd:/cdr/log/mailer.log'
SMTP_RELAY    = 'MAILFWD.NIH.GOV'
CONN          = None
SESSION       = None
EMAIL         = None
JOBID         = ""
LATEX_OPTS    = '-halt-on-error -quiet -interaction batchmode'
DEF_PRINTER   = r'\\CIPSFS1\HP8100'
PAGES_PATTERN = re.compile("%%Pages: (\\d+)")
ADDR_PATTERN  = re.compile("<Address>(.*)</Address>", re.DOTALL)
MAX_STAPLED   = 25
STAPLE_PROLOG = """\
\033%-12345X@PJL
@PJL SET FINISH=STAPLE
@PJL SET STAPLEOPTION=ONE
@PJL SET OUTBIN=OPTIONALOUTBIN2
@PJL ENTER LANGUAGE=POSTSCRIPT
"""

#----------------------------------------------------------------------
# Log message to logfile.
#----------------------------------------------------------------------
def log(message):
    try:
        msg = "[%s] Job %d: %s" % (time.ctime(time.time()), JOBID, message)
        open(LOGFILE, 'a').write(msg + "\n")
    except:
        pass

#----------------------------------------------------------------------
# Inform the user that the job has completed.
#----------------------------------------------------------------------
def sendMail(address, jobId):
    if not address: return # Sanity check!
    server = smtplib.SMTP(SMTP_RELAY)
    sender = "cdr@mmdb2.nci.nih.gov"
    subject = "CDR Publishing Job Status"
    message = """\
From: %s
To: %s
Subject: %s

Job %d has completed.

You can view a status report for this job at:

http://mmdb2.nci.nih.gov/cgi-bin/cdr/PubStatus.py?id=%d

--
Please do not reply to this message.
""" % (sender, address, subject, jobId, jobId)
    server.sendmail(sender, [address], message)
    server.quit()

#----------------------------------------------------------------------
# Object to hold a document to be sent to the printer.
#----------------------------------------------------------------------
class PrintJob:
    SUMMARY = 1
    COVERPAGE = 2
    def __init__(self, filename, type):
        self.filename = filename
        self.type     = type
        self.staple   = 0
        if type == PrintJob.SUMMARY:
            pages = None
            ps = open(filename)
            while 1:
                line = ps.readline()
                match = PAGES_PATTERN.match(line)
                if match:
                    pages = int(match.group(1))
                    break
            if not pages:
                raise "Can't find page count in %s" % filename
            if pages <= MAX_STAPLED:
                self.staple = 1
            ps = None
    def Print(self, printer):
        log("printing %s %s" % (
            self.filename,
            self.staple and "(stapled)" or ""))
        if 0:
            prn = open(printer, "w")
            doc = open(self.filename).read()
            prn.write((self.staple and STAPLE_PROLOG or "") + doc)

#----------------------------------------------------------------------
# Object to hold job settings for mailer.
#----------------------------------------------------------------------
class JobSettings:
    def __init__(self, jobId, board, outputDir, printer, email = None):
        self.jobId     = jobId
        self.board     = board
        self.outputDir = outputDir
        self.printer   = printer
        self.email     = email

#----------------------------------------------------------------------
# Object to hold information about a board member.
#----------------------------------------------------------------------
class BoardMember:
    def __init__(self, id, name, address = None, summaries = []):
        self.id        = id
        self.name      = name
        self.address   = address
        self.summaries = []

#----------------------------------------------------------------------
# Object to hold information about a summary.
#----------------------------------------------------------------------
class Summary:
    def __init__(self, id, title):
        self.id    = id
        self.title = title

#----------------------------------------------------------------------
# Look up job settings in the publishing tables.
#----------------------------------------------------------------------
def getJobSettings(cursor, jobId):
    try:
        cursor.execute("""\
            SELECT output_dir, email
              FROM pub_proc
             WHERE id = ?
""", (jobId))
        row = cursor.fetchone()
        if not row:
            raise 'Unable to find job %d' % jobId
        (outputDir, email) = row
    except cdrdb.Error, info:
        raise 'Database error retrieving job settings: %s' % info[1][0]
    try:
        cursor.execute("""\
            SELECT parm_name, parm_value
              FROM pub_proc_parm
             WHERE pub_proc = ?
          ORDER BY ID
""", (jobId))
        rows = cursor.fetchall()
        board = None
        printer = DEF_PRINTER
        if rows:
            for row in rows:
                if row[0] == 'Board':
                    board = row[1]
                    break
                elif row[0] == 'Printer':
                    printer = row[1]
        if not board:
            raise 'Board parameter not found'
    except cdrdb.Error, info:
        raise 'Database error retrieving job parameters: %s' % info[1][0]
    return JobSettings(jobId, board, outputDir, printer, email)

#----------------------------------------------------------------------
# Find the documents which this job should process.
#----------------------------------------------------------------------
def getDocList(cursor, jobId):
    try:
        cursor.execute("""\
            SELECT doc_id, doc_version
              FROM pub_proc_doc
             WHERE pub_proc = ?
""", (jobId))
        docList = cursor.fetchall()
        if not docList:
            raise 'No documents found for job %d' % jobId
    except cdrdb.Error, info:
        raise 'Database error retrieving job documents: %s' % info[1][0]
    return docList

#----------------------------------------------------------------------
# Retrieve the CIPS contact address for the board member.
#----------------------------------------------------------------------
def getAddress(id, session):
    docId   = cdr.normalize(id)
    filters = ['name:CIPS Contact Address']
    result  = cdr.filterDoc(session, filters, docId)
    if type(result) == type(""):
        raise 'Failure extracting contact address for %s: %s' % (docId, result)
    return result[0]

#----------------------------------------------------------------------
# Gather the list of board members.
#----------------------------------------------------------------------
def findBoardMembers(cursor, board, docIds, memberCounts, session):
    try:
        digits = re.sub('[^\d]', '', board)
        boardId  = int(digits)
        cursor.execute("""\
            SELECT DISTINCT p.id, p.title, s.id, s.title
                       FROM document p
                       JOIN query_term m
                         ON m.int_val = p.id
                       JOIN document s
                         ON s.id = m.doc_id
                       JOIN query_term b
                         ON b.doc_id = s.id
                      WHERE b.int_val = ?
                        AND b.path = '/Summary/SummaryMetaData/PDQBoard'
                                   + '/Board/@cdr:ref'
                        AND m.path = '/Summary/SummaryMetaData/PDQBoard'
                                   + '/BoardMember/@cdr:ref'
                        AND LEFT(b.node_loc, 8) = LEFT(m.node_loc, 8)
                   ORDER BY p.title, p.id, s.title, s.id
""", (boardId,))
        rows = cursor.fetchall()
        boardMembers = {}
        for row in rows:
            memberId     = row[0]
            memberName   = row[1]
            summaryId    = row[2]
            summaryTitle = row[3]
            if summaryId in docIds:
                if not boardMembers.has_key(memberId):
                    log("found board member %s" % memberName)
                    address = getAddress(memberId, session)
                    boardMembers[memberId] = BoardMember(memberId,
                                                         memberName,
                                                         address)
                boardMembers[memberId].summaries.append(Summary(summaryId,
                                                                summaryTitle))
                memberCounts[summaryId] += 1
        return boardMembers
    except cdrdb.Error, info:
        raise 'Database error finding board members: %s' % info[1][0]

#----------------------------------------------------------------------
# Filter the documents and generate the LaTeX source.
#----------------------------------------------------------------------
def makeLatexSource(docList, memberCounts, docErrors, session):
    docLatex = {}
    filters = ['name:Summary Filter1',
               'name:Summary Filter2',
               'name:Summary Filter3',
               'name:Summary Filter4',
               'name:Summary Filter5']
    for doc in docList:
        log("filtering document CDR%010d" % doc[0])
        if memberCounts[doc[0]] < 1:
            docErrors[doc[0]] = "No Board Members found"
            continue
        docId = cdr.normalize(doc[0])
        result = cdr.filterDoc(session, filters, docId)
        if type(result) == type(""):
            raise 'Failure filtering Summary document %s: %s' % (docId, result)
        try:
            docDom = xml.dom.minidom.parseString(result[0])
            log("creating LaTeX for %s" % docId)
            docLatex[doc[0]] = cdrmailer.process(docDom, "Summary", "initial")
        except Exception, eInfo:
            raise 'Failure generating LaTeX for %s: %s' % (docId, str(eInfo))
    return docLatex

#----------------------------------------------------------------------
# Generate the main cover page.
#----------------------------------------------------------------------
def mainCoverPage(jobId, boardMembers):
    filename = "MainCoverPage.txt"
    f = open(filename, "w")
    f.write("\n\nPDQ Board Member Summary Review Mailer\n\n")
    f.write("Job Number: %d\n\n" % jobId)
    for key in boardMembers.keys():
        member = boardMembers[key]
        f.write("Board Member: %s (CDR%010d)\n" % (member.name, member.id))
        for summary in member.summaries:
            f.write("\tSummary CDR%010d: %s\n" % (summary.id,
                                                  summary.title[:50]))
    return PrintJob(filename, PrintJob.COVERPAGE)

#----------------------------------------------------------------------
# Generate a document for tracking a mailer.
#----------------------------------------------------------------------
def addMailerTrackingDoc(session, member, summary, now, deadline, jobId):
    memberId = "CDR%010d" % member.id
    summaryId = "CDR%010d" % summary.id
    addrMatch = ADDR_PATTERN.search(member.address)
    if not addrMatch:
        raise "Address not found for %s in %s" % (memberId, member.address)
    address = addrMatch.group(1)
    doc = """\
<CdrDoc Type='Mailer'>
 <CdrDocCtl>
  <DocTitle>Mailer for document %s sent to %s</DocTitle>
 </CdrDocCtl>
 <CdrDocXml><![CDATA[
  <Mailer xmlns:cdr='cips.nci.nih.gov/cdr'>
   <Type>PDQ Editorial Board</Type>
   <JobId>%d</JobId>
   <Recipient cdr:ref='%s'>%s</Recipient>
   <Address>%s</Address>
   <Document cdr:ref='%s'>%s</Document>
   <Sent>%s</Sent>
   <Deadline>%s</Deadline>
  </Mailer>]]>
 </CdrDocXml>
</CdrDoc>
""" % (summaryId, memberId, jobId, memberId, member.name, address, summaryId,
       summary.title, now, deadline)
    docId = cdr.addDoc(session, doc = doc, checkIn = 'Y', ver = 'Y')
    if docId.find("<Err") != -1:
        raise "Failure adding tracking document for %s: %s" % (summaryId,
                                                               docId)
    digits = re.sub('[^\d]', '', docId)
    return int(digits)

#----------------------------------------------------------------------
# Convert LaTeX to PostScript.
#----------------------------------------------------------------------
def makePS(latex, basename, type):

    # Save the LaTeX source.
    filename = basename + '.tex'
    log('writing %s' % filename)
    open(filename, 'w').write(latex)

    # Convert it to PostScript.
    rc = os.system('latex %s %s' % (LATEX_OPTS, filename))
    if rc:
        raise 'Failure running LaTeX processor on %s' % filename
    rc = os.system('dvips -q %s' % basename)
    if rc:
        raise 'Failure running dvips processor on %s.dvi' % basename
    return PrintJob(basename + '.ps', type)

#----------------------------------------------------------------------
# Update the pub_proc table's status.
#----------------------------------------------------------------------
def updateStatus(jobId, status, message = None):
    try:
        cursor = CONN.cursor()
        if message:
            cursor.execute("""\
                UPDATE pub_proc
                   SET status = ?,
                       messages = ?,
                       completed = GETDATE()
                 WHERE id = ?
""", (status, message, jobId))
        else:
            cursor.execute("""\
                UPDATE pub_proc
                   SET status = ?,
                       completed = GETDATE()
                 WHERE id = ?
""", (status, jobId))
        CONN.commit()
    except:
        pass

#----------------------------------------------------------------------
# Process the job.
#----------------------------------------------------------------------
def main(jobId):

    #------------------------------------------------------------------
    # Verify that we got a job ID.
    #------------------------------------------------------------------
    if not jobId:
        raise "Job ID not provided"
    jobId = int(jobId)
    log("starting job %d..." % jobId)

    #------------------------------------------------------------------
    # Calculate needed dates (now and two months from now).
    #------------------------------------------------------------------
    now = time.localtime(time.time())
    deadline = (now[0], now[1] + 2, now[2], 0, 0, 0, 0, 0, -1)
    deadline = time.localtime(time.mktime(deadline))
    now = time.strftime("%Y-%m-%dT%H:%M:%S", now)
    deadline = time.strftime("%Y-%m-%d", deadline)
    
    #------------------------------------------------------------------
    # Log into the CDR server.
    #------------------------------------------------------------------
    global SESSION
    SESSION = cdr.login('rmk', '***REDACTED***')
    log("logged in as session ...")
    log("... " + SESSION)

    #------------------------------------------------------------------
    # Log into the CDR database.
    #------------------------------------------------------------------
    global CONN
    try:
        CONN = cdrdb.connect('CdrPublishing')
        cursor = CONN.cursor()
    except cdrdb.Error, info:
        raise 'Database connection failure: %s' % info[1][0]
    log("connected to CDR database...")
    sys.stdout.flush()

    #------------------------------------------------------------------
    # Gather the job settings.
    #------------------------------------------------------------------
    global EMAIL
    jobSettings = getJobSettings(cursor, jobId)
    EMAIL = jobSettings.email
    log("job settings retrieved...")
    docList = getDocList(cursor, jobId)
    log("doc list retrieved...")
    docIds = []
    memberCounts = {}
    for doc in docList:
        docIds.append(doc[0])
        memberCounts[doc[0]] = 0

    #------------------------------------------------------------------
    # Gather the list of board members.
    #------------------------------------------------------------------
    boardMembers = findBoardMembers(cursor, jobSettings.board, docIds, 
                                    memberCounts, SESSION)

    #------------------------------------------------------------------
    # Filter the documents and generate the LaTeX source.
    #------------------------------------------------------------------
    docErrors = {}
    docLatex = makeLatexSource(docList, memberCounts, docErrors, SESSION)

    #------------------------------------------------------------------
    # Prepare to build a print queue in the job's directory.
    #------------------------------------------------------------------
    try:
        lastPart = jobSettings.outputDir
        slash = lastPart.rfind('/')
        if slash == -1:
            slash = lastPart.rfind('\\')
        if slash != -1:
            lastPart = lastPart[slash + 1:]
        log("cd to %s" % lastPart)
        os.chdir(jobSettings.outputDir)
    except:
        err = "Failure setting working directory to %s" % jobSettings.outputDir
        raise err
    printQueue = [mainCoverPage(jobId, boardMembers)]

    #------------------------------------------------------------------
    # Walk through the board member list, generating packets for each.
    #------------------------------------------------------------------
    nPackets = 0
    coverLetterTemplate = open("../PDQSummaryReviewerCoverLetter.tex").read()
    for mKey in boardMembers.keys():
        member = boardMembers[mKey]
        log("building packet for %s" % member.name)

        # Walk through the documents this member is to receive.
        for summary in member.summaries:
            log("processing summary CDR%010d" % summary.id)

            # Create a document for tracking the mailer.
            mailerId = addMailerTrackingDoc(SESSION, member, summary, now, 
                                            deadline, jobId)

            # Create a cover letter.
            latex = coverLetterTemplate.replace('@@REVIEWER@@', member.name)
            latex = latex.replace('@@SUMMARY@@', summary.title)
            latex = latex.replace('@@DEADLINE@@', summary.title)
            basename = 'CoverLetter-%d-%d' % (member.id, summary.id)
            printQueue.append(makePS(latex, basename, PrintJob.COVERPAGE))

            # Customize the LaTeX for this copy of the summary.
            latex = docLatex[summary.id]
            latex = latex.replace('@@BoardMember@@', member.name)
            latex = latex.replace('@@MailerDocId@@', str(mailerId))
            basename = 'Mailer-%d-%d' % (member.id, summary.id)
            printQueue.append(makePS(latex, basename, PrintJob.SUMMARY))
            nPackets += 1

    # Print the queue.
    for job in printQueue:
        job.Print(jobSettings.printer)

    # Clean up.
    cdr.logout(SESSION)
    log("logged out of CDR")
    updateStatus(jobId, "Success", "Printed %d mailer packets" % nPackets)
    log("updated database status")
    sendMail(jobSettings.email, jobId)
    log("sent email report to %s" % jobSettings.email)
    return 0

if __name__ == "__main__":
    try:
        JOBID = int(sys.argv[1])
        result = main(JOBID)
        if result:
            log(result)
        else:
            log("ok")
    except:
        (t,v) = sys.exc_info()[:2]
        log(v and v or t)
        if SESSION:
            cdr.logout(SESSION)
        if CONN:
            updateStatus(JOBID, "Failure", v and v or t)
        sendMail(EMAIL, JOBID)
