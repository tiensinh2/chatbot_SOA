"""
API Server cho Shop Chatbot
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
from services.redis_service import RedisService

# ----------------- Thiết lập Flask -----------------
app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------- Khởi tạo services -----------------
db_handler = None
groq_service = None
redis_service = None

def init_services():
    global db_handler, groq_service, redis_service
    try:
        db_handler = MongoDBHandler()
        groq_service = GroqService()
        redis_service = RedisService()
        logger.info("✅ Services đã được khởi tạo thành công")
    except Exception as e:
        logger.error(f"❌ Lỗi khi khởi tạo services: {e}")
        raise

init_services()

# ----------------- Routes -----------------

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
            "POST /chat": "Chat với AI",
            "GET /stats": "Thống kê hệ thống"
        }
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Kiểm tra MongoDB, Groq và Redis"""
    try:
        mongo_status = db_handler.test_connection() if db_handler else False
        groq_status = groq_service.test_connection() if groq_service else False
        redis_status = redis_service.is_connected if redis_service else False
        
        return jsonify({
            "status": "healthy" if all([mongo_status, groq_status, redis_status]) else "degraded",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "mongodb": "connected" if mongo_status else "disconnected",
                "groq_api": "connected" if groq_status else "disconnected",
                "redis": "connected" if redis_status else "disconnected"
            }
        })
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat():
    """Endpoint chat với AI, lưu lịch sử vào Redis"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Thiếu dữ liệu request body"}), 400
        
        user_id = data.get('user_id', 'anonymous')
        session_id = data.get('session_id', user_id)
        message = data.get('message')
        
        if not message:
            return jsonify({"success": False, "error": "Thiếu tin nhắn (message)"}), 400

        # --- Lấy hoặc tạo session ---
        session = redis_service.get_session(user_id)
        if not session:
            session = redis_service.create_session(user_id)

        # --- Thêm message vào history ---
        redis_service.add_message(user_id, role="user", content=message)
        redis_service.increment_message_count(user_id)

        # --- Tìm sản phẩm liên quan ---
        products = db_handler.search_products(message, limit=3)
        
        # --- Tạo response từ AI ---
        response_text = groq_service.create_product_recommendation(
            user_query=message,
            products=products,
            conversation_history=redis_service.get_conversation_history(user_id)
        )
        
        # --- Thêm response AI vào history ---
        redis_service.add_message(user_id, role="assistant", content=response_text)

        return jsonify({
            "success": True,
            "user_id": user_id,
            "session_id": session_id,
            "query": message,
            "response": response_text,
            "products_found": len(products),
            "products": products[:3],
            "timestamp": datetime.now().isoformat(),
            "model": config.DEFAULT_MODEL
        })
        
    except Exception as e:
        logger.error(f"❌ Lỗi chat endpoint: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/chat/history', methods=['GET'])
def get_chat_history():
    """Lấy lịch sử chat cho user"""
    try:
        user_id = request.args.get('user_id', 'anonymous')
        limit = int(request.args.get('limit', config.MAX_CHAT_HISTORY))
        history = redis_service.get_conversation_history(user_id, limit=limit)
        return jsonify({
            "success": True,
            "user_id": user_id,
            "history": history,
            "count": len(history)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/chat/clear', methods=['POST'])
def clear_chat_history():
    """Xóa lịch sử chat của user"""
    try:
        data = request.get_json()
        user_id = data.get('user_id', 'anonymous')
        success = redis_service.clear_conversation(user_id)
        return jsonify({"success": success, "user_id": user_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/stats', methods=['GET'])
def get_stats():
    """Lấy thống kê hệ thống Redis"""
    try:
        redis_info = redis_service.get_redis_info()
        return jsonify({"success": True, "redis_info": redis_info})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ----------------- Chạy server -----------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🚀 API Server đang chạy tại http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
