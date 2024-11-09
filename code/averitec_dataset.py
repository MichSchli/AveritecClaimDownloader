import json
import os
import time
import random
import requests
#from code.utils.blocklist_helper import BlocklistCreator, GPTSearchTermHelper
#from code.utils.google_search import GoogleSearch
import waybackpy
from waybackpy.exceptions import WaybackError
import re
from rank_bm25 import BM25Okapi
import numpy as np
from code.claim.claim import Claim
from code.claim.claim_factory import ClaimFactory
from bs4 import BeautifulSoup, SoupStrainer
from tqdm import tqdm
import json
from code.utils.python_utils import format_str_table, ensure_dir


class AveritecDataset:
    claims = None

    def __init__(self):
        self.claims = {}
        self.claim_factory = ClaimFactory()
        self.loaded_json_claims = False

    def from_raw_json(self, json_file, start=0, end=None):
        self.id_dict = {}

        with open(json_file, "r") as f:
            json_dict = json.load(f)

            for k, v in sorted(json_dict.items())[start:end]:
                claim = self.claim_factory.from_raw(v)
                self.claims[claim.id] = claim

                self.id_dict[k] = claim.id

    def load_json_claim(self, claim, json_folder, output_prefix, id=False):
        filename = self.to_filename(output_prefix, claim, id=id)
        fname = os.path.join(json_folder, filename)

        if os.path.isfile(fname):
            with open(fname, "r") as f:
                try:
                    j = json.load(f)
                    claim = self.claim_factory.from_json(j)

                    if claim is None:
                        print("Warning: Error loading " + fname + ".")
                    else:
                        return claim
                except:
                    print("Warning: Error loading " + fname + ".")

    def preload_json_claims(self, json_folder, output_prefix, exclusive=False):
        if exclusive:
            included = []

        for json_file in tqdm(list(os.listdir(json_folder)), desc="Loading existing json claims"):
            fname = os.path.join(json_folder, json_file)
            if os.path.isfile(fname):
                if self.from_filename(output_prefix, json_file) not in self.claims:
                    continue

                with open(fname, "r") as f:
                    try:
                        j = json.load(f)
                        claim = self.claim_factory.from_json(j)
                        self.claims[claim.id] = claim
                        included.append(claim.id)
                    except:
                        print("Warning: Error loading " + fname + ".")

        if exclusive:
            for k in list(self.claims.keys()):
                if k not in included:
                    del self.claims[k]

        self.loaded_json_claims = True

    def delete_error_claims(self):
        updated_claims = {}
        discard_reasons = {
        }
        for idx, claim in self.claims.items():
            raw_html = claim.fact_checking_article_raw_html

            # Discard articles where the html is None, or if it contains any kind of error (403, 404, ...)
            if raw_html is None:
                if "is none" not in discard_reasons:
                    discard_reasons["is none"] = 0
                discard_reasons["is none"] += 1

                continue
            
            if "<H1>403 ERROR</H1>" in raw_html:
                if "403 error" not in discard_reasons:
                    discard_reasons["403 error"] = 0
                discard_reasons["403 error"] += 1
                continue

            if "<H1>404 ERROR</H1>" in raw_html:
                if "404 error" not in discard_reasons:
                    discard_reasons["404 error"] = 0
                discard_reasons["404 error"] += 1
                continue

            if "<H1>500 ERROR</H1>" in raw_html:
                if "500 error" not in discard_reasons:
                    discard_reasons["500 error"] = 0
                discard_reasons["500 error"] += 1
                continue

            if "<H1>Access Denied</H1>" in raw_html:
                if "access denied" not in discard_reasons:
                    discard_reasons["access denied"] = 0
                discard_reasons["access denied"] += 1
                continue

            updated_claims[idx] = claim

        print(len(updated_claims))
        print(discard_reasons)
        self.claims = updated_claims

    def delete_long_and_short_claims(self, cutoff_lower = 50, cutoff_upper = 2500):
        updated_claims = {}
        for idx, claim in tqdm(list(self.claims.items()), desc="Deleting long and short claims"):
            word_count = claim.count_words()

            if word_count < cutoff_lower or word_count > cutoff_upper:
                continue

            updated_claims[idx] = claim

        print(len(updated_claims))
        self.claims = updated_claims

    def delete_claims_with_no_archive_link(self):
        updated_claims = {}
        for idx, claim in self.claims.items():
            if claim.web_archive is None:
                continue

            updated_claims[idx] = claim

        print(len(updated_claims))
        self.claims = updated_claims

    def delete_duplicate_claims(self):
        # Get the list of all claim texts:
        all_claim_texts = []
        for idx, claim in self.claims.items():
            all_claim_texts.append(claim.claim_text)

        # Create BM25 model:
        corpus = [sentence.lower().strip().split() for sentence in all_claim_texts]  # Tokenize each claim
        bm25 = BM25Okapi(corpus)

        updated_claims = {}
        all_keys = list(self.claims.keys())
        edges = {}

        for claim_id, claim in tqdm(list(self.claims.items()), desc="Finding duplicate claims"):
            # Get the claim text:
            claim_text = claim.claim_text

            # Get the BM25 scores for each sentence in the corpus based on the answer
            scores = bm25.get_scores(claim_text.lower().strip().split())
        
            # Get the top sentences:
            top_k = 11
            top_k_idxs = np.argsort(scores)[::-1][:top_k]
            top_k_sentences = [corpus[idx] for idx in top_k_idxs]
            top_k_scores = [scores[idx] for idx in top_k_idxs]
            top_k_keys = [all_keys[idx] for idx in top_k_idxs]

            # Connect all claims that have similarity higher than 25:

            for idx,score in enumerate(top_k_scores[1:]):
                if score > 30:
                    if claim_id not in edges:
                        edges[claim_id] = []

                    if top_k_keys[idx+1] not in edges:
                        edges[top_k_keys[idx+1]] = []

                    if top_k_keys[idx+1] not in edges[claim_id]:
                        edges[claim_id].append(top_k_keys[idx+1])

                    if claim_id not in edges[top_k_keys[idx+1]]:
                        edges[top_k_keys[idx+1]].append(claim_id)

        sets = []
        visited = []

        for claim_id, claim in tqdm(list(self.claims.items()), desc="Traversing graph"):
            if claim_id in visited:
                continue

            queue = [claim_id]
            visited.append(claim_id)
            this_set = [claim_id]

            while len(queue) > 0:
                this_claim_id = queue.pop(0)
                this_claim = self.claims[this_claim_id]

                if this_claim_id in edges:
                    for other_claim_id in edges[this_claim_id]:
                        if other_claim_id not in visited:
                            queue.append(other_claim_id)
                            visited.append(other_claim_id)
                            this_set.append(other_claim_id)

            sets.append(this_set)

        updated_claims = {}
        for s in sets:
            # Pick a random claim from the set:
            random.shuffle(s)
            claim_id = s[0]

            updated_claims[claim_id] = self.claims[claim_id]

        print(len(updated_claims))            
        self.claims = updated_claims

    def iter_claims(self, json_folder, output_prefix, desc=""):
        if self.loaded_json_claims:
            for k, v in tqdm(list(self.claims.items()), desc=desc):
                yield k,v
        else:
            for k, v in tqdm(list(self.claims.items()), desc=desc):
                v = self.load_json_claim(v, json_folder, output_prefix)
                if v is not None:
                    yield k,v

    def save_to_json(self, json_folder, output_prefix, load_from_existing_jsons=None, filter=False):
        s = "Writing JSON files." if not filter else "Writing JSON files. Discarding any that do not meet acceptance criteria."

        for k, v in tqdm(list(self.claims.items()), desc=s):
            output_file = self.to_filename(output_prefix, v)
            output_file = os.path.join(json_folder, output_file)
            ensure_dir(output_file)
            if load_from_existing_jsons:
                v = self.load_json_claim(v, load_from_existing_jsons, output_prefix)
                if v is not None and (not filter or not v.should_discard()):
                    with open(output_file, "w") as f:
                        json_line = v.to_json()
                        string_repr = json.dumps(json_line)
                        print(string_repr, file=f)
            else:
                with open(output_file, "w") as f:
                    json_line = v.to_json()
                    string_repr = json.dumps(json_line)
                    print(string_repr, file=f)

    def mark_internal_refs(self, save_during=False, json_folder=None, output_prefix=None, wrt=None):
        all_sources = {}
        all_source_domains = {}

        for k, v in self.iter_claims(json_folder, output_prefix, desc="Gathering list of fact checking sources"):
            source = v.fact_checking_article_url

            source_domain = source.split("/")[2]

            if source_domain.startswith("www"):
                source_domain = source_domain[4:]

            all_source_domains[source_domain] = True

            if source in all_sources:
                v.check_if_direct_duplicate(all_sources[source])
            else:
                all_sources[source] = v

        if wrt is not None:
            for k,v in wrt:
                source = v.fact_checking_article_url

                source_domain = source.split("/")[2]

                if source_domain.startswith("www"):
                    source_domain = source_domain[4:]

                all_source_domains[source_domain] = True

                if source in all_sources:
                    v.check_if_direct_duplicate(all_sources[source])
                else:
                    all_sources[source] = v

        for k, v in self.iter_claims(json_folder, output_prefix, desc="Finding articles that refer to other fact checking articles"):
            v.reset_refers_to()
            if v.fact_checking_article_raw_html is not None:
                this_source = v.fact_checking_article_url
                this_source_domain = this_source.split("/")[2]
                if this_source_domain.startswith("www"):
                    this_source_domain = this_source_domain[4:]

                soup = BeautifulSoup(v.fact_checking_article_raw_html, parse_only=SoupStrainer("a"),
                                     features="html.parser")

                for link in soup:
                    if link.has_attr("href"):
                        if link["href"].startswith("http") or link["href"].startswith("www"):
                            if link["href"] != this_source and this_source_domain not in link["href"] and link["href"] in all_sources:
                                v.mark_refers_to_other_claim_article(link["href"])

                            for source_domain in all_source_domains.keys():
                                if source_domain != this_source_domain and source_domain in link["href"]:
                                    v.mark_refers_to_fact_checking_site(source_domain)

            if save_during and output_prefix is not None:
                output_file = self.to_filename(output_prefix, v)
                output_file = os.path.join(json_folder, output_file)
                with open(output_file, "w") as f:
                    json_line = v.to_json()
                    string_repr = json.dumps(json_line)
                    print(string_repr, file=f)

    def write(self, claim_folder=None, output_folder=None, output_prefix=None):
        if claim_folder is None or output_folder is None or output_prefix is None:
            iterable = self.claims.items()
            iterable = tqdm(iterable, desc="Writing dataset copy")
        else:
            iterable = self.iter_claims(claim_folder, output_prefix, desc="Writing dataset copy")

        for k, v in iterable:
            output_file = self.to_filename(output_prefix, v)
            output_file = os.path.join(output_folder, output_file)
            ensure_dir(output_file)
            with open(output_file, "w") as f:
                json_line = v.to_json()
                string_repr = json.dumps(json_line)
                print(string_repr, file=f)

    def to_filename(self, output_prefix, claim, id=False):
        if not id:
            claim = claim.id

        output_file = output_prefix + "_" + claim + ".json"
        return output_file

    def from_filename(self, output_prefix, filename):
        prefix_len = len(output_prefix) + 1

        return filename[prefix_len:-5]

    def add_web_archive_links(self, save_during=True, json_folder=None, output_prefix=None):
        for k, v in self.iter_claims(json_folder, output_prefix, desc="Creating or fetching archive.org links"):
            # Skip things that have already been archived in our system
            if v.web_archive is not None:
                continue
            elif v.fact_checking_org == "Snopes.com" or v.fact_checking_org == "Snopes":  # Skip Snopes because they have requested not to be archived
                continue

            url = v.fact_checking_article_url
            user_agent = "Averitec dataset builder // contact: mss84@cam.ac.uk"

            wayback = waybackpy.Url(url, user_agent)

            # It looks stupid but this is the only way to discover that a domain is blocked:
            try:
                n_archived = wayback.total_archives()
            except:
                print("The domain \"" + v.fact_checking_org + "\" seems to block archival. Skipping.")
                continue

            # Take either newest archive, or save an archive if none exists:
            if n_archived > 0:
                try:
                    archive = wayback.newest()
                except:
                    print("I failed to retrieve a saved archival page for " + url + ". Building a new page.")

                    for i in range(5):
                        try:
                            archive = wayback.save()
                            break
                        except:
                            print("I couldn't reach the archive to build a page for " + url + ". Trying again in 3 seconds.")
                            time.sleep(3)
                            archive = None
            else:
                for i in range(5):
                    try:
                        archive = wayback.save()
                        break
                    except:
                        print("I couldn't reach the archive to build a page for " + url + ". Trying again in 3 seconds.")
                        time.sleep(3)
                        archive = None

            if archive is not None:
                v.web_archive = archive.archive_url

            if save_during and output_prefix is not None:
                output_file = self.to_filename(output_prefix, v)
                output_file = os.path.join(json_folder, output_file)
                with open(output_file, "w") as f:
                    json_line = v.to_json()
                    string_repr = json.dumps(json_line)
                    print(string_repr, file=f)

    def add_duplicate_claim_annotation(self, json_folder=None, output_prefix=None, duplicate_claim_file=None, save_during=True):
        with open(duplicate_claim_file, 'r') as f:
            j = json.load(f)

        duplicate_chain_dict = {}

        for k,v in j.items():
            for c1 in v:
                for c2 in v:
                    if c1 != c2:
                        if not self.id_dict[c1] in duplicate_chain_dict:
                            duplicate_chain_dict[self.id_dict[c1]] = [self.id_dict[c2]]
                        else:
                            duplicate_chain_dict[self.id_dict[c1]].append(self.id_dict[c2])

        for k,v in self.iter_claims(json_folder, output_prefix, desc="Marking duplicate claims"):
            if v.id in duplicate_chain_dict:
                v.duplicate_claims = duplicate_chain_dict[v.id]
            else:
                v.duplicate_claims = []

            if save_during and output_prefix is not None:
                output_file = self.to_filename(output_prefix, v)
                output_file = os.path.join(json_folder, output_file)
                with open(output_file, "w") as f:
                    json_line = v.to_json()
                    string_repr = json.dumps(json_line)
                    print(string_repr, file=f)

    def add_different_aspect(self, json_folder=None, output_prefix=None, different_aspect_file=None, save_during=True):
        with open(different_aspect_file, 'r') as f:
            j = json.load(f)

        fixed_j = {}
        for k, v in j.items():
            fixed_j[self.id_dict[k]] = [self.id_dict[x] for x in v]

        for k,v in self.iter_claims(json_folder, output_prefix, desc="Adding different aspect annotation"):
            if v.id in fixed_j:
                v.different_aspect = fixed_j[v.id]
            else:
                v.different_aspect = []

            if save_during and output_prefix is not None:
                output_file = self.to_filename(output_prefix, v)
                output_file = os.path.join(json_folder, output_file)
                with open(output_file, "w") as f:
                    json_line = v.to_json()
                    string_repr = json.dumps(json_line)
                    print(string_repr, file=f)

    def add_blocklist(self):
        config_json = "config.json"
        searcher = GoogleSearch(config_json)
        gpt_helper = GPTSearchTermHelper(config_json)
        blocklist_creator = BlocklistCreator(searcher, gpt_helper)

        for k, claim in tqdm(list(self.claims.items()), desc="Creating blocklists"):
            claim_text = claim.claim_text
            fca = claim.fact_checking_article_url

            blocklist = blocklist_creator.get_older_fcas(claim_text, fca)

            claim.set_blocklist(blocklist)

            print(blocklist)

    def add_entity_replace(self, json_folder=None, output_prefix=None, entity_replace_file=None, save_during=True):
        with open(entity_replace_file, 'r') as f:
            j = json.load(f)

        fixed_j = {}
        for k, v in j.items():
            fixed_j[self.id_dict[k]] = [self.id_dict[x] for x in v]

        for k,v in self.iter_claims(json_folder, output_prefix, desc="Adding entity_replace annotation"):
            if v.id in fixed_j:
                v.entity_replace = fixed_j[v.id]
            else:
                v.entity_replace = []

            if save_during and output_prefix is not None:
                output_file = self.to_filename(output_prefix, v)
                output_file = os.path.join(json_folder, output_file)
                with open(output_file, "w") as f:
                    json_line = v.to_json()
                    string_repr = json.dumps(json_line)
                    print(string_repr, file=f)

    def add_semantically_similar(self, json_folder=None, output_prefix=None, semantically_similar_file=None, save_during=True):
        with open(semantically_similar_file, 'r') as f:
            j = json.load(f)

        fixed_j = {}
        for k, v in j.items():
            fixed_j[self.id_dict[k]] = [self.id_dict[x] for x in v]

        for k,v in self.iter_claims(json_folder, output_prefix, desc="Adding semantic similarity annotation"):
            if v.id in fixed_j:
                v.semantically_similar = fixed_j[v.id]
            else:
                v.semantically_similar = []

            if save_during and output_prefix is not None:
                output_file = self.to_filename(output_prefix, v)
                output_file = os.path.join(json_folder, output_file)
                with open(output_file, "w") as f:
                    json_line = v.to_json()
                    string_repr = json.dumps(json_line)
                    print(string_repr, file=f)

    def fetch_all_fact_checking_article_htmls(self, save_during=False, json_folder=None, output_prefix=None):
        for i, (k, v) in enumerate(self.iter_claims(json_folder, output_prefix, desc="Fetching fact checking article html")):
            if v.fact_checking_article_raw_html is None or "<H1>403 ERROR</H1>" in v.fact_checking_article_raw_html:
                url = v.fact_checking_article_url

                if url is not None:
                    for _ in range(5):
                        try:
                            resp = requests.get(url)
                            html_text = str(resp.content)

                            if "<H1>403 ERROR</H1>" not in html_text:
                                v.fact_checking_article_raw_html = html_text
                            else:
                                v.fact_checking_article_raw_html = None
                        except:
                            print("I couldn't retrieve the raw html. Trying again in 3 seconds.")
                            time.sleep(3)

                if save_during and output_prefix is not None:
                    output_file = self.to_filename(output_prefix, v)
                    output_file = os.path.join(json_folder, output_file)
                    with open(output_file, "w") as f:
                        json_line = v.to_json()
                        string_repr = json.dumps(json_line)
                        print(string_repr, file=f)

    def filter_and_split(self, json_folder, output_prefix, keep_folder, store_folder, discard_folder, claim_count=7500, false_limit=2500, true_limit=2500):
        kept_falsy_ids = []
        kept_truthy_ids = []
        kept_other_ids = []
        discarded_ids = []

        if json_folder is None or output_prefix is None:
            iterable = self.claims.items()
            iterable = tqdm(iterable, desc="Constructing filtered dataset of " + str(claim_count) + " claims")
        else:
            iterable = self.iter_claims(json_folder, output_prefix, desc="Constructing filtered dataset of " + str(claim_count) + " claims")

        for k, v in iterable:
            discard = False

            # Discard any exact duplicates:
            if v.duplicate_chain is not None and v.duplicate_chain != v.id:
                discard = True

            # Discard articles with direct links to other articles:
            if len(v.refers_to) > 0:
                discard = True

            # Discard articles that were not properly cached:
            if not v.web_archive:
                discard = True

            # Discard fact-checking articles with errors:
            if v.fact_checking_article_raw_html is None or "<H1>403 ERROR</H1>" in v.fact_checking_article_raw_html:
                discard = True

            # Discard very long and very short articles, if the label is falsy:
            if v.label_is_falsy() and not discard:
                this_article_words = v.count_words()
                if 50 > this_article_words or 2500 < this_article_words:
                    discard = True
                else:
                    kept_falsy_ids.append(v.id)
            elif v.label_is_truthy() and not discard:
                kept_truthy_ids.append(v.id)
            elif not discard:
                kept_other_ids.append(v.id)

            if discard:
                discarded_ids.append(v.id)

        random.shuffle(kept_truthy_ids)
        random.shuffle(kept_falsy_ids)
        random.shuffle(kept_other_ids)

        keep_t = kept_truthy_ids[:true_limit]
        store_t = kept_truthy_ids[true_limit:]

        keep_f = kept_falsy_ids[:false_limit]
        store_f = kept_truthy_ids[false_limit:]

        n_rest = claim_count - len(keep_t) - len(keep_f)

        keep_o = kept_other_ids[:n_rest]
        store_o = kept_other_ids[n_rest:]

        print("Dataset has been split.")
        print("=" * 60)
        print(format_str_table("Kept falsy claims:", str(len(kept_falsy_ids)), sp=60))
        print(format_str_table("Kept truthy claims:", str(len(kept_truthy_ids)), sp=60))
        print(format_str_table("Kept other claims:", str(len(kept_other_ids)), sp=60))
        print(format_str_table("Sampled falsy claims:", str(len(keep_f)), sp=60))
        print(format_str_table("Sampled truthy claims:", str(len(keep_t)), sp=60))
        print(format_str_table("Sampled other claims:", str(len(keep_o)), sp=60))
        print(format_str_table("Discarded claims:", str(len(discarded_ids)), sp=60))

        for claim_id in  tqdm(keep_t + keep_f + keep_o, desc="Saving kept claims"):
            if json_folder is not None:
                claim = self.load_json_claim(claim_id, json_folder, output_prefix, id=True)
            else:
                claim = self.claims[claim_id]
            output_file = self.to_filename(output_prefix, claim)
            output_file = os.path.join(keep_folder, output_file)
            ensure_dir(output_file)
            with open(output_file, "w") as f:
                json_line = claim.to_json()
                string_repr = json.dumps(json_line)
                print(string_repr, file=f)

        for claim_id in  tqdm(store_t + store_f + store_o, desc="Saving stored claims"):
            if json_folder is not None:
                claim = self.load_json_claim(claim_id, json_folder, output_prefix, id=True)
            else:
                claim = self.claims[claim_id]
            output_file = self.to_filename(output_prefix, claim)
            output_file = os.path.join(store_folder, output_file)
            ensure_dir(output_file)
            with open(output_file, "w") as f:
                json_line = claim.to_json()
                string_repr = json.dumps(json_line)
                print(string_repr, file=f)

        for claim_id in  tqdm(discarded_ids, desc="Saving discard claims"):
            if json_folder is not None:
                claim = self.load_json_claim(claim_id, json_folder, output_prefix, id=True)
            else:
                claim = self.claims[claim_id]
            output_file = self.to_filename(output_prefix, claim)
            output_file = os.path.join(discard_folder, output_file)
            ensure_dir(output_file)
            with open(output_file, "w") as f:
                json_line = claim.to_json()
                string_repr = json.dumps(json_line)
                print(string_repr, file=f)

    def remove_raw_html(self):
        for k, v in tqdm(list(self.claims.items()), desc="Removing raw html"):
            v.fact_checking_article_raw_html = None

    def save_as_averitec_json(self, json_file):
        claim_list = []

        for k, v in tqdm(list(self.claims.items()), desc="Converting dataset to JSON"):
            claim_list.append(v.to_averitec_json())

        with open(json_file, "w") as f:
            json_line = claim_list
            string_repr = json.dumps(json_line, indent=4)
            print(string_repr, file=f)

    def statistic_summary(self, json_folder=None, output_prefix=None):
        total_count = len(self.claims)

        direct_duplicates = 0
        internal_refs = 0
        has_html = 0
        refs_fact_checking_site = 0
        has_archive = 0

        domains = {}

        included = 0

        different_aspect = 0
        entity_replace = 0
        semantically_similar = 0

        ir_different_aspect = 0
        ir_entity_replace = 0
        ir_semantically_similar = 0

        duplicate_claims = 0
        ir_duplicate_claims = 0

        verdict_dict = {}
        kept_verdict_dict = {}

        keyphrase_filtered = 0

        avg_words = 0
        min_words = None
        max_words = None

        truthy = 0
        falsy = 0
        others = 0

        outside_word_count_bounds = 0

        if json_folder is None or output_prefix is None:
            iterable = self.claims.items()
            iterable = tqdm(iterable, desc="Computing statistics")
        else:
            iterable = self.iter_claims(json_folder, output_prefix, desc="Computing statistics")

        for k, v in iterable:
            discard = False

            if v.fact_checking_article_raw_html is not None:
                this_article_words = v.count_words()

                if 50 < this_article_words < 2500:
                    avg_words += this_article_words

                    if min_words is None or this_article_words < min_words:
                        min_words = this_article_words

                    if max_words is None or this_article_words > max_words:
                        max_words = this_article_words

                    if v.should_keyphrase_filter():
                        keyphrase_filtered += 1
                        #discard = True
                else:
                    discard = True
                    outside_word_count_bounds += 1

            if v.duplicate_claims is not None and len(v.duplicate_claims) > 0:
                duplicate_claims += 1

                if len(v.refers_to) > 0:
                    ir_duplicate_claims += 1

            if v.different_aspect is not None and len(v.different_aspect) > 0:
                different_aspect += 1

                if len(v.refers_to) > 0:
                    ir_different_aspect += 1

            if v.entity_replace is not None and len(v.entity_replace) > 0:
                entity_replace += 1

                if len(v.refers_to) > 0:
                    ir_entity_replace += 1

            if v.semantically_similar is not None and len(v.semantically_similar) > 0:
                semantically_similar += 1

                if len(v.refers_to) > 0:
                    ir_semantically_similar += 1

            if v.duplicate_chain is not None and v.duplicate_chain != v.id:
                direct_duplicates += 1
                discard = True

            if len(v.refers_to) > 0:
                internal_refs += 1
                discard = True

            if len(v.refers_to_fact_checking_site) > 0:
                refs_fact_checking_site += 1

            if v.web_archive:
                has_archive += 1
            else:
                discard = True

            if v.fact_checking_article_raw_html is not None and "<H1>403 ERROR</H1>" not in v.fact_checking_article_raw_html:
                has_html += 1
            else:
                discard = True

            if v.fact_checking_org in domains:
                domains[v.fact_checking_org] += 1
            else:
                domains[v.fact_checking_org] = 1

            if v.fact_checking_verdict in verdict_dict:
                verdict_dict[v.fact_checking_verdict] += 1
            else:
                verdict_dict[v.fact_checking_verdict] = 1

            if not discard:
                included += 1

                if v.label_is_falsy():
                    falsy += 1
                elif v.label_is_truthy():
                    truthy += 1
                else:
                    others += 1

                if v.fact_checking_verdict in kept_verdict_dict:
                    kept_verdict_dict[v.fact_checking_verdict] += 1
                else:
                    kept_verdict_dict[v.fact_checking_verdict] = 1

        print("Some statistics for the dataset:")
        print("=" * 60)
        print(format_str_table("Total claims:", str(total_count), sp=60))
        print(format_str_table("Average words:", str(avg_words / total_count), sp=60))
        print(format_str_table("Minimum words:", str(min_words), sp=60))
        print(format_str_table("Maximum words:", str(max_words), sp=60))
        print(format_str_table("Total claims included:", str(included), sp=60))
        print(format_str_table("Exact duplicate claims (hyperlink):", str(direct_duplicates), sp=60))
        print(format_str_table("Internal references:", str(internal_refs), sp=60))
        print(format_str_table("Different aspect:", str(different_aspect), sp=60))
        print(format_str_table("Entity replacement:", str(entity_replace), sp=60))
        print(format_str_table("Duplicate claims:", str(duplicate_claims), sp=60))
        print(format_str_table("Semantically similar claims:", str(semantically_similar), sp=60))
        print(format_str_table("Retrieved HTML correctly:", str(has_html), sp=60))
        print(format_str_table("Built web archive page correctly:", str(has_archive), sp=60))
        print(format_str_table("Refers to some fact checking site:", str(refs_fact_checking_site), sp=60))
        print(format_str_table("Keyphrase filtered:", str(keyphrase_filtered), sp=60))
        print(format_str_table("Outside word count boundaries:", str(outside_word_count_bounds), sp=60))
        print("=" * 60)
        print(format_str_table("Truthy claims:", str(truthy), sp=60))
        print(format_str_table("Falsy claims:", str(falsy), sp=60))
        print(format_str_table("Other claims:", str(others), sp=60))
        print("=" * 60)
        print(format_str_table("Internal refer + DC:", str(ir_duplicate_claims), sp=60))
        print(format_str_table("Internal refer + DA:", str(ir_different_aspect), sp=60))
        print(format_str_table("Internal refer + ER:", str(ir_entity_replace), sp=60))
        print(format_str_table("Internal refer + SS:", str(ir_semantically_similar), sp=60))
        print("=" * 60)
        for k, v in domains.items():
            print(format_str_table(k + ":", str(v), sp=60))
        print("=" * 60)
        print("Labels (# > 5):")
        for k, v in verdict_dict.items():
            if v > 5:
                print(format_str_table(k + ":", str(v), sp=60))
        print("=" * 60)
        print("Kept labels (# > 5):")
        for k, v in kept_verdict_dict.items():
            if v > 5:
                print(format_str_table(k + ":", str(v), sp=60))
