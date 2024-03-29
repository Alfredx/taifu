
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from uuid import uuid4

import streamlit as st
from loguru import logger
from streamlit_markmap import markmap

from llm import (chat_on_paper_with_moonshot, get_rag_query,
                 get_related_concepts, get_related_questions,
                 is_answer_denying_query, summarize_chat,
                 summarize_paper_with_moonshot, summarize_query_to_name)
from search.arxiv import ArxivSearch
from search.gscholar import GoogleScholarSearch
from slides import SlidesGenerator
from structs import ChatMessage, Node

st.set_page_config(page_title="Taifu-太傅", layout="wide")


if "root_node" not in st.session_state:
    root_node = Node(name="SEARCH FOR CONCEPT",
                     query="  ", node_type="concept")
    st.session_state.root_node = root_node
if "current_node" not in st.session_state:
    st.session_state.current_node = root_node
if "query_prompt" not in st.session_state:
    st.session_state.query_prompt = "搜索论文主题>"
if "query_on_start" not in st.session_state:
    st.session_state.query_on_start = ""
if "thread_pool_executor" not in st.session_state:
    st.session_state.thread_pool_executor = ThreadPoolExecutor(4)
if "mindmap_generator" not in st.session_state:
    st.session_state.mindmap_generator = None
if "global_search_result" not in st.session_state:
    st.session_state.global_search_result = None
if "ppt_download_path" not in st.session_state:
    st.session_state.ppt_download_path = ""
if "search" not in st.session_state:
    search = GoogleScholarSearch()
    st.session_state.search = search
if "node_tree_download_path" not in st.session_state:
    st.session_state.node_tree_download_path = ""


def buildMarkmapData(node: Node, depth: int = 0) -> str:
    name = node.display_name
    if node is st.session_state.current_node:
        name = f"=={node.display_name}=="
    md_content = f"{depth*'  '}- **{name}**\n"  # \n{depth*'  '}  {node.query}
    if not node.children:
        return md_content
    for child in node.children:
        md_content += buildMarkmapData(child, depth+1)
    return md_content


def do_query(query):
    current_node = st.session_state.current_node
    if current_node is st.session_state.root_node:
        current_node.query = query
        current_node.name = query
    search = st.session_state.search
    query_result = search.search(query)
    st.session_state.query_prompt = f"主题> {query}"
    st.session_state.global_search_result = query_result

def do_more_query(length:int = 10):
    if st.session_state.global_search_result is None:
        return
    search = st.session_state.search
    query_result = search.more(length)
    st.session_state.global_search_result += query_result

def do_advanced_query(query: str, year_from: str, sort_by: str):
    current_node = st.session_state.current_node
    if current_node is st.session_state.root_node:
        current_node.query = query
        current_node.name = query
    if year_from.lower() == "unlimited":
        year_from = None
    else:
        year_from = int(year_from.split(" ")[-1])
    search = st.session_state.search
    query_result = search.search(query, year_from, sort_by.lower())
    st.session_state.query_prompt = f"主题> {query}"
    st.session_state.global_search_result = query_result


def rag_query_to_node(query, contexts, node: Node) -> None:
    node.answer = get_rag_query(query, contexts)

# def related_questions_to_node(query, contexts, node: Node) -> None:
#     node.related_questions = get_related_questions(query, contexts)


def start_chat_with_paper(current_node: Node, article):
    if current_node.node_type == "paper":
        parent_node = current_node.prev
    elif current_node.node_type == "concept":
        parent_node = current_node
    if node := parent_node.get_child_by_name(article['title']):
        st.session_state.current_node = node
    else:
        search = st.session_state.search
        node = Node(name=article['title'])
        node.article = article
        node.node_type = "paper"
        node.prev = parent_node
        parent_node.children.append(node)
        st.session_state.current_node = node
        if "arxiv.org" not in article['url']:
            node.need_upload_paper = True
        else:
            node.paper_content = search.download_and_read(article)
            node.current_stream = summarize_paper_with_moonshot(
                f"arxiv_pdf/{article['id'] + '.pdf'}", st.secrets.get('DELETE_PAPER', False))


def get_paper_related_questions(current_node: Node, summary: str):
    logger.info("getting related questions...")
    current_node.related_questions = get_related_questions(
        current_node.name, summary)
    logger.info("getting related questions...done")


def get_paper_related_concepts(current_node: Node, summary: str):
    logger.info("getting related concepts...")
    current_node.related_concepts = get_related_concepts(
        current_node.name, summary)
    logger.info("getting related concepts...done")


def display_search_result(node: Node):
    current_node = st.session_state.current_node
    if st.session_state.global_search_result is not None:
        st.text(f"Total search records: {len(st.session_state.global_search_result)}")
        for article in st.session_state.global_search_result:
            with st.container(border=True):
                col_title, col_link, col_chat_btn = st.columns([6, 1, 2])
                with col_title.container():
                    st.write(f"**{article['title']}**")
                    # st.page_link(article['url'], label=article['title'], icon="🔗", use_container_width=True, help=article['title'])
                with col_link.container():
                    st.page_link(article['url'], label="🔗"
                                , use_container_width=True)
                with col_chat_btn.container():
                    st.button("Chat", use_container_width=True,
                            key=article['id'], on_click=start_chat_with_paper, args=(current_node, article))
                with st.container(height=155, border=False):
                    author_md = ", ".join([f"[{author['name']}]({author['citation_url']})" if author['id'] else author['name'] for author in article['authors']])
                    st.write(f"{author_md} - {article['journal_ref']}, {article['publish_date']}, Cited by {article['num_citations']}")
                    st.caption(f"**Abstract:** {article['abstract']}")
        if len(st.session_state.global_search_result) < 30: # to prevent blocked by google
            _, col_next, _ = st.columns([1,1,1])
            with col_next.container():
                st.button("More", on_click=do_more_query, args=(10,), use_container_width=True)
        else:
            st.text("We only support maximum 30 records now.")
        


def on_related_concept(current_node: Node, concept: str):
    if node := current_node.get_child_by_name(concept):
        st.session_state.current_node = node
    else:
        node = Node(name=concept, node_type="concept")
        node.prev = current_node
        current_node.children.append(node)
        st.session_state.query_on_start = concept
        st.session_state.current_node = node


def on_related_question(current_node: Node, question: str):
    current_node.messages.append(ChatMessage("user", question))
    current_node.current_stream = chat_on_paper_with_moonshot(
        current_node.paper_content, current_node.messages)


def switch_to_node(node: Node):
    if not st.session_state.current_node is node:
        st.session_state.current_node = node


def remove_node(node: Node):
    prev = node.prev
    if not prev:
        return
    prev.remove_child_by_name(node.name)
    st.session_state.current_node = prev

def gen_ppt():
    gen = SlidesGenerator(st.session_state.root_node)
    gen.generate()
    filepath = gen.save()
    st.session_state.ppt_download_path = filepath

def summarize_chat_to_single_slide(current_node: Node):
    current_node.current_stream = summarize_chat(current_node.messages)
    current_node.next_stream_is_summary = True

def gen_node_tree():
    random_name = str(uuid4()).replace("-", "_") + ".taifu"
    with open(random_name, "w") as f:
        json.dump(st.session_state.root_node.to_json(), f)
    st.session_state.node_tree_download_path = random_name

def import_node_tree(import_file):
    json_obj = json.load(import_file)
    node = Node.from_json(json_obj)
    st.session_state.root_node = node
    st.session_state.current_node = node
    st.session_state.query_on_start = node.name

current_node = st.session_state.current_node
with st.sidebar:
    st.button("Generate PPT", on_click=gen_ppt, type="primary", use_container_width=True)
    if st.session_state.ppt_download_path:
        with open(st.session_state.ppt_download_path, "rb") as ppt:
            st.download_button("Download", data=ppt, file_name=st.session_state.ppt_download_path, use_container_width=True)
    st.divider()
    st.write("Previous Node")
    if current_node.prev:
        def on_prev_click(prev):
            st.session_state.current_node = prev
        st.button(current_node.prev.display_name, use_container_width=True,
                  type="secondary", on_click=on_prev_click, args=(current_node.prev,))
    st.write("Current Node")
    if current_node:
        st.button(f"{current_node.display_name}", use_container_width=True,
                  type="primary", disabled=True)
        if current_node.prev:
            st.button("REMOVE NODE", use_container_width=True,
                      type="primary", on_click=remove_node, args=(current_node, ))
    st.write("Child nodes")
    for child in current_node.children:
        st.button(child.display_name, on_click=switch_to_node, args=(child, ))

    st.divider()
    st.text("导出/入脑图")
    st.button("Export", on_click=gen_node_tree, use_container_width=True)
    if st.session_state.node_tree_download_path:
        with open(st.session_state.node_tree_download_path, "rb") as node_tree:
            st.download_button("Download", data=node_tree, file_name=st.session_state.node_tree_download_path, use_container_width=True)

    with st.form("my-form", clear_on_submit=True, border=False):
        file = st.file_uploader("import", "taifu", label_visibility="collapsed")
        submitted = st.form_submit_button("Import", use_container_width=True)
        if submitted and file is not None:
            import_node_tree(file)


col_left, col_right = st.columns([2, 3])
with col_left.container():
    current_node = st.session_state.current_node
    data = buildMarkmapData(st.session_state.root_node)
    with st.container(border=True, height=250):
        markmap(data, height=200)
    use_arxiv_only = st.checkbox("Only search from arxiv.org")
    col_search_bar, col_advanced = st.columns([4,1])
    with col_search_bar.container():
        if query := st.chat_input(st.session_state.query_prompt):
            if use_arxiv_only:
                query += " site:arxiv.org"
            do_query(query)
            st.rerun()
    with col_advanced.container():
        popover = st.popover("高级", help="高级搜索")
        query = popover.text_input("Topic AND/OR Author")
        if use_arxiv_only:
            query += " site:arxiv.org"
        unlimited = "Unlimited"
        this_year = f"Since {date.today().year}"
        last_year = f"Since {date.today().year - 1}"
        four_years_ago = f"Since {date.today().year - 4}"
        date_range = popover.selectbox("Published Year", [unlimited, this_year, last_year, four_years_ago])
        sort_by = popover.selectbox("Sort by", ["Relevance", "Date"])
        popover.button("Search", type="primary", on_click=do_advanced_query, args=(query, date_range, sort_by))
    # render current node
    display_search_result(current_node)
with col_right.container():
    current_node = st.session_state.current_node
    if current_node.article:
        st.markdown(f"### {current_node.article['title']}")
        if current_node.need_upload_paper:
            st.write("We currently don't support reading paper from this website.")
            if paper := st.file_uploader("But you can upload by yourself. Choose a PDF file:", type="pdf"):
                bytes_data = paper.read()
                filepath = current_node.article['title'].lower().replace(" ", "_") + ".pdf"
                with open(filepath, "wb") as f:
                    f.write(bytes_data)
                current_node.need_upload_paper = False
                current_node.current_stream = summarize_paper_with_moonshot(filepath, True)
                st.rerun()
            st.divider()
            col_no_paper_hint, _, col_drop_paper = st.columns([2,1,1])
            with col_no_paper_hint.container():
                st.write("Haven't obtained this paper?")
            with col_drop_paper.container():
                popover = st.popover("Drop it", use_container_width=True)
                popover.button("Confirm", on_click=remove_node, args=(current_node,), type="primary", use_container_width=True)
    # with col_cite.container():
    #     st.button("Cite me", type="primary", use_container_width=True)
    # Chat part
    else:
        search_result = st.session_state.global_search_result
        if search_result:
            sorted_search_result = sorted(search_result, key=lambda x: x['num_citations'], reverse=True)
            st.write(f"#### {st.session_state.query_prompt}")
            st.write("You may interested in (most cited from current search results):")
            for article in sorted_search_result[:3]:
                with st.container(border=True):
                    col_title, col_link, col_chat_btn = st.columns([6, 1, 2])
                    with col_title.container():
                        st.write(f"**{article['title']}**")
                    with col_link.container():
                        st.page_link(article['url'], label="🔗"
                                    , use_container_width=True)
                    with col_chat_btn.container():
                        st.button("Chat", use_container_width=True,
                                key=f"interest_{article['id']}", on_click=start_chat_with_paper, args=(current_node, article))
                    with st.container(border=False):
                        author_md = ", ".join([f"[{author['name']}]({author['citation_url']})" if author['id'] else author['name'] for author in article['authors']])
                        st.write(f"{author_md} - {article['journal_ref']}, {article['publish_date']}, Cited by {article['num_citations']}")
                        st.caption(f"**Abstract:** {article['abstract']}")
        
    for message in current_node.messages:
        if not message.skip:
            with st.chat_message(message.role):
                st.write(message.message, unsafe_allow_html=True)
    if current_node.chat_summary:
        with st.chat_message("assistant"):
            st.write(f"**[ Here is the summary of chats above. You may expect this in your PPT. ]** \n\n {current_node.chat_summary}")
    if current_node.current_stream:
        with st.chat_message("assistant"):
            logger.info("start writing stream...")
            response = st.write_stream(current_node.current_stream)
        logger.info("stream chat written.")
        if current_node.next_stream_is_summary:
            current_node.chat_summary = response
            current_node.next_stream_is_summary = False
        else:
            message = ChatMessage(role="assistant", message=response)
            current_node.messages.append(message)
        current_node.current_stream = None
        if not current_node.related_questions:
            get_paper_related_questions(current_node, response)
        if not current_node.related_concepts:
            get_paper_related_concepts(current_node, response)
        st.rerun()

    if current_node.messages and not current_node.current_stream:
        col_related_questions, col_related_concepts = st.columns([1, 1])
        with col_related_questions.container():
            if current_node.related_questions:
                st.write("Related question:")
                for q in current_node.related_questions:
                    st.button(q['question'], on_click=on_related_question, args=(
                        current_node, q['question'],), key=q['question'], use_container_width=True)
        with col_related_concepts.container():
            if current_node.related_concepts:
                st.write("Related concepts:")
                for concept in current_node.related_concepts:
                    st.button(concept['concept'], on_click=on_related_concept, args=(
                        current_node, concept['concept']), key=concept['concept'], use_container_width=True)
        if chat := st.chat_input("对论文提问>"):
            current_node.messages.append(ChatMessage("user", chat))
            current_node.current_stream = chat_on_paper_with_moonshot(
                current_node.paper_content, current_node.messages)
            st.rerun()
        st.divider()
        col1, col_summary_to_ppt, col_drop_paper = st.columns([2,1,1])
        with col1.container():
            st.write("Satisfied with answer?")
        with col_summary_to_ppt.container():
            if current_node.messages:
                st.button("Summay into PPT", on_click=summarize_chat_to_single_slide, args=(current_node,), use_container_width=True)
        with col_drop_paper.container():
            popover = st.popover("Drop it", use_container_width=True)
            popover.button("Confirm", on_click=remove_node, args=(current_node,), type="primary", use_container_width=True)

    if query_on_start := st.session_state.query_on_start:
        st.session_state.query_on_start = ""
        do_query(query_on_start)
        st.rerun()
