#----------------------------------------------------------------------
#
# $Id: ElectronicMailers.py,v 1.2 2004-05-18 13:06:40 bkline Exp $
#
# Script to generate electronic S&P mailers.
#
# $Log: not supported by cvs2svn $
# Revision 1.1  2004/04/27 20:00:22  bkline
# Script to generate electronic S&P mailers.
#
#----------------------------------------------------------------------
import cdr, cdrdb, os, sys, time, xml.dom.minidom

def show(what):
    sys.stderr.write("%s\n" % what)

#------------------------------------------------------------------
# Generate a document for tracking a mailer.
#------------------------------------------------------------------
def addMailerTrackingDoc(jobId, docId, recipId, orgId,
                         mailerType, session, email):

    docId   = "CDR%010d" % docId
    recipId = "CDR%010d" % recipId
    orgId   = cdr.normalize(orgId)
    xml     = u"""\
<CdrDoc Type="Mailer">
 <CdrDocCtl>
  <DocTitle>Mailer for document %s sent to %s</DocTitle>
 </CdrDocCtl>
 <CdrDocXml><![CDATA[
  <Mailer xmlns:cdr="cips.nci.nih.gov/cdr">
   <Type>%s</Type>
   <JobId>%d</JobId>
   <Recipient cdr:ref="%s"/>
   <ProtocolOrg cdr:ref='%s'/>
   <MailerAddress>
    <Email>%s</Email>
   </MailerAddress>
   <Document cdr:ref="%s"/>
   <Sent>%s</Sent>
   <Deadline>%s</Deadline>
  </Mailer>]]>
 </CdrDocXml>
</CdrDoc>
""" % (docId, recipId, mailerType, jobId, recipId, recipName, protOrg,
       address, docId, jobDate, deadline)
    rsp   = cdr.addDoc(session, doc = xml.encode('utf-8'),
                       checkIn = "Y", ver = "Y", val = 'Y')
    match = self.__ERR_PATTERN.search(rsp)
    if match:
        err = match.group(1)
        raise StandardError (
            "failure adding tracking document for %s: %s" % (docId, err))
    self.__nMailers += 1
    digits = re.sub("[^\d]", "", rsp)
    return int(digits)

def dumpTable(name, order):
    cursor.execute("SELECT * FROM %s ORDER BY %s" % (name, order))
    print "*** TABLE %s ***" % name
    for row in cursor.fetchall():
        print row

def extractEmailAddress(doc):
    dom = xml.dom.minidom.parseString(doc)
    for node in dom.documentElement.childNodes:
        if node.nodeName == "ContactDetail":
            for child in node.childNodes:
                if child.nodeName == "Email":
                    return cdr.getTextContent(child)

class PUP:
    def __init__(self, docId, addrLink):
        self.docId    = docId
        self.addrLink = addrLink
        self.mailers  = []

class Mailer:
    def __init__(self, leadOrg, protocol, pup):
        self.leadOrg  = leadOrg
        self.protocol = protocol
        self.pup      = pup

class LeadOrg:
    def __init__(self, docId):
        self.docId    = docId

class Protocol:
    def __init__(self, docId, docVersion):
        self.docId      = docId
        self.docVersion = docVersion

class ProtocolParms:
    def __init__(self, protXml):
        self.protId = ""
        self.title  = ""
        self.status = ""
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

mailers = {}
pups    = {}
orgs    = {}
prots   = {}
conn    = cdrdb.connect('CdrGuest')
cursor  = conn.cursor()
initial = len(sys.argv) > 1 and sys.argv[1] == "--initial"
cursor.execute("CREATE TABLE #mailer_prots (id INT, ver INT)")
conn.commit()
show("#mailer_prots table created ...")
if initial:
    cursor.execute("""\
    INSERT INTO #mailer_prots (id, ver)
SELECT DISTINCT protocol.id, MAX(doc_version.num)
           FROM document protocol
           JOIN doc_version
             ON doc_version.id = protocol.id
           JOIN query_term prot_status
             ON prot_status.doc_id = protocol.id
           JOIN ready_for_review
             ON ready_for_review.doc_id = protocol.id
          WHERE prot_status.value IN ('Active',
                                      'Approved-Not Yet Active',
                                      'Temporarily closed')
            AND prot_status.path = '/InScopeProtocol/ProtocolAdminInfo'
                                 + '/CurrentProtocolStatus'
            AND doc_version.val_status = 'V'
            AND protocol.active_status = 'A'

            -- Don't send the initial mailer twice.
            AND NOT EXISTS (SELECT pd.doc_id
                              FROM pub_proc p
                              JOIN pub_proc_doc pd
                                ON p.id = pd.pub_proc
                             WHERE pd.doc_id = protocol.id
                               AND p.pub_subset IN ('Protocol-Quarterly status'
                                                  + '/participant check', 
                                                    'Protocol-Initial status'
                                                  + '/participant check')
                               AND (p.status = 'Success'
                                OR  p.completed IS NULL)
                               ABD (pd.failure IS NULL
                                OR  pd.failure = 'N')
       GROUP BY protocol.id""")
else:
    cursor.execute("""\
    INSERT INTO #mailer_prots (id, ver)
SELECT DISTINCT protocol.id, MAX(doc_version.num)
           FROM document protocol
           JOIN doc_version
             ON doc_version.id = protocol.id
           JOIN query_term prot_status
             ON prot_status.doc_id = protocol.id
          WHERE prot_status.value IN ('Active',
                                      'Approved-Not Yet Active',
                                      'Temporarily closed')
            AND prot_status.path = '/InScopeProtocol/ProtocolAdminInfo'
                                 + '/CurrentProtocolStatus'
            AND doc_version.publishable = 'Y'
            AND protocol.active_status  = 'A'
       GROUP BY protocol.id""")
conn.commit()
show("%d rows inserted ..." % cursor.rowcount)
dumpTable("#mailer_prots", "id, ver")
cursor.execute("""\
   CREATE TABLE #lead_orgs
       (prot_id INTEGER,
       prot_ver INTEGER,
         org_id INTEGER,
         pup_id INTEGER,
       pup_link VARCHAR(80),
    update_mode VARCHAR(80))""")
conn.commit()
show("#lead_orgs table created ...")
cursor.execute("""\
    INSERT INTO #lead_orgs (prot_id, prot_ver, org_id, pup_id, pup_link,
                            update_mode)
         SELECT m.id, m.ver, o.int_val, p.int_val, p.value, u.value
           FROM #mailer_prots m
           JOIN query_term o
             ON o.doc_id = m.id
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
             ON u.doc_id = o.doc_id
            AND LEFT(u.node_loc, 8)  = LEFT(o.node_loc, 8)
            AND u.path  = '/InScopeProtocol/ProtocolAdminInfo'
                        + '/ProtocolLeadOrg/UpdateMode'
         -- AND u.value = 'Web-based'
LEFT OUTER JOIN query_term t
             ON t.doc_id = u.doc_id
            AND LEFT(t.node_loc, 12) = LEFT(u.node_loc, 12)
            AND t.path  = '/InScopeProtocol/ProtocolAdminInfo'
                        + '/ProtocolLeadOrg/UpdateMode/@MailerType'
            AND t.value = 'Protocol_SandP'
          WHERE o.path  = '/InScopeProtocol/ProtocolAdminInfo'
                        + '/ProtocolLeadOrg/LeadOrganizationID/@cdr:ref'
            AND s.path  = '/InScopeProtocol/ProtocolAdminInfo'
                        + '/ProtocolLeadOrg/LeadOrgProtocolStatuses'
                        + '/CurrentOrgStatus/StatusName'
            AND s.value IN ('Active', 'Approved-not yet active',
                            'Temporarily closed')
            AND p.path  = '/InScopeProtocol/ProtocolAdminInfo'
                        + '/ProtocolLeadOrg/LeadOrgPersonnel'
                        + '/Person/@cdr:ref'
            AND r.path  = '/InScopeProtocol/ProtocolAdminInfo'
                        + '/ProtocolLeadOrg/LeadOrgPersonnel'
                        + '/PersonRole'
            AND r.value = 'Update person'""", timeout = 300)
conn.commit()
show("%d rows inserted ..." % cursor.rowcount)
dumpTable("#lead_orgs", "prot_id, prot_ver, org_id, pup_id")
cursor.execute("""\
    CREATE TABLE #pup_update_mode
         (pup_id INTEGER,
     update_mode VARCHAR(80))""")
conn.commit()
show("#pup_update_mode table created ...")
cursor.execute("""\
    INSERT INTO #pup_update_mode (pup_id, update_mode)
SELECT DISTINCT u.doc_id, u.value
           FROM #lead_orgs o
           JOIN query_term u
             ON u.doc_id = o.pup_id
           JOIN query_term t
             ON t.doc_id = u.doc_id
            AND LEFT(t.node_loc, 8) = LEFT(u.node_loc, 8)
          WHERE o.update_mode IS NULL
            AND u.path  = '/Person/PersonLocations/UpdateMode'
            AND t.path  = '/Person/PersonLocations/UpdateMode/@MailerType'
            AND t.value = 'Protocol_SandP'""")
conn.commit()
show("%d rows inserted ..." % cursor.rowcount)
dumpTable("#pup_update_mode", "pup_id")
cursor.execute("""\
    CREATE TABLE #mailer_job
        (prot_id INTEGER,
        prot_ver INTEGER,
          org_id INTEGER,
          pup_id INTEGER,
        pup_link VARCHAR(80))""")
conn.commit()
show("#mailer_job table created ...")
cursor.execute("""\
    INSERT INTO #mailer_job
    SELECT prot_id, prot_ver, org_id, pup_id, pup_link
      FROM #lead_orgs
     WHERE update_mode = 'Web-based'
        OR update_mode IS NULL
       AND pup_id IN (SELECT pup_id
                        FROM #pup_update_mode
                       WHERE update_mode = 'Web-based')""")
conn.commit()
show("%d rows inserted ..." % cursor.rowcount)
dumpTable("#mailer_job", "prot_id, org_id, pup_id")
cursor.execute("SELECT * FROM #mailer_job")
rows = cursor.fetchall()
show("%d rows fetched ..." % len(rows))
for (docId, docVersion, orgId, recipId, addrLink) in rows:
    key      = (addrLink, docId, orgId)
    recip    = pups.get(addrLink)
    protocol = prots.get(docId)
    org      = orgs.get(orgId)
    mailer   = mailers.get(key)
    if not recip:
        pups[addrLink] = recip = PUP(recipId, addrLink)
    if not org:
        orgs[orgId] = org = LeadOrg(orgId)
    if not protocol:
        prots[docId] = protocol = Protocol(docId, docVersion)
    if not mailer:
        mailers[key] = mailer = Mailer(org, protocol, recip)
        recip.mailers.append(mailer)
show("%d pups loaded ..." % len(pups))
show("%d orgs loaded ..." % len(orgs))
show("%d prots loaded ..." % len(prots))
show("%d mailers loaded ..." % len(mailers))
jobTime = time.strftime("%Y%m%d%H%M%S")
dirName = time.strftime("Emailer-%s" % jobTime)
os.mkdir(dirName)
show("creating job %s" % dirName)
manifest = open("%s/manifest.xml" % dirName, "w")
manifest.write("""\
<?xml version="1.0" encoding="UTF-8"?>
<Manifest jobTime='%s'>
""" % jobTime)

for key in pups:
    pup = pups[key]
    print "processing mailers for %s" % pup.addrLink
    try:
        docId, fragId = pup.addrLink.split("#")
    except:
        raise "Invalid fragment link: %s" % pup.addrLink
    id = pup.addrLink
    pw = "%.3f" % time.time()
    parms = (("fragId", fragId),)
    filters = ["name:Person Address Fragment With Name (Emailer)"]
    rsp = cdr.filterDoc('guest', filters, docId, parm = parms)
    if type(rsp) in (type(""), type(u"")):
        raise "Unable to find address for %s: %s" % (str(fragId), rsp)
    name = "%s-%s.xml" % (docId, fragId)
    email = extractEmailAddress(rsp[0])
    if not email:
        show("no email address for %s" % pup.addrLink)
    else:
        show("email for %s = %s" % (pup.addrLink, email))
    manifest.write("""\
 <UpdatePerson>
  <ID>%s</ID>
  <Password>%s</Password>
  <DocFile>%s</DocFile>
  <Documents>
""" % (id, pw, name))
    file = open("%s/%s" % (dirName, name), "wb")
    file.write(rsp[0])
    file.close()
    filters = ['name:InScopeProtocol Status and Participant eMailer']
    for mailer in pup.mailers:
        print "\tprotocol %d; lead org %d" % (mailer.protocol.docId,
                                              mailer.leadOrg.docId)
        parms = [('leadOrgId', 'CDR%010d' % mailer.leadOrg.docId)]
        rsp = cdr.filterDoc('guest', filters, mailer.protocol.docId,
                            docVer = mailer.protocol.docVersion,
                            parm = parms)
        if type(rsp) in (type(""), type(u"")):
            raise ("Unable to extract information for lead org %d "
                   "from protocol %d: %s" % (mailer.leadOrg.docId,
                                             mailer.protocol.docId,
                                             rsp))
        name = "%s-%s-%d-%d.xml" % (docId, fragId,
                                    mailer.protocol.docId,
                                    mailer.leadOrg.docId)
        file = open("%s/%s" % (dirName, name), "wb")
        file.write(rsp[0])
        file.close()
        protocolParms = ProtocolParms(rsp[0])
        manifest.write((u"""\
   <Document id='CDR%010d'>
    <DocFile>%s</DocFile>
    <Attrs>
     <Attr name='ProtID'>%s</Attr>
     <Attr name='Title'>%s</Attr>
     <Attr name='Status'>%s</Attr>
    </Attrs>
   </Document>
""" % (mailer.protocol.docId,
       name,
       protocolParms.protId,
       protocolParms.title,
       protocolParms.status)).encode("utf-8"))
    manifest.write("""\
  </Documents>
 </UpdatePerson>
""")
manifest.write("""\
</Manifest>
""")
manifest.close()
