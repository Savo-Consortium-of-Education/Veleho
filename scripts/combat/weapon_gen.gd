class_name WeaponGen
extends RefCounted
## Procedural weapon generation (stats, spell slots, names, looks) and flasks.

const QUALITY: Array[String] = ["Vanha", "Kulunut", "Hiottu", "Taidokas", "Mahtava", "Muinainen", "Tähtien"]
const WAND_BASE := {
	"spark": "kipinäsauva", "orb": "helmisauva", "ice": "jääsauva", "acid": "happosauva",
	"missile": "ohjussauva", "water": "vesisauva", "drill": "porasauva", "fireball": "liekkisauva",
	"lightning": "myrskysauva",
}
const STAFF_BASE := {
	"fireball": "tulikeppi", "bomb": "pommikeppi", "meteor": "meteorikeppi", "quake": "järistyskeppi",
	"lightning": "ukkoskeppi", "acid": "myrkkykeppi", "ice": "routakeppi",
}


static func generate(seed_value: int, tier: int, forced_type: int = -1) -> Weapon:
	var r := RandomNumberGenerator.new()
	r.seed = seed_value
	var w := Weapon.new()
	w.seed = seed_value
	w.tier = tier
	w.type = forced_type
	if w.type < 0:
		var roll := r.randf()
		w.type = Weapon.WAND if roll < 0.45 else (Weapon.STAFF if roll < 0.75 else Weapon.SWORD)
	if w.type == Weapon.FLASK:
		return make_flask(seed_value, tier)
	w.look = r.randi_range(0, 3)
	var t := clampi(tier, 1, 10)
	var quality := clampf((t - 1) * 0.6 + r.randf_range(-0.5, 1.6), 0.0, QUALITY.size() - 1.0)
	match w.type:
		Weapon.WAND:
			var cap := clampi(2 + r.randi_range(0, 1 + t / 2) + (1 if r.randf() < 0.3 else 0), 2, 8)
			w.set_capacity(cap)
			var fill := clampi(r.randi_range(1, cap), 1, cap)
			for i in fill:
				var last := i == fill - 1
				if not last and r.randf() < 0.15 + t * 0.03:
					w.spells[i] = Spells.pick(Spells.MOD_POOL, r)
				else:
					w.spells[i] = Spells.pick(Spells.WAND_POOL, r)
			w.cast_delay = r.randf_range(0.08, 0.3) * (1.0 - minf(t, 8) * 0.03)
			w.recharge = r.randf_range(0.2, 0.75)
			w.spread = r.randf_range(0.0, 10.0)
			w.multicast = 1
			if r.randf() < 0.08 + t * 0.04:
				w.multicast += 1
			w.speed_mult = r.randf_range(0.85, 1.25)
			w.dmg_mult = 1.0 + t * 0.08 + r.randf_range(-0.1, 0.2)
			w.mana_mult = r.randf_range(0.7, 1.15)
		Weapon.STAFF:
			var cap := clampi(1 + r.randi_range(0, 1) + (1 if t >= 3 and r.randf() < 0.5 else 0), 1, 3)
			w.set_capacity(cap)
			# modifiers first, projectile last: every cast = modifiers + projectile
			var proj_slot := cap - 1
			if cap > 1 and r.randf() < 0.5:
				proj_slot = cap - 2
			for i in proj_slot:
				if r.randf() < 0.6:
					w.spells[i] = Spells.pick(Spells.MOD_POOL, r)
			w.spells[proj_slot] = Spells.pick(Spells.STAFF_POOL, r)
			w.charge_time = r.randf_range(0.6, 1.25)
			w.recharge = r.randf_range(0.35, 0.8)
			w.dmg_mult = 1.1 + t * 0.1 + r.randf_range(0.0, 0.25)
			w.mana_mult = r.randf_range(0.8, 1.15)
			w.spread = r.randf_range(0.0, 3.0)
			w.speed_mult = r.randf_range(0.9, 1.2)
		Weapon.SWORD:
			w.set_capacity(1)
			var er := r.randf()
			if er < 0.45 - t * 0.04:
				w.element = ""
			else:
				w.element = ["fire", "ice", "acid", "void"][r.randi_range(0, 3)]
			w.reach = r.randf_range(18.0, 26.0) + (6.0 if w.element == "void" else 0.0)
			w.arc = r.randf_range(100.0, 150.0)
			w.damage = r.randf_range(11.0, 16.0) * (1.0 + t * 0.12)
			w.swing_time = r.randf_range(0.22, 0.38)
			w.cut = r.randi_range(20, 34) + t * 2
	w.name = _make_name(w, int(quality), r)
	return w


static func make_flask(seed_value: int, tier: int, forced_liquid: int = -1) -> Weapon:
	var r := RandomNumberGenerator.new()
	r.seed = seed_value ^ 0xf1a5
	var w := Weapon.new()
	w.type = Weapon.FLASK
	w.seed = seed_value
	w.tier = tier
	w.look = r.randi_range(0, 2)
	w.set_capacity(1)
	var table := {Mat.WATER: 6.0, Mat.OIL: 2.0, Mat.ACID: 2.0, Mat.ELONNESTE: 3.0, Mat.AETHER: 2.0, Mat.SLUDGE: 1.0, Mat.BLOOD: 1.0}
	if tier >= 2:
		table[Mat.LAVA] = 1.0
	var keys := table.keys()
	var weights := PackedFloat32Array()
	for k in keys:
		weights.append(table[k])
	w.liquid = forced_liquid if forced_liquid >= 0 else int(keys[r.rand_weighted(weights)])
	w.amount = round(r.randf_range(55.0, 100.0))
	w.name = ["Pullo", "Taikapullo", "Lasipullo"][w.look]
	return w


static func _make_name(w: Weapon, q: int, r: RandomNumberGenerator) -> String:
	var prefix := QUALITY[clampi(q, 0, QUALITY.size() - 1)]
	match w.type:
		Weapon.WAND:
			return "%s %s" % [prefix, WAND_BASE.get(w.main_spell(), "sauva")]
		Weapon.STAFF:
			return "%s %s" % [prefix, STAFF_BASE.get(w.main_spell(), "keppi")]
		_:
			match w.element:
				"fire":
					return "%s liekkiterä" % prefix
				"ice":
					return "%s routaterä" % prefix
				"acid":
					return "%s happoterä" % prefix
				"void":
					return "%s tyhjyyden terä" % prefix
			var plain: Array[String] = ["miekka", "rautamiekka", "terässapeli", "velhon miekka"]
			return "%s %s" % [prefix, plain[r.randi_range(0, plain.size() - 1)]]


## Starting equipment for a new run: wand, staff, sword and a potion flask.
static func starter_kit(run_seed: int) -> Array:
	var r := RandomNumberGenerator.new()
	r.seed = run_seed ^ 0x51ab
	var wand := generate(r.randi() & 0x7fffffff, 1, Weapon.WAND)
	wand.set_capacity(3)
	wand.spells[0] = "spark"
	wand.spells[1] = ["spark", "orb", "drill", "water"][r.randi_range(0, 3)]
	wand.spells[2] = ""
	wand.multicast = 1
	wand.cast_delay = 0.14
	wand.recharge = 0.35
	wand.spread = 2.0
	wand.dmg_mult = 1.0
	wand.mana_mult = 0.9
	wand.name = "Oppipojan kipinäsauva"
	var staff := generate(r.randi() & 0x7fffffff, 1, Weapon.STAFF)
	staff.set_capacity(2)
	staff.spells[0] = ""
	staff.spells[1] = ["bomb", "fireball", "quake"][r.randi_range(0, 2)]
	staff.name = "Oppipojan " + String(STAFF_BASE.get(staff.spells[1], "keppi"))
	var sword := generate(r.randi() & 0x7fffffff, 1, Weapon.SWORD)
	sword.element = ""
	sword.reach = 20.0
	sword.damage = 13.0
	sword.name = "Ruosteinen miekka"
	var liquids := [Mat.WATER, Mat.WATER, Mat.ELONNESTE, Mat.OIL, Mat.ACID]
	var flask := make_flask(r.randi() & 0x7fffffff, 1, liquids[r.randi_range(0, liquids.size() - 1)])
	flask.amount = 100.0
	return [wand.to_dict(), staff.to_dict(), sword.to_dict(), flask.to_dict()]


## Loose spells in the starting spell bag (16 slots).
static func starter_bag(run_seed: int) -> Array:
	var r := RandomNumberGenerator.new()
	r.seed = run_seed ^ 0xba9
	var bag: Array = []
	bag.resize(16)
	bag.fill("")
	bag[0] = ["fireball", "ice", "acid", "missile", "orb"][r.randi_range(0, 4)]
	bag[1] = ["multi2", "dmg_up", "homing", "speed_up"][r.randi_range(0, 3)]
	return bag
