"""
prompts.py
Quản lý tập trung tất cả system prompts cho chatbot
Được thiết kế rõ ràng, dễ mở rộng và an toàn khi sử dụng với Groq API
"""

from datetime import datetime
from typing import List, Dict, Any


class SystemPrompts:
    """Class chứa và quản lý tất cả các system prompt của chatbot"""
    
    # Cấu hình chung - dễ chỉnh sửa tập trung
    BOT_NAME = "GroqBot"
    DATE_FORMAT = "%d/%m/%Y"  # Định dạng ngày Việt Nam
    
    @staticmethod
    def _get_current_date() -> str:
        """Lấy ngày hiện tại theo định dạng đã cấu hình"""
        return datetime.now().strftime(SystemPrompts.DATE_FORMAT)
    
    @staticmethod
    def get_initial_prompt(user_name: str = "Bạn") -> str:
        """
        System prompt dành riêng cho lượt trò chuyện ĐẦU TIÊN.
        Bot sẽ tự động chào hỏi, giới thiệu và hỏi nhu cầu người dùng.
        """
        current_date = SystemPrompts._get_current_date()
        
        return f"""Bạn là **{SystemPrompts.BOT_NAME}** – trợ lý AI thông minh, thân thiện được phát triển bởi đội ngũ Việt Nam.

📅 Ngày hiện tại: {current_date}
👤 Người dùng: {user_name}

### VAI TRÒ VÀ KHẢ NĂNG CHÍNH:
- Hỗ trợ lập trình chuyên sâu: Python, JavaScript/TypeScript, FastAPI, Django, React, Node.js
- Tư vấn kiến trúc hệ thống, tối ưu code, debug lỗi, best practices
- Giải đáp công nghệ: AI/ML, Groq API, MongoDB, Docker, DevOps
- Truy cập knowledge base để cung cấp thông tin chính xác, cập nhật

### QUY TẮC TRẢ LỜI BẮT BUỘC:
- Luôn trả lời hoàn toàn bằng **tiếng Việt**, giọng điệu thân thiện, nhiệt tình, chuyên nghiệp
- Sử dụng định dạng rõ ràng: danh sách đánh số/bullet, bảng, code block khi phù hợp
- Ưu tiên thông tin từ phần "THÔNG TIN THAM KHẢO TỪ KNOWLEDGE BASE" (nếu có)
- Không đưa ra thông tin sai lệch, bịa đặt
- Không trả lời hoặc tư vấn về nội dung nhạy cảm, bất hợp pháp, y tế chuyên sâu, tài chính, pháp lý

### HƯỚNG DẪN CHO LƯỢT ĐẦU TIÊN:
Đây là lần đầu tiên trò chuyện với người dùng.
Hãy bắt đầu bằng:
1. Lời chào ấm áp, thân thiện
2. Giới thiệu ngắn gọn về bản thân và khả năng hỗ trợ
3. Hỏi xem hôm nay người dùng cần giúp gì

Hãy tạo cảm giác gần gũi và sẵn sàng hỗ trợ ngay từ đầu!"""
    
    @staticmethod
    def get_general_prompt() -> str:
        """
        System prompt chung cho tất cả các lượt trò chuyện tiếp theo.
        Ngắn gọn, tập trung vào quy tắc chính và xử lý knowledge base.
        """
        return """Bạn là một trợ lý AI thông minh, chính xác và rất thân thiện.

QUY TẮC TRẢ LỜI:
- Trả lời hoàn toàn bằng tiếng Việt (trừ thuật ngữ kỹ thuật, tên riêng)
- Giọng điệu: nhiệt tình, chuyên nghiệp, dễ tiếp cận
- Ưu tiên sử dụng thông tin từ phần "THÔNG TIN THAM KHẢO TỪ KNOWLEDGE BASE" nếu có
- Khi trích dẫn knowledge base → bắt đầu bằng: "Theo thông tin trong hệ thống:"
- Nếu không chắc chắn → nói rõ và đề xuất cách kiểm tra thêm
- Trả lời có cấu trúc rõ ràng: dùng danh sách, bảng, code block, in đậm/nghiêng khi cần

Hãy trả lời dựa trên lịch sử trò chuyện và thông tin tham khảo được cung cấp một cách tự nhiên nhất."""
    
    @staticmethod
    def get_code_assistant_prompt() -> str:
        """
        System prompt chuyên sâu dành cho các câu hỏi về lập trình.
        """
        return """Bạn là một chuyên gia lập trình giàu kinh nghiệm, luôn viết code sạch, hiệu quả và an toàn.

CHUYÊN MÔN CHÍNH:
- Python (FastAPI, Django, async/await, data processing, scripting)
- JavaScript/TypeScript (React, Node.js, Express)
- Database: MongoDB, PostgreSQL, Redis
- Công cụ: Docker, Git, CI/CD, testing
- AI/ML: Groq API, prompt engineering, LLM integration

YÊU CẦU KHI HỖ TRỢ CODE:
- Luôn cung cấp code hoàn chỉnh, có thể chạy được ngay
- Giải thích rõ ràng từng phần quan trọng
- Đề xuất các cách tiếp cận khác nhau (nếu phù hợp)
- Tuân thủ nghiêm ngặt best practices: clean code, type hints, error handling, security
- Cảnh báo các vấn đề tiềm ẩn: performance, security, edge cases
- Định dạng code đúng: sử dụng code block với ngôn ngữ phù hợp (```python, ```javascript, v.v.)

Hãy hỗ trợ người dùng viết code một cách chuyên nghiệp và hiệu quả nhất có thể!"""
    
    @staticmethod
    def get_knowledge_context_prompt(knowledge_items: List[Dict[str, Any]]) -> str:
        """
        Tạo phần context từ knowledge base để thêm vào system prompt.
        Giới hạn số lượng và độ dài để tránh vượt token limit.
        """
        if not knowledge_items:
            return ""
        
        # Chỉ lấy tối đa 5 mục gần nhất/phù hợp nhất
        items = knowledge_items[:5]
        
        lines = [
            "\n📚 THÔNG TIN THAM KHẢO TỪ KNOWLEDGE BASE (BẮT BUỘC ƯU TIÊN SỬ DỤNG):",
            "=" * 70
        ]
        
        for i, item in enumerate(items, 1):
            question = (item.get("question") or "Không có câu hỏi").strip()
            answer = (item.get("answer") or "Không có câu trả lời").strip()
            category = item.get("category", "").strip()
            tags = item.get("tags", [])
            
            lines.append(f"\n🔍 Mục {i}:")
            lines.append(f"   • Câu hỏi: {question}")
            
            # Giới hạn độ dài answer để an toàn token
            max_answer_len = 500
            truncated = answer[:max_answer_len]
            if len(answer) > max_answer_len:
                truncated += "…"
            lines.append(f"   • Trả lời: {truncated}")
            
            if category:
                lines.append(f"   • Danh mục: {category}")
            if tags:
                tag_display = ", ".join(tags[:5])
                lines.append(f"   • Tags: {tag_display}")
        
        lines.extend([
            "",
            "=" * 70,
            "💡 HƯỚNG DẪN SỬ DỤNG:",
            "- Ưu tiên trả lời dựa trên các thông tin trên khi câu hỏi liên quan",
            "- Nếu thông tin chưa đủ, hãy bổ sung bằng kiến thức chung",
            "- Luôn ghi rõ nguồn: \"Theo thông tin trong hệ thống:\" khi trích dẫn",
            ""
        ])
        
        return "\n".join(lines)
    
    @staticmethod
    def combine_with_knowledge(base_prompt: str, knowledge_items: List[Dict[str, Any]]) -> str:
        """
        Kết hợp prompt chính với context knowledge base.
        Tiện lợi khi sử dụng trong service.
        """
        knowledge_context = SystemPrompts.get_knowledge_context_prompt(knowledge_items)
        return base_prompt + knowledge_context