import ast
from pathlib import Path
from pprint import pprint
import re
from dataclasses import dataclass, field
from typing import Literal, Optional

from . import CompositeUnit, InvalidUnitNameError, Unit, UnitRegistry


REGEXP_SCALAR = re.compile(r"([+-])? *(?:\d* *\. *\d+|\d+(?: *\.)?)(?:e([+-])?(\d+))?")
REGEXP_PUNCT = re.compile(r"\*\*|\*|/|\(|\)|\^")


@dataclass
class GroupOpenToken:
  pass

@dataclass
class GroupCloseToken:
  pass

@dataclass
class OpToken:
  value: Literal['mul', 'div', 'exp']

@dataclass
class ScalarToken:
  value: float | int

@dataclass
class UnitToken:
  value: Unit

Token = GroupCloseToken | GroupOpenToken | OpToken | ScalarToken | UnitToken


ureg = UnitRegistry.load((Path(__file__).parent / "registry.toml").open("rb"))

def tokenize(input_value: str, /):
  cursor = 0
  tokens = list[Token]()

  while cursor < len(input_value):
    forward_value = input_value[cursor:]

    if (match := REGEXP_SCALAR.match(forward_value)):
      cursor += match.span()[1]
      value = ast.literal_eval(match.group())
      tokens.append(ScalarToken(value))
    elif (match := REGEXP_PUNCT.match(forward_value)):
      cursor += match.span()[1]

      match match.group():
        case "*":
          tokens.append(OpToken('mul'))
        case "/":
          tokens.append(OpToken('div'))
        case "**" | "^":
          tokens.append(OpToken('exp'))
        case "(":
          tokens.append(GroupOpenToken())
        case ")":
          tokens.append(GroupCloseToken())
    elif (match := re.match(" +", forward_value)):
      cursor += match.span()[1]
    elif (match := re.match("[a-zA-Z]+", forward_value)):
      cursor += match.span()[1]
      value = match.group()

      try:
        unit = ureg.unit(value)
      except InvalidUnitNameError:
        print(f"Unknown token '{match.group()}'")
      else:
        tokens.append(UnitToken(unit))

      # if (unit := UNITS.get(match.group())):
      #   tokens.append(UnitToken(unit))
      # else:
      #   print(f"Unknown token '{match.group()}'")
    else:
      raise Exception(f"Unknown token '{forward_value[0]}'")

  return tokens


# def analyze(tokens: list[Token], /):
#   current_op: Optional[Literal['mul', 'div', 'exp']] = None
#   current_scalar: Optional[float | int] = None
#   current_unit: Optional[Unit] = None
#   div_mode: Optional[bool] = None

#   result: Optional[Quantity] = None

#   def commit():
#     nonlocal current_scalar, current_unit, result

#     if current_op is not None:
#       raise Exception("Invalid")
#     elif (current_scalar is not None) and (current_unit is not None):
#       increment =  current_scalar * current_unit

#       if result is None:
#         result = increment
#       else:
#         result += increment

#       current_scalar = None
#       current_unit = None
#     elif (current_scalar is not None):
#       result += current_scalar * ureg.dimensionless
#     elif (current_unit is not None):
#       raise Exception("Invalid")


#   for token in tokens:
#     match token:
#       case OpToken(value) if current_unit:
#         current_op = value
#       case ScalarToken(value): # if (not current_scalar) and (not current_unit):
#         commit()
#         current_scalar = value
#       case UnitToken(value) if (current_scalar is not None) and (current_unit is None):
#         current_unit = value
#       case UnitToken(value) if (current_unit is not None) and (current_op is not None):
#         match current_op:
#           case 'mul':
#             current_unit *= value
#           case 'div':
#             current_unit /= value
#           case 'exp':
#             raise Exception()

#         current_op = None
#       case _:
#         raise Exception("Invalid 3")

#   commit()

#   return result


@dataclass
class ParserError(Exception):
  message: str
  token: Optional[Token] = None


@dataclass
class TokenWalker:
  cursor: int = field(default=0, init=False)
  tokens: list[GroupOpenToken]

  groups: list[Token] = field(default_factory=list, init=False)

  def dec(self):
    self.cursor -= 1

  def inc(self):
    self.cursor += 1

  def peek(self):
    return tokens[self.cursor] if (self.cursor < len(self.tokens)) else None

  def pop(self):
    token = self.peek()
    self.cursor += 1
    return token

  def __iter__(self):
    for _ in self.tokens[self.cursor:]:
      yield self.pop()


  def accept_base_unit(self):
    match self.peek():
      case UnitToken(value):
        self.inc()
        return value
      case _:
        return None

  def accept_composite_unit(self) -> Optional[CompositeUnit]:
    if isinstance(token := self.pop(), GroupOpenToken):
      self.groups.append(token)
    else:
      self.dec()

    base_unit = self.accept_base_unit()

    if not base_unit:
      return None

    current_unit = base_unit

    for token in self:
      match token:
        case OpToken('exp'):
          exp = self.accept_scalar()

          if exp is None:
            raise ParserError("Invalid token, expected scalar", self.peek())

          current_unit **= exp

        case OpToken('div' | 'mul'):
          if isinstance(self.peek(), GroupOpenToken):
            other_unit = self.accept_composite_unit()
          else:
            other_unit = self.accept_base_unit()

          if other_unit is None:
            raise ParserError("Invalid token, expected unit", self.peek())

          match token:
            case OpToken('mul'):
              current_unit *= other_unit
            case OpToken('div'):
              current_unit /= other_unit

        case GroupCloseToken():
          if not self.groups:
            raise ParserError("Invalid token, unexpected group close", token)

          self.groups.pop()

          # current_unit *= other_unit

        #   if value == 'mul':
        #     base_unit *= self.accept_base_unit()
        #   elif value == 'div':
        #     base_unit /= self.accept_base_unit()

    if self.groups:
      raise ParserError("Invalid token, expected group close", self.groups[-1])

    return current_unit

  # def accept_group(self):
  #   if not isinstance(self.peek(), GroupOpenToken):
  #     return None

  #   self.inc()

  #   tokens = list[Token]()
  #   count = 0

  #   for token in self:
  #     match token:



  def accept_quantity(self):
    scalar = self.accept_scalar()

    if scalar is None:
      return None

    unit = self.accept_composite_unit()

    if unit is None:
      return ureg.dimensionless(scalar)

    return scalar * unit

  def accept_scalar(self):
    match self.peek():
      case ScalarToken(value):
        self.inc()
        return value
      case _:
        return None

  def expect_eof(self):
    if (token := self.peek()):
      raise ParserError("Expected EOF", token)

def analyze(tokens: list[Token], /):
  walker = TokenWalker(tokens)
  x = walker.accept_quantity()
  walker.expect_eof()
  return x

# def accept_quantity(walker: TokenWalker, /):
#   match walker.peek():
#     case ScalarToken(value):
#       scalar = value
#     case _:
#       return None

#   walker.pop()

#   unit = accept_composite_unit(walker)
#   return unit * scalar

# def accept_base_unit(walker: TokenWalker, /):
#   match walker.peek():
#     case UnitToken(value):
#       walker.pop()
#       return value
#     case _:
#       return None

# def accept_composite_unit(walker: TokenWalker, /):
#   base_unit = accept_base_unit(walker)

#   if base_unit:




tokens = tokenize("-30.6e2 (meter * s)**-2.5 * (s^2)")
pprint(tokens)
print(analyze(tokens))


# ----


"""
REGEXP_SCALAR = regex.compile(r"^(\d+)(?:,(\d+))*$")

def parse_scalar(value: str, /):
  match = REGEXP_SCALAR.match(value)

  if not match:
    return None

  factor = 0
  result = 0

  # for capture in [m.group]
  # print(match.captures(2))
  # print(repr(match.group(1)))
  # print(repr(m))

  for num in [match.group(1), *match.captures(2)][::-1]:
    result += int(num) * (10 ** factor)
    factor += len(num)

  return result

print(parse_scalar("123,5,6"))
print(parse_scalar("123"))
"""
