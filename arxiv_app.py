
from datetime import date
from concurrent.futures import ThreadPoolExecutor

import streamlit as st
from loguru import logger
from streamlit_markmap import markmap

from llm import (chat_on_paper_with_moonshot, get_rag_query,
                 get_related_concepts, get_related_questions,
                 is_answer_denying_query, summarize_paper_with_moonshot,
                 summarize_query_to_name)
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

search = GoogleScholarSearch()


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
    query_result = search.search(query)
    st.session_state.query_prompt = f"主题> {query}"
    st.session_state.global_search_result = query_result

def do_advanced_query(query: str, year_from: str, sort_by: str):
    current_node = st.session_state.current_node
    if current_node is st.session_state.root_node:
        current_node.query = query
        current_node.name = query
    if year_from.lower() == "unlimited":
        year_from = None
    else:
        year_from = int(year_from.split(" ")[-1])
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
        node = Node(name=article['title'])
        node.article = article
        node.node_type = "paper"
        node.paper_content = search.download_and_read(article)
        node.prev = parent_node
        parent_node.children.append(node)
        st.session_state.current_node = node
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
                    author_md = ", ".join([f"[{author['name']}](https://scholar.google.com/citations?user={author['id']})" if author['id'] else author['name'] for author in article['authors']])
                    st.write(f"{author_md} - {article['journal_ref']}, {article['publish_date']}, Cited by {article['num_citations']}")
                    st.caption(f"**Abstract:** {article['abstract']}")


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
col_left, col_right = st.columns([2, 3])
with col_left.container():
    current_node = st.session_state.current_node
    data = buildMarkmapData(st.session_state.root_node)
    with st.container(border=True, height=250):
        markmap(data, height=200)
    col_search_bar, col_advanced = st.columns([4,1])
    with col_search_bar.container():
        if query := st.chat_input(st.session_state.query_prompt):
            do_query(query)
            st.rerun()
    with col_advanced.container():
        popover = st.popover("高级", help="高级搜索")
        query = popover.text_input("Topic AND/OR Author")
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
    # with col_cite.container():
    #     st.button("Cite me", type="primary", use_container_width=True)
    # Chat part
    for message in current_node.messages:
        with st.chat_message(message.role):
            st.write(message.message)
    if current_node.current_stream:
        with st.chat_message("assistant"):
            logger.info("start writing stream...")
            response = st.write_stream(current_node.current_stream)
        logger.info("stream chat written.")
        current_node.messages.append(ChatMessage(
            role="assistant", message=response))
        current_node.current_stream = None
        if not current_node.related_questions:
            get_paper_related_questions(current_node, response)
        if not current_node.related_concepts:
            get_paper_related_concepts(current_node, response)

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

    if query_on_start := st.session_state.query_on_start:
        st.session_state.query_on_start = ""
        do_query(query_on_start)
        st.rerun()
