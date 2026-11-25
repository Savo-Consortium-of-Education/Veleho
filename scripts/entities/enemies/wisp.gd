class_name EnemyWisp
extends Enemy
## Tulihenki: floating flame that sets things alight and spits fire.

var spit_cd := 3.0


func _init_kind() -> void:
	kind = "wisp"
	display_name = "Tulihenki"
	hw = 4
	hh = 4
	max_hp = 14.0
	contact_damage = 7.0
	sight = 180.0
	gold = 3
	flying = true
	gravity_scale = 0.0
	fire_immune = true
	bleeds = 0
	make_sprite("wisp", 12, 12, [["float", 0, 4, 10, true], ["death", 1, 4, 10, false]], 0.0)
	spit_cd = randf_range(2.0, 4.0)


func setup(g: Game, lvl: int, dim: Dictionary) -> void:
	super.setup(g, lvl, dim)
	tint = Color.WHITE


func ai(delta: float, p: Player, dist: float) -> void:
	spit_cd -= delta
	var desired := Vector2(sin(anim_time * 0.9) * 20.0, cos(anim_time * 1.3) * 12.0)
	if p and (can_see or aggro > 0.0):
		var to := p.center() - center()
		face = 1 if to.x > 0 else -1
		if dist > 60.0:
			desired += to.normalized() * 42.0
		if spit_cd <= 0.0 and can_see and dist < 150.0:
			spit_cd = randf_range(2.5, 4.0)
			game.cast_spell("enemy_fire", center(), to.normalized(), 1, 1.0, 1.0 + 0.1 * (level - 1), 1.0)
	vel = vel.lerp(desired, 2.0 * delta)
	game.add_light(position, 46.0, Color(1.0, 0.55, 0.2) * 0.9)
	if randf() < 0.05:
		var fx := bx + randi_range(-2, hw * 2 + 1)
		var fy := by + randi_range(-2, hh * 2 + 1)
		var m := world.get_mat(fx, fy)
		if m != 0 and Mat.FLAM[m] > 0:
			world.ignite(fx, fy)
	if game.particles and randf() < 0.4:
		game.particles.spawn(center() + Vector2(randf_range(-3, 3), randf_range(-2, 2)), Vector2(randf_range(-8, 8), randf_range(-35, -15)), Color(1.0, randf_range(0.4, 0.9), 0.15), 0.4, -0.2)
	if in_liquid == Mat.WATER or wet > 0.0:
		take_damage(30.0 * delta, "Vesi", Vector2.ZERO, "env")


func _on_death() -> void:
	game.explosion(center(), 9, 35.0, true, 10.0, 1, "Tulihengen räjähdys")
