#----------------------------------------------------------------------
#
# $Id: StatAndParticMailer.py,v 1.5 2002-10-23 22:05:17 bkline Exp $
#
# Master driver script for processing initial protocol status and
# participant verification mailers.
#
# $Log: not supported by cvs2svn $
# Revision 1.4  2002/10/23 11:44:08  bkline
# Removed obsolete code.
#
# Revision 1.3  2002/09/12 23:29:51  ameyer
# Removed common routine from individual mailers to cdrmailer.py.
# Added a few trace statements.
#
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
    # Overrides method in base class for filling the print queue.
    #------------------------------------------------------------------
    def fillQueue(self):
        self.__getRecipients()
        self.__makeIndex()
        self.__makeCoverSheet()
        self.__makeMailers()

    #------------------------------------------------------------------
    # Find lead organization personnel who should receive these mailers.
    #------------------------------------------------------------------
    def __getRecipients(self):
        """
        Trickier than most mailers, because not only can each document
        get mailed to more than one recipient (not unusual in itself), and
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
        otPath   = "/Organization/OrganizationType"
        try:
            self.getCursor().execute("""\
                SELECT DISTINCT person.id,
                                person.title,
                                org.id,
                                org.title,
                                protocol.id,
                                protocol.title,
                                doc_version.num,
                                person_link.value,
                                org_type.value
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
                           JOIN query_term org_type
                             ON org_type.doc_id = org.id
                          WHERE pub_proc_doc.pub_proc = ?
                            AND lead_org.path         = '%s'
                            AND person_link.path      = '%s'
                            AND person_role.path      = '%s'
                            AND org_type.path         = '%s'
                            AND person_role.value     = 'Update person'
                            AND NOT EXISTS (SELECT *
                                              FROM query_term contact_mode
                                             WHERE contact_mode.path = '%s'
                                               AND contact_mode.doc_id =
                                                   lead_org.int_val)""" %
                                (orgPath, pupPath, rolePath, otPath, modePath),
                                (self.getId(),))
            rows = self.getCursor().fetchall()
            self.__orgMap = {}
            orgs          = {}
            for row in rows:
                (recipId, recipName, orgId, orgName, docId, docTitle,
                 docVersion, addrLink, orgType) = row
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
                    org = cdrmailer.Org(orgId, orgName, orgType)
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
        if type(rsp) in (type(""), type(u"")):
            raise "Unable to find address for %s: %s" % (str(fragLink), rsp)
        return cdrmailer.Address(rsp[0])

    #------------------------------------------------------------------
    # Generate an index of the mailers in order of postal codes.
    # Using new criterion for determining whether an organization is
    # a cooperative group supplied by Lakshmi in email dated 21Oct2002.
    #------------------------------------------------------------------
    def __makeIndex(self):
        self.__index     = []
        recipients       = self.getRecipients()
        for recipKey in recipients.keys():
            recip        = recipients[recipKey]
            address      = recip.getAddress()
            country      = address.getCountry()
            postalCode   = address.getPostalCode()
            for doc in recip.getDocs():
                org      = self.__orgMap[recip, doc]
                coopName = "NCI-supported clinical trials group"
                isCoop   = org.getType() == coopName and 1 or 0
                key      = (country, postalCode, recip, isCoop, doc)
                self.__index.append(key)
        self.__index.sort()

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
            org = self.__orgMap[recip, doc]
            f.write("  Recipient: %d\n" % recip.getId())
            f.write("       Name: %s\n" % recip.getName())
            f.write("    Country: %s\n" % country)
            f.write("Postal Code: %s\n" % zip)
            f.write("   Protocol: %d\n" % doc.getId())
            f.write("      Title: %s\n" % title[:60])
            f.write("     Org ID: %d\n" % org.getId())
            f.write("   Org Name: %s\n\n" % org.getName())
        f.write("\f")
        f.close()
        job = cdrmailer.PrintJob(filename, cdrmailer.PrintJob.PLAIN)
        self.addToQueue(job)

    #------------------------------------------------------------------
    # Walk through the index, generating protocol mailers.
    #------------------------------------------------------------------
    def __makeMailers(self):

        # Get the templates for the cover letters.        
        baseDir                = self.getMailerIncludePath()
        coverLetterParmCoop    = self.getParm("CoverLetterCoop")
        coverLetterParmNonCoop = self.getParm("CoverLetterNonCoop")
        coverLetterNameCoop    = baseDir + coverLetterParmCoop
        coverLetterNameNonCoop = baseDir + coverLetterParmNonCoop
        coverLetterCoopFile    = open(coverLetterNameCoop)
        coverLetterNonCoopFile = open(coverLetterNameNonCoop)
        coverLetterCoop        = coverLetterCoopFile.read()
        coverLetterNonCoop     = coverLetterNonCoopFile.read()
        coverLetterCoopFile.close()
        coverLetterNonCoopFile.close()

        # Gather the mailers into sets.
        lastCombo              = None
        sets                   = []
        for elem in self.__index:
            recip, isCoop, doc  = elem[2:]
            thisCombo           = (recip, isCoop)
            if thisCombo != lastCombo:
                lastCombo  = thisCombo
                docs       = []
                currentSet = (thisCombo, docs)
                sets.append(currentSet)
            docs.append(doc)
        setNumber = 0

        # Pump out each set of mailers.
        for combo, docs in sets:
            recip, isCoop = combo
            setNumber += 1

            # Create a mailing label.
            address   = recip.getAddress()
            latex     = self.createAddressLabelPage(address)
            basename  = 'MailingLabel-%d' % setNumber
            jobType   = cdrmailer.PrintJob.COVERPAGE
            self.addToQueue(self.makePS(latex, 1, basename, jobType))

            # Create a cover letter.
            template  = isCoop and coverLetterCoop or coverLetterNonCoop
            address   = self.formatAddress(address)
            latex     = template.replace('@@PUPADDRESS@@', address)
            basename  = 'CoverLetter-%d' % setNumber
            jobType   = cdrmailer.PrintJob.COVERPAGE
            self.addToQueue(self.makePS(latex, 1, basename, jobType))

            # Append each mailer to the set.
            for doc in docs:
                self.__makeMailer(recip, doc)
        

    #------------------------------------------------------------------
    # Create a protocol abstract mailer.
    #------------------------------------------------------------------
    def __makeMailer(self, recip, doc):

        # Add document to the repository for tracking replies to the mailer.
        mailerId = self.addMailerTrackingDoc(doc, recip, self.getSubset())

        # Create the LaTeX for the document.
        org       = self.__orgMap[recip, doc]
        orgId     = org.getId()
        docId     = doc.getId()
        self.log("generating LaTeX for CDR%010d" % docId)
        self.log("lead Organization CDR%010d" % orgId)
        filters   = ['name:InScopeProtocol Status and Participant Mailer']
        parms     = [('leadOrgId', 'CDR%010d' % orgId)]
        doc.latex = self.makeLatex(doc, filters, "StatusCheck", parms)

        # Customize the LaTeX for this copy of the protocol.
        nPasses   = doc.latex.getLatexPassCount()
        latex     = doc.latex.getLatex()
        latex     = latex.replace('@@MAILERID@@', str(mailerId))
        latex     = latex.replace('@@DOCID@@', str(docId))
        basename  = 'Mailer-%d-%d' % (recip.getId(), docId)
        jobType   = cdrmailer.PrintJob.MAINDOC
        self.addToQueue(self.makePS(latex, nPasses, basename, jobType))

if __name__ == "__main__":
    sys.exit(InitialStatusAndParticipantMailer(int(sys.argv[1])).run())
