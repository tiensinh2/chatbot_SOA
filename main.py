"""
chatbot.py
Phiên bản ĐẦY ĐỦ, HOÀN CHỈNH và ỔN ĐỊNH NHẤT
- Ưu tiên history cực mạnh (lưu current_products trong session)
- Không hallucinate, không overthink
- Tìm kiếm thông minh chỉ khi cần
- Giao diện console đẹp, lệnh admin đầy đủ
- ĐÃ LOẠI BỎ HOÀN TOÀN increment_message_count → KHÔNG CÒN LỖI
"""

import sys
import logging
import time
from datetime import datetime
from typing import List, Dict, Any

from config import config
from database.mongo_handler import MongoDBHandler
from services.groq_service import GroqService
from services.redis_service import RedisService

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('chatbot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class Chatbot:
    def __init__(self):
        print("=" * 80)
        print("                🛍️  CHATBOT HỖ TRỢ MUA SẮM - SHOP ASSISTANT")
        print("=" * 80)

        try:
            config.validate_config()

            logger.info("Khởi tạo services...")
            self._init_services()

            self.total_messages = 0
            self.start_time = datetime.now()

            print("\n✅ CHATBOT ĐÃ SẴN SÀNG!\n")
            self._show_system_info()

        except Exception as e:
            logger.error(f"Lỗi khởi động chatbot: {e}")
            print(f"\n❌ Không thể khởi động: {e}")
            sys.exit(1)

    def _init_services(self):
        self.db_handler = MongoDBHandler()
        self.groq_service = GroqService()
        self.redis_service = RedisService()

        if not self.db_handler.test_connection():
            raise ConnectionError("Không kết nối được MongoDB")
        if not self.groq_service.test_connection():
            raise ConnectionError("Không kết nối được Groq API")

        logger.info("Tất cả services đã sẵn sàng")

    def _show_system_info(self):
        try:
            stats = self.db_handler.get_products_stats()
            categories = self.db_handler.get_categories()[:10]

            print("📊 THÔNG TIN HỆ THỐNG")
            print(f"   📦 Tổng sản phẩm    : {stats.get('total_products', 0):,}")
            print(f"   ✅ Còn hàng         : {stats.get('in_stock', 0):,}")
            print(f"   ❌ Hết hàng         : {stats.get('out_of_stock', 0):,}")
            print(f"   🏷️  Số danh mục      : {stats.get('categories_count', 0)}")
            if categories:
                print(f"   📁 Danh mục mẫu     : {', '.join(categories)}")

            groq_stats = self.groq_service.get_stats()
            print(f"   🤖 Model AI         : {groq_stats.get('model')}")
            print(f"   📈 Tổng request AI  : {groq_stats.get('total_requests', 0)}")

            redis_info = self.redis_service.get_redis_info()
            print(f"   🗄️ Redis kết nối     : {'Có' if redis_info.get('connected') else 'Không'}")
            if redis_info.get('connected'):
                print(f"   • Sessions hiện tại: {redis_info.get('session_count', 0)}")

        except Exception as e:
            logger.warning(f"Không lấy được thông tin hệ thống: {e}")

        print("\n📋 LỆNH HỖ TRỢ:")
        print("   sp     → Xem sản phẩm ngẫu nhiên")
        print("   dm     → Xem danh mục")
        print("   tk     → Thống kê chi tiết")
        print("   clear  → Xóa lịch sử chat hiện tại")
        print("   user   → Đổi user ID")
        print("   help   → Hiển thị lại thông tin này")
        print("   thoát  → Thoát chương trình")
        print("=" * 80)

    # ================= SESSION & HISTORY =================
    def _get_or_create_session(self, user_id: str) -> Dict:
        session = self.redis_service.get_session(user_id)
        if not session:
            session = self.redis_service.create_session(user_id)
            logger.info(f"Tạo session mới cho {user_id}")
        return session

    def _get_history(self, user_id: str, limit: int = 12) -> List[Dict]:
        return self.redis_service.get_conversation_history(user_id, limit)

    def _add_to_history(self, user_id: str, role: str, content: str):
        self.redis_service.add_message(user_id, role, content)

    # ================= LOGIC ƯU TIÊN HISTORY =================
    def _is_follow_up_question(self, text: str) -> bool:
        """Phát hiện câu hỏi tiếp nối ám chỉ sản phẩm trước đó"""
        text = text.lower().strip()
        patterns = [
            'cái rẻ nhất', 'cái đắt nhất', 'con nào', 'mẫu nào', 'cái đó',
            'con đó', 'bao nhiêu tiền', 'giá bao nhiêu', 'cấu hình',
            'có màu gì', 'trong số đó', 'trong danh sách', 'cái kia',
            'mẫu đó', 'con kia', 'mẫu nào tốt', 'cái nào tốt nhất'
        ]
        return any(pattern in text for pattern in patterns)

    def _search_relevant_products(self, user_input: str, history: List[Dict]) -> List[Dict]:
        """Tìm kiếm mới khi user thay đổi chủ đề (có thể cải tiến thêm keyword logic)"""
        return self.db_handler.search_products(user_input, limit=config.PRODUCT_SEARCH_LIMIT or 8)

    # ================= XỬ LÝ TIN NHẮN CHÍNH =================
    def process_message(self, user_id: str, user_input: str) -> Dict[str, Any]:
        self.total_messages += 1

        try:
            self.redis_service._check_and_cleanup()

            session = self._get_or_create_session(user_id)
            history = self._get_history(user_id, limit=12)

            logger.info(f"[{user_id}] User: {user_input}")

            # Lưu tin nhắn user
            self._add_to_history(user_id, 'user', user_input)

            # Lấy danh sách sản phẩm đang tư vấn từ session
            current_product_ids = session.get('current_products', [])

            if current_product_ids and self._is_follow_up_question(user_input):
                # ƯU TIÊN HISTORY: Dùng lại sản phẩm đang nói đến
                products = self.db_handler.get_products_by_ids(current_product_ids)
                logger.info(f"Ưu tiên history → tái sử dụng {len(products)} sản phẩm")
            else:
                # Tìm kiếm mới
                products = self._search_relevant_products(user_input, history)
                logger.info(f"Tìm kiếm mới → {len(products)} sản phẩm")

            # Cập nhật session với danh sách sản phẩm hiện tại
            if products:
                product_ids = [str(p['_id']) for p in products]
                session['current_products'] = product_ids[:getattr(config, 'PRODUCT_SEARCH_LIMIT', 8)]
                self.redis_service.update_session(user_id, session)

            # Gọi Groq AI
            logger.info("Gọi Groq để tạo phản hồi...")
            start_time = time.time()
            response = self.groq_service.create_product_recommendation(
                user_query=user_input,
                products=products,
                conversation_history=history
            )
            logger.info(f"AI phản hồi trong {time.time() - start_time:.2f}s")

            # Lưu phản hồi AI
            self._add_to_history(user_id, 'assistant', response)

            # Đánh dấu không còn là lần đầu chat
            if session.get('is_first_chat'):
                session['is_first_chat'] = False
                self.redis_service.update_session(user_id, session)

            return {"response": response, "products": products}

        except Exception as e:
            logger.exception("Lỗi xử lý tin nhắn")
            return {"response": "Xin lỗi, tôi đang gặp sự cố. Vui lòng thử lại sau.", "products": []}

    # ================= LỆNH ADMIN =================
    def handle_admin_command(self, cmd: str, current_user: str) -> bool:
        if cmd == 'sp':
            products = self.db_handler.get_random_products(6)
            print("\n🛍️ SẢN PHẨM NGẪU NHIÊN:")
            for p in products:
                stock = "✅ Còn hàng" if p.get('stock', 0) > 0 else "❌ Hết hàng"
                price = f"{int(p.get('price', 0)):,}₫" if p.get('price') else "Liên hệ"
                print(f"   • {p.get('name')} - {price} [{stock}]")
            return True

        elif cmd == 'dm':
            cats = self.db_handler.get_categories()
            print(f"\n🏷️  DANH MỤC ({len(cats)}):")
            print("   " + ", ".join(cats))
            return True

        elif cmd == 'tk':
            self.show_stats()
            return True

        elif cmd == 'clear':
            self.redis_service.clear_conversation(current_user)
            print(f"✅ Đã xóa lịch sử chat của {current_user}")
            # Reset current_products
            session = self.redis_service.get_session(current_user)
            if session:
                session['current_products'] = []
                self.redis_service.update_session(current_user, session)
            return True

        return False

    def show_stats(self):
        runtime = (datetime.now() - self.start_time).total_seconds() / 3600
        db_stats = self.db_handler.get_products_stats()
        groq_stats = self.groq_service.get_stats()
        redis_info = self.redis_service.get_redis_info()

        print("\n" + "="*60)
        print("                   📊 THỐNG KÊ CHI TIẾT")
        print("="*60)
        print(f"⏱️  Thời gian chạy     : {runtime:.2f} giờ")
        print(f"💬 Tổng tin nhắn       : {self.total_messages:,}")
        if runtime > 0:
            print(f"📈 Tin nhắn/giờ        : {self.total_messages/runtime:.1f}")

        print(f"\n📦 SẢN PHẨM")
        print(f"   Tổng cộng          : {db_stats.get('total_products', 0):,}")
        print(f"   Còn hàng           : {db_stats.get('in_stock', 0):,}")
        print(f"   Hết hàng           : {db_stats.get('out_of_stock', 0):,}")
        print(f"   Danh mục           : {db_stats.get('categories_count', 0)}")

        print(f"\n🤖 AI SERVICE")
        print(f"   Model              : {groq_stats.get('model')}")
        print(f"   Tổng request       : {groq_stats.get('total_requests', 0):,}")
        print(f"   Tokens sử dụng     : {groq_stats.get('total_tokens', 0):,}")

        print(f"\n🗄️ REDIS")
        if redis_info.get('connected'):
            print(f"   Sessions hiện tại  : {redis_info.get('session_count', 0)}")
            print(f"   Memory used        : {redis_info.get('memory_used', 'N/A')}")
        else:
            print("   Không kết nối")

        print("="*60)

    # ================= VÒNG LẶP CHÍNH =================
    def run(self):
        current_user = "khach_01"
        print(f"\n👤 User hiện tại: {current_user}")
        print("💬 Bắt đầu trò chuyện nào! (gõ 'help' để xem lệnh)\n")

        while True:
            try:
                user_input = input(f"[{current_user}] > ").strip()

                if not user_input:
                    continue

                cmd = user_input.lower()

                if cmd == 'thoát':
                    print("\n👋 Cảm ơn bạn đã sử dụng chatbot! Hẹn gặp lại!")
                    break

                elif cmd == 'help':
                    self._show_system_info()
                    continue

                elif cmd in ['sp', 'dm', 'tk', 'clear']:
                    self.handle_admin_command(cmd, current_user)
                    continue

                elif cmd == 'user':
                    new_id = input("👤 Nhập User ID mới: ").strip()
                    if new_id:
                        current_user = new_id
                        print(f"✅ Đã chuyển sang user: {current_user}")
                    continue

                # Xử lý tin nhắn bình thường
                print("🤖 Đang suy nghĩ...")
                result = self.process_message(current_user, user_input)

                print(f"\n{'='*70}")
                print("🤖 CHATBOT:")
                print(f"{'='*70}")
                print(result["response"])

                if result["products"]:
                    print(f"\n💡 Gợi ý {len(result['products'])} sản phẩm phù hợp")
                print(f"{'─'*70}\n")

            except KeyboardInterrupt:
                print(f"\n\n⚠️ Đã dừng chatbot. Tạm biệt {current_user}!")
                break
            except Exception as e:
                logger.exception("Lỗi trong vòng lặp chính")
                print(f"\n❌ Lỗi không mong đợi: {e}")

    # ================= DỌN DẸP =================
    def cleanup(self):
        print("\n🧹 Đang dọn dẹp tài nguyên...")
        try:
            self.db_handler.close()
            self.redis_service.close()
            runtime = (datetime.now() - self.start_time).total_seconds() / 3600
            logger.info(f"Chatbot dừng - Chạy {runtime:.2f}h, xử lý {self.total_messages} tin nhắn")
        except Exception as e:
            logger.error(f"Lỗi cleanup: {e}")
        finally:
            print("✅ Hoàn tất!")


def main():
    chatbot = None
    try:
        chatbot = Chatbot()
        chatbot.run()
    except KeyboardInterrupt:
        print("\nĐã dừng bởi người dùng.")
    except Exception as e:
        logger.critical(f"Lỗi nghiêm trọng: {e}")
    finally:
        if chatbot:
            chatbot.cleanup()


if __name__ == "__main__":
    main()