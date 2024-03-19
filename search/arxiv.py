from typing import List
from loguru import logger
import fitz
import requests
import os
import feedparser
from dateutil import parser


class ArxivSearch(object):
    """
    see also: https://info.arxiv.org/help/api/user-manual.html
    """

    def search(self, content: str | List[str]):
        search_query = f"all:{content}"
        if isinstance(content, list):
            search_query = "+AND+".join([f"all:{e}" for e in content])
        search_query = search_query.replace(" ", "+")
        logger.info(f"Start ARXIV query: {search_query}")
        # articles = arxivpy.query(
        #     search_query=search_query, results_per_iteration=20, max_index=20, sort_by="relevance")
        articles = []
        response = requests.get(f"http://export.arxiv.org/api/query?search_query={search_query}&sortBy=relevance")
        entries = feedparser.parse(response.content.decode())
        for entry in entries['entries']:
            if entry['title'] == 'Error':
                print('Error %s' % entry['summary'])
            main_term = entry['arxiv_primary_category']['term']
            terms = '|'.join([tag['term'] for tag in entry['tags']])
            main_author = entry['author']
            update_date = parser.parse(entry['updated'])
            authors = ', '.join([author['name'].strip() for author in entry['authors']])
            url = entry['link']
            for e in entry['links']:
                if 'title' in e.keys():
                    if e['title'] == 'pdf':
                        pdf_url = e['href']
                else:
                    pdf_url = 'http://arxiv.org/pdf/%s' % url.split('/abs/')[-1]
            if 'arxiv_comment' in entry.keys():
                comment = entry['arxiv_comment']
            else:
                comment = 'No comment found'
            if 'journal_ref' in entry.keys():
                journal_ref = entry['journal_ref']
            else:
                journal_ref = 'No journal ref found'

            title = entry['title_detail']['value'].replace('\n', ' ').strip()
            abstract = entry['summary'].replace('\n', ' ')
            publish_date = parser.parse(entry['published'])
            article = {'id': url.split('/abs/')[-1],
                       'term': main_term,
                       'terms': terms,
                       'main_author': main_author,
                       'authors': authors,
                       'url': url,
                       'pdf_url': pdf_url,
                       'title': title,
                       'abstract': abstract,
                       'update_date': update_date,
                       'publish_date': publish_date,
                       'comment': comment,
                       'journal_ref': journal_ref}
            articles.append(article)
        logger.info(f"found {len(articles)} articles")
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


if __name__ == "__main__":
    search = ArxivSearch()
    result = search.search("attention")
    for q in result:
        print(q)
