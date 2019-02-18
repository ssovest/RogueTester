# -*- coding: utf-8 -*-

import os
import time
from game_utils import *



def search(start, goal, goal_test, eval_func, expand):

	start_node = Node(start)
	fringe = [start_node]
	expanded = set([])

	while fringe:
		fringe.sort(key = eval_func)
		node = fringe.pop(0)
		if node in expanded:
			continue
		if goal_test(node, goal):
			return node
		fringe += expand(node)
		expanded.add(node)

	return start_node

def expand(room, node):

	for dir_ in room.get_valid_directions(node.value):
		pos = node.value + dir_
		node.add_child(Node(pos))
	return node.children

def expand_w_doors(room, node):

	for dir_ in room.DIRECTIONS.values():
		door = room.object_in_pos(node.value + dir_)
		if door:
			door = door.is_door
		if room.passable(node.value + dir_) or door:
			pos = node.value + dir_
			node.add_child(Node(pos))
	return node.children

def search_path(room, start, goal, goal_test = lambda x,y : x.value.manhattan(y) == 1,\
                xp = expand):

	eval_func = lambda x : x.value.manhattan(goal) + x.depth
	node = search(start, goal, goal_test, eval_func, lambda x : xp(room, x))

	result = []
	while node.parent:
		result.append(node.value)
		node = node.parent
	result.reverse()

	return result



def get_target(agent, target_test = lambda x : x.faction == "testers", \
               target_eval = lambda x : x.level):
	"""
	Получаем текущую цель. Предпочтение отдаём видимым целям. Если видимых нет,
	то шерстим память на наличие подходящих кандидатов.
	"""
	target = None
	visible_units = agent._get_visible_units()
	for unit in visible_units:
		if target_test(unit) and (not target or target_eval(unit) > target_eval(target)):
			target = unit

	if not target:
		memory = agent.soul.recall(agent.room).units
		for unit in memory.values():
			if target_test(unit) and (not target or target_eval(unit) > target_eval(target)):
				target = unit

	return target



def lazy_agent(agent):
	"""
	Самый ленивый в мире агент, который будет
	стоять на месте и ничего не делать, 
	даже когда его убивают.
	"""
	agent.wait()
	return False

def standing_agent(agent):
	"""
	Турель - автотест. Не двигается. Из доступных целей выбирает самую высокоуровневую.
	"""

	def target_test(x):
		pos_diff = x.position - agent.position
		return (x.faction == "bugs") and (pos_diff.x == 0 or pos_diff.y == 0) and (agent._get_mdist(x.position) <= 4)

	target = get_target(agent, target_test = target_test, target_eval = lambda x : x.level)

	if target:
		direction = target.position - agent.position

		if direction.x < 0:
			direction.x = -1
		if direction.x > 0:
			direction.x = 1

		if direction.y < 0:
			direction.y = -1
		if direction.y > 0:
			direction.y = 1

		agent.attack(direction)
	else:
		agent.wait()
	return False

def dumb_agent(agent):
	"""
	Туповатый агент. Используется для управления баженьками.
	"""
	target = get_target(agent, target_eval = lambda x : -agent._get_mdist(x.position))

	if target:

		if agent.position.touch(target.position):
			agent.attack(target.position - agent.position)
			return False

		path = search_path(agent.room, agent.position, target.position)

		if path:
			dir_ = path[0] - agent.position
			agent.move(dir_)
		else:
			agent.wait()
	return False

def summoned_agent(agent):
	"""
	Открытый (вызванный) баг. Будет держаться поближе
	к призывателю, если нет цели
	"""
	target = get_target(agent)

	if target:
		if agent.position.touch(target.position):
			agent.attack(target.position - agent.position)
			return False
		path = search_path(agent.room, agent.position, target.position)
	else:
		path = search_path(agent.room, agent.position, agent.master.position,\
                           goal_test = lambda x,y: x.value.manhattan(y) in range(2,3))

	if path:
		dir_ = path[0] - agent.position
		agent.move(dir_)
	else:
		agent.wait()
	return False

def owner_agent(agent):
	"""
	Призыватель багов. Тоже не Эйнштейн, но достаточно умён,
	чтобы открывать двери.
	"""
	target = get_target(agent)

	if target:

		if agent._get_mdist(target.position) <= 5 and agent._can_summon():
			directions = agent.room.get_valid_directions(agent.position)
			if directions:
				dir_ = random.choice(directions)
				agent.summon(dir_)
				return False

		path = search_path(agent.room, agent.position, target.position, \
			goal_test = lambda x,y: x.value.manhattan(y) in range(3,4), \
			xp = expand_w_doors)
		if path:
			dir_ = path[0] - agent.position
			door = agent.room.object_in_pos(path[0])
			if door and door.is_door and door.closed:
				agent.use(dir_)
			else:
				agent.move(dir_)
		elif agent.position.touch(target.position):
			agent.attack(target.position - agent.position)
			return False
		else:
			agent.wait()
	elif agent.room.items_in_pos(agent.position):
		agent.take()
	return False

def player_agent(agent):
	"""
	Агент, контролируемый игроком.
	"""
	def draw_hud(agent):
		os.system('cls' if os.name == 'nt' else 'clear')
		if agent.showtime:
			print(time.time() - agent.time)
		print(agent._get_vision())
		print(agent.name)
		print("Ур. %s, ПЗ: %s/%s, И: %s, Х: %s, Э: %s/%s, xp: %s   [%s, %s]" % agent._stats())
		items = agent.room.items_in_pos(agent.position)
		print((("На полу лежит " + items[-1].name) if items else "") + (" и ещё что-то" if len(items) > 1 else ""))

	draw_hud(agent)

	agent._see_logs()

	valid_commands = [comm for comm in agent.interface.keys(agent)]

	while True:
		valid = True
		query = input().split(" ")
		command, args = query[0].lower(), map(lambda x : int(x) if x.isdigit() else x, query[1:])

		if command in valid_commands:
			agent.interface.get(command, agent)(*args)
			break
		elif command == "items":
			floor_items = agent.room.items_in_pos(agent.position)

			print("Инвентарь:")
			if agent.inventory:
				for i in range(len(agent.inventory)):
					print(str(i) + ": " + agent.inventory[i].name)
			else:
				print("Пусто")

			print()

			print("Пол:")
			if floor_items:
				for i in range(len(floor_items)):
					print(str(i) + ": " + floor_items[i].name)
			else:
				print("Пусто")
		elif command == "exit":
			exit("Пока-пока, %s!" % (agent.name))
		elif command == "help":
			print("Характеристики:\n")
			print("ПЗ - Психическое Здоровье. Если оно 0, то YOU DIED. Лечи играми и книгами.")
			print("И - Интеллект. Им можно давить. Чем он выше, тем сильнее атаки.")
			print("Х - Хитрость. Чем она выше, тем больше попадаешь ты, и тем меньше - по тебе.")
			print("Э - Энергия. Это типа мана. Восстанавливай шоколадками и кофе.\n")
			print("Обозначения:\n")
			print("@ - это ты. Правда красивый?")
			print("б - это бажик. Он тупой, но больно кусается.")
			print("З - это заказчик. Он может призывать новых багов.")
			print("+ - это дверь. Её можно открывать и закрывать.")
			print("0 - это игровая станция. Восстанавливает здоровье (психическое).")
			print("Ф - это кофейный автомат. Восстанавливает энергию")
			print("' - шоколадка, \" - книга, [ - ключ")
			print("# - стена, . - пол, < и > - переходы между картами\n")
			print("Доступные команды:\n")
			for c in valid_commands:
				print(c + " " + getattr(agent, c).__doc__)
			print("exit - выход из игры")
		elif command == "showtime":
			agent.showtime = not agent.showtime
		else:
			print("Некорректная команда")
	agent.time = time.time()
	return True

class Memory(object):
	"""
	Содержит память об определённой комнате.
	Просто оболочка для трёх словарй для лучшей читаемости.
	"""
	def __init__(self):
		self.walls = {}
		self.units = {}
		self.objects = {}

class UnitMemory(object):
	"""
	Воспоминание о каком-то юните. Нужно, чтобы не хранить в памяти самих юнитов и,
	соответственно, не иметь доступа к их текущей позиции, когда их не видно.
	"""
	def __init__(self, unit = None):
		self.position = Position(unit.position.x, unit.position.y) if unit else None
		self.name = unit.name if unit else None
		self.faction = unit.faction if unit else None
		self.skin = unit.skin if unit else None

	def __bool__(self):
		return self.position != None


class Soul(object):
	"""
	Личность нашего существа. Складывается из памяти и управляющего алгоритма.
	Это, в теории, позволяет:
	 - Передавать управление юнитом игроку, заменяя алгоритм. Тогда мы будем
	   использовать память (или её отсутствие) этого юнита.
	 - Использовать крутые способности управления разумом, заменяя личность полностью. Тогда
	   будет использоваться память "контролёра"
	 - Расшаривать память между несколькими юнитами (например, если все они - юниты игрока)
	 - Или, наоборот, управлять несколькими игровыми персами с раздельной памятью
	"""
	def __init__(self, control = dumb_agent):
		self.memory = {}
		self.control = control

	def memorize(self, room, data):
		return

	def recall(self, room):
		return Memory()

class BugSoul(Soul):
	"""
	Личность баженьки. У баженек нету памяти. Чего не видит - того не существует.
	"""
	def __init__(self, control = dumb_agent):
		Soul.__init__(self, control)

class HumanSoul(Soul):
	"""
	Человечья личность. Именно такая у игрока и человеко-мобов.
	Человек - скотина злопамятная, он помнит, где ты был.
	"""
	def __init__(self, control = dumb_agent):
		Soul.__init__(self, control)

	def memorize(self, room, data):
		if room.id not in self.memory:
			self.memory[room.id] = Memory()

		memory = self.memory[room.id]

		for pos in data[0]:
			#update() удалит из словаря ключ, если новое значение квалифицируется как False
			update(memory.walls, pos, room[pos] == "#")
			update(memory.objects, pos, room.object_in_pos(pos))
			update(memory.units, pos, UnitMemory(room.unit_in_pos(pos)))

	def recall(self, room):
		return self.memory[room.id]