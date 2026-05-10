# Python Type Hints — Complete Tutorial Summary

**Source:** Corey Schafer — "Python Type Hints" ([YouTube](https://www.youtube.com/watch?v=RwH2UzC2rIo))

---

## 1. What Are Type Hints?

- Type hints let you add **type information** to your Python code.
- **Benefits:**
  - Self-documenting code
  - Catch bugs earlier
  - Better IDE auto-completion
- **Important:** Type hinting by itself does **NOT** give you type checking in Python. You need a **type checker** to actually validate hints.
- Tutorial uses **mypy** as the type checker (via the VS Code extension or CLI).

### Installing mypy

```bash
pip install mypy
# or with uv
uv add mypy
# or as a one-off tool
uvx mypy main.py
```

Output when running mypy:
```
Success: no issues found in 1 source file
```

---

## 2. Starting Point — Code Without Type Hints

```python
def create_user(first_name, last_name, age=None):
    email = f"{first_name.lower()}_{last_name.lower()}@example.com"
    return {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "age": age,
    }

user1 = create_user("Corey", "Schafer", age=38)
user2 = create_user("John", "Doe")
print(user1)
print(user2)
```

Code works fine, but no type information at all.

---

## 3. Variable Type Hints

### Syntax: `variable: type = value`

**Before:**
```python
name = "Corey"
age = 38
```

**After:**
```python
name: str = "Corey"
age: int = 38
```

### What mypy catches:

```python
age: int = 38
age = "38"   # ❌ mypy error: Incompatible types in assignment
             # has type "str", variable has type "int"
```

> **Corey's tip:** He almost never type-hints variables that are **obvious** (like `name = "Corey"`). Annotate variables only when:
> - You want it type-checked as it changes
> - The variable is more complex (iterables, etc.)

---

## 4. Function Parameter Type Hints

This is where type hints **really start to become useful**.

**Before:**
```python
def create_user(first_name, last_name, age=None):
    ...
```

**After:**
```python
def create_user(first_name: str, last_name: str, age: int = None):
    ...
```

You're now telling anyone (including yourself) **exactly what types** each parameter expects.

---

## 5. Return Type Annotation

Use `->` after the parentheses to specify what the function returns.

**Before:**
```python
def create_user(first_name: str, last_name: str, age: int = None):
    ...
    return { ... }
```

**After:**
```python
def create_user(first_name: str, last_name: str, age: int = None) -> dict:
    ...
    return { ... }
```

> **Note on the `email` variable inside:** Since `email = f"..."` is obviously an f-string, Corey wouldn't add `email: str = ...` here.

---

## 6. Union Types — Handling Optional Parameters

### Problem:
```python
def create_user(first_name: str, last_name: str, age: int = None):
    # ❌ mypy error: age default is None but type is int
```

### Solution — Use `|` (pipe = "or") — Python 3.10+

```python
def create_user(first_name: str, last_name: str, age: int | None = None):
    ...
```

This says **age can be an int OR None**.

### Older syntax (`Optional`) — pre-Python 3.10

```python
from typing import Optional

def create_user(first_name: str, last_name: str, age: Optional[int] = None):
    ...
```

`Optional[int]` is equivalent to `int | None`. You'll see this in older codebases.

---

## 7. More Specific Dictionary Return Types

### Less specific:
```python
-> dict
```

### More specific (typed keys & values):
```python
-> dict[str, str]   # keys are str, values are str
```

### With multiple value types using union:
```python
-> dict[str, str | int | None]   # values can be str, int, or None
```

**Full function so far:**
```python
def create_user(
    first_name: str,
    last_name: str,
    age: int | None = None
) -> dict[str, str | int | None]:
    email = f"{first_name.lower()}_{last_name.lower()}@example.com"
    return {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "age": age,
    }
```

---

## 8. Type Aliases

The dict signature above is getting **crowded**. A **type alias** creates a new name for an existing type.

### Creating a type alias (Python 3.12+):
```python
type User = dict[str, str | int | None]
```

The explicit `type` keyword (3.12+) makes it clear this is a type alias.

### Using it:

**Before:**
```python
def create_user(...) -> dict[str, str | int | None]:
```

**After:**
```python
def create_user(...) -> User:
```

### Type aliases for any type — example with RGB:

```python
type RGB = tuple[int, int, int]
```

Now anywhere you'd write `tuple[int, int, int]`, you can just write `RGB`.

---

## 9. The Type Alias Pitfall — RGB vs HSL

### Adding a `favorite_color` parameter:

```python
type RGB = tuple[int, int, int]
type User = dict[str, str | int | RGB | None]

def create_user(
    first_name: str,
    last_name: str,
    age: int | None = None,
    favorite_color: RGB | None = None,
) -> User:
    email = f"{first_name.lower()}_{last_name.lower()}@example.com"
    return {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "age": age,
        "favorite_color": favorite_color,
    }

user1 = create_user("Corey", "Schafer", age=38, favorite_color=(109, 124, 150))
```

### The problem:

If your codebase also has HSL colors (also `tuple[int, int, int]`):

```python
type HSL = tuple[int, int, int]

# Developer accidentally passes HSL where RGB is expected
user2 = create_user("John", "Doe", favorite_color=(206, 10, 48))  # ❌ HSL!
```

**No error is raised** — type aliases are just nicknames. RGB and HSL are both `tuple[int, int, int]` underneath, so they're interchangeable to the type checker.

---

## 10. `NewType` — Creating Distinct Types

`NewType` creates a **brand new, distinct type** the type checker treats separately.

```python
from typing import NewType

RGB = NewType("RGB", tuple[int, int, int])
HSL = NewType("HSL", tuple[int, int, int])
```

### Now you must explicitly construct the type:

**Before (with type alias):**
```python
user1 = create_user("Corey", "Schafer", favorite_color=(109, 124, 150))
```

**After (with NewType):**
```python
user1 = create_user("Corey", "Schafer", favorite_color=RGB((109, 124, 150)))

# This now fails type checking:
user2 = create_user("John", "Doe", favorite_color=HSL((206, 10, 48)))
# ❌ mypy error: argument has incompatible type "HSL"; expected "RGB | None"
```

The developer's mistake **gets caught immediately**.

---

## 11. `TypedDict` — Per-Key Type Checking

### Problem with the dict approach:

```python
type User = dict[str, str | int | RGB | None]

def create_user(...) -> User:
    str_age = str(age)   # contrived: age accidentally turned into str
    return {
        ...
        "age": str_age,   # ❌ should be int | None but it's str
    }
```

**No error** — because the type alias says **any** value can be `str | int | RGB | None`, so a string for `age` is fine.

### Solution — `TypedDict`:

```python
from typing import TypedDict, NewType

RGB = NewType("RGB", tuple[int, int, int])

class User(TypedDict):
    first_name: str
    last_name: str
    email: str
    age: int | None
    favorite_color: RGB | None
```

Now each **key** has its **own type**, and mypy will catch:

```python
"age": str_age,   # ❌ mypy: expression has type "str", TypedDict item "age" has type "int | None"
```

---

## 12. Switching to a `dataclass`

If you're creating this **from scratch** (not working with existing dicts), a `dataclass` is often better — it gives you a real class with auto-generated `__init__`, `__repr__`, etc.

### Convert `TypedDict` → `dataclass`:

**Before (TypedDict):**
```python
from typing import TypedDict

class User(TypedDict):
    first_name: str
    last_name: str
    email: str
    age: int | None
    favorite_color: RGB | None
```

**After (dataclass):**
```python
from dataclasses import dataclass

@dataclass
class User:
    first_name: str
    last_name: str
    email: str
    age: int | None = None
    favorite_color: RGB | None = None
```

### Update the function to return a `User` instance:

**Before:**
```python
def create_user(...) -> User:
    ...
    return {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "age": age,
        "favorite_color": favorite_color,
    }
```

**After:**
```python
def create_user(...) -> User:
    email = f"{first_name.lower()}_{last_name.lower()}@example.com"
    return User(
        first_name=first_name,
        last_name=last_name,
        email=email,
        age=age,
        favorite_color=favorite_color,
    )
```

### Quick rule-of-thumb:
| Situation | Use |
|-----------|-----|
| Working with **existing dicts** | `TypedDict` |
| Creating **from scratch** | `dataclass` |

---

## 13. Generics — The `random_choice` Problem

### The setup:
```python
import random

def random_choice(items: list[User]) -> User:
    return random.choice(items)

users = [user1, user2]
rando_user = random_choice(users)         # ✅ works
emails = [user.email for user in users]
rando_email = random_choice(emails)       # ❌ list[str] passed where list[User] expected
```

We want this function to work with **any** type — not just `list[User]`.

---

## 14. Attempt #1 — `Any` (the wrong way)

```python
from typing import Any

def random_choice(items: list[Any]) -> Any:
    return random.choice(items)
```

### Pros:
- No mypy errors anywhere.

### Cons:
- IDE has **no idea** what comes back.
- `rando_user.` shows **no autocomplete** — IDE doesn't know it's a `User`.
- Lost the connection between input type and output type.

> **Use `Any` only when** you genuinely don't know or care (external data, unvalidated JSON, etc.).

---

## 15. Attempt #2 — `TypeVar` (the older correct way)

```python
from typing import TypeVar

T = TypeVar("T")

def random_choice(items: list[T]) -> T:
    return random.choice(items)
```

### What this says:
- `T` is a placeholder for "some type".
- Whatever type the **list** contains, that's the type that gets **returned**.
- The connection between **input** and **output** is preserved.

### IDE behavior now:
```python
rando_user = random_choice(users)
rando_user.    # ✅ autocomplete shows: first_name, last_name, email, age, favorite_color

rando_email = random_choice(emails)
rando_email.   # ✅ autocomplete shows str methods like .upper(), .lower(), etc.
```

---

## 16. Attempt #3 — Python 3.12+ Generic Syntax (cleanest)

In Python 3.12, you no longer need to import `TypeVar` or declare `T` separately.

**Before (older syntax):**
```python
from typing import TypeVar

T = TypeVar("T")

def random_choice(items: list[T]) -> T:
    return random.choice(items)
```

**After (Python 3.12+):**
```python
def random_choice[T](items: list[T]) -> T:
    return random.choice(items)
```

### Advantages:
- No `TypeVar` import.
- `T` is **scoped to the function** (cleaner).
- More concise and readable.

---

## 17. Third-Party Packages — Type Stubs

Many third-party packages **don't include** type hints. mypy treats them as `Any` and gives no warnings.

### Example with `requests`:

```python
import requests

resp = requests.get("https://coreyms.com", timeout=5)
status = resp.status_code
```

### mypy warning:
```
Library stubs not installed for "requests"
Hint: "python3 -m pip install types-requests"
```

### Install stubs:
```bash
pip install types-requests
# or with uv
uv add types-requests
```

### Pattern: `types-<package_name>`

After installing, mypy now knows:
```python
status = resp.status_code   # known to be int
status = "ok"               # ❌ mypy: incompatible types — has type "str", variable has type "int"
```

---

## 18. Best Practices & Final Tips

### Type hinting is **not all-or-nothing**
- Start small.
- Add hints to new functions you write.
- Use them in **critical** parts of your application.
- Gradually retrofit older code over time.
- Add them piece by piece — one function/variable at a time.

### General rule of thumb:

> **Inputs as generic as possible. Outputs as specific as possible.**

#### Example — the `random_choice` function:
- We made the **input** generic (any list, any type).
- It could be made even more generic: accept an `Iterable` instead of a `list` — then it would also work for tuples, sets, etc.

#### Example — the `create_user` function:
We progressively got **more specific** with the output:

| Stage | Return type |
|-------|-------------|
| 1 | `dict` (untyped) |
| 2 | `dict[str, str \| int \| None]` (typed keys/values) |
| 3 | `TypedDict` subclass `User` (per-key types) |
| 4 | `@dataclass` `User` (typed attributes, real class) |

---

## 19. Final Combined Code

```python
from typing import NewType
from dataclasses import dataclass
import random
import requests

# --- Distinct color types ---
RGB = NewType("RGB", tuple[int, int, int])
HSL = NewType("HSL", tuple[int, int, int])


# --- User as a dataclass ---
@dataclass
class User:
    first_name: str
    last_name: str
    email: str
    age: int | None = None
    favorite_color: RGB | None = None


def create_user(
    first_name: str,
    last_name: str,
    age: int | None = None,
    favorite_color: RGB | None = None,
) -> User:
    email = f"{first_name.lower()}_{last_name.lower()}@example.com"
    return User(
        first_name=first_name,
        last_name=last_name,
        email=email,
        age=age,
        favorite_color=favorite_color,
    )


# --- Generic helper (Python 3.12+ syntax) ---
def random_choice[T](items: list[T]) -> T:
    return random.choice(items)


# --- Usage ---
user1 = create_user("Corey", "Schafer", age=38, favorite_color=RGB((109, 124, 150)))
user2 = create_user("John", "Doe")  # passing HSL here would now be a type error

users = [user1, user2]
rando_user = random_choice(users)        # IDE knows this is a User
print(rando_user)

emails = [user.email for user in users]
rando_email = random_choice(emails)       # IDE knows this is a str
print(rando_email)

# --- Third-party with stubs installed (`uv add types-requests`) ---
resp = requests.get("https://coreyms.com", timeout=5)
status = resp.status_code                 # known to be int
```

---

## 20. Quick Reference Cheat Sheet

| Concept | Syntax |
|---------|--------|
| Variable hint | `name: str = "Corey"` |
| Function param | `def f(x: int):` |
| Return type | `def f() -> str:` |
| Optional / union | `int \| None` (3.10+) or `Optional[int]` |
| List of T | `list[int]` |
| Dict | `dict[str, int]` |
| Tuple of fixed types | `tuple[int, int, int]` |
| Type alias (3.12+) | `type Vector = list[float]` |
| Distinct type | `UserId = NewType("UserId", int)` |
| Per-key dict types | `class X(TypedDict): ...` |
| Real class with hints | `@dataclass class X: ...` |
| Generic function (3.12+) | `def f[T](x: list[T]) -> T:` |
| Generic function (older) | `T = TypeVar("T"); def f(x: list[T]) -> T:` |
| Wildcard | `from typing import Any` |
| Third-party stubs | `pip install types-<package>` |

---

## What Was NOT Covered (mentioned by Corey)

- **Pydantic** — runtime validation library using type hints (future Corey video).
- **`asyncio`** — also a future Corey video.

---

*End of summary.*
