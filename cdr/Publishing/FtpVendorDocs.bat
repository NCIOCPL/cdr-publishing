cd \cdr\output\%1

tar cvjf Country.tar.bz2 Country
tar cvjf PoliticalSubUnit.tar.bz2 PoliticalSubUnit
tar cvjf Person.tar.bz2 Person
tar cvjf Organization.tar.bz2 Organization
tar cvjf Summary.tar.bz2 Summary
tar cvjf Terminology.tar.bz2 Terminology
tar cvjf GlossaryTerm.tar.bz2 GlossaryTerm
tar cvjf ProtocolActive.tar.bz2 ProtocolActive
tar cvjf ProtocolClosed.tar.bz2 ProtocolClosed

c:\Winnt\System32\ftp.exe -i -s:\cdr\publishing\VendorDocsFtpScript
