class_name EnemyCaster
extends Enemy
## Varjomaagi: keeps its distance and hurls dark bolts.

var cast_cd := 1.5
var casting := 0.0


func _init_kind() -> void:
	kind = "caster"
	display_name = "Varjomaagi"
	hw = 3
	hh = 7
	max_hp = 26.0
	contact_damage = 5.0
	sight = 220.0
	gold = 6
	make_sprite("caster", 16, 18, [["idle", 0, 2, 3, true], ["walk", 1, 4, 8, true], ["cast", 2, 3, 8, false], ["death", 3, 5, 8, false]], -2.0)
	tint = Color.WHITE
	cast_cd = randf_range(1.0, 2.5)


func setup(g: Game, lvl: int, dim: Dictionary) -> void:
	super.setup(g, lvl, dim)
	tint = Color.WHITE


func ai(delta: float, p: Player, dist: float) -> void:
	cast_cd -= delta
	var speed := 30.0 * (0.5 if chilled > 0.0 else 1.0)
	if casting > 0.0:
		casting -= delta
		vel.x = move_toward(vel.x, 0.0, 400.0 * delta)
		game.add_light(position + Vector2(face * 5, -8), 26.0, Color(1.0, 0.15, 0.25) * 0.8)
		if casting <= 0.0 and p and not p.dead:
			var from := position + Vector2(face * 6, -8)
			var lead := p.center() + p.vel * clampf(dist / 140.0, 0.0, 0.6) * 0.5
			game.cast_spell("enemy_bolt", from, (lead - from).normalized(), 1, 1.0, 1.0 + 0.12 * (level - 1), 1.0)
			Audio.play_at("caster_cast", position, -4.0)
			cast_cd = randf_range(1.6, 2.6) / (1.0 + 0.08 * (level - 1))
		return
	if p and (can_see or aggro > 0.0):
		face = 1 if p.position.x > position.x else -1
		var want := 0.0
		if dist < 70.0:
			want = -face * speed
		elif dist > 150.0:
			want = face * speed
		if want != 0.0 and not ground_ahead(signi(int(want))):
			want = 0.0
		vel.x = move_toward(vel.x, want, 300.0 * delta)
		if cast_cd <= 0.0 and can_see:
			casting = 0.45
			play("cast")
			return
	else:
		think -= delta
		if think <= 0.0:
			think = randf_range(1.5, 3.5)
			state = randi_range(-1, 1)
		var want2 := state * speed * 0.6
		if want2 != 0.0:
			face = signi(int(want2))
			if not ground_ahead(face) or blocked_ahead(face):
				state = -state
				want2 = 0.0
		vel.x = move_toward(vel.x, want2, 300.0 * delta)
	if on_ground and absf(vel.x) > 1.0 and blocked_ahead(1 if vel.x > 0 else -1):
		vel.y = -150.0
	play("walk" if absf(vel.x) > 4.0 else "idle")
