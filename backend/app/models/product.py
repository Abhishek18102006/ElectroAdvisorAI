from sqlalchemy import Column, String, Float, Integer, Text, JSON
from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    brand = Column(String(100), nullable=False, index=True)
    category = Column(String(100), nullable=False, index=True)
    price = Column(Float, nullable=False, index=True)
    currency = Column(String(10), default="INR")
    rating = Column(Float, default=4.5)
    stock = Column(Integer, default=15)
    
    # Structured specifications dictionary
    # {
    #   "cpu": "Intel Core i5-13500H",
    #   "ram_gb": 16,
    #   "storage_gb": 512,
    #   "storage_type": "NVMe SSD",
    #   "gpu": "NVIDIA GeForce RTX 4050 6GB",
    #   "gpu_type": "dedicated",  # dedicated | integrated | unified
    #   "vram_gb": 6,
    #   "display": "15.6 FHD 144Hz IPS",
    #   "weight_kg": 2.1,
    #   "battery_life_hours": 6.5,
    #   "os": "Windows 11 Home",
    #   "ports": "Thunderbolt 4, HDMI 2.1, USB-A x3, RJ45"
    # }
    specs = Column(JSON, nullable=False, default=dict)

    # List of suitable use cases: ["programming", "machine_learning", "gaming", "general_coursework", "creative_work"]
    intended_uses = Column(JSON, nullable=False, default=list)

    # Key highlight bullet points
    features = Column(JSON, nullable=False, default=list)

    # Strengths and trade-offs
    pros = Column(JSON, nullable=False, default=list)
    cons = Column(JSON, nullable=False, default=list)

    description = Column(Text, nullable=False)
    image_url = Column(String(500), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "brand": self.brand,
            "category": self.category,
            "price": self.price,
            "currency": self.currency,
            "rating": self.rating,
            "stock": self.stock,
            "specs": self.specs or {},
            "intended_uses": self.intended_uses or [],
            "features": self.features or [],
            "pros": self.pros or [],
            "cons": self.cons or [],
            "description": self.description,
            "image_url": self.image_url,
        }
