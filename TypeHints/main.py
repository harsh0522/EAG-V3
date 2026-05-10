#from  typing import Optional, NewType, TypedDict
# name: str = "harsh"
# age: int = 30

#-> dict means we want dictnory of returned value
# we can use this "age: int | None = None"
# or we vcan call a library typing that has a module called Optional and write it like 
#this "age: Optional[int] = None"
#dict[str, str] def will return a dictionary with key as string and value as string
#dict[str, str | int | None] this means def will return dictionary with key as string and 
# value as string or integer or None
# now as you can see it will be complex to write code 
# we can do is -- type alias we create a new variable for a particular type
# so now instead of writing all this
# def create_user(first_name: str, last_name: str, age: int | None = None) -> dict[str, str|int|None]:
# we will write user
# def create_user(first_name: str, last_name: str, age: int | None = None) -> User
# python3.12

# RGB = NewType("RGB", tuple[int|int|int])
# HSL = NewType("HSL", tuple[int|int|int])
# #type User = dict[str, str | int | RGB | None]

# class User(TypedDict):
#     first_name: str
#     last_name: str
#     email: str
#     sge: int | None
#     fav_color: RGB | None

# def create_user(
#         first_name: str, 
#         last_name: str, 
#         age: int | None = None, 
#         fav_color: RGB | None = None) -> User:
#     email = f"{first_name.lower()}_{last_name.lower()}@example.com"

# #    str_age = str(age)

#     return{
#         "first_name": first_name,
#         "last_name": last_name,
#         "email": email,
#         "age": age,
#         "fav_color": fav_color
#     }

# user1 = create_user("harsh", "agarwal", age=92, fav_color=RGB((109,124,150)))
# user2 = create_user("jhon","doe", fav_color=HSL((206,10,48)))
# print(user1)
# print(user2)

#coverting evrything to a data class
#TypeVar type should be same across 
from  typing import NewType, Any, TypeVar
from dataclasses import dataclass
import random

import requests

resp = requests.get("https://coreyms.com")
status = resp.status_code
status = "ok"

RGB = NewType("RGB", tuple[int|int|int])
HSL = NewType("HSL", tuple[int|int|int])
#type User = dict[str, str | int | RGB | None]

@dataclass
class User:
    first_name: str
    last_name: str
    email: str
    age: int | None = None
    fav_color: RGB | None = None

def create_user(
        first_name: str, 
        last_name: str, 
        age: int | None = None, 
        fav_color: RGB | None = None) -> User:
    email = f"{first_name.lower()}_{last_name.lower()}@example.com"

#    str_age = str(age)

    return User(
        first_name = first_name,
        last_name = last_name,
        email = email,
        age = age,
        fav_color= fav_color
    )
# def random_choice(items: list[User]) -> User:
#     return random.choice(items)
#changed to 
# def random_choice(items: list[Any]) -> Any:
#     return random.choice(items)
#changed to
#generaic typevar
T = TypeVar("T")
def random_choice(items: list[T]) -> T:
    return random.choice(items)
#after TypeVar connection between input and output

user1 = create_user("harsh", "agarwal", age=92, fav_color=RGB((109,124,150)))
user2 = create_user("jhon","doe", fav_color=HSL((206,10,48)))
#print(user1)
#print(user2)

users = [user1, user2]
rando_user = random_choice(users)
print(rando_user)

#does not know what it is
#rando_user.
#after adding typeVar a list appear that has module names like age email, fav color
#rando_user.
emails = [user.email for user in users]
#rando_email = random_choice(emails)#wrong
rando_email = random_choice(emails)
print(rando_email)

#now removed import typeVar and wrote this instead
#removed all this 
# T = TypeVar("T")
# def random_choice(items: list[T]) -> T:
#     return random.choice(items)
#and add this
# def random_choice[T](items: list[T]) -> T:
#     return random.choice(items)
#genaric typevar
#new python3.12 syntax


##inputs: Generic
##outputs: specific