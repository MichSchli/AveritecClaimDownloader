import json
from time import sleep
from googleapiclient.discovery import build
import json
from urllib.parse import urlparse
import sys

class GoogleSearch:

    api_key = None
    search_engine_id = None

    blacklist = [
        #"jstor.org", # Blacklisted because their pdfs are not labelled as such, and clog up the download
        #"facebook.com", # Blacklisted because only post titles can be scraped, but the scraper doesn't know this,
        "ftp.cs.princeton.edu", # Blacklisted because it hosts many large NLP corpora that keep showing up
        "nlp.cs.princeton.edu"
    ]

    blacklist_files = [ # Blacklisted strings to block specific nlp files
        "/glove.", 
        "mit.edu/adamrose/Public/googlelist",
        "googlelist.counts",
        "cse.unsw.edu.au/~cs2521/18s2/lecs/week03_04_sorting/exercises/SortMerge/log512",
        "/wordlist.",
        ".ipynb",
    ]

    blacklist_extensions = [ # Blacklisted .txt, .csv, .tsv, and .json files to avoid downloading large NLP corpora. Also blacklisted microsoft office files because they are unparseable. Finally, archives + a few that catch corpora.
        ".txt",
        ".json" ,
        ".doc",
        ".docx",
        ".ppt",
        ".pptx",
        ".xls",
        ".xlsx",
        ".csv",
        ".tsv",
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".rar",
        ".7z",
        ".fwl",
        ".words",
        ".vocab",
        ".voc",
        ".vocabulary",
        ".dic",
        ".dict",
        ".dictionary",
        ".wordlist",
        #".pdf",
    ]

    cache = None

    def __init__(self, config_json) -> None:
        super().__init__()
        self.cache = {}

        # Load API key and search engine ID from config file
        with open(config_json) as f:
            config = json.load(f)
            self.api_key = config["google_api_key"]
            self.search_engine_id = config["search_engine_id"]
    
    def get_domain_name(self, url):
        if '://' not in url:
            url = 'http://' + url

        domain = urlparse(url).netloc

        if domain.startswith("www."):
            return domain[4:]
        else:
            return domain

    def __google_search__(self, search_term, **kwargs):
        service = build("customsearch", "v1", developerKey=self.api_key)
        res = service.cse().list(q=search_term, cx=self.search_engine_id, **kwargs).execute()

        if "items" in res:
            return res['items']
        else:
            return []
    
    def process_search_results(self, results, search_string):
        for result in results:
            stop = False
            link = str(result["link"])

            domain = self.get_domain_name(link)

            if domain in self.blacklist:
                stop = True

            for b_file in self.blacklist_files:
                if b_file in link:
                    stop = True

            for b_ext in self.blacklist_extensions:
                if link.endswith(b_ext):
                    stop = True

            if not stop:
                yield link
        
    def get_google_search_results(self, search_string, sort_date=None, page=0):
        search_results = []
        sort = None if sort_date is None else ("date:r:19000101:"+sort_date)

        for attempt in range(3):
            try:
                search_results += self.__google_search__(
                    search_string,
                    num=10,
                    start=10 * page,
                    sort=sort,
                    dateRestrict=None,
                    gl="US"
                )

                for search_result in self.process_search_results(search_results, search_string):
                    yield search_result
                break
            except:
                print("I encountered an error trying to search \""+search_string+"\". Maybe the connection dropped. Trying again in 3 seconds...", file=sys.stderr)
                sleep(3)


    def run_search(self, query, sort_date=None, max_pages=3):
        # Define the cache key by combining query and sort_date, accounting for None in sort_date
        cache_key = query + "_" + ("None" if sort_date is None else sort_date)

        if cache_key in self.cache:
            #print("Found \""+query+"\" and \""+sort_date+"\" in cache. Returning " + str(len(self.cache[query + sort_date])) + " results.")
            return self.cache[cache_key]

        #print("Searching for \""+query+"\", filtering by sort date \""+sort_date+"\". Retrieving "+str(max_pages)+" pages of results.")
        all_search_results = []
        for page in range(max_pages):
            search_results = list(self.get_google_search_results(query, sort_date=sort_date, page=page))

            # Add new search results to the list, filtering for duplicates
            for search_result in search_results:
                if search_result not in all_search_results:
                    all_search_results.append(search_result)

        #print("Found "+str(len(all_search_results))+" results.")

        results = all_search_results
        self.cache[cache_key] = results

        return results

