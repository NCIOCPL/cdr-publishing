#----------------------------------------------------------------------
#
# $Id: StatAndParticMailer.py,v 1.3 2002-09-12 23:29:51 ameyer Exp $
#
# Master driver script for processing initial protocol status and
# participant verification mailers.
#
# $Log: not supported by cvs2svn $
# Revision 1.2  2002/01/23 17:14:58  bkline
# Modifications to accomodate changed requirements.
#
# Revision 1.1  2001/12/04 13:38:05  bkline
# Initial version
#
#----------------------------------------------------------------------

import cdr, cdrdb, cdrmailer, re, sys

#----------------------------------------------------------------------
# Derived class for PDQ Editorial Board Member mailings.
#----------------------------------------------------------------------
class InitialStatusAndParticipantMailer(cdrmailer.MailerJob):

    #------------------------------------------------------------------
    # Specific constant values for subclass.
    #------------------------------------------------------------------
    MAILER_TYPE = "Protocol Status and Participant"

    #------------------------------------------------------------------
    # Overrides method in base class for filling the print queue.
    #------------------------------------------------------------------
    def fillQueue(self):
        self.__getRecipients()
        #self.__getDocuments()
        self.__makeIndex()
        self.__makeCoverSheet()
        self.__makeMailers()

    #------------------------------------------------------------------
    # Find lead organization personnel who should receive these mailers.
    #------------------------------------------------------------------
    def __getRecipients(self):
        """
        Trickier than most mailers, because not only can each document
        get mailed to more than one recipient (which is standard), and
        different documents for the same recipient can go to different
        addresses (this also happens with some other mailers) but different
        documents for the same recipient at the same address can have a
        different organization associated with the recipient.  So we keep
        track of which Org objects we have already constructed (with the
        orgs dictionary) and we have a map of each address+document combo
        (self.__orgMap) which remembers which organization is used.

        As if this complication weren't enough, we also have to filter
        each package separately, because the content for a given protocol
        varies based on the lead org whose PUP is getting the mailer!
        This means that we can't take advantage of our usual optimization
        of filtering each document only once.
        """
        docType  = "InScopeProtocol"
        orgPath  = "/InScopeProtocol/ProtocolAdminInfo/ProtocolLeadOrg"\
                   "/LeadOrganizationID/@cdr:ref"
        pupPath  = "/InScopeProtocol/ProtocolAdminInfo/ProtocolLeadOrg"\
                   "/LeadOrgPersonnel/Person/@cdr:ref"
        rolePath = "/InScopeProtocol/ProtocolAdminInfo/ProtocolLeadOrg"\
                   "/LeadOrgPersonnel/PersonRole"
        modePath = "/Organization/OrganizationDetails"\
                   "/PreferredProtocolContactMode"
        try:
            self.getCursor().execute("""\
                SELECT DISTINCT person.id,
                                person.title,
                                org.id,
                                org.title,
                                protocol.id,
                                protocol.title,
                                doc_version.num,
                                person_link.value
                           FROM document person
                           JOIN query_term person_link
                             ON person_link.int_val = person.id
                           JOIN query_term person_role
                             ON person_role.doc_id = person_link.doc_id
                            AND LEFT(person_role.node_loc, 12) =
                                LEFT(person_link.node_loc, 12)
                           JOIN query_term lead_org
                             ON lead_org.doc_id = person_link.doc_id
                            AND LEFT(lead_org.node_loc, 8) =
                                LEFT(person_link.node_loc, 8)
                           JOIN document org
                             ON org.id = lead_org.int_val
                           JOIN document protocol
                             ON protocol.id = lead_org.doc_id
                           JOIN doc_version
                             ON doc_version.id = protocol.id
                           JOIN pub_proc_doc
                             ON pub_proc_doc.doc_version = doc_version.num
                            AND pub_proc_doc.doc_id      = doc_version.id
                          WHERE pub_proc_doc.pub_proc = ?
                            AND lead_org.path         = '%s'
                            AND person_link.path      = '%s'
                            AND person_role.path      = '%s'
                            AND person_role.value     = 'Update person'
                            AND NOT EXISTS (SELECT *
                                              FROM query_term contact_mode
                                             WHERE contact_mode.path = '%s'
                                               AND contact_mode.doc_id =
                                                   lead_org.int_val)""" %
                                (orgPath, pupPath, rolePath, modePath),
                                (self.getId(),))
            rows = self.getCursor().fetchall()
            self.__orgMap = {}
            orgs          = {}
            for row in rows:
                (recipId, recipName, orgId, orgName, docId, docTitle,
                 docVersion, addrLink) = row
                #print recipId, orgId, docId, docVersion, addrLink
                recipient = self.getRecipients().get(addrLink)
                document  = self.getDocuments().get(docId)
                org       = orgs.get(orgId)
                if not recipient:
                    self.log("found recipient at address %s" % addrLink)
                    addr = self.__getRecipAddress(addrLink)
                    recipient = cdrmailer.Recipient(recipId, recipName, addr)
                    self.getRecipients()[addrLink] = recipient
                if not document:
                    document = cdrmailer.Document(docId, docTitle, docType)
                    self.getDocuments()[docId] = document
                if not org:
                    org = cdrmailer.Org(orgId, orgName)
                    orgs[orgId] = org
                recipient.getDocs().append(document)
                self.__orgMap[(recipient, document)] = org
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
        #print "address=%s" % rsp[0]
        return cdrmailer.Address(rsp[0])

    #------------------------------------------------------------------
    # Produce LaTeX source for all summaries to be mailed out.
    #------------------------------------------------------------------
    def __getDocuments(self):
        filters = ['name:InScopeProtocol Status and Participant Mailer']
        for docId in self.getDocuments().keys():
            self.log("generating LaTeX for CDR%010d" % docId)
            doc = self.getDocuments()[docId]
            doc.latex = self.makeLatex(doc, filters, "SP")

    #------------------------------------------------------------------
    # Generate an index of the mailers in order of postal codes.
    #------------------------------------------------------------------
    def __makeIndex(self):
        self.__index   = []
        recipients     = self.getRecipients()
        for recipKey in recipients.keys():
            recip      = recipients[recipKey]
            address    = recip.getAddress()
            country    = address.getCountry()
            postalCode = address.getPostalCode()
            for doc in recip.getDocs():
                self.__index.append((country, postalCode, recip, doc))
                #print "__makeIndex(): country=%s; postalCode=%s" % (country,
                #       postalCode)
        self.__index.sort()

    #------------------------------------------------------------------
    # Generate a main cover page and add it to the print queue.
    #------------------------------------------------------------------
    def __makeCoverSheet(self):
        filename = "MainCoverPage.txt"
        f = open(filename, "w")
        f.write("\n\nInitial Protocol Status and Participant Mailers\n\n")
        f.write("Job Number: %d\n\n" % self.getId())
        for country, zip, recip, doc in self.__index:
            org = self.__orgMap[recip, doc]
            f.write("  Recipient: %010d\n" % recip.getId())
            f.write("       Name: %s\n" % recip.getName())
            f.write("    Country: %s\n" % country)
            f.write("Postal Code: %s\n" % zip)
            f.write("   Protocol: %010d\n" % doc.getId())
            f.write("      Title: %s\n" % doc.getTitle())
            f.write("     Org ID: %010d\n" % org.getId())
            f.write("   Org Name: %s\n\n" % org.getName())
        f.close()
        job = cdrmailer.PrintJob(filename, cdrmailer.PrintJob.COVERPAGE)
        self.addToQueue(job)

    #------------------------------------------------------------------
    # Walk through the index, generating protocol mailers.
    #------------------------------------------------------------------
    def __makeMailers(self):
        coverLetterName     = "../ProtInitStatParticCoverLetter.tex"
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

        # Create a cover letter.
        org       = self.__orgMap[recip, doc]
        address   = self.formatAddress(recip.getAddress(), org)
        recipName = recip.getAddress().getAddressee()
        salutation= "Dear %s:" % recipName
        docId     = "%d (Tracking ID: %d)" % (doc.getId(), mailerId)
        latex     = template.replace('@@ADDRESS@@', address)
        latex     = latex.replace('@@SALUTATION@@', salutation)
        latex     = latex.replace('@@DOCID@@', docId)
        basename  = 'CoverLetter-%d-%d' % (recip.getId(), doc.getId())
        jobType   = cdrmailer.PrintJob.COVERPAGE
        self.addToQueue(self.makePS(latex, 1, basename, jobType))

        # Create the LaTeX for the document.
        self.log("generating LaTeX for CDR%010d" % doc.getId())
        self.log("lead Organization CDR%010d" % org.getId())
        filters   = ['name:InScopeProtocol Status and Participant Mailer']
        parms     = [('leadOrgId', 'CDR%010d' % org.getId())]
        doc.latex = self.makeLatex(doc, filters, "SP", parms)

        # Customize the LaTeX for this copy of the protocol.
        nPasses   = doc.latex.getLatexPassCount()
        latex     = doc.latex.getLatex()
        latex     = latex.replace('@@Recipient@@', recipName)
        latex     = latex.replace('@@MailerDocId@@', str(mailerId))
        basename  = 'Mailer-%d-%d' % (recip.getId(), doc.getId())
        jobType   = cdrmailer.PrintJob.MAINDOC
        self.addToQueue(self.makePS(latex, nPasses, basename, jobType))

if __name__ == "__main__":
    sys.exit(InitialStatusAndParticipantMailer(int(sys.argv[1])).run())
