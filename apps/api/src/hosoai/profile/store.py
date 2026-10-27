from collections.abc import Iterator

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

from hosoai.profile.models import Profile, ProfileData
from hosoai.settings import Settings

_engine: Engine | None = None


def engine() -> Engine:
    global _engine
    if _engine is None:
        url = Settings().database_url
        _engine = create_engine(url, connect_args={"check_same_thread": False})
        SQLModel.metadata.create_all(_engine)
    return _engine


def get_db() -> Iterator[Session]:
    with Session(engine()) as session:
        yield session


def load_profile(db: Session) -> ProfileData:
    row = db.get(Profile, 1)
    return ProfileData.model_validate(row.model_dump(exclude={"id"})) if row else ProfileData()


def save_profile(db: Session, data: ProfileData) -> ProfileData:
    row = db.get(Profile, 1) or Profile(id=1)
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    db.add(row)
    db.commit()
    return load_profile(db)
