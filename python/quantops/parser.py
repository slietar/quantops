import ast
import re
from abc import ABC
from dataclasses import dataclass, field
from typing import Literal, Optional, TypeVar

from snaptext import LocatedString, LocationArea

from .core import CompositeUnit, Dimensionality, InvalidUnitNameError, UnitAssembly, UnitAssemblyConstantPart, UnitAssemblyVariablePart, UnitRegistry


REGEXP_SCALAR = re.compile(r"([+-] *)?(?:\d* *\. *\d+|\d+(?: *\.)?)(?:e([+-])?(\d+))?")
REGEXP_PUNCT = re.compile(r"\*\*|\*|/|\(|\)|\^|±|\+-|-|~")
REGEXP_UNIT = re.compile(r"[a-zA-Z_\u00b5\u03bc]+")


T = TypeVar('T')


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
    elif (match := forward_value.match_re(REGEXP_UNIT)):
      cursor += match.span()[1]
      tokens.append(UnitToken(match.group(), area=match.area))
    else:
      raise ParserError("Invalid value", forward_value[0].area)

  return TokenWalker(registry, input_value, tokens)


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
    dimensionality = Dimensionality()

    before_variable_parts = list[UnitAssemblyConstantPart]()
    after_variable_parts = list[UnitAssemblyConstantPart]()
    variable_part: Optional[UnitAssemblyVariablePart] = None

    while True:
      power = 1.0
      started = False
      variable = False

      if before_variable_parts or variable_part:
        match self.peek():
          case OpToken('mul'):
            self.inc()
          case OpToken('div'):
            self.inc()
            power = -1.0
            started = True

      if not variable_part:
        match self.peek():
          case OpToken('var'):
            self.inc()
            variable = True
          case None:
            break

      match self.peek():
        case UnitToken(value):
          self.inc()
          unit_name = value
        case _ if started:
          raise ParserError("Invalid token, expected unit", self.peek_area())
        case _:
          break

      power *= self.accept_assembly_power()

      if (group := self.registry._unit_groups.get(unit_name)) and variable:
        variable_part = UnitAssemblyVariablePart(frozenset(group), power)
        dimensionality *= next(iter(group)).dimensionality ** power
      elif (unit := self.registry._units_by_name.get(unit_name)):
        if variable:
          variable_part = UnitAssemblyVariablePart(frozenset({unit}), power)
        else:
          (after_variable_parts if variable_part else before_variable_parts).append(UnitAssemblyConstantPart(unit, power))

        dimensionality *= unit.dimensionality ** power
      else:
        raise ParserError("Invalid name", value.area)

    if not (before_variable_parts or variable_part or after_variable_parts):
      return None

    return UnitAssembly(
      after_variable_parts,
      before_variable_parts,
      variable_part
    ), dimensionality

  def accept_assembly_part(self, *, allow_variable: bool):
    variable = False

    if allow_variable:
      match self.peek():
        case OpToken('var'):
          self.inc()
          variable = True
        case None:
          return None

    match self.peek():
      case UnitToken(value):
        self.inc()

        if (group := self.registry._unit_groups.get(value)) and variable:
          return True, frozenset(group)
        elif (unit := self.registry._units_by_name.get(value)):
          return (True, frozenset({unit})) if variable else (False, unit)
        else:
          raise ParserError("Invalid name", value.area)
      case _ if variable:
        raise ParserError("Invalid token, expected unit", self.peek_area())
      case _:
        return None

  def accept_assembly_power(self):
    match self.peek():
      case OpToken('exp'):
        self.inc()
        exp = self.accept_scalar()

        if exp is None:
          raise ParserError("Invalid token, expected scalar", self.peek_area())

        return exp
      case _:
        return 1

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
      return self.registry._dimensionless(scalar)

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

  def expect_only(self, value: Optional[T], /) -> T:
    if value is None:
      raise ParserError("Invalid token", self.peek_area())

    self.expect_eof()

    return value


__all__ = [
  'ParserError'
]
