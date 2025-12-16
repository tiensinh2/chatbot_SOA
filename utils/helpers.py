import re
from datetime import datetime
from typing import List, Dict, Any

def format_timestamp(timestamp: datetime) -> str:
    """Format timestamp thành string dễ đọc"""
    if not timestamp:
        return "N/A"
    return timestamp.strftime("%d/%m/%Y %H:%M:%S")

def format_conversation_display(conversation: Dict) -> str:
    """Format conversation để hiển thị"""
    output = []
    
    if not conversation:
        return "Không có dữ liệu"
    
    output.append(f"👤 User ID: {conversation.get('user_id', 'Unknown')}")
    output.append(f"📅 Cập nhật: {format_timestamp(conversation.get('updated_at'))}")
    output.append("-" * 40)
    
    for i, msg in enumerate(conversation.get('messages', [])):
        role_icon = "👤" if msg['role'] == 'user' else "🤖"
        time_str = format_timestamp(msg.get('timestamp'))
        output.append(f"{role_icon} [{time_str}] {msg['role'].upper()}:")
        output.append(f"   {msg['content']}")
        output.append("")
    
    return "\n".join(output)

def format_knowledge_display(knowledge_items: List[Dict]) -> str:
    """Format knowledge items để hiển thị"""
    if not knowledge_items:
        return "📭 Knowledge base trống"
    
    output = []
    
    for i, item in enumerate(knowledge_items, 1):
        output.append(f"📚 Item #{i}")
        output.append(f"   ❓ Câu hỏi: {item.get('question', 'N/A')}")
        output.append(f"   ✅ Câu trả lời: {item.get('answer', 'N/A')}")
        
        if item.get('category'):
            output.append(f"   📁 Category: {item['category']}")
        
        if item.get('tags'):
            output.append(f"   🏷️  Tags: {', '.join(item['tags'])}")
        
        if item.get('created_at'):
            output.append(f"   📅 Created: {format_timestamp(item['created_at'])}")
        
        output.append("")
    
    return "\n".join(output)

def clean_text(text: str) -> str:
    """Làm sạch text input"""
    if not text:
        return ""
    
    # Xóa khoảng trắng thừa
    text = ' '.join(text.split())
    
    # Xóa ký tự đặc biệt không cần thiết
    text = re.sub(r'[^\w\s.,!?-]', '', text)
    
    return text.strip()

def truncate_text(text: str, max_length: int = 100) -> str:
    """Cắt ngắn text nếu quá dài"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."

def calculate_token_estimate(text: str) -> int:
    """Ước tính số lượng token (approximate)"""
    # Ước tính: 1 token ≈ 4 ký tự tiếng Anh, tiếng Việt khoảng 2-3 ký tự/token
    return len(text) // 3

def validate_user_input(input_text: str, max_length: int = 1000) -> tuple[bool, str]:
    """Kiểm tra input từ người dùng"""
    if not input_text or len(input_text.strip()) == 0:
        return False, "Input không được để trống"
    
    if len(input_text) > max_length:
        return False, f"Input quá dài (tối đa {max_length} ký tự)"
    
    # Kiểm tra ký tự nguy hiểm (cơ bản)
    dangerous_patterns = ['<script>', 'javascript:', 'onload=', 'onerror=']
    for pattern in dangerous_patterns:
        if pattern in input_text.lower():
            return False, "Input chứa nội dung không hợp lệ"
    
    return True, "Input hợp lệ"

def get_current_time_string() -> str:
    """Lấy thời gian hiện tại dưới dạng string"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def format_stats(stats: Dict) -> str:
    """Format thống kê để hiển thị"""
    if not stats:
        return "Không có thống kê"
    
    output = ["📊 THỐNG KÊ HỆ THỐNG", "=" * 30]
    
    if 'conversations_count' in stats:
        output.append(f"💬 Số conversations: {stats['conversations_count']}")
    
    if 'knowledge_count' in stats:
        output.append(f"📚 Số knowledge items: {stats['knowledge_count']}")
    
    if 'users_count' in stats:
        output.append(f"👥 Số users: {stats['users_count']}")
    
    return "\n".join(output)