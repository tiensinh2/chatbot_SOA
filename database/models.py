from datetime import datetime
from typing import List, Dict, Any

class User:
    """Class đại diện cho người dùng"""
    def __init__(self, user_id: str, name: str = None, email: str = None):
        self.user_id = user_id
        self.name = name or f"User_{user_id}"
        self.email = email
        self.created_at = datetime.utcnow()
        self.last_active = datetime.utcnow()
        self.chat_count = 0
        self.is_first_chat = True  # Flag để xác định lần đầu chat
    
    def to_dict(self) -> Dict:
        return {
            'user_id': self.user_id,
            'name': self.name,
            'email': self.email,
            'created_at': self.created_at,
            'last_active': self.last_active,
            'chat_count': self.chat_count,
            'is_first_chat': self.is_first_chat
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'User':
        user = cls(
            user_id=data['user_id'],
            name=data.get('name'),
            email=data.get('email')
        )
        user.created_at = data.get('created_at', datetime.utcnow())
        user.last_active = data.get('last_active', datetime.utcnow())
        user.chat_count = data.get('chat_count', 0)
        user.is_first_chat = data.get('is_first_chat', True)
        return user
    
    def update_activity(self):
        """Cập nhật thời gian hoạt động và tăng số lần chat"""
        self.last_active = datetime.utcnow()
        self.chat_count += 1
        
        # Sau lần chat đầu tiên, đổi flag
        if self.is_first_chat and self.chat_count > 0:
            self.is_first_chat = False
class Message:
    """Class đại diện cho một message trong conversation"""
    def __init__(self, role: str, content: str, timestamp: datetime = None):
        self.role = role  # 'user' hoặc 'assistant'
        self.content = content
        self.timestamp = timestamp or datetime.utcnow()
    
    def to_dict(self) -> Dict:
        """Chuyển đổi thành dictionary để lưu vào MongoDB"""
        return {
            'role': self.role,
            'content': self.content,
            'timestamp': self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Message':
        """Tạo Message từ dictionary"""
        return cls(
            role=data['role'],
            content=data['content'],
            timestamp=data.get('timestamp', datetime.utcnow())
        )

class Conversation:
    """Class đại diện cho một conversation"""
    def __init__(self, user_id: str, messages: List[Message] = None):
        self.user_id = user_id
        self.messages = messages or []
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def add_message(self, message: Message):
        """Thêm message vào conversation"""
        self.messages.append(message)
        self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> Dict:
        """Chuyển đổi thành dictionary để lưu vào MongoDB"""
        return {
            'user_id': self.user_id,
            'messages': [msg.to_dict() for msg in self.messages],
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Conversation':
        """Tạo Conversation từ dictionary"""
        conv = cls(user_id=data['user_id'])
        conv.messages = [Message.from_dict(msg) for msg in data.get('messages', [])]
        conv.created_at = data.get('created_at', datetime.utcnow())
        conv.updated_at = data.get('updated_at', datetime.utcnow())
        return conv

class KnowledgeItem:
    """Class đại diện cho một mục trong knowledge base"""
    def __init__(self, question: str, answer: str, category: str = None, tags: List[str] = None):
        self.question = question
        self.answer = answer
        self.category = category
        self.tags = tags or []
        self.created_at = datetime.utcnow()
    
    def to_dict(self) -> Dict:
        """Chuyển đổi thành dictionary để lưu vào MongoDB"""
        return {
            'question': self.question,
            'answer': self.answer,
            'category': self.category,
            'tags': self.tags,
            'created_at': self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'KnowledgeItem':
        """Tạo KnowledgeItem từ dictionary"""
        return cls(
            question=data['question'],
            answer=data['answer'],
            category=data.get('category'),
            tags=data.get('tags', [])
        )