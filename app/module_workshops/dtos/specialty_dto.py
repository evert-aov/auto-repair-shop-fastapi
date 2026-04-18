from pydantic import BaseModel, ConfigDict, Field

class SpecialtyBase(BaseModel):
    name: str = Field(..., max_length=50)

class SpecialtyCreate(SpecialtyBase):
    pass

class SpecialtyUpdate(SpecialtyBase):
    pass

class SpecialtyResponse(SpecialtyBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
