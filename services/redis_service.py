"""
Redis Service for Chatbot với Auto-Cleanup
"""

import redis
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from config import config

logger = logging.getLogger(__name__)

class RedisService:
    """Service để tương tác với Redis Cloud và tự động dọn dẹp"""
    
    def __init__(self):
        self.client = None
        self.is_connected = False
        self.last_cleanup_time = 0
        self._connect()
    
    def _connect(self):
        """Kết nối đến Redis Cloud"""
        try:
            logger.info(f"🔄 Đang kết nối đến Redis Cloud: {config.REDIS_HOST}:{config.REDIS_PORT}")
            
            connection_params = {
                'host': config.REDIS_HOST,
                'port': config.REDIS_PORT,
                'db': config.REDIS_DB,
                'decode_responses': True,
                'socket_timeout': 5,
                'socket_connect_timeout': 5,
            }
            
            if config.REDIS_USERNAME:
                connection_params['username'] = config.REDIS_USERNAME
            if config.REDIS_PASSWORD:
                connection_params['password'] = config.REDIS_PASSWORD
            
            if config.REDIS_SSL:
                connection_params['ssl'] = True
                connection_params['ssl_cert_reqs'] = None
            
            self.client = redis.Redis(**connection_params)
            
            if self.client.ping():
                self.is_connected = True
                logger.info("✅ Đã kết nối thành công đến Redis Cloud")
                self._run_initial_cleanup()
            else:
                logger.error("❌ Không thể kết nối đến Redis Cloud")
                
        except redis.exceptions.AuthenticationError as e:
            logger.error(f"❌ Lỗi xác thực Redis: {e}")
        except redis.exceptions.ConnectionError as e:
            logger.error(f"❌ Lỗi kết nối Redis: {e}")
        except Exception as e:
            logger.error(f"❌ Lỗi khởi tạo Redis: {e}")
    
    def _run_initial_cleanup(self):
        """Chạy cleanup lần đầu khi khởi động"""
        try:
            logger.info("🧹 Đang dọn dẹp session cũ...")
            cleaned = self._cleanup_old_sessions()
            logger.info(f"✅ Đã dọn dẹp {cleaned} session cũ")
        except Exception as e:
            logger.error(f"❌ Lỗi khi chạy initial cleanup: {e}")
    
    def _check_and_cleanup(self):
        """Kiểm tra và chạy cleanup nếu đến thời gian"""
        current_time = time.time()
        cleanup_interval = config.CLEANUP_INTERVAL_MINUTES * 60  # Convert to seconds
        
        if current_time - self.last_cleanup_time >= cleanup_interval:
            try:
                cleaned = self._cleanup_old_sessions()
                if cleaned > 0:
                    logger.info(f"🧹 Tự động dọn dẹp: Đã xóa {cleaned} session cũ")
                self.last_cleanup_time = current_time
            except Exception as e:
                logger.error(f"❌ Lỗi khi chạy auto-cleanup: {e}")
    
    def _cleanup_old_sessions(self) -> int:
        """Dọn dẹp session cũ và dữ liệu liên quan"""
        try:
            if not self.is_connected:
                return 0
            
            deleted_count = 0
            
            # Lấy tất cả session keys
            session_keys = self.client.keys("session:*")
            
            for session_key in session_keys:
                try:
                    # Lấy session data
                    session_data = self.client.get(session_key)
                    if not session_data:
                        continue
                    
                    session = json.loads(session_data)
                    
                    # Kiểm tra thời gian không hoạt động
                    if 'last_active' in session:
                        last_active = datetime.fromisoformat(session['last_active'])
                        time_diff = datetime.now() - last_active
                        
                        # Nếu không hoạt động quá SESSION_TIMEOUT_HOURS
                        if time_diff.total_seconds() > config.SESSION_TTL:
                            # Xóa session
                            self.client.delete(session_key)
                            deleted_count += 1
                            
                            # Xóa conversation history liên quan
                            user_id = session_key.split(":")[1]
                            history_key = f"history:{user_id}"
                            self.client.delete(history_key)
                            
                            # Xóa stats liên quan
                            stats_key = f"stats:messages:{user_id}"
                            self.client.delete(stats_key)
                            
                except Exception as e:
                    logger.warning(f"⚠️ Lỗi khi xử lý session {session_key}: {e}")
                    continue
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"❌ Lỗi cleanup_old_sessions: {e}")
            return 0
    
    # ================ SESSION MANAGEMENT ================
    
    def get_session(self, user_id: str) -> Optional[Dict]:
        """Lấy session của user và tự động cleanup"""
        try:
            self._check_and_cleanup()
            
            if not self.is_connected:
                return None
                
            key = f"session:{user_id}"
            data = self.client.get(key)
            
            if data:
                session = json.loads(data)
                
                # Kiểm tra nếu session đã hết hạn
                if 'last_active' in session:
                    last_active = datetime.fromisoformat(session['last_active'])
                    time_diff = datetime.now() - last_active
                    
                    if time_diff.total_seconds() > config.SESSION_TTL:
                        # Session đã hết hạn, xóa tất cả dữ liệu
                        self._delete_user_data(user_id)
                        return None
                
                # Cập nhật last_active và gia hạn TTL
                session['last_active'] = datetime.now().isoformat()
                self.client.setex(key, config.SESSION_TTL, json.dumps(session))
                return session
                
        except Exception as e:
            logger.error(f"❌ Lỗi get session: {e}")
        return None
    
    def _delete_user_data(self, user_id: str):
        """Xóa tất cả dữ liệu của user"""
        try:
            # Xóa session
            session_key = f"session:{user_id}"
            
            # Xóa history
            history_key = f"history:{user_id}"
            
            # Xóa stats
            stats_key = f"stats:messages:{user_id}"
            
            # Xóa tất cả keys
            keys = [session_key, history_key, stats_key]
            
            # Thêm các temp keys nếu có
            temp_pattern = f"temp:{user_id}:*"
            temp_keys = self.client.keys(temp_pattern)
            keys.extend(temp_keys)
            
            # Xóa tất cả keys
            if keys:
                self.client.delete(*keys)
                
            logger.debug(f"🧹 Đã xóa dữ liệu user: {user_id}")
                    
        except Exception as e:
            logger.error(f"❌ Lỗi delete user data: {e}")
    
    def create_session(self, user_id: str, session_data: Dict = None) -> Dict:
        """Tạo session mới cho user"""
        try:
            self._check_and_cleanup()
            
            if not self.is_connected:
                return self._create_fallback_session(user_id)
                
            # Kiểm tra nếu user đã có session cũ, xóa trước khi tạo mới
            self._delete_user_data(user_id)
            
            key = f"session:{user_id}"
            session = session_data or {
                'user_id': user_id,
                'created_at': datetime.now().isoformat(),
                'last_active': datetime.now().isoformat(),
                'message_count': 0,
                'is_first_chat': True,
                'expires_at': (datetime.now() + timedelta(seconds=config.SESSION_TTL)).isoformat()
            }
            
            self.client.setex(key, config.SESSION_TTL, json.dumps(session))
            logger.debug(f"✅ Đã tạo session: {user_id} (TTL: {config.SESSION_TTL}s)")
            return session
            
        except Exception as e:
            logger.error(f"❌ Lỗi create session: {e}")
            return self._create_fallback_session(user_id)
    
    def _create_fallback_session(self, user_id: str) -> Dict:
        """Tạo session fallback khi không có Redis"""
        return {
            'user_id': user_id,
            'created_at': datetime.now().isoformat(),
            'last_active': datetime.now().isoformat(),
            'message_count': 0,
            'is_first_chat': True,
            'is_fallback': True
        }
    
    def update_session(self, user_id: str, updates: Dict) -> bool:
        """Cập nhật session và gia hạn TTL"""
        try:
            self._check_and_cleanup()
            
            if not self.is_connected:
                return False
                
            key = f"session:{user_id}"
            session = self.get_session(user_id)
            if not session:
                session = self.create_session(user_id)
            
            session.update(updates)
            session['last_active'] = datetime.now().isoformat()
            session['expires_at'] = (datetime.now() + timedelta(seconds=config.SESSION_TTL)).isoformat()
            
            self.client.setex(key, config.SESSION_TTL, json.dumps(session))
            return True
            
        except Exception as e:
            logger.error(f"❌ Lỗi update session: {e}")
            return False
    
    def delete_session(self, user_id: str) -> bool:
        """Xóa session của user"""
        try:
            if not self.is_connected:
                return False
                
            self._delete_user_data(user_id)
            return True
            
        except Exception as e:
            logger.error(f"❌ Lỗi delete session: {e}")
            return False
    
    # ================ CONVERSATION HISTORY ================
    
    def add_message(self, user_id: str, role: str, content: str) -> bool:
        """Thêm message vào lịch sử conversation"""
        try:
            self._check_and_cleanup()
            
            if not self.is_connected:
                return False
                
            key = f"history:{user_id}"
            message = {
                'role': role,
                'content': content,
                'timestamp': datetime.now().isoformat(),
                'expires_in': config.SESSION_TTL
            }
            
            self.client.rpush(key, json.dumps(message))
            
            # Set TTL cho history (cùng với session)
            self.client.expire(key, config.SESSION_TTL)
            return True
            
        except Exception as e:
            logger.error(f"❌ Lỗi add message: {e}")
            return False
    
    def get_conversation_history(self, user_id: str, limit: int = None) -> List[Dict]:
        """Lấy lịch sử conversation"""
        try:
            self._check_and_cleanup()
            
            if not self.is_connected:
                return []
                
            key = f"history:{user_id}"
            
            # Kiểm tra nếu session còn tồn tại
            session_key = f"session:{user_id}"
            if not self.client.exists(session_key):
                # Session đã hết hạn, xóa history
                self.client.delete(key)
                return []
            
            if not limit:
                limit = config.MAX_CHAT_HISTORY
            
            total = self.client.llen(key)
            start = max(0, total - limit)
            messages = self.client.lrange(key, start, -1)
            
            result = []
            for msg in messages:
                try:
                    result.append(json.loads(msg))
                except:
                    continue
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Lỗi get conversation history: {e}")
            return []
    
    def clear_conversation(self, user_id: str) -> bool:
        """Xóa conversation history"""
        try:
            if not self.is_connected:
                return False
                
            key = f"history:{user_id}"
            return self.client.delete(key) > 0
            
        except Exception as e:
            logger.error(f"❌ Lỗi clear conversation: {e}")
            return False
    
    # ================ PRODUCT CACHE ================
    
    def cache_product_search(self, query: str, products: List[Dict]) -> bool:
        """Cache kết quả tìm kiếm sản phẩm"""
        try:
            if not self.is_connected:
                return False
                
            key = f"search:{query.lower().replace(' ', '_')}"
            self.client.setex(key, config.REDIS_SEARCH_TTL, json.dumps(products))
            return True
            
        except Exception as e:
            logger.error(f"❌ Lỗi cache product search: {e}")
            return False
    
    def get_cached_search(self, query: str) -> Optional[List[Dict]]:
        """Lấy kết quả tìm kiếm từ cache"""
        try:
            if not self.is_connected:
                return None
                
            key = f"search:{query.lower().replace(' ', '_')}"
            data = self.client.get(key)
            if data:
                return json.loads(data)
                
        except Exception as e:
            logger.error(f"❌ Lỗi get cached search: {e}")
        return None
    
    def cache_products_by_category(self, category: str, products: List[Dict]) -> bool:
        """Cache sản phẩm theo category"""
        try:
            if not self.is_connected:
                return False
                
            key = f"category:{category.lower()}"
            self.client.setex(key, config.REDIS_CATEGORY_TTL, json.dumps(products))
            return True
            
        except Exception as e:
            logger.error(f"❌ Lỗi cache products by category: {e}")
            return False
    
    def get_cached_category_products(self, category: str) -> Optional[List[Dict]]:
        """Lấy sản phẩm theo category từ cache"""
        try:
            if not self.is_connected:
                return None
                
            key = f"category:{category.lower()}"
            data = self.client.get(key)
            if data:
                return json.loads(data)
                
        except Exception as e:
            logger.error(f"❌ Lỗi get cached category products: {e}")
        return None
    
    # ================ STATISTICS ================
    
    def increment_message_count(self, user_id: str) -> bool:
        """Tăng số lượng message của user"""
        try:
            self._check_and_cleanup()
            
            if not self.is_connected:
                return False
                
            key = f"stats:messages:{user_id}"
            self.client.incr(key)
            self.client.expire(key, config.SESSION_TTL)
            return True
            
        except Exception as e:
            logger.error(f"❌ Lỗi increment message count: {e}")
            return False
    
    def get_user_message_count(self, user_id: str) -> int:
        """Lấy số lượng message của user"""
        try:
            if not self.is_connected:
                return 0
                
            key = f"stats:messages:{user_id}"
            count = self.client.get(key)
            return int(count) if count else 0
            
        except Exception as e:
            logger.error(f"❌ Lỗi get user message count: {e}")
            return 0
    
    # ================ SYSTEM STATS ================
    
    def get_redis_info(self) -> Dict:
        """Lấy thông tin Redis"""
        try:
            if not self.is_connected:
                return {'connected': False}
                
            info = self.client.info()
            
            # Đếm các loại keys
            session_keys = len(self.client.keys("session:*"))
            history_keys = len(self.client.keys("history:*"))
            search_keys = len(self.client.keys("search:*"))
            stats_keys = len(self.client.keys("stats:*"))
            category_keys = len(self.client.keys("category:*"))
            
            return {
                'connected': True,
                'version': info.get('redis_version'),
                'memory_used': info.get('used_memory_human'),
                'connected_clients': info.get('connected_clients'),
                'total_keys': info.get('db0', {}).get('keys', 0),
                'session_keys': session_keys,
                'history_keys': history_keys,
                'search_keys': search_keys,
                'category_keys': category_keys,
                'stats_keys': stats_keys,
                'uptime_days': info.get('uptime_in_days', 0)
            }
            
        except Exception as e:
            logger.error(f"❌ Lỗi get redis info: {e}")
            return {'connected': False}
    
    def cleanup_all_expired(self) -> Dict:
        """Dọn dẹp tất cả dữ liệu hết hạn"""
        try:
            if not self.is_connected:
                return {'cleaned': 0}
            
            # Chạy cleanup old sessions
            sessions_cleaned = self._cleanup_old_sessions()
            
            # Get key counts before and after
            total_keys_before = len(self.client.keys("*"))
            
            # Try memory purge if available
            try:
                self.client.memory_purge()
            except:
                pass
            
            total_keys_after = len(self.client.keys("*"))
            
            return {
                'sessions_cleaned': sessions_cleaned,
                'total_keys_before': total_keys_before,
                'total_keys_after': total_keys_after,
                'keys_freed': total_keys_before - total_keys_after
            }
            
        except Exception as e:
            logger.error(f"❌ Lỗi cleanup_all_expired: {e}")
            return {'cleaned': 0}
    
    def get_all_sessions(self) -> List[Dict]:
        """Lấy tất cả sessions (cho admin/debug)"""
        try:
            if not self.is_connected:
                return []
            
            sessions = []
            session_keys = self.client.keys("session:*")
            
            for key in session_keys:
                try:
                    data = self.client.get(key)
                    if data:
                        session = json.loads(data)
                        session['key'] = key
                        sessions.append(session)
                except:
                    continue
            
            return sessions
            
        except Exception as e:
            logger.error(f"❌ Lỗi get all sessions: {e}")
            return []
    
    def close(self):
        """Đóng kết nối Redis"""
        try:
            if self.client:
                self.client.close()
                logger.info("✅ Đã đóng kết nối Redis")
        except Exception as e:
            logger.error(f"❌ Lỗi khi đóng Redis: {e}")