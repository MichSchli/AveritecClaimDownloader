# See how Google's Fact Check Tools API works
# See https://developers.google.com/fact-check/tools/api/reference/rest/v1alpha1/claims for data structure etc.
import json
import requests
import hashlib
import pprint
import time
import tqdm

API_KEY = "YOU_API_KEY" # Instructions https://support.google.com/googleapi/answer/6158862
URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"


def find_publishers(query: str, max_age=30) -> set:
    """Get list of all publishers (e.g. fact checking organizations) that have
    published claims matching the given query in the last *max_age* days.
    """

    data = {
        "query": query,
        "maxAgeDays": max_age,
        "pageSize": 25,
        "languageCode": "en",
        "key": API_KEY,  # NB: API key is passed into params, not headers or auth or anywhere else
    }

    #r = requests.get(URL, params=data)

    #print(r)
    #exit()

    #rj = r.json()

    rj = query_api(URL, data)

    publishers = set()
    finished = False
    claims = rj.get("claims", [])
    if claims is None or len(claims) == 0:
        finished = True
    while finished is False:
        next_page = rj.get("nextPageToken")
        for c in claims:
            claim_review = c.get("claimReview")[0]
            site = claim_review.get("publisher").get("site")
            publishers.add(site)
        if next_page is None:
            finished = True
        else:
            # Getting next page
            data["pageToken"] = next_page
            #r = requests.get(URL, params=data)
            #rj = r.json()
            rj = query_api(URL, data)
            claims = rj.get("claims")
            if claims is None or len(claims) == 0:
                print("No more claims!")
                finished = True

    return publishers


def find_many_publishers(max_age=360):
    all_pubs = set()
    for query in tqdm.tqdm([
        "vaccine",
        "congress",
        "covid",
        "climate",
        "facebook",
        "twitter",
        "candidate",
        "statement",
        "quote",
        "true",
        "false",
        "misleading",
        "right",
        "wrong",
        "claim",
        "journalist",
        "tweet",
        "post"
    ], desc="Querying API for publishers using specified keywords"):
        pubs = find_publishers(query, max_age=max_age)
        all_pubs.update(pubs)
        print(f"After query '{query}', we have {len(all_pubs)} publishers in total")
    return all_pubs

def query_api(url, data):
    r = requests.get(url, params=data)
    rj = r.json()

    sleep_time = 1

    while "error" in rj and rj["error"]["code"] == 503:
        print("Service unavailable. Trying again in " + str(sleep_time) + " sec.")
        time.sleep(sleep_time)
        r = requests.get(url, params=data)
        rj = r.json()
        sleep_time *= 2

    return rj


def get_publisher_sightings(publisher_site="fullfact.org", max_age=30):
    """Get all fact checks from a single publisher up to *max_age* days old."""
    data = {
        "maxAgeDays": max_age,
        "pageSize": 25,
        "languageCode": "en",
        "reviewPublisherSiteFilter": publisher_site,
        "key": API_KEY,  # NB: API key is passed into params, not headers or auth or anywhere else
    }

    #r = requests.get(URL, params=data)
    #rj = r.json()

    rj = query_api(URL, data)

    cm_pairs = []
    finished = False

    claims = rj.get("claims", [])
    if claims is None:
        finished = True

    while finished is False:
        next_page = rj.get("nextPageToken")
        for c in claims:
            claim_review = c.get("claimReview")[0]
            fce_claim_text = claim_review.get("title")
            fce_sighting = c.get("text")

            publisher = claim_review.get("publisher").get(
                "name", claim_review.get("publisher").get("site", "na")
            )
            # FCE doesn't give claim ids, so let's make one by hashing the organzation, review URL & date
            raw_id = " ".join(
                [
                    publisher,
                    claim_review.get("url"),
                    claim_review.get("reviewDate", ""),
                ]
            )
            claim_id = hashlib.sha256(raw_id.encode()).hexdigest()
            cm_pairs.append(
                {
                    "claim_id": claim_id,
                    "claim_org": publisher,
                    "claim_text": fce_claim_text,
                    "claim_conclusion": claim_review.get("textualRating"),
                    "claim_url": claim_review.get("url"),
                    "text": fce_sighting,
                    "publication": c.get("claimant"),
                    "publication_date": c.get("claimDate"),
                }
            )

        if next_page is None:
            finished = True
        else:
            # Getting next page of results
            data["pageToken"] = next_page
            #r = requests.get(URL, params=data)
            #rj = r.json()

            rj = query_api(URL, data)

            claims = rj.get("claims")
            if claims is None:
                print(rj)
                finished = True

    return cm_pairs


def recent_sample(publishers: set, output_filename="fce_sightings.json", max_age=194) -> dict:
    """Find recent sightings from each of a set of publishers (fact checkers).
    Optionally write them to a file.
    Also display how many sightings were found per publisher.
    """
    site_counts = {}
    all_pairs = {}

    for pub in tqdm.tqdm(publishers, desc="Getting recent sightings"):
        pairs = get_publisher_sightings(publisher_site=pub, max_age=max_age)
        print(f"Got {len(pairs):4d} claim-sentence pairs from {pub:30s}")
        for p in pairs:
            if p.get("text") is None or p.get("claim_text") is None:
                print("Error encountered. Skipping this claim.")
                continue

            hash_key = hashlib.sha256(
                " ".join([p.get("text"), p.get("claim_text")]).encode()
            ).hexdigest()
            all_pairs[hash_key] = p
        site_counts[pub] = len(pairs)

    print(site_counts)

    if output_filename is not None:
        with open(output_filename, "w") as fout:
            fout.write(json.dumps(all_pairs))

    return all_pairs


if __name__ == "__main__":
    all_pubs = find_many_publishers(max_age=544)
    claim_match_pairs = recent_sample(all_pubs, output_filename="new_sightings.json", max_age=544)
    # Or try this to focus on one org:
    # claim_match_pairs = get_publisher_sightings("africacheck.org")

    print(f"Found {len(claim_match_pairs)} pairs")
    #pprint.pprint(list(claim_match_pairs.values())[0:5])
