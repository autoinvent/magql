import pytest

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

base = declarative_base()
Session = sessionmaker()


@pytest.fixture
def session():
    """Create and configure a new app instance for each test."""
    # create the app with common test config
    engine = create_engine('sqlite://')
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


from sqlalchemy.orm import relationship
from sqlalchemy import String, Integer, Column, ForeignKey


class Person(base):
    __tablename__ = 'Person'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    age = Column(Integer)

    house_id = Column(ForeignKey("House.id"), nullable=False)
    house = relationship("House", back_populates="inhabitants")

    car_id = Column(ForeignKey("Car.id"))
    car = relationship("Car", back_populates="drivers")


class House(base):
    __tablename__ = 'House'

    id = Column(Integer, primary_key=True)
    name = Column(String)

    inhabitants = relationship("Person", cascade="all, delete-orphan", back_populates="house")


class Car(base):
    __tablename__ = 'Car'

    id = Column(Integer, primary_key=True)
    name = Column(String)

    drivers = relationship("Person", back_populates="car")
