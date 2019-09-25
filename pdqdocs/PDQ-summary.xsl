<?xml version = "1.0" ?>
<!-- 
================================================================
XSLT PDQ Summaries Transformation Example
Date: 2016-03-22
================================================================ -->
<xsl:stylesheet                version = "1.0" 
                             xmlns:xsl = "http://www.w3.org/1999/XSL/Transform">
  <xsl:output                   method = "html"
                              encoding = "utf-8"/>
  <xsl:param                      name = "section"
  								select = "'*'"/>
  <xsl:param                      name = "targetedDevice"
                                select = "'screen'"/>
  <xsl:param                      name = "pp"
                                select = "'Y'"/>
  <xsl:param                      name = "default.table.width" 
                                select = "''"/>

  <xsl:variable                   name = "cdrId"
                                select = "number(
                                           substring-after(/Summary/@id, 
                                                           'CDR'))"/>
  <!-- Define a variable for the summary type -->
  <xsl:variable                   name = "sType">
   <xsl:choose>
    <xsl:when                     test = "/Summary/
                                           SummaryMetaData/
                                           SummaryType = 
                                      'Complementary and alternative medicine'">
     <xsl:text>cam</xsl:text>
    </xsl:when>
    <xsl:when                     test = "/Summary/
                                           SummaryMetaData/
                                           SummaryType = 'Genetics'">
     <xsl:text>genetics</xsl:text>
    </xsl:when>
    <xsl:otherwise>
     <xsl:text>other</xsl:text>
    </xsl:otherwise>
   </xsl:choose>
  </xsl:variable>

  <!-- Define a variable for the audience type -->
  <xsl:variable                   name = "audience">
   <xsl:choose>
    <xsl:when                     test = "/Summary/
                                           SummaryMetaData/
                                           SummaryAudience = 'Patients'">
     <xsl:text>patient</xsl:text>
    </xsl:when>
    <xsl:otherwise>
     <xsl:text>healthprofessional</xsl:text>
    </xsl:otherwise>
   </xsl:choose>
  </xsl:variable>

  <!-- Define a variable for the language type -->
  <xsl:variable                   name = "language">
   <xsl:choose>
    <xsl:when                     test = "/Summary/
                                           SummaryMetaData/
                                           SummaryLanguage = 'English'">
     <xsl:text>en</xsl:text>
    </xsl:when>
    <xsl:when                     test = "/Summary/
                                           SummaryMetaData/
                                           SummaryLanguage = 'Spanish'">
     <xsl:text>es</xsl:text>
    </xsl:when>
    <xsl:otherwise>
     <xsl:text>undefined</xsl:text>
    </xsl:otherwise>
   </xsl:choose>
  </xsl:variable>

  <!-- Create the string values for different languages -->
  <xsl:variable                   name = "strEnlarge">
   <xsl:choose>
    <xsl:when                     test = "$language = 'en'">
     <xsl:text>Enlarge</xsl:text>
    </xsl:when>
    <xsl:when                     test = "$language = 'es'">
     <xsl:text>Ampliar</xsl:text>
    </xsl:when>
    <xsl:otherwise>
     <xsl:text>undefined</xsl:text>
    </xsl:otherwise>
   </xsl:choose>
  </xsl:variable>

 <!--
 ================================================================
 ================================================================ -->
  <xsl:template                  match = "/Summary">
   <xsl:variable                  name = "page"
                                select = "SummarySection[$section]"/>

<html>
 <head>
  <xsl:element                    name = "meta">
   <xsl:attribute                 name = "name">
    <xsl:text>content-language</xsl:text>
   </xsl:attribute>
   <xsl:attribute                 name = "content">
    <xsl:value-of               select = "$language"/>
   </xsl:attribute>
  </xsl:element>
  <title>
   <xsl:text>WCMS Summary: </xsl:text>
   <xsl:value-of             select = "SummaryTitle"/>
  </title>

<link href="http://www.cancer.gov/PublishedContent/Styles/nvcg.css" 
      type="text/css" rel="StyleSheet"/>

  <script type="text/javascript" 
           src="http://ajax.googleapis.com/ajax/libs/jquery/1.5.1/jquery.min.js"></script>
  <script type="text/javascript">
// wrap a div with overflow: auto around all tables in the body 
$(document).ready(function() { 
$('.contentzoneXXX table').wrap('<div style="overflow: auto;"></div>'); 
});
</script>

 <style type="text/css">
  body { background: none; }

  .contentzone {
           float: none;
           margin: 10px auto 0; }
           
  .enlarged, normal { }

  ol.lower-alpha  { list-style-type: lower-alpha; }
  ol.lower-roman  { list-style-type: lower-roman; }
  ol.upper-alpha  { list-style-type: upper-alpha; }
  ol.upper-roman  { list-style-type: upper-roman; }
 </style>

 </head>
 <body>
  <div class="contentzone">
  <article id="_article">
   <xsl:apply-templates         select = "SummaryMetaData"/>
   <xsl:apply-templates         select = "SummaryTitle"/>

   <!--
   There are no TOC or KeyPoint boxes on mobile
   =================================================================== -->
   <xsl:if                        test = "$targetedDevice = 'screen'">
    <!-- create container to insert full document TOC -->
    <xsl:element                  name = "div">
     <xsl:attribute               name = "id">
      <xsl:text>_toc_article</xsl:text>
     </xsl:attribute>
     <!-- Style it -->
     <xsl:attribute               name = "class">
      <xsl:text>pdq-on-this-page</xsl:text>
     </xsl:attribute>
    </xsl:element>
   </xsl:if>

   <!--
   We have to loop over each top section in order to set the numbering
   for the References section
   This is also where we're creating the KeyPoints box and the TOC
   =================================================================== -->
   <xsl:for-each                select = "$page">
    <xsl:variable                 name = "topSection">
     <xsl:text>section_</xsl:text><xsl:number/>
    </xsl:variable>

    <xsl:if                       test = "(contains(
                                            concat(' ', @IncludedDevices, ' '), 
                                            concat(' ', $targetedDevice, ' ')
                                            ) 
                                           or 
                                           not(@IncludedDevices)
                                          ) 
                                          and 
                                          (not(contains(
                                            concat(' ', @ExcludedDevices, ' '), 
                                            concat(' ', $targetedDevice, ' ')
                                            )) 
                                           or 
                                           not(@ExcludedDevices)
                                          )">
     <xsl:element                 name = "section">
      <xsl:attribute              name = "id">
       <xsl:text>_section</xsl:text>
       <xsl:value-of            select = "./@id"/>
       <xsl:text>_</xsl:text>
       <xsl:value-of            select = "count(preceding-sibling::SummarySection) + 1"/>
      </xsl:attribute>
      <xsl:attribute              name = "class">
       <xsl:text>pdq-sections</xsl:text>
      </xsl:attribute>


      <!--
      Mobile needs an extra div
      ========================= -->
      <xsl:choose>
       <xsl:when                  test = "$targetedDevice = 'mobile'">
        <xsl:element              name = "div">
         <xsl:attribute           name = "data-role">
          <xsl:text>collapsible</xsl:text>
         </xsl:attribute>
         <xsl:attribute           name = "data-collapsed">
          <xsl:text>true</xsl:text>
         </xsl:attribute>
         <xsl:attribute           name = "data-iconpos">
          <xsl:text>right</xsl:text>
         </xsl:attribute>
         <xsl:attribute           name = "name">
          <xsl:text>Section{@id}</xsl:text>
         </xsl:attribute>
         <xsl:attribute           name = "id">
          <xsl:text>Section{@id}</xsl:text>
         </xsl:attribute>
         <xsl:call-template       name = "Title_TOC_KP">
          <xsl:with-param         name = "topSection"
                                select = "$topSection"/>
         </xsl:call-template>
        </xsl:element>
       </xsl:when>
       <xsl:otherwise>
        <xsl:call-template        name = "Title_TOC_KP">
         <xsl:with-param          name = "topSection"
                                select = "$topSection"/>
        </xsl:call-template>
       </xsl:otherwise>
      </xsl:choose>
     </xsl:element>

    </xsl:if>
   </xsl:for-each>
  </article>
  </div>

  <xsl:call-template              name = "addTOC"/>
  <xsl:call-template              name = "SuperSizeMe"/>

 </body>
</html>
  </xsl:template>


  <!--
  ================================================================
  =================================================================== -->
  <xsl:template                   name = "Title_TOC_KP">
   <xsl:param                     name = "topSection"
                                select = "'toc'"/>
   <!-- The section title of the top SummarySection has to be
        printed above the keypoints box or the TOC -->
   <xsl:apply-templates         select = "Title"/>

   <!-- Create a container for the TOC for this section 
        Note: We only want to add this diff if there exist subsections
              and this should not be added if there are key points.
   ===================================================================== -->
   <xsl:if                        test = "(descendant::SummarySection 
                                           and
                                           $audience = 'healthprofessional')
                                           or
                                           ($audience = 'patient'
                                            and
                                            not(descendant::KeyPoint))">
    <xsl:element                  name = "div">
     <xsl:attribute               name = "id">
      <xsl:text>_toc_section</xsl:text>
     <xsl:value-of              select = "./@id"/>
     <xsl:text>_</xsl:text>
      <xsl:value-of             select = "count(preceding-sibling::SummarySection) + 1"/>
     </xsl:attribute>
     <xsl:attribute               name = "class">
      <xsl:text>pdq-on-this-page</xsl:text>
     </xsl:attribute>
     <xsl:text> </xsl:text>
    </xsl:element>
   </xsl:if>

   <!--
   There are no TOC or KeyPoint boxes on mobile
   These only get created for the desktop.
   =================================================================== -->
   <xsl:if                        test = "../descendant::KeyPoint
                                          and
                                          not($targetedDevice = 'mobile')">
    <!-- xsl:call-template         name = "keypointsboxJS"/ -->
    <xsl:call-template            name = "keypointsbox"/>
   </xsl:if>
 
   <xsl:apply-templates         select = "*[not(self::Title)]">
    <xsl:with-param               name = "topSection"
                                select = "$topSection"/>
   </xsl:apply-templates>

  </xsl:template>


  <!--
  ================================================================
  Template to use jQuery to create Enlarge buttons for Tables and 
  Images
  =================================================================== -->
  <xsl:template                  name = "SuperSizeMe">
   <script type="text/javascript"
           src="FTP_summary_files/Enlarge.js"></script>

   <script type="text/javascript">
      <xsl:text>
       $(function() {
          $( ".expandable-container" ).supersizeme( { } );
        });
      </xsl:text>
   </script>
  </xsl:template>


  <!--
  ================================================================
  This JavaScript calls the TOC function to attach the TOC to the DIV
  element with ID="_toc_section_N" N=1,2,3,...
  =================================================================== -->
  <xsl:template                  name = "addTOC">
   <script type="text/javascript"
           src="FTP_summary_files/STOC.js"></script>

   <script id="sectionToc" type="text/javascript">
      <xsl:text>
       $(function(){
      <!-- Full document TOC -->
          $("#_toc_article").stoc({ search: "article", start: 2, depth: 3,
          tocTitleEn: "Table of content for this document",
          tocTitleEs: "Tabla de contenidos para esta (document???)"});
      </xsl:text>
      
    <xsl:choose>
     <xsl:when                    test = "$audience = 'patient'">
      <xsl:for-each             select = "/Summary/SummarySection">
       <xsl:variable              name = "thisSection"
                                select = "count(
                                          preceding-sibling::SummarySection) + 1"/>
       <xsl:choose>
       <xsl:when                  test = "descendant::KeyPointXXX">
        <xsl:text>
          $("#_toc_section</xsl:text>
         <xsl:value-of          select = "./@id"/>
         <xsl:text>_</xsl:text>
         <xsl:value-of          select = "$thisSection"/>
         <xsl:text>").stoc({search: "#_section</xsl:text>
         <xsl:value-of          select = "./@id"/>
         <xsl:text>_</xsl:text>
         <xsl:value-of          select = "$thisSection"/>
         <xsl:text>", start: 3</xsl:text>
         <xsl:text>, depth: 2</xsl:text>
         <!-- xsl:text>, kp: 1</xsl:text -->
         <xsl:text>});</xsl:text>
       </xsl:when>
       <xsl:otherwise>
       <xsl:if                     test = "descendant::SummarySection">
        <xsl:text>
         $("#_toc_section</xsl:text>
        <xsl:value-of       select = "./@id"/>
        <xsl:text>_</xsl:text>
        <xsl:value-of select = "$thisSection"/>
        <xsl:text>").stoc({search: "#_section</xsl:text>
        <xsl:value-of       select = "./@id"/>
        <xsl:text>_</xsl:text>
        <xsl:value-of select = "$thisSection"/>
        <xsl:text>",</xsl:text>
        <xsl:text> start: 3,</xsl:text>
        <xsl:text> depth: 2,</xsl:text>
        <xsl:text> tocTitleEn:"Table of content for this section", </xsl:text>
        <xsl:text> tocTitleEs:"Tabla de contenidos para esta secci&#243;n"</xsl:text>
        <xsl:text>});</xsl:text>
       </xsl:if>
       </xsl:otherwise>
       </xsl:choose>
      </xsl:for-each>
     </xsl:when>
     <xsl:otherwise>
      <!-- 
      Create TOC for HP sections
      (but suppress TOC header if no subsections exist)
      ================================================================= -->
      <xsl:for-each              select = "/Summary/SummarySection">
      <xsl:variable               name = "thisSection"
                                select = "count(
                                          preceding-sibling::SummarySection) + 1"/>
       <xsl:if                     test = "descendant::SummarySection">
        <xsl:text>
         $("#_toc_section</xsl:text>
        <xsl:value-of       select = "./@id"/>
        <xsl:text>_</xsl:text>
        <xsl:value-of select = "$thisSection"/>
        <xsl:text>").stoc({search: "#_section</xsl:text>
        <xsl:value-of       select = "./@id"/>
        <xsl:text>_</xsl:text>
        <xsl:value-of select = "$thisSection"/>
        <xsl:text>",</xsl:text>
        <xsl:text> start: 3,</xsl:text>
        <xsl:text> depth: 2,</xsl:text>
        <xsl:text> tocTitleEn:"Table of content for this section", </xsl:text>
        <xsl:text> tocTitleEs:"Tabla de contenidos para esta secci&#243;n"</xsl:text>
        <xsl:text>});</xsl:text>
       </xsl:if>
      </xsl:for-each>

     </xsl:otherwise>
    </xsl:choose>
      <xsl:text>
         });</xsl:text>
   </script>
  </xsl:template>


  <!--
  ================================================================
  Template to display basic meta data information
  *** for testing only ***
  ================================================================ -->
  <xsl:template                  match = "SummaryMetaData">
    <div style="background-color: yellow;">
    <p>
     <xsl:apply-templates       select = "../@id"/>
     <xsl:text>;</xsl:text>
     <xsl:apply-templates       select = "SummaryType"/>
     <xsl:text>;</xsl:text>
     <xsl:apply-templates       select = "SummaryAudience"/>
     <xsl:text>;</xsl:text>
     <xsl:apply-templates       select = "SummaryLanguage"/>
    </p>
    </div>
  </xsl:template>

  <!--
  ================================================================
  Template to remove display of SectionMetaData on any level
  ================================================================ -->
  <xsl:template                  match = "SectMetaData">
    <!-- This template is empty -->
  </xsl:template>

  <!--
  ================================================================
  ================================================================ -->
  <xsl:template                  match = "SummaryTitle">
    <xsl:element                  name = "h1">
     <xsl:value-of              select = "substring-before(., '(PDQ')"/>
     <xsl:text>(PDQ</xsl:text>
     <xsl:element                 name = "sup">
      <xsl:text>&#174;</xsl:text>
     </xsl:element>
     <xsl:text>)</xsl:text>
    </xsl:element>
  </xsl:template>

  <!--
  ================================================================
  Template for Top SummarySections
  Note: SummarySections may be excluded from mobile
  ================================================================ -->
  <xsl:template                  match = "SummarySection">
   <xsl:param                     name = "topSection" 
                                select = "'sub'"/>
   <xsl:choose>
    <xsl:when                     test = "(contains(
                                            concat(' ', @IncludedDevices, ' '), 
                                            concat(' ', $targetedDevice, ' ')
                                            ) 
                                           or 
                                           not(@IncludedDevices)
                                          ) 
                                          and 
                                          (not(contains(
                                            concat(' ', @ExcludedDevices, ' '), 
                                            concat(' ', $targetedDevice, ' ')
                                            )) 
                                           or 
                                           not(@ExcludedDevices)
                                          )">
     <xsl:element                 name = "section">
      <xsl:attribute              name = "id">
       <xsl:value-of            select = "@id"/>
      </xsl:attribute>
     <xsl:apply-templates>
      <xsl:with-param             name = "topSection"
                                select = "$topSection"/>
     </xsl:apply-templates>
     </xsl:element>
    </xsl:when>
    </xsl:choose>
   </xsl:template>

  <!--
  ================================================================
  Display the Keypoints as Titles within the text
  ================================================================ -->
  <xsl:template                  match = "KeyPoint">
   <xsl:variable                  name = "nestedKp">
    <xsl:choose>
     <xsl:when                 test = "count(ancestor::SummarySection) + 2 > 6">
      <xsl:text>h6</xsl:text>
     </xsl:when>
     <xsl:otherwise>
      <xsl:value-of          select = "concat('h',
                                        count(ancestor::SummarySection) + 1)"/>
     </xsl:otherwise>
    </xsl:choose>
   </xsl:variable>

   <xsl:element                   name = "{$nestedKp}">
    <xsl:attribute                name = "id">
     <xsl:value-of              select = "@id"/>
    </xsl:attribute>
    <xsl:attribute                name = "type">
     <xsl:text>keypoint</xsl:text>
    </xsl:attribute>
    <xsl:apply-templates/>
   </xsl:element>
  </xsl:template>


  <!--
  ================================================================
  Create the section titles
  ================================================================ -->
  <xsl:template                  match = "Title">
   <xsl:param                     name = "topSection" 
                                select = "'title'"/>
   <xsl:choose>
    <xsl:when                     test = "$topSection = 'title'
                                          and
                                          not($targetedDevice = 'mobile')">
     <xsl:element                 name = "h2">
      <xsl:attribute              name = "id">
       <xsl:value-of            select = "parent::SummarySection/@id"/>
       <xsl:text>_toc</xsl:text>
      </xsl:attribute>
      <xsl:apply-templates/>
     </xsl:element>
    </xsl:when>
    <xsl:when                     test = "$topSection = 'title'
                                          and
                                          $targetedDevice = 'mobile'">
     <xsl:element                 name = "h2">
      <xsl:attribute              name = "id">
       <xsl:value-of            select = "parent::SummarySection/@id"/>
       <xsl:text>_toc</xsl:text>
      </xsl:attribute>
      <xsl:attribute              name = "class">
       <xsl:text>section_heading</xsl:text>
      </xsl:attribute>
      
      <xsl:element                name = "span">
       <xsl:apply-templates/>
      </xsl:element>
     </xsl:element>
    </xsl:when>
    <xsl:otherwise>
     <!--
     Testing the level of nested sections to determine the H-tag
     The top SummarySection starts with the H3 tag.
     If the level goes beyond 6 everything will be marked up as level 6
     ================================================================== -->
     <xsl:variable               name = "nestedLevel">
      <xsl:choose>
       <xsl:when                 test = "count(ancestor::*) + 0 > 6">
        <xsl:text>h6</xsl:text>
       </xsl:when>
       <xsl:otherwise>
        <xsl:value-of          select = "concat('h',count(ancestor::*) + 0)"/>
       </xsl:otherwise>
      </xsl:choose>
     </xsl:variable>

     <xsl:element                name = "{$nestedLevel}">
      <xsl:attribute             name = "id">
       <xsl:value-of           select = "parent::SummarySection/@id"/>
       <xsl:text>_toc</xsl:text>
      </xsl:attribute>
      <xsl:apply-templates/>
     </xsl:element>
    </xsl:otherwise>
   </xsl:choose>
  </xsl:template>

  <!--
  ================================================================
  ================================================================ -->
  <xsl:template                  match = "Para">
   <xsl:param                     name = "topSection" 
                                select = "'para'"/>
   <xsl:element                   name = "p">
    <xsl:attribute                name = "id">
     <xsl:value-of              select = "@id"/>
    </xsl:attribute>
    <xsl:attribute                name = "tabindex">
     <xsl:text>0</xsl:text>
    </xsl:attribute>

    <xsl:apply-templates>
     <xsl:with-param              name = "topSection"
                                select = "$topSection"/>
    </xsl:apply-templates>
   </xsl:element>
  </xsl:template>

  <!--
  ================================================================
  An itemized list will be converted into a DD/DL if the style is
  simple
  ================================================================ -->
  <xsl:template                  match = "ItemizedList">
   <xsl:param                     name = "topSection" 
                                select = "'il'"/>
   <xsl:element                   name = "div">
    <xsl:attribute                name = "class">
     <xsl:text>pdq-content-list</xsl:text>
    </xsl:attribute>

    <xsl:apply-templates        select = "ListTitle"/>
    <xsl:element                  name = "ul">
     <xsl:attribute               name = "id">
      <xsl:value-of             select = "@id"/>
     </xsl:attribute>
     <xsl:apply-templates       select = "@Style"/>
     <xsl:apply-templates       select = "ListItem">
      <xsl:with-param             name = "topSection"
                                select = "$topSection"/>
     </xsl:apply-templates>
    </xsl:element>
   </xsl:element>
  </xsl:template>

  <!--
  ================================================================
  An itemized list will be converted into a DD/DL if the style is
  simple
  This has changed:  We're now keeping the list item and creating 
  a new style 'no-bullets'.
  ================================================================ -->
  <xsl:template                  match = "XX_ItemizedList[@Style='simple']">
   <xsl:param                     name = "topSection" 
                                select = "'il'"/>
   <xsl:element                   name = "dl">
    <xsl:attribute                name = "id">
     <xsl:value-of              select = "@id"/>
    </xsl:attribute>
    <xsl:apply-templates          mode = "simple">
     <xsl:with-param              name = "topSection"
                                select = "$topSection"/>
    </xsl:apply-templates>
   </xsl:element>
  </xsl:template>

  <!--
  ================================================================
  Ordered lists will be displayed as is
  Unordered lists will be displayed without style and without 
  compact mode.  No 'dash', no 'bullet'.  
  Style="simple" will be converted into class="no-bullets" (indentation?)
  and eventually converted to some sort of address block when available
  ================================================================ -->
  <xsl:template                  match = "@Style">
   <xsl:choose>
    <xsl:when                      test = ". = 'bullet'"/>
    <!-- Arabic (i.e. class="decimal") is the default.  
         Don't need to include this in the HTML output -->
    <xsl:when                      test = ". = 'Arabic'"/>
    <xsl:otherwise>
     <xsl:attribute                 name = "class">
      <xsl:choose>
       <xsl:when                    test = ". = 'LAlpha'">
        <xsl:text>lower-alpha</xsl:text>
       </xsl:when>
       <xsl:when                    test = ". = 'LRoman'">
        <xsl:text>lower-roman</xsl:text>
       </xsl:when>
       <xsl:when                    test = ". = 'UAlpha'">
        <xsl:text>upper-alpha</xsl:text>
       </xsl:when>
       <xsl:when                    test = ". = 'URoman'">
        <xsl:text>upper-roman</xsl:text>
       </xsl:when>
       <xsl:when                    test = ". = 'circle'">
        <xsl:text>list-circle</xsl:text>
       </xsl:when>
       <xsl:when                    test = ". = 'square'">
        <xsl:text>list-square</xsl:text>
       </xsl:when>
       <xsl:when                    test = ". = 'dash'">
        <xsl:text>list-dash</xsl:text>
       </xsl:when>
       <xsl:when                    test = ". = 'simple'">
        <xsl:text>pdq-address-block</xsl:text>
       </xsl:when>
       <xsl:otherwise>
        <xsl:text>style_undefined</xsl:text>
       </xsl:otherwise>
      </xsl:choose>
     </xsl:attribute>
    </xsl:otherwise>
   </xsl:choose>
  </xsl:template>

  <!--
  ================================================================
  ================================================================ -->
  <xsl:template                  match = "OrderedList">
   <xsl:param                     name = "topSection" 
                                select = "'ol'"/>
   <xsl:element                   name = "div">
    <xsl:attribute                name = "class">
     <xsl:text>pdq-content-list</xsl:text>
    </xsl:attribute>

    <xsl:apply-templates        select = "ListTitle"/>
    <xsl:element                  name = "ol">
     <xsl:attribute               name = "id">
      <xsl:value-of             select = "@id"/>
     </xsl:attribute>
     <xsl:apply-templates       select = "@Style"/>
     <xsl:apply-templates       select = "ListItem">
      <xsl:with-param             name = "topSection"
                                select = "$topSection"/>
     </xsl:apply-templates>
    </xsl:element>
   </xsl:element>
  </xsl:template>

  <!--
  ================================================================
  ================================================================ -->
  <xsl:template                  match = "ListItem">
   <xsl:param                     name = "topSection" 
                                select = "'li'"/>
   <xsl:element                   name = "li">
    <xsl:apply-templates>
     <xsl:with-param              name = "topSection"
                                select = "$topSection"/>
    </xsl:apply-templates>
   </xsl:element>
  </xsl:template>

  <!--
  ================================================================
  ================================================================ -->
  <xsl:template                  match = "ListItemXXX"
                                  mode = "simple">
   <xsl:element                   name = "dd">
    <xsl:apply-templates/>
   </xsl:element>
  </xsl:template>

  <!--
  ================================================================
  ================================================================ -->
  <xsl:template                  match = "ListTitle">
   <xsl:element                   name = "p">
    <xsl:attribute                name = "class">
     <xsl:text>pdq-list-title</xsl:text>
    </xsl:attribute>

    <xsl:apply-templates/>
   </xsl:element>
  </xsl:template>


  <!--
  ================================================================
  Template to add a Note/Nota to the text
  ================================================================ -->
  <xsl:template                  match = "Note">
   <xsl:text>[</xsl:text>
   <xsl:element                   name = "em">
    <xsl:choose>
     <xsl:when                    test = "$language = 'en'">
      <xsl:text>Note: </xsl:text>
     </xsl:when>
     <xsl:when                    test = "$language = 'es'">
      <xsl:text>Nota: </xsl:text>
     </xsl:when>
     <xsl:otherwise>
      <xsl:text>***undefined***</xsl:text>
     </xsl:otherwise>
    </xsl:choose>

    <xsl:apply-templates/>

   </xsl:element>
   <xsl:text>]</xsl:text>
  </xsl:template>


  <!--
  ================================================================
  Template to display the citations in the Reference Section
  Note: There used to be two types of references: PubMed citations
        and protocol citations.  The protocol citations (i.e.
        @ProtocolID attributes) are not used anymore and therefore 
        not implemented here.
  ================================================================ -->
  <xsl:template                  match = "ReferenceSection">
   <xsl:param                     name = "topSection" 
                                select = "'ref'"/>
   <xsl:choose>
    <xsl:when                     test = "$language = 'en'">
     <xsl:element                 name = "h6">
      <xsl:text>References</xsl:text>
     </xsl:element>
    </xsl:when>
    <xsl:when                     test = "$language = 'es'">
     <xsl:element                 name = "h6">
      <xsl:text>Bibliograf&#237;a</xsl:text>
     </xsl:element>
    </xsl:when>
    <xsl:otherwise>
     <xsl:element                 name = "h6">
      <xsl:text>*** Undefined ***</xsl:text>
     </xsl:element>
    </xsl:otherwise>
   </xsl:choose>

    <ol>
     <xsl:for-each              select = "Citation">
      <xsl:variable               name = "pubMedUrl">
       <xsl:if                    test = "@PMID">
        <xsl:text>http://www.ncbi.nlm.nih.gov/entrez/query.fcgi</xsl:text>
        <xsl:text>?cmd=Retrieve&amp;db=PubMed&amp;list_uids=</xsl:text>
        <xsl:value-of           select = "@PMID"/>
        <xsl:text>&amp;dopt=Abstract</xsl:text>
       </xsl:if>
      </xsl:variable>
      <li>
       <xsl:attribute             name = "id">
        <xsl:value-of           select = "$topSection"/>
        <xsl:text>.</xsl:text>
        <xsl:value-of           select = "@idx"/>
       </xsl:attribute>
       
       <xsl:apply-templates/>
       <xsl:if                    test = "@PMID">
        <xsl:text> </xsl:text>
        <xsl:element              name = "a">
         <xsl:attribute           name = "href">
          <xsl:text>http://www.ncbi.nlm.nih.gov/entrez/query.fcgi</xsl:text>
          <xsl:text>?cmd=Retrieve&amp;db=PubMed&amp;list_uids=</xsl:text>
          <xsl:value-of          select = "@PMID"/>
          <xsl:text>&amp;dopt=Abstract</xsl:text>
         </xsl:attribute>
        <xsl:attribute            name = "title">
         <xsl:value-of           select = "$pubMedUrl"/>
        </xsl:attribute>
         <xsl:text>[PUBMED Abstract]</xsl:text>
        </xsl:element>
       </xsl:if>
      </li>
     </xsl:for-each>
    </ol>
  </xsl:template>


  <!--
  ================================================================
  Template to create the links to the reference section
  For PublishPreview we're creating the brackets.
  ================================================================ -->
  <xsl:template                  match = "Reference">
   <xsl:param                     name = "topSection" 
                                select = "'citation'"/>
    <xsl:if                       test = "$pp = 'Y'">
     <xsl:text>[</xsl:text>
    </xsl:if>

    <xsl:element                  name = "a">
     <xsl:attribute               name = "href">
      <xsl:text>#</xsl:text>
      <xsl:value-of             select = "$topSection"/>
      <xsl:text>.</xsl:text>
      <xsl:value-of             select = "@refidx"/>
     </xsl:attribute>
     <xsl:value-of              select = "@refidx"/>
    </xsl:element>

    <xsl:if                       test = "$pp = 'Y'">
     <xsl:text>]</xsl:text>
    </xsl:if>
  </xsl:template>


  <!--
  ================================================================
  Template to handle QandA sets
  Contains: MarkedUpTitle (optional)
            QandADiv+ or QandAEntry+
  ================================================================ -->
  <xsl:template                  match = "QandASet">
   <xsl:element                   name = "ol">
    <xsl:attribute                name = "id">
     <xsl:value-of              select = "@id"/>
    </xsl:attribute>
    <xsl:apply-templates        select = "MarkedUpTitle"/>
    <xsl:apply-templates        select = "QandAEntry"/>
   </xsl:element>
  </xsl:template>

  <!--
  ================================================================
  Template to handle MarkedUpTitle
  The element can contain inline markup elements
  Note:
  This element has not been clearly defined yet.  I'm setting it
  to <strong /> but it may need to be displayed in h-tags.
  ================================================================ -->
  <xsl:template                  match = "MarkedUpTitle">
    <strong><xsl:apply-templates/></strong>
  </xsl:template>

  <!--
  ================================================================
  Template to handle QandAEntry sets
  ================================================================ -->
  <xsl:template                  match = "QandAEntry">
   <xsl:element                   name = "li">
    <xsl:attribute                name = "id">
     <xsl:value-of              select = "@id"/>
    </xsl:attribute>

    <xsl:element                  name = "strong">
     <xsl:apply-templates       select = "Question"/>
    </xsl:element>

    <xsl:apply-templates        select = "Answer"/>
   </xsl:element>
  </xsl:template>


  <!--
  ================================================================
  Elements that will by default be marked up for display in italics
  ================================================================ -->
  <xsl:template                  match = "Emphasis | 
                                          ForeignWord |
                                          GeneName | 
                                          ScientificName">
   <xsl:param                     name = "topSection" 
                                select = "'em'"/>
   <xsl:element                   name = "em">
    <xsl:apply-templates>
     <xsl:with-param              name = "topSection"
                                select = "$topSection"/>
    </xsl:apply-templates>
   </xsl:element>
  </xsl:template>

  <!--
  ================================================================
  ================================================================ -->
  <xsl:template                  match = "Strong">
   <xsl:param                     name = "topSection" 
                                select = "'strong'"/>
   <xsl:element                   name = "strong">
    <xsl:apply-templates>
     <xsl:with-param              name = "topSection"
                                select = "$topSection"/>
    </xsl:apply-templates>
   </xsl:element>
  </xsl:template>

  <!--
  ================================================================
  Template to link to the Glossary terms (by language)
  ================================================================ -->
  <xsl:template                  match = "GlossaryTermRef">
   <!-- Specifying the language for the glossary terms -->
   <xsl:variable                  name = "glossLanguage">
    <xsl:choose>
     <xsl:when                    test = "$language = 'en'">
      <xsl:text>English</xsl:text>
     </xsl:when>
     <xsl:when                    test = "$language = 'es'">
      <xsl:text>Spanish</xsl:text>
     </xsl:when>
     <xsl:otherwise>
      <xsl:text>*** undefined ***</xsl:text>
     </xsl:otherwise>
    </xsl:choose>
   </xsl:variable>

   <!-- CAM summaries are using the HP dictionary -->
   <xsl:variable                  name = "glossAudience">
    <xsl:choose>
     <xsl:when                    test = "$sType = 'genetics'">
      <xsl:text>HealthProfessional</xsl:text>
     </xsl:when>
     <xsl:otherwise>
      <xsl:text>Patient</xsl:text>
     </xsl:otherwise>
    </xsl:choose>
   </xsl:variable>

   <xsl:element                   name = "a">
    <xsl:attribute                name = "class">
     <xsl:text>definition</xsl:text>
    </xsl:attribute>
    <xsl:attribute                name = "href">
     <!--
     Next Line For Testing on DEV only !!! 
     ===================================== -->
     <xsl:text>http://www.cancer.gov</xsl:text>
     <xsl:text>/Common/PopUps/popDefinition.aspx?id=</xsl:text>
     <xsl:value-of              select = "number(
                                           substring-after(@href, 'CDR'))"/>
     <xsl:text>&amp;version=</xsl:text>
     <xsl:value-of              select = "$glossAudience"/>
     <xsl:text>&amp;language=</xsl:text>
     <xsl:value-of              select = "$glossLanguage"/>
    </xsl:attribute>
    <xsl:attribute                name = "onclick">
     <xsl:text>javascript:popWindow('defbyid','</xsl:text>
     <xsl:value-of              select = "@href"/>
     <xsl:text>&amp;version=</xsl:text>
     <xsl:value-of              select = "$glossAudience"/>
     <xsl:text>&amp;language=</xsl:text>
     <xsl:value-of              select = "$glossLanguage"/>
     <xsl:text>'); </xsl:text>
     <xsl:text>return(false);</xsl:text>
    </xsl:attribute>
    <xsl:apply-templates/>
   </xsl:element>
  </xsl:template>


  <!--
  ================================================================
  Template to link to the LOE terms (by language)
  LOERefs only exist for HP summaries
  ================================================================ -->
  <xsl:template                  match = "LOERef">
   <!-- Specifying the language for the glossary terms -->
   <xsl:variable                  name = "loeLanguage">
    <xsl:choose>
     <xsl:when                    test = "$language = 'en'">
      <xsl:text>English</xsl:text>
     </xsl:when>
     <xsl:when                    test = "$language = 'es'">
      <xsl:text>Spanish</xsl:text>
     </xsl:when>
     <xsl:otherwise>
      <xsl:text>*** undefined ***</xsl:text>
     </xsl:otherwise>
    </xsl:choose>
   </xsl:variable>

   <xsl:element                   name = "a">
    <xsl:attribute                name = "href">
     <!--
     Next Line For Testing on DEV only !!! 
     ===================================== -->
     <xsl:text>http://www.cancer.gov</xsl:text>
     <xsl:text>/Common/PopUps/popDefinition.aspx?id=</xsl:text>
     <xsl:value-of              select = "number(
                                           substring-after(@href, 'CDR'))"/>
     <xsl:text>&amp;version=HealthProfessional&amp;language=</xsl:text>
     <xsl:value-of              select = "$loeLanguage"/>
    </xsl:attribute>
    <xsl:attribute                name = "onclick">
     <xsl:text>javascript:popWindow('defbyid','</xsl:text>
     <xsl:value-of              select = "@href"/>
     <xsl:text>&amp;version=HealthProfessional&amp;language=</xsl:text>
     <xsl:value-of              select = "$loeLanguage"/>
     <xsl:text>'); </xsl:text>
     <xsl:text>return(false);</xsl:text>
    </xsl:attribute>
    <xsl:apply-templates/>
   </xsl:element>
  </xsl:template>


  <!--
  ================================================================
  Template to link to the Cancer.gov trials information of the 
  protocol
  ================================================================ -->
  <xsl:template                  match = "ProtocolRef">
   <xsl:element                   name = "a">
    <xsl:attribute                name = "href">
     <!--
     Next Line For Testing on DEV only !!! 
     ===================================== -->
     <xsl:text>http://www.cancer.gov</xsl:text>
     <xsl:text>/clinicaltrials/search/view?version=</xsl:text>
     <xsl:value-of              select = "$audience"/>
     <xsl:text>&amp;cdrid=</xsl:text>
     <xsl:value-of              select = "number(
                                           substring-after(@href, 'CDR'))"/>
    </xsl:attribute>
    <xsl:apply-templates/>
   </xsl:element>
  </xsl:template>


  <!--
  ================================================================
  ================================================================ -->
  <xsl:template                  match = "SummaryRef">
   <xsl:element                   name = "a">
    <xsl:attribute                name = "href">
     <!--
     Next Line For Testing on DEV only !!! 
     ===================================== -->
     <xsl:text>http://www.cancer.gov</xsl:text>
     <xsl:value-of              select = "@url"/>
    </xsl:attribute>
    <xsl:apply-templates/>
   </xsl:element>
  </xsl:template>

  <!--
  ================================================================
  ================================================================ -->
  <xsl:template                  match = "ExternalRef">
   <xsl:element                   name = "a">
    <xsl:attribute                name = "href">
     <!--
     Next Line For Testing on DEV only !!! 
     ===================================== -->
     <xsl:value-of              select = "@xref"/>
    </xsl:attribute>
    <xsl:attribute                name = "title">
     <xsl:value-of              select = "@xref"/>
    </xsl:attribute>
    <xsl:apply-templates/>
   </xsl:element>
  </xsl:template>

  <!--
  ================================================================
  ================================================================ -->
  <xsl:template                  match = "MediaLink">
   <xsl:if                        test = "(contains(
                                            concat(' ', @IncludedDevices, ' '), 
                                            concat(' ', $targetedDevice, ' ')
                                            ) 
                                           or 
                                           not(@IncludedDevices)
                                          ) 
                                          and 
                                          (not(contains(
                                            concat(' ', @ExcludedDevices, ' '), 
                                            concat(' ', $targetedDevice, ' ')
                                            )) 
                                           or 
                                           not(@ExcludedDevices)
                                          )">
    <xsl:element                  name = "figure">
     <xsl:attribute               name = "id">
      <xsl:text>figure</xsl:text>
      <xsl:value-of             select = "@id"/>
     </xsl:attribute>
     <!-- Add expandable-container as a hook for the JavaScript enlarge/collapse
          generation -->
     <xsl:attribute               name = "class">
      <xsl:text>image-center</xsl:text>
      <xsl:text> expandable-container</xsl:text>
     </xsl:attribute>


     <!--
     Display the Image
     ============================= -->
     <xsl:element                 name = "img">
      <xsl:attribute              name = "id">
       <xsl:value-of            select = "@id"/>
      </xsl:attribute>
      <xsl:attribute              name = "alt">
       <xsl:value-of            select = "@alt"/>
      </xsl:attribute>
      <xsl:attribute              name = "title">
       <xsl:value-of            select = "@alt"/>
      </xsl:attribute>
      <!--
      <xsl:attribute              name = "border">
       <xsl:value-of            select = "'1'"/>
      </xsl:attribute>
      -->
      <xsl:attribute              name = "src">
       <!--
       Next Line For Testing on DEV only !!! 
       ===================================== -->
       <xsl:text>http://www.cancer.gov</xsl:text>
       <xsl:text>/images/cdr/live/CDR</xsl:text>
       <xsl:value-of            select = "number(
                                            substring-after(@ref, 'CDR'))"/>
       <xsl:choose>
        <xsl:when                 test = "$targetedDevice = 'mobile'">
         <xsl:text>-571.jpg</xsl:text>
        </xsl:when>
        <xsl:otherwise>
         <xsl:text>-750.jpg</xsl:text>
        </xsl:otherwise>
       </xsl:choose>
      </xsl:attribute>
      <!--
      <xsl:attribute               name = "class">
       <xsl:text>cdrMediaImage </xsl:text>
       <xsl:value-of             select = "@size"/>
      </xsl:attribute>
      -->
     </xsl:element>
     <xsl:apply-templates/>
    </xsl:element>
   </xsl:if>
  </xsl:template>


  <!--
  ================================================================
  ================================================================ -->
  <xsl:template                  match = "Caption">
    <xsl:element                 name = "figcaption">
     <xsl:element                 name = "div">
      <xsl:attribute              name = "class">
       <xsl:text>caption-container</xsl:text>
      </xsl:attribute>
 
      <xsl:apply-templates/>
     </xsl:element>
    </xsl:element>
  </xsl:template>


<!-- *************** TABLES ********************************** -->
  <!--
  ================================================================
  Template for Tables
  ================================================================ -->
  <xsl:template                  match = "Table">
   <xsl:param                     name = "topSection" 
                                select = "'table'"/>
   <xsl:if                        test = "(contains(
                                            concat(' ', @IncludedDevices, ' '), 
                                            concat(' ', $targetedDevice, ' ')
                                            ) 
                                           or 
                                           not(@IncludedDevices)
                                          ) 
                                          and 
                                          (not(contains(
                                            concat(' ', @ExcludedDevices, ' '), 
                                            concat(' ', $targetedDevice, ' ')
                                            )) 
                                           or 
                                           not(@ExcludedDevices)
                                          )">

   <!-- Display the Table -->
   <xsl:apply-templates        select = "TGroup">
    <xsl:with-param              name = "topSection"
                               select = "$topSection"/>
   </xsl:apply-templates>
   </xsl:if>
  </xsl:template>

  <!--
  ================================================================
  Template for Table Caption/Title
  ================================================================ -->
  <xsl:template                  match = "Title"
                                  mode = "table">
   <xsl:element                   name = "caption">
    <xsl:apply-templates/>
   </xsl:element>
  </xsl:template>

  <!--
  ================================================================
  Template for colgroup
  ================================================================ -->
  <!--
  <xsl:template                  match = "TGroupXXX">
   <xsl:param                     name = "topSection" 
                                select = "'tgroup'"/>
   <xsl:param  name = "numCols" select="count(child::ColSpec)"/>
   <xsl:element                   name = "colgroup">
    <xsl:for-each               select = "ColSpec">
     <xsl:element                 name = "col">
      <xsl:attribute              name = "width">
       <xsl:value-of            select = "@ColWidth"/>
      </xsl:attribute>
     </xsl:element>
    </xsl:for-each>
   </xsl:element>

   <xsl:apply-templates         select = "THead"/>
   <xsl:apply-templates         select = "TFoot"/>
   <xsl:apply-templates         select = "TBody">
    <xsl:with-param               name = "topSection"
                                select = "$topSection"/>
   </xsl:apply-templates>
  </xsl:template>
  -->

  <!--
  Template for Table Caption/Title
  ================================================================ -->
  <xsl:template                  match = "THead">

   <xsl:element                   name = "thead">
    <xsl:apply-templates        select = "Row">
     <xsl:with-param              name = "type"
                                select = "'header'"/>
    </xsl:apply-templates>
   </xsl:element>
  </xsl:template>

  <!--
  Template for Table Caption/Title
  Unused due to duplicate template
  ================================================================ -->
  <!--
  <xsl:template                  match = "TFootXXX">

   <xsl:element                   name = "tfoot">
    <xsl:apply-templates        select = "Row">
     <xsl:with-param              name = "type"
                                select = "'footer'"/>
    </xsl:apply-templates>
   </xsl:element>
  </xsl:template>
  -->

  <!--
  Template for Table Caption/Title
  Unused due to duplicate template
  ================================================================ -->
  <!--
  <xsl:template                  match = "TBodyXXX">
   <xsl:param                     name = "topSection" 
                                select = "'tbody'"/>
   <xsl:element                   name = "tbody">
    <xsl:apply-templates        select = "Row">
    <xsl:with-param               name = "topSection"
                                select = "$topSection"/>
    </xsl:apply-templates>
   </xsl:element>
  </xsl:template>
  -->

  <!--
  Template for Table Caption/Title
  ================================================================ -->
  <!--
  <xsl:template                  match = "RowXXX">
   <xsl:param                     name = "topSection"
                                select = "'row'"/>
   <xsl:param                     name = "type"/>
   <xsl:param                     name = "numCols" 
                                select = "count(child::entry)"/>
                                
   <xsl:element                   name = "tr">
    <xsl:apply-templates        select = "entry">
     <xsl:with-param              name = "topSection"
                                select = "$topSection"/>
     <xsl:with-param              name = "type"
                                select = "$type"/>
     <xsl:with-param              name = "numCols"
                                select = "$numCols"/>
    </xsl:apply-templates>
   </xsl:element>
  </xsl:template>
  -->

  <!--
  Template for Table Caption/Title
  Unused due to more specific templates .../Row/entry
  ================================================================ -->
  <!--
  <xsl:template                  match = "entryXXX">
   <xsl:param                     name = "topSection"
                                select = "'entry'"/>
   <xsl:param                     name = "type"
                                select = "''"/>
   <xsl:param                     name = "numCols"/>

   <xsl:choose>
    <xsl:when                     test = "$type = 'header'">
     <xsl:element                 name = "th">
      <xsl:attribute              name = "scope">
       <xsl:text>col</xsl:text>
      </xsl:attribute>
      <xsl:apply-templates/>
     </xsl:element>
    </xsl:when>
    <xsl:when                     test = "$type = 'footer'">
     <xsl:element                 name = "td">
      <xsl:if                     test = "$numCols = '1'
                                          and
                                          ../../../@Cols > $numCols">
       <xsl:attribute             name = "colspan">
        <xsl:value-of           select = "../../../@Cols"/>
       </xsl:attribute>
      </xsl:if>
      <xsl:apply-templates/>
     </xsl:element>
    </xsl:when>
    <xsl:otherwise>
     <xsl:element                 name = "td">
      <xsl:apply-templates>
       <xsl:with-param            name = "topSection"
                                select = "$topSection"/>
      </xsl:apply-templates>
     </xsl:element>
    </xsl:otherwise>
   </xsl:choose>
  </xsl:template>
  -->


  <!--
  Template for super script
  (The superscript causes problems in Chrome. It displays all 
  following anchor tags as subscripts)
  ================================================================
  <xsl:template                  match = "Superscript">
   <xsl:element                   name = "sup">
    <xsl:apply-templates/>
   </xsl:element>
  </xsl:template>
  -->

  <!--
  Template as a workaround for the Chrome superscript issue
  ================================================================ -->
  <xsl:template                  match = "Superscript">
   <xsl:element                   name = "span">
    <xsl:attribute                name = "class">
     <xsl:text>sup</xsl:text>
    </xsl:attribute>
    <xsl:apply-templates/>
   </xsl:element>
  </xsl:template>


  <!--
  ================================================================ -->
  <xsl:template                  match = "Subscript">
   <xsl:element                   name = "sub">
    <xsl:apply-templates/>
   </xsl:element>
  </xsl:template>



<!--
========================================================================
    NAMED TEMPLATES
======================================================================== -->
  <!--
  ================================================================
  Template to create the Keypoint box - this could be created with
  JS but it's difficult to set ids for KeyPoint containers when
  multiple KP boxes exist on one page (i.e. 'View entire document')
  ================================================================ -->
  <xsl:template                   name = "keypointsbox">
   <xsl:if                        test = "descendant::KeyPoint">
    <xsl:element                  name = "div">
     <xsl:attribute               name = "class">
      <xsl:text>keyPoints</xsl:text>
     </xsl:attribute>

     <!--
     KeyPoint box header
     ==================== -->
     <xsl:element                 name = "h3">
      <xsl:attribute              name = "id">
       <xsl:value-of            select = "@id"/>
       <xsl:text>_kpBoxHdr</xsl:text>
      </xsl:attribute>
      <xsl:choose>
       <xsl:when                  test = "$language = 'en'">
        <xsl:text>Key Points for This Section</xsl:text>
       </xsl:when>
       <xsl:when                  test = "$language = 'es'">
        <xsl:text>Puntos importantes de esta secci&#243;n</xsl:text>
       </xsl:when>
       <xsl:otherwise>
        <xsl:text>*** language not defined ***</xsl:text>
       </xsl:otherwise>
      </xsl:choose>
     </xsl:element>

     <!--
     KeyPoint box container
     ====================== -->
     <xsl:element                 name = "div">
      <xsl:attribute              name = "id">
       <xsl:text>_kp_section</xsl:text>
       <xsl:value-of            select = "./@id"/>
       <xsl:text>_</xsl:text>
       <xsl:value-of            select = "count(
                                            preceding-sibling::SummarySection) 
                                                                         + 1"/>
      </xsl:attribute>

      <!-- 
      Creating the nested list containing the key point links
      ======================================================= -->
      <xsl:element                name = "ul">
       <xsl:call-template         name = "createKeyPointBox"/>
      </xsl:element>
     </xsl:element>
    </xsl:element>
   </xsl:if>
  </xsl:template>


  <!--
  ================================================================
  Template to create the individual LI elements.
  If Sub-sections with key points exist create another UL
  ================================================================ -->
  <xsl:template                   name = "createKeyPointBox">
   <xsl:for-each                select = "SummarySection">
    <xsl:element                  name = "li">
     <xsl:apply-templates       select = "KeyPoint"
                                  mode = "kpBox"/>

     <!--
     Nested Keypoint list
     ==================== -->
     <xsl:if                      test = "SummarySection/KeyPoint">
      <xsl:element                name = "ul">
       <xsl:call-template         name = "createKeyPointBox"/>
      </xsl:element>
     </xsl:if>

    </xsl:element>
   </xsl:for-each>
  </xsl:template>


  <!--
  ================================================================
  Template to add the anchor tag to each key point.
  ================================================================ -->
  <xsl:template                  match = "KeyPoint"
                                  mode = "kpBox">
   <xsl:element                   name = "a">
    <xsl:attribute                name = "href">
     <xsl:text>#</xsl:text>
     <xsl:value-of              select = "@id"/>
    </xsl:attribute>
    <xsl:value-of               select = "."/>
   </xsl:element>
  </xsl:template>


  <!--
  ================================================================
  Template to create the Keypoint box (created with JavaScript)
  ================================================================ -->
  <xsl:template                   name = "keypointsboxJS">
   <xsl:if                        test = "descendant::KeyPoint">
   <xsl:element                   name = "div">
    <xsl:attribute                name = "class">
     <xsl:text>keyPoints</xsl:text>
    </xsl:attribute>

    <xsl:element                  name = "h3">
     <xsl:choose>
      <xsl:when                   test = "$language = 'en'">
       <xsl:text>Key Points for This Section (JS)</xsl:text>
      </xsl:when>
      <xsl:when                   test = "$language = 'es'">
       <xsl:text>Puntos importantes de esta secci&#243;n</xsl:text>
      </xsl:when>
      <xsl:otherwise>
       <xsl:text>*** language not defined ***</xsl:text>
      </xsl:otherwise>
     </xsl:choose>
    </xsl:element>
     <xsl:element                 name = "div">
      <xsl:attribute              name = "id">
       <xsl:text>_toc_section</xsl:text>
      <xsl:value-of             select = "./@id"/>
      <xsl:text>_</xsl:text>
       <xsl:value-of             select = "count(
                                          preceding-sibling::SummarySection) + 1"/>
      </xsl:attribute>
     </xsl:element>
   </xsl:element>
   </xsl:if>
  </xsl:template>


<!--
========================================================================
    Template for CALS to HTML Conversion 
    (code adapted from 
    http://www.biglist.com/lists/xsl-list/archives/200202/msg00666.html)
======================================================================== -->
<!--
Template for Creating a table (from CALS)
============================================================== -->
<xsl:template                    match = "TGroup">
   <xsl:param                     name = "topSection" 
                                select = "'tgroup'"/>
   <xsl:element                   name = "table">
    <xsl:attribute                name = "id">
     <xsl:value-of              select = "../@id"/>
    </xsl:attribute>
    <xsl:attribute                name = "class">
     <xsl:text>table-default</xsl:text>
     <xsl:text> expandable-container</xsl:text>
    </xsl:attribute>

    <xsl:if test="@PgWide=1">
      <xsl:attribute name="width">100%</xsl:attribute>
    </xsl:if>
    <xsl:if test="TGroup/@Align">
      <xsl:attribute name="align">
        <xsl:value-of select="TGroup/@Align"/>
      </xsl:attribute>
    </xsl:if>
      <!-- Should be coming from CSS 
    <xsl:choose>
      <xsl:when test="@Frame='TOPBOT'">
        <xsl:attribute name="style">border-top:thin solid black; border-bottom:thin solid black;</xsl:attribute>
      </xsl:when>
      -->
      <!-- Should be coming from CSS 
      <xsl:when test="@Frame='None'">
        <xsl:attribute name="border">0</xsl:attribute>
      </xsl:when>
      -->
      <!-- Should be coming from CSS 
      <xsl:otherwise>
        <xsl:attribute name="border">0</xsl:attribute>
      </xsl:otherwise>
    </xsl:choose>
      -->

    <xsl:variable name="colgroup">
      <colgroup>
        <xsl:call-template name="generate.colgroup">
          <xsl:with-param name="cols" select="@Cols"/>
        </xsl:call-template>
      </colgroup>
    </xsl:variable>

    <xsl:variable name="table.width">
      <xsl:choose>
        <xsl:when test="$default.table.width = ''">
          <xsl:text>100%</xsl:text>
        </xsl:when>
        <xsl:otherwise>
          <xsl:value-of select="$default.table.width"/>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:variable>

    <!-- Remove attribute for Table width; coming from class
    <xsl:attribute name="width">
       <xsl:value-of select="$table.width"/>
    </xsl:attribute>
    -->


    <xsl:apply-templates        select = "../Title"
                                  mode = "table"/>


    <xsl:copy-of select="$colgroup"/>

      <xsl:apply-templates>
       <xsl:with-param            name = "topSection"
                                select = "$topSection"/>
      </xsl:apply-templates>

   </xsl:element>
</xsl:template>

<xsl:template                    match = "ColSpec"></xsl:template>

<xsl:template                    match = "SpanSpec"></xsl:template>

<!-- 
=====================================================================
===================================================================== -->
<xsl:template                    match = "THead | TFoot">
   <xsl:param                     name = "topSection" 
                                select = "'tbody'"/>
  <xsl:element                    name = "{name(.)}">
    <!-- Only display Align attribute if it's not center. Coming from CSS -->
    <xsl:if                       test = "@Align">
      <xsl:choose>
       <xsl:when                  test = "not(@Align = 'Center')">
        <xsl:attribute            name = "align">
          <xsl:value-of         select = "@Align"/>
        </xsl:attribute>
       </xsl:when>
      </xsl:choose>
    </xsl:if>
    <xsl:if                       test = "@Char">
      <xsl:attribute              name = "char">
        <xsl:value-of           select = "@Char"/>
      </xsl:attribute>
    </xsl:if>
    <xsl:if                       test = "@Charoff">
      <xsl:attribute              name = "charoff">
        <xsl:value-of           select = "@Charoff"/>
      </xsl:attribute>
    </xsl:if>
    <xsl:if                       test = "@Valign">
      <xsl:attribute              name = "valign">
        <xsl:value-of           select = "@Valign"/>
      </xsl:attribute>
    </xsl:if>
    <xsl:if                       test = "name(.) = 'TFoot'">
     <xsl:attribute               name = "class">
      <xsl:text>pdq-footer</xsl:text>
     </xsl:attribute>
    </xsl:if>

    <xsl:apply-templates>
     <xsl:with-param              name = "topSection"
                                select = "$topSection"/>
    </xsl:apply-templates>
  </xsl:element>
</xsl:template>


<!-- 
=====================================================================
===================================================================== -->
<xsl:template                    match = "TBody">
   <xsl:param                     name = "topSection" 
                                select = "'tbody'"/>
  <tbody>
    <xsl:if test="@Align">
      <xsl:attribute name="align">
        <xsl:value-of select="@Align"/>
      </xsl:attribute>
    </xsl:if>
    <xsl:if test="@Char">
      <xsl:attribute name="char">
        <xsl:value-of select="@Char"/>
      </xsl:attribute>
    </xsl:if>
    <xsl:if test="@Charoff">
      <xsl:attribute name="charoff">
        <xsl:value-of select="@Charoff"/>
      </xsl:attribute>
    </xsl:if>
    <xsl:if test="@Valign">
      <xsl:attribute name="valign">
        <xsl:value-of select="@Valign"/>
      </xsl:attribute>
    </xsl:if>

      <xsl:apply-templates>
       <xsl:with-param            name = "topSection"
                                select = "$topSection"/>
      </xsl:apply-templates>
  </tbody>
</xsl:template>

  <!--
  =======================================================================
  Creating Table Rows
  ======================================================================= -->
<xsl:template                    match = "Row">
  <xsl:param                      name = "topSection" 
                                select = "'trow'"/>
  <tr>
    <xsl:if                       test = "@Align">
      <xsl:attribute              name = "align">
        <xsl:value-of           select = "@Align"/>
      </xsl:attribute>
    </xsl:if>
    <xsl:if                       test = "@Char">
      <xsl:attribute              name = "char">
        <xsl:value-of           select = "@Char"/>
      </xsl:attribute>
    </xsl:if>
    <xsl:if                       test = "@Charoff">
      <xsl:attribute              name = "charoff">
        <xsl:value-of           select = "@Charoff"/>
      </xsl:attribute>
    </xsl:if>
    <xsl:if                       test = "@Valign">
      <xsl:attribute              name = "valign">
        <xsl:value-of           select = "@Valign"/>
      </xsl:attribute>
    </xsl:if>

    <xsl:apply-templates>
      <xsl:with-param             name = "topSection" 
                                select = "$topSection"/>
    </xsl:apply-templates>
  </tr>
</xsl:template>

<!--
=========================================================================
========================================================================= -->
<xsl:template                    match = "THead/Row/entry">
   <xsl:param                     name = "topSection" 
                                select = "'thcell'"/>

  <xsl:call-template              name = "process.cell">
    <xsl:with-param               name = "topSection" 
                                select = "$topSection"/>
    <xsl:with-param               name = "cellgi">
      <xsl:text>th</xsl:text>
    </xsl:with-param>
  </xsl:call-template>

</xsl:template>

  <!--
  =======================================================================
  ======================================================================= -->
<xsl:template                    match = "TBody/Row/entry">
  <xsl:param                     name  = "topSection" 
                                select = "'tbcell'"/>

  <xsl:call-template              name = "process.cell">
     <xsl:with-param              name = "topSection" 
                                select = "$topSection"/>
    <xsl:with-param               name = "cellgi">
      <xsl:text>td</xsl:text>
    </xsl:with-param>
  </xsl:call-template>
</xsl:template>


<!--
=========================================================================
========================================================================= -->
<xsl:template                    match = "TFoot/Row/entry">
  <xsl:param                      name = "topSection" 
                                select = "'tfcell'"/>
  <xsl:call-template              name = "process.cell">
    <xsl:with-param               name = "topSection" 
                                select = "$topSection"/>
    <xsl:with-param               name = "cellgi">
      <xsl:text>td</xsl:text>
    </xsl:with-param>
  </xsl:call-template>
</xsl:template>

  <!--
  =======================================================================
  This is processing the table cells.  Is passed from the 'entry'
  template to identify if the processing is for body/header/footer
  entries
  ======================================================================= -->
<xsl:template                     name = "process.cell">
 <xsl:param                       name = "topSection" 
                                select = "'cell'"/>
 <xsl:param                       name = "cellgi">td</xsl:param>


  <xsl:variable                   name = "empty.cell" 
                                select = "count(node()) = 0"/>

  <xsl:variable                   name="entry.colnum">
    <xsl:call-template            name="entry.colnum"/>
  </xsl:variable>

  <!--
  X<xsl:value-of select = "$empty.cell"/>_
   <xsl:value-of select = "$entry.colnum"/>X
  -->

  <!--
  If there aren't enough cells for a row CALS assumes the missing
  cells for the row need to be empty.
  However, this code doesn't check if a previous row accounts for
  the missing cells
  =============================================================== -->
  <!--
  <xsl:if                         test = "$entry.colnum != ''">
  XXX
    <xsl:variable                 name = "prev.entry" 
                                select = "preceding-sibling::*[1]"/>
    <xsl:variable                 name = "prev.ending.colnum">
      <xsl:choose>
        <xsl:when                 test = "$prev.entry">
          <xsl:call-template      name = "entry.ending.colnum">
            <xsl:with-param       name = "entry" 
                                select = "$prev.entry"/>
          </xsl:call-template>
        </xsl:when>
        <xsl:otherwise>0</xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    -->
    <!--
    Removed the call to this template since it's creating empty table cells
    on rows following a row with a rowspan
    I'm not certain if the entire if-block could be dropped.
    =======================================================================
    <xsl:call-template            name = "add-empty-entries">
      <xsl:with-param             name = "number">
        <xsl:choose>
          <xsl:when               test = "$prev.ending.colnum = ''">0</xsl:when>
          <xsl:otherwise>
            <xsl:value-of       select = "$entry.colnum - $prev.ending.colnum - 1"/>
          </xsl:otherwise>
        </xsl:choose>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:if>
    -->

  <xsl:element                    name = "{$cellgi}">

  <xsl:if test="@SpanName">
  	<xsl:variable name="namest"
select="ancestor::TGroup/SpanSpec[@SpanName=./@SpanName]/@NameSt"/>
	<xsl:variable name="nameend"
select="ancestor::TGroup/SpanSpec[@SpanName=./@SpanName]/@NameEnd"/>
	<xsl:variable name="colst"
select="ancestor::*[ColSpec/@ColName=$namest]/ColSpec[@ColName=$namest]/@ColNum"/>
	<xsl:variable name="colend"
select="ancestor::*[ColSpec/@ColName=$nameend]/ColSpec[@ColName=$nameend]/@ColNum"/>
	<xsl:attribute              name = "colspan">
      <xsl:value-of           select = "number($colend) - number($colst) + 1"/>
    </xsl:attribute>
  </xsl:if>

    <!-- Setting the rowspan for the current row -->
    <xsl:if test="@MoreRows">
      <xsl:attribute name="rowspan">
        <xsl:value-of select="@MoreRows+1"/>
      </xsl:attribute>
    </xsl:if>

    <!-- Setting the colspan -->
    <xsl:if test="@NameSt">
      <xsl:attribute name="colspan">
        <xsl:call-template name="calculate.colspan"/>
      </xsl:attribute>
    </xsl:if>

    <xsl:if                       test = "@Align">
      <xsl:choose>
       <xsl:when                  test = "not(@Align = 'Center')">
        <xsl:attribute              name = "align">
          <xsl:value-of           select = "@Align"/>
        </xsl:attribute>
       </xsl:when>
      </xsl:choose>
      <xsl:attribute name="scope">
        <xsl:value-of select="'col'"/>
      </xsl:attribute>
    </xsl:if>
    <xsl:if test="@Char">
      <xsl:attribute name="char">
        <xsl:value-of select="@Char"/>
      </xsl:attribute>
    </xsl:if>
    <xsl:if test="@Charoff">
      <xsl:attribute name="charoff">
        <xsl:value-of select="@Charoff"/>
      </xsl:attribute>
    </xsl:if>
    <xsl:if test="@Valign">
      <xsl:attribute name="valign">
        <xsl:value-of select="@Valign"/>
      </xsl:attribute>
    </xsl:if>

    <!--
	<xsl:if test="@RowSep='1'">
		<xsl:attribute name="style">border-bottom:thin solid black</xsl:attribute>
	</xsl:if>
    -->

    <xsl:if test="not(preceding-sibling::*)
                  and ancestor::Row/@id">
      <a name="{ancestor::Row/@id}"/>
    </xsl:if>

    <xsl:if test="@id">
      <a name="{@id}"/>
    </xsl:if>

    <!-- Process Cell Content (entry element) -->
    <xsl:choose>
      <xsl:when test="$empty.cell">
        <xsl:text>&#160;</xsl:text>
      </xsl:when>
      <xsl:otherwise>
        <xsl:apply-templates>
         <xsl:with-param name = "topSection" select = "$topSection"/>
        </xsl:apply-templates>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:element>
</xsl:template>

<!--
=========================================================================
========================================================================= -->
<xsl:template                     name = "add-empty-entries">
  <xsl:param                      name = "number" 
                                select = "'0'"/>
  <xsl:value-of select = "$number"/>
  <xsl:choose>
    <xsl:when                     test = "$number &lt;= 0">
    </xsl:when>
    <xsl:otherwise>
      <td>&#160;X</td>
      <xsl:call-template          name = "add-empty-entries">
        <xsl:with-param           name = "number" 
                                select = "$number - 1"/>
      </xsl:call-template>
    </xsl:otherwise>
  </xsl:choose>
</xsl:template>


<!--
=========================================================================
========================================================================= -->
<xsl:template                     name = "entry.colnum">
  <xsl:param                      name = "entry" 
                                select = "."/>

  <xsl:choose>
    <xsl:when                     test = "$entry/@ColName">
      <xsl:variable               name = "colname" 
                                select = "$entry/@ColName"/>
      <xsl:variable               name = "colspec"
                                select = "$entry/ancestor::TGroup
                                              /ColSpec[@ColName=$colname]"/>
      <xsl:call-template          name = "colspec.colnum">
        <xsl:with-param           name = "colspec" 
                                select = "$colspec"/>
      </xsl:call-template>
    </xsl:when>
    <xsl:when                     test = "$entry/@NameSt">
      <xsl:variable               name = "namest" 
                                select = "$entry/@NameSt"/>
      <xsl:variable               name = "colspec"
                                select = "$entry/ancestor::TGroup
                                              /ColSpec[@ColName=$namest]"/>
      <xsl:call-template          name = "colspec.colnum">
        <xsl:with-param           name = "colspec" 
                                select = "$colspec"/>
      </xsl:call-template>
    </xsl:when>
    <xsl:when                     test = "count($entry/preceding-sibling::*) = 0">1</xsl:when>
    <xsl:otherwise>
      <xsl:variable               name = "pcol">
        <xsl:call-template        name = "entry.ending.colnum">
          <xsl:with-param         name = "entry"
                                select = "$entry/preceding-sibling::*[1]"/>
        </xsl:call-template>
      </xsl:variable>
      <xsl:value-of             select = "$pcol + 1"/>
    </xsl:otherwise>
  </xsl:choose>
</xsl:template>


<!--
=========================================================================
========================================================================= -->
<xsl:template                     name = "entry.ending.colnum">
  <xsl:param name="entry" select="."/>

  <xsl:choose>
    <xsl:when test="$entry/@ColName">
      <xsl:variable name="colname" select="$entry/@ColName"/>
      <xsl:variable name="colspec"
select="$entry/ancestor::TGroup/ColSpec[@ColName=$colname]"/>
      <xsl:call-template name="colspec.colnum">
        <xsl:with-param name="colspec" select="$colspec"/>
      </xsl:call-template>
    </xsl:when>
    <xsl:when test="$entry/@NameEnd">
      <xsl:variable name="nameend" select="$entry/@NameEnd"/>
      <xsl:variable name="colspec"
select="$entry/ancestor::TGroup/ColSpec[@ColName=$nameend]"/>
      <xsl:call-template name="colspec.colnum">
        <xsl:with-param name="colspec" select="$colspec"/>
      </xsl:call-template>
    </xsl:when>
    <xsl:when test="count($entry/preceding-sibling::*) = 0">1</xsl:when>
    <xsl:otherwise>
      <xsl:variable name="pcol">
        <xsl:call-template name="entry.ending.colnum">
          <xsl:with-param name="entry"
select="$entry/preceding-sibling::*[1]"/>
        </xsl:call-template>
      </xsl:variable>
      <xsl:value-of select="$pcol + 1"/>
    </xsl:otherwise>
  </xsl:choose>
</xsl:template>


<!--
=========================================================================
========================================================================= -->
<xsl:template                     name = "colspec.colnum">
  <xsl:param name="colspec" select="."/>
  <xsl:choose>
    <xsl:when test="$colspec/@ColNum">
      <xsl:value-of select="$colspec/@ColNum"/>
    </xsl:when>
    <xsl:when test="$colspec/preceding-sibling::ColSpec">
      <xsl:variable name="prec.colspec.colnum">
        <xsl:call-template name="colspec.colnum">
          <xsl:with-param name="colspec"
                          select="$colspec/preceding-sibling::ColSpec[1]"/>
        </xsl:call-template>
      </xsl:variable>
      <xsl:value-of select="$prec.colspec.colnum + 1"/>
    </xsl:when>
    <xsl:otherwise>1</xsl:otherwise>
  </xsl:choose>
</xsl:template>

<!--
=========================================================================
========================================================================= -->
<xsl:template                     name = "generate.colgroup">
  <xsl:param name="cols" select="1"/>
  <xsl:param name="count" select="1"/>
  <xsl:choose>
    <xsl:when test="$count>$cols"></xsl:when>
    <xsl:otherwise>
      <xsl:call-template name="generate.col">
        <xsl:with-param name="countcol" select="$count"/>
      </xsl:call-template>
      <xsl:call-template name="generate.colgroup">
        <xsl:with-param name="cols" select="$cols"/>
        <xsl:with-param name="count" select="$count+1"/>
      </xsl:call-template>
    </xsl:otherwise>
  </xsl:choose>
</xsl:template>

<!--
=========================================================================
========================================================================= -->
<xsl:template                     name = "generate.col">
  <xsl:param name="countcol">1</xsl:param>
  <xsl:param name="colspecs" select="./ColSpec"/>
  <xsl:param name="count">1</xsl:param>
  <xsl:param name="colnum">1</xsl:param>

  <xsl:choose>
    <xsl:when test="$count>count($colspecs)">
      <col/>
    </xsl:when>
    <xsl:otherwise>
      <xsl:variable name="colspec" select="$colspecs[$count=position()]"/>
      <xsl:variable name="colspec.colnum">
        <xsl:choose>
          <xsl:when test="$colspec/@ColNum">
            <xsl:value-of select="$colspec/@ColNum"/>
          </xsl:when>
          <xsl:otherwise>
            <xsl:value-of select="$colnum"/>
          </xsl:otherwise>
        </xsl:choose>
      </xsl:variable>

      <xsl:choose>
        <xsl:when test="$colspec.colnum=$countcol">
          <col>
            <xsl:if test="$colspec/@Align">
              <xsl:attribute name="align">
                <xsl:value-of select="$colspec/@Align"/>
              </xsl:attribute>
            </xsl:if>
            <xsl:if test="$colspec/@Char">
              <xsl:attribute name="char">
                <xsl:value-of select="$colspec/@Char"/>
              </xsl:attribute>
            </xsl:if>
            <xsl:if test="$colspec/@Charoff">
              <xsl:attribute name="charoff">
                <xsl:value-of select="$colspec/@Charoff"/>
              </xsl:attribute>
            </xsl:if>
            <!-- VE start -->
            <xsl:if test="$colspec/@ColWidth">
              <xsl:attribute name="width">
                <xsl:value-of select="$colspec/@ColWidth"/>
              </xsl:attribute>
            </xsl:if>
            <!-- VE end  -->
          </col>
        </xsl:when>
        <xsl:otherwise>
          <xsl:call-template name="generate.col">
            <xsl:with-param name="countcol" select="$countcol"/>
            <xsl:with-param name="colspecs" select="$colspecs"/>
            <xsl:with-param name="count" select="$count+1"/>
            <xsl:with-param name="colnum">
              <xsl:choose>
                <xsl:when test="$colspec/@ColNum">
                  <xsl:value-of select="$colspec/@ColNum + 1"/>
                </xsl:when>
                <xsl:otherwise>
                  <xsl:value-of select="$colnum + 1"/>
                </xsl:otherwise>
              </xsl:choose>
            </xsl:with-param>
           </xsl:call-template>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:otherwise>
  </xsl:choose>

</xsl:template>

<!--
=========================================================================
========================================================================= -->
<xsl:template                     name = "colspec.colwidth">
  <!-- when this macro is called, the current context must be an entry -->
  <xsl:param name="colname"></xsl:param>
  <!-- .. = Row, ../.. = THead|TBody, ../../.. = TGroup -->
  <xsl:param name="colspecs" select="../../../../TGroup/ColSpec"/>
  <xsl:param name="count">1</xsl:param>
  <xsl:choose>
    <xsl:when test="$count>count($colspecs)"></xsl:when>
    <xsl:otherwise>
      <xsl:variable name="colspec" select="$colspecs[$count=position()]"/>
      <xsl:choose>
        <xsl:when test="$colspec/@ColName=$colname">
          <xsl:value-of select="$colspec/@ColWidth"/>
        </xsl:when>
        <xsl:otherwise>
          <xsl:call-template name="colspec.colwidth">
            <xsl:with-param name="colname" select="$colname"/>
            <xsl:with-param name="colspecs" select="$colspecs"/>
            <xsl:with-param name="count" select="$count+1"/>
          </xsl:call-template>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:otherwise>
  </xsl:choose>
</xsl:template>

<!--
=========================================================================
========================================================================= -->
<xsl:template                     name = "calculate.colspan">
 <xsl:param name="entry" select="."/>
 <xsl:variable name="namest" select="$entry/@NameSt"/>
 <xsl:variable name="nameend" select="$entry/@NameEnd"/>

 <xsl:variable name="scol">
    <xsl:call-template name="colspec.colnum">
      <xsl:with-param name="colspec"
select="$entry/ancestor::TGroup/ColSpec[@ColName=$namest]"/>
    </xsl:call-template>
  </xsl:variable>
  <xsl:variable name="ecol">
    <xsl:call-template name="colspec.colnum">
      <xsl:with-param name="colspec"
select="$entry/ancestor::TGroup/ColSpec[@ColName=$nameend]"/>
    </xsl:call-template>
  </xsl:variable>
 <xsl:value-of select="$ecol - $scol + 1"/>
</xsl:template>

</xsl:stylesheet>
