#----------------------------------------------------------------------
#
# $Id: ProtAbstractMailer.py,v 1.6 2002-10-22 20:22:19 bkline Exp $
#
# Master driver script for processing initial protocol abstract mailers.
#
# $Log: not supported by cvs2svn $
# Revision 1.5  2002/10/10 17:45:16  bkline
# Mods to cover letters.
#
# Revision 1.4  2002/10/10 13:44:25  bkline
# Ready for testing.
#
# Revision 1.3  2002/10/08 01:43:27  bkline
# Added missing clause to SQL query.  Brought cover letter processing
# closer in line with requirements.  Dropped some unnecessary tweaking of
# the personal address filter output.
#
# Revision 1.2  2002/09/12 23:29:50  ameyer
# Removed common routine from individual mailers to cdrmailer.py.
# Added a few trace statements.
#
# Revision 1.1  2002/01/28 09:36:24  bkline
# Adding remaining CDR scripts.
#
#----------------------------------------------------------------------

import cdr, cdrdb, cdrmailer, re, sys

#----------------------------------------------------------------------
# Derived class for protocol abstract mailings.
#----------------------------------------------------------------------
class ProtocolAbstractMailer(cdrmailer.MailerJob):

    #------------------------------------------------------------------
    # Overrides method in base class for filling the print queue.
    #------------------------------------------------------------------
    def fillQueue(self):
        self.__getRecipients()
        self.__getDocuments()
        self.makeIndex()
        self.__makeCoverSheet()
        self.__makeMailers()

    #------------------------------------------------------------------
    # Find lead organization personnel who should receive these mailers.
    #------------------------------------------------------------------
    def __getRecipients(self):
        docType = "InScopeProtocol"
        try:
            self.getCursor().execute("""\
                SELECT DISTINCT recipient.id,
                                recipient.title,
                                protocol.id,
                                protocol.title,
                                doc_version.num,
                                cdrref.value
                           FROM document recipient
                           JOIN query_term cdrref
                             ON cdrref.int_val = recipient.id
                           JOIN query_term cdrid
                             ON cdrid.doc_id = cdrref.doc_id
                            AND LEFT(cdrid.node_loc, 12) =
                                LEFT(cdrref.node_loc, 12)
                           JOIN query_term idref
                             ON idref.doc_id = cdrid.doc_id
                            AND idref.value = cdrid.value
                           JOIN document protocol
                             ON protocol.id = idref.doc_id
                           JOIN doc_version
                             ON doc_version.id = protocol.id
                           JOIN pub_proc_doc
                             ON pub_proc_doc.doc_version = doc_version.num
                            AND pub_proc_doc.doc_id = protocol.id
                          WHERE pub_proc_doc.pub_proc = ?
                            AND cdrref.path = '/InScopeProtocol'
                                            + '/ProtocolAdminInfo'
                                            + '/ProtocolLeadOrg'
                                            + '/LeadOrgPersonnel'
                                            + '/Person/@cdr:ref'
                            AND cdrid.path  = '/InScopeProtocol'
                                            + '/ProtocolAdminInfo'
                                            + '/ProtocolLeadOrg'
                                            + '/LeadOrgPersonnel/@cdr:id'
                            AND idref.path  = '/InScopeProtocol'
                                            + '/ProtocolAdminInfo'
                                            + '/ProtocolLeadOrg'
                                            + '/MailAbstractTo'""",
                                            (self.getId(),), 120)
            rows = self.getCursor().fetchall()
            for row in rows:
                recipient = self.getRecipients().get(row[0])
                document  = self.getDocuments().get(row[2])
                if not recipient:
                    self.log("found recipient %s" % row[1])
                    addr = cdrmailer.Address(self.__getRecipAddress(row[5]))
                    recipient = cdrmailer.Recipient(row[0], row[1], addr)
                    self.getRecipients()[row[0]] = recipient
                if not document:
                    document = cdrmailer.Document(row[2], row[3], docType)
                    self.getDocuments()[row[2]] = document
                recipient.getDocs().append(document)
        except cdrdb.Error, info:
            raise "database error finding recipients: %s" % str(info[1][0])

    #------------------------------------------------------------------
    # Find a protocol lead organization personnel's mailing address.
    #------------------------------------------------------------------
    def __getRecipAddress(self, fragLink):
        try:
            docId, fragId = fragLink.split("#")
        except:
            raise "Invalid fragment link: %s" % fragLink
        parms = (("fragId", fragId),)
        filters = ["name:Person Address Fragment With Name"]
        rsp = cdr.filterDoc(self.getSession(), filters, docId, parm = parms)
        if type(rsp) == type("") or type(rsp) == type(u""):
            raise "Unable to find address for %s: %s" % (str(fragLink), rsp)
        return rsp[0]

    #------------------------------------------------------------------
    # Produce LaTeX source for all summaries to be mailed out.
    #------------------------------------------------------------------
    def __getDocuments(self):
        filters = [
            "name:Denormalization Filter (1/1): InScope Protocol",
            "name:Denormalization: sort OrganizationName for Postal Address"
        ]
        for docId in self.getDocuments().keys():
            self.log("generating LaTeX for CDR%010d" % docId)
            doc = self.getDocuments()[docId]
            doc.latex = self.makeLatex(doc, filters)

    #------------------------------------------------------------------
    # Generate a main cover page and add it to the print queue.
    #------------------------------------------------------------------
    def __makeCoverSheet(self):
        filename = "MainCoverPage.txt"
        f = open(filename, "w")
        f.write("\n\n%s\n\n" % self.getSubset())
        f.write("Job Number: %d\n\n" % self.getId())
        for country, zip, recip, doc in self.__index:
            title = doc.getTitle()
            if len(title) > 60: title = "%s ..." % title[:60]
            f.write("  Recipient: %010d\n" % recip.getId())
            f.write("       Name: %s\n" % recip.getName())
            f.write("    Country: %s\n" % country)
            f.write("Postal Code: %s\n" % zip)
            f.write("   Protocol: %010d\n" % doc.getId())
            f.write("      Title: %s\n\n" % title)
        f.write("\f")
        f.close()
        job = cdrmailer.PrintJob(filename, cdrmailer.PrintJob.PLAIN)
        self.addToQueue(job)

    #------------------------------------------------------------------
    # Walk through the index, generating protocol mailers.
    #------------------------------------------------------------------
    def __makeMailers(self):
        coverLetterParm     = self.getParm("CoverLetter")
        if not coverLetterParm:
            raise "CoverLetter parameter missing"
        coverLetterName     = 'd:/cdr/mailers/include/' + coverLetterParm[0]
        coverLetterTemplate = open(coverLetterName).read()
        for elem in self.__index:
            recip, doc = elem[2:]
            self.__makeMailer(recip, doc, coverLetterTemplate)

    #------------------------------------------------------------------
    # Create a protocol abstract mailer.
    #------------------------------------------------------------------
    def __makeMailer(self, recip, doc, template):

        # Add document to the repository for tracking replies to the mailer.
        mailerId = self.addMailerTrackingDoc(doc, recip, self.MAILER_TYPE)

        # Create a mailing label.
        latex     = self.createAddressLabelPage(recip.getAddress())
        basename  = 'MailingLabel-%d-%d' % (recip.getId(), doc.getId())
        jobType   = cdrmailer.PrintJob.COVERPAGE
        self.addToQueue(self.makePS(latex, 1, basename, jobType))

        # Create the cover letter.
        address   = self.formatAddress(recip.getAddress())
        docTitle  = doc.getTitle()
        pieces    = docTitle.split(';', 1)
        if len(pieces) != 2:
            raise "Protocol title missing component: %s" % docTitle
        protId    = pieces[0]
        protTitle = pieces[1]
        docId     = "%d (Tracking ID: %d)" % (doc.getId(), mailerId)

        # Real placeholders:
        latex     = template.replace('@@ADDRESS@@', address)
        latex     = latex.replace('@@PROTOCOLID@@', protId)
        latex     = latex.replace('@@PROTOCOLTITLE@@', protTitle)

        basename  = 'CoverLetter-%d-%d' % (recip.getId(), doc.getId())
        jobType   = cdrmailer.PrintJob.COVERPAGE
        self.addToQueue(self.makePS(latex, 1, basename, jobType))

        # Customize the LaTeX for this copy of the protocol.
        nPasses   = doc.latex.getLatexPassCount()
        latex     = doc.latex.getLatex()
        latex     = latex.replace('@@DOCID@@', str(doc.getId()))
        latex     = latex.replace('@@MailerDocID@@', str(mailerId))
        basename  = 'Mailer-%d-%d' % (recip.getId(), doc.getId())
        jobType   = cdrmailer.PrintJob.MAINDOC
        self.addToQueue(self.makePS(latex, nPasses, basename, jobType))

if __name__ == "__main__":
    sys.exit(ProtocolAbstractMailer(int(sys.argv[1])).run())


