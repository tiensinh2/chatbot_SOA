"""
services/redis_service.py
Redis Service cho Chatbot - Hỗ trợ session, history, current_products và auto-cleanup thông minh
Phiên bản hoàn chỉnh, ổn định, không còn hàm thừa gây lỗi
"""

import redis
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from config import config

logger = logging.getLogger(__name__)


class RedisService:
    """
    Redis Service quản lý:
    - Session (với last_active, current_products, message_count)
    - Conversation history
    - Auto-cleanup dựa trên TTL và last_active
    - Thống kê cơ bản
    """
    
    def __init__(self):
        self.client = None
        self.is_connected = False
        self.last_cleanup_time = time.time()
        
        self._connect()
    
    def _connect(self):
        """Kết nối đến Redis Cloud với xử lý SSL/auth linh hoạt"""
        try:
            logger.info("Đang kết nối đến Redis...")

            connection_params = {
                'host': config.REDIS_HOST,
                'port': config.REDIS_PORT,
                'db': config.REDIS_DB,
                'decode_responses': True,
                'socket_connect_timeout': 10,
                'socket_timeout': 10,
                'retry_on_timeout': True,
            }

            # Chỉ thêm username/password/ssl nếu có trong config
            if getattr(config, 'REDIS_USERNAME', None):
                connection_params['username'] = config.REDIS_USERNAME
            if getattr(config, 'REDIS_PASSWORD', None):
                connection_params['password'] = config.REDIS_PASSWORD
            if getattr(config, 'REDIS_SSL', False):
                connection_params['ssl'] = True
                connection_params['ssl_cert_reqs'] = None

            self.client = redis.Redis(**connection_params)
            self.client.ping()  # Test kết nối
            self.is_connected = True
            logger.info("Kết nối Redis thành công!")

            # Cleanup lần đầu
            self._cleanup_old_sessions()

        except redis.AuthenticationError as e:
            logger.critical(f"Lỗi xác thực Redis: {e}")
            raise
        except redis.ConnectionError as e:
            logger.critical(f"Lỗi kết nối Redis: {e}")
            raise
        except Exception as e:
            logger.critical(f"Lỗi khởi tạo RedisService: {e}")
            raise

    # ================= AUTO CLEANUP =================
    def _cleanup_old_sessions(self) -> int:
        """Dọn dẹp session hết hạn dựa trên last_active"""
        try:
            if not self.is_connected:
                return 0

            deleted = 0
            session_keys = self.client.keys("session:*")

            for key in session_keys:
                try:
                    data = self.client.get(key)
                    if not data:
                        continue

                    session = json.loads(data)
                    if 'last_active' not in session:
                        continue

                    last_active = datetime.fromisoformat(session['last_active'].replace('Z', '+00:00'))
                    inactive_seconds = (datetime.now() - last_active).total_seconds()

                    if inactive_seconds > config.SESSION_TTL:
                        user_id = key.split(":", 1)[1]
                        self._delete_user_data(user_id)
                        deleted += 1

                except Exception as e:
                    logger.warning(f"Lỗi xử lý cleanup key {key}: {e}")

            if deleted > 0:
                logger.info(f"Auto cleanup: Đã xóa {deleted} session hết hạn")

            return deleted

        except Exception as e:
            logger.error(f"Lỗi cleanup_old_sessions: {e}")
            return 0

    def _check_and_cleanup(self):
        """Gọi định kỳ để cleanup (trong process_message)"""
        current_time = time.time()
        interval = getattr(config, 'CLEANUP_INTERVAL_MINUTES', 30) * 60
        if current_time - self.last_cleanup_time >= interval:
            self._cleanup_old_sessions()
            self.last_cleanup_time = current_time

    def _delete_user_data(self, user_id: str):
        """Xóa toàn bộ dữ liệu của user (session, history, stats)"""
        try:
            keys = [
                f"session:{user_id}",
                f"history:{user_id}",
                f"stats:messages:{user_id}"
            ]
            temp_keys = self.client.keys(f"temp:{user_id}:*")
            keys.extend(temp_keys)

            existing_keys = [k for k in keys if self.client.exists(k)]
            if existing_keys:
                self.client.delete(*existing_keys)
            logger.debug(f"Đã xóa toàn bộ dữ liệu user: {user_id}")
        except Exception as e:
            logger.warning(f"Lỗi xóa dữ liệu user {user_id}: {e}")

    # ================= SESSION MANAGEMENT =================
    def create_session(self, user_id: str) -> Dict:
        """Tạo session mới (xóa cũ nếu tồn tại)"""
        self._check_and_cleanup()

        # Xóa dữ liệu cũ
        self._delete_user_data(user_id)

        session = {
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "is_first_chat": True,
            "current_products": [],  # Danh sách _id sản phẩm đang tư vấn - QUAN TRỌNG NHẤT
            "message_count": 0
        }

        key = f"session:{user_id}"
        self.client.setex(key, config.SESSION_TTL, json.dumps(session))
        logger.info(f"Tạo session mới cho user {user_id}")
        return session

    def get_session(self, user_id: str) -> Optional[Dict]:
        """Lấy session và gia hạn TTL"""
        self._check_and_cleanup()

        if not self.is_connected:
            return None

        key = f"session:{user_id}"
        data = self.client.get(key)

        if not data:
            return None

        try:
            session = json.loads(data)

            # Kiểm tra hết hạn
            last_active = datetime.fromisoformat(session['last_active'].replace('Z', '+00:00'))
            if (datetime.now() - last_active).total_seconds() > config.SESSION_TTL:
                self._delete_user_data(user_id)
                return None

            # Gia hạn TTL
            session['last_active'] = datetime.now().isoformat()
            self.client.setex(key, config.SESSION_TTL, json.dumps(session))

            return session

        except Exception as e:
            logger.error(f"Lỗi parse session {user_id}: {e}")
            self._delete_user_data(user_id)
            return None

    def update_session(self, user_id: str, updates: Dict) -> bool:
        """Cập nhật session (current_products, is_first_chat, v.v.)"""
        try:
            session = self.get_session(user_id)
            if not session:
                return False

            session.update(updates)
            session['last_active'] = datetime.now().isoformat()

            key = f"session:{user_id}"
            self.client.setex(key, config.SESSION_TTL, json.dumps(session))
            return True
        except Exception as e:
            logger.error(f"Lỗi update session {user_id}: {e}")
            return False

    # ================= CONVERSATION HISTORY =================
    def add_message(self, user_id: str, role: str, content: str) -> bool:
        """Thêm tin nhắn vào history"""
        try:
            self._check_and_cleanup()

            key = f"history:{user_id}"
            message = {
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat()
            }

            self.client.rpush(key, json.dumps(message))
            self.client.expire(key, config.SESSION_TTL)

            # Giới hạn history 60 tin nhắn
            if self.client.llen(key) > 60:
                self.client.ltrim(key, -60, -1)

            # Cập nhật message_count trong session
            session = self.get_session(user_id)
            if session:
                session['message_count'] = session.get('message_count', 0) + 1
                self.update_session(user_id, session)

            return True
        except Exception as e:
            logger.error(f"Lỗi add_message: {e}")
            return False

    def get_conversation_history(self, user_id: str, limit: int = 12) -> List[Dict]:
        """Lấy history gần nhất (mặc định 12 tin ~ 6 lượt)"""
        try:
            self._check_and_cleanup()

            key = f"history:{user_id}"
            if not self.client.exists(key):
                return []

            raw = self.client.lrange(key, -limit, -1)
            history = []
            for item in raw:
                try:
                    history.append(json.loads(item))
                except json.JSONDecodeError:
                    continue
            return history
        except Exception as e:
            logger.error(f"Lỗi get_conversation_history: {e}")
            return []

    def clear_conversation(self, user_id: str):
        """Xóa history và reset current_products"""
        try:
            key = f"history:{user_id}"
            self.client.delete(key)

            # Reset current_products và message_count
            session = self.get_session(user_id)
            if session:
                session['current_products'] = []
                session['message_count'] = 0
                self.update_session(user_id, session)

            logger.info(f"Đã xóa history và reset ngữ cảnh cho {user_id}")
        except Exception as e:
            logger.error(f"Lỗi clear_conversation: {e}")

    # ================= THỐNG KÊ =================
    def get_redis_info(self) -> Dict[str, Any]:
        """Thông tin Redis cho thống kê"""
        try:
            if not self.is_connected:
                return {"connected": False}

            info = self.client.info()

            return {
                "connected": True,
                "memory_used": info.get("used_memory_human", "N/A"),
                "uptime_days": info.get("uptime_in_days", 0),
                "connected_clients": info.get("connected_clients", 0),
                "session_count": len(self.client.keys("session:*")),
                "history_count": len(self.client.keys("history:*")),
                "total_keys": info.get("db0", {}).get("keys", 0)
            }
        except Exception as e:
            logger.error(f"Lỗi get_redis_info: {e}")
            return {"connected": False}

    def get_all_sessions(self) -> List[Dict]:
        """Lấy tất cả session (cho debug/admin)"""
        try:
            keys = self.client.keys("session:*")
            sessions = []
            for key in keys:
                data = self.client.get(key)
                if data:
                    try:
                        sessions.append(json.loads(data))
                    except:
                        continue
            return sessions
        except Exception as e:
            logger.error(f"Lỗi get_all_sessions: {e}")
            return []

    def close(self):
        """Đóng kết nối Redis"""
        try:
            if self.client:
                self.client.close()
                logger.info("Đã đóng kết nối Redis")
        except Exception as e:
            logger.error(f"Lỗi đóng Redis: {e}")