#----------------------------------------------------------------------
#
# $Id: StatAndParticMailer.py,v 1.17 2006-07-13 13:18:10 bkline Exp $
#
# Master driver script for processing initial protocol status and
# participant verification mailers.
#
# $Log: not supported by cvs2svn $
# Revision 1.16  2006/06/08 13:57:33  bkline
# Added sources to emailer manifest.
#
# Revision 1.15  2005/03/02 15:46:06  bkline
# Removed temporary code to block Brussels mailers.
#
# Revision 1.14  2005/02/16 22:44:53  bkline
# Added PubSubset attribute to EmailerManifest document.
#
# Revision 1.13  2004/10/08 12:56:36  bkline
# Added temporary code to block some brussels mailers.
#
# Revision 1.12  2004/06/15 14:25:44  bkline
# Added tracker attribute to EmailerDocument element in EmailerManifest.
#
# Revision 1.11  2004/05/18 17:58:48  bkline
# Modified emailer manifest element names to match schema.
#
# Revision 1.10  2004/05/18 13:09:59  bkline
# Added support for electronic mailers.
#
# Revision 1.9  2003/08/21 19:43:06  bkline
# Added support for ProtocolOrg element in mailer tracking document for
# S&P mailers.
#
# Revision 1.8  2003/05/05 21:08:08  bkline
# Restricted mailers to lead orgs with (sort of) active statuses.
#
# Revision 1.7  2003/02/07 22:36:23  bkline
# Added call to UnicodeToLatex.convert() for title.
#
# Revision 1.6  2002/10/24 02:39:39  bkline
# Added code to handle worst-case combinations of protocol/recipient/org.
#
# Revision 1.5  2002/10/23 22:05:17  bkline
# Updated ancient code to prepare for final testing.
#
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

import cdr, cdrdb, cdrmailer, re, sys, UnicodeToLatex, time, xml.dom.minidom
import xml.sax.saxutils

#----------------------------------------------------------------------
# Object for a protocol update person.
#----------------------------------------------------------------------
class PUP:
    def __init__(self, docId, addrLink):
        self.docId    = docId
        self.addrLink = addrLink
        self.emailers = []

#----------------------------------------------------------------------
# Object for protocol's string ID, title, and status.
#----------------------------------------------------------------------
class ProtocolParms:
    def __init__(self, protXml):
        self.protId  = ""
        self.title   = ""
        self.status  = ""
        self.sources = []
        topElem = xml.dom.minidom.parseString(protXml).documentElement
        for node in topElem.childNodes:
            if node.nodeName == "ProtocolStatusAndParticipants":
                for child in node.childNodes:
                    if child.nodeName == "ProtocolID":
                        self.protId = cdr.getTextContent(child)
                    elif child.nodeName == "ProtocolTitle":
                        self.title = cdr.getTextContent(child)
                    elif child.nodeName == "CurrentProtocolStatus":
                        for grandchild in child.childNodes:
                            if grandchild.nodeName == "ProtocolStatusName":
                                self.status = cdr.getTextContent(grandchild)
            elif node.nodeName == "ProtocolSources":
                for child in node.childNodes:
                    if child.nodeName == "ProtocolSource":
                        for grandchild in child.childNodes:
                            if grandchild.nodeName == 'SourceName':
                                sourceName = cdr.getTextContent(grandchild)
                                if sourceName:
                                    self.sources.append(sourceName)

#----------------------------------------------------------------------
# Derived class for PDQ Editorial Board Member mailings.
#----------------------------------------------------------------------
class StatusAndParticipantMailer(cdrmailer.MailerJob):

    #------------------------------------------------------------------
    # Overrides method in base class for filling the print queue.
    #------------------------------------------------------------------
    def fillQueue(self):

        # Allow the user to restrict the job to one pup or lead org.
        self.__pupFilter = None
        self.__orgFilter = None
        pupId = self.getParm('PUP')
        orgId = self.getParm('LeadOrg')
        if pupId and pupId[0]:
            id = cdr.exNormalize(pupId[0])
            self.__pupFilter = id[1]
        if orgId and orgId[0]:
            id = cdr.exNormalize(orgId[0])
            self.__orgFilter = id[1]

        # Note which flavor(s) of mailers the user asked for.
        self.__paper = self.__electronic = False
        updateMode = self.getParm('UpdateModes')
        if not updateMode:
            raise "no update modes specified"
        updateMode = updateMode[0].upper()
        if '[MAIL]' in updateMode:
            self.__paper = True
        if '[WEB-BASED]' in updateMode:
            self.__electronic = True

        # Collect the mailer information into temporary tables.
        self.__getRecipients()

        # Create paper mailers if they were requested.
        if self.__paper:
            self.__makeIndex()
            self.__makeCoverSheet()
            self.__makeMailers()

    #------------------------------------------------------------------
    # Generate mailers for those who prefer the electronic method.
    #------------------------------------------------------------------
    def createEmailers(self):

        # Make sure the user asked for electronic mailers.
        if not self.__electronic:
            return
        
        # Create the separate emailer directory and move to it.
        self.initEmailers()

        # Build the set of electronic mailers.
        try:
            self.getCursor().execute("""\
         SELECT prot_id, prot_ver, org_id, pup_id, pup_link
           FROM #lead_orgs
          WHERE update_mode = 'Web-based'""")
            emailers        = {}
            pups            = {}
            rows            = self.getCursor().fetchall()
            self.log("%d rows retrieved for electronic mailers" % len(rows))
            for (docId, docVer, orgId, pupId, pupLink) in rows:
                if self.__pupFilter and pupId != self.__pupFilter:
                    continue
                if self.__orgFilter and orgId != self.__orgFilter:
                    continue
                key = (pupLink, docId, orgId)
                if key not in emailers:
                    recipient = pups.get(pupLink)
                    document  = self.getDocuments().get(docId)
                    if not recipient:
                        self.log("found recipient at address %s" % pupLink)
                        name          = self.__docTitles[pupId]
                        recipient     = cdrmailer.Recipient(pupId, name)
                        pups[pupLink] = recipient
                    if not document:
                        title    = self.__docTitles[docId]
                        document = cdrmailer.Document(docId, title,
                                                      "InScopeProtocol",
                                                      docVer)
                        self.getDocuments()[docId] = document
                    emailers[key] = emailer = cdrmailer.Emailer(document,
                                                                recipient,
                                                                orgId)
                    recipient.getEmailers().append(emailer)
        except cdrdb.Error, info:
            raise "database error building emailer list: %s" % str(info[1][0])
        self.log("%d update persons loaded" % len(pups))
        self.log("%d emailers to be created" % len(emailers))

        # Create the manifest document for the set of electronic mailers.
        manifest = open("manifest.xml", "w")
        manifest.write("""\
<?xml version='1.0' encoding='UTF-8'?>
<EmailerManifest JobTime='%s'
                 JobType='ProtocolStatusAndParticipant'
                 PubSubset='%s'
                 JobId='%d'>
""" % (self.getJobTime(), self.getSubset(), self.getId()))
        counter = 0

        # Generate the emailers for each recipient
        for addrLink in pups:
            pup = pups[addrLink]
            self.log("processing emailers for %s" % addrLink)
            try:
                docId, fragId = addrLink.split("#")
            except:
                raise "Invalid fragment link: %s" % addrLink
            id = addrLink
            pw = "%.3f" % time.time()
            parms = (("fragId", fragId),)
            filters = ['name:Person Address Fragment With Name (Emailer)']
            rsp = cdr.filterDoc('guest', filters, docId, parm = parms)
            if type(rsp) in (type(''), type(u'')):
                continue
                raise "Unable to find address for %s: %s" % (str(fragId), rsp)
            name = "%s-%s.xml" % (docId, fragId)
            email = self.extractEmailAddress(rsp[0])
            if not email:
                continue
                raise "No email address found for %s" % str(fragId)
            manifest.write("""\
 <EmailerRecipient>
  <EmailerRecipientID>%s</EmailerRecipientID>
  <EmailerRecipientPassword>%s</EmailerRecipientPassword>
  <EmailerFilename>%s</EmailerFilename>
  <EmailerAddress>%s</EmailerAddress>
  <EmailerDocuments>
""" % (id, pw, name, xml.sax.saxutils.escape(email)))
            file = open(name, "wb")
            file.write(rsp[0])
            file.close()
            filters = ['name:InScopeProtocol Status and Participant eMailer']
            for emailer in pup.getEmailers():
                leadOrgId = emailer.getLeadOrgId()
                document  = emailer.getDocument()
                parms = [('leadOrgId', 'CDR%010d' % leadOrgId)]
                rsp = cdr.filterDoc('guest', filters,
                                    document.getId(),
                                    docVer = document.getVersion(),
                                    parm = parms)
                if type(rsp) in (type(''), type(u'')):
                    raise ("Failure extracting information for lead org %d "
                           "from protocol %d: %s" % (leadOrgId,
                                                     document.getId(),
                                                     rsp))
                name = "%s-%s-%d-%d.xml" % (docId, fragId,
                                            document.getId(),
                                            leadOrgId)
                self.log("generating emailer %s" % name)
                file = open(name, "wb")
                file.write(rsp[0])
                file.close()
                protocolParms = ProtocolParms(rsp[0])
                trackerId = self.addMailerTrackingDoc(document, pup,
                                                      self.getSubset(),
                                                      protOrgId = leadOrgId,
                                                      email = email)
                manifest.write((u"""\
   <EmailerDocument id='CDR%010d' tracker='%d'>
    <EmailerFilename>%s</EmailerFilename>
    <EmailerAttrs>
     <EmailerAttr name='ProtID'>%s</EmailerAttr>
     <EmailerAttr name='Title'>%s</EmailerAttr>
     <EmailerAttr name='Status'>%s</EmailerAttr>
     <EmailerAttr name='Sources'>%s</EmailerAttr>
    </EmailerAttrs>
   </EmailerDocument>
""" % (document.getId(),
       trackerId,
       name,
       protocolParms.protId,
       xml.sax.saxutils.escape(protocolParms.title),
       protocolParms.status,
       u"|".join(protocolParms.sources))).encode('utf-8'))
                counter += 1
            manifest.write("""\
  </EmailerDocuments>
 </EmailerRecipient>
""")
        manifest.write("""\
</EmailerManifest>
""")
        manifest.close()
        self.log("%d emailers successfully generated" % counter)

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

        To top it all off, I just discovered that we can have the same
        receipient for the *same* protocol with more than one lead
        organization!  Aargh!

        But wait, it gets even worse!  Organizations can now have more
        than one OrganizationType element!

        2004-05-13: Rewritten to handle emailers.  Note that we need
        to execute the first part of this method even if paper mailers
        are not requested, because this is where we create the temporary
        database tables for all the job's mailers.
        """
        try:

            # Create a temporary table of the lead organizations and PUPs.
            self.getCursor().execute("""\
   CREATE TABLE #lead_orgs
       (prot_id INTEGER,
       prot_ver INTEGER,
         org_id INTEGER,
         pup_id INTEGER,
       pup_link VARCHAR(80),
    update_mode VARCHAR(80) NULL)""")
            self.commit()
            self.log("#lead_orgs table created")
            self.getCursor().execute("""\
    INSERT INTO #lead_orgs (prot_id, prot_ver, org_id, pup_id, pup_link,
                update_mode)
         SELECT m.doc_id, m.doc_version, o.int_val, p.int_val, p.value,
                u.value
           FROM pub_proc_doc m
           JOIN query_term o
             ON o.doc_id = m.doc_id
           JOIN query_term s
             ON s.doc_id = o.doc_id
            AND LEFT(s.node_loc, 8)  = LEFT(o.node_loc, 8)
           JOIN query_term p
             ON p.doc_id = o.doc_id
            AND LEFT(p.node_loc, 8)  = LEFT(o.node_loc, 8)
           JOIN query_term r
             ON r.doc_id = p.doc_id
            AND LEFT(r.node_loc, 12) = LEFT(p.node_loc, 12)
LEFT OUTER JOIN query_term u
             ON u.doc_id   = o.doc_id
            AND LEFT(u.node_loc, 8)  = LEFT(o.node_loc, 8)
            AND u.path     = '/InScopeProtocol/ProtocolAdminInfo'
                           + '/ProtocolLeadOrg/UpdateMode'
LEFT OUTER JOIN query_term t
             ON t.doc_id   = u.doc_id
            AND LEFT(t.node_loc, 12) = LEFT(u.node_loc, 12)
            AND t.path     = '/InScopeProtocol/ProtocolAdminInfo'
                           + '/ProtocolLeadOrg/UpdateMode/@MailerType'
            AND t.value    = 'Protocol_SandP'
          WHERE m.pub_proc = ?
            AND o.path     = '/InScopeProtocol/ProtocolAdminInfo'
                           + '/ProtocolLeadOrg/LeadOrganizationID/@cdr:ref'
            AND s.path     = '/InScopeProtocol/ProtocolAdminInfo'
                           + '/ProtocolLeadOrg/LeadOrgProtocolStatuses'
                           + '/CurrentOrgStatus/StatusName'
            AND s.value IN ('Active', 'Approved-not yet active',
                            'Temporarily closed')
            AND p.path     = '/InScopeProtocol/ProtocolAdminInfo'
                           + '/ProtocolLeadOrg/LeadOrgPersonnel'
                           + '/Person/@cdr:ref'
            AND r.path     = '/InScopeProtocol/ProtocolAdminInfo'
                           + '/ProtocolLeadOrg/LeadOrgPersonnel'
                           + '/PersonRole'
            AND r.value    = 'Update person'""", self.getId(), timeout = 300)
            self.commit()
            self.log("%d rows inserted into #lead_orgs table" %
                     self.getCursor().rowcount)

            # Fill in missing update mode values, using the PUPs' preferences.
            self.getCursor().execute("""\
    CREATE TABLE #pup_update_mode
         (pup_id INTEGER,
     update_mode VARCHAR(80))""")
            self.commit()
            self.log("#pup_update_mode table created")
            self.getCursor().execute("""\
    INSERT INTO #pup_update_mode (pup_id, update_mode)
SELECT DISTINCT u.doc_id, MAX(u.value) -- Avoid multiple values
           FROM #lead_orgs o
           JOIN query_term u
             ON u.doc_id = o.pup_id
           JOIN query_term t
             ON t.doc_id = u.doc_id
            AND LEFT(t.node_loc, 8) = LEFT(u.node_loc, 8)
          WHERE o.update_mode IS NULL
            AND u.path  = '/Person/PersonLocations/UpdateMode'
            AND t.path  = '/Person/PersonLocations/UpdateMode/@MailerType'
            AND t.value = 'Protocol_SandP'
       GROUP BY u.doc_id""", timeout = 300)
            self.commit()
            self.log("%d rows inserted into #pup_update_mode table" %
                     self.getCursor().rowcount)
            self.getCursor().execute("""\
         UPDATE #lead_orgs
            SET update_mode = p.update_mode
           FROM #lead_orgs o
           JOIN #pup_update_mode p
             ON p.pup_id = o.pup_id
          WHERE o.update_mode IS NULL
            AND p.update_mode IS NOT NULL""")
            self.commit()
            self.log("update_mode adjusted in %d rows" %
                     self.getCursor().rowcount)

            # Collect the document titles.
            self.__docTitles = {}
            self.getCursor().execute("""\
                SELECT DISTINCT id, title
                           FROM document
                          WHERE id IN (SELECT prot_id FROM #lead_orgs)
                             OR id IN (SELECT org_id FROM #lead_orgs)
                             OR id IN (SELECT pup_id FROM #lead_orgs)""",
                                     timeout = 300)
            for (id, title) in self.getCursor().fetchall():
                self.__docTitles[id] = title
            self.log("%d document titles loaded" % len(self.__docTitles))

            # Collect the org types (an org can have more than one).
            self.__orgTypes = {}
            self.getCursor().execute("""\
                SELECT DISTINCT t.doc_id, t.value
                           FROM query_term t
                           JOIN #lead_orgs o
                             ON o.org_id = t.doc_id
                          WHERE t.path = '/Organization/OrganizationType'""")
            for (id, orgType) in self.getCursor().fetchall():
                if id not in self.__orgTypes:
                    self.__orgTypes[id] = [orgType]
                else:
                    self.__orgTypes[id].append(orgType)
            self.log("org types for %d orgs loaded" % len(self.__orgTypes))
                                       
            # Fill up the queue for paper mailers (if the user asked for them).
            if not self.__paper:
                return
            self.getCursor().execute("""\
         SELECT prot_id, prot_ver, org_id, pup_id, pup_link
           FROM #lead_orgs
          WHERE update_mode = 'Mail'""")
            self.__combos   = {}
            orgs            = {}
            rows            = self.getCursor().fetchall()
            self.log("%d rows retrieved for paper mailers" % len(rows))
            for (docId, docVer, orgId, pupId, pupLink) in rows:
                if self.__pupFilter and pupId != self.__pupFilter:
                    continue
                if self.__orgFilter and orgId != self.__orgFilter:
                    continue
                key       = (pupLink, docId, orgId)
                recipient = self.getRecipients().get(pupLink)
                document  = self.getDocuments().get(docId)
                org       = orgs.get(orgId)
                if not recipient:
                    self.log("found recipient at address %s" % pupLink)
                    addr      = self.__getRecipAddress(pupLink)
                    name      = self.__docTitles[pupId]
                    recipient = cdrmailer.Recipient(pupId, name, addr)
                    self.getRecipients()[pupLink] = recipient
                if not document:
                    title    = self.__docTitles[docId]
                    document = cdrmailer.Document(docId, title,
                                                  "InScopeProtocol",
                                                  docVer)
                    self.getDocuments()[docId] = document
                if not org:
                    name        = self.__docTitles[orgId]
                    org         = cdrmailer.Org(orgId, name)
                    orgs[orgId] = org
                if not self.__combos.has_key(key):
                    self.__combos[key] = (recipient, document, org)
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
        coopType         = "NCI-supported clinical trials group"
        for key in self.__combos.keys():
            recip, doc, org = self.__combos[key]
            address         = recip.getAddress()
            country         = address.getCountry()
            postalCode      = address.getPostalCode()
            orgTypes        = self.__orgTypes[org.getId()]
            isCoop          = coopType in orgTypes and 1 or 0
            sortKey         = (country, postalCode, recip, isCoop, doc, org)
            self.__index.append(sortKey)
        self.__index.sort()

    #------------------------------------------------------------------
    # Generate a main cover page and add it to the print queue.
    #------------------------------------------------------------------
    def __makeCoverSheet(self):
        filename = "MainCoverPage.txt"
        f = open(filename, "w")
        f.write("\n\n%s\n\n" % self.getSubset())
        f.write("Job Number: %d\n\n" % self.getId())
        for country, zip, recip, isCoop, doc, org in self.__index:
            title = doc.getTitle()
            f.write("  Recipient: %d\n" % recip.getId())
            f.write("       Name: %s\n" % recip.getName())
            f.write("    Country: %s\n" % country)
            f.write("Postal Code: %s\n" % zip)
            f.write("   Protocol: %d\n" % doc.getId())
            f.write("      Title: %s\n" % UnicodeToLatex.convert(title[:60]))
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
        baseDir                = self.getMailerIncludePath() + "/"
        coverLetterParmCoop    = self.getParm("CoverLetterCoop")
        coverLetterParmNonCoop = self.getParm("CoverLetterNonCoop")
        coverLetterNameCoop    = baseDir + coverLetterParmCoop[0]
        coverLetterNameNonCoop = baseDir + coverLetterParmNonCoop[0]
        coverLetterCoopFile    = open(coverLetterNameCoop)
        coverLetterNonCoopFile = open(coverLetterNameNonCoop)
        coverLetterCoop        = coverLetterCoopFile.read()
        coverLetterNonCoop     = coverLetterNonCoopFile.read()
        coverLetterCoopFile.close()
        coverLetterNonCoopFile.close()

        # Gather the mailers into sets.  Everything going to the same
        # recipient address is collected, and then separated (if needed)
        # between the mailers for lead orgs which are cooperative groups
        # and for those which are not cooperative groups (because coops
        # and non-coops get different cover letters).  The recipFlagCombo
        # variable is a tuple representing a recipient address and the
        # flag for cooperative versus non-cooperative groups.  For each
        # of these recipient-flag combinations we collect all of the
        # combinations of protocol+lead org combinations which will be
        # sent to this recipient with the appropriate cover letter.
        # These sub-combinations (protocol doc + lead org) are represented
        # by the docOrgCombo(s) variables.
        lastRecipFlagCombo = None
        sets               = []
        for elem in self.__index:
            recip, isCoop, doc, org = elem[2:]
            recipFlagCombo = (recip, isCoop)
            docOrgCombo    = (doc, org)
            if lastRecipFlagCombo != recipFlagCombo:
                lastRecipFlagCombo = recipFlagCombo
                docOrgCombos       = []
                currentSet         = (recipFlagCombo, docOrgCombos)
                sets.append(currentSet)
            docOrgCombos.append(docOrgCombo)

        # Pump out each set of mailers.
        setNumber = 0
        for recipFlagCombo, docOrgCombos in sets:
            recip, isCoop = recipFlagCombo
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
            for doc, org in docOrgCombos:
                self.__makeMailer(recip, doc, org)
        

    #------------------------------------------------------------------
    # Create a protocol abstract mailer.
    #------------------------------------------------------------------
    def __makeMailer(self, recip, doc, org):

        # Add document to the repository for tracking replies to the mailer.
        mailerId = self.addMailerTrackingDoc(doc, recip, self.getSubset(),
                                             protOrgId = org.getId())

        # Create the LaTeX for the document.
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
        basename  = 'Mailer-%d-%d-%d' % (recip.getId(), docId, orgId)
        jobType   = cdrmailer.PrintJob.MAINDOC
        self.addToQueue(self.makePS(latex, nPasses, basename, jobType))

if __name__ == "__main__":
    sys.exit(StatusAndParticipantMailer(int(sys.argv[1])).run())
