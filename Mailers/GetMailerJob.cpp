/*
 * $Id$
 *
 * Fetches print files for CDR mailer job, and saves the compressed
 * archive as PrintFilesForJob<JOB>.tar.bz2 in the current working
 * directory.
 *
 * Usage:
 *  GetMailerJob host job
 *
 * Example:
 *  GetMailerJob bach.nci.nih.gov 1177
 *
 * To compile/link (VS2003):
 *  cl /EHa /DWINVER=0x0501 /MD /D_AFXDLL=1 GetMailerJob.cpp /link /OPT:NOREF
 */

// System headers.
#include <iostream>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <afxinet.h>

int main(int ac, char** av)
{
    // Tell the user how to invoke the program.
    if (ac != 3) {
        std::cerr << "usage: GetMailerJob host job\n";
        std::cerr << " e.g.: GetMailerJob bach.nci.nih.gov 1177\n";
        exit(EXIT_FAILURE);
    }

    // Connect to the web server.
    CInternetSession session;
    CHttpConnection* conn = NULL;
    try {
        conn = session.GetHttpConnection(av[1], 0, 80);
    }
    catch (...) {
        std::cerr << "Unable to connect to " << av[1] << "\n";
        exit(EXIT_FAILURE);
    }

    // Ask for the print files for the mailer job.
    char request[256];
    sprintf(request, "/cgi-bin/cdr/GetMailerPrintFiles.py?job=%s", av[2]);
    CHttpFile* file = conn->OpenRequest("GET", request);
    file->SendRequest();

    // If the request succeeded, loop through the bytes and save them.
    DWORD rc;
    file->QueryInfoStatusCode(rc);
    if (rc == HTTP_STATUS_OK) {
        char name[256];
        sprintf(name, "PrintFilesForJob%s.tar.bz2", av[2]);
        FILE* fp = fopen(name, "wb");
        if (!fp) {
            std::cerr << "Unable to write to " << name << "\n";
            exit(EXIT_FAILURE);
        }
        char buf[1024];
        UINT n = file->Read(buf, sizeof(buf));
        while (n > 0) {
            fwrite(buf, n, 1, fp);
            n = file->Read(buf, sizeof(buf));
        }
        fclose(fp);
        return EXIT_SUCCESS;
    }

    // Report failure.
    std::cerr << "HTTP failure code: " << rc << "\n";
    return EXIT_FAILURE;
}
