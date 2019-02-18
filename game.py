#coding -*- utf-8 -*-

from game_core import *

"""
Тут пока бардак, файл по-быстрому состряпан для обеспечения
минимальной играбельности.
"""

OBJ_TYPES = {"COFFEE": CoffeeMachine,
             "GAME": GameMachine,
             "DOOR": Door,
             "BUG": Bug,
             "OWNER": Owner,
             "ITEM": Item,
             "FOO": ItemFooBar,
             "BOOK": ItemBook,
             "GRENADE": ItemTestGrenade}

def load_objects(room, filename):
	f = open(filename, "r", encoding="utf-8")
	for line in f:
		name, x, y, *args = line[:-1].split(";")
		OBJ_TYPES[name](*args)._place(room, Position(int(x),int(y)))

MAPS_FOLDER = "./maps/"
MAP_NAMES = ("1.txt", "2.txt", "test_area.txt")
OBJECTS = ("1_objects.txt",)

rooms = [Room(MAPS_FOLDER + name) for name in MAP_NAMES]

for i in range(len(rooms) - 1):
	rooms[i].next_room = rooms[i+1]
	rooms[i+1].prev_room = rooms[i]

current_room = rooms[0]

for i in range(len(OBJECTS)):
	load_objects(rooms[i], MAPS_FOLDER + OBJECTS[i])

name = input("Как приключенца назовём?\n")
hero = Adventurer(name, level = 0)
hero._place(current_room, current_room.entry_point)
hero.__log__("Введи команду \"help\" (без кавычек) для получения справки по игре")

while True:
	observer = False
	for room in rooms:
		observer = room.tick() or observer

	if not observer:
		exit("Здесь больше не осталось игроков. Зачем существовать Вселенной, если некому её увидеть?")