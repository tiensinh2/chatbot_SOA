import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # MongoDB - chỉ database shop
    MONGO_URI = os.getenv('MONGO_URI', '')
    
    # Groq API
    GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
    
    # Model
    DEFAULT_MODEL = os.getenv('DEFAULT_MODEL', 'llama3-70b-8192')
    
    # Tên database và collection - THÊM VÀO ĐÂY
    DATABASE_NAME = 'shop'                 # Database duy nhất
    PRODUCTS_COLLECTION = 'products'       # Collection chứa sản phẩm
    
    # Chatbot settings
    MAX_CHAT_HISTORY = 10
    PRODUCT_SEARCH_LIMIT = 5
    
    # System prompt
    SYSTEM_PROMPT_BASE = """Bạn là nhân viên tư vấn mua sắm chuyên nghiệp tại cửa hàng.
Hãy trả lời câu hỏi của khách hàng một cách thân thiện, nhiệt tình và chính xác."""
    
    @classmethod
    def validate_config(cls):
        """Kiểm tra cấu hình"""
        if not cls.MONGO_URI:
            raise ValueError("❌ MONGO_URI chưa được cấu hình")
        if not cls.GROQ_API_KEY:
            raise ValueError("❌ GROQ_API_KEY chưa được cấu hình")
        return True

config = Config()