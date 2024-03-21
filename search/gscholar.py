import os

import fitz
import requests
import streamlit as st
from loguru import logger
from scholarly import scholarly


class GoogleScholarSearch(object):
    def __init__(self) -> None:
        self.last_query = None

    def search(self, content: str, year_from: int = None, sort_by: str = "relevance"):
        query_str = f"{content}"
        query = scholarly.search_pubs(
            query_str, year_low=year_from, sort_by=sort_by)
        self.last_query = query
        articles = []
        for _ in range(10):
            try:
                r = next(query)
                article = self._build_article(r)
                articles.append(article)
            except StopIteration as e:
                break
        return articles

    def more(self, length: int = 10):
        if not self.last_query or length >= 30:
            logger.warning(f"no last_query or too large length")
            return []
        articles = []
        for _ in range(length):
            try:
                r = next(self.last_query)
                article = self._build_article(r)
                articles.append(article)
            except StopIteration as e:
                break
        return articles

    def _build_article(self, r):
        authors = []
        for i, name in enumerate(r['bib']['author']):
            author_id = r['author_id'][i]
            authors.append({
                'name': name,
                'id': author_id,
                'citation_url': f"https://scholar.google.com/citations?user={author_id}"
            })
        article = {
            'id': r['pub_url'].split('/abs/')[-1],
            'term': '',
            'terms': '',
            'main_author': r['bib']['author'][0],
            'authors': authors,
            'url': r['pub_url'],
            'pdf_url': r.get('eprint_url', r['pub_url'].replace('abs', 'pdf')),
            'title': r['bib']['title'],
            'abstract': r['bib']['abstract'],
            'update_date': '',
            'publish_date': r['bib']['pub_year'],
            'comment': '',
            'journal_ref': r['bib']['venue'],
            'num_citations': r['num_citations']
        }
        return article

    def download_and_read(self, article: dict) -> str:
        pdf_dir = "arxiv_pdf"
        if not os.path.isdir(pdf_dir):
            os.mkdir(pdf_dir)
        filename = f"{pdf_dir}/{article['id'] + '.pdf'}"
        logger.info(f"downloading arxiv pdf... {filename}")
        if not os.path.exists(filename):
            pdf_url = article['pdf_url']
            if mirror_url := st.secrets.get("ARXIV_DOWNLOAD_URL", ""):
                pdf_url = article['pdf_url'].replace(
                    "https://arxiv.org", mirror_url)
            r = requests.get(article['pdf_url'].replace(
                "html", "pdf"), allow_redirects=True)
            with open(filename, "wb") as f:
                f.write(r.content)
        text = ""
        logger.info(f"reading pdf...")
        with fitz.open(filename) as doc:
            for page in doc:
                text += page.get_text()
        logger.info(f"reading pdf...done")
        return text
