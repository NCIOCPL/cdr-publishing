import cdrmailer, cdrxmllatex

class DummyJob(cdrmailer.MailerJob):
    def t(self, addressXml):
        addr = cdrmailer.Address(addressXml)
        return self.createAddressLabelPage(addr)

xmlAddress = u"""\
<?xml version="1.0" encoding="UTF-8"?>
<AddressElements xmlns:cdr="cips.nci.nih.gov/cdr">
 <PersonName>
  <GivenName>G\u00fcnther</GivenName>
  <MiddleInitial>M.</MiddleInitial>
  <SurName>von Ma\u0142ek</SurName>
  <ProfessionalSuffix>
   <StandardProfessionalSuffix>MD</StandardProfessionalSuffix>
  </ProfessionalSuffix>
  <Comment>
   LS Skehan request - PI; 8/90 gmd.
   Name was Van Den Stadt, changed per 8/90 m/m; 11/90 gmd.
   Grp 55 dele per 12/95 EORTC update 1/96 nge.
  </Comment>
 </PersonName>
 <OrgName>Universit\xe4tsklinik f\xfcr Dermatologie</OrgName>
 <ParentNames>
  <ParentName>Karl-FranzensUniversity Graz</ParentName>
 </ParentNames>
 <PostalAddress AddressType="Non US">
  <Street>Auenbruggerstra\u00dfe 8</Street>
  <City>Graz</City>
  <Country cdr:ref="CDR0000043769">Austria</Country>
  <PostalCode_ZIP>A-8036</PostalCode_ZIP>
  <CodePosition>after City</CodePosition>
 </PostalAddress>
 <Phone>3123-5141516</Phone>
 <Fax>3123-5291560</Fax>
 <Email Public="No">intspzhe@knmg.nl</Email>
</AddressElements>
"""
dummyJob = DummyJob(42)
latex = dummyJob.t(xmlAddress.encode('utf-8'))
print latex
