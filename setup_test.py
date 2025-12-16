#!/usr/bin/env python3
"""
Script kiểm tra cấu hình và kết nối - FIXED VERSION
"""

import sys
from config import config
from database.mongo_handler import MongoDBHandler
from services.groq_service import GroqService

def test_mongodb():
    """Kiểm tra kết nối MongoDB"""
    print("\n🔗 KIỂM TRA MONGODB:")
    
    try:
        # Kiểm tra URI
        if not config.MONGO_URI:
            print("❌ MONGO_URI chưa được cấu hình")
            return False
        
        # Kết nối
        db_handler = MongoDBHandler()
        
        # Kiểm tra collection
        collections = db_handler.db.list_collection_names()
        print(f"✅ Kết nối thành công!")
        print(f"   Database: {config.DATABASE_NAME}")
        print(f"   Collection: {config.PRODUCTS_COLLECTION}")
        print(f"   Collections có sẵn: {collections}")
        
        # Kiểm tra số lượng sản phẩm
        count = db_handler.products_collection.count_documents({})
        print(f"   Số sản phẩm: {count}")
        
        # Lấy categories
        categories = db_handler.get_categories()
        print(f"   Số danh mục: {len(categories)}")
        if categories:
            print(f"   Danh mục: {', '.join(categories[:3])}" + 
                  ("..." if len(categories) > 3 else ""))
        
        # Test tìm kiếm sản phẩm
        test_products = db_handler.search_products("phone", limit=2)
        if test_products:
            print(f"   Test search 'phone': {len(test_products)} sản phẩm")
        
        db_handler.close()
        return True
        
    except Exception as e:
        print(f"❌ Lỗi MongoDB: {e}")
        return False

def test_groq_api():
    """Kiểm tra kết nối Groq API - FIXED"""
    print("\n🤖 KIỂM TRA GROQ API:")
    
    try:
        # Kiểm tra API Key
        if not config.GROQ_API_KEY:
            print("❌ GROQ_API_KEY chưa được cấu hình")
            return False
        
        # Khởi tạo service
        groq_service = GroqService()
        
        # Test connection với request đơn giản
        print("   Đang test kết nối cơ bản...")
        test_response = groq_service.generate_response(
            messages=[{"role": "user", "content": "Xin chào! Hãy nói 'Kết nối thành công'"}],
            max_tokens=50
        )
        
        print(f"✅ Kết nối thành công!")
        print(f"   Model: {config.DEFAULT_MODEL}")
        print(f"   Response: {test_response}")
        
        # Test product recommendation với dữ liệu giả
        print(f"\n🔍 Test product recommendation...")
        test_products = [
            {"name": "iPhone 15", "price": "25,000,000 VND", "category": "Điện thoại", "description": "iPhone mới nhất"},
            {"name": "Samsung Galaxy S23", "price": "22,000,000 VND", "category": "Điện thoại", "description": "Android flagship"}
        ]
        
        recommendation = groq_service.create_product_recommendation(
            user_query="Tôi muốn mua điện thoại",
            products=test_products
        )
        
        print(f"   Recommendation test OK!")
        print(f"   Length: {len(recommendation)} chars")
        print(f"   Preview: {recommendation[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Lỗi Groq API: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=" * 60)
    print("🔧 CHATBOT SETUP TEST - SHOP DATABASE")
    print("=" * 60)
    
    # Kiểm tra cấu hình
    print("\n🔍 KIỂM TRA CẤU HÌNH:")
    print(f"   • MongoDB URI: {'✅' if config.MONGO_URI else '❌ Không có'}")
    print(f"   • Groq API Key: {'✅' if config.GROQ_API_KEY else '❌ Không có'}")
    print(f"   • Model: {config.DEFAULT_MODEL}")
    print(f"   • Database: {config.DATABASE_NAME}")
    print(f"   • Collection: {config.PRODUCTS_COLLECTION}")
    
    if not config.MONGO_URI or not config.GROQ_API_KEY:
        print("\n❌ Vui lòng cấu hình đầy đủ file .env")
        return
    
    # Chạy tests
    mongodb_ok = test_mongodb()
    groq_ok = test_groq_api()
    
    print("\n" + "=" * 60)
    print("🎯 KẾT QUẢ KIỂM TRA:")
    
    if mongodb_ok and groq_ok:
        print("✅ TẤT CẢ KẾT NỐI HOẠT ĐỘNG TỐT!")
        print("\n🚀 CHẠY CHATBOT:")
        print("   python main.py")
        print("\n💡 HƯỚNG DẪN:")
        print("   - Nhập câu hỏi về sản phẩm để được tư vấn")
        print("   - Gõ 'sp' để xem sản phẩm")
        print("   - Gõ 'dm' để xem danh mục")
        print("   - Gõ 'thoát' để kết thúc")
    else:
        print("❌ CÓ VẤN ĐỀ VỚI MỘT SỐ KẾT NỐI:")
        if not mongodb_ok:
            print("   • MongoDB: Kiểm tra URI và kết nối mạng")
        if not groq_ok:
            print("   • Groq API: Kiểm tra API key và quota")

if __name__ == "__main__":
    main()