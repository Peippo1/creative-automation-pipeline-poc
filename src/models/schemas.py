from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict

class Product(BaseModel):
    sku: str
    name: str

class Requirements(BaseModel):
    aspect_ratios: List[Literal["1:1","9:16","16:9"]]

class Brand(BaseModel):
    primary_colour: str
    logo_path: str

class CampaignBrief(BaseModel):
    campaign_id: str
    campaign_name: str
    products: List[Product]
    target_market: str
    audience: str
    message: str
    languages: List[str] = Field(default=["en-GB"])
    requirements: Requirements
    brand: Brand
