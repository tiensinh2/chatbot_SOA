"""
Chatbot chính cho cửa hàng sản phẩm
Tích hợp MongoDB (shop database), Groq API và Redis (session & history)
"""

import sys
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict

from config import config
from database.mongo_handler import MongoDBHandler
from services.groq_service import GroqService, GroqServiceError
from services.redis_service import RedisService

# Thiết lập logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('chatbot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class Chatbot:
    """
    Chatbot chính tích hợp MongoDB, Groq API và Redis

    Tính năng:
    1. Quản lý conversation với Redis (session + history)
    2. Tìm kiếm sản phẩm từ MongoDB
    3. Tạo response thông minh với Groq API
    4. Thống kê & cleanup tự động
    """

    def __init__(self):
        print("=" * 70)
        print("🛍️  CHATBOT HỖ TRỢ MUA SẮM - SHOP ASSISTANT")
        print("=" * 70)

        try:
            # Validate cấu hình
            config.validate_config()

            # Khởi tạo services
            logger.info("🔄 Đang khởi tạo services...")
            self._init_services()

            # Thống kê
            self.total_messages = 0
            self.start_time = datetime.now()

            print("\n✅ CHATBOT ĐÃ SẴN SÀNG!")
            self._show_system_info()

        except Exception as e:
            logger.error(f"❌ Lỗi khởi động chatbot: {e}")
            print(f"\n❌ Không thể khởi động: {e}")
            sys.exit(1)

    def _init_services(self):
        """Khởi tạo các services"""
        # MongoDB Handler
        self.db_handler = MongoDBHandler()

        # Groq Service
        self.groq_service = GroqService()

        # Redis Service (session + history)
        self.redis_service = RedisService()

        # Test connections
        if not self.db_handler.test_connection():
            raise ConnectionError("Không thể kết nối đến MongoDB")

        if not self.groq_service.test_connection():
            raise ConnectionError("Không thể kết nối đến Groq API")

        logger.info("✅ Tất cả services đã sẵn sàng")

    def _show_system_info(self):
        """Hiển thị thông tin hệ thống"""
        try:
            stats = self.db_handler.get_products_stats()
            print(f"\n📊 THÔNG TIN HỆ THỐNG:")
            print(f"   📦 Tổng sản phẩm: {stats.get('total_products', 0)}")
            print(f"   🏷️  Số danh mục: {stats.get('categories_count', 0)}")

            categories = self.db_handler.get_categories()
            if categories:
                print(f"   📁 Danh mục: {', '.join(categories[:5])}" +
                      ("..." if len(categories) > 5 else ""))

            # Thông tin Groq
            groq_stats = self.groq_service.get_stats()
            print(f"   🤖 Model AI: {groq_stats.get('model', 'N/A')}")

            # Redis info
            redis_info = self.redis_service.get_redis_info()
            print(f"   🗄️ Redis connected: {redis_info.get('connected', False)}")
            if redis_info.get('connected', False):
                print(f"   • Memory used: {redis_info.get('memory_used')}")
                print(f"   • Sessions: {redis_info.get('session_keys')}")

        except Exception as e:
            logger.warning(f"⚠️ Không thể lấy thông tin hệ thống: {e}")

        print("\n📋 LỆNH HỖ TRỢ:")
        print("   'sp'          - Xem sản phẩm")
        print("   'dm'          - Xem danh mục")
        print("   'tk'          - Thống kê")
        print("   'user'        - Đổi user")
        print("   'clear'       - Xóa chat")
        print("   'help'        - Hiển thị trợ giúp")
        print("   'thoát'       - Thoát chương trình")
        print("=" * 70)

    # ================= SESSION & HISTORY =================
    def _get_or_create_session(self, user_id: str) -> Dict:
        """Lấy hoặc tạo session cho user"""
        session = self.redis_service.get_session(user_id)
        if not session:
            session = self.redis_service.create_session(user_id)
        return session

    def _add_to_conversation_history(self, user_id: str, role: str, content: str):
        """Thêm message vào conversation history"""
        self.redis_service.add_message(user_id, role, content)

    def _get_conversation_history(self, user_id: str, limit: int = 5) -> List[Dict]:
        """Lấy lịch sử conversation"""
        history = self.redis_service.get_conversation_history(user_id, limit)
        return history

    # ================= PRODUCT SEARCH =================
    def _search_relevant_products(self, user_input: str) -> List[Dict]:
        try:
            keywords = self._extract_keywords(user_input)
            all_products = []
            for keyword in keywords:
                products = self.db_handler.search_products(keyword, limit=3)
                all_products.extend(products)

            # Remove duplicates
            seen_ids = set()
            unique_products = []
            for product in all_products:
                product_id = product.get('_id')
                if product_id and product_id not in seen_ids:
                    seen_ids.add(product_id)
                    unique_products.append(product)

            unique_products.sort(key=lambda x: (
                -len(x.get('name', '')),
                -x.get('price', 0) if x.get('price') else 0
            ))
            return unique_products[:config.PRODUCT_SEARCH_LIMIT]

        except Exception as e:
            logger.error(f"❌ Lỗi tìm kiếm sản phẩm: {e}")
            return []

    def _extract_keywords(self, text: str) -> List[str]:
        stop_words = {'tôi', 'muốn', 'mua', 'cần', 'có', 'nào', 'gì', 'bao', 'nhiêu', 'tiền'}
        words = text.lower().split()
        keywords = [word for word in words if word not in stop_words and len(word) > 1]
        if len(text) > 3:
            keywords.append(text)
        return list(set(keywords))

    # ================= PROCESS MESSAGE =================
    def process_message(self, user_id: str, user_input: str) -> str:
        self.total_messages += 1
        try:
            # Cleanup Redis cũ
            self.redis_service._check_and_cleanup()

            # Session
            session = self._get_or_create_session(user_id)

            # Log user input
            logger.info(f"📩 User '{user_id}': {user_input[:50]}...")

            # Lưu user message
            self._add_to_conversation_history(user_id, 'user', user_input)

            # Tìm sản phẩm liên quan
            relevant_products = self._search_relevant_products(user_input)

            # Lấy history
            history = self._get_conversation_history(user_id)

            # AI response
            logger.info("🔄 Đang tạo response với AI...")
            start_time = time.time()
            response = self.groq_service.create_product_recommendation(
                user_query=user_input,
                products=relevant_products,
                conversation_history=history
            )
            logger.info(f"✅ Response tạo xong trong {time.time() - start_time:.2f}s")

            # Lưu AI response
            self._add_to_conversation_history(user_id, 'assistant', response)

            # Cập nhật session
            if session.get('is_first_chat', True):
                session['is_first_chat'] = False
                self.redis_service.update_session(user_id, session)

            return response

        except GroqServiceError as e:
            logger.error(f"❌ Lỗi AI: {e}")
            return f"Xin lỗi, có lỗi xảy ra: {e}"
        except Exception as e:
            logger.error(f"❌ Lỗi xử lý tin nhắn: {e}")
            return "Xin lỗi, tôi gặp sự cố khi xử lý yêu cầu của bạn. Vui lòng thử lại."

    # ================= COMMANDS =================
    def clear_chat(self, user_id: str = None):
        if user_id:
            self.redis_service.clear_conversation(user_id)
            print(f"✅ Đã xóa chat history của user {user_id}")
        else:
            for uid in self.redis_service.get_all_sessions():
                self.redis_service.clear_conversation(uid.get('user_id'))
            print("✅ Đã xóa tất cả chat history")

    # ================= STATS =================
    def show_stats(self):
        runtime = datetime.now() - self.start_time
        hours = runtime.total_seconds() / 3600
        db_stats = self.db_handler.get_products_stats()
        groq_stats = self.groq_service.get_stats()
        redis_info = self.redis_service.get_redis_info()

        print("\n📊 THỐNG KÊ HỆ THỐNG:")
        print("=" * 40)
        print(f"\n📦 CƠ SỞ DỮ LIỆU:")
        print(f"   • Tổng sản phẩm: {db_stats.get('total_products', 0)}")
        print(f"   • Số danh mục: {db_stats.get('categories_count', 0)}")
        print(f"   • Còn hàng: {db_stats.get('in_stock', 0)}")
        print(f"   • Hết hàng: {db_stats.get('out_of_stock', 0)}")
        print(f"\n🤖 AI SERVICE:")
        print(f"   • Model: {groq_stats.get('model', 'N/A')}")
        print(f"   • Tổng requests: {groq_stats.get('total_requests', 0)}")
        print(f"   • Tổng tokens: {groq_stats.get('total_tokens', 0):,}")
        print(f"\n💬 CHATBOT:")
        print(f"   • Thời gian chạy: {runtime.total_seconds()/3600:.1f} giờ")
        print(f"   • Tổng tin nhắn: {self.total_messages}")
        print(f"   • Tin nhắn/giờ: {self.total_messages/hours:.1f}" if hours>0 else "   • Tin nhắn/giờ: N/A")
        print(f"\n💾 REDIS:")
        if redis_info.get('connected'):
            print(f"   • Sessions: {redis_info.get('session_keys')}")
            print(f"   • Memory used: {redis_info.get('memory_used')}")

    # ================= MAIN LOOP =================
    def run(self):
        current_user = "khach_hang_01"
        print(f"\n👤 User hiện tại: {current_user}")
        print("💬 Hãy bắt đầu chat (hoặc gõ 'help' để xem lệnh)")

        while True:
            try:
                user_input = input(f"\n👤 [{current_user}] > ").strip()
                if not user_input:
                    continue
                cmd = user_input.lower()

                if cmd == 'thoát':
                    print("\n👋 Cảm ơn bạn đã sử dụng! Hẹn gặp lại!")
                    break
                elif cmd == 'help':
                    self._show_system_info()
                    continue
                elif cmd == 'tk':
                    self.show_stats()
                    continue
                elif cmd == 'clear':
                    self.clear_chat(current_user)
                    continue
                elif cmd == 'user':
                    new_user = input("👤 Nhập User ID mới: ").strip()
                    if new_user:
                        current_user = new_user
                        print(f"✅ Đã chuyển sang user: {current_user}")
                    continue

                # Xử lý tin nhắn thông thường
                print("🔄 Đang xử lý...")
                response = self.process_message(current_user, user_input)
                print(f"\n{'🤖'*30}\n🤖 CHATBOT:\n{'🤖'*30}")
                print(response)
                print(f"{'━'*50}")

            except KeyboardInterrupt:
                print(f"\n\n⚠️  Đang thoát... Tạm biệt {current_user}!")
                break
            except Exception as e:
                print(f"\n❌ Lỗi không mong đợi: {e}")
                logger.exception("Unhandled exception in main loop")

    def cleanup(self):
        print("\n🧹 Đang dọn dẹp resources...")
        try:
            if hasattr(self, 'db_handler'):
                self.db_handler.close()
            if hasattr(self, 'redis_service'):
                self.redis_service.close()

            runtime = datetime.now() - self.start_time
            logger.info(f"📊 Chatbot kết thúc: Tổng thời gian: {runtime.total_seconds()/3600:.2f}h, Tổng tin nhắn: {self.total_messages}")
            print("✅ Đã hoàn thành!")

        except Exception as e:
            print(f"⚠️  Lỗi khi cleanup: {e}")


def main():
    chatbot = None
    try:
        chatbot = Chatbot()
        chatbot.run()
    except KeyboardInterrupt:
        print("\n\n👋 Đã dừng chatbot!")
    except Exception as e:
        print(f"\n❌ Lỗi nghiêm trọng: {e}")
    finally:
        if chatbot:
            chatbot.cleanup()


if __name__ == "__main__":
    main()
