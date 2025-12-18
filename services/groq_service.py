"""
Service xử lý tương tác với Groq API
- Chỉ gửi đúng định dạng {role, content} cho Groq
- Clean input triệt để, tránh field thừa
- Logic rõ ràng, dễ bảo trì, xử lý lỗi tốt hơn
"""

from groq import Groq
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from config import config

logger = logging.getLogger(__name__)


class GroqServiceError(Exception):
    """Lỗi tùy chỉnh cho GroqService"""
    pass


def _clean_message(msg: Any) -> Optional[Dict[str, str]]:
    """Chuyển đổi và làm sạch một message, chỉ giữ role + content"""
    if not isinstance(msg, dict):
        return None
    role = msg.get("role")
    content = msg.get("content")
    if isinstance(role, str) and isinstance(content, str):
        role = role.strip()
        content = content.strip()
        if role in {"system", "user", "assistant"} and content:
            return {"role": role, "content": content}
    return None


class GroqService:
    def __init__(self, api_key: str = None, model: str = None):
        try:
            self.api_key = api_key or config.GROQ_API_KEY
            self.model = model or config.DEFAULT_MODEL

            if not self.api_key:
                raise GroqServiceError("Groq API Key không được cấu hình")

            self.client = Groq(api_key=self.api_key)

            self.total_requests = 0
            self.total_tokens = 0
            self.start_time = datetime.now()

            logger.info("🤖 GroqService đã sẵn sàng")
            logger.info(f"   Model: {self.model}")

        except Exception as e:
            logger.error(f"❌ Lỗi khởi tạo GroqService: {e}")
            raise GroqServiceError(f"Không thể khởi tạo GroqService: {e}")

    # --------------------------------------------------
    # CORE CALL
    # --------------------------------------------------
    def generate_response(
        self,
        messages: List[Any],
        system_prompt: str = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        top_p: float = 1.0,
    ) -> str:
        try:
            # Làm sạch và xây dựng danh sách messages hợp lệ
            clean_messages: List[Dict[str, str]] = []

            if system_prompt and system_prompt.strip():
                clean_messages.append({
                    "role": "system",
                    "content": system_prompt.strip()
                })

            for msg in messages:
                cleaned = _clean_message(msg)
                if cleaned:
                    clean_messages.append(cleaned)

            if not clean_messages:
                raise GroqServiceError("Không có message hợp lệ để gửi đến Groq")

            logger.info(f"📤 Gửi {len(clean_messages)} messages đến Groq (model: {self.model})")

            # Tăng request trước khi gọi API (chỉ tăng khi thực sự gọi)
            self.total_requests += 1

            response = self.client.chat.completions.create(
                model=self.model,
                messages=clean_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                stream=False,
            )

            response_text = response.choices[0].message.content.strip()

            # Cập nhật token usage nếu có
            if hasattr(response, "usage") and response.usage:
                self.total_tokens += response.usage.total_tokens

            logger.info("📥 Nhận response từ Groq thành công")

            return response_text

        except Exception as e:
            logger.error(f"❌ Lỗi khi gọi Groq API: {e}")

            error_msg = str(e).lower()
            if "rate limit" in error_msg:
                raise GroqServiceError("Đã vượt giới hạn tốc độ API. Vui lòng thử lại sau vài giây.")
            if "authentication" in error_msg or "api key" in error_msg:
                raise GroqServiceError("Lỗi xác thực API Key.")
            if "model" in error_msg and "not found" in error_msg:
                raise GroqServiceError("Model không tồn tại hoặc không khả dụng.")
            if "invalid" in error_msg or "unsupported" in error_msg:
                raise GroqServiceError("Dữ liệu gửi lên không hợp lệ.")

            raise GroqServiceError("Lỗi không xác định khi gọi Groq API.")

    # --------------------------------------------------
    # PRODUCT RECOMMENDATION
    # --------------------------------------------------
    def create_product_recommendation(
        self,
        user_query: str,
        products: List[Dict[str, Any]],
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        try:
            if not user_query or not user_query.strip():
                raise GroqServiceError("Câu hỏi người dùng trống")

            product_context = self._format_products_for_prompt(products)

            system_prompt = f"""Bạn là một trợ lý tư vấn sản phẩm thân thiện và chuyên nghiệp.

THÔNG TIN SẢN PHẨM HIỆN CÓ:
{product_context}

HƯỚNG DẪN:
- Chỉ tư vấn dựa trên các sản phẩm có sẵn ở trên.
- Trả lời ngắn gọn, rõ ràng, giá cả chính xác.
- Nếu không có sản phẩm phù hợp, hãy nói rõ và lịch sự.
- Giọng điệu: thân thiện, nhiệt tình, chuyên nghiệp.
"""

            # Xây dựng lịch sử hội thoại (lấy tối đa 10 tin nhắn gần nhất)
            messages: List[Dict[str, str]] = []
            if conversation_history:
                recent_history = conversation_history[-10:]
                for msg in recent_history:
                    cleaned = _clean_message(msg)
                    if cleaned:
                        messages.append(cleaned)

            # Thêm câu hỏi hiện tại
            messages.append({"role": "user", "content": user_query.strip()})

            return self.generate_response(
                messages=messages,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=1024,
            )

        except GroqServiceError:
            raise
        except Exception as e:
            logger.error(f"❌ Lỗi tạo recommendation: {e}")
            raise GroqServiceError("Không thể tạo gợi ý sản phẩm từ AI.")

    # --------------------------------------------------
    # UTILS
    # --------------------------------------------------
    def _format_products_for_prompt(self, products: List[Dict[str, Any]]) -> str:
        if not products:
            return "Hiện tại không có sản phẩm nào phù hợp với yêu cầu."

        lines = []
        for i, p in enumerate(products, 1):
            name = p.get("name", "Sản phẩm không tên")
            line = f"{i}. {name}"

            if price := p.get("price"):
                line += f" - 💰 {price}"

            if category := p.get("category"):
                line += f" - 🏷️ {category}"

            stock = p.get("stock")
            if stock is not None:
                status = "✅ Còn hàng" if stock > 0 else "❌ Hết hàng"
                line += f" - {status}"

            lines.append(line)

        return "\n".join(lines)

    # --------------------------------------------------
    # HEALTH CHECK
    # --------------------------------------------------
    def test_connection(self) -> bool:
        """Kiểm tra kết nối bằng cách gửi một yêu cầu đơn giản"""
        try:
            res = self.generate_response(
                messages=[{"role": "user", "content": "Chỉ trả lời đúng một từ: pong"}],
                system_prompt="Bạn là một bot kiểm tra kết nối. Chỉ trả lời đúng từ 'pong'.",
                max_tokens=10
            )
            return "pong" in res.lower()
        except Exception as e:
            logger.warning(f"Test connection failed: {e}")
            return False

    # --------------------------------------------------
    # STATS
    # --------------------------------------------------
    def get_stats(self) -> Dict[str, Any]:
        runtime_hours = round((datetime.now() - self.start_time).total_seconds() / 3600, 2)
        return {
            "model": self.model,
            "total_requests": self.total_requests,
            "total_tokens": self.total_tokens,
            "runtime_hours": runtime_hours,
            "status": "connected" if self.test_connection() else "disconnected"
        }