from sqlalchemy import Column, String, Float
from geoalchemy2 import Geometry
from app.core.database import Base

class Address(Base):
    __tablename__ = "address"
    
    landlot_address = Column(String(500), primary_key=True)
    road_name_address = Column(String(500), nullable=False)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    geom = Column(Geometry('POINT', srid=4326))