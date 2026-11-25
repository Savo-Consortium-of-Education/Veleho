class_name Perks
extends RefCounted
## Blessings ("siunaukset") chosen at every dimensional gate.

const LIST := {
	"vitality": {"name": "Elinvoima", "desc": "+30 maks. elämä ja täysi parannus"},
	"mana_flow": {"name": "Manavirta", "desc": "+40 % manan palautus"},
	"mana_well": {"name": "Manakaivo", "desc": "+40 maks. mana"},
	"fire_ward": {"name": "Tulenkesto", "desc": "Et syty palamaan", "unique": true},
	"feather": {"name": "Höyhenkevyt", "desc": "+1,2 s leijuntaa"},
	"power": {"name": "Loitsuvoima", "desc": "+20 % vahinko kaikilla aseilla"},
	"vampire": {"name": "Verenimu", "desc": "Jokainen tappo parantaa 4 elämää"},
	"swift": {"name": "Vikkelyys", "desc": "+15 % liikkumisnopeus"},
	"blast_ward": {"name": "Räjähdyssuoja", "desc": "-50 % räjähdysvahinko"},
	"long_blade": {"name": "Pitkä terä", "desc": "+30 % miekan ulottuvuus"},
	"acid_skin": {"name": "Happokuori", "desc": "Happo ei satuta sinua", "unique": true},
}


static func choices(seed_value: int, taken: Array) -> Array[String]:
	var r := RandomNumberGenerator.new()
	r.seed = seed_value
	var pool: Array[String] = []
	for k in LIST:
		if LIST[k].get("unique", false) and taken.has(k):
			continue
		pool.append(k)
	var out: Array[String] = []
	while out.size() < 3 and not pool.is_empty():
		var i := r.randi_range(0, pool.size() - 1)
		out.append(pool[i])
		pool.remove_at(i)
	return out


static func apply(id: String, p: Player) -> void:
	p.perks.append(id)
	match id:
		"vitality":
			p.max_hp += 30.0
			p.hp = p.max_hp
		"mana_flow":
			p.mana_regen *= 1.4
		"mana_well":
			p.mana_max += 40.0
		"fire_ward":
			p.fire_immune = true
		"feather":
			p.lev_max += 1.2
		"power":
			p.dmg_mult *= 1.2
		"vampire":
			p.lifesteal += 4.0
		"swift":
			p.speed_mult *= 1.15
		"blast_ward":
			p.blast_resist = 1.0 - (1.0 - p.blast_resist) * 0.5
		"long_blade":
			p.reach_mult *= 1.3
		"acid_skin":
			p.acid_immune = true
