class_name EnemyGolem
extends Enemy
## Kivikolossi: slow and tough, slams the ground and crumbles terrain.

var attack_cd := 1.0
var windup := 0.0
var step_t := 0.0


func _init_kind() -> void:
	kind = "golem"
	display_name = "Kivikolossi"
	hw = 6
	hh = 10
	max_hp = 95.0
	contact_damage = 12.0
	sight = 170.0
	gold = 15
	max_step = 4
	knock_resist = 0.8
	bleeds = 0
	make_sprite("golem", 24, 24, [["idle", 0, 2, 3, true], ["walk", 1, 4, 5, true], ["attack", 2, 4, 7, false], ["death", 3, 5, 7, false]], -2.0)


func setup(g: Game, lvl: int, dim: Dictionary) -> void:
	super.setup(g, lvl, dim)
	tint = Color.WHITE


func ai(delta: float, p: Player, dist: float) -> void:
	attack_cd -= delta
	if windup > 0.0:
		windup -= delta
		vel.x = move_toward(vel.x, 0.0, 400.0 * delta)
		if windup <= 0.0:
			_slam()
		return
	var speed := 26.0 * (0.5 if chilled > 0.0 else 1.0)
	if p and (can_see or aggro > 0.0):
		face = 1 if p.position.x > position.x else -1
		if dist < 34.0 and attack_cd <= 0.0:
			windup = 0.55
			play("attack")
			return
		var want := face * speed
		if not ground_ahead(face):
			want = 0.0
		vel.x = move_toward(vel.x, want, 200.0 * delta)
	else:
		vel.x = move_toward(vel.x, 0.0, 200.0 * delta)
	if on_ground and absf(vel.x) > 1.0 and blocked_ahead(face):
		vel.y = -130.0
	if absf(vel.x) > 3.0:
		play("walk")
		step_t -= delta
		if step_t <= 0.0:
			step_t = 0.5
			Audio.play_at("golem_stomp", position, -14.0, 0.8)
	else:
		play("idle")
	game.add_light(position + Vector2(face * 2, -6), 22.0, Color(0.3, 0.9, 1.0) * 0.5)


func _slam() -> void:
	attack_cd = 2.0
	var hit := center() + Vector2(face * 14, hh - 2)
	Audio.play_at("golem_stomp", position, 2.0)
	game.shake(5.0)
	world.crumble(int(hit.x), int(hit.y + 4), 7, 70)
	if game.particles:
		game.particles.burst(hit, 24, Color("8a8070"), 110.0, 0.6, 1.0, PI, -PI * 0.5)
	for a in game.actors_in_radius(hit, 26.0, 1):
		a.take_damage(contact_damage * 1.4, display_name, (a.center() - hit).normalized() * 160.0 + Vector2(0, -80), "melee")


func _on_death() -> void:
	if game.particles:
		for k in 40:
			game.particles.spawn_material(center(), Vector2(randf_range(-80, 80), randf_range(-120, -20)), Mat.GRAVEL, Mat.GRAVEL)
