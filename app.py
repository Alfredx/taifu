
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import streamlit as st
from streamlit_markmap import markmap

from search.bing import BingSearch
from search.arxiv import ArxivSearch
from llm import get_rag_query, get_related_questions, summarize_query_to_name, is_answer_denying_query

st.set_page_config(page_title="Taifu-太傅", layout="wide")

@dataclass
class Node(object):
    """Docstring for Node."""
    prev: "Node" = None
    children: list["Node"] = field(default_factory=list)
    name: str = ""
    query: str = ""
    answer: str = ""
    search_result: str = ""
    related_questions: str = ""

    def get_child_by_name(self, name: str) -> "Node":
        for child in self.children:
            if child.name == name:
                return child
        return None


if "root_node" not in st.session_state:
    root_node = Node(name="root placeholder", query="  ")
    st.session_state.root_node = root_node
if "current_node" not in st.session_state:
    st.session_state.current_node = root_node
if "query_prompt" not in st.session_state:
    st.session_state.query_prompt = "何以治学？"
if "query_on_start" not in st.session_state:
    st.session_state.query_on_start = ""
if "thread_pool_executor" not in st.session_state:
    st.session_state.thread_pool_executor = ThreadPoolExecutor(4)
if "mindmap_generator" not in st.session_state:
    st.session_state.mindmap_generator = None

bing_search = BingSearch(st.secrets["BING_SEARCH_SUB_KEY"])


def buildMarkmapData(node: Node, depth: int = 0) -> str:
    name = node.name
    if node is st.session_state.current_node:
        name = f"=={node.name}=="
    md_content = f"{depth*'  '}- **{name}**\n{depth*'  '}  {node.query}\n"
    if not node.children:
        return md_content
    for child in node.children:
        md_content += buildMarkmapData(child, depth+1)
    return md_content

def do_query(query):
    st.session_state.query_prompt = query
    current_node.query = query
    current_node.name = summarize_query_to_name(query)
    query_result = bing_search.search(query)
    current_node.search_result = query_result
    contexts = query_result["value"]
    current_node.answer = get_rag_query(query, contexts)
    more_related_questions = get_related_questions(query, contexts)
    current_node.related_questions = more_related_questions
    st.rerun()

def rag_query_to_node(query, contexts, node: Node) -> None:
    node.answer = get_rag_query(query, contexts)

def related_questions_to_node(query, contexts, node: Node) -> None:
    node.related_questions = get_related_questions(query, contexts)

def query_and_auto_mindmap(query: str, current_node: Node, depth: int = 0, max_depth: int = 1):
    print(f"start query: {query}")
    current_node.query = query
    current_node.name = summarize_query_to_name(query)
    print(f"summarized title as {current_node.name}")
    query_result = bing_search.search(query)
    current_node.search_result = query_result
    print(f"searched result: {len(query_result['value'])}")
    contexts = query_result["value"]
    rag_query_to_node(query, contexts, current_node)
    print(f"summarized query result")
    if is_answer_denying_query(query, current_node.answer):
        yield current_node
        return None
    related_questions = get_related_questions(query, current_node.answer)
    print(f"got related questions: {related_questions}")
    current_node.related_questions = related_questions
    yield current_node
    if depth >= max_depth:
        return None
    for q in related_questions:
        node = Node(prev=current_node)
        current_node.children.append(node)
        for node in query_and_auto_mindmap(q['question'], node, depth+1, max_depth):
            if node:
                yield node
            continue


col_left, col_right = st.columns([1, 1])
with col_left.container():
    data = buildMarkmapData(st.session_state.root_node)
    markmap(data)
with col_right.container():
    current_node = st.session_state.current_node
    col_prev, col_current, col_next = st.columns([1, 1, 1])
    with col_prev.container():
        st.write("Previous Node")
        if current_node.prev:
            def on_prev_click(prev):
                st.session_state.current_node = prev
            st.button(current_node.prev.name, use_container_width=True,
                    type="secondary", on_click=on_prev_click, args=(current_node.prev,))
    with col_current.container():
        st.write("Current Node")
        if current_node:
            st.button(f"{current_node.name}", use_container_width=True,
                    type="primary", disabled=True)
    with col_next.container():
        st.write("Child nodes")
        option = st.selectbox('Child nodes',
                            [child.name for child in current_node.children],
                            label_visibility="collapsed", index=None)
        if option and option != current_node.name:
            if child := current_node.get_child_by_name(option):
                st.session_state.current_node = child
                st.rerun()
    
    if query := st.chat_input(st.session_state.query_prompt):
        mindmap_generator = query_and_auto_mindmap(query, current_node, depth=0, max_depth=2)
        st.session_state.mindmap_generator = mindmap_generator
        st.rerun()
        # for node in query_and_auto_mindmap(query, current_node, depth=0, max_depth=2):
        #     st.session_state.current_node = node
    # render current node
    if current_node.search_result:
        col_answer, col_search = st.columns([1, 1])
        with col_answer.container():
            st.markdown(current_node.answer, unsafe_allow_html=True)
        with col_search.container():
            for index, content in enumerate(current_node.search_result["value"]):
                st.markdown(f"[\[{index+1}\]{content['name']}]({content['url']})",
                            unsafe_allow_html=True)
    if current_node.related_questions:
        st.write("相关问题：")
        for q in current_node.related_questions:
            def add_node(query):
                node = Node(prev=current_node,
                            name=summarize_query_to_name(query), query=query)
                current_node.children.append(node)
                st.session_state.query_on_start = query
                st.session_state.current_node = node
            st.button(q['question'], on_click=add_node, args=(q['question'],))

    if query_on_start := st.session_state.query_on_start:
        st.session_state.query_on_start = ""
        do_query(query_on_start)
    
    if mindmap_generator:= st.session_state.mindmap_generator:
        try:
            node = mindmap_generator.__next__()
            if node:
                st.session_state.current_node = node
                st.rerun()
        except StopIteration as e:
            st.session_state.mindmap_generator = None
        except ValueError as e:
            pass

