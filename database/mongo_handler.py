"""
database/mongo_handler.py
Xử lý kết nối và thao tác với MongoDB - ĐÃ FIX HOÀN TOÀN LỖI ObjectId JSON serializable
Chỉ làm việc với database 'shop' và collection 'products'
Phiên bản hoàn chỉnh, ổn định cho chatbot bán hàng
"""

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure, PyMongoError
from datetime import datetime
from typing import List, Dict, Any, Optional
from bson import ObjectId
import logging

from config import config

logger = logging.getLogger(__name__)


class MongoDBHandler:
    """
    Handler quản lý tất cả thao tác với MongoDB cho cửa hàng
    """
    
    def __init__(self, max_retries: int = 3):
        self.client = None
        self.db = None
        self.products_collection = None
        self.max_retries = max_retries
        self.is_connected = False
        
        config.validate_config()
        self._connect()
    
    def _connect(self):
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Đang kết nối MongoDB (lần {attempt + 1}/{self.max_retries})...")
                
                self.client = MongoClient(
                    config.MONGO_URI,
                    serverSelectionTimeoutMS=10000,
                    connectTimeoutMS=30000,
                    socketTimeoutMS=45000,
                    maxPoolSize=50,
                    minPoolSize=10,
                    retryWrites=True,
                    retryReads=True
                )
                
                self.client.admin.command('ping')
                
                self.db = self.client[config.DATABASE_NAME]
                self.products_collection = self.db[config.PRODUCTS_COLLECTION]
                
                self.is_connected = True
                
                product_count = self.products_collection.count_documents({})
                logger.info(f"Kết nối MongoDB thành công! Tổng sản phẩm: {product_count}")
                
                self._ensure_indexes()
                return
                
            except ConnectionFailure as e:
                logger.error(f"Lỗi kết nối MongoDB (lần {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    import time
                    time.sleep(3)
            except OperationFailure as e:
                logger.error(f"Lỗi xác thực MongoDB: {e}")
                raise
            except Exception as e:
                logger.error(f"Lỗi kết nối: {e}")
                raise
        
        raise ConnectionError("Không thể kết nối MongoDB")

    def _ensure_indexes(self):
        try:
            self.products_collection.create_index(
                [("name", "text"), ("category", "text"), ("description", "text")],
                name="product_text_search_idx",
                weights={"name": 10, "category": 5, "description": 2},
                default_language="none"
            )
            self.products_collection.create_index([("category", 1)], name="category_idx")
            self.products_collection.create_index([("price", 1)], name="price_idx")
            self.products_collection.create_index([("stock", 1)], name="stock_idx")
            logger.info("Đã tạo indexes")
        except Exception as e:
            logger.warning(f"Không thể tạo indexes: {e}")

    # ==================== HÀM CONVERT _id → string ====================
    def _convert_objectid_to_str(self, products: List[Dict]) -> List[Dict]:
        """Convert _id từ ObjectId sang string để an toàn khi jsonify"""
        for p in products:
            if '_id' in p:
                p['_id'] = str(p['_id'])
        return products

    # ==================== TÌM KIẾM & LẤY DỮ LIỆU ====================
    def search_products(
        self,
        query: str,
        limit: Optional[int] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        category: Optional[str] = None
    ) -> List[Dict]:
        try:
            if not self.is_connected:
                raise ConnectionError("MongoDB chưa kết nối")

            search_query = {}
            if query and query.strip():
                search_query["$text"] = {"$search": query.strip()}

            if min_price is not None or max_price is not None:
                price_filter = {}
                if min_price is not None:
                    price_filter["$gte"] = min_price
                if max_price is not None:
                    price_filter["$lte"] = max_price
                search_query["price"] = price_filter

            if category and category.strip():
                search_query["category"] = {"$regex": f"^{category.strip()}$", "$options": "i"}

            search_limit = limit or getattr(config, 'PRODUCT_SEARCH_LIMIT', 10)

            projection = {
                "name": 1, "price": 1, "category": 1, "short_description": 1,
                "description": 1, "image": 1, "stock": 1, "rating": 1, "url": 1
            }
            if query and query.strip():
                projection["score"] = {"$meta": "textScore"}

            cursor = self.products_collection.find(search_query, projection)

            if query and query.strip():
                cursor = cursor.sort([("score", {"$meta": "textScore"})])
            else:
                cursor = cursor.sort("name", 1)

            cursor = cursor.limit(search_limit)
            results = list(cursor)

            # FIX LỖI JSON SERIALIZABLE
            return self._convert_objectid_to_str(results)

        except Exception as e:
            logger.error(f"Lỗi search_products: {e}")
            return []

    def get_products_by_ids(self, product_ids: List[str]) -> List[Dict]:
        """Lấy sản phẩm theo list ID - QUAN TRỌNG cho ưu tiên history"""
        if not product_ids:
            return []

        try:
            valid_ids = [ObjectId(pid) for pid in product_ids if ObjectId.is_valid(pid)]
            if not valid_ids:
                return []

            cursor = self.products_collection.find(
                {"_id": {"$in": valid_ids}},
                {
                    "name": 1, "price": 1, "category": 1, "short_description": 1,
                    "description": 1, "image": 1, "stock": 1, "rating": 1, "url": 1
                }
            )
            results = list(cursor)

            # Giữ nguyên thứ tự theo product_ids
            id_map = {str(p["_id"]): p for p in results}
            ordered = [id_map[pid] for pid in product_ids if pid in id_map]

            # FIX JSON SERIALIZABLE
            return self._convert_objectid_to_str(ordered)

        except Exception as e:
            logger.error(f"Lỗi get_products_by_ids: {e}")
            return []

    def get_product_by_id(self, product_id: str) -> Optional[Dict]:
        try:
            if not ObjectId.is_valid(product_id):
                return None

            product = self.products_collection.find_one({"_id": ObjectId(product_id)})
            if product:
                product["_id"] = str(product["_id"])
                return product
            return None
        except Exception as e:
            logger.error(f"Lỗi get_product_by_id: {e}")
            return None

    def get_categories(self) -> List[str]:
        try:
            cats = self.products_collection.distinct("category")
            return sorted([c for c in cats if c and c.strip()])
        except Exception as e:
            logger.error(f"Lỗi get_categories: {e}")
            return []

    def get_random_products(self, count: int = 5) -> List[Dict]:
        try:
            pipeline = [{"$sample": {"size": count}}]
            results = list(self.products_collection.aggregate(pipeline))
            return self._convert_objectid_to_str(results)
        except Exception as e:
            logger.error(f"Lỗi get_random_products: {e}")
            return []

    def get_products_stats(self) -> Dict[str, Any]:
        try:
            total = self.products_collection.count_documents({})
            in_stock = self.products_collection.count_documents({"stock": {"$gt": 0}})
            out_of_stock = total - in_stock
            categories = len(self.get_categories())

            return {
                "total_products": total,
                "in_stock": in_stock,
                "out_of_stock": out_of_stock,
                "categories_count": categories
            }
        except Exception as e:
            logger.error(f"Lỗi get_products_stats: {e}")
            return {}

    # ==================== UTILITY ====================
    def test_connection(self) -> bool:
        try:
            self.client.admin.command('ping')
            return True
        except:
            return False

    def close(self):
        if self.client:
            self.client.close()
            self.is_connected = False
            logger.info("Đã đóng kết nối MongoDB")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()