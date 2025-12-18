#!/usr/bin/env python3
"""
Script kiểm tra kết nối tất cả services:
- MongoDB
- Groq API
- Redis Cloud (SSL)
"""

import sys
import traceback
from config import config
from database.mongo_handler import MongoDBHandler
from services.groq_service import GroqService, GroqServiceError

# Redis
import redis


def test_mongodb():
    """Kiểm tra kết nối MongoDB"""
    print("\n🔗 KIỂM TRA MONGODB:")
    try:
        if not config.MONGO_URI:
            print("❌ MONGO_URI chưa được cấu hình")
            return False

        db_handler = MongoDBHandler()
        collections = db_handler.db.list_collection_names()
        count = db_handler.products_collection.count_documents({})
        categories = db_handler.get_categories()

        print(f"✅ Kết nối MongoDB thành công!")
        print(f"   Database: {config.DATABASE_NAME}")
        print(f"   Collection: {config.PRODUCTS_COLLECTION}")
        print(f"   Collections có sẵn: {collections}")
        print(f"   Số sản phẩm: {count}")
        print(f"   Số danh mục: {len(categories)}")
        if categories:
            print(f"   Danh mục mẫu: {', '.join(categories[:3])}" +
                  ("..." if len(categories) > 3 else ""))

        db_handler.close()
        return True
    except Exception as e:
        print(f"❌ Lỗi MongoDB: {e}")
        traceback.print_exc()
        return False


def test_groq_api():
    """Kiểm tra kết nối Groq API"""
    print("\n🤖 KIỂM TRA GROQ API:")
    try:
        if not config.GROQ_API_KEY:
            print("❌ GROQ_API_KEY chưa được cấu hình")
            return False

        groq_service = GroqService()
        test_response = groq_service.generate_response(
            messages=[{"role": "user", "content": "Xin chào! Hãy nói 'Kết nối thành công'"}],
            max_tokens=50
        )
        print(f"✅ Kết nối Groq API thành công!")
        print(f"   Model: {config.DEFAULT_MODEL}")
        print(f"   Response test: {test_response}")

        # Test product recommendation
        test_products = [
            {"name": "iPhone 15", "price": "25,000,000 VND", "category": "Điện thoại", "description": "iPhone mới nhất"},
            {"name": "Samsung Galaxy S23", "price": "22,000,000 VND", "category": "Điện thoại", "description": "Android flagship"}
        ]
        recommendation = groq_service.create_product_recommendation(
            user_query="Tôi muốn mua điện thoại",
            products=test_products
        )
        print(f"   ✅ Product recommendation test OK")
        print(f"   Preview: {recommendation[:100]}...")
        return True
    except GroqServiceError as e:
        print(f"❌ Lỗi Groq API: {e}")
        return False
    except Exception as e:
        print(f"❌ Lỗi Groq API: {e}")
        traceback.print_exc()
        return False


def test_redis():
    """Kiểm tra kết nối Redis (SSL nếu cần)"""
    print("\n🟢 KIỂM TRA REDIS SERVICE:")
    try:
        if not config.REDIS_HOST or not config.REDIS_PASSWORD:
            print("❌ REDIS_HOST hoặc REDIS_PASSWORD chưa được cấu hình")
            return False

        r = redis.Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            username=config.REDIS_USERNAME,
            password=config.REDIS_PASSWORD,
            db=config.REDIS_DB,
            decode_responses=True,
            ssl=config.REDIS_SSL
        )

        # Test set/get
        r.set("test_key", "test_value", ex=10)
        val = r.get("test_key")
        if val == "test_value":
            print(f"✅ Kết nối Redis thành công! SSL: {config.REDIS_SSL}")
            return True
        else:
            print(f"❌ Không thể lưu/get dữ liệu Redis")
            return False
    except Exception as e:
        print(f"❌ Lỗi kết nối Redis: {e}")
        traceback.print_exc()
        return False


def main():
    print("=" * 60)
    print("🔧 CHATBOT SERVICES TEST")
    print("=" * 60)

    try:
        config.validate_config()
    except ValueError as e:
        print(f"\n❌ Lỗi cấu hình: {e}")
        sys.exit(1)

    mongo_ok = test_mongodb()
    groq_ok = test_groq_api()
    redis_ok = test_redis()

    print("\n" + "=" * 60)
    print("🎯 KẾT QUẢ KIỂM TRA TẤT CẢ SERVICES:")
    if mongo_ok and groq_ok and redis_ok:
        print("✅ TẤT CẢ SERVICES HOẠT ĐỘNG TỐT!")
    else:
        print("❌ CÓ VẤN ĐỀ VỚI MỘT HOẶC NHIỀU SERVICES:")
        if not mongo_ok:
            print("   • MongoDB")
        if not groq_ok:
            print("   • Groq API")
        if not redis_ok:
            print("   • Redis")
    print("=" * 60)


if __name__ == "__main__":
    main()
