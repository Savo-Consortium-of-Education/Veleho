class_name Enemy
extends Actor
## Base enemy: line of sight, contact damage, death, drops, animation helpers.

var kind := ""
var display_name := "Olento"
var sprite: AnimatedSprite2D
var contact_damage := 8.0
var sight := 170.0
var can_see := false
var aggro := 0.0
var los_t := 0.0
var think := 0.0
var state := 0
var level := 1
var tint := Color.WHITE
var gold := 2
var flying := false
var death_t := 0.0
var touch_cd := 0.0
var face := 1
var anim_time := 0.0
var bleeds := Mat.BLOOD
var blood_color := Color("a81a2a")
var knock_resist := 0.0


func setup(g: Game, lvl: int, dim: Dictionary) -> void:
	init_actor(g)
	level = lvl
	tint = dim.get("tint", Color.WHITE)
	_init_kind()
	var scale_hp := 1.0 + 0.22 * (lvl - 1)
	max_hp *= scale_hp
	hp = max_hp
	contact_damage *= 1.0 + 0.12 * (lvl - 1)
	z_index = 1


## Override: set hitbox, stats and sprite.
func _init_kind() -> void:
	pass


## Override: per-frame behaviour.
func ai(_delta: float, _p: Player, _dist: float) -> void:
	pass


func on_touch_player(_p: Player) -> void:
	pass


func make_sprite(sheet: String, fw: int, fh: int, anims: Array, offset_y: float) -> void:
	sprite = AnimatedSprite2D.new()
	sprite.sprite_frames = Assets.frames(sheet, fw, fh, anims)
	sprite.position = Vector2(0, offset_y)
	add_child(sprite)
	sprite.play(String(anims[0][0]))


func play(anim: String) -> void:
	if sprite and sprite.animation != anim:
		sprite.play(anim)


func _physics_process(delta: float) -> void:
	if game == null or game.paused_for_ui:
		return
	anim_time += delta
	if dead:
		death_t += delta
		gravity_scale = 1.0
		vel.x = move_toward(vel.x, 0.0, 200.0 * delta)
		physics_move(delta, game.dim_gravity)
		if death_t > 1.4:
			queue_free()
		return
	var p := game.player
	var dist := 9999.0
	if p:
		dist = position.distance_to(p.position)
	if dist > 560.0:
		return
	los_t -= delta
	if los_t <= 0.0:
		los_t = 0.18 + randf() * 0.12
		can_see = p != null and not p.dead and dist < sight and world.line_clear(center(), p.center())
		if can_see:
			aggro = 4.0
	aggro = maxf(0.0, aggro - delta)
	ai(delta, p, dist)
	physics_move(delta, game.dim_gravity)
	env_effects(delta)
	touch_cd -= delta
	if touch_cd <= 0.0 and p and not p.dead and hit_rect().intersects(p.hit_rect()):
		touch_cd = 0.7
		p.take_damage(contact_damage, display_name, (p.center() - center()).normalized() * 110.0 + Vector2(0, -50), "melee")
		on_touch_player(p)
	if sprite:
		sprite.flip_h = face < 0
		var m := tint
		if hurt_flash > 0.0:
			m = Color(3, 3, 3)
		elif burning > 0.0:
			m = tint * Color(1.5, 0.8, 0.6)
		elif chilled > 0.0:
			m = tint * Color(0.7, 0.9, 1.4)
		sprite.modulate = m
	if burning > 0.0:
		game.add_light(position, 30.0, Color(1.0, 0.5, 0.15) * 0.6)
	elif dist < 260.0:
		game.add_light(position, 16.0 + hh, Color(0.75, 0.7, 0.9) * 0.3)


func take_damage(amount: float, source: String, knock: Vector2 = Vector2.ZERO, kind_: String = "") -> void:
	if dead:
		return
	knock *= 1.0 - knock_resist
	super.take_damage(amount, source, knock, kind_)
	aggro = 5.0
	can_see = true
	if amount >= 1.0:
		game.floating_text(position + Vector2(0, -hh - 6), str(int(round(amount))), Color("fff2c0"), true)
		if kind_ != "env" and kind_ != "fire":
			Audio.play_at("hit_enemy", position, -6.0)
		if game.particles:
			for k in mini(6, 1 + int(amount / 4.0)):
				game.particles.spawn_material(center(), Vector2(randf_range(-60, 60), randf_range(-90, -10)), bleeds if randf() < 0.5 else 0, Mat.BLOOD if bleeds == Mat.BLOOD else Mat.SLUDGE)


func die(source: String) -> void:
	dead = true
	death_t = 0.0
	play("death")
	Audio.play_at("enemy_die", position, -2.0)
	game.on_enemy_killed(self, source)
	if gold > 0:
		game.spawn_gold(center(), gold)
	if kind == "caster" and randf() < 0.22:
		var sp := game.spawn_pickup("spell", center(), Spells.random_spell(randi(), level))
		sp.vel = Vector2(randf_range(-30, 30), -80)
	if game.particles:
		for k in 14:
			game.particles.spawn_material(center(), Vector2(randf_range(-90, 90), randf_range(-140, -20)), bleeds if k % 2 == 0 else 0, Mat.BLOOD if bleeds == Mat.BLOOD else Mat.SLUDGE)
	_on_death()


func _on_death() -> void:
	pass


func dir_to(p: Player) -> Vector2:
	return (p.center() - center()).normalized()


## Ground walker helper: true if there is ground ahead in direction d.
func ground_ahead(d: int) -> bool:
	var x := bx + hw + d * (hw + 2)
	var y := by + hh * 2
	for k in 6:
		if world.is_solid_at(x, y + k):
			return true
	return false


func blocked_ahead(d: int) -> bool:
	var x := bx + (hw * 2 if d > 0 else -1)
	return not world.col_free(x, by, by + hh * 2 - 4)
