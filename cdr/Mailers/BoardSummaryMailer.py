#----------------------------------------------------------------------
#
# $Id: BoardSummaryMailer.py,v 1.2 2001-10-06 21:52:30 bkline Exp $
#
# Master driver script for processing PDQ Editorial Board Member mailings.
#
# $Log: not supported by cvs2svn $
# Revision 1.1  2001/10/05 20:38:09  bkline
# Initial revision
#
#----------------------------------------------------------------------

import cdrdb, cdrmailer, re, sys

#----------------------------------------------------------------------
# Derived class for PDQ Editorial Board Member mailings.
#----------------------------------------------------------------------
class BoardSummaryMailerJob(cdrmailer.MailerJob):

    #----------------------------------------------------------------------
    # Specific constant values for subclass.
    #----------------------------------------------------------------------
    MAILER_TYPE = "PDQ Editorial Board"

    #----------------------------------------------------------------------
    # Constructor for derived BoardSummaryMailerJob class.
    #----------------------------------------------------------------------
    def __init__(self, jobId):
        cdrmailer.MailerJob.__init__(self, jobId)

    #----------------------------------------------------------------------
    # Overrides method in base class for filling the print queue.
    #----------------------------------------------------------------------
    def fillQueue(self):
        self.getBoardId()
        self.getBoardMembers()
        self.getDocuments()
        self.makeCoverSheet()
        self.makePackets()

    #----------------------------------------------------------------------
    # Locate the parameter which specifies the board.
    #----------------------------------------------------------------------
    def getBoardId(self):
        if not self.parms.has_key("Board"):
            raise "parameter for Board not specified"
        digits = re.sub("[^\d]", "", self.parms["Board"][0])
        self.boardId = int(digits)
        self.log("processing board CDR%010d" % self.boardId)

    #----------------------------------------------------------------------
    # Gather the list of board members.
    #----------------------------------------------------------------------
    def getBoardMembers(self):
        try:
            self.cursor.execute("""\
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
                       ORDER BY p.title, p.id, s.title, s.id""", 
                       (self.boardId,))
            rows = self.cursor.fetchall()
            for row in rows:
                #self.log("row[0]=%d row[2]=%d" % (row[0], row[2]))
                if row[2] in self.docIds:
                    recipient = self.recipients.get(row[0])
                    doc       = self.documents.get(row[2])
                    if not recipient:
                        self.log("found board member %s" % row[1])
                        addr      = self.getCipsContactAddress(row[0])
                        recipient = cdrmailer.Recipient(row[0], row[1], addr)
                        self.recipients[row[0]] = recipient
                    if not doc:
                        doc = cdrmailer.Document(row[2], row[3], "Summary")
                        self.documents[row[2]] = doc
                    recipient.docs.append(doc)
                    #self.log("%d docs for recipient" % len(recipient.docs))
        except cdrdb.Error, info:
            raise "database error finding board members: %s" % info[1][0]

    #----------------------------------------------------------------------
    # Produce LaTeX source for all summaries to be mailed out.
    #----------------------------------------------------------------------
    def getDocuments(self):
        filters = ['name:Summary Filter1',
                   'name:Summary Filter2',
                   'name:Summary Filter3',
                   'name:Summary Filter4',
                   'name:Summary Filter5']
        for docId in self.documents.keys():
            self.log("generating LaTeX for CDR%010d" % docId)
            self.documents[docId].latex = self.makeLatex(docId, filters)

    #----------------------------------------------------------------------
    # Generate a main cover page and add it to the print queue.
    #----------------------------------------------------------------------
    def makeCoverSheet(self):
        filename = "MainCoverPage.txt"
        f = open(filename, "w")
        f.write("\n\nPDQ Board Member Summary Review Mailer\n\n")
        f.write("Job Number: %d\n\n" % self.id)
        for key in self.recipients.keys():
            recipient = self.recipients[key]
            f.write("Board Member: %s (CDR%010d)\n" % (recipient.name, 
                                                       recipient.id))
            for doc in recipient.docs:
                f.write("\tSummary CDR%010d: %s\n" % (doc.id, doc.title[:50]))
        f.close()
        self.queue.append(cdrmailer.PrintJob(filename, 
                                             cdrmailer.PrintJob.COVERPAGE))

    #------------------------------------------------------------------
    # Walk through the board member list, generating packets for each.
    #------------------------------------------------------------------
    def makePackets(self):
        coverLetterName     = "../PDQSummaryReviewerCoverLetter.tex"
        coverLetterTemplate = open(coverLetterName).read()
        for key in self.recipients.keys():
            self.makePacket(self.recipients[key], coverLetterTemplate)

    #------------------------------------------------------------------
    # Create a mailer packet for a single mailer recipient.
    #------------------------------------------------------------------
    def makePacket(self, recipient, coverLetterTemplate):
        self.log("building packet for %s" % recipient.name)
        for doc in recipient.docs:
            self.addDocToPacket(recipient, doc, coverLetterTemplate)

    #------------------------------------------------------------------
    # Add one summary document to a board member's packet.
    #------------------------------------------------------------------
    def addDocToPacket(self, recipient, doc, template):

        # Add document to the repository for tracking replies to the mailer.
        mailerId = self.addMailerTrackingDoc(doc, recipient, self.MAILER_TYPE)

        # Create a cover letter.
        latex = template.replace('@@REVIEWER@@', recipient.name)
        latex = latex.replace('@@SUMMARY@@', doc.title)
        latex = latex.replace('@@DEADLINE@@', doc.title)
        basename = 'CoverLetter-%d-%d' % (recipient.id, doc.id)
        ps = self.makePS(latex, 1, basename, cdrmailer.PrintJob.COVERPAGE)
        self.queue.append(ps)

        # Customize the LaTeX for this copy of the summary.
        nPasses = doc.latex.getLatexPassCount()
        latex = doc.latex.getLatex().replace('@@BoardMember@@', recipient.name)
        latex = latex.replace('@@MailerDocId@@', str(mailerId))
        basename = 'Mailer-%d-%d' % (recipient.id, doc.id)
        ps = self.makePS(latex, nPasses, basename, cdrmailer.PrintJob.MAINDOC)
        self.queue.append(ps)
        self.log("added CDR%010d to packet" % doc.id)

if __name__ == "__main__":
    BoardSummaryMailerJob(int(sys.argv[1])).run()
