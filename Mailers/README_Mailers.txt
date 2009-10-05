LaTeX Mailer Creation
=====================
(Document created:  07/18/2002)

1.  Sample File Location
    For each mailer type exists a directory on MMDB2 under
        d:\venglisch\tex\cdr
    The directory names are
    - genetics            No genetics mailers are being created
    - org                 Organization mailer
    - patsum              Summary mailer
    - person              Person mailer
    - prot_abstract       Protocol abstract mailer
    - prot_statpart       Protocol status and participant check mailer

    Each of these directories contain one (or more) samples of the LaTeX
    document that the system has to create.  In other words, we are trying to
    make the system create a LaTeX document that 'looks' as close to this as
    possible.

2.  Development File Location
    The mailers are developed on MMDB2 in the directory
        d:\venglisch\tex\test

3.  Mailer Development
    Alan has written the software that allows us to extract a particular node
    from the XML document and prefix or suffix the data of the element with
    some text.  This text to be added will mostly  be our case LaTeX code.
    The LaTeX code to be added, prefixed or suffixed is controlled via a
    control file called:
        cdrlatexlib.py
    This control file is being used to add the LaTeX code to the XML document
    as well as including Python functions needed to perform special tasks that
    can not be handled via the standard cdrlatexlib.py functionallity.
    All the work involved in creating the LaTeX mailer documents involves
    adding special processing functions and entering the proper control code
    in the cdrlatexlib.py program.

4.  Development process
    In the development directory (assuming d:\venglisch\tex\test)
    will be the source file located (*.xml), the start command
    procedure (*.cmd), and the cdrlatexlib.py control file.
    The command procedure runs the Python program to extract the
    XML text elements from the XML source document and combines
    these into a LaTeX document (*.tex).
    That LaTeX document will be processed via the latex program
    to create the *.dvi file which in turn is being converted
    from the device file *.dvi into a PostScript file (*.ps).
    The PostScript file shows the result of the mailer process.

    This is a sample of the command file (e.g. run_person.cmd):
       python TestLatex.py person_denorm.xml Person > Person.tex
       latex Person.tex
       dvips Person.dvi
    where
    - person_denorm.xml is the XML source file created by
      running a document through the appropriate CDR
      denormalization filter and saving the resulting output in the
    - Person is the parameter passed to the cdrlatexlib.py control file
      to indicate which mailer type is to be processed.
    - Person.tex is the file to be processed with LaTeX
    - Person.dvi is the output file created by the LaTeX
      processor and the input file for the dvips converter.
    - Person.ps is the resulting PostScript output once this
      command procedure finished executing.

    Currently, there exist the following mailer types:
      Protocol
      Summary
      Summary,initial
      Organization
      Person
      StatusCheck
      StatusCheckCCOP
      Test

    Each of the mailer types are set to process different mailer
    instructions and each of these instructions are concatenating
    the LaTex Header with the Body and the Footer of the mailer.
    For example, by initializing the Person mailer the Python
    program processes the PersonInstructions
       ("Person",           ""):PersonInstructions,
    which are concatenating the PersonHeader, ...
       PersonInstructions =     \
         DocumentPersonHeader + \
         DocumentPersonBody   + \
         DocumentPersonFooter

    The document header and footer are mainly a concatenation of
    the individual LaTeX elements needed for the particular
    mailer that don't require any data from the XML source.
    For instance the DocumentPersonHeader is defined as:
      DocumentPersonHeader =(
        XProc(prefix=LATEXHEADER),
        XProc(prefix=DRAFT),
        XProc(prefix=FONT),
        XProc(prefix=STYLES),
        XProc(prefix=ENTRYLIST),
        XProc(prefix=QUOTES),
        XProc(prefix=PERSON_HDRTEXT),
        XProc(prefix=FANCYHDR),
        XProc(prefix=TEXT_BOX),
        XProc(prefix=PHONE_RULER),
        XProc(prefix=PERSON_DEFS),
        XProc(prefix=PERSON_TITLE),
        XProc(prefix=ENDPREAMBLE)
        )

   where the first line sets up the LaTeX header
   the second line includes the Draft style for this document
   the third line sets the font
   ...
   These sections were created based on CIPS requirements for the
   layout and should not need any modifications unless the
   requirements change.

   The real work of creating the mailers is being done in the 'Body'
   section, which extracts the data from the XML source document
   by stringing together a number of XProc functions.  Each of
   these XProc functions is extracting an element from the XML
   document, adds some code to the beginning of the element text node of
   (using the prefix option), adds some LaTeX code to
   the end of the element text node (using the suffix option),
   defining the text output mode (using the textOut option), and
   setting the position of the output element (using the order
   option).
   The LaTeX document is setup such that extracting the data
   mostly means to set the LaTeX defined variables properly to be
   printed within a template.

   For example, in order to print the name of a person in the
   person mailer the following source code is passed to the
   program:
     <PersonNameInformation>
       <GivenName>Louis S.</GivenName>
       <SurName>Constine</SurName>
       <GenerationSuffix>III</GenerationSuffix>
       <ProfessionalSuffix>
         <StandardProfessionalSuffix>MD</StandardProfessionalSuffix>
       </ProfessionalSuffix>
     </PersonNameInformation>

   This section will be processed with the XProc statements:
     XProc(element="GivenName",
           order=1,
           prefix="  \\newcommand{\Person}{",
           suffix=" "),
     XProc(element="SurName",
           order=1,
           suffix="}\n"),
     XProc(element="StandardProfessionalSuffix",
           prefix="  \\newcommand{\PerSuffix}{",
           suffix="}\n"),

   The Python program creates this LaTeX code from the given
   information:
     \newcommand{\Person}{Louis S. Constine}
     \newcommand{\PerSuffix}{MD}

   which will then printed as part of the following address
   template:
      %% PERSON_PRINT_CONTACT %%
      %% -------------------- %%
      \Person, \PerSuffix  \\
      \Org     \\
      \Street   \\
      \City, \PoliticalUnitState\  \PostalCodeZIP \\






To Do:
======
General:
-
Organizations:
- The final document structure is very different from the
  structure used for testing.
  The program will need to be modified and most of the element
  tags will have to be renamed.
- modify street() function to position the ZIP code according to
  the PostalCodePosition element
- modify the address to include the parent name if attribute is
  set accordingly
- modify the address to sort the paranet name to the top/bottom
  according to the given attribute


Person:
- The final document structure is very different from the
  structure used for testing.
  The program will need to be modified and most of the element
  tags will have to be renamed.
  It may be simpler to preformat the XML documents using XSLT
  filters.
- Include code not to print a comma if there is a generation
  suffix element.
- street() function prints a \\newline for every sibling node
  instead of printing a \\newline for every 'Street' sibling
  node.
- When the datenumber and calc packages are both used an error
  message is reported from the calc package.
  Without the calc package, the width of the labels for the lists
  can not be calculated.
  Without the datenumber package, the deadline (when to return
  the mailer) can not be calculated.



Summary:
- In-line markup not implemented
- The attributes for lists (style, compact=Y/N) are not
  implemented.
- Nested SummarySections are currently not displayed.
- In-line summary references are not implemented.
-

Protocol:
- The phone number for the protocol chair needs to be selected
  based on the data of an element.
- The low age limit is not extracted from the XML source (and I
  just cannot find out why that is.
-
