"""
Service xử lý tương tác với Groq API
- FIX triệt để lỗi field thừa (expires_in, timestamp, ...)
- Chỉ gửi role + content cho Groq
"""

from groq import Groq
from typing import List, Dict, Any
import logging
from datetime import datetime

from config import config

logger = logging.getLogger(__name__)


class GroqServiceError(Exception):
    pass


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
            raise GroqServiceError(str(e))

    # --------------------------------------------------
    # CORE CALL
    # --------------------------------------------------
    def generate_response(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        top_p: float = 1.0,
    ) -> str:
        try:
            self.total_requests += 1

            # 🔥 CLEAN messages: chỉ role + content
            clean_messages = []

            if system_prompt:
                clean_messages.append({
                    "role": "system",
                    "content": system_prompt
                })

            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                role = msg.get("role")
                content = msg.get("content")
                if role and content:
                    clean_messages.append({
                        "role": role,
                        "content": content
                    })

            if not clean_messages:
                raise GroqServiceError("Danh sách messages rỗng")

            logger.info(f"📤 Gửi {len(clean_messages)} messages đến Groq")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=clean_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                stream=False,
            )

            response_text = response.choices[0].message.content

            if hasattr(response, "usage"):
                self.total_tokens += response.usage.total_tokens

            logger.info("📥 Nhận response từ Groq thành công")

            return response_text

        except Exception as e:
            self.total_requests -= 1
            logger.error(f"❌ Lỗi Groq API: {e}")

            msg = str(e).lower()
            if "rate limit" in msg:
                raise GroqServiceError("API đang bị giới hạn tốc độ, vui lòng thử lại sau.")
            if "authentication" in msg or "api key" in msg:
                raise GroqServiceError("Lỗi xác thực Groq API.")
            if "model" in msg:
                raise GroqServiceError("Model không khả dụng.")
            if "unsupported" in msg:
                raise GroqServiceError("Dữ liệu gửi lên Groq không hợp lệ.")

            raise GroqServiceError("Có lỗi xảy ra khi gọi Groq API.")

    # --------------------------------------------------
    # PRODUCT RECOMMENDATION
    # --------------------------------------------------
    def create_product_recommendation(
        self,
        user_query: str,
        products: List[Dict],
        conversation_history: List[Dict] = None
    ) -> str:
        try:
            product_context = self._format_products_for_prompt(products)

            system_prompt = f"""{config.SYSTEM_PROMPT_BASE}

THÔNG TIN SẢN PHẨM HIỆN CÓ:
{product_context}

YÊU CẦU:
- Tư vấn dựa trên sản phẩm
- Giá cả rõ ràng
- Giọng thân thiện, chuyên nghiệp
"""

            messages: List[Dict[str, str]] = []

            # 🔥 CLEAN history từ Redis
            if conversation_history:
                recent_history = conversation_history[-10:]
                for msg in recent_history:
                    role = msg.get("role")
                    content = msg.get("content")
                    if role and content:
                        messages.append({
                            "role": role,
                            "content": content
                        })

            messages.append({
                "role": "user",
                "content": user_query
            })

            return self.generate_response(
                messages=messages,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=1024
            )

        except GroqServiceError:
            raise
        except Exception as e:
            logger.error(f"❌ Lỗi recommendation: {e}")
            raise GroqServiceError("Không thể tạo phản hồi từ AI.")

    # --------------------------------------------------
    # UTILS
    # --------------------------------------------------
    def _format_products_for_prompt(self, products: List[Dict]) -> str:
        if not products:
            return "Không có sản phẩm phù hợp."

        lines = []
        for i, p in enumerate(products, 1):
            line = f"{i}. {p.get('name', 'Không tên')}"
            if p.get("price"):
                line += f" - 💰 {p['price']}"
            if p.get("category"):
                line += f" - 🏷️ {p['category']}"
            if p.get("stock") is not None:
                line += " - ✅ Còn hàng" if p["stock"] > 0 else " - ❌ Hết hàng"
            lines.append(line)

        return "\n".join(lines)

    # --------------------------------------------------
    # HEALTH CHECK
    # --------------------------------------------------
    def test_connection(self) -> bool:
        try:
            res = self.generate_response(
                messages=[{"role": "user", "content": "ping"}],
                system_prompt="Trả lời 'pong'",
                max_tokens=5
            )
            return bool(res)
        except:
            return False

    # --------------------------------------------------
    # STATS
    # --------------------------------------------------
    def get_stats(self) -> Dict[str, Any]:
        runtime = (datetime.now() - self.start_time).total_seconds() / 3600
        return {
            "total_requests": self.total_requests,
            "total_tokens": self.total_tokens,
            "runtime_hours": round(runtime, 2),
            "model": self.model,
            "status": "connected"
        }
