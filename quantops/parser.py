import ast
import re
from abc import ABC
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

from snaptext import LocatedString, LocationArea

from .core import CompositeUnit, InvalidUnitNameError, UnitAssemblyOption, UnitRegistry


REGEXP_SCALAR = re.compile(r"([+-] *)?(?:\d* *\. *\d+|\d+(?: *\.)?)(?:e([+-])?(\d+))?")
REGEXP_PUNCT = re.compile(r"\*\*|\*|/|\(|\)|\^|±|\+-|-|~")


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
  value: Literal['mul', 'div', 'exp', 'rng', 'unc', 'var']

@dataclass
class ScalarToken(BaseToken):
  value: float | int

@dataclass
class UnitToken(BaseToken):
  value: LocatedString

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

    if ((not tokens) or not isinstance(tokens[-1], ScalarToken)) and (match := forward_value.match_re(REGEXP_SCALAR)):
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
        case "±" | "+-":
          tokens.append(OpToken('unc', area=match.area))
        case "-":
          tokens.append(OpToken('rng', area=match.area))
        case "~":
          tokens.append(OpToken('var', area=match.area))
        case "(":
          tokens.append(GroupOpenToken(area=match.area))
        case ")":
          tokens.append(GroupCloseToken(area=match.area))
    elif (match := re.match(" +", forward_value)):
      cursor += match.span()[1]
    elif (match := forward_value.match_re("[a-zA-Z]+")):
      cursor += match.span()[1]
      tokens.append(UnitToken(match.group(), area=match.area))
    else:
      raise ParserError("Invalid value", forward_value[0].area)

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


  def accept_assembly(self):
    components = list()
    var_component_index = None

    while True:
      factor: Optional[int] = None

      if components:
        match self.peek():
          case OpToken('mul'):
            self.inc()
            factor = 1
          case OpToken('div'):
            self.inc()
            factor = -1

      if var_component_index is None:
        match self.peek():
          case OpToken('var'):
            self.inc()
            factor = 1
            var_component_index = len(components)

      component = self.accept_assembly_component()

      if component is None:
        if factor is not None:
          raise ParserError("Invalid token, expected unit", self.peek_area())

        break

      if factor is not None:
        component = (component[0], component[1] * factor)

      components.append(component)

    return UnitAssemblyOption(
      tuple(components),
      var_component_index
    )

    # return (components, var_component_index)

  def accept_assembly_component(self):
    match self.peek():
      case UnitToken(value):
        self.inc()

        if (unit := self.registry._units_by_name.get(value)):
          item = frozenset({unit})
        else:
          raise ParserError("Invalid name", value.area)
      case _:
        return None

    match self.peek():
      case OpToken('exp'):
        self.inc()
        exp = self.accept_scalar()

        if exp is None:
          raise ParserError("Invalid token, expected scalar", self.peek_area())

        return (item, exp)
      case _:
        return (item, 1.0)

  def accept_base_unit(self):
    match self.peek():
      case UnitToken(value):
        self.inc()

        try:
          unit = self.registry.unit(value)
        except InvalidUnitNameError:
          raise ParserError(f"Invalid unit '{value}'", value.area)

        return unit
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

  def accept_quantity(self):
    scalar = self.accept_scalar()

    if scalar is None:
      return None

    unit = self.accept_composite_unit()

    if unit is None:
      return self.registry.dimensionless(scalar)

    return scalar * unit

  def accept_measurement(self):
    quantity = self.accept_quantity()

    if quantity is None:
      return None

    match self.peek():
      case OpToken('unc'):
        self.inc()
      case None:
        return (quantity, )
      case _:
        raise ParserError("Invalid token, expected uncertainty operator or EOF", self.peek_area())

    uncertainty = self.accept_quantity()

    if uncertainty is None:
      raise ParserError("Invalid token, expected uncertainty quantity", self.peek_area())

    return (quantity, uncertainty)

  def accept_range(self):
    quantity = self.accept_quantity()

    if quantity is None:
      return None

    match self.peek():
      case OpToken('rng'):
        self.inc()
      case _:
        raise ParserError("Invalid token, expected range operator", self.peek_area())

    other_quantity = self.accept_quantity()

    if other_quantity is None:
      raise ParserError("Invalid token, expected range quantity", self.peek_area())

    return (quantity, other_quantity)

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

  def expect_only(self, value: Optional[Any], /):
    if value is None:
      raise ParserError("Invalid token", self.peek_area())

    self.expect_eof()

    return value


def parse(raw_input_value: LocatedString | str, /, registry: UnitRegistry):
  input_value = LocatedString(raw_input_value)
  tokens = tokenize(input_value, registry)

  # from pprint import pprint
  # pprint(tokens)

  walker = TokenWalker(registry, input_value, tokens)
  return walker.expect_only(walker.accept_quantity())

def parse_assembly(raw_input_value: LocatedString | str, /, registry: UnitRegistry):
  input_value = LocatedString(raw_input_value)
  tokens = tokenize(input_value, registry)
  walker = TokenWalker(registry, input_value, tokens)
  return walker.expect_only(walker.accept_assembly())


__all__ = [
  'ParserError'
]
