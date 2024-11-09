from code.claim.claim import Claim
from datetime import datetime

class ClaimFactory:

    def from_raw(self, claim_dict):
        claim = Claim()

        claim.id = claim_dict["claim_id"]
        claim.claim_text = claim_dict["text"]

        claim.fact_checking_org = claim_dict["claim_org"]
        claim.fact_checking_article_url = claim_dict["claim_url"]
        claim.fact_checking_article_headline = claim_dict["claim_text"]
        claim.fact_checking_verdict = claim_dict["claim_conclusion"]

        if claim_dict["publication_date"] is not None:
            claim.fact_checking_date = datetime.strptime(claim_dict["publication_date"], "%Y-%m-%dT%H:%M:%SZ")

        claim.original_claim_url = None
        claim.original_claim_source = claim_dict["publication"]

        return claim

    def from_json(self, claim_dict):
        claim = Claim()

        claim.id = claim_dict["id"]
        claim.claim_text = claim_dict["claim_text"]

        claim.fact_checking_org = claim_dict["fact_checking_org"]
        claim.fact_checking_article_url = claim_dict["fact_checking_article_url"]
        claim.fact_checking_article_headline = claim_dict["fact_checking_article_headline"]
        claim.fact_checking_verdict = claim_dict["fact_checking_verdict"]

        if "fact_checking_date" in claim_dict:
            claim.fact_checking_date = datetime.strptime(claim_dict["fact_checking_date"], "%d-%m-%yT%H:%M:%S")
            claim.fact_checking_date.strftime("%d-%m-%yT%H:%M:%S")

        claim.original_claim_url = claim_dict["original_claim_url"]
        claim.original_claim_source = claim_dict["original_claim_source"]

        if "fact_checking_article_raw_html" in claim_dict:
            claim.fact_checking_article_raw_html = claim_dict["fact_checking_article_raw_html"]

        if "duplicate_chain" in claim_dict:
            claim.duplicate_chain = claim_dict["duplicate_chain"]

        if "refers_to" in claim_dict:
            claim.refers_to = claim_dict["refers_to"]

        if "refers_to_fact_checking_site" in claim_dict:
            claim.refers_to_fact_checking_site = claim_dict["refers_to_fact_checking_site"]

        if "web_archive" in claim_dict:
            claim.web_archive = claim_dict["web_archive"]

        if "entity_replace" in claim_dict:
            claim.entity_replace = claim_dict["entity_replace"]

        if "different_aspect" in claim_dict:
            claim.different_aspect = claim_dict["different_aspect"]

        if "semantically_similar" in claim_dict:
            claim.semantically_similar = claim_dict["semantically_similar"]

        if "duplicate_claims" in claim_dict:
            claim.duplicate_claims = claim_dict["duplicate_claims"]

        return claim
