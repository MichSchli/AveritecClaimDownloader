import sys
from urllib.parse import urlparse
import argparse
import waybackpy
import time
from datetime import datetime, timedelta


# This python file is used to archive the websites used as the evidence. 
archive_sites = [
    "archive.org",
    "archive.is",
    "archive.fo",
    "perma.cc",
    "archive.md"
]

blocked_sites = [
    "snopes.com"
]

def should_exclude(url):
    domain = urlparse(url).netloc

    if domain.startswith("www."):
        domain = domain[4:]

    return domain in archive_sites or domain in blocked_sites

def cache_in_archive(url):
    user_agent = "Averitec dataset builder // contact: mss84@cam.ac.uk"

    if should_exclude(url):
        return url

    wayback = waybackpy.Url(url, user_agent)

    # Test if the domain is blocked
    try:
        n_archived = wayback.total_archives()
    except:
        return url

    # Take either newest archive, or save an archive if none exists:
    if n_archived > 0:
        try:
            archive = wayback.newest()
            print("I found an existing saved archival page for " + url + "! Checking the timestamp...", file=sys.stderr)

            time_between_archival = datetime.now() - archive.timestamp
            if time_between_archival < timedelta(days=7):
                print("Page is less than a week old. Keeping it!")
            else:
                print("Page is too old. Rebuilding...")
                for i in range(5):
                    try:
                        archive = wayback.save()
                        break
                    except:
                        print(
                            "I couldn't reach the archive to build a page for " + url + ". Trying again in 3 seconds.",
                            file=sys.stderr)
                        time.sleep(3)
                        archive = None
        except:
            print("I failed to retrieve a saved archival page for " + url + ". Building a new page.", file=sys.stderr)

            for i in range(5):
                try:
                    archive = wayback.save()
                    break
                except:
                    print("I couldn't reach the archive to build a page for " + url + ". Trying again in 3 seconds.",
                          file=sys.stderr)
                    time.sleep(3)
                    archive = None
    else:
        print("I found no saved page for " + url + ". Building a new page.", file=sys.stderr)
        for i in range(5):
            try:
                archive = wayback.save()
                break
            except:
                print("I couldn't reach the archive to build a page for " + url + ". Trying again in 3 seconds.",
                      file=sys.stderr)
                time.sleep(3)
                archive = None

    if archive is not None:
        return archive.archive_url
    else:
        return None