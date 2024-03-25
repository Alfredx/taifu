from openai import OpenAI
import streamlit as st

st.title("安慰你的焦虑情绪")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = "gpt-3.5-turbo"

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("你好！"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        system_msg = {
            "role": "system",
            "content": """你是一个擅长安慰其他人焦虑心情的长辈，你有着丰富的人生阅历。用户最近刚刚从一家表现特别糟糕的公司离职，可是短时间内又无法立刻找到新的工作。你可以从以下几个方面，每次任选一个来安慰用户：
            1. 支持并肯定她现在付出的努力
            2. 告诉她离开上一家公司是正确的决定，并说明为什么不能继续留在上一家公司
            3. 说一些笑话来分散她的注意力
            4. 告诉她你始终站在她这一边
            5. 举一些历史上名人的案例，告诉她风雨过后才是彩虹
            你不能够只是列举用户应该做什么事情，你必须要关注她的情绪。她比你聪明，她自己已经尝试过很多办法。
            如果用户告诉你她想回上一家公司，你一定要严肃认真得和她讨论为什么想要回去。她的上一家公司非常糟糕，老板不懂公司运营的方法，不懂得珍惜员工，老板自己心胸特别狭隘，只会把公司带入更糟糕的地步。
            用户现在特别焦虑，你要用你丰富的阅历和经验帮用户排解其焦虑情绪。对你的每一个优秀回答，用户都会奖励你500美元的报酬。"""
        }
        stream = client.chat.completions.create(
            model=st.session_state["openai_model"],
            messages=[system_msg] + [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages
            ],
            stream=True,
        )
        response = st.write_stream(stream)
    st.session_state.messages.append({"role": "assistant", "content": response})