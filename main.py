"""
Chatbot chính cho cửa hàng sản phẩm
Tích hợp MongoDB (shop database) và Groq API
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
    Chatbot chính tích hợp MongoDB và Groq API
    
    Tính năng:
    1. Quản lý conversation với cache
    2. Tìm kiếm sản phẩm từ MongoDB
    3. Tạo response thông minh với Groq API
    4. Quản lý user sessions
    """
    
    def __init__(self):
        """Khởi tạo chatbot"""
        print("=" * 70)
        print("🛍️  CHATBOT HỖ TRỢ MUA SẮM - SHOP ASSISTANT")
        print("=" * 70)
        
        try:
            # Validate cấu hình
            config.validate_config()
            
            # Khởi tạo services
            logger.info("🔄 Đang khởi tạo services...")
            self._init_services()
            
            # Cache management
            self.conversation_cache = defaultdict(list)  # user_id -> list of messages
            self.user_sessions = {}                      # user_id -> session data
            self.product_cache = {}                      # cache sản phẩm
            
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
        
        # Test connections
        if not self.db_handler.test_connection():
            raise ConnectionError("Không thể kết nối đến MongoDB")
        
        if not self.groq_service.test_connection():
            raise ConnectionError("Không thể kết nối đến Groq API")
        
        logger.info("✅ Tất cả services đã sẵn sàng")
    
    def _show_system_info(self):
        """Hiển thị thông tin hệ thống"""
        # Thông tin database
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
    
    def _get_or_create_session(self, user_id: str) -> Dict:
        """Lấy hoặc tạo session cho user"""
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                'user_id': user_id,
                'created_at': datetime.now(),
                'last_active': datetime.now(),
                'message_count': 0,
                'is_first_chat': True
            }
        
        session = self.user_sessions[user_id]
        session['last_active'] = datetime.now()
        session['message_count'] += 1
        
        return session
    
    def _get_conversation_history(self, user_id: str, limit: int = 5) -> List[Dict]:
        """Lấy lịch sử conversation từ cache"""
        return self.conversation_cache.get(user_id, [])[-limit:]
    
    def _add_to_conversation_history(self, user_id: str, role: str, content: str):
        """Thêm message vào conversation history"""
        message = {
            'role': role,
            'content': content,
            'timestamp': datetime.now()
        }
        
        if user_id not in self.conversation_cache:
            self.conversation_cache[user_id] = []
        
        self.conversation_cache[user_id].append(message)
        
        # Giới hạn lịch sử
        if len(self.conversation_cache[user_id]) > config.MAX_CHAT_HISTORY * 2:
            self.conversation_cache[user_id] = self.conversation_cache[user_id][-config.MAX_CHAT_HISTORY*2:]
    
    def _search_relevant_products(self, user_input: str) -> List[Dict]:
        """
        Tìm kiếm sản phẩm phù hợp với user input
        
        Returns:
            Danh sách sản phẩm có liên quan
        """
        try:
            # Extract keywords từ user input
            keywords = self._extract_keywords(user_input)
            
            # Tìm kiếm với từng keyword
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
            
            # Sort by relevance (simplified)
            unique_products.sort(key=lambda x: (
                -len(x.get('name', '')),
                -x.get('price', 0) if x.get('price') else 0
            ))
            
            return unique_products[:config.PRODUCT_SEARCH_LIMIT]
            
        except Exception as e:
            logger.error(f"❌ Lỗi tìm kiếm sản phẩm: {e}")
            return []
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Trích xuất keywords từ text"""
        # Loại bỏ stop words đơn giản
        stop_words = {'tôi', 'muốn', 'mua', 'cần', 'có', 'nào', 'gì', 'bao', 'nhiêu', 'tiền'}
        
        words = text.lower().split()
        keywords = [word for word in words if word not in stop_words and len(word) > 1]
        
        # Thêm toàn bộ text như một keyword
        if len(text) > 3:
            keywords.append(text)
        
        return list(set(keywords))  # Remove duplicates
    
    def process_message(self, user_id: str, user_input: str) -> str:
        """
        Xử lý tin nhắn từ user và trả về response
        
        Args:
            user_id: ID của user
            user_input: Nội dung tin nhắn
        
        Returns:
            Response từ chatbot
        """
        try:
            self.total_messages += 1
            
            # Lấy session
            session = self._get_or_create_session(user_id)
            
            # Log
            logger.info(f"📩 User '{user_id}': {user_input[:50]}...")
            
            # Thêm user message vào history
            self._add_to_conversation_history(user_id, 'user', user_input)
            
            # Tìm sản phẩm liên quan
            relevant_products = self._search_relevant_products(user_input)
            
            # Lấy conversation history
            history = self._get_conversation_history(user_id)
            
            # Tạo response với Groq API
            logger.info("🔄 Đang tạo response với AI...")
            start_time = time.time()
            
            response = self.groq_service.create_product_recommendation(
                user_query=user_input,
                products=relevant_products,
                conversation_history=history
            )
            
            processing_time = time.time() - start_time
            logger.info(f"✅ Đã tạo response trong {processing_time:.2f}s")
            
            # Thêm AI response vào history
            self._add_to_conversation_history(user_id, 'assistant', response)
            
            # Cập nhật session
            if session['is_first_chat']:
                session['is_first_chat'] = False
            
            # Log success
            logger.info(f"✅ Response length: {len(response)} chars")
            
            return response
            
        except GroqServiceError as e:
            error_msg = f"❌ Lỗi AI: {str(e)}"
            logger.error(error_msg)
            return f"Xin lỗi, có lỗi xảy ra: {str(e)}"
            
        except Exception as e:
            error_msg = f"❌ Lỗi xử lý tin nhắn: {e}"
            logger.error(error_msg)
            return "Xin lỗi, tôi gặp sự cố khi xử lý yêu cầu của bạn. Vui lòng thử lại."
    
    def show_products(self, category: str = None, page: int = 1):
        """Hiển thị sản phẩm"""
        try:
            if category:
                products = self.db_handler.get_products_by_category(category, limit=20)
                print(f"\n📦 SẢN PHẨM TRONG DANH MỤC '{category.upper()}':")
            else:
                result = self.db_handler.get_all_products(page=page, per_page=10)
                products = result.get('products', [])
                pagination = result.get('pagination', {})
                
                print(f"\n📦 TẤT CẢ SẢN PHẨM (Trang {page}/{pagination.get('total_pages', 1)}):")
            
            if not products:
                print("   📭 Không có sản phẩm nào.")
                return
            
            for i, product in enumerate(products, 1):
                print(f"\n{i}. {product.get('name', 'Không có tên')}")
                
                price = product.get('price')
                if price:
                    print(f"   💰 Giá: {price}")
                
                cat = product.get('category')
                if cat:
                    print(f"   🏷️  Danh mục: {cat}")
                
                desc = product.get('description')
                if desc:
                    print(f"   📝 {desc[:80]}..." if len(desc) > 80 else f"   📝 {desc}")
                
                stock = product.get('stock')
                if stock is not None:
                    status = "✅ Còn hàng" if stock > 0 else "❌ Hết hàng"
                    print(f"   📦 {status}")
            
            if not category and pagination:
                print(f"\n📄 Trang {pagination['page']}/{pagination['total_pages']}")
                if pagination.get('has_next'):
                    print("   📝 Gõ 'sp trang_sau' để xem trang tiếp theo")
                if pagination.get('has_previous'):
                    print("   📝 Gõ 'sp trang_truoc' để xem trang trước")
                    
        except Exception as e:
            print(f"❌ Lỗi khi hiển thị sản phẩm: {e}")
    
    def show_categories(self):
        """Hiển thị danh mục sản phẩm"""
        try:
            categories = self.db_handler.get_categories()
            
            print("\n🏷️ DANH MỤC SẢN PHẨM:")
            if not categories:
                print("   📭 Không có danh mục nào.")
                return
            
            # Hiển thị theo cột
            for i, category in enumerate(categories, 1):
                print(f"   {i:2d}. {category}")
            
            print(f"\n📝 Gõ 'sp tên_danh_mục' để xem sản phẩm trong danh mục")
            
        except Exception as e:
            print(f"❌ Lỗi khi hiển thị danh mục: {e}")
    
    def show_stats(self):
        """Hiển thị thống kê"""
        try:
            runtime = datetime.now() - self.start_time
            hours = runtime.total_seconds() / 3600
            
            # Database stats
            db_stats = self.db_handler.get_products_stats()
            
            # Groq stats
            groq_stats = self.groq_service.get_stats()
            
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
            print(f"   • Requests/giờ: {groq_stats.get('requests_per_hour', 0):.1f}")
            
            print(f"\n💬 CHATBOT:")
            print(f"   • Thời gian chạy: {runtime.total_seconds()/3600:.1f} giờ")
            print(f"   • Tổng tin nhắn: {self.total_messages}")
            print(f"   • Số user: {len(self.user_sessions)}")
            print(f"   • Tin nhắn/giờ: {self.total_messages/hours:.1f}" if hours > 0 else "   • Tin nhắn/giờ: N/A")
            
            print(f"\n💾 CACHE:")
            print(f"   • Conversation cache: {sum(len(v) for v in self.conversation_cache.values())} messages")
            print(f"   • User sessions: {len(self.user_sessions)}")
            
        except Exception as e:
            print(f"❌ Lỗi khi hiển thị thống kê: {e}")
    
    def clear_chat(self, user_id: str = None):
        """Xóa chat history"""
        if user_id:
            if user_id in self.conversation_cache:
                del self.conversation_cache[user_id]
                print(f"✅ Đã xóa chat history của user {user_id}")
            else:
                print(f"⚠️  User {user_id} không có chat history")
        else:
            self.conversation_cache.clear()
            print("✅ Đã xóa tất cả chat history")
    
    def run(self):
        """Chạy chatbot main loop"""
        current_user = "khach_hang_01"  # User mặc định
        
        print(f"\n👤 User hiện tại: {current_user}")
        print("💬 Hãy bắt đầu chat (hoặc gõ 'help' để xem lệnh)")
        
        while True:
            try:
                # Hiển thị prompt
                user_input = input(f"\n👤 [{current_user}] > ").strip()
                
                # Xử lý lệnh đặc biệt
                if not user_input:
                    continue
                    
                elif user_input.lower() == 'thoát':
                    print("\n👋 Cảm ơn bạn đã sử dụng! Hẹn gặp lại!")
                    break
                
                elif user_input.lower() == 'help':
                    self._show_system_info()
                    continue
                
                elif user_input.lower().startswith('sp '):
                    # Lệnh xem sản phẩm
                    parts = user_input[3:].strip().split()
                    if len(parts) > 0:
                        category = parts[0]
                        page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
                        self.show_products(category if category != 'trang_sau' and category != 'trang_truoc' else None, page)
                    else:
                        self.show_products()
                    continue
                
                elif user_input.lower() == 'dm':
                    self.show_categories()
                    continue
                
                elif user_input.lower() == 'tk':
                    self.show_stats()
                    continue
                
                elif user_input.lower() == 'user':
                    new_user = input("👤 Nhập User ID mới: ").strip()
                    if new_user:
                        current_user = new_user
                        print(f"✅ Đã chuyển sang user: {current_user}")
                    continue
                
                elif user_input.lower() == 'clear':
                    self.clear_chat(current_user)
                    continue
                
                # Xử lý tin nhắn thông thường
                print("🔄 Đang xử lý...")
                response = self.process_message(current_user, user_input)
                
                # Hiển thị response
                print(f"\n{'🤖' * 30}")
                print(f"🤖 CHATBOT:")
                print(f"{'🤖' * 30}")
                print(f"{response}")
                print(f"{'━' * 50}")
                
            except KeyboardInterrupt:
                print(f"\n\n⚠️  Đang thoát... Tạm biệt {current_user}!")
                break
            except Exception as e:
                print(f"\n❌ Lỗi không mong đợi: {e}")
                logger.exception("Unhandled exception in main loop")
    
    def cleanup(self):
        """Dọn dẹp resources"""
        print("\n🧹 Đang dọn dẹp resources...")
        
        try:
            if hasattr(self, 'db_handler'):
                self.db_handler.close()
            
            # Log final stats
            runtime = datetime.now() - self.start_time
            logger.info(f"📊 Chatbot kết thúc:")
            logger.info(f"   • Tổng thời gian: {runtime.total_seconds()/3600:.2f} giờ")
            logger.info(f"   • Tổng tin nhắn: {self.total_messages}")
            logger.info(f"   • Số user: {len(self.user_sessions)}")
            
            print("✅ Đã hoàn thành!")
            
        except Exception as e:
            print(f"⚠️  Lỗi khi cleanup: {e}")

def main():
    """Hàm main"""
    chatbot = None
    
    try:
        chatbot = Chatbot()
        chatbot.run()
        
    except KeyboardInterrupt:
        print("\n\n👋 Đã dừng chatbot!")
    except Exception as e:
        print(f"\n❌ Lỗi nghiêm trọng: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if chatbot:
            chatbot.cleanup()

if __name__ == "__main__":
    main()