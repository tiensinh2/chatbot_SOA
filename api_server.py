"""
api_server.py
API Server cho Shop Chatbot - Ổn định cao, tối ưu ngữ cảnh
Chỉ search database khi người dùng yêu cầu sản phẩm mới (dựa trên từ khóa)
Các câu hỏi tiếp theo sẽ tái sử dụng danh sách sản phẩm hiện tại trong session
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from datetime import datetime
import os
import traceback

from config import config
from database.mongo_handler import MongoDBHandler
from services.groq_service import GroqService, GroqServiceError
from services.redis_service import RedisService

app = Flask(__name__)
CORS(app)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('api_server.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Khởi tạo services
try:
    db_handler = MongoDBHandler()
    groq_service = GroqService()
    redis_service = RedisService()
    logger.info("API Server - Tất cả services đã khởi tạo thành công")
except Exception as e:
    logger.critical(f"Không thể khởi tạo services: {e}")
    raise


# ================= TỪ KHÓA KÍCH HOẠT TÌM KIẾM SẢN PHẨM MỚI =================
PRODUCT_KEYWORDS = {
    'laptop', 'macbook', 'dell', 'hp', 'asus', 'lenovo', 'acer',
    'điện thoại', 'iphone', 'samsung', 'xiaomi', 'oppo', 'vivo', 'realme',
    'tai nghe', 'headphone', 'airpods', 'sony', 'jbl', 'marshall',
    'loa', 'speaker', 'màn hình', 'monitor', 'tv', 'tivi', 'smart tv',
    'máy ảnh', 'camera', 'đồng hồ', 'smartwatch', 'watch'
}

def is_new_product_request(text: str) -> bool:
    """Kiểm tra xem tin nhắn có chứa yêu cầu tìm sản phẩm mới không"""
    if not text:
        return False
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in PRODUCT_KEYWORDS)


# ================= ROUTES =================

@app.route('/')
def home():
    return jsonify({
        "status": "running",
        "message": "Shop Chatbot API - Ổn định & tối ưu ngữ cảnh",
        "version": "optimized-v1"
    })


@app.route('/health')
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })


@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json(force=True)
        if not data or 'message' not in data:
            return jsonify({"success": False, "error": "Thiếu trường 'message'"}), 400

        user_id = data.get('user_id', 'anonymous')
        message = str(data['message']).strip()
        if not message:
            return jsonify({"success": False, "error": "Tin nhắn rỗng"}), 400

        logger.info(f"[{user_id}] User: {message}")

        # Lấy hoặc tạo session
        session = redis_service.get_session(user_id) or redis_service.create_session(user_id)

        # Lưu tin nhắn người dùng vào lịch sử
        redis_service.add_message(user_id, "user", message)

        products = []
        should_search_new = is_new_product_request(message)

        if should_search_new:
            # Chỉ search khi thực sự có yêu cầu sản phẩm mới
            logger.info(f"[{user_id}] Phát hiện yêu cầu sản phẩm mới → thực hiện search")
            try:
                products = db_handler.search_products(message, limit=6)
                if products:
                    valid_ids = [str(p['_id']) for p in products if p.get('_id')]
                    session['current_products'] = valid_ids
                    redis_service.update_session(user_id, session)
                logger.info(f"[{user_id}] Tìm thấy {len(products)} sản phẩm mới")
            except Exception as e:
                logger.error(f"[{user_id}] Lỗi khi search sản phẩm: {e}")
                products = []

        elif session.get('current_products'):
            # Có ngữ cảnh cũ → tái sử dụng
            current_ids = session['current_products']
            try:
                products = db_handler.get_products_by_ids(current_ids)
                logger.info(f"[{user_id}] Tái sử dụng ngữ cảnh cũ: {len(products)} sản phẩm")
            except Exception as e:
                logger.error(f"[{user_id}] Lỗi lấy sản phẩm theo ID cũ: {e}")
                products = []

        # Lấy lịch sử trò chuyện (ưu tiên mạnh)
        try:
            history = redis_service.get_conversation_history(user_id, limit=12)
        except Exception as e:
            logger.warning(f"[{user_id}] Lỗi lấy history: {e}")
            history = []

        # Gọi Groq để tạo phản hồi
        try:
            response = groq_service.create_product_recommendation(
                user_query=message,
                products=products,
                conversation_history=history
            )
        except GroqServiceError:
            response = "Xin lỗi, AI đang bận. Bạn thử lại sau vài phút nhé 😊"
        except Exception as e:
            logger.error(f"[{user_id}] Lỗi Groq: {e}")
            response = "Xin lỗi, có lỗi khi xử lý yêu cầu của bạn."

        # Lưu phản hồi trợ lý
        redis_service.add_message(user_id, "assistant", response)

        # Chuẩn hóa _id thành string để JSON serializable
        safe_products = [
            {**p, '_id': str(p['_id'])} if p.get('_id') else p
            for p in products
        ]

        return jsonify({
            "success": True,
            "user_id": user_id,
            "query": message,
            "response": response,
            "products_found": len(safe_products),
            "products": safe_products,
            "new_search_performed": should_search_new,
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Lỗi nghiêm trọng tại /chat: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": "Lỗi server nội bộ"}), 500


@app.route('/chat/history', methods=['GET'])
def get_history():
    try:
        user_id = request.args.get('user_id', 'anonymous')
        limit = max(1, int(request.args.get('limit', 20)))
        history = redis_service.get_conversation_history(user_id, limit=limit)
        return jsonify({"success": True, "count": len(history), "history": history})
    except Exception as e:
        logger.error(f"Lỗi lấy history: {e}")
        return jsonify({"success": False, "error": "Không thể lấy lịch sử"}), 500


@app.route('/chat/clear', methods=['POST'])
def clear_history():
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id', 'anonymous')
        redis_service.clear_conversation(user_id)
        return jsonify({"success": True, "message": "Đã xóa lịch sử trò chuyện và ngữ cảnh sản phẩm"})
    except Exception as e:
        logger.error(f"Lỗi xóa history: {e}")
        return jsonify({"success": False, "error": "Không thể xóa lịch sử"}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"API Server đang chạy tại http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)