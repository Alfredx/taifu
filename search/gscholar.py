from scholarly import scholarly
import os
from loguru import logger
import requests
import fitz

class GoogleScholarSearch(object):

    def search(self, content: str):
        query_str = f"{content} site:arxiv.org"
        query = scholarly.search_pubs(query_str)
        articles = []
        for i in range(10):
            r = next(query)
            article = {
                'id': r['pub_url'].split('/abs/')[-1],
                'term': '',
                'terms': '',
                'main_author': r['bib']['author'][0],
                'authors': ", ".join(r['bib']['author']),
                'url': r['pub_url'],
                'pdf_url': r['eprint_url'],
                'title': r['bib']['title'],
                'abstract': r['bib']['abstract'],
                'update_date': '',
                'publish_date': r['bib']['pub_year'],
                'comment': '',
                'journal_ref': '',
                'num_citations': r['num_citations']
            }
            articles.append(article)
        return articles

    def download_and_read(self, article: dict) -> str:
        pdf_dir = "arxiv_pdf"
        if not os.path.isdir(pdf_dir):
            os.mkdir(pdf_dir)
        filename = f"{pdf_dir}/{article['id'] + '.pdf'}"
        logger.info(f"downloading arxiv pdf... {filename}")
        if not os.path.exists(filename):
            r = requests.get(article['pdf_url'], allow_redirects=True)
            with open(filename, "wb") as f:
                f.write(r.content)
        text = ""
        logger.info(f"reading pdf...")
        with fitz.open(filename) as doc:
            for page in doc:
                text += page.get_text()
        logger.info(f"reading pdf...done")
        return text