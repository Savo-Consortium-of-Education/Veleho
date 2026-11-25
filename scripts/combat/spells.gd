class_name Spells
extends RefCounted
## Spell definitions. "row" = row in projectiles.png (-1 = no sprite).

const ELEMENT_COLORS := {
	"arcane": Color("7fd8ff"),
	"fire": Color("ff7a2a"),
	"ice": Color("a8e4f5"),
	"acid": Color("9be03a"),
	"earth": Color("e0b070"),
	"water": Color("4aa3df"),
	"storm": Color("fff27a"),
	"void": Color("9a5cf0"),
	"dark": Color("c8283c"),
	"": Color("c8d0d8"),
}

const DATA := {
	"spark": {
		"icon": 0, "name": "Kipinä", "row": 0, "speed": 330.0, "damage": 7.0, "mana": 4.0, "life": 0.7,
		"gravity": 0.0, "radius": 2, "spread": 1.5, "light": Color(0.35, 0.75, 1.0), "light_r": 22.0,
		"sound": "shoot_spark", "element": "arcane", "trail": "spark", "rotate": true,
		"desc": "Nopea ja halpa taikasalama.",
	},
	"fireball": {
		"icon": 1, "name": "Tulipallo", "row": 1, "speed": 190.0, "damage": 10.0, "mana": 16.0, "life": 2.0,
		"gravity": 0.12, "radius": 3, "explode_r": 9, "explode_power": 55.0, "fire": true, "ignite": true,
		"light": Color(1.0, 0.5, 0.15), "light_r": 48.0, "sound": "shoot_fire", "element": "fire",
		"trail": "fire", "desc": "Räjähtää liekkeihin ja sytyttää.",
	},
	"orb": {
		"icon": 2, "name": "Pomppuhelmi", "row": 2, "speed": 235.0, "damage": 9.0, "mana": 8.0, "life": 3.2,
		"gravity": 0.55, "radius": 3, "bounces": 6, "light": Color(1.0, 0.4, 0.8), "light_r": 26.0,
		"sound": "shoot_orb", "element": "arcane", "trail": "spark_pink",
		"desc": "Kimpoilee seinistä.",
	},
	"ice": {
		"icon": 3, "name": "Jääpiikki", "row": 3, "speed": 300.0, "damage": 11.0, "mana": 9.0, "life": 1.0,
		"gravity": 0.05, "radius": 2, "pierce": 3, "freeze_r": 3, "chill": true,
		"light": Color(0.5, 0.85, 1.0), "light_r": 24.0, "sound": "shoot_ice", "element": "ice", "rotate": true,
		"trail": "ice", "desc": "Lävistää, jäädyttää veden ja sammuttaa tulen.",
	},
	"acid": {
		"icon": 4, "name": "Happolima", "row": 4, "speed": 175.0, "damage": 6.0, "mana": 11.0, "life": 3.0,
		"gravity": 0.85, "radius": 3, "liquid": Mat.ACID, "liquid_r": 4,
		"light": Color(0.5, 1.0, 0.25), "light_r": 22.0, "sound": "shoot_acid", "element": "acid",
		"trail": "acid", "desc": "Roiskii syövyttävää happoa.",
	},
	"bomb": {
		"icon": 5, "name": "Pommi", "row": 5, "speed": 165.0, "damage": 4.0, "mana": 32.0, "life": 2.2,
		"gravity": 1.0, "radius": 3, "bounces": 99, "bounce_damp": 0.45, "explode_r": 22,
		"explode_power": 100.0, "fire": true, "expire_explode": true, "no_hit_die": true,
		"light": Color(1.0, 0.55, 0.25), "light_r": 18.0, "sound": "shoot_bomb", "element": "fire",
		"trail": "fuse", "desc": "Iso räjähdys sytytinlangan palettua.",
	},
	"missile": {
		"icon": 6, "name": "Taikaohjus", "row": 6, "speed": 120.0, "accel": 280.0, "max_speed": 300.0,
		"damage": 14.0, "mana": 14.0, "life": 3.0, "homing": 7.0, "radius": 3, "explode_r": 5,
		"explode_power": 35.0, "light": Color(0.7, 0.45, 1.0), "light_r": 30.0,
		"sound": "shoot_missile", "element": "arcane", "trail": "spark_violet", "rotate": true,
		"desc": "Hakeutuu kohti vihollisia.",
	},
	"meteor": {
		"icon": 7, "name": "Meteori", "row": 7, "speed": 120.0, "damage": 30.0, "mana": 42.0, "life": 4.0,
		"gravity": 0.45, "radius": 5, "explode_r": 26, "explode_power": 125.0, "fire": true,
		"light": Color(1.0, 0.45, 0.15), "light_r": 64.0, "sound": "shoot_meteor", "element": "fire",
		"trail": "fire", "desc": "Raskas ja tuhoisa kivenjärkäle.",
	},
	"drill": {
		"icon": 8, "name": "Poraterä", "row": 8, "speed": 210.0, "damage": 5.0, "mana": 5.0, "life": 0.42,
		"gravity": 0.0, "radius": 2, "dig_r": 4, "dig_power": 90, "pierce": 2,
		"light": Color(1.0, 0.8, 0.35), "light_r": 20.0, "sound": "shoot_drill", "element": "earth",
		"rotate": true, "trail": "dust", "desc": "Kaivaa tunnelin maastoon.",
	},
	"water": {
		"icon": 9, "name": "Vesipallo", "row": 9, "speed": 215.0, "damage": 3.0, "mana": 6.0, "life": 2.0,
		"gravity": 0.6, "radius": 3, "liquid": Mat.WATER, "liquid_r": 5, "extinguish_r": 9,
		"light": Color(0.35, 0.6, 1.0), "light_r": 22.0, "sound": "shoot_water", "element": "water",
		"trail": "water", "desc": "Luo vettä ja sammuttaa tulen.",
	},
	"quake": {
		"icon": 10, "name": "Järistys", "row": 10, "speed": 150.0, "damage": 10.0, "mana": 24.0, "life": 0.9,
		"gravity": 0.0, "radius": 3, "crumble_r": 16, "crumble_power": 85, "expire_explode": true,
		"light": Color(0.9, 0.6, 0.25), "light_r": 26.0, "sound": "shoot_quake", "element": "earth",
		"trail": "dust", "desc": "Murentaa kallion soraksi.",
	},
	"lightning": {
		"icon": 11, "name": "Salama", "row": -1, "hitscan": true, "range": 230.0, "damage": 20.0, "mana": 20.0,
		"chain": 2, "explode_r": 3, "explode_power": 45.0, "light": Color(0.6, 0.8, 1.0), "light_r": 50.0,
		"sound": "lightning", "element": "storm", "desc": "Välitön ketjuuntuva salama.",
	},
	"enemy_bolt": {
		"name": "Pimeyden ammus", "row": 11, "speed": 140.0, "damage": 10.0, "mana": 0.0, "life": 3.0,
		"gravity": 0.0, "radius": 3, "light": Color(1.0, 0.15, 0.25), "light_r": 28.0,
		"sound": "shoot_enemy", "element": "dark", "rotate": true, "trail": "dark",
		"desc": "",
	},
	"flask": {
		"name": "Pullo", "row": -1, "speed": 230.0, "damage": 5.0, "mana": 0.0, "life": 5.0,
		"gravity": 0.9, "radius": 3, "light": Color(0.6, 0.8, 1.0), "light_r": 10.0,
		"sound": "", "element": "", "desc": "",
	},
	"boss_shard": {
		"name": "Vartijan sirpale", "row": 12, "speed": 165.0, "damage": 11.0, "mana": 0.0, "life": 3.0,
		"gravity": 0.0, "radius": 3, "light": Color(1.0, 0.3, 0.6), "light_r": 24.0,
		"sound": "boss_attack", "element": "dark", "rotate": true, "trail": "dark", "desc": "",
	},
	"enemy_fire": {
		"name": "Liekkisylky", "row": 1, "speed": 150.0, "damage": 8.0, "mana": 0.0, "life": 2.0,
		"gravity": 0.2, "radius": 3, "explode_r": 5, "explode_power": 30.0, "fire": true, "ignite": true,
		"light": Color(1.0, 0.5, 0.15), "light_r": 30.0, "sound": "wisp_flare", "element": "fire",
		"trail": "fire", "desc": "",
	},
}

## Modifiers change the next projectile spell drawn from the wand.
## mod keys: dmg/speed/power multiply, homing/explode take the max,
## bounces/pierce add, draw = extra spells cast at once, accurate = no spread.
const MODIFIERS := {
	"dmg_up": {"icon": 12, "name": "Tehostus", "mana": 8.0, "mod": {"dmg": 1.5}, "desc": "+50 % vahinko seuraavalle loitsulle."},
	"speed_up": {"icon": 13, "name": "Kiihdytys", "mana": 3.0, "mod": {"speed": 1.6}, "desc": "+60 % lentonopeus."},
	"homing": {"icon": 14, "name": "Hakeutuvuus", "mana": 9.0, "mod": {"homing": 6.0}, "desc": "Seuraava loitsu hakeutuu vihollisiin."},
	"bounce": {"icon": 15, "name": "Kimmoisuus", "mana": 4.0, "mod": {"bounces": 4}, "desc": "Seuraava loitsu kimpoaa 4 kertaa."},
	"multi2": {"icon": 16, "name": "Kaksoisloitsu", "mana": 2.0, "mod": {"draw": 1}, "desc": "Loitsii seuraavat 2 loitsua yhtä aikaa."},
	"multi3": {"icon": 17, "name": "Kolmoisloitsu", "mana": 4.0, "mod": {"draw": 2}, "desc": "Loitsii seuraavat 3 loitsua yhtä aikaa."},
	"explosive": {"icon": 18, "name": "Räjähtävä", "mana": 12.0, "mod": {"explode": 7}, "desc": "Seuraava loitsu räjähtää osuessaan."},
	"pierce": {"icon": 19, "name": "Lävistävä", "mana": 7.0, "mod": {"pierce": 3}, "desc": "Seuraava loitsu lävistää 3 vihollista."},
	"accuracy": {"icon": 20, "name": "Tarkkuus", "mana": 1.0, "mod": {"accurate": 1}, "desc": "Poistaa hajonnan seuraavalta loitsulta."},
	"big": {"icon": 21, "name": "Jättiläinen", "mana": 15.0, "mod": {"power": 1.6}, "desc": "Suurempi ja voimakkaampi loitsu."},
}
const MOD_POOL := {
	"dmg_up": 6, "speed_up": 5, "homing": 4, "bounce": 4, "multi2": 5, "multi3": 2, "explosive": 3, "pierce": 4, "accuracy": 4, "big": 2,
}
const PROJECTILE_IDS: Array[String] = ["spark", "fireball", "orb", "ice", "acid", "bomb", "missile", "meteor", "drill", "water", "quake", "lightning"]

const WAND_POOL := {
	"spark": 10, "orb": 7, "ice": 6, "acid": 5, "missile": 5, "water": 4, "drill": 6, "fireball": 4, "lightning": 3,
}
const STAFF_POOL := {
	"fireball": 6, "bomb": 6, "meteor": 4, "quake": 5, "lightning": 4, "acid": 3, "ice": 3,
}


static func get_spell(id: String) -> Dictionary:
	if MODIFIERS.has(id):
		return MODIFIERS[id]
	return DATA.get(id, DATA["spark"])


static func is_modifier(id: String) -> bool:
	return MODIFIERS.has(id)


static func icon_of(id: String) -> Texture2D:
	return Assets.spell_icon(int(get_spell(id).get("icon", 0)))


## Random spell for pickups: projectiles and modifiers, rarer ones deeper.
static func random_spell(seed_value: int, level: int) -> String:
	var r := RandomNumberGenerator.new()
	r.seed = seed_value
	if r.randf() < 0.45:
		return pick(MOD_POOL, r)
	var pool := WAND_POOL.duplicate()
	if level >= 2:
		pool["bomb"] = 3
		pool["meteor"] = 2
		pool["quake"] = 3
	return pick(pool, r)


static func describe(id: String) -> Array[String]:
	var d := get_spell(id)
	var lines: Array[String] = []
	lines.append(String(d.get("name", id)) + ("  (muokkain)" if is_modifier(id) else ""))
	if String(d.get("desc", "")) != "":
		lines.append(String(d["desc"]))
	if is_modifier(id):
		lines.append("Mana %d" % int(d.get("mana", 0)))
	else:
		lines.append("Vahinko %d · Mana %d" % [int(d.get("damage", 0)), int(d.get("mana", 0))])
	return lines


static func name_of(id: String) -> String:
	return String(get_spell(id).get("name", id))


static func color_of(id: String) -> Color:
	return ELEMENT_COLORS.get(get_spell(id).get("element", ""), Color.WHITE)


static func pick(pool: Dictionary, r: RandomNumberGenerator) -> String:
	var keys := pool.keys()
	var w := PackedFloat32Array()
	for k in keys:
		w.append(float(pool[k]))
	return keys[r.rand_weighted(w)]
