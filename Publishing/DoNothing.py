#!d:/python/python.exe
# *******************************************************
# File Name:  DoNothing.py
#             ---------------
# Sript to be initiated for various steps in the 
# Jobmaster.py program to skip over these.
# *******************************************************
import cdr, sys, socket, os.path

l = cdr.Log('Jobmaster.log')
localhost = socket.gethostname()
message   = "%s: Doing nothing - per request!" % localhost
l.write(message, stdout = True)

sys.exit(0)
