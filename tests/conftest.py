import pytest
from sqlalchemy import Column
from sqlalchemy import create_engine
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker

from magql.manager import MagqlTableManagerCollection

base = declarative_base()
Session = sessionmaker()


@pytest.fixture
def session():
    """Create and configure a new app instance for each test."""
    # create the app with common test config
    engine = create_engine("sqlite://")
    base.metadata.create_all(engine)
    Session.configure(bind=engine)
    session = Session()

    car = Car(name="Car 1")
    house = House(name="House 1")
    person = Person(name="Person 1", car=car, house=house)
    session.add(car)
    session.add(house)
    session.add(person)
    session.commit()
    return session


@pytest.fixture
def manager_collection():
    table = {}
    for table_name, _table in base.metadata.tables.items():
        table[table_name] = _table
    return MagqlTableManagerCollection(table)


class Person(base):
    __tablename__ = "Person"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    age = Column(Integer)

    house_id = Column(ForeignKey("House.id"), nullable=False)
    house = relationship("House", back_populates="inhabitants")

    car_id = Column(ForeignKey("Car.id"))
    car = relationship("Car", back_populates="drivers")


class House(base):
    __tablename__ = "House"

    id = Column(Integer, primary_key=True)
    name = Column(String)

    inhabitants = relationship(
        "Person", cascade="all, delete-orphan", back_populates="house"
    )


class Car(base):
    __tablename__ = "Car"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    mpg = Column(Float)
    top_speed = Column(Numeric)

    drivers = relationship("Person", back_populates="car")
