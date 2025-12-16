"""
API Server để test bằng Postman
Chạy: python api_server.py
Truy cập: http://localhost:5000
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from datetime import datetime
import os

from config import config
from database.mongo_handler import MongoDBHandler
from services.groq_service import GroqService

# Thiết lập Flask app
app = Flask(__name__)
CORS(app)  # Cho phép CORS để test từ Postman

# Thiết lập logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Khởi tạo services
db_handler = None
groq_service = None

def init_services():
    """Khởi tạo các services"""
    global db_handler, groq_service
    try:
        db_handler = MongoDBHandler()
        groq_service = GroqService()
        logger.info("✅ Services đã được khởi tạo")
    except Exception as e:
        logger.error(f"❌ Lỗi khởi tạo services: {e}")
        raise
init_services()
# Route chính
@app.route('/')
def home():
    """Trang chủ"""
    return jsonify({
        "status": "running",
        "service": "Shop Chatbot API",
        "version": "1.0",
        "endpoints": {
            "GET /": "Trang chủ",
            "GET /health": "Kiểm tra sức khỏe hệ thống",
            "GET /products": "Lấy danh sách sản phẩm",
            "GET /products/search?q=...": "Tìm kiếm sản phẩm",
            "GET /categories": "Lấy danh mục sản phẩm",
            "POST /chat": "Chat với AI (xem docs bên dưới)",
            "GET /stats": "Thống kê hệ thống"
        },
        "chat_example": {
            "method": "POST",
            "url": "http://localhost:5000/chat",
            "body": {
                "user_id": "user_001",
                "message": "Tôi muốn mua điện thoại",
                "session_id": "optional_session_id"
            }
        }
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Kiểm tra sức khỏe hệ thống"""
    try:
        # Kiểm tra MongoDB
        mongo_status = db_handler.test_connection() if db_handler else False
        
        # Kiểm tra Groq API
        groq_status = groq_service.test_connection() if groq_service else False
        
        return jsonify({
            "status": "healthy" if mongo_status and groq_status else "degraded",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "mongodb": "connected" if mongo_status else "disconnected",
                "groq_api": "connected" if groq_status else "disconnected"
            },
            "database": {
                "name": config.DATABASE_NAME,
                "collection": config.PRODUCTS_COLLECTION,
                "product_count": db_handler.products_collection.count_documents({}) if db_handler else 0
            }
        })
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500

@app.route('/products', methods=['GET'])
def get_products():
    """Lấy danh sách sản phẩm"""
    try:
        # Lấy query parameters
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        category = request.args.get('category')
        
        if category:
            # Lấy sản phẩm theo category
            products = db_handler.get_products_by_category(category, limit=limit)
            result = {
                "products": products,
                "category": category,
                "count": len(products)
            }
        else:
            # Lấy tất cả sản phẩm với phân trang
            result = db_handler.get_all_products(page=page, per_page=limit)
        
        return jsonify({
            "success": True,
            "data": result,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"❌ Lỗi lấy sản phẩm: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/products/search', methods=['GET'])
def search_products():
    """Tìm kiếm sản phẩm"""
    try:
        query = request.args.get('q', '')
        limit = int(request.args.get('limit', 5))
        
        if not query:
            return jsonify({
                "success": False,
                "error": "Thiếu tham số tìm kiếm (q)"
            }), 400
        
        products = db_handler.search_products(query, limit=limit)
        
        return jsonify({
            "success": True,
            "query": query,
            "count": len(products),
            "products": products,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"❌ Lỗi tìm kiếm sản phẩm: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/categories', methods=['GET'])
def get_categories():
    """Lấy danh mục sản phẩm"""
    try:
        categories = db_handler.get_categories()
        
        return jsonify({
            "success": True,
            "count": len(categories),
            "categories": categories,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"❌ Lỗi lấy danh mục: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/chat', methods=['POST'])
def chat():
    """Endpoint chat với AI"""
    try:
        # Lấy data từ request
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "Thiếu dữ liệu request body"
            }), 400
        
        user_id = data.get('user_id', 'anonymous')
        message = data.get('message')
        session_id = data.get('session_id', user_id)
        
        if not message:
            return jsonify({
                "success": False,
                "error": "Thiếu tin nhắn (message)"
            }), 400
        
        logger.info(f"📩 Chat request từ {user_id}: {message[:50]}...")
        
        # Tìm sản phẩm liên quan
        products = db_handler.search_products(message, limit=3)
        
        # Tạo response từ AI
        response = groq_service.create_product_recommendation(
            user_query=message,
            products=products
        )
        
        logger.info(f"📤 Chat response cho {user_id}: {len(response)} chars")
        
        return jsonify({
            "success": True,
            "user_id": user_id,
            "session_id": session_id,
            "query": message,
            "response": response,
            "products_found": len(products),
            "products": products[:3],  # Trả về tối đa 3 sản phẩm
            "timestamp": datetime.now().isoformat(),
            "model": config.DEFAULT_MODEL
        })
        
    except Exception as e:
        logger.error(f"❌ Lỗi chat endpoint: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/stats', methods=['GET'])
def get_stats():
    """Lấy thống kê hệ thống"""
    try:
        # Thống kê database
        db_stats = db_handler.get_products_stats()
        
        # Thống kê Groq
        groq_stats = groq_service.get_stats() if groq_service else {}
        
        return jsonify({
            "success": True,
            "database": {
                "total_products": db_stats.get('total_products', 0),
                "categories_count": db_stats.get('categories_count', 0),
                "in_stock": db_stats.get('in_stock', 0),
                "out_of_stock": db_stats.get('out_of_stock', 0),
                "categories": db_stats.get('category_stats', [])
            },
            "groq_api": groq_stats,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"❌ Lỗi lấy thống kê: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/chat/history', methods=['POST'])
def simulate_chat_history():
    """Simulate chat với history (cho test)"""
    try:
        data = request.get_json()
        
        user_id = data.get('user_id', 'test_user')
        messages = data.get('messages', [])
        
        if not messages:
            return jsonify({
                "success": False,
                "error": "Thiếu messages"
            }), 400
        
        # Lấy sản phẩm liên quan từ tin nhắn cuối
        last_message = messages[-1]['content'] if messages else ""
        products = db_handler.search_products(last_message, limit=3)
        
        # Tạo response
        response = groq_service.create_product_recommendation(
            user_query=last_message,
            products=products,
            conversation_history=messages
        )
        
        return jsonify({
            "success": True,
            "user_id": user_id,
            "response": response,
            "products_found": len(products),
            "message_count": len(messages)
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__ == '__main__':
    # Khởi tạo services
    print("🚀 Đang khởi động API Server...")
    try:
        init_services()
        
        print(f"✅ API Server đã sẵn sàng!")
        print(f"🌐 Địa chỉ: http://localhost:5000")
        print(f"📚 API Documentation: http://localhost:5000")
        print("\n📋 Các endpoints:")
        print("   GET  /              - Trang chủ")
        print("   GET  /health        - Health check")
        print("   GET  /products      - Lấy sản phẩm")
        print("   GET  /products/search?q=... - Tìm kiếm")
        print("   GET  /categories    - Lấy danh mục")
        print("   POST /chat          - Chat với AI")
        print("   GET  /stats         - Thống kê")
        print("\n🎯 Để test với Postman:")
        print("   1. Mở Postman")
        print("   2. Tạo POST request đến http://localhost:5000/chat")
        print("   3. Thêm header: Content-Type: application/json")
        print("   4. Thêm body JSON: {\"user_id\": \"test\", \"message\": \"Tôi muốn mua điện thoại\"}")
        
        # Chạy server
        port = int(os.environ.get("PORT", 5000))
        app.run(host="0.0.0.0", port=port, debug=False)
        
    except Exception as e:
        print(f"❌ Không thể khởi động server: {e}")