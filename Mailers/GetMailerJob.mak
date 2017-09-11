#----------------------------------------------------------------------
# Rules for building the tool for fetching a mailer job.
#----------------------------------------------------------------------
GetMailerJob.exe: GetMailerJob.cpp
	cl /EHa /DWINVER=0x0501 /MD /D_AFXDLL=1 GetMailerJob.cpp /link /OPT:NOREF
