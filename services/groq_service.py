"""
Service xử lý tương tác với Groq API - FIXED VERSION
"""

from groq import Groq
from typing import List, Dict, Any
import logging
from datetime import datetime

from config import config

logger = logging.getLogger(__name__)

class GroqServiceError(Exception):
    """Custom exception cho Groq Service"""
    pass

class GroqService:
    """
    Service quản lý tất cả tương tác với Groq API
    """
    
    def __init__(self, api_key: str = None, model: str = None):
        """
        Khởi tạo Groq Service
        """
        try:
            # Lấy cấu hình
            self.api_key = api_key or config.GROQ_API_KEY
            self.model = model or config.DEFAULT_MODEL
            
            if not self.api_key:
                raise GroqServiceError("Groq API Key không được cấu hình")
            
            # Khởi tạo client
            self.client = Groq(api_key=self.api_key)
            
            # Thống kê
            self.total_requests = 0
            self.total_tokens = 0
            self.start_time = datetime.now()
            
            logger.info(f"🤖 Đã khởi tạo GroqService")
            logger.info(f"   Model: {self.model}")
            
        except Exception as e:
            logger.error(f"❌ Lỗi khởi tạo GroqService: {e}")
            raise GroqServiceError(f"Không thể khởi tạo GroqService: {str(e)}")
    
    def generate_response(self, 
                         messages: List[Dict[str, str]], 
                         system_prompt: str = None,
                         temperature: float = 0.7,
                         max_tokens: int = 1024,
                         top_p: float = 1.0) -> str:
        """
        Tạo response từ Groq API
        
        Args:
            messages: Danh sách messages theo format {"role": "user/assistant", "content": "..."}
            system_prompt: Prompt hệ thống (optional)
            temperature: Độ sáng tạo (0.0-1.0)
            max_tokens: Số token tối đa trong response
            top_p: Top-p sampling
        
        Returns:
            Response text từ AI
        
        Raises:
            GroqServiceError: Nếu có lỗi từ API
        """
        try:
            self.total_requests += 1
            logger.info(f"📤 Gửi request #{self.total_requests} đến Groq API...")
            
            # Chuẩn bị messages
            api_messages = []
            
            # Thêm system prompt nếu có
            if system_prompt:
                api_messages.append({
                    "role": "system",
                    "content": system_prompt
                })
            
            # Thêm conversation messages
            api_messages.extend(messages)
            
            # Log thông tin request
            total_chars = sum(len(msg.get('content', '')) for msg in api_messages)
            logger.debug(f"   Messages: {len(api_messages)}")
            logger.debug(f"   Total chars: {total_chars}")
            logger.debug(f"   Temperature: {temperature}")
            
            # Gọi API - KHÔNG DÙNG STREAM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=api_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                stream=False,  # QUAN TRỌNG: luôn là False
                stop=None,
            )
            
            # Lấy response
            response_text = response.choices[0].message.content
            
            # Cập nhật thống kê
            if hasattr(response, 'usage'):
                self.total_tokens += response.usage.total_tokens
            
            # Log kết quả
            logger.info(f"📥 Nhận response thành công!")
            logger.debug(f"   Response length: {len(response_text)} chars")
            logger.debug(f"   Model: {response.model}")
            
            if hasattr(response, 'usage'):
                logger.debug(f"   Usage: {response.usage.total_tokens} tokens")
            
            return response_text
            
        except Exception as e:
            self.total_requests -= 1  # Rollback counter
            error_msg = f"❌ Lỗi Groq API: {str(e)}"
            logger.error(error_msg)
            
            # Phân loại lỗi
            error_detail = str(e).lower()
            if "rate limit" in error_detail:
                user_msg = "API đang bị giới hạn tốc độ. Vui lòng thử lại sau ít phút."
            elif "authentication" in error_detail or "api key" in error_detail:
                user_msg = "Lỗi xác thực API. Vui lòng kiểm tra API Key."
            elif "model" in error_detail:
                user_msg = "Model không khả dụng. Vui lòng kiểm tra model name."
            else:
                user_msg = "Có lỗi xảy ra khi xử lý yêu cầu. Vui lòng thử lại."
            
            raise GroqServiceError(user_msg)
    
    def create_product_recommendation(self, 
                                    user_query: str, 
                                    products: List[Dict],
                                    conversation_history: List[Dict] = None) -> str:
        """
        Tạo recommendation dựa trên sản phẩm và query
        
        Args:
            user_query: Câu hỏi/request của user
            products: Danh sách sản phẩm từ database
            conversation_history: Lịch sử chat (optional)
        
        Returns:
            Response được cá nhân hóa
        """
        try:
            # Chuẩn bị product context
            product_context = self._format_products_for_prompt(products)
            
            # Tạo system prompt
            system_prompt = f"""{config.SYSTEM_PROMPT_BASE}

THÔNG TIN SẢN PHẨM HIỆN CÓ:
{product_context}

HƯỚNG DẪN TRẢ LỜI:
1. Sử dụng thông tin sản phẩm trên để tư vấn
2. Nếu sản phẩm không phù hợp, đề xuất sản phẩm khác hoặc xin lỗi
3. Luôn đề cập đến giá cả nếu có
4. Gợi ý sản phẩm liên quan nếu phù hợp
5. Giữ thái độ thân thiện, chuyên nghiệp
6. Nếu user hỏi về thông tin không có, hãy nói rõ

Hãy trả lời dựa trên thông tin trên."""
            
            # Chuẩn bị messages
            messages = []
            
            # Thêm lịch sử chat nếu có
            if conversation_history:
                # Chỉ lấy 5 tin nhắn gần nhất
                recent_history = conversation_history[-10:]  # 5 cặp user/assistant
                messages.extend(recent_history)
            
            # Thêm query hiện tại
            messages.append({
                "role": "user",
                "content": user_query
            })
            
            # Gọi API
            response = self.generate_response(
                messages=messages,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=1024
            )
            
            return response
            
        except GroqServiceError:
            raise
        except Exception as e:
            logger.error(f"❌ Lỗi tạo recommendation: {e}")
            raise GroqServiceError("Không thể tạo recommendation")
    
    def _format_products_for_prompt(self, products: List[Dict]) -> str:
        """Format sản phẩm thành text cho prompt"""
        if not products:
            return "Hiện không có sản phẩm phù hợp."
        
        formatted = ""
        for i, product in enumerate(products, 1):
            formatted += f"\n{i}. {product.get('name', 'Không có tên')}"
            
            price = product.get('price')
            if price:
                formatted += f" - 💰 {price}"
            
            category = product.get('category')
            if category:
                formatted += f" - 🏷️ {category}"
            
            description = product.get('description')
            if description and len(description) > 0:
                # Giới hạn độ dài description
                desc_preview = description[:100] + "..." if len(description) > 100 else description
                formatted += f"\n   📝 {desc_preview}"
            
            stock = product.get('stock')
            if stock is not None:
                stock_status = "✅ Còn hàng" if stock > 0 else "❌ Hết hàng"
                formatted += f"\n   📦 {stock_status}"
        
        return formatted
    
    def test_connection(self) -> bool:
        """Kiểm tra kết nối đến Groq API"""
        try:
            # Gửi một test request đơn giản
            test_response = self.generate_response(
                messages=[{"role": "user", "content": "Xin chào"}],
                system_prompt="Trả lời ngắn gọn 'Kết nối thành công'",
                max_tokens=20
            )
            
            return bool(test_response and len(test_response) > 0)
        except:
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Lấy thống kê sử dụng"""
        runtime = datetime.now() - self.start_time
        hours = runtime.total_seconds() / 3600
        
        return {
            "total_requests": self.total_requests,
            "total_tokens": self.total_tokens,
            "runtime_hours": round(hours, 2),
            "requests_per_hour": round(self.total_requests / hours, 2) if hours > 0 else 0,
            "model": self.model,
            "status": "connected" if self.client else "disconnected"
        }