#----------------------------------------------------------------------
#
# $Id: ElectronicMailers.py,v 1.1 2004-04-27 20:00:22 bkline Exp $
#
# Script to generate electronic S&P mailers.
#
# $Log: not supported by cvs2svn $
#----------------------------------------------------------------------
import cdr, cdrdb, os, time, xml.dom.minidom

class PUP:
    def __init__(self, docId, name, addrLink):
        self.docId    = docId
        self.name     = name
        self.addrLink = addrLink
        self.mailers  = []

class Mailer:
    def __init__(self, leadOrg, protocol, pup):
        self.leadOrg  = leadOrg
        self.protocol = protocol
        self.pup      = pup

class LeadOrg:
    def __init__(self, docId, orgName):
        self.docId    = docId
        self.orgName  = orgName
        self.orgTypes = []

class Protocol:
    def __init__(self, docId, docVersion, title):
        self.docId      = docId
        self.docVersion = docVersion
        self.title      = title

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
conn = cdrdb.connect('CdrGuest')
cursor = conn.cursor()
cursor.execute("CREATE TABLE #mailer_prots (id INT, ver INT)")
conn.commit()
cursor.execute("""\
    INSERT INTO #mailer_prots (id, ver)
SELECT DISTINCT protocol.id, MAX(doc_version.num)
           FROM document protocol
           JOIN doc_version
             ON doc_version.id = protocol.id
           JOIN ready_for_review
             ON ready_for_review.doc_id = protocol.id
           JOIN query_term prot_status
             ON prot_status.doc_id = protocol.id
           JOIN query_term lead_org
             ON lead_org.doc_id = protocol.id
          WHERE prot_status.value IN ('Active',
                                      'Approved-Not Yet Active')
            AND prot_status.path = '/InScopeProtocol/ProtocolAdminInfo'
                                 + '/CurrentProtocolStatus'
            AND lead_org.path    = '/InScopeProtocol/ProtocolAdminInfo'
                                 + '/ProtocolLeadOrg/LeadOrganizationID'
                                 + '/@cdr:ref'
            AND doc_version.val_status = 'V'
            AND protocol.active_status = 'A'

            -- Which ones want electronic mailers?
            AND EXISTS (SELECT *
                          FROM query_term contact_mode
                         WHERE contact_mode.doc_id = lead_org.int_val
                           AND contact_mode.path = '/Organization'
                                                 + '/OrganizationDetails'
                                                 + '/PreferredProtocol'
                                                 + 'ContactMode')

            -- Don't send mailers for Brussels protocols.
            AND NOT EXISTS (SELECT *
                              FROM query_term src
                             WHERE src.value = 'NCI Liaison Office-Brussels'
                               AND src.path  = '/InScopeProtocol'
                                             + '/ProtocolSources'
                                             + '/ProtocolSource/SourceName'
                               AND src.doc_id = protocol.id)

            -- Don't send the initial mailer twice.
            AND NOT EXISTS (SELECT *
                              FROM pub_proc p
                              JOIN pub_proc_doc pd
                                ON p.id = pd.pub_proc
                             WHERE pd.doc_id = protocol.id
                               AND p.pub_subset IN ('Protocol-Quarterly status'
                                                  + '/participant check', 
                                                    'Protocol-Initial status'
                                                  + '/participant check')
                               AND (p.status = 'Success'
                                OR p.completed IS NULL))
       GROUP BY protocol.id""")
conn.commit()
cursor.execute("""\
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
           JOIN query_term lead_org_status
             ON lead_org_status.doc_id = lead_org.doc_id
            AND LEFT(lead_org.node_loc, 8) =
                LEFT(lead_org_status.node_loc, 8)
           JOIN document org
             ON org.id = lead_org.int_val
           JOIN document protocol
             ON protocol.id = lead_org.doc_id
           JOIN doc_version
             ON doc_version.id = protocol.id
           JOIN #mailer_prots
             ON #mailer_prots.ver = doc_version.num
            AND #mailer_prots.id  = doc_version.id
           JOIN query_term org_type
             ON org_type.doc_id = org.id
          WHERE lead_org.path     = '/InScopeProtocol/ProtocolAdminInfo'
                                  + '/ProtocolLeadOrg/LeadOrganizationID'
                                  + '/@cdr:ref'
            AND person_link.path  = '/InScopeProtocol/ProtocolAdminInfo'
                                  + '/ProtocolLeadOrg/LeadOrgPersonnel'
                                  + '/Person/@cdr:ref'
            AND person_role.path  = '/InScopeProtocol/ProtocolAdminInfo'
                                  + '/ProtocolLeadOrg/LeadOrgPersonnel'
                                  + '/PersonRole'
            AND org_type.path     = '/Organization/OrganizationType'
            AND person_role.value = 'Update person'
            AND lead_org_status.value IN (
                                   'Active',
                                   'Approved-not yet active',
                                   'Temporarily closed')
            AND EXISTS (SELECT *
                          FROM query_term contact_mode
                         WHERE contact_mode.path = '/Organization'
                                                 + '/OrganizationDetails'
                                                 + '/PreferredProtocol'
                                                 + 'ContactMode'
                           AND contact_mode.doc_id = lead_org.int_val)""",
               timeout = 300)
rows = cursor.fetchall()
for row in rows:
    (recipId, recipName, orgId, orgName, docId, docTitle,
     docVersion, addrLink, orgType) = row
    key      = (addrLink, docId, orgId)
    recip    = pups.get(addrLink)
    protocol = prots.get(docId)
    org      = orgs.get(orgId)
    mailer   = mailers.get(key)
    if not recip:
        pups[addrLink] = recip = PUP(recipId, recipName, addrLink)
    if not org:
        orgs[orgId] = org = LeadOrg(orgId, orgName)
    if not protocol:
        prots[docId] = protocol = Protocol(docId, docVersion, docTitle)
    if not orgType in org.orgTypes:
        org.orgTypes.append(orgType)
    if not mailer:
        mailers[key] = mailer = Mailer(org, protocol, recip)
        recip.mailers.append(mailer)

jobTime = time.strftime("%Y%m%d%H%M%S")
dirName = time.strftime("Emailer-%s" % jobTime)
os.mkdir(dirName)
manifest = open("%s/manifest.xml" % dirName, "w")
manifest.write("""\
<?xml version="1.0" encoding="UTF-8"?>
<Manifest jobTime='%s'>
""" % jobTime)

for key in pups:
    pup = pups[key]
    print "processing mailers for %s (%s)" % (pup.addrLink,
                                              pup.name.encode('ascii',
                                                              "ignore")[:40])
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
        print "\tprotocol %d: %s" % (mailer.protocol.docId,
                                     mailer.protocol.title.encode('ascii',
                                                                  'ignore')
                                     [:40])
        print "\tlead org %d: %s" % (mailer.leadOrg.docId,
                                     mailer.leadOrg.orgName.encode('ascii',
                                                                   'ignore')
                                     [:40])
        parms = [('leadOrgId', 'CDR%010d' % mailer.leadOrg.docId)]
        rsp = cdr.filterDoc('guest', filters, mailer.protocol.docId,
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
