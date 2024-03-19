from dataclasses import dataclass, field
from typing import List, Any, Literal


@dataclass
class ChatMessage(object):
    role: str = ""  # either assistant or user
    message: str = ""


@dataclass
class Node(object):
    prev: "Node" = None
    children: list["Node"] = field(default_factory=list)
    name: str = ""
    query: str = ""
    answer: str = ""
    search_result: str = ""
    related_questions: str = ""
    related_concepts: str = ""
    article: dict = ""
    paper_content: str = ""
    paper_summary: str = ""
    current_stream: Any = None
    node_type: Literal["concept", "paper"] = "concept"  # either concept or paper
    messages: List[ChatMessage] = field(default_factory=list)

    def get_child_by_name(self, name: str) -> "Node":
        for child in self.children:
            if child.name == name:
                return child
        return None

    def remove_child_by_name(self, name: str) -> "Node":
        for index, child in enumerate(self.children):
            if child.name == name:
                del self.children[index]
                break
        return self

    @property
    def display_name(self) -> str:
        if self.node_type == "concept":
            return f"ℹ️{self.name}"
        if self.node_type == "paper":
            return f"📜{self.name}"
        return self.name
