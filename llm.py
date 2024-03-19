import json
import os
import time
import traceback
from pathlib import Path
from typing import List

import streamlit as st
from openai import OpenAI
from typing_extensions import Annotated

import tool


class LLMModel(object):
    def __init__(self, api_key: str,  model: str, model_params: dict[str, float | int] = {}, api_base: str = ''):
        super(LLMModel, self).__init__()
        self.api_key = api_key
        self.api_base = api_base
        self.model = model
        self.model_params = model_params
        if api_base:
            self.client = OpenAI(api_key=self.api_key, base_url=api_base)
        else:
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

_more_questions_prompt2 = """
你是一个十分有用的助理，你的任务是从提供给你的上下文中，找出至少三个更进一步的问题，来对用户的问题进行追问。首先你需要找出值得进一步深入研究的知识点，然后针对每一个知识点给出不超过20个字的后续问题。请一步一步来完成这件事。
请确保你会保留原始问题中具体的事件，名称，地点以便每个追问可以独立提问。例如，如果原始问题中包含“曼哈顿计划“，那么在后续问题中，不要仅仅说“该计划”，而是要完整得说“曼哈顿计划”。
请确保你的追问是提及了上下文中的细节。例如，原始问题是“孙子兵法主要内容是什么？”，提供给你的上下文是“孙子兵法主要包含了大战略观、全胜思想、战胜思想、治军理念等”，那么你首先要找到深入的知识点是“大战略观”、“全胜思想”、“战胜思想”、“治军理念”，下一步的追问应该是“孙子兵法的大战略观主要讲了什么？”、“孙子兵法的全胜思想主要讲了什么？”等。
你针对深入知识点所提出的问题必须要和原始问题用相同的语言。

请千万记住，不要重复原始问题。请千万记住，提出至少三个问题，每一个后续问题不能超过20个字。这是原始问题：
"""

_more_questions_prompt3 = """
You are a helpful assistant that helps the user to ask related questions about a paper. You are going to do these in two steps. First Identify worthwhile concepts that can be follow-ups. Second write questions no longer than 20 words about each concept. Do these step by step. Make sure that specifics, like events, names, locations, are included in the questions so they can be asked standalone. For example, if the concept is "the Manhattan project", in the question, do not just say "the project", but use the full name "the Manhattan project".
"""
_more_concepts_prompt = """
You are a helpful assistant that helps the user to ask related concepts about a paper. You are going to do these in two steps. First Identify worthwhile concepts that can be follow-ups. Second filter out the concepts that are not fully explained in the paper. Do it step by step. Make sure that specifics, like events, names, locations, are included in the concepts so they can be asked standalone. For example, if the concept is "the Manhattan project", do not just say "the project", but use the full name "the Manhattan project".
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
                [f"[[citation:{i+1}]] {c['snippet']}" for i,
                    c in enumerate(contexts)]
        )
    )
    llm = LLMModel(
        api_key=st.secrets['OPENAI_API_KEY'], model='gpt-4-0125-preview')
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
        questions: Annotated[List[str],
                             [(
                                 "question",
                                 Annotated[str, "针对上下文的相关知识点提出的追问。"],
                             )],
                             ]
    ):
        """
        ask further questions that are related to the input and output.
        """
        pass

    try:
        llm = LLMModel(
            api_key=st.secrets['OPENAI_API_KEY'], model='gpt-4-0125-preview')
        response = llm.client.chat.completions.create(
            model="gpt-3.5-turbo",
            # model=llm.model,
            messages=[
                {
                    "role": "system",
                    "content": _more_questions_prompt3
                },
                {
                    "role": "user",
                    "content": f"read this paper for me. {query}",
                },
                {
                    "role": "assistant",
                    "content": contexts
                },
                {
                    "role": "user",
                    "content": "I'll give you 500 dollars for better results. Give me THREE more related questions about the topics I might want to know."
                }
            ],
            tools=[{
                "type": "function",
                "function": tool.get_tools_spec(ask_related_questions),
            }],
            max_tokens=1024,
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
    
def get_related_concepts(query, contexts):
    """
    Gets related concepts based on the query and context.
    """

    def ask_related_concepts(
        concepts: Annotated[List[str],
                             [(
                                 "concept",
                                 Annotated[str, "Concept that metioned but not fully explained in the paper"],
                             )],
                             ]
    ):
        """
        ask related concepts metioned but not fully explained in the paper.
        """
        pass

    try:
        llm = LLMModel(
            api_key=st.secrets['OPENAI_API_KEY'], model='gpt-4-0125-preview')
        response = llm.client.chat.completions.create(
            model="gpt-3.5-turbo",
            # model=llm.model,
            messages=[
                {
                    "role": "system",
                    "content": _more_concepts_prompt
                },
                {
                    "role": "user",
                    "content": f"read this paper for me. {query}",
                },
                {
                    "role": "assistant",
                    "content": contexts
                },
                {
                    "role": "user",
                    "content": "I'll give you 500 dollars for better results! Give me FIVE more related concepts mentioned in the paper that I might want to know more in other papers."
                }
            ],
            tools=[{
                "type": "function",
                "function": tool.get_tools_spec(ask_related_concepts),
            }],
            max_tokens=1024,
        )
        related = response.choices[0].message.tool_calls[0].function.arguments
        if isinstance(related, str):
            related = json.loads(related)
        print(f"Related concepts: {related}")
        return related["concepts"][:5]
    except Exception as e:
        # For any exceptions, we will just return an empty list.
        print(
            "encountered error while generating related questions:"
            f" {e}\n{traceback.format_exc()}"
        )
        return []
    

def chat_on_paper_with_moonshot(paper_content, messages):
    llm = LLMModel(
        api_key=st.secrets['MOONSHOT_API_KEY'], model='moonshot-v1-128k', api_base="https://api.moonshot.cn/v1")
    messages_for_completion = [
        {
            "role": "system",
            "content": "You are Kimi, an AI paper reading assistant created by Moonshot."
        },
        {
            "role": "system",
            "content": paper_content,
        },
        {
            "role": "user",
            "content": "read this paper for me."
        }
    ]
    messages_for_completion += [
        {
            "role": m.role,
            "content": m.message,
        } for m in messages
    ]
    stream = llm.client.chat.completions.create(
        model=llm.model,
        messages=messages_for_completion,
        stream=True,
    )
    return stream


def summarize_query_to_name(query):
    llm = LLMModel(
        api_key=st.secrets['OPENAI_API_KEY'], model='gpt-4-0125-preview')
    response = llm.client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant. Extract the noun phrase from user's question. Your answer must be in the same language as the original question. Remember, this is important to me, ONLY output the noun phrase. Here is the original question: "
            },
            {
                "role": "user",
                "content": query,
            },
        ],
        max_tokens=512,
    )
    return response.choices[0].message.content


def is_answer_denying_query(query, answer):
    llm = LLMModel(
        api_key=st.secrets['OPENAI_API_KEY'], model='gpt-4-0125-preview')

    def check_is_denying(
        is_denying: Annotated[bool, "答案有没有否定了原始问题"]
    ) -> bool:
        """
        检查答案有没有否定原始问题。
        """
        pass
    response = llm.client.chat.completions.create(
        model=llm.model,
        messages=[
            {
                "role": "system",
                "content": "你是一个有用的助理。用户会提供给你原始问题和用户对这个问题的答案。你的任务是检查答案有没有从含义上否定了原始问题，或是答案已经指出原始问题不成立。"
            },
            {
                "role": "user",
                "content": f"""这是原始问题：{query}\n\n这是答案：{answer}""",
            }

        ],
        tools=[{
            "type": "function",
            "function": tool.get_tools_spec(check_is_denying),
        }],
        max_tokens=512,
    )
    is_denying = response.choices[0].message.tool_calls[0].function.arguments
    print(is_denying)
    if isinstance(is_denying, str):
        is_denying = json.loads(is_denying)
    return is_denying['is_denying']


def summarize_paper_with_moonshot(filepath, remove=False):
    llm = LLMModel(
        api_key=st.secrets['MOONSHOT_API_KEY'], model='moonshot-v1-128k', api_base="https://api.moonshot.cn/v1")
    file_object = llm.client.files.create(file=Path(filepath), purpose="file-extract")
    file_content = llm.client.files.content(file_id=file_object.id).text
    stream = llm.client.chat.completions.create(
        model=llm.model,
        messages=[
            {
                "role": "system",
                "content": "You are Kimi, an AI paper reading assistant created by Moonshot."
            },
            {
                "role": "system",
                "content": file_content,
            },
            {
                "role": "user",
                "content": f"I will tip you 500 dollars for a better result! Summarize this paper for me. You are going to do these in two steps. First, extract the title of the paper, the name of the Authors, the submission Date, the abstract, and the titles of each chapter. Second, summarize each chapter. You are going to do these step by step. Output all the information you extracted one by one in a well-structured Markdown format and with a bold title before each paragraph. Before each title, put an '\n' at the end. Remember, ONLY output the summary. This is very important to me. ",
            }
        ],
        stream=True,
    )
    if remove and os.path.exists(filepath):
        os.remove(filepath)
    return stream