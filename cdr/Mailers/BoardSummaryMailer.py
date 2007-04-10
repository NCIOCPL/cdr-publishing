#----------------------------------------------------------------------
#
# $Id: BoardSummaryMailer.py,v 1.13 2007-04-10 13:06:07 kidderc Exp $
#
# Master driver script for processing PDQ Editorial Board Member mailings.
#
# $Log: not supported by cvs2svn $
# Revision 1.12  2004/04/27 15:44:00  bkline
# Added support for use of PDQBoardMemberInfo documents.
#
# Revision 1.11  2004/04/19 15:54:25  bkline
# Suppressed creation of mailing labels at Lakshmi's request (#1188).
#
# Revision 1.10  2003/05/13 19:57:21  bkline
# Replaced explitly enumerated filter list with named filter set invocation.
#
# Revision 1.9  2003/02/13 20:17:36  bkline
# Added filter to strip out "Changes to summary" SummarySection elements.
#
# Revision 1.8  2003/01/28 15:20:52  bkline
# Added date and mailer ID to summary mailer cover letters.
#
# Revision 1.7  2002/11/08 21:46:08  bkline
# Ready for user testing.
#
# Revision 1.6  2001/10/09 12:07:19  bkline
# Removed superfluous constructor override.  Removed title truncation
# from top cover page.  Fixed typo (this -> self).
#
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

import cdrdb, cdrmailer, re, sys, UnicodeToLatex, time

#----------------------------------------------------------------------
# Derived class for PDQ Editorial Board Member mailings.
#----------------------------------------------------------------------
class BoardSummaryMailerJob(cdrmailer.MailerJob):

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
        self.__boardId = int(digits)
        self.log("processing board CDR%010d" % self.__boardId)

    #----------------------------------------------------------------------
    # Gather the list of board members.
    #----------------------------------------------------------------------
    def __getBoardMembers(self):
        Person = self.getParm("Person")
        if (Person and ( len(Person) > 0) ):
            sWhere = ' AND person.id = %s' % Person
        else:
            sWhere = ''
		
        memberPath = '/Summary/SummaryMetaData/PDQBoard/Board/@cdr:ref'
        boardPath  = '/Summary/SummaryMetaData/PDQBoard/BoardMember/@cdr:ref'
        infoPath   = '/PDQBoardMemberInfo/BoardMemberName/@cdr:ref'
        try:
            self.getCursor().execute("""\
                SELECT DISTINCT person.id,
                                person.title,
                                summary.id,
                                summary.title,
                                pub_proc_doc.doc_version,
                                member_info.doc_id
                           FROM document person
                           JOIN query_term member
                             ON member.int_val = person.id
                           JOIN document summary
                             ON summary.id = member.doc_id
                           JOIN query_term board
                             ON board.doc_id = summary.id
                           JOIN pub_proc_doc
                             ON pub_proc_doc.doc_id = summary.id
                           JOIN query_term member_info
                             ON member_info.int_val = person.id
                          WHERE board.int_val = ?
                            AND pub_proc_doc.pub_proc = ?
                            %s
                            AND board.path = '%s'
                            AND member.path = '%s'
                            AND member_info.path = '%s'
                            AND LEFT(board.node_loc, 8) =
                                LEFT(member.node_loc, 8)
                       ORDER BY person.title,
                                person.id,
                                summary.title,
                                summary.id""" % (sWhere, memberPath, boardPath,
                                                 infoPath), 
                                                (self.__boardId,
                                                 self.getId()))
                                                 
            rows = self.getCursor().fetchall()
            for (personId, personTitle, summaryId, summaryTitle, docVer,
                 memberInfo) in rows:
                if summaryId in self.getDocIds():
                    recipient = self.getRecipients().get(personId)
                    doc       = self.getDocuments().get(summaryId)
                    if not recipient:
                        self.log("found board member %s" % personTitle)
                        addr      = self.getBoardMemberAddress(personId,
                                                               memberInfo)
                        recipient = cdrmailer.Recipient(personId, personTitle,
                                                        addr)
                        self.getRecipients()[personId] = recipient
                    if not doc:
                        doc = cdrmailer.Document(summaryId, summaryTitle,
                                                 "Summary", docVer)
                        self.getDocuments()[summaryId] = doc
                    recipient.getDocs().append(doc)
        except cdrdb.Error, info:
            raise "database error finding board members: %s" % (
                info[1][0].encode('ascii'))

    #----------------------------------------------------------------------
    # Produce LaTeX source for all summaries to be mailed out.
    #----------------------------------------------------------------------
    def __getDocuments(self):
        filters = ["set:Mailer Summary Set"]
        for docId in self.getDocuments().keys():
            self.log("generating LaTeX for CDR%010d" % docId)
            doc = self.getDocuments()[docId]
            doc.latex = self.makeLatex(doc, filters)

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
                title = doc.getTitle().encode('latin-1', 'replace')
                if len(title) > 50: title = title[:50] + " ..."
                f.write("\tSummary CDR%010d: %s\n" % (doc.getId(), title))
        f.close()
        job = cdrmailer.PrintJob(filename, cdrmailer.PrintJob.PLAIN)
        self.addToQueue(job)

    #------------------------------------------------------------------
    # Walk through the board member list, generating packets for each.
    #------------------------------------------------------------------
    def __makePackets(self):
        coverLetterParm     = self.getParm("CoverLetter")
        basePath            = self.getMailerIncludePath() + "/"
        coverLetterName     = basePath + coverLetterParm[0]
        coverLetterFile     = open(coverLetterName)
        coverLetterTemplate = coverLetterFile.read()
        sepSheetName        = basePath + "ListOfSummaries.tex"
        sepSheetFile        = open(sepSheetName)
        sepSheetTemplate    = sepSheetFile.read()
        coverLetterFile.close()
        sepSheetFile.close()
        
        for key in self.getRecipients().keys():
            self.__makePacket(self.getRecipients()[key], coverLetterTemplate,
                                                         sepSheetTemplate)

    #------------------------------------------------------------------
    # Create a mailer packet for a single mailer recipient.
    #------------------------------------------------------------------
    def __makePacket(self, recipient, coverLetterTemplate, sepSheetTemplate):
        self.log("building packet for %s" % recipient.getName())

        # Create a separator sheet.
        docList   = ""
        basename  = 'SeparatorSheet-%d' % recipient.getId()
        jobType   = cdrmailer.PrintJob.COVERPAGE
        name      = recipient.getAddress().getAddressee()
        latex     = sepSheetTemplate.replace('@@REVIEWER@@', name)
        for doc in recipient.getDocs():
            docList += "\\item %d: %s\n" % (doc.getId(),
                    UnicodeToLatex.convert(doc.getTitle().split(';')[0]))
        latex     = latex.replace('@@SUMMARYLIST@@', docList)
        self.addToQueue(self.makePS(latex, 1, basename, jobType))

        # Add the document mailers.
        for doc in recipient.getDocs():
            self.__addDocToPacket(recipient, doc, coverLetterTemplate)

    #------------------------------------------------------------------
    # Add one summary document to a board member's packet.
    #------------------------------------------------------------------
    def __addDocToPacket(self, recipient, doc, template):

        # Add document to the repository for tracking replies to the mailer.
        mailerId = self.addMailerTrackingDoc(doc, recipient, self.getSubset())

        # Create a cover letter.
        docTitle = UnicodeToLatex.convert(doc.getTitle().split(';')[0])
        name     = recipient.getAddress().getAddressee()
        latex    = template.replace('@@REVIEWER@@', name)
        latex    = latex.replace('@@SUMMARYTITLE@@', docTitle)
        latex    = latex.replace('@@MAILERID@@', 'CDR%010d' % mailerId)
        latex    = latex.replace('@@DATE@@', time.strftime("%B %d, %Y"))
        basename = 'CoverLetter-%d-%d' % (recipient.getId(), doc.getId())
        jobType  = cdrmailer.PrintJob.COVERPAGE
        self.addToQueue(self.makePS(latex, 1, basename, jobType))

        # Customize the LaTeX for this copy of the summary.
        nPasses  = doc.latex.getLatexPassCount()
        latex    = doc.latex.getLatex()
        latex    = latex.replace('@@BoardMember@@', name)
        #latex   = latex.replace('@@MailerDocId@@', str(mailerId))
        basename = 'Mailer-%d-%d' % (recipient.getId(), doc.getId())
        jobType  = cdrmailer.PrintJob.MAINDOC
        self.addToQueue(self.makePS(latex, nPasses, basename, jobType))
        self.log("added CDR%010d to packet" % doc.getId())

if __name__ == "__main__":
    sys.exit(BoardSummaryMailerJob(int(sys.argv[1])).run())
