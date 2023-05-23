import ast
import re
from abc import ABC
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

from snaptext import LocatedString, LocationArea

from .core import CompositeUnit, InvalidUnitNameError, Unit, UnitRegistry


REGEXP_SCALAR = re.compile(r"([+-] *)?(?:\d* *\. *\d+|\d+(?: *\.)?)(?:e([+-])?(\d+))?")
REGEXP_PUNCT = re.compile(r"\*\*|\*|/|\(|\)|\^")


@dataclass(kw_only=True)
class BaseToken(ABC):
  area: LocationArea

@dataclass
class GroupOpenToken(BaseToken):
  pass

@dataclass
class GroupCloseToken(BaseToken):
  pass

@dataclass
class OpToken(BaseToken):
  value: Literal['mul', 'div', 'exp']

@dataclass
class ScalarToken(BaseToken):
  value: float | int

@dataclass
class UnitToken(BaseToken):
  value: Unit

Token = GroupCloseToken | GroupOpenToken | OpToken | ScalarToken | UnitToken


@dataclass
class ParserError(Exception):
  message: str
  area: LocationArea


def tokenize(input_value: LocatedString, registry: UnitRegistry):
  cursor = 0
  tokens = list[Token]()

  while cursor < len(input_value):
    forward_value = input_value[cursor:]

    if (match := forward_value.match_re(REGEXP_SCALAR)):
      cursor += match.span()[1]

      value = ast.literal_eval(match.group())
      tokens.append(ScalarToken(value, area=match.area))
    elif (match := forward_value.match_re(REGEXP_PUNCT)):
      cursor += match.span()[1]

      match match.group():
        case "*":
          tokens.append(OpToken('mul', area=match.area))
        case "/":
          tokens.append(OpToken('div', area=match.area))
        case "**" | "^":
          tokens.append(OpToken('exp', area=match.area))
        case "(":
          tokens.append(GroupOpenToken(area=match.area))
        case ")":
          tokens.append(GroupCloseToken(area=match.area))
    elif (match := re.match(" +", forward_value)):
      cursor += match.span()[1]
    elif (match := forward_value.match_re("[a-zA-Z]+")):
      cursor += match.span()[1]
      value = match.group()

      try:
        unit = registry.unit(value)
      except InvalidUnitNameError:
        raise ParserError(f"Invalid unit '{value}'", match.area)
      else:
        tokens.append(UnitToken(unit, area=match.area))
    else:
      raise ParserError("Invalid token", forward_value[0].area)

  return tokens


@dataclass
class TokenWalker:
  registry: UnitRegistry
  source: LocatedString
  tokens: list[Token]

  cursor: int = field(default=0, init=False)
  groups: list[Token] = field(default_factory=list, init=False)

  def dec(self):
    self.cursor -= 1

  def inc(self):
    self.cursor += 1

  def peek(self):
    return self.tokens[self.cursor] if (self.cursor < len(self.tokens)) else None

  def peek_area(self):
    return next_token.area if (next_token := self.peek()) else self.source[-1].area

  def pop(self):
    token = self.peek()
    self.cursor += 1
    return token

  def __iter__(self):
    while token := self.pop():
      yield token


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
            raise ParserError("Invalid token, expected scalar", self.peek_area())

          current_unit **= exp

        case OpToken('div' | 'mul'):
          if isinstance(self.peek(), GroupOpenToken):
            other_unit = self.accept_composite_unit()
          else:
            other_unit = self.accept_base_unit()

          if other_unit is None:
            raise ParserError("Invalid token, expected unit", self.peek_area())

          match token:
            case OpToken('mul'):
              current_unit *= other_unit
            case OpToken('div'):
              current_unit /= other_unit

        case GroupCloseToken():
          if not self.groups:
            raise ParserError("Invalid token", token.area)

          self.groups.pop()

        case _:
          raise ParserError("Invalid token", token.area)

    if self.groups:
      raise ParserError("Unexpected EOF, expected matching closing parenthesis", self.groups[-1].area)

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
      raise ParserError("Invalid token", token.area)

def walk(tokens: list[Token], source: LocatedString, registry: UnitRegistry):
  walker = TokenWalker(registry, source, tokens)

  quantity = walker.accept_quantity()

  if quantity is None:
    raise ParserError("Invalid token", walker.peek_area())

  walker.expect_eof()

  return quantity


def parse(raw_input_value: LocatedString | str, /, registry: UnitRegistry):
  input_value = LocatedString(raw_input_value)
  tokens = tokenize(input_value, registry)
  return walk(tokens, input_value, registry)


__all__ = [
  'ParserError'
]


if __name__ == "__main__":
  ureg = UnitRegistry.load((Path(__file__).parent / "registry.toml").open("rb"))

  try:
    # print(parse("-3 km^-1", ureg))
    print(parse("-3", ureg))
    # print(parse("-30.6e2 (meter * s)**-2.5 * (s^2)", ureg))
    # pprint(tokens)
  except ParserError as e:
    print(e.message)
    print(e.area.format())
