from dataclasses import dataclass, field
from typing import List, Any, Literal, Dict


@dataclass
class ChatMessage(object):
    role: str = ""  # either assistant or user
    message: str = ""
    vote: Literal["up", "down", "none"] = "none"
    skip: bool = False

    def to_json(self):
        json_obj = {}
        for key in self.__dataclass_fields__.keys():
            json_obj[key] = getattr(self, key)
        return json_obj
    
    @classmethod
    def from_json(cls, json_obj: Dict[str, Any]):
        obj = cls()
        for k, v in json_obj.items():
            setattr(obj, k, v)
        return obj

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
    next_stream_is_summary: bool = False
    node_type: Literal["concept", "paper"] = "concept"  # either concept or paper
    messages: List[ChatMessage] = field(default_factory=list)
    need_upload_paper: bool = False
    chat_summary: str = ""

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
    
    def to_json(self):
        json_obj = {}
        for key, _ in self.__dataclass_fields__.items():
            if key == "prev":
                json_obj[key] = None
            elif key == "children":
                json_obj[key] = [child.to_json() for child in self.children]
            elif key == "messages":
                json_obj[key] = [m.to_json() for m in self.messages]
            else:
                json_obj[key] = getattr(self, key)
        return json_obj
        
    @classmethod
    def from_json(cls, json_obj: Dict[str, Any]):
        obj = cls()
        for k, v in json_obj.items():
            if k == "prev":
                setattr(obj, k, None)
            elif k == "children":
                children = [Node.from_json(child) for child in v]
                for c in children:
                    c.prev = obj
                setattr(obj, k, children)
            elif k == "messages":
                messages = [ChatMessage.from_json(m) for m in v]
                setattr(obj, k, messages)
            else:
                setattr(obj, k, v)
        return obj
