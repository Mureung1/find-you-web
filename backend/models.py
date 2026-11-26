from datetime import date, datetime, timedelta, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


class Category(StrEnum):
    ELECTRONICS = "electronics"
    WALLET = "wallet"
    CARD = "card"
    ACCESSORY = "accessory"
    CLOTHING = "clothing"
    BAG = "bag"
    OTHER = "other"


CATEGORY_LABELS = {
    Category.ELECTRONICS: "전자기기",
    Category.WALLET: "지갑",
    Category.CARD: "카드·신분증",
    Category.ACCESSORY: "생활용품",
    Category.CLOTHING: "의류·잡화",
    Category.BAG: "가방",
    Category.OTHER: "기타",
}

LocationID = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
Features = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=500)]


class Location(BaseModel):
    location_id: str
    region: str
    dong: str


class Coordinates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: Annotated[float, Field(strict=True, ge=-90, le=90)]
    longitude: Annotated[float, Field(strict=True, ge=-180, le=180)]


class CandidateQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: LocationID
    category: Category
    features: Features


class CandidateResult(BaseModel):
    has_candidate: bool


class Registration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: LocationID
    category: Category
    title: Title
    event_date: date

    @field_validator("event_date")
    @classmethod
    def validate_event_date(cls, event_date: date) -> date:
        today = datetime.now(timezone(timedelta(hours=9))).date()
        if event_date > today:
            raise ValueError("날짜는 오늘 또는 이전이어야 합니다.")
        return event_date


class LostRegistration(Registration):
    consent_to_publish: bool = False


class FoundRegistration(Registration):
    features: Features


class RegistrationResult(BaseModel):
    item_id: str


class PublicLostItem(BaseModel):
    item_id: str
    title: str
    category: Category
    location: Location
    event_date: date
    status: Literal["searching", "returned"]
