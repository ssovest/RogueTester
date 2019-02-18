# -*- coding: utf-8 -*-

import random
import math

"""
Всякие вспомогательные классы и функции
"""

class LoopedTuple(object):

	def __init__(self, data):
		self.data = data
		self.len = len(data)

	def __getitem__(self, index):
		return self.data[index % self.len]

class Node(object):

	def __init__(self, value):
		self.value = value
		self.children = []
		self.parent = None
		self.depth = 0

	def __eq__(self, other):
		return self.value == other.value

	def __hash__(self):
		return self.value.__hash__()

	def add_child(self, child):
		child.parent = self
		child.depth = self.depth + 1
		self.children.append(child)

class Position(object):

	"""
	Рабочая лошадка этой игры. Используется чуть менее, чем везде.
	"""

	#кажется, трюк с кешем работает капельку быстрее, чем считать корни каждый вызов dist()
	cache = {(x,y) : round(math.sqrt(x**2 + y**2)) for x in range(-100,100) for y in range(-100,100)}

	def __init__(self, x, y):
		self.x = x
		self.y = y

	def __getitem__(self, index):
		return (self.x, self.y)[index]

	def __add__(self, other):
		return Position(self.x + other.x, self.y + other.y)

	def __sub__(self, other):
		return Position(self.x - other.x, self.y - other.y)

	def __eq__(self, other):
		return (self.x == other.x and self.y == other.y) if other else False

	def __str__(self):
		return "(" + str(self.x) + "," + str(self.y) + ")"

	def __hash__(self):
		return (self.x, self.y).__hash__()

	def manhattan(self, other):
		return abs(self.x - other.x) + abs(self.y - other.y)

	def dist(self, other):
		d = (self.x - other.x, self.y - other.y)
		if d not in Position.cache:
			Position.cache[d] = round(math.hypot(self.x - other.x, self.y - other.y))
		return Position.cache[d]

	def touch(self, other):
		return self.manhattan(other) <= 1

class PredicateDict(object):

	"""
	Отдаст только те значения, для которых истинен предикат от 
	переданного с ключом аргумента
	"""

	def __init__(self):
		self.data = {}

	def set(self, key, value, predicate = lambda x : True):
		self.data[key] = (predicate, value)

	def get(self, key, arg):
		entry = self.data[key]
		if entry[0](arg):
			return entry[1]
		else:
			raise KeyError

	def delete(self, key):
		self.data.pop(key)

	def keys(self, arg):
		return [key for key in self.data if self.data[key][0](arg)]

	def values(self, arg):
		return [self.data[key] for key in self.data if self.data[key][0](arg)]

class Rational(object):

	"""
	Используется в Creature._shadowcast из-за проблем со сравнением флоатов
	"""

	def __init__(self, numerator = 0, denominator = 1):
		self.numerator = numerator
		self.denominator = denominator

	def __eq__(self, other):
		return self.numerator * other.denominator == other.numerator * self.denominator

	def __lt__(self, other):
		return self.numerator * other.denominator <  other.numerator * self.denominator

	def __le__(self, other):
		return self.numerator * other.denominator <= other.numerator * self.denominator

class RealLine(object):

	"""
	Линия с отрезками на ней. Используется в Creature_.shadowcast.
	"""

	def __init__(self):
		self.lines = []

	def add(self, line):
		insert_to_sorted(self.lines, line, lambda x, y: x[0] < y[0])

	def append(self, line):
		"""
		В Creature._shadowcast начало каждого следующего отрезка не может быть меньше предыдущего, 
		поэтому тут можно чуть сэкономить и не запариваться с поиском нужной позиции в списке.
		"""
		self.lines.append(line)

	def merge(self, other):

		i, j = 0, 0
		while i < len(self.lines) and j < len(other.lines):
			if other.lines[j] < self.lines[i]:
				self.lines.insert(i, other.lines[j])
				j += 1
			else:
				i += 1
		while j < len(other.lines):
			self.lines.append(other.lines[j])
			j += 1

		self.unite()

	def unite(self):
		if not self.lines:
			return
		i = 1
		line = self.lines[0]
		while i < len(self.lines):
			if line[1] >= self.lines[i][0]:
				line[1] = max(line[1], self.lines[i][1])
				self.lines.pop(i)
			else:
				line = self.lines[i]
				i += 1

	def contains(self, line):
		for interval in self.lines:
			if interval[0] <= line[0] and \
			   interval[1] >= line[1]:
				return True
		return False

def translate(start, point, n):

	"""
	Переводим Position из локальной системы координат в глобальную.
	"""

	if n == 0:
		return Position(start.x + point.y, start.y - point.x)
	if n == 1:
		return Position(start.x + point.x, start.y + point.y)
	if n == 2:
		return Position(start.x - point.y, start.y + point.x)
	if n == 3:
		return Position(start.x - point.x, start.y - point.y)

def process_direction(room, args):

	"""
	В методы, принимающие направление, может прийти как строка, так и Position.
	Здесь мы обрабатываем оба этих случая и возвращаем Position
	"""

	result = None

	if not args:
		return None

	direction = args[0]

	if type(direction) == str:
		direction = direction.lower()
		if direction in room.DIRECTIONS:
			result = room.DIRECTIONS[direction]
	elif type(direction) == Position and direction in room.DIR_LIST:
		result = direction

	return result

def dice(n = 1, sides = 20):
	result = 0
	for i in range(n):
		result += random.randint(1, sides)
	return result

def update(container, key, value):
	if value:
		container[key] = value
	elif key in container:
		container.pop(key)

def get_item_safe(container, key, fail_value):
	if key in container:
		return container[key]
	else:
		return fail_value

def retrieve_item(container, index):
	if not container:
		return None
	if index >= 0 and index < lend(container):
		return container.pop(index)
	else:
		return container.pop()

def insert_to_sorted(container, value, cmp = lambda x, y : x < y):
	if len(container) == 0:
		container.append(value)
		return

	index = 0
	while index < len(container) and cmp(container[index], value):
		index += 1

	if index < len(container):
		container.insert(index, value)
	else:
		container.append(value)