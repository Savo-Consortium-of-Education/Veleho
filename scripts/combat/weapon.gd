class_name Weapon
extends RefCounted
## A wand, staff, sword or potion flask. Data only (plus runtime state).
## Wands and staffs have `capacity` spell slots; empty slots hold "".

const WAND := 0
const STAFF := 1
const SWORD := 2
const FLASK := 3
const TYPE_NAMES: Array[String] = ["Taikasauva", "Taikakeppi", "Miekka", "Pullo"]
const FLASK_MAX := 100.0

var type := WAND
var name := ""
var seed := 0
var tier := 1
var capacity := 1
var spells: Array[String] = []
var cast_delay := 0.2
var recharge := 0.5
var spread := 3.0
var multicast := 1
var speed_mult := 1.0
var dmg_mult := 1.0
var mana_mult := 1.0
var charge_time := 1.0
var reach := 22.0
var arc := 120.0
var damage := 12.0
var swing_time := 0.3
var cut := 28
var element := ""
var look := 0
# flasks
var liquid := 0
var amount := 0.0

# runtime
var cursor := 0
var cooldown := 0.0
var _icon: Texture2D
var _icon_key := ""


func to_dict() -> Dictionary:
	return {
		"type": type, "name": name, "seed": seed, "tier": tier, "capacity": capacity,
		"spells": Array(spells), "cast_delay": cast_delay, "recharge": recharge, "spread": spread,
		"multicast": multicast, "speed_mult": speed_mult, "dmg_mult": dmg_mult, "mana_mult": mana_mult,
		"charge_time": charge_time, "reach": reach, "arc": arc, "damage": damage,
		"swing_time": swing_time, "cut": cut, "element": element, "look": look,
		"liquid": liquid, "amount": amount,
	}


static func from_dict(d: Dictionary) -> Weapon:
	var w := Weapon.new()
	w.type = int(d.get("type", 0))
	w.name = String(d.get("name", "?"))
	w.seed = int(d.get("seed", 0))
	w.tier = int(d.get("tier", 1))
	w.spells.clear()
	for s in d.get("spells", []):
		w.spells.append(String(s))
	w.capacity = int(d.get("capacity", maxi(1, w.spells.size())))
	w.set_capacity(w.capacity)
	w.cast_delay = float(d.get("cast_delay", 0.2))
	w.recharge = float(d.get("recharge", 0.5))
	w.spread = float(d.get("spread", 3.0))
	w.multicast = int(d.get("multicast", 1))
	w.speed_mult = float(d.get("speed_mult", 1.0))
	w.dmg_mult = float(d.get("dmg_mult", 1.0))
	w.mana_mult = float(d.get("mana_mult", 1.0))
	w.charge_time = float(d.get("charge_time", 1.0))
	w.reach = float(d.get("reach", 22.0))
	w.arc = float(d.get("arc", 120.0))
	w.damage = float(d.get("damage", 12.0))
	w.swing_time = float(d.get("swing_time", 0.3))
	w.cut = int(d.get("cut", 28))
	w.element = String(d.get("element", ""))
	w.look = int(d.get("look", 0))
	w.liquid = int(d.get("liquid", 0))
	w.amount = float(d.get("amount", 0.0))
	return w


func uses_spells() -> bool:
	return type == WAND or type == STAFF


func set_capacity(n: int) -> void:
	capacity = maxi(1, n)
	while spells.size() < capacity:
		spells.append("")
	while spells.size() > capacity:
		spells.remove_at(spells.size() - 1)


## Spell ids in slot order, skipping empty slots.
func filled() -> Array[String]:
	var out: Array[String] = []
	for s in spells:
		if s != "":
			out.append(s)
	return out


## First projectile spell (for colours and names).
func main_spell() -> String:
	for s in spells:
		if s != "" and not Spells.is_modifier(s):
			return s
	return ""


func icon() -> Texture2D:
	if type == FLASK:
		var key := "%d_%d" % [liquid, int(amount / 5.0)]
		if _icon == null or key != _icon_key:
			_icon_key = key
			_icon = WeaponArt.make(self)
		return _icon
	if _icon == null:
		_icon = WeaponArt.make(self)
	return _icon


func type_name() -> String:
	return TYPE_NAMES[type]


func main_color() -> Color:
	if type == SWORD:
		return Spells.ELEMENT_COLORS.get(element, Color.WHITE)
	if type == FLASK:
		return Mat.color_of(liquid, 0.7) if liquid != 0 and amount > 0.0 else Color("a8c8e8")
	var ms := main_spell()
	if ms == "":
		return Color("8f86a8")
	return Spells.color_of(ms)


func spell_names() -> String:
	var parts: Array[String] = []
	for s in filled():
		parts.append(Spells.name_of(s))
	return " · ".join(parts) if not parts.is_empty() else "(tyhjä)"


func liquid_name() -> String:
	if liquid == 0 or amount <= 0.0:
		return "tyhjä"
	return Mat.NAMES[liquid]


func describe() -> Array[String]:
	var lines: Array[String] = []
	match type:
		WAND:
			lines.append("Loitsut: " + spell_names())
			lines.append("Paikat %d/%d · Kerralla %d · Hajonta %d°" % [filled().size(), capacity, multicast, int(spread)])
			lines.append("Viive %.2f s · Lataus %.2f s" % [cast_delay, recharge])
			lines.append("Vahinko x%.2f · Mana x%.2f" % [dmg_mult, mana_mult])
		STAFF:
			lines.append("Loitsut: " + spell_names() + " (lataa pitämällä)")
			lines.append("Paikat %d/%d · Latausaika %.2f s · Palautus %.2f s" % [filled().size(), capacity, charge_time, recharge])
			lines.append("Vahinko x%.2f · Mana x%.2f" % [dmg_mult, mana_mult])
		SWORD:
			var el := ""
			match element:
				"fire":
					el = " · Tuli"
				"ice":
					el = " · Jää"
				"acid":
					el = " · Happo"
				"void":
					el = " · Tyhjyys"
			lines.append("Vahinko %d · Ulottuvuus %d%s" % [int(damage), int(reach), el])
			lines.append("Lyönti %.2f s · Kaari %d° · Leikkaa %d" % [swing_time, int(arc), cut])
		FLASK:
			lines.append("Sisältö: %s %d/%d" % [liquid_name(), int(amount), int(FLASK_MAX)])
			lines.append("Vasen: kaada · Oikea: heitä · F: juo")
			lines.append("Täyttyy, kun upotat pullon nesteeseen.")
	return lines
