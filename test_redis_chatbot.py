"""
File test RedisService cho Chatbot
Chạy: python test_redis_chatbot.py
"""

import time
import json
from services.redis_service import RedisService
from config import config

def main():
    print("🚀 Bắt đầu test RedisService...")

    redis_service = RedisService()
    
    if not redis_service.is_connected:
        print("❌ Redis chưa kết nối. Kiểm tra cấu hình!")
        return

    test_user = "test_user_001"

    # 1️⃣ Tạo session
    print("\n1️⃣ Test tạo session...")
    session = redis_service.create_session(test_user)
    print("Session:", session)

    # 2️⃣ Lưu message vào lịch sử
    print("\n2️⃣ Test lưu message...")
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "user", "content": "I want to buy a phone"},
        {"role": "bot", "content": "Sure! Here are some options..."}
    ]
    
    for msg in messages:
        success = redis_service.add_message(test_user, msg['role'], msg['content'])
        print(f"Added message: {msg['content'][:30]}... -> {success}")

    # 3️⃣ Lấy lịch sử chat
    print("\n3️⃣ Test lấy lịch sử chat...")
    history = redis_service.get_conversation_history(test_user)
    print(f"History ({len(history)} messages):")
    for h in history:
        print(f" - [{h['role']}] {h['content']} (timestamp: {h['timestamp']})")

    # 4️⃣ Kiểm tra TTL (tự xóa sau config.SESSION_TTL)
    print("\n4️⃣ Test TTL / auto-cleanup...")
    ttl_seconds = 5  # Test nhanh, giả lập TTL 5s
    redis_service.client.expire(f"session:{test_user}", ttl_seconds)
    redis_service.client.expire(f"history:{test_user}", ttl_seconds)
    print(f"TTL đặt {ttl_seconds}s, đợi hết TTL...")
    time.sleep(ttl_seconds + 1)

    expired_session = redis_service.get_session(test_user)
    expired_history = redis_service.get_conversation_history(test_user)
    print("Session sau TTL:", expired_session)
    print("History sau TTL:", expired_history)

    # 5️⃣ Test xóa session thủ công
    print("\n5️⃣ Test xóa session thủ công...")
    redis_service.create_session(test_user)
    redis_service.add_message(test_user, "user", "Test message")
    deleted = redis_service.delete_session(test_user)
    print(f"Deleted session: {deleted}")
    print("Session hiện tại:", redis_service.get_session(test_user))
    print("History hiện tại:", redis_service.get_conversation_history(test_user))

    # 6️⃣ Test cache sản phẩm
    print("\n6️⃣ Test cache product search...")
    sample_products = [{"id": 1, "name": "Phone A"}, {"id": 2, "name": "Phone B"}]
    redis_service.cache_product_search("phone", sample_products)
    cached_products = redis_service.get_cached_search("phone")
    print("Cached products:", cached_products)

    # 7️⃣ Test cache category
    print("\n7️⃣ Test cache category...")
    redis_service.cache_products_by_category("electronics", sample_products)
    cached_category = redis_service.get_cached_category_products("electronics")
    print("Cached category products:", cached_category)

    # 8️⃣ Test message count
    print("\n8️⃣ Test increment message count...")
    redis_service.increment_message_count(test_user)
    redis_service.increment_message_count(test_user)
    count = redis_service.get_user_message_count(test_user)
    print(f"Message count for {test_user}: {count}")

    # 9️⃣ Test Redis info
    print("\n9️⃣ Test Redis info...")
    info = redis_service.get_redis_info()
    print("Redis info:", json.dumps(info, indent=2))

    # 10️⃣ Cleanup cuối
    print("\n🔟 Cleanup dữ liệu test...")
    redis_service.delete_session(test_user)
    print("✅ Test kết thúc!")

if __name__ == "__main__":
    main()
