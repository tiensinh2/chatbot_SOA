"""
Xử lý kết nối và thao tác với MongoDB
Chỉ làm việc với database 'shop' và collection 'products'
"""

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure, PyMongoError
from datetime import datetime
from typing import List, Dict, Any, Optional
from bson import ObjectId
import logging

from config import config

# Thiết lập logging
logger = logging.getLogger(__name__)

class MongoDBHandler:
    """
    Handler quản lý tất cả thao tác với MongoDB
    
    Chỉ làm việc với:
    - Database: 'shop'
    - Collection: 'products'
    """
    
    def __init__(self, max_retries: int = 3):
        """
        Khởi tạo kết nối MongoDB
        
        Args:
            max_retries: Số lần thử kết nối lại khi thất bại
        """
        self.client = None
        self.db = None
        self.products_collection = None
        self.max_retries = max_retries
        self.is_connected = False
        
        # Validate cấu hình trước khi kết nối
        config.validate_config()
        
        # Thiết lập kết nối
        self._connect()
    
    def _connect(self):
        """Thiết lập kết nối đến MongoDB Atlas với retry logic"""
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Đang kết nối MongoDB (lần {attempt + 1}/{self.max_retries})...")
                
                # Tạo client với các tùy chọn kết nối
                self.client = MongoClient(
                    config.MONGO_URI,
                    serverSelectionTimeoutMS=10000,  # 10 giây timeout
                    connectTimeoutMS=30000,          # 30 giây connect timeout
                    socketTimeoutMS=45000,           # 45 giây socket timeout
                    maxPoolSize=50,                  # Kích thước connection pool
                    minPoolSize=10,
                    retryWrites=True,
                    retryReads=True
                )
                
                # Test kết nối
                self.client.admin.command('ping')
                
                # Chọn database 'shop'
                self.db = self.client[config.DATABASE_NAME]
                
                # Chọn collection 'products'
                self.products_collection = self.db[config.PRODUCTS_COLLECTION]
                
                # Kiểm tra collection có tồn tại không
                collections = self.db.list_collection_names()
                if config.PRODUCTS_COLLECTION not in collections:
                    logger.warning(f"Collection '{config.PRODUCTS_COLLECTION}' chưa tồn tại")
                
                self.is_connected = True
                
                # Lấy thông tin thống kê
                product_count = self.products_collection.count_documents({})
                
                logger.info(f"✅ Kết nối MongoDB thành công!")
                logger.info(f"   Database: {config.DATABASE_NAME}")
                logger.info(f"   Collection: {config.PRODUCTS_COLLECTION}")
                logger.info(f"   Tổng sản phẩm: {product_count}")
                
                # Tạo index nếu cần
                self._ensure_indexes()
                
                return
                
            except ConnectionFailure as e:
                logger.error(f"❌ Lỗi kết nối MongoDB (lần {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    import time
                    time.sleep(2)  # Chờ 2 giây trước khi thử lại
                else:
                    logger.critical("❌ Không thể kết nối MongoDB sau nhiều lần thử")
                    raise
                    
            except OperationFailure as e:
                logger.error(f"❌ Lỗi xác thực MongoDB: {e}")
                logger.error("   💡 Kiểm tra username/password và IP whitelist trong MongoDB Atlas")
                raise
                
            except Exception as e:
                logger.error(f"❌ Lỗi không mong đợi: {e}")
                raise
    
    def _ensure_indexes(self):
        """Tạo các index cần thiết cho hiệu suất tìm kiếm"""
        try:
            # Text index cho tìm kiếm full-text
            self.products_collection.create_index(
                [("name", "text"), ("description", "text"), ("category", "text")],
                name="product_search_idx",
                default_language="none",
                weights={
                    "name": 10,
                    "category": 5,
                    "description": 3
                }
            )
            
            # Index cho category để filter nhanh
            self.products_collection.create_index(
                [("category", 1)],
                name="category_idx"
            )
            
            # Index cho price để sorting nhanh
            self.products_collection.create_index(
                [("price", 1)],
                name="price_idx"
            )
            
            logger.info("✅ Đã tạo indexes cho collection products")
            
        except Exception as e:
            logger.warning(f"⚠️ Không thể tạo indexes: {e}")
            # Tiếp tục chạy ngay cả khi tạo index thất bại
    
    # ==================== PRODUCT METHODS ====================
    
    def search_products(self, query: str, limit: int = None, 
                       min_price: float = None, max_price: float = None,
                       category: str = None) -> List[Dict]:
        """
        Tìm kiếm sản phẩm với nhiều tùy chọn
        
        Args:
            query: Từ khóa tìm kiếm
            limit: Số kết quả tối đa
            min_price: Giá tối thiểu
            max_price: Giá tối đa
            category: Danh mục sản phẩm
        
        Returns:
            Danh sách sản phẩm phù hợp
        """
        try:
            if not self.is_connected:
                raise ConnectionError("MongoDB chưa được kết nối")
            
            # Xây dựng query
            search_query = {}
            
            # Thêm text search nếu có query
            if query and query.strip():
                search_query["$text"] = {"$search": query}
            
            # Thêm filter theo price range
            price_filter = {}
            if min_price is not None:
                price_filter["$gte"] = min_price
            if max_price is not None:
                price_filter["$lte"] = max_price
            
            if price_filter:
                search_query["price"] = price_filter
            
            # Thêm filter theo category
            if category and category.strip():
                search_query["category"] = {"$regex": f"^{category}$", "$options": "i"}
            
            # Thiết lập limit mặc định
            search_limit = limit or config.PRODUCT_SEARCH_LIMIT
            
            # Thực hiện tìm kiếm
            cursor = self.products_collection.find(
                search_query,
                {
                    "name": 1,
                    "price": 1,
                    "category": 1,
                    "description": 1,
                    "image": 1,
                    "stock": 1,
                    "rating": 1,
                    "score": {"$meta": "textScore"} if query else None
                }
            )
            
            # Sắp xếp kết quả
            if query and query.strip():
                cursor = cursor.sort([("score", {"$meta": "textScore"})])
            else:
                cursor = cursor.sort("name", 1)
            
            # Giới hạn kết quả
            cursor = cursor.limit(search_limit)
            
            # Convert kết quả sang list và format
            results = list(cursor)
            
            # Convert ObjectId thành string
            for product in results:
                product["_id"] = str(product["_id"])
            
            logger.info(f"🔍 Tìm thấy {len(results)} sản phẩm với query: '{query}'")
            
            return results
            
        except PyMongoError as e:
            logger.error(f"❌ Lỗi khi tìm kiếm sản phẩm: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Lỗi không mong đợi khi tìm kiếm: {e}")
            return []
    
    def get_all_products(self, page: int = 1, per_page: int = 20, 
                        sort_by: str = "name", sort_order: int = 1) -> Dict:
        """
        Lấy tất cả sản phẩm với phân trang
        
        Args:
            page: Trang hiện tại
            per_page: Số sản phẩm mỗi trang
            sort_by: Trường sắp xếp
            sort_order: 1 (tăng dần) hoặc -1 (giảm dần)
        
        Returns:
            Dictionary chứa sản phẩm và thông tin phân trang
        """
        try:
            # Tính toán skip
            skip = (page - 1) * per_page
            
            # Lấy tổng số sản phẩm
            total_products = self.products_collection.count_documents({})
            
            # Lấy sản phẩm với phân trang
            cursor = self.products_collection.find(
                {},
                {
                    "name": 1,
                    "price": 1,
                    "category": 1,
                    "description": 1,
                    "image": 1,
                    "stock": 1,
                    "rating": 1
                }
            ).sort(sort_by, sort_order).skip(skip).limit(per_page)
            
            products = list(cursor)
            
            # Convert ObjectId
            for product in products:
                product["_id"] = str(product["_id"])
            
            return {
                "products": products,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total_pages": (total_products + per_page - 1) // per_page,
                    "total_products": total_products,
                    "has_next": skip + per_page < total_products,
                    "has_previous": page > 1
                }
            }
            
        except PyMongoError as e:
            logger.error(f"❌ Lỗi khi lấy sản phẩm: {e}")
            return {"products": [], "pagination": {}}
    
    def get_product_by_id(self, product_id: str) -> Optional[Dict]:
        """
        Lấy thông tin chi tiết sản phẩm theo ID
        
        Args:
            product_id: ID của sản phẩm
        
        Returns:
            Thông tin sản phẩm hoặc None
        """
        try:
            if not ObjectId.is_valid(product_id):
                logger.warning(f"⚠️ Product ID không hợp lệ: {product_id}")
                return None
            
            product = self.products_collection.find_one(
                {"_id": ObjectId(product_id)},
                {
                    "_id": 0,  # Ẩn ObjectId
                    "name": 1,
                    "price": 1,
                    "category": 1,
                    "description": 1,
                    "image": 1,
                    "stock": 1,
                    "rating": 1,
                    "specifications": 1,
                    "created_at": 1,
                    "updated_at": 1
                }
            )
            
            if product:
                # Convert ObjectId thành string
                product["id"] = product_id
                logger.info(f"✅ Đã tìm thấy sản phẩm: {product.get('name')}")
                return product
            else:
                logger.warning(f"⚠️ Không tìm thấy sản phẩm với ID: {product_id}")
                return None
                
        except PyMongoError as e:
            logger.error(f"❌ Lỗi khi lấy sản phẩm theo ID: {e}")
            return None
    
    def get_categories(self) -> List[str]:
        """
        Lấy danh sách tất cả categories
        
        Returns:
            Danh sách categories
        """
        try:
            categories = self.products_collection.distinct("category")
            # Lọc bỏ None/empty và sắp xếp
            categories = sorted([cat for cat in categories if cat])
            logger.info(f"📁 Tìm thấy {len(categories)} categories")
            return categories
        except PyMongoError as e:
            logger.error(f"❌ Lỗi khi lấy categories: {e}")
            return []
    
    def get_products_by_category(self, category: str, limit: int = 10) -> List[Dict]:
        """
        Lấy sản phẩm theo category
        
        Args:
            category: Tên category
            limit: Số sản phẩm tối đa
        
        Returns:
            Danh sách sản phẩm
        """
        try:
            products = list(self.products_collection.find(
                {"category": {"$regex": f"^{category}$", "$options": "i"}},
                {
                    "name": 1,
                    "price": 1,
                    "description": 1,
                    "image": 1
                }
            ).limit(limit))
            
            for product in products:
                product["_id"] = str(product["_id"])
            
            logger.info(f"✅ Đã lấy {len(products)} sản phẩm từ category '{category}'")
            return products
            
        except PyMongoError as e:
            logger.error(f"❌ Lỗi khi lấy sản phẩm theo category: {e}")
            return []
    
    def get_products_stats(self) -> Dict[str, Any]:
        """
        Lấy thống kê về sản phẩm
        
        Returns:
            Dictionary chứa các thống kê
        """
        try:
            pipeline = [
                {
                    "$group": {
                        "_id": "$category",
                        "count": {"$sum": 1},
                        "avg_price": {"$avg": "$price"},
                        "min_price": {"$min": "$price"},
                        "max_price": {"$max": "$price"},
                        "total_stock": {"$sum": "$stock"}
                    }
                },
                {"$sort": {"count": -1}}
            ]
            
            category_stats = list(self.products_collection.aggregate(pipeline))
            
            # Thống kê tổng quan
            total_products = self.products_collection.count_documents({})
            out_of_stock = self.products_collection.count_documents({"stock": 0})
            
            stats = {
                "total_products": total_products,
                "out_of_stock": out_of_stock,
                "in_stock": total_products - out_of_stock,
                "categories_count": len(category_stats),
                "category_stats": category_stats
            }
            
            logger.info(f"📊 Thống kê: {total_products} sản phẩm, {len(category_stats)} categories")
            return stats
            
        except PyMongoError as e:
            logger.error(f"❌ Lỗi khi lấy thống kê: {e}")
            return {}
    
    # ==================== UTILITY METHODS ====================
    
    def test_connection(self) -> bool:
        """Kiểm tra kết nối MongoDB"""
        try:
            self.client.admin.command('ping')
            return True
        except:
            return False
    
    def close(self):
        """Đóng kết nối MongoDB"""
        if self.client:
            self.client.close()
            self.is_connected = False
            logger.info("📭 Đã đóng kết nối MongoDB")
    
    def __enter__(self):
        """Context manager enter"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
    
    def __del__(self):
        """Destructor"""
        self.close()