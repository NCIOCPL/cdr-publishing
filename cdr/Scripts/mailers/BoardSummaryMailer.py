#----------------------------------------------------------------------
#
# $Id: BoardSummaryMailer.py,v 1.6 2001-10-09 12:07:19 bkline Exp $
#
# Master driver script for processing PDQ Editorial Board Member mailings.
#
# $Log: not supported by cvs2svn $
# Revision 1.5  2001/10/07 15:16:25  bkline
# Added call to getDeadline().
#
# Revision 1.4  2001/10/07 12:49:12  bkline
# Reduced use of publicly accessible members.
#
# Revision 1.3  2001/10/06 23:42:08  bkline
# Changed parameters to makeLatex() method.
#
# Revision 1.2  2001/10/06 21:52:30  bkline
# Factored out base class MailerJob.
#
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
    # Overrides method in base class for filling the print queue.
    #----------------------------------------------------------------------
    def fillQueue(self):
        self.__getBoardId()
        self.__getBoardMembers()
        self.__getDocuments()
        self.__makeCoverSheet()
        self.__makePackets()

    #----------------------------------------------------------------------
    # Locate the parameter which specifies the board.
    #----------------------------------------------------------------------
    def __getBoardId(self):
        boardParm = self.getParm("Board")
        if not boardParm:
            raise "parameter for Board not specified"
        digits = re.sub("[^\d]", "", boardParm[0])
        self.boardId = int(digits)
        self.log("processing board CDR%010d" % self.boardId)

    #----------------------------------------------------------------------
    # Gather the list of board members.
    #----------------------------------------------------------------------
    def __getBoardMembers(self):
        try:
            self.getCursor().execute("""\
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
            rows = self.getCursor().fetchall()
            for row in rows:
                if row[2] in self.getDocIds():
                    recipient = self.getRecipients().get(row[0])
                    doc       = self.getDocuments().get(row[2])
                    if not recipient:
                        self.log("found board member %s" % row[1])
                        addr      = self.getCipsContactAddress(row[0])
                        recipient = cdrmailer.Recipient(row[0], row[1], addr)
                        self.getRecipients()[row[0]] = recipient
                    if not doc:
                        doc = cdrmailer.Document(row[2], row[3], "Summary")
                        self.getDocuments()[row[2]] = doc
                    recipient.getDocs().append(doc)
        except cdrdb.Error, info:
            raise "database error finding board members: %s" % info[1][0]

    #----------------------------------------------------------------------
    # Produce LaTeX source for all summaries to be mailed out.
    #----------------------------------------------------------------------
    def __getDocuments(self):
        filters = ['name:Summary Filter1',
                   'name:Summary Filter2',
                   'name:Summary Filter3',
                   'name:Summary Filter4',
                   'name:Summary Filter5']
        for docId in self.getDocuments().keys():
            self.log("generating LaTeX for CDR%010d" % docId)
            doc = self.getDocuments()[docId]
            doc.latex = self.makeLatex(doc, filters, "initial")

    #----------------------------------------------------------------------
    # Generate a main cover page and add it to the print queue.
    #----------------------------------------------------------------------
    def __makeCoverSheet(self):
        filename = "MainCoverPage.txt"
        f = open(filename, "w")
        f.write("\n\nPDQ Board Member Summary Review Mailer\n\n")
        f.write("Job Number: %d\n\n" % self.getId())
        for key in self.getRecipients().keys():
            recipient = self.getRecipients()[key]
            f.write("Board Member: %s (CDR%010d)\n" % (recipient.getName(), 
                                                       recipient.getId()))
            for doc in recipient.getDocs():
                f.write("\tSummary CDR%010d: %s\n" % (doc.getId(),
                                                      doc.getTitle()))
        f.close()
        job = cdrmailer.PrintJob(filename, cdrmailer.PrintJob.COVERPAGE)
        self.addToQueue(job)

    #------------------------------------------------------------------
    # Walk through the board member list, generating packets for each.
    #------------------------------------------------------------------
    def __makePackets(self):
        coverLetterName     = "../PDQSummaryReviewerCoverLetter.tex"
        coverLetterTemplate = open(coverLetterName).read()
        for key in self.getRecipients().keys():
            self.__makePacket(self.getRecipients()[key], coverLetterTemplate)

    #------------------------------------------------------------------
    # Create a mailer packet for a single mailer recipient.
    #------------------------------------------------------------------
    def __makePacket(self, recipient, coverLetterTemplate):
        self.log("building packet for %s" % recipient.getName())
        for doc in recipient.getDocs():
            self.__addDocToPacket(recipient, doc, coverLetterTemplate)

    #------------------------------------------------------------------
    # Add one summary document to a board member's packet.
    #------------------------------------------------------------------
    def __addDocToPacket(self, recipient, doc, template):

        # Add document to the repository for tracking replies to the mailer.
        mailerId = self.addMailerTrackingDoc(doc, recipient, self.MAILER_TYPE)

        # Create a cover letter.
        latex    = template.replace('@@REVIEWER@@', recipient.getName())
        latex    = latex.replace('@@SUMMARY@@', doc.getTitle())
        latex    = latex.replace('@@DEADLINE@@', self.getDeadline())
        basename = 'CoverLetter-%d-%d' % (recipient.getId(), doc.getId())
        jobType  = cdrmailer.PrintJob.COVERPAGE
        self.addToQueue(self.makePS(latex, 1, basename, jobType))

        # Customize the LaTeX for this copy of the summary.
        nPasses  = doc.latex.getLatexPassCount()
        latex    = doc.latex.getLatex()
        latex    = latex.replace('@@BoardMember@@', recipient.getName())
        latex    = latex.replace('@@MailerDocId@@', str(mailerId))
        basename = 'Mailer-%d-%d' % (recipient.getId(), doc.getId())
        jobType  = cdrmailer.PrintJob.MAINDOC
        self.addToQueue(self.makePS(latex, nPasses, basename, jobType))
        self.log("added CDR%010d to packet" % doc.getId())

if __name__ == "__main__":
    sys.exit(BoardSummaryMailerJob(int(sys.argv[1])).run())
