import sys, cdrxmllatex

""" Test driver for cdrxmllatex.makeLatex() """

if len (sys.argv) < 3:
    print "usage: TestLatex.py xmlfile format {subformat}"
    sys.exit(1)

# First arg is input file name
try:
    inf = open (sys.argv[1], "r")

except Exception:
    sys.stderr.write (str(sys.exc_info()[1]))
    sys.exit(1)

# Format and subformat
fmt = sys.argv[2]
if len (sys.argv) > 3:
    subfmt = sys.argv[3]
else:
    subfmt = ""

# Read in XML
xmlText = inf.read()

# Try it
latexDoc = cdrxmllatex.makeLatex (xmlText, fmt, subfmt)

# Output
print latexDoc.getLatex()
