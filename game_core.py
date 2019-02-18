# -*- coding: utf-8 -*-

from game_ai import *
from game_utils import *
from game_texts import *



class GameObject(object):

	"""
	Базовый класс, от которого наследуют все объекты, находяшиеся на карте
	"""

	def __init__(self, name = "Object", opaque = False, passable = False, skin = " "):
		self.name = name
		self.opaque = opaque
		self.passable = passable
		self.skin = skin
		self.room = None
		self.position = None

	def _tick(self):
		"""
		Используется у классов, которым нужно считать ходы
		"""
		return

	def _get_position(self):
		return self.position

	def _get_room(self):
		return self.room

	def __log__(self, message, global_log = False):
		if self._get_room():
			self._get_room().log.append((self._get_position(), global_log, message))

class Creature(GameObject):

	"""
	Класс, от которого наследуют все существа,
	как игрок, так и монстры
	"""

	text_damaged = "повреждён"
	text_dead = "уничтожен"

	def __init__(self, name, level = 0, opaque = False, passable = False, skin = "C",\
		         soul = Soul, control = dumb_agent):
		GameObject.__init__(self, opaque = opaque, passable = passable, skin = skin)
		#характеристики и фракция
		self.name = name
		self.health_max = 10
		self.health = 10
		self.health_per_level = 3
		self.intellect = 2
		self.cunning = 2
		self.power_max = 2
		self.power = 2
		self.level = 0
		self.kill_count = 2**int(level)
		self.faction = "neutral"
		self.inventory = CreatureInventory(self)
		self.summoned_creatures = set([])

		#природные показатели
		self.damage_dice = (1,4)
		self.view_dist = 6

		#положение в пространстве
		self.room = None
		self.position = Position(-1,-1)
		self.shadowed_tiles = set([])
		self.visible_tiles = set([])

		#дед или андед :)
		self.dead = False
		self.undead = False

		#Искусственный Идиот
		self.soul = soul(control = control)
		self.interface = PredicateDict()
		self.interface.set("move", self.move)
		self.interface.set("wait", self.wait)
		self.interface.set("attack", self.attack)
		self.interface.set("drop", self.drop)
		self.interface.set("take", self.take)
		self.interface.set("item", self.item)
		self.interface.set("use", self.use)
		self.interface.set("enter", self.enter)
		self.interface.set("say", self.say)

		#это для замера производительности
		self.showtime = False
		self.time = 0

	#методы без нижнего подчёркивания доступны игроку
	#напрямую через текстовые команды
	def attack(self, *args):
		"""[west|north|east|south] - атаковать в заданном направлении"""
		direction = process_direction(self.room, args)

		if direction:
			position = self.position + direction
		else:
			self.__log__(self.name + ": непонятное направление")
			return

		atk_stats = self.__atk__()
		target = self.room.unit_in_pos(position)
		if target:
			target._receive_attack(*atk_stats);
		else:
			self.__log__(self.name + ": тут никого нет!")

	def drop(self, *args, silent = False):
		"""[номер] - бросить предмет на пол"""
		index = args[0] if args and type(args[0]) == int else -1
		item = self._shift_item(self.inventory, index, self.room.items_in_pos(self.position))
		if silent:
			return
		if item:
			self.__log__(self.name + " выкидывает предмет: " + item.name)
		else:
			self.__log__(self.name + ": нечего выкидывать")

	def enter(self, *args):
		"""- войти в переход на другую карту"""
		if self.room[self.position] == ">" and self.room.next_room:
			self._place(self.room.next_room, self.room.next_room.entry_point)
		elif self.room[self.position] == "<" and self.room.prev_room:
			self._place(self.room.prev_room, self.room.prev_room.leave_point)
		else:
			self.__log__(self.name + ": тут ничего нет.")

	def item(self, *args):
		"""[номер] - использовать предмет из инвентаря"""
		index = args[0] if args and type(args[0]) == int else -1
		if index >= 0 and index < len(self.inventory):
			self.inventory[index]._use(self)
		else:
			self.__log__(self.name + ": такого предмета нет")

	def move(self, *args):
		"""[west|north|east|south] - двигаться в заданном направлении"""
		direction = process_direction(self.room, args)
		if direction:
			position = self.position + direction
			if self.room.passable(position):
				self.room.move(self, position)
			else:
				self.__log__(self.name + " не может идти туда")
		else:
			self.__log__(self.name + ": непонятное направление")

	def say(self, *args):
		"""[text] - сказать что-нибудь"""
		self.__log__(self.name + ": \"" + " ".join(args) + "\"")

	def take(self, *args):
		"""[номер] - поднять предмет с пола"""
		index = args[0] if args and type(args[0]) == int else -1
		item = self._shift_item(self.room.items_in_pos(self.position), index, self.inventory)
		if item:
			self.__log__(self.name + " подбирает предмет: " + item.name)
		else:
			self.__log__(self.name + ": здесь ничего нет")

	def use(self, *args):
		"""[west|north|east|south] - использовать объект"""
		direction = process_direction(self.room, args)
		if direction:
			position = self.position + direction
			obj = self.room.object_in_pos(position)
			if obj:
				obj._use(self)
			else:
				self.__log__(self.name + ": тут ничего нет")
		else:
			self.__log__(self.name + ": непонятное направление")

	def wait(self, *args):
		"""- пропустить ход"""
		self.__log__(self.name + " стоит на месте.")

	#методы с нижним подчёркиванием не доступны игроку
	def _act(self):
		"""
		Сделать свой ход. Вызывается при каждом проходе по списку юнитов.
		Возвращает True, если контролируется игроком, это нужно для определения геймовера.
		"""
		is_player = False
		if not self.dead:
			self._observe()

			is_player = self.soul.control(self)

			while self.kill_count >= 2**(self.level + 1):
				skills = set(self.interface.keys(self))
				if not is_player:
					self._level_up()
				else:
					self._level_up_by_player()
				for skill in set(self.interface.keys(self)) - skills:
					self.__log__(self.name + " получает новую способность: " + skill + "!")
			self._tick()

		return is_player

	def _can_see(self, target):
		return target in self.visible_tiles

	def _can_summon(self):
		return False

	def _get_inventory(self):
		return self.inventory.copy()

	def _get_mdist(self, pos):
		return self.position.manhattan(pos)

	def _get_visible_units(self):
		result = []
		for pos in self.visible_tiles:
			unit = self.room.unit_in_pos(pos)
			if unit:
				result.append(unit)
		return result

	def _get_vision(self):
		"""
		Получаем строку с картой так, как видит и помнит её юнит
		"""
		result = ""
		memory = self.soul.recall(self.room)

		for y in range(self.room.height):
			for x in range(self.room.width):
				pos = Position(x,y)

				ch = " "

				if pos in self.visible_tiles:
					unit = self.room.unit_in_pos(pos)
					obj = self.room.object_in_pos(pos)
					items = self.room.items_in_pos(pos)
					item = items[-1] if items else None

					if unit:
						ch = unit.skin
					elif obj:
						ch = obj.skin
					elif item:
						ch = item.skin
					else:
						ch = self.room[pos]

				elif pos in memory.walls:
					ch = self.room[pos]
				elif pos in memory.units:
					ch = memory.units[pos].skin
				elif pos in memory.objects:
					ch = memory.objects[pos].skin
				result += ch

			if y+1 < self.room.height:
				result += "\n"

		return result

	def _level_up(self, i = None):
		"""
		Общий метод левелапа. Мобы качают случайную характеристику.
		"""
		self.level += 1
		self.health_max += self.health_per_level
		self.health += self.health_per_level

		if i == None:
			i = random.randint(0,3)

		if i < 0 or i > 3:
			return False

		if i == 0:
			self.health_max += 2
			self.health += 2
		if i == 1:
			self.intellect += 1
		if i == 2:
			self.cunning += 1
		if i == 3:
			self.power_max += 1
			self.power += 1

		return True

	def _level_up_by_player(self):
		"""
		Немного костыльный метод левелапа для игрока.
		"""
		while True:
			print("Левелап! Ты теперь " + str(self.level + 1) + " уровня! Что будем качать?")
			print("0 - Здоровье (психическое), 1 - Интеллект, 2 - Хитрость, 3 - Энергия: ", end="")
			choice = input()

			if choice.isdigit():
				i = int(choice)
				if self._level_up(i):
					break

			print("Чёто не то")

	def _observe(self):
		"""
		Получаем видимые/невидимые тайлы и обновляем память.
		Вызывается из _act() каждый ход.
		"""
		result = self._shadowcast()
		self.soul.memorize(self.room, result)
		self.visible_tiles, self.shadowed_tiles = result
		return result

	def _place(self, new_room, position):
		"""
		Размещаем юнита на новой карте. Используется при создании юнита и при
		переходе на новую карту.
		"""
		if self.room:
			self.room.remove(self)

		if not new_room.passable(position):
			unit = new_room.unit_in_pos(position)
			if unit:
				unit.__die__(self) #teleport frag! :)
			else:
				raise IndexError

		self.room = new_room
		self.position = position
		self.room.add(self)
		self._observe()

	def _receive_attack(self, other, attack_roll, damage_roll, crit):
		defence = 10 + round(self.cunning / 2)
		message = "Атака %s vs. %s (%s vs. %s): " % (other.name, self.name, attack_roll, defence)

		if (defence < attack_roll) or crit:
			self.health -= damage_roll
			message += ("%s %s на %s ПЗ!" % (self.name, self.text_damaged, damage_roll))
		else:
			message += "промах!"
		self.__log__(message)

		if self.health <= 0:
				self.__die__(other)

	def _remove_summon(self, unit):
		self.summoned_creatures.remove(unit)

	def _restore_health(self, health):
		self.health = min(self.health_max, self.health + health)

	def _restore_power(self, power):
		self.power = min(self.power_max, self.power + power)

	def _see_logs(self):
		while self.room.log:
			message = self.room.log.pop(0)
			if self._can_see(message[0]) or message[1]:
				print(message[2])

	def _shadowcast(self):
		"""
		Разделяем тайлы на видимые и затенённые. Основная идея скоммунизжена отсюда:
		http://journal.stuffwithstuff.com/2015/09/07/what-the-hero-sees/
		"""
		def tile_line(row, col):
			n = col + row
			d = 2 * row + 1
			return [Rational(n, d), Rational(n + 1, d)]

		result = (set([self.position]), set([]))
		start = Position(0,0)
		point = Position(0,0)

		max_up = min(self.position.y, self.view_dist)
		max_down = min(self.room.height - self.position.y - 1, self.view_dist)
		max_left = min(self.position.x, self.view_dist)
		max_right = min(self.room.width - self.position.x - 1, self.view_dist)

		bounds = LoopedTuple((max_up, max_right, max_down, max_left))

		for n in range(4):

			shadowline = RealLine()
			for point.x in range(1, min(bounds[n], self.view_dist) + 1):
				current_shadowline = RealLine()
				for point.y in range(max(-bounds[n+3], -point.x), min(bounds[n+1] + 1 ,point.x + 1)):

					global_pos = translate(self.position, point, n)

					if (start.dist(point) > self.view_dist):
						continue

					line = tile_line(point.x, point.y)
					shadowed = shadowline.contains(line)
					opaque = self.room.opaque(global_pos)

					result[shadowed].add(global_pos)

					if opaque:
						current_shadowline.append(line)

				shadowline.merge(current_shadowline)

		return result

	def _shift_item(self, from_container, index, to_container):

		if from_container:
			if not (index < len(from_container) and index >= -len(from_container)):
				index = -1
			item = from_container[index]
			item.shift(to_container)
			return item
		else:
			return None

	def _stats(self):
		"""
		Используется для отображения статов на экране
		"""
		return self.level, self.health, self.health_max, \
		       self.intellect, self.cunning, self.power, self.power_max,\
		       self.kill_count, self.position.x, self.position.y

	def _summon(self, direction, unit_type, level):
		"""
		Общий метод для вызова существ.
		"""
		if not self._can_summon():
			self.__log__(self.name + ": нельзя вызвать больше существ")
			return

		if direction:
			summon_pos = self.position + direction
			if self.room.passable(summon_pos):
				summoned = unit_type(self, level = level)
				summoned._place(self.room, summon_pos)
				self.summoned_creatures.add(summoned)
				return summoned
			else:
				return None
		else:
			self.__log__(self.name + ": непонятное направление.")
			return None

	def _tick(self):
		for item in self.inventory:
			item._tick()

	def __atk__(self):
		attack_roll = dice(1,20)
		crit = False
		attack = attack_roll + round(self.cunning / 2)
		if attack_roll < 20:
			damage = dice(self.damage_dice[0], self.damage_dice[1])
		else:
			self.__log__(self.name + ": крит!")
			crit = True
			damage = dice(self.damage_dice[0]*2, self.damage_dice[1])
		damage += round(self.intellect / 2) * (1 + crit)
		return (self, attack, damage, crit)

	def __die__(self, killer = None):
		self.__log__(self.name + " " + self.text_dead + "!")
		if self.soul.control == player_agent:
			self._see_logs()
		self.dead = True
		self.health = 0
		while self.inventory:
			self.drop(silent = True)
		self.room.remove(self)
		if killer:
			killer.__killed__(self)

	def __killed__(self, victim):
		if not victim.undead:
			self.kill_count += 1

class Adventurer(Creature):

	"""
	Наш тестер-приключенец. Такой же юнит, как и все остальные, только
	с присобаченным к нему контроллером и парой уникальных способностей.
	"""

	text_damaged = "задолбан"
	text_dead = "слишком устал"

	def __init__(self, name, level = 0, skin = "@"):
		self.dbg = 0
		Creature.__init__(self, name, level = level, skin = skin, \
			              soul = HumanSoul, control = player_agent)
		self.faction = "testers"
		self.interface.set("wait", self.wait)
		self.interface.set("smoke", self.smoke)
		self.interface.set("auto", self.auto, lambda x : x.level >= 3) # автотест даём только с 3-го уровня

	def wait(self, *args):
		"""- тактическая прокрастинация. Пропускает ход."""
		self.__log__(self.name + " прокрастинирует")

	def smoke(self, *args):
		"""[west|north|east|south] - разместить заслоняющую обзор стену из трёх смоук-тестов. Стоит 1 энергии."""
		if self.power < 1:
			self.__log__(self.name + ": недостаточно энергии")
			return

		direction = process_direction(self.room, args)
		if direction:
			self.power -= 1
			n = ((0,-1),(1,0),(0,1),(-1,0)).index((direction.x, direction.y))
			p1 = self.position + direction
			p2 = Position(*translate(self.position, Position(1,-1), n))
			p3 = Position(*translate(self.position, Position(1, 1), n))

			lifetime = 3 + round(self.level / 3)
			for pos in (p1,p2,p3):
				smoke_cloud = Smoke(lifetime = lifetime)
				smoke_cloud._place(self.room, pos)
		else:
			self.__log__(self.name + ": непонятное направление")

	def auto(self, *args):
		"""[west|north|east|south] - разместить на карте турель-автотест. Стоит 3 энергии."""

		if self.power < 3:
			self.__log__(self.name + ": недостаточно энергии")
			return
		else:
			self.power -= 3

		direction = process_direction(self.room, args)
		unit = self._summon(direction, AutoTest, level = self.level)
		if unit:
			self.__log__(self.name + " запускает Автотест!")
		else:
			self.say("Я не могу запустить Автотест здесь")

	def _can_summon(self):
		return len(self.summoned_creatures) < 1

class AutoTest(Creature):

	"""
	Типа турель. Стоит на месте и атакует врагов очередями
	по вертикали или горизонтали.
	"""

	def __init__(self, master, name = "Автотест", level = 0, \
		         skin = "^", soul = BugSoul, control = standing_agent):
		Creature.__init__(self, name, level = level, soul = soul, control = control, skin = skin)
		self.master = master
		self.lifetime = 2 + round(master.level / 3)
		self.intellect = master.intellect
		self.cunning = master.cunning
		self.power = 0
		self.power_max = 0
		self.undead = True
		self.faction = "testers"
		self.interface.set("attack", self.attack)
		self.interface.set("wait", self.wait)

	def attack(self, *args):
		"""[west|north|east|south] - очередь из трёх автотестов, стреляет на расстояние до четырёх тайлов."""
		direction = process_direction(self.room, args)
		dist = 4
		attacks = 3
		if direction:
			self.__log__("Тра-та-та! " + self.name + " тестирует очередью!")
			for a in range(attacks):
				position = Position(self.position.x, self.position.y)
				for x in range(dist):
					position += direction
					unit = self.room.unit_in_pos(position)
					if unit:
						unit._receive_attack(*self.master.__atk__())
						break

	def wait(self):
		return

	def _level_up(self):
		"""
		Автотест и так уже обладает статами хозяина, качаем только здоровье.
		"""
		self.level += 1
		self.health += 2
		self.health_max += 2

	def _tick(self):
		Creature._tick(self)
		self.lifetime -= 1
		if self.lifetime <= 0:
			self.__die__()

	def __killed__(self, victim):
		self.master.__killed__(victim)

	def __die__(self, killer = None):
		Creature.__die__(self, killer)
		self.master._remove_summon(self)

class Bug(Creature):

	"""
	Это бажик. Бегает и кусается. Сам генерит себе имена.
	Не имеет памяти и забудет об игроке, если потеряет его из виду.
	"""

	prefixes = ("DEV-", "GAME-", "GAMEADM-")
	text_damaged = "протестирован"
	text_dead = "закрыт"
	counter = 1337

	def __init__(self, name = "", level = 0, skin = "б", soul = BugSoul, control = dumb_agent):
		if name:
			Creature.__init__(self, name, level, skin = skin, soul = soul, control = control)
		else:
			Creature.__init__(self, random.choice(Bug.prefixes) + str(Bug.counter), \
				              level, skin = skin)
		self.id = Bug.counter
		Bug.counter += 1
		self.faction = "bugs"
		self.view_dist = 5
		self.health_max = 5
		self.health = 5
		self.health_per_level = 3

	def __hash__(self):
		return self.id.__hash__()

class OwnedBug(Bug):

	"""
	Тоже бажик, но вызванный. За него не дают экспы.
	Самозакрывается, если победить его хозяина.
	"""

	def __init__(self, master, name = "", level = 0, skin = "б", \
		         soul = BugSoul, control = summoned_agent):
		Bug.__init__(self, name, level = level, soul = soul, control = control, skin = skin)
		self.master = master
		self.undead = True

	def __die__(self, killer = None):
		Bug.__die__(self, killer)
		self.master._remove_summon(self)

class Owner(Creature):

	"""
	Заказчик - призыватель багов.
	Помнит карту и позиции юнитов.
	"""

	text_damaged = "задобрен"
	text_dead = "довольно кивает и уходит"

	def __init__(self, name = "Заказчик", level = 0, skin = "З"):
		Creature.__init__(self, name = name, level = level, skin = skin, \
			              soul = HumanSoul, control = owner_agent)
		self.faction = "bugs"
		self.interface.set("summon", self.summon)

	def summon(self, *args):
		"""
		[west|north|east|south] - открыть новый баг
		"""
		direction = process_direction(self.room, args)
		unit = self._summon(direction, OwnedBug, level = round(self.level / 2))
		if unit:
			self.say(random.choice(TALK_SUMMON))
			self.__log__(self.name + " открывает " + unit.name + "!")
		else:
			self.say("Я не могу открыть баг здесь")

	def _can_summon(self):
		return len(self.summoned_creatures) < 1 + self.level/4

	def __die__(self, killer = None):
		Creature.__die__(self, killer)
		for bug in self.summoned_creatures.copy():
			bug.__die__(killer)



class Item(GameObject):

	"""
	Базовый класс для предметов. Можно поднять, можно выкинуть.
	"""

	def __init__(self, name = "", skin = "["):
		if name:
			self.name = name
		self.skin = skin
		self.container = None

	def _get_position(self):
		if self.container:
			return self.container._get_position()
		else:
			return None

	def _get_room(self):
		if self.container:
			return self.container._get_room()
		else:
			return None

	def shift(self, to_container, index = None):
		i = index if index != None else self.container.index(self)
		to_container.append(self.container.pop(i))
		self.container = to_container

	def _place(self, room, position):
		if not room.wall_in_pos(position):
			self.container = room.items_in_pos(position)
			self.container.append(self)
		else:
			self.__die__()

	def _use(self, user):
		user.__log__(user.name + " и " + self.name + " смотрят друг на друга")

	def __die__(self):
		if self.container:
			self.container.remove(self)
			self.container = None

class ItemFooBar(Item):

	def __init__(self, name = "Батончик \"Foo\"", skin = "'"):
		Item.__init__(self, name, skin)

	def _use(self, user):
		user.__log__(user.name + " ест батончик \"Foo\"")
		user._restore_power(1)
		self.__die__()

class ItemBook(Item):

	def __init__(self, name = "Книга", skin = "\""):
		Item.__init__(self, name, skin)

	def _use(self, user):
		user.__log__(user.name + " читает книгу")
		user._restore_health(5)
		self.__die__()

class ItemTestGrenade(Item):

	name = "Коробка"
	exploded = False

	def __init__(self, name = "", skin = "!"):
		Item.__init__(self, name, skin)
		self.lifetime = None
		self.activator = None

	def _use(self, user):
		if not self.lifetime:
			user.__log__(user.name + " открывает коробку. Это же безопасно, верно?..")
			self.__log__("Содержимое коробки тикает и мигает красной лампочкой")
			self.activator = user
			self.lifetime = 6
			if not ItemTestGrenade.exploded:
				user.say("Я знал, что коробки - зло!")
				ItemTestGrenade.name = "Бомба?"
			user.drop(user._get_inventory().index(self))
		else:
			user.__log__(user.name + ": оно тикает")

	def _tick(self):
		if not self.lifetime:
			return

		self.lifetime -= 1
		self.name = ItemTestGrenade.name + ": " + str(self.lifetime)

		if self.lifetime <= 0:
			self.__log__("БАБАХ!!!", global_log = True)
			if not ItemTestGrenade.exploded:
				ItemTestGrenade.exploded = True
				self.activator.say("Вот это бомбануло")
			ItemTestGrenade.name = "Бомба"

			for pos in (Position(-1,-1), Position(-1,0), Position(-1,1),\
				        Position( 0,-1), Position( 0,0), Position( 0,1),
				        Position( 1,-1), Position( 1,0), Position( 1,1)):

				unit = self._get_room().unit_in_pos(self._get_position() + pos)
				if unit:
					unit._receive_attack(self.activator, 20, dice(4,10), True)

				#пока что закомментировано, чтобы не взорвать запертую дверь
				"""
				obj = self._get_room().object_in_pos(self._get_position() + pos)
				if obj:
					obj.__die__()
				"""

				smoke_cloud = Smoke(lifetime = 3)
				smoke_cloud._place(self._get_room(), self._get_position() + pos)

			self.__die__()
		else:
			self.__log__(self.name + "...")



class Placeable(GameObject):

	"""
	Класс, от которого наследуют неживые объекты типа дверей и кофе-машин
	"""

	def __init__(self, name = "", opaque = True, passable = False, skin = "0"):
		GameObject.__init__(self, name = name, opaque = opaque, passable = passable, skin = skin)
		self.room = None
		self.position = None
		self.is_door = False

	def _place(self, room, position):
		if (room.passable(position) or (self.passable and room.unit_in_pos(position))) and \
		    not room.object_in_pos(position):
			room.place_object(self, position)
			self.room = room
			self.position = position
		else:
			self.__die__()

	def _use(self, user):
		user.__log__(user.name + ": это нельзя использовать")

	def __die__(self):
		if self.room:
			self.room.remove_object(self)
			self.position = None
			self.room = None

class Door(Placeable):

	def __init__(self, name = "Дверь", key = None, opaque = True, passable = False, skin = "+"):
		Placeable.__init__(self, opaque = opaque, passable = passable, skin = skin)
		self.name = name
		self.closed = True
		self.is_door = True
		self.key = key

	def close(self, user):
		if not self.room.unit_in_pos(self.position):
			self.skin = "+"
			self.passable = False
			self.opaque = True
			self.closed = True
		else:
			user.__log__(user.name + " не может закрыть дверь прямо сейчас")

	def open(self, user):
		if self.key:
			#проверять ключи по name костыльненько, но это временно
			users_keys = [k for k in user.inventory if k.name == self.key]
			if users_keys:
				user.__log__(self.key + " подходит к двери")
				self.key = None
			else:
				user.__log__(self.name + " закрыта на ключ")
				return
		self.skin = "/"
		self.passable = True
		self.opaque = False
		self.closed = False

	def _use(self, user):
		if self.closed:
			self.open(user)
		else:
			self.close(user)

class Smoke(Placeable):

	"""
	Блок дыма. Загораживает обзор. Существует ограниченное время.
	"""

	def __init__(self, opaque = True, skin = "*", lifetime = 4):
		Placeable.__init__(self, opaque = opaque, passable = True, skin = skin)
		self.lifetime = lifetime
		self.count = 0

	def _tick(self):
		self.count += 1
		if self.count >= self.lifetime:
			self.__die__()

class CoffeeMachine(Placeable):

	"""
	Кофе-машина. Восстанавливает энергию.
	"""

	def __init__(self, opaque = True, passable = False, skin = "Ф"):
		Placeable.__init__(self, opaque = opaque, passable = passable, skin = skin)
		self.cups = 3
		self.name = "Кофейный автомат"

	def _use(self, user):
		if self.cups > 0:
			self.cups -= 1
			user.power = user.power_max
			user.__log__(user.name + ": бодрячок!")
			self.__log__(self.name + ": осталось %s кофе" % (self.cups))
		else:
			self.__log__(self.name + ": кофе больше нет :(")

class GameMachine(Placeable):

	"""
	Игровая машина. Восстанавливает здоровье.
	"""

	def __init__(self, opaque = True, passable = False, skin = "0"):
		Placeable.__init__(self, opaque = opaque, passable = passable, skin = skin)
		self.cups = 3
		self.name = "Игровая станция"

	def _use(self, user):
		if self.cups > 0:
			self.cups -= 1
			user.health = user.health_max
			user.say(random.choice(TALK_GAMES))
			self.__log__(self.name + ": осталось %s игры" % (self.cups))
		else:
			self.__log__(self.name + ": нет игор :(")



class Inventory(object):

	"""
	Базовый класс для инвентаря. По сути просто оболочка над списком.
	"""

	def __init__(self):
		self.data = []

	def __getitem__(self, index):
		return self.data[index]

	def __setitem__(self, index, value):
		self.data[index] = value

	def __len__(self):
		return len(self.data)

	def __bool__(self):
		return bool(self.data)

	def append(self, value):
		self.data.append(value)

	def index(self, value):
		return self.data.index(value)

	def pop(self, index = None):
		return self.data.pop(index) if index != None else self.data.pop()

	def remove(self, value):
		self.data.remove(value)

class StaticInventory(Inventory):

	"""
	Недвижимый инвентарь. Используется для хранения итемов на полу.
	Позиция задаётся раз и навсегда.
	"""

	def __init__(self, room, position):
		Inventory.__init__(self)
		self.room = room
		self.position = position

	def copy(self):
		cp = StaticInventory(self.room, self.position)
		cp.data = self.data.copy()
		return cp

	def _get_position(self):
		return self.position

	def _get_room(self):
		return self.room

class CreatureInventory(Inventory):

	"""
	Инвентарь существа. В качестве позиции использует position хозяина.
	"""

	def __init__(self, owner):
		Inventory.__init__(self)
		self.owner = owner

	def copy(self):
		cp = CreatureInventory(self.owner)
		cp.data = self.data.copy()
		return cp

	def _get_position(self):
		return self.owner.position

	def _get_room(self):
		return self.owner.room

class Room(object):

	"""
	Класс с реализацией игровой карты
	"""

	DIRECTIONS = {"north": Position(0,-1), \
                  "south": Position(0,1), \
                  "west": Position(-1,0), \
                  "east": Position(1,0)}
	DIR_LIST = list(DIRECTIONS.values())

	count = 0

	def __init__(self, input_file = "", width = 50, height = 20):
		self.id = Room.count
		Room.count += 1
		self.map = []
		self.items = {}
		self.unit_queue = [] #нужен для сохранения очерёдности между ходами
		self.log = [] #тут логи, которые будем показывать каждый ход
		self.entry_point = None #позиция входа на карту
		self.leave_point = None #позиция выхода с карты
		self.prev_room = None
		self.next_room = None
		if input_file:
			f = open(input_file, "r")
			params = f.readline().split(" ")
			self.width = int(params[0])
			self.entry_point = Position(int(params[1]), int(params[2]))
			if len(params) >= 5:
				self.leave_point = Position(int(params[3]), int(params[4]))
			self.height = 0
			for i in range(self.width):
				self.map.append([])
			for line in f:
				self.height += 1
				for xpos in range(self.width):
					self.map[xpos].append(line[xpos])
			f.close()
		else:
			self.width = width
			self.height = height
			self.entry_point = Position(1,1)
			for x in range(self.width):	
				self.map.append([])
				for y in range(self.height):
					self.map[-1].append(random.choice(("#", ".")))

		self.units = [[None for y in range(self.height)] for x in range(self.width)]
		self.objects = [[None for y in range(self.height)] for x in range(self.width)]

	def __getitem__(self, pos):
		return self.map[pos.x][pos.y]

	def __setitem__(self, pos, value):
		self.map[pos.x][pos.y] = value

	def __str__(self):
		result = ""
		for y in range(self.height):
			for x in range(self.width):
				pos = Position(x,y)
				unit = self.unit_in_pos(pos)
				obj = self.object_in_pos(pos)
				items = self.items_in_pos(pos)

				if unit:
					result += unit.skin
				elif obj:
					result += obj.skin
				elif items:
					result += items[-1]
				else:
					result += self[pos]

			if y+1 < self.height:
				result += "\n"
		return result

	def get_valid_directions(self, pos):
		result = []
		for dir_ in self.DIR_LIST:
			if self.passable(pos + dir_) and self.in_bounds(pos + dir_):
				result.append(dir_)
		return result

	def add(self, target):
		self.units[target.position.x][target.position.y] = target
		self.unit_queue.append(target)

	def remove(self, target):
		self.units[target.position.x][target.position.y] = None
		self.unit_queue.pop(self.unit_queue.index(target))

	def move(self, target, pos):
		if self.in_bounds(pos) and self.passable(pos):
			self.units[target.position.x][target.position.y] = None
			self.units[pos.x][pos.y] = target
			target.position = pos
		else:
			self.log.append(target.name + " не может идти туда!")

	def passable(self, pos):
		if not self.in_bounds(pos):
			return False
		unit = self.unit_in_pos(pos)
		obj = self.object_in_pos(pos)
		if obj:
			obj = not obj.passable
		return (self[pos] != "#") and not obj and not unit

	def opaque(self, pos):
		opaque_object = False
		obj = self.object_in_pos(pos)
		if obj:
			opaque_object = obj.opaque
		return self[pos] == "#" or opaque_object

	def in_bounds(self, pos):
		return (pos.x >= 0 and pos.x < self.width) and (pos.y >= 0 and pos.y < self.height)

	def wall_in_pos(self, pos):
		return self[pos] == "#"

	def unit_in_pos(self, pos):
		return self.units[pos.x][pos.y]

	def object_in_pos(self, pos):
		return self.objects[pos.x][pos.y]

	def items_in_pos(self, pos):
		if pos not in self.items:
			self.items[pos] = StaticInventory(self, pos)
		return self.items[pos]

	def tick(self):
		human_observer = False
		#объекты могут самоуничтожаться, поэтому тут копируем
		for unit in self.unit_queue.copy():
			human_observer = unit._act() or human_observer

		for x in range(self.width):
			for y in range(self.height):
				if self.objects[x][y]:
					self.objects[x][y]._tick()

		for floor_tile in self.items.values():
			for item in floor_tile.copy():
				item._tick()
		return human_observer

	def place_object(self, obj, position):
		self.objects[position.x][position.y] = obj

	def remove_object(self, obj):
		self.objects[obj.position.x][obj.position.y] = None