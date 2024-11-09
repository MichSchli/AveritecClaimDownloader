from bs4 import BeautifulSoup

class Claim:
    id = None
    claim_text = None

    fact_checking_org = None
    fact_checking_article_url = None
    fact_checking_article_headline = None
    fact_checking_verdict = None
    fact_checking_date = None
    fact_checking_article_raw_html = None

    original_claim_url = None
    original_claim_source = None

    duplicate_chain = None  # Deprecated; marks claims with the exact same hyperlink. Already removed.

    refers_to = None
    refers_to_fact_checking_site = None

    web_archive = None

    different_aspect = None
    entity_replace = None
    semantically_similar = None

    duplicate_claims = None

    def __init__(self):
        self.reset_refers_to()

    def check_if_direct_duplicate(self, other_claim):
        if self.claim_text == other_claim.claim_text:
            if other_claim.duplicate_chain is None:
                self.duplicate_chain = other_claim.id
                other_claim.duplicate_chain = other_claim.id
            else:
                self.duplicate_chain = other_claim.duplicate_chain

    def reset_refers_to(self):
        self.refers_to = []
        self.refers_to_fact_checking_site = []

    def mark_refers_to_other_claim_article(self, other_claim_article_url):
        if other_claim_article_url not in self.refers_to:
            self.refers_to.append(other_claim_article_url)

    def mark_refers_to_fact_checking_site(self, site):
        if site not in self.refers_to_fact_checking_site:
            self.refers_to_fact_checking_site.append(site)

    def to_json(self):
        d = self.__dict__

        if "fact_checking_date" in d and d["fact_checking_date"] is not None:
            d["fact_checking_date"] = d["fact_checking_date"].strftime("%d-%m-%yT%H:%M:%S")

        return d
    
    def to_averitec_json(self):
        """ 
        Convert the file to a JSON matching the published averitec dataset format
        """

        d = {}

        d["claim"] = self.claim_text
        d["label"] = self.fact_checking_verdict
        
        if self.fact_checking_date is not None:
            d["claim_date"] = self.fact_checking_date.strftime("%d-%m-%yT%H:%M:%S")

            # Format the data to yyyy-mm-dd
            d["claim_date"] = d["claim_date"][6:10] + "-" + d["claim_date"][3:5] + "-" + d["claim_date"][0:2]

        d["reporting_source"] = self.original_claim_source
        d["original_claim_url"] = self.original_claim_url
        d["fact_checking_article"] = self.web_archive
        d["fact_checking_organization"] = self.fact_checking_org

        return d

    def label_is_falsy(self):
        filtered_label_list = ["false",
                               "fake",
                               "satire",
                               "totally false",
                               "totally fake",
                               "pants on fire",
                               "incorrect",
                               "false!",
                               "fake!",
                               "scam",
                               "unsupported",
                               "false – content that has no basis in fact.",
                               "false - The primary claim of the content is factually inaccurate.",
                               "fake quote",
                               "0 Star",
                               "1 Star",
                               "2 Star",
                               "barely-true",
                               "digital manipulations!",
                               "disputed",
                               "disputed!",
                               "fiction",
                               "fiction! & disputed!",
                               "fiction!",
                               "satire!",
                               "full-flop",
                               "inaccurate attribution!",
                               "incorrect attribution!",
                               "incorrect authorship!",
                               "incorrectly attributed!",
                               "misattributed",
                               "mostly fiction!",
                               "mostly-false",
                               "not true",
                               "pants-fire",
                               "pants-on-fire!",
                               "reported as fiction!",
                               "reported fiction!",
                               "no"]

        return self.fact_checking_verdict.lower() in filtered_label_list

    def label_is_truthy(self):
        filtered_label_list = ["true",
                               "truth",
                               "correct",
                               "accurate"
                               "mostly true",
                               "mostly correct",
                               "mostly accurate",
                               "accurate (supported by evidence and facts; acceptable margin of error)",
                               "4 Star",
                               "5 Star",
                               "authorship confirmed!",
                               "commentary!",
                               "confirmed authorship",
                               "confirmed authorship!",
                               "correct attribution!",
                               "correct-attribution",
                               "correctly attributed!",
                               "mostly truth!",
                               "mostly-true",
                               "no-flip",
                               "official!",
                               "reported to be true!",
                               "reported to be truth!",
                               "truth but an opinion!",
                               "truth!",
                               "truth! but an opinion!",
                               "truth! but not intentionally!",
                               "truth! but not the one you think!",
                               "truth! but now resolved!",
                               "yes"]

        return self.fact_checking_verdict.lower() in filtered_label_list

    def should_keyphrase_filter(self):
        keyphrase_list = ["audio clip",
                          "photo was taken",
                          "photo was originally taken",
                          "video was taken",
                          "video was originally taken",
                          "was filmed",
                          "was originally filmed",
                          "reverse image search",
                          "previously posted to",
                          "we asked",
                          "was fact-checked",
                          "was debunked",
                          "was factchecked"
                          "was previously fact-checked",
                          "was previously debunked",
                          "was previously factchecked"]

        for keyword in keyphrase_list:
            if keyword in self.fact_checking_article_raw_html:
                return True

        return False

    def should_discard(self):
        # Discard direct duplicates:
        if self.duplicate_chain is not None and self.duplicate_chain != self.id:
            return True

        # Discard claims with html links to other claims on their page:
        if len(self.refers_to) > 0:
            return True

        # Discard claims that failed to build an archive copy of the article:
        if not self.web_archive:
            return True

        # Discard claims that have no html data:
        if self.fact_checking_article_raw_html is None or "<H1>403 ERROR</H1>" in self.fact_checking_article_raw_html:
            return True

        return False

    def cache_in_archive(self):
        archive_helper = WaybackHelper()
        archive_url = archive_helper.cache_in_archive(self.fact_checking_article_url)

        if archive_url is not None:
            self.web_archive = archive_url

    def count_words(self):
        soup = BeautifulSoup(self.fact_checking_article_raw_html, features="html.parser")

        # kill all script and style elements
        for script in soup(["script", "style"]):
            script.extract()  # rip it out

        # get text
        text = soup.get_text()
        text = text.replace("\\n", "\n")

        # break into lines and remove leading and trailing space on each
        lines = [line.strip() for line in text.splitlines()]

        # break multi-headlines into a line each
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # drop blank lines

        this_article_words = 0

        for chunk in chunks:
            if chunk:
                chunk_words = chunk.strip().split(" ")
                chunk_len = len([c for c in chunk_words if c])

                if chunk_len > 1:
                    this_article_words += chunk_len

        return this_article_words