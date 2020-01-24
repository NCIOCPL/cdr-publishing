# CDR Publishing

The CDR Publishing repository has the following sets of files

## Publishing Software

The `Publishing` directory contains
 * Python scripts invoked by the publishing system by the CDR Scheduler (see the `cdr-scheduler` repository) for processing queued publishing jobs.
 * Publishing-control XML documents for the three categories of publishing jobs (`Primary`, to export documents, `Mailers`, for soliciting external review of documents, and `QcFilterSets`, to control how documents are filtered for internal review.
 * A script for populating a new instance of the Drupal CMS with PDQ content published by the CDR.

## PDQ Data Partners

The `Licensee` directory contains the DTDs used to validate documents exported to PDQ data partners (including the NCI web site).
The `pdqdocs` directory contains documentation provided to the PDQ data partners describing the structure of the PDQ data and offering guidelines for processing that data.

## Mailers

The `Mailers` directory contains the Python software used to send PDQ documents to external reviewers.
