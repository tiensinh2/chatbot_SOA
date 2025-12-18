import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """
    Cấu hình chung cho Chatbot:
    - MongoDB
    - Groq API
    - Redis Cloud
    - TTL và các cài đặt khác
    """

    # ---------------- MongoDB ----------------
    MONGO_URI = os.getenv('MONGO_URI', '')
    DATABASE_NAME = os.getenv('DATABASE_NAME', 'shop')
    PRODUCTS_COLLECTION = os.getenv('PRODUCTS_COLLECTION', 'products')

    # ---------------- Groq API ----------------
    GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
    DEFAULT_MODEL = os.getenv('DEFAULT_MODEL', 'llama3-70b-8192')

    # ---------------- Redis Cloud ----------------
    REDIS_HOST = os.getenv('REDIS_HOST', '')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_USERNAME = os.getenv('REDIS_USERNAME', 'default')
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')
    REDIS_DB = int(os.getenv('REDIS_DB', 0))
    REDIS_SSL = os.getenv('REDIS_SSL', 'True').lower() in ('true', '1', 'yes')

    # ---------------- Redis TTL Settings (seconds) ----------------
    SESSION_TIMEOUT_HOURS = int(os.getenv('SESSION_TIMEOUT_HOURS', 24))
    SESSION_TTL = SESSION_TIMEOUT_HOURS * 3600  # seconds

    REDIS_HISTORY_TTL = SESSION_TTL            # same as session
    REDIS_SEARCH_TTL = 3600                    # 1 hour
    REDIS_PRODUCT_TTL = 21600                  # 6 hours
    REDIS_CATEGORY_TTL = 7200                  # 2 hours

    # ---------------- Auto-cleanup Settings ----------------
    CLEANUP_INTERVAL_MINUTES = int(os.getenv('CLEANUP_INTERVAL_MINUTES', 60))
    MAX_INACTIVE_SESSIONS = int(os.getenv('MAX_INACTIVE_SESSIONS', 1000))

    # ---------------- Chatbot Settings ----------------
    MAX_CHAT_HISTORY = int(os.getenv('MAX_CHAT_HISTORY', 10))
    PRODUCT_SEARCH_LIMIT = int(os.getenv('PRODUCT_SEARCH_LIMIT', 5))
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

    # ---------------- System prompt ----------------
    SYSTEM_PROMPT_BASE = """Bạn là nhân viên tư vấn mua sắm chuyên nghiệp tại cửa hàng.
Hãy trả lời câu hỏi của khách hàng một cách thân thiện, nhiệt tình và chính xác.
Sử dụng thông tin sản phẩm từ database để tư vấn cho khách hàng."""

    # ---------------- Validation ----------------
    @classmethod
    def validate_config(cls):
        """Kiểm tra các cấu hình bắt buộc"""
        errors = []

        if not cls.MONGO_URI:
            errors.append("❌ MONGO_URI chưa được cấu hình")
        if not cls.GROQ_API_KEY:
            errors.append("❌ GROQ_API_KEY chưa được cấu hình")
        if not cls.REDIS_HOST:
            errors.append("❌ REDIS_HOST chưa được cấu hình")
        if not cls.REDIS_PASSWORD:
            errors.append("❌ REDIS_PASSWORD chưa được cấu hình")

        if errors:
            raise ValueError("\n".join(errors))

        print("✅ Tất cả cấu hình đã được thiết lập")
        print(f"📊 Session TTL: {cls.SESSION_TIMEOUT_HOURS} giờ")
        print(f"🧹 Cleanup interval: {cls.CLEANUP_INTERVAL_MINUTES} phút")
        return True


# Khởi tạo config
config = Config()
