class_name EnemyBoss
extends Enemy
## Portinvartija: floating stone guardian of the dimensional gate. Appears on
## every BOSS_EVERY-th level in an arena in front of the sealed portal.
## Attacks: shard volley, summon, dash (carves terrain), elemental rain (phase 2).

var home := Vector2.ZERO
var arena := Rect2()
var phase := 1
var boss_index := 1
var attack_cd := 2.0
var action := ""
var action_t := 0.0
var volleys_left := 0
var dash_dir := Vector2.ZERO
var awake := false
var rain_t := 0.0
var _hurt_snd := 0.0
var _move_rem := Vector2.ZERO


func _init_kind() -> void:
	kind = "boss"
	display_name = "Portinvartija"
	hw = 12
	hh = 12
	max_hp = 520.0
	contact_damage = 16.0
	sight = 320.0
	gold = 0
	flying = true
	gravity_scale = 0.0
	knock_resist = 1.0
	bleeds = 0
	make_sprite("boss", 48, 48, [["idle", 0, 6, 8, true], ["attack", 1, 6, 10, false], ["summon", 2, 6, 8, false], ["death", 3, 6, 7, false]], 0.0)


func setup_boss(g: Game, lvl: int, dim: Dictionary, center: Vector2, area: Rect2) -> void:
	setup(g, lvl, dim)
	tint = Color.WHITE
	boss_index = maxi(1, lvl / GameState.BOSS_EVERY)
	max_hp = 520.0 * (1.0 + 0.45 * (boss_index - 1))
	hp = max_hp
	contact_damage = 16.0 * (1.0 + 0.15 * (boss_index - 1))
	home = center
	arena = area


## The guardian floats freely through rock but stays inside its arena.
func physics_move(delta: float, _dim_gravity: float = 1.0) -> void:
	_move_rem += vel * delta
	var mv := Vector2i(int(_move_rem.x), int(_move_rem.y))
	_move_rem -= Vector2(mv)
	bx += mv.x
	by += mv.y
	if arena.size.x > 0.0:
		bx = clampi(bx, int(arena.position.x), int(arena.end.x) - hw * 2)
		by = clampi(by, int(arena.position.y), int(arena.end.y) - hh * 2)
	_sync()
	on_ground = false


func ai(delta: float, p: Player, dist: float) -> void:
	_hurt_snd -= delta
	game.add_light(position, 80.0 if phase == 1 else 95.0, (Color(0.55, 0.45, 1.0) if phase == 1 else Color(1.0, 0.35, 0.45)) * 0.85)
	if game.particles and randf() < 0.3:
		var a := randf() * TAU
		game.particles.spawn(position + Vector2(cos(a), sin(a)) * 16.0, Vector2(cos(a), sin(a)) * -12.0, Color(0.6, 0.9, 1.0) if phase == 1 else Color(1.0, 0.5, 0.6), 0.6, 0.0)
	if not awake:
		vel = vel.lerp((home + Vector2(0, sin(anim_time) * 4.0) - position) * 2.0, 2.0 * delta)
		if p and not p.dead and (arena.grow(16).has_point(p.position) or (can_see and dist < 170.0)):
			_wake_up()
		return
	if p == null or p.dead:
		vel = vel.lerp(Vector2.ZERO, 2.0 * delta)
		return
	if phase == 1 and hp < max_hp * 0.5:
		phase = 2
		Audio.play("boss_roar")
		game.shake(7.0)
		game.hud.message("Portinvartija raivostuu!", Color("ff6b8a"))
		attack_cd = 0.8
		if game.particles:
			game.particles.burst(position, 40, Color(1.0, 0.4, 0.5), 140.0, 0.8, 0.0)
	var spd := 1.35 if phase == 2 else 1.0
	match action:
		"":
			var target := Vector2(p.position.x + sin(anim_time * 0.8) * 70.0, p.position.y - 60.0)
			target.x = clampf(target.x, arena.position.x + 30.0, arena.end.x - 30.0)
			target.y = clampf(target.y, arena.position.y + 24.0, arena.end.y - 40.0)
			vel = vel.lerp((target - position).limit_length(70.0 * spd), 2.0 * delta)
			attack_cd -= delta * spd
			play("idle")
			if attack_cd <= 0.0:
				_choose_action()
		"volley":
			vel = vel.lerp(Vector2.ZERO, 4.0 * delta)
			action_t -= delta
			if action_t <= 0.0:
				_fire_volley(p)
				volleys_left -= 1
				if volleys_left > 0:
					action_t = 0.45
					sprite.play("attack")
					sprite.frame = 3
				else:
					_end_action(1.6)
		"summon":
			vel = vel.lerp(Vector2.ZERO, 4.0 * delta)
			action_t -= delta
			if action_t <= 0.0:
				_summon()
				_end_action(2.0)
		"dash":
			action_t -= delta
			if action_t > 0.7:
				vel = vel.lerp(Vector2.ZERO, 6.0 * delta)
				game.shake(1.0)
				if action_t - delta <= 0.7:
					dash_dir = (p.center() - center()).normalized()
					Audio.play_at("boss_attack", position, 0.0, 0.7)
			elif action_t > 0.0:
				vel = dash_dir * 240.0 * spd
				world.carve_circle(int(position.x), int(position.y), 10, 75, 0.06)
			else:
				_end_action(1.4)
		"rain":
			vel = vel.lerp(Vector2.ZERO, 3.0 * delta)
			action_t -= delta
			rain_t -= delta
			if rain_t <= 0.0:
				rain_t = 0.11
				var from := Vector2(p.position.x + randf_range(-90.0, 90.0), arena.position.y + 6.0)
				game.cast_spell(_rain_spell(), from, Vector2(randf_range(-0.15, 0.15), 1.0), 1, 1.0, 1.0 + 0.15 * (boss_index - 1), 0.9)
			if action_t <= 0.0:
				_end_action(1.8)


func _wake_up() -> void:
	awake = true
	attack_cd = 1.6
	Audio.play("boss_roar")
	game.shake(6.0)
	game.on_boss_awake(self)


func _choose_action() -> void:
	var options := ["volley", "volley", "dash", "dash"]
	if _alive_minions() < 4:
		options.append("summon")
	if phase == 2:
		options.append("rain")
		options.append("rain")
	action = options[randi() % options.size()]
	match action:
		"volley":
			action_t = 0.7
			volleys_left = 1 if phase == 1 else 2
			play("attack")
		"summon":
			action_t = 1.0
			play("summon")
			Audio.play_at("boss_summon", position, 0.0)
		"dash":
			action_t = 1.3
			play("attack")
		"rain":
			action_t = 1.8
			rain_t = 0.3
			play("summon")
			Audio.play_at("boss_summon", position, -2.0, 1.3)


func _end_action(cd: float) -> void:
	action = ""
	attack_cd = cd * (0.75 if phase == 2 else 1.0)


func _fire_volley(p: Player) -> void:
	var n := 6 + (phase - 1) * 3
	var base := (p.center() - center()).angle()
	var spread := deg_to_rad(80.0)
	for i in n:
		var a := base - spread * 0.5 + spread * (float(i) / float(n - 1))
		game.cast_spell("boss_shard", center() + Vector2.from_angle(a) * 12.0, Vector2.from_angle(a), 1, 1.0, 1.0 + 0.15 * (boss_index - 1), 1.0 + 0.1 * (phase - 1))
	game.shake(2.0)


func _summon() -> void:
	var table: Array = []
	for k in game.dim.get("enemies", {}).keys():
		if k != "golem":
			table.append(k)
	if table.is_empty():
		table = ["bat"]
	for i in 2 + (phase - 1):
		var a := randf() * TAU
		var pos := center() + Vector2(cos(a), sin(a)) * 26.0
		var kind_name: String = table[randi() % table.size()]
		if kind_name != "bat" and kind_name != "wisp":
			kind_name = "bat" if randf() < 0.5 else kind_name
		game.spawn_enemy(kind_name, pos)
		game.spawn_fx("sparkle", pos, 0.0, Color(0.8, 0.6, 1.0))


func _alive_minions() -> int:
	var n := 0
	for e in game.enemies:
		if is_instance_valid(e) and not e.dead and e != self and e.position.distance_to(position) < 260.0:
			n += 1
	return n


func _rain_spell() -> String:
	match String(game.dim.get("id", "")):
		"frost":
			return "ice"
		"crystal", "fungal":
			return "acid"
		"void":
			return "boss_shard"
		_:
			return "enemy_fire"


func take_damage(amount: float, source: String, knock: Vector2 = Vector2.ZERO, kind_: String = "") -> void:
	if dead:
		return
	if not awake:
		_wake_up()
	super.take_damage(amount, source, Vector2.ZERO, kind_)
	if _hurt_snd <= 0.0 and amount >= 2.0:
		_hurt_snd = 0.15
		Audio.play_at("boss_hurt", position, -4.0)


func die(source: String) -> void:
	dead = true
	death_t = 0.0
	play("death")
	Audio.play("boss_die")
	game.shake(9.0)
	game.on_enemy_killed(self, source)
	game.on_boss_killed(self)


func _physics_process(delta: float) -> void:
	if dead:
		if game == null or game.paused_for_ui:
			return
		death_t += delta
		vel = Vector2.ZERO
		if game.particles and randf() < 0.6:
			game.particles.spawn_material(center() + Vector2(randf_range(-12, 12), randf_range(-12, 12)), Vector2(randf_range(-60, 60), randf_range(-90, -10)), Mat.GRAVEL, Mat.ROCK)
		if death_t > 1.6:
			queue_free()
		return
	super._physics_process(delta)
