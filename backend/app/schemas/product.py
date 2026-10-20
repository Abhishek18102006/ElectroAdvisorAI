from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ProductSpecs(BaseModel):
    cpu: Optional[str] = None
    ram_gb: Optional[int] = None
    storage_gb: Optional[int] = None
    storage_type: Optional[str] = None
    gpu: Optional[str] = None
    gpu_type: Optional[str] = None  # "dedicated", "integrated", "unified"
    vram_gb: Optional[int] = None
    display: Optional[str] = None
    weight_kg: Optional[float] = None
    battery_life_hours: Optional[float] = None
    os: Optional[str] = None
    ports: Optional[str] = None


class ProductBase(BaseModel):
    id: str
    name: str
    brand: str
    category: str
    price: float
    currency: str = "INR"
    rating: float = 4.5
    stock: int = 10
    specs: Dict[str, Any] = Field(default_factory=dict)
    intended_uses: List[str] = Field(default_factory=list)
    features: List[str] = Field(default_factory=list)
    pros: List[str] = Field(default_factory=list)
    cons: List[str] = Field(default_factory=list)
    description: str
    image_url: Optional[str] = None


class ProductResponse(ProductBase):
    pass


class ProductListResponse(BaseModel):
    total: int
    page: int
    limit: int
    pages: int
    items: List[ProductResponse]


class CategoryItem(BaseModel):
    name: str
    display_name: str
    count: int
    min_price: float
    max_price: float
    brands: List[str]


class CategoryListResponse(BaseModel):
    total_categories: int
    categories: List[CategoryItem]


class ProductCompareResponse(BaseModel):
    product_ids: List[str]
    products: List[ProductResponse]
    comparison_matrix: Dict[str, Dict[str, Any]]
    key_differences: List[str]

