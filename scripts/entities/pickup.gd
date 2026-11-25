class_name Pickup
extends Actor
## Gold, heart crystals, mana crystals and weapons lying in the world.

var kind := "gold"
var value := 0
var weapon: Weapon
var sprite: Node2D
var float_mode := false
var age := 0.0
var collected := false
var base_y := 0.0
var spell_id := ""
var _full_msg := 0.0


func setup_pickup(g: Game, k: String, pos: Vector2, data = null, floating: bool = false) -> void:
	init_actor(g)
	kind = k
	float_mode = floating
	z_index = 1
	match k:
		"gold":
			hw = 2
			hh = 2
			value = int(data) if data != null else 5
			_anim_sprite(1)
		"heart":
			hw = 3
			hh = 3
			_anim_sprite(0)
		"mana":
			hw = 3
			hh = 3
			_anim_sprite(2)
		"spell":
			hw = 3
			hh = 3
			value = 0
			spell_id = String(data)
			var t := Assets.tex("items")
			if t.get_height() >= 48:
				_anim_sprite(3)
			else:
				var s0 := Sprite2D.new()
				s0.texture = Spells.icon_of(spell_id)
				add_child(s0)
				sprite = s0
		"weapon":
			hw = 5
			hh = 3
			weapon = data
			var s := Sprite2D.new()
			s.texture = weapon.icon()
			s.rotation = 0.0 if weapon.type == Weapon.FLASK else (-PI * 0.25 if weapon.type != Weapon.SWORD else -PI * 0.5)
			add_child(s)
			sprite = s
	if float_mode:
		gravity_scale = 0.0
	place_at(pos)
	base_y = position.y


func _anim_sprite(row: int) -> void:
	var s := AnimatedSprite2D.new()
	var anims := [["heart", 0, 4, 6, true], ["gold", 1, 4, 6, true], ["mana", 2, 4, 6, true]]
	if Assets.tex("items").get_height() >= 48:
		anims.append(["scroll", 3, 4, 6, true])
	s.sprite_frames = Assets.frames("items", 12, 12, anims, str(anims.size()))
	s.play(["heart", "gold", "mana", "scroll"][row])
	s.frame = randi() % 4
	add_child(s)
	sprite = s


func _physics_process(delta: float) -> void:
	if game == null or game.paused_for_ui or collected:
		return
	age += delta
	if not float_mode:
		vel.x = move_toward(vel.x, 0.0, 120.0 * delta)
		physics_move(delta, game.dim_gravity)
	if kind != "gold" and sprite:
		sprite.position.y = sin(age * 2.6) * 1.5 - 1.0
	match kind:
		"weapon":
			game.add_light(position, 26.0, weapon.main_color() * 0.55)
			if game.particles and randf() < 0.05:
				game.particles.spawn(position + Vector2(randf_range(-6, 6), randf_range(-4, 4)), Vector2(0, -12), weapon.main_color().lightened(0.4), 0.6, 0.0)
		"heart":
			game.add_light(position, 30.0, Color(1.0, 0.3, 0.35) * 0.6)
		"mana":
			game.add_light(position, 30.0, Color(0.35, 0.6, 1.0) * 0.6)
		"spell":
			game.add_light(position, 26.0, Spells.color_of(spell_id) * 0.5 if not Spells.is_modifier(spell_id) else Color(0.4, 0.6, 1.0) * 0.5)
		"gold":
			if randf() < 0.01:
				game.spawn_fx("sparkle", position + Vector2(randf_range(-2, 2), randf_range(-2, 2)), 0.0, Color("fff2a8"))
	var p := game.player
	if p == null or p.dead or kind == "weapon" or age < 0.4:
		return
	var d := p.center().distance_to(center())
	if kind == "gold" and d < 30.0:
		var pull := (p.center() - center()).normalized() * 150.0 * delta
		bx += int(round(pull.x))
		by += int(round(pull.y))
		_sync()
	_full_msg -= get_physics_process_delta_time()
	if d < 8.0 + hw:
		if kind == "spell" and p.spell_bag.find("") < 0:
			if _full_msg <= 0.0:
				_full_msg = 3.0
				game.hud.message("Loitsupussi on täynnä (Tab avaa repun)", Color("a89cc0"))
			return
		_collect(p)


func to_save() -> Dictionary:
	var d := {"kind": kind, "pos": position, "value": value, "spell": spell_id, "float": float_mode}
	if weapon:
		d["weapon"] = weapon.to_dict()
	return d


func _collect(p: Player) -> void:
	collected = true
	match kind:
		"gold":
			GameState.run["stats"]["gold"] = int(GameState.run["stats"]["gold"]) + value
			Audio.play("pickup_gold", -6.0)
			game.floating_text(position + Vector2(0, -6), "+%d" % value, Color("f2c14e"))
		"heart":
			p.max_hp += 10.0
			p.heal(35.0)
			Audio.play("pickup_heart")
			game.hud.message("Elämänkristalli! +10 maks. elämä", Color("ff7a8a"))
		"mana":
			p.mana_max += 15.0
			p.mana = p.mana_max
			Audio.play("pickup_heart", 0.0, 1.3)
			game.hud.message("Manakristalli! +15 maks. mana", Color("7ab8ff"))
		"spell":
			p.add_spell(spell_id)
			Audio.play("spell_pickup")
			game.hud.message("Löysit loitsun: %s (Tab)" % Spells.name_of(spell_id), Color("c8a8ff"))
	game.spawn_fx("sparkle", position, 0.0, Color.WHITE)
	queue_free()
