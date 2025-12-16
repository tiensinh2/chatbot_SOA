#!/usr/bin/env python3
"""
Script kiểm tra cấu hình và kết nối
"""

from config import config
from database.mongo_handler import MongoDBHandler
from groq import Groq

def check_config():
    print("🔍 Kiểm tra cấu hình...")
    
    # Kiểm tra biến môi trường
    print(f"1. MONGO_URI: {'✅' if config.MONGO_URI else '❌ Không có'}")
    print(f"2. GROQ_API_KEY: {'✅' if config.GROQ_API_KEY else '❌ Không có'}")
    print(f"3. DEFAULT_MODEL: {config.DEFAULT_MODEL}")
    
    return config.MONGO_URI and config.GROQ_API_KEY

def test_mongodb_connection():
    print("\n🔗 Kiểm tra kết nối MongoDB...")
    try:
        db_handler = MongoDBHandler()
        print("✅ Kết nối MongoDB thành công!")
        
        # Kiểm tra database và collections
        print(f"   Database: {config.MONGO_DATABASE}")
        print(f"   Collections: {db_handler.db.list_collection_names()}")
        
        db_handler.close()
        return True
    except Exception as e:
        print(f"❌ Lỗi kết nối MongoDB: {e}")
        return False

def test_groq_api():
    print("\n🤖 Kiểm tra Groq API...")
    try:
        client = Groq(api_key=config.GROQ_API_KEY)
        
        # Test với một prompt đơn giản
        response = client.chat.completions.create(
            model=config.DEFAULT_MODEL,
            messages=[{"role": "user", "content": "Xin chào, bạn có khỏe không?"}],
            max_tokens=50
        )
        
        print(f"✅ Kết nối Groq API thành công!")
        print(f"   Model: {config.DEFAULT_MODEL}")
        print(f"   Test response: {response.choices[0].message.content[:50]}...")
        return True
    except Exception as e:
        print(f"❌ Lỗi kết nối Groq API: {e}")
        return False

def main():
    print("=" * 50)
    print("SETUP KIỂM TRA CHATBOT CONFIGURATION")
    print("=" * 50)
    
    # Kiểm tra cấu hình
    if not check_config():
        print("\n❌ Vui lòng cấu hình đầy đủ file .env trước khi tiếp tục")
        return
    
    # Kiểm tra kết nối MongoDB
    mongodb_ok = test_mongodb_connection()
    
    # Kiểm tra kết nối Groq API
    groq_ok = test_groq_api()
    
    print("\n" + "=" * 50)
    print("KẾT QUẢ KIỂM TRA:")
    
    if mongodb_ok and groq_ok:
        print("✅ Tất cả kết nối đều hoạt động!")
        print("\n🎉 Bạn có thể chạy chatbot bằng lệnh:")
        print("   python main.py")
    else:
        print("❌ Có vấn đề với một số kết nối:")
        if not mongodb_ok:
            print("   - MongoDB: Kiểm tra URI và network connection")
        if not groq_ok:
            print("   - Groq API: Kiểm tra API key và quota")
        
        print("\n💡 Khắc phục sự cố:")
        print("   1. Kiểm tra file .env đã được tạo chưa")
        print("   2. Kiểm tra API key có đúng không")
        print("   3. Kiểm tra internet connection")
        print("   4. Kiểm tra MongoDB Atlas IP whitelist")

if __name__ == "__main__":
    main()