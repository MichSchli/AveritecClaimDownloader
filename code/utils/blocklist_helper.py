import argparse
from google_search import GoogleSearch
import json
import os
import sys
from html2lines import url2lines
import tqdm
import openai
import time

class GPTSearchTermHelper:

    def __init__(self, config):
        self.model = "gpt-3.5-turbo"

        # Load the openai API key from the config file
        with open(config) as f:
            j = json.load(f)
            self.openai_api_key = j["openai_api_key"]

        openai.api_key = self.openai_api_key

    def generate_headline(self, passage):
        system_message = "You are HeadlineGPT, a world-class AI tool that assists journalists in writing fact-checking articles. The journalist gives you an article they have written, and you propose headlines for that article."
        prompt = "I have written the following article. What headlines should I consider?\n\nArticle: \"" + passage + "\"\n\n"

        prompt += "Format your output as valid markdown. First, provide a section **Discussion** where you debate the criteria that a good headline for this fact-checking article must meet. This could for example include listing key facts to reference, or thinking of SEO optimization. "
        prompt += "Then, provide a section **Suggestions**, where you output, as a numbered list, AT LEAST FIVE and AT MOST TEN suggestion headlines."

        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ]

        result_message = self.send_message(messages)
        after_suggestions = result_message.split("Suggestions")[1]

        qs = []

        for line in after_suggestions.split("\n"):
            # if the line is empty, skip
            if line == "":
                continue

            # If the line starts with a number, it is a question
            if line[0].isdigit():
                # Split line on first space
                question = line.split(" ", 1)[1].replace("\"", "")
                qs.append(question)

        # We simply return the last three questions
        return qs[-3:]

    def decide_if_fca(self, passage, claim): # Alternative to test: Does FACT CHECKED: claim work as a headline?
        system_message = "You are ArticleTypeGPT, a world-class AI tool that assists internet users. The user gives you an article, and you answer questions about the type of the article, e.g. whether it can be characterised as a fact-checking article, debunking article, or similar."
        prompt = "I have found the following article. Is the article an article of the type \"fact-checking, debunking, correcting, or similar\" addressing the claim \"" + claim + "\"?\n\nArticle: \"" + passage[:1500] + "\"\n\n"

        prompt += "Format your output as valid markdown. First, provide a section **Discussion** where you reason step-by-step about whether this article falls under fall under \"fact-checking, debunking, correcting, or similar\". This could for example be articles that debunk claims, that prove claims to be false, that reveal claims to be satire, or that test the veracity of claims. Furthermore, discuss whether the article addresses the claim \"" + claim + "\". "
        prompt += "Then, provide a section **Types**, where you output, as a numbered list, the top three types of articles that this article falls under. "
        prompt += "Finally, provide a section **Decision**, where you output your decision: either YES, if it is a fall under \"fact-checking, debunking, correcting, or similar\" article and is about the claim \"" + claim + "\", or NO, if it does not fall under \"fact-checking, debunking, correcting, or similar\" or does not address the claim \"" + claim + "\". You must answer either YES or NO. Before answering NO, provide a short explanation of what other type of article it is."

        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ]

        result_message = self.send_message(messages)

        decision = result_message.split("Decision")[-1]
        decision = "YES" in decision

        return decision
    
    def decide_if_fca_headline(self, passage, claim): # Alternative to test: Does FACT CHECKED: claim work as a headline?
        system_message = "You are HeadlineGPT, a world-class AI tool that assists people in understanding news media. You are given articles and headlines, you must decide if they match."
        prompt = "I have read the following article. I am looking for an article with the headline \"FACT CHECK: " + claim +"\". Could this be the article?\n\nArticle: \"" + passage[:1500] + "\"\n\n"

        prompt += "Format your output as valid markdown. First, provide a section **Discussion** where you reason step-by-step about whether this headline is a close enough fit for the content that it COULD be the right article. You don't have to be absolutely sure -- if some of the content matches, and if the articles seems to be about fact-checking, debunking, or similar, then you can say YES. "
        prompt += "Then, provide a section **Decision**, where you output your decision: either YES, if the article could be the one published with this headline, or NO, if the headline cannot match the article."

        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ]

        result_message = self.send_message(messages)

        decision = result_message.split("Decision")[-1]
        decision = "YES" in decision

        return decision
    
    def decide_if_fca_keywords(self, passage): 
        keyword_list = ["fact check", "debunked", "debunk", "false", "true", "satire", "verified", "factcheck", "fact-check"]

        decision = False
        for keyword in keyword_list:
            if keyword in passage:
                decision = True
                break

        return decision

    def send_message(self, message):
        # Send message to OpenAI, with exponential backoff
        backoff = 1
        while True:
            try:
                response = openai.ChatCompletion.create(
                    model=self.model,
                    messages=message,
                    temperature=0.5
                )
                text = response.choices[0].message.content
                break
            except:
                print("OpenAI API call failed, retrying in " + str(backoff) + " seconds", file=sys.stderr)
                time.sleep(backoff)
                backoff *= 2       

        return text


class BlocklistCreator:

    def __init__(self, searcher, gpt_helper, dataset=None) -> None:
        super().__init__()
        self.searcher = searcher
        if dataset:
            self.dataset = self.load_dataset(dataset)
        self.gpt_helper = gpt_helper
        self.blocklist = []

    def load_dataset(self, json_filepath):
        with open(json_filepath, "r") as f:
            dataset = json.load(f)
        return dataset
    
    def make_blocklist(self):
        for claim in tqdm.tqdm(self.dataset):
            fcas = self.find_other_fcas(claim)
            self.blocklist.append(fcas)

            claim["urls_to_block"] = fcas
            yield claim

    def is_fca_article(self, url, claim):
        lines = "\n".join(url2lines(url))
        if len(lines) < 10:
            return False
        
        test_1 = self.gpt_helper.decide_if_fca(lines, claim)
        if test_1:
            return True
        
        test_2 = self.gpt_helper.decide_if_fca_headline(lines, claim)

        return test_2
    
    def find_other_fcas(self, claim):
        fca = claim["fact_checking_article"]
        claim = claim["claim"]

        other_fcas = self.get_older_fcas(claim, fca)
        
        return other_fcas

    def get_older_fcas(self, claim, fca):
        other_fcas = []

        # Add the fca itself, removing the wayback machine prefix and accounting for both http and https
        fca_no_wayback = fca.split("://")[-1]
        other_fcas.append("http://"+fca_no_wayback)
        other_fcas.append("https://"+fca_no_wayback)

        naive = self.searcher.run_search("fact check " + claim + "", max_pages=1)
        for n in tqdm.tqdm(naive, desc="Naive search"):
            if self.is_fca_article(n, claim):
                other_fcas.append(n)

        lines = url2lines(fca)
        potential_titles = [l for l in lines[:3] if len(l) > 20]
        gpt_titles = self.gpt_helper.generate_headline("\n".join(lines))

        for title in tqdm.tqdm(potential_titles + gpt_titles, desc="Title generation"):
            for url in tqdm.tqdm(self.searcher.run_search(title, max_pages=1), desc="Title search"):
                if self.is_fca_article(url, claim):
                    other_fcas.append(url)
        return other_fcas
        
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json", help="Path to config file")
    parser.add_argument("--dataset_path", type=str, default="data/averifever.json")
    parser.add_argument("--output_path", type=str, default="data/averifever.with_blocklist.json")
    args = parser.parse_args()

    config_json = args.config
    searcher = GoogleSearch(config_json)
    gpt_helper = GPTSearchTermHelper(config_json)

    blocklist_creator = BlocklistCreator(searcher, gpt_helper, args.dataset_path)
    
    new_dataset = []
    for claim in blocklist_creator.make_blocklist():
        new_dataset.append(claim)

    with open(args.output_path, "w") as f:
        json.dump(new_dataset, f, indent=4)