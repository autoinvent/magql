from datetime import date

import pytest
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import create_engine
from sqlalchemy import Date
from sqlalchemy import Enum
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
    hometown = Hometown(id="San Diego", country="United States")
    status = Status(id=True, date_of_birth=date.today())
    wealth = Wealth(id=1.5, currency="USD", abbreviation="M")
    person = Person(
        name="Person 1",
        car=car,
        house=house,
        hometown=hometown,
        status=status,
        wealth=wealth,
    )
    session.add(car)
    session.add(house)
    session.add(person)
    session.commit()
    return session


@pytest.fixture
def manager_collection():
    table = {}
    for table_name, _table in base.metadata.tables.items():
        if table_name == "BadClass" or table_name == "BadRelClass":
            continue
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

    hometown_id = Column(ForeignKey("Hometown.id"))
    hometown = relationship("Hometown", back_populates="notable_people")

    status_id = Column(ForeignKey("Status.id"))
    status = relationship("Status", back_populates="person")

    wealth_id = Column(ForeignKey("Wealth.id"))
    wealth = relationship("Wealth", back_populates="person_of_note")


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


class Hometown(base):
    __tablename__ = "Hometown"

    id = Column(String, primary_key=True, unique=True, nullable=False)
    country = Column(String)

    notable_people = relationship(
        "Person", cascade="all, delete-orphan", back_populates="hometown"
    )


class Status(base):
    __tablename__ = "Status"

    id = Column(Boolean, primary_key=True, nullable=False)
    date_of_birth = Column(Date, nullable=False)
    date_of_death = Column(Date, nullable=True)

    person = relationship(
        "Person", cascade="all, delete-orphan", back_populates="status"
    )


class Wealth(base):
    __tablename__ = "Wealth"

    id = Column(Float, primary_key=True, nullable=False)
    currency = Column(Enum("USD", "EUR", "GBP", name="denomination"), nullable=False)
    abbreviation = Column(Enum("M", "K", "B", "T", name="money_abbreviation"))

    person_of_note = relationship(
        "Person", cascade="all, delete-orphan", back_populates="wealth"
    )


class BadClass(base):
    """Test class for bad relationship keys"""

    __tablename__ = "BadClass"

    id = Column(Date, primary_key=True, nullable=False)

    bad_rel = relationship(
        "BadRelClass", cascade="all, delete-orphan", back_populates="bad_class"
    )


class BadRelClass(base):
    """Relationship class for bad relationship key"""

    __tablename__ = "BadRelClass"

    id = Column(String, primary_key=True, nullable=False)

    bad_class_id = Column(ForeignKey("BadClass.id"))
    bad_class = relationship("BadClass", back_populates="bad_rel")
