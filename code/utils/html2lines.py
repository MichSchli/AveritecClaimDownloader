from distutils.command.config import config
import requests
from time import sleep
import trafilatura
from trafilatura.meta import reset_caches
from trafilatura.settings import DEFAULT_CONFIG
import sys
from bs4 import BeautifulSoup, CData, NavigableString, Tag
import html2text
import re

DEFAULT_CONFIG.MAX_FILE_SIZE = 50000

def get_page(url):
    page = None
    for i in range(5):
        try:
            page = trafilatura.fetch_url(url, config=DEFAULT_CONFIG)
            assert page is not None
            break
        except:
            sleep(3)
    return page

def url2lines_html2text(url):
    h = html2text.HTML2Text()
    h.ignore_links = True
    h.ignore_images = True

    res = requests.get(url)
    html_page = res.content

    return [x.strip() for x in h.handle(str(html_page)).replace("\\n", " ").replace("\\t", " ").split("\n") if x.strip()]



def find_divs_and_ps_with_href(html, target_url):
    soup = BeautifulSoup(html, 'html.parser')
    target_url_plain = re.sub(r'https?://web\.archive\.org/web/\d+/(.*)', r'\1', target_url)

    results = []

    def has_target_url(tag):
        if isinstance(tag, Tag) and tag.name == 'a' and tag.get('href'):
            href = tag['href']
            if target_url_plain in href:
                return True
        return False

    for tag in soup.find_all(has_target_url):
        parent_div = tag.find_parent('div')
        parent_p = tag.find_parent('p')

        if parent_div:
            text_parts = []
            hrefs = []

            for content in parent_div.contents:
                if isinstance(content, Tag) and content.name == 'a':
                    if target_url_plain in content['href']:
                        text_parts.append(str(content))
                    else:
                        text_parts.append(content.get_text())
                    hrefs.append(content['href'])
                elif isinstance(content, str):
                    text_parts.append(content)

            text = ' '.join(text_parts).strip()
            if text:
                results.append(text)

        if parent_p:
            text_parts = []
            hrefs = []

            for content in parent_p.contents:
                if isinstance(content, Tag) and content.name == 'a':
                    if target_url_plain in content['href']:
                        text_parts.append(str(content))
                    else:
                        text_parts.append(content.get_text())
                    hrefs.append(content['href'])
                elif isinstance(content, str):
                    text_parts.append(content)

            text = ' '.join(text_parts).strip()
            if text:
                results.append(text)

    return results

def url2lines_find_link(url, target_url):
    res = requests.get(url)
    html_page = res.content
    text = find_divs_and_ps_with_href(html_page, target_url)
    return text

def url2lines(url):
    page = get_page(url)

    if page is None:
        return []
    
    lines = html2lines(page)
    return lines

def html2lines(page):
    out_lines = []

    if len(page.strip()) == 0 or page is None:
        return out_lines
    

    text = trafilatura.extract(page, config=DEFAULT_CONFIG)
    reset_caches()

    if text is None:
        return out_lines

    return text.split("\n") # We just spit out the entire page, so need to reformat later.