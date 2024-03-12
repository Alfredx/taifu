import json
import time
import traceback
from dataclasses import dataclass, field
from typing import List

import streamlit as st
from openai import OpenAI
from streamlit_markmap import markmap
from typing_extensions import Annotated

import tool
from bing import BingSearch

st.set_page_config(page_title="Taifu-太傅", layout="wide")


class LLMModel(object):
    def __init__(self, api_key: str,  model: str, model_params: dict[str, float | int] = {}, api_base: str = ''):
        super(LLMModel, self).__init__()
        self.api_key = api_key
        self.api_base = api_base
        self.model = model
        self.model_params = model_params
        self.client = OpenAI(api_key=self.api_key)

    def ask_question(self, system_prompt: str, user_prompt: str) -> str:
        start = time.time()
        completions = self.client.chat.completions
        response = completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        print(f"llm api call time cost: {time.time() - start} seconds")
        result = response.choices[0].message
        return result


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

bing_search = BingSearch(st.secrets["BING_SEARCH_SUB_KEY"])
llm = LLMModel(
    api_key=st.secrets['OPENAI_API_KEY'], model='gpt-4-0125-preview')


def buildMarkmapData(node: Node, depth: int = 0) -> str:
    md_content = f"{depth*'  '}- **{node.name}**\n{depth*'  '}  {node.query}\n"
    if not node.children:
        return md_content
    for child in node.children:
        md_content += buildMarkmapData(child, depth+1)
    return md_content

_rag_query_text = """
You are a large language AI assistant built by Lepton AI. You are given a user question, and please write clean, concise and accurate answer to the question. You will be given a set of related contexts to the question, each starting with a reference number like [[citation:x]], where x is a number. Please use the context and cite the context at the end of each sentence if applicable.

Your answer must be correct, accurate and written by an expert using an unbiased and professional tone. Please limit to 1024 tokens. Do not give any information that is not related to the question, and do not repeat. Say "information is missing on" followed by the related topic, if the given context do not provide sufficient information.

Please cite the contexts with the reference numbers, in the format [citation:x]. If a sentence comes from multiple contexts, please list all applicable citations, like [citation:3][citation:5]. Other than code and specific names and citations, your answer must be written in the same language as the question.

Here are the set of contexts:

{context}

Remember, don't blindly repeat the contexts verbatim. And here is the user question:
"""

_more_questions_prompt = """
You are a helpful assistant that helps the user to ask related questions, based on user's original question and the related contexts. Please identify worthwhile topics that can be follow-ups, and write questions no longer than 20 words each. Please make sure that specifics, like events, names, locations, are included in follow up questions so they can be asked standalone. For example, if the original question asks about "the Manhattan project", in the follow up question, do not just say "the project", but use the full name "the Manhattan project". Your related questions must be in the same language as the original question.

Here are the contexts of the question:

{context}

Remember, based on the original question and related contexts, suggest three such further questions. Do NOT repeat the original question. Each related question should be no longer than 20 words. Here is the original question:
"""

def get_rag_query(query, contexts):
    stop_words = [
        "<|im_end|>",
        "[End]",
        "[end]",
        "\nReferences:\n",
        "\nSources:\n",
        "End.",
    ]

    system_prompt = _rag_query_text.format(
            context="\n\n".join(
                [f"[[citation:{i+1}]] {c['snippet']}" for i, c in enumerate(contexts)]
            )
        )
    response = llm.client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ],
        max_tokens=1024,
        temperature=0.9,
    )
    return response.choices[0].message.content

def get_related_questions(query, contexts):
    """
    Gets related questions based on the query and context.
    """

    def ask_related_questions(
        questions: Annotated[
            List[str],
            [
            (
                "question",
                Annotated[str, "related question to the original question and context."],
            )],
        ]
    ):
        """
        ask further questions that are related to the input and output.
        """
        pass

    try:
        response = llm.client.chat.completions.create(
            model=llm.model,
            messages=[
                {
                    "role": "system",
                    "content": _more_questions_prompt.format(
                        context="\n\n".join([c["snippet"] for c in contexts])
                    ),
                },
                {
                    "role": "user",
                    "content": query,
                },
            ],
            tools=[{
                "type": "function",
                "function": tool.get_tools_spec(ask_related_questions),
            }],
            max_tokens=512,
        )
        related = response.choices[0].message.tool_calls[0].function.arguments
        if isinstance(related, str):
            related = json.loads(related)
        print(f"Related questions: {related}")
        return related["questions"][:5]
    except Exception as e:
        # For any exceptions, we will just return an empty list.
        print(
            "encountered error while generating related questions:"
            f" {e}\n{traceback.format_exc()}"
        )
        return []

def summarize_query_to_name(query):
    response = llm.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Extract the noun phrase from user's question. Your answer must be in the same language as the original question. Here is the original question: "
                },
                {
                    "role": "user",
                    "content": query,
                },
            ],
            max_tokens=512,
        )
    return response.choices[0].message.content

# for i in range(5):
#     i_node = Node(name=f"i{i}", query=f"q-i{i}", prev=st.session_state.root_node)
#     for j in range(3):
#         j_node = Node(name=f"j{j}", query=f"q-j{j}", prev=i_node)
#         for k in range(2):
#             k_node = Node(name=f"k{k}", query=f"q-k{k}", prev=j_node)
#             j_node.children.append(k_node)
#         i_node.children.append(j_node)
#     st.session_state.root_node.children.append(i_node)


col_left, col_right = st.columns([1, 1])

with col_left.container():
    data = buildMarkmapData(st.session_state.root_node)
    markmap(data)

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
                              (child.name for child in current_node.children),
                              label_visibility="collapsed")
        if option != current_node.name:
            if child := current_node.get_child_by_name(option):
                st.session_state.current_node = child
    if query := st.chat_input(st.session_state.query_prompt):
        do_query(query)
    # render current node
    if current_node.search_result:
        col_answer, col_search = st.columns([1,1])
        with col_answer.container():
            st.markdown(current_node.answer)
        with col_search.container():    
            for index, content in enumerate(current_node.search_result["value"]):
                st.markdown(f"[\[{index+1}\]{content['name']}]({content['url']})",
                            unsafe_allow_html=True)
    if current_node.related_questions:
        st.write("相关问题：")
        for q in current_node.related_questions:
            def add_node(query):
                node = Node(prev=current_node, name=summarize_query_to_name(query), query=query)
                current_node.children.append(node)
                st.session_state.query_on_start = query
                st.session_state.current_node = node
            st.button(q['question'], on_click=add_node, args=(q['question'],))

    
    if query_on_start := st.session_state.query_on_start:
        st.session_state.query_on_start = ""
        do_query(query_on_start)
